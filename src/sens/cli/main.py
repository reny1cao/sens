#!/usr/bin/env python3
"""Main CLI entry point for Sens.

This module provides a command-line interface for all Sens operations including:
- Natural language to SQL conversion
- Schema extraction and management
- Embedding index building
- Interactive query mode
- SQL validation
"""

import argparse
import asyncio
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Optional, Set

import structlog

from sens.chat.orchestrator import ChatOrchestrator
from sens.chat.session import SessionManager
from sens.cli.enhanced_pipeline import EnhancedNL2SQLPipeline
from sens.cli.formatters import format_nl2sql_response
from sens.execution import SQLExecutor
from sens.schema.context import ValidatorSchemaContext
from sens.schema.graph import SchemaGraph
from sens.settings import get_settings
from sens.validation.sql_validator import SQLValidator, ValidationLevel

# Configure structured logging
log = structlog.get_logger()


def setup_logging(verbose: bool = False) -> None:
    """Configure logging level and format.

    Args:
        verbose: If True, set logging level to DEBUG
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def check_redis_availability(session_id: Optional[str] = None) -> None:
    """Check Redis availability if session persistence is needed.

    Args:
        session_id: Optional session ID. If provided and Redis is unavailable,
                   the function will exit with an error.
    """
    if session_id:
        session_manager = SessionManager()
        if not session_manager.redis_available:
            log.error(
                "redis_unavailable",
                error="Cannot connect to session store. Session persistence requires Redis.",
                session_id=session_id,
            )
            sys.exit(1)


async def handle_nl2sql(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> None:
    """Handle natural language to SQL conversion command.

    Args:
        args: Command line arguments
        parser: The argument parser instance
    """
    try:
        # Check Redis availability if session ID is provided
        check_redis_availability(args.session_id)

        # Initialize enhanced pipeline with options
        pipeline = EnhancedNL2SQLPipeline(
            session_id=args.session_id,
            metrics_enabled=args.metrics,
            debug_mode=args.debug,
        )

        # Print session ID at start
        if args.session_id:
            print(f"Using existing session: {args.session_id}")
        else:
            print(f"Created new session: {pipeline.session_id}")

        if args.interactive:
            print("Enter your questions (Ctrl+D or Ctrl+C to exit):")
            while True:
                try:
                    question = input("\nQuestion> ").strip()
                    if not question:
                        continue

                    result = await pipeline.process_question(
                        question=question,
                        format_type=args.format,
                        show_preview=not args.no_preview,
                        max_rows=args.max_rows,
                    )
                    print("\nResult:")
                    formatted = format_nl2sql_response(
                        result,
                        format=args.format,
                        show_preview=not args.no_preview,
                        max_rows=args.max_rows,
                        pretty=args.pretty,
                        show_metrics=args.metrics,
                        show_debug=args.debug,
                    )
                    print(formatted)

                except (EOFError, KeyboardInterrupt):
                    print("\nExiting interactive mode...")
                    break
                except Exception as e:
                    print(f"\nError: {e}")
        else:
            if not args.question:
                parser.error("either --question or --interactive must be specified")

            result = await pipeline.process_question(
                question=args.question,
                format_type=args.format,
                show_preview=not args.no_preview,
                max_rows=args.max_rows,
            )
            formatted = format_nl2sql_response(
                result,
                format=args.format,
                show_preview=not args.no_preview,
                max_rows=args.max_rows,
                pretty=args.pretty,
                show_metrics=args.metrics,
                show_debug=args.debug,
            )
            print(formatted)

    except Exception as e:
        log.error("nl2sql_command_failed", error=str(e))
        sys.exit(1)


def handle_extract_schema(args: argparse.Namespace) -> None:
    """Handle schema extraction command.

    Args:
        args: Command line arguments
    """
    try:
        # Import here to avoid loading dependencies unless needed
        from sens.schema.schema_extractor import SchemaExtractor

        settings = get_settings()
        schema_path = args.output or settings.schema_path

        # Ensure output directory exists
        schema_path.parent.mkdir(parents=True, exist_ok=True)

        extractor = SchemaExtractor()
        schema = extractor.extract_and_save(config_dir=str(schema_path.parent))

        log.info(
            "schema_extracted",
            output_path=str(schema_path),
            table_count=len(schema.tables),
            relationship_count=len(schema.relationships),
        )

    except Exception as e:
        log.error("schema_extraction_failed", error=str(e))
        sys.exit(1)


def handle_build_index(args: argparse.Namespace) -> None:
    """Handle embedding index building command.

    Args:
        args: Command line arguments
    """
    try:
        # Import here to avoid loading dependencies unless needed
        from sens.retrieval.embedding.search import EmbeddingSearch

        settings = get_settings()
        schema_path = args.schema or settings.schema_path
        index_dir = args.output or settings.index_dir

        if not schema_path.exists():
            log.error("schema_file_not_found", path=str(schema_path))
            sys.exit(1)

        # Ensure index directory exists
        index_dir.mkdir(parents=True, exist_ok=True)

        searcher = EmbeddingSearch(index_dir=str(index_dir))
        searcher.build_index(schema_path=str(schema_path))

        log.info(
            "embedding_index_built",
            schema_path=str(schema_path),
            index_dir=str(index_dir),
        )

    except Exception as e:
        log.error("index_build_failed", error=str(e))
        sys.exit(1)


def handle_validate(args: argparse.Namespace) -> None:
    """Handle SQL validation command.

    Args:
        args: Command line arguments
    """
    try:
        # Get schema context
        schema_graph = SchemaGraph.get_instance()

        # Convert schema graph to validator context for full schema
        full_schema = ValidatorSchemaContext(
            tables=set(schema_graph.list_all_tables()),
            columns_per_table={
                table: set(schema_graph.get_table_columns(table))
                for table in schema_graph.list_all_tables()
            },
            metadata=(
                schema_graph._schema_data.metadata
                if schema_graph._schema_data
                else None
            ),
        )

        # If a prompted schema file is provided, load it
        prompted_schema = None
        if args.prompted_schema:
            with open(args.prompted_schema, "r") as f:
                prompted_data = json.load(f)
                prompted_schema = ValidatorSchemaContext(
                    tables=set(prompted_data["tables"]),
                    columns_per_table={
                        table: set(columns)
                        for table, columns in prompted_data["columns_per_table"].items()
                    },
                )

        # Initialize validator with options
        validator = SQLValidator(
            whitelisted_keywords=set(args.allow or []),
            require_where_for_updates=not args.allow_unfiltered,
        )

        # Read SQL from file or argument
        sql = None
        if args.file:
            with open(args.file, "r") as f:
                sql = f.read().strip()
        else:
            sql = args.sql.strip()

        if not sql:
            log.error("empty_sql_input")
            sys.exit(1)

        # Determine validation levels
        levels = set()
        if args.syntax:
            levels.add(ValidationLevel.SYNTAX)
        if args.schema:
            levels.add(ValidationLevel.SCHEMA)
        if args.safety:
            levels.add(ValidationLevel.SAFETY)
        if not levels:  # If no specific levels, validate all
            levels.add(ValidationLevel.ALL)

        # Generate a query ID for logging
        query_id = hashlib.md5(sql.encode()).hexdigest()[:8]

        # Validate SQL
        validation_result = validator.validate(
            sql=sql,
            full_schema=full_schema,
            prompted_schema=prompted_schema,
            query_id=query_id,
            levels=levels,
        )

        # Print validation result
        print(validation_result)

        # Print context bypass information if available
        if (
            validation_result.context_bypass_info
            and validation_result.context_bypass_info.is_bypass
        ):
            print("\nContext Bypass Analysis:")
            print(f"Score: {validation_result.context_bypass_info.bypass_score:.2%}")
            print("Columns used but not in prompted schema:")
            for (
                table,
                column,
            ) in validation_result.context_bypass_info.used_but_missing_columns:
                print(f"  - {table}.{column}")

        sys.exit(0 if validation_result.is_valid else 1)

    except Exception as e:
        log.error("validation_failed", error=str(e))
        sys.exit(1)


def handle_execute(args: argparse.Namespace) -> None:
    """Handle SQL execution command.

    Args:
        args: Command line arguments
    """
    try:
        # Read SQL from file or stdin
        sql = args.sql
        if args.file:
            with open(args.file, "r") as f:
                sql = f.read()

        # Execute SQL
        executor = SQLExecutor()
        result = executor.execute(sql)

        if result.error:
            print(f"Error executing SQL: {result.error}")
            sys.exit(1)

        # Format output
        if args.json:
            output = {
                "columns": result.columns,
                "rows": result.rows,
                "row_count": result.row_count,
            }
            print(json.dumps(output, indent=2))
        else:
            from tabulate import tabulate

            print(tabulate(result.rows, headers=result.columns, tablefmt="grid"))
            print(f"\nTotal rows: {result.row_count}")

    except Exception as e:
        log.error("execution_failed", error=str(e))
        sys.exit(1)


def main() -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Sens - Natural language to SQL conversion"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # NL2SQL command
    nl2sql_parser = subparsers.add_parser(
        "nl2sql", help="Convert natural language to SQL"
    )
    nl2sql_parser.add_argument(
        "-q", "--question", help="Natural language question to convert"
    )
    nl2sql_parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Start interactive mode",
    )
    nl2sql_parser.add_argument(
        "-f",
        "--format",
        choices=["json", "table", "summary"],
        default="json",
        help="Output format",
    )
    nl2sql_parser.add_argument(
        "--no-preview",
        action="store_true",
        help="Don't show result preview",
    )
    nl2sql_parser.add_argument(
        "--max-rows",
        type=int,
        default=5,
        help="Maximum preview rows",
    )
    nl2sql_parser.add_argument(
        "-p", "--pretty", action="store_true", help="Pretty print output"
    )
    nl2sql_parser.add_argument(
        "-m", "--metrics", action="store_true", help="Include metrics in output"
    )
    nl2sql_parser.add_argument(
        "-d", "--debug", action="store_true", help="Include debug info in output"
    )
    nl2sql_parser.add_argument(
        "-s",
        "--session-id",
        help="Session ID for conversation continuity. If not provided, a new session will be created.",
    )

    # Schema extraction command
    extract_parser = subparsers.add_parser(
        "extract-schema", help="Extract database schema"
    )
    extract_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output path for schema file",
    )

    # Index building command
    build_parser = subparsers.add_parser("build-index", help="Build embedding index")
    build_parser.add_argument(
        "-s",
        "--schema",
        type=Path,
        help="Path to schema file",
    )
    build_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output directory for index",
    )

    # SQL validation command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate SQL queries",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    sql_group = validate_parser.add_mutually_exclusive_group(required=True)
    sql_group.add_argument(
        "sql",
        nargs="?",
        help="SQL query to validate",
    )
    sql_group.add_argument(
        "-f",
        "--file",
        type=Path,
        help="Read SQL from file",
    )
    validate_parser.add_argument(
        "--syntax",
        action="store_true",
        help="Validate syntax only",
    )
    validate_parser.add_argument(
        "--schema",
        action="store_true",
        help="Validate schema only",
    )
    validate_parser.add_argument(
        "--safety",
        action="store_true",
        help="Validate safety only",
    )
    validate_parser.add_argument(
        "--allow",
        nargs="+",
        help="Whitelist specific SQL keywords",
    )
    validate_parser.add_argument(
        "--allow-unfiltered",
        action="store_true",
        help="Allow UPDATE/DELETE without WHERE clause",
    )
    validate_parser.add_argument(
        "-j",
        "--json",
        action="store_true",
        help="Output in JSON format",
    )
    validate_parser.add_argument(
        "-p",
        "--pretty",
        action="store_true",
        help="Pretty print JSON output",
    )
    validate_parser.add_argument(
        "-ps",
        "--prompted-schema",
        type=Path,
        help="Path to prompted schema file",
    )

    # SQL execution command
    execute_parser = subparsers.add_parser("execute", help="Execute SQL")
    execute_parser.add_argument("sql", nargs="?", help="SQL to execute")
    execute_parser.add_argument("-f", "--file", type=Path, help="Read SQL from file")
    execute_parser.add_argument(
        "-j", "--json", action="store_true", help="Output in JSON format"
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "nl2sql":
        asyncio.run(handle_nl2sql(args, parser))
    elif args.command == "extract-schema":
        handle_extract_schema(args)
    elif args.command == "build-index":
        handle_build_index(args)
    elif args.command == "validate":
        handle_validate(args)
    elif args.command == "execute":
        handle_execute(args)


if __name__ == "__main__":
    main()
