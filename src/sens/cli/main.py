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
import json
import logging
import sys
from pathlib import Path
from typing import Optional, Set

import structlog

from sens.settings import get_settings
from sens.validation.sql_validator import SchemaContext, SQLValidator, ValidationLevel

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


async def handle_nl2sql(args: argparse.Namespace) -> None:
    """Handle natural language to SQL conversion command.

    Args:
        args: Command line arguments
    """
    try:
        # Import here to avoid loading dependencies unless needed
        from sens.cli.nl2sql import NL2SQLPipeline

        pipeline = NL2SQLPipeline()
        await pipeline.initialize()

        if args.interactive:
            print("Enter your questions (Ctrl+D or Ctrl+C to exit):")
            while True:
                try:
                    question = input("\nQuestion> ").strip()
                    if not question:
                        continue

                    result = await pipeline.process_question(
                        question=question,
                        k=args.k,
                    )
                    print("\nResult:")
                    print(json.dumps(result, indent=2 if args.pretty else None))

                except (EOFError, KeyboardInterrupt):
                    print("\nExiting interactive mode...")
                    break
                except Exception as e:
                    print(f"\nError: {e}")
        else:
            result = await pipeline.process_question(
                question=args.question,
                k=args.k,
            )
            print(json.dumps(result, indent=2 if args.pretty else None))

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
        schema = extractor.extract_and_save(output_path=schema_path)

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
        # Import schema-related components only when needed
        from sens.schema.graph import SchemaGraph
        from sens.schema.schema_extractor import SchemaExtractor

        # Get schema context
        schema_graph = SchemaGraph.get_instance()
        tables = schema_graph.list_all_tables()
        columns_per_table = {
            table: set(schema_graph.get_table_columns(table)) for table in tables
        }
        schema = SchemaContext(tables=set(tables), columns_per_table=columns_per_table)

        # Initialize validator with options
        validator = SQLValidator(
            whitelisted_keywords=set(args.allow or []),
            require_where_for_updates=not args.allow_unfiltered,
        )

        # Determine validation levels
        levels: Set[ValidationLevel] = set()
        if args.syntax:
            levels.add(ValidationLevel.SYNTAX)
        if args.schema:
            levels.add(ValidationLevel.SCHEMA)
        if args.safety:
            levels.add(ValidationLevel.SAFETY)
        if not levels:  # If no specific levels, validate all
            levels.add(ValidationLevel.ALL)

        # Read SQL input
        if args.file:
            with open(args.file) as f:
                sql = f.read()
        else:
            sql = args.sql

        # Validate SQL
        result = validator.validate(sql, schema, levels)

        # Output results
        if args.json:
            output = {
                "valid": result.is_valid,
                "errors": [
                    {
                        "level": error.level.name,
                        "message": error.message,
                        "details": error.details,
                    }
                    for error in result.errors
                ],
                "warnings": result.warnings,
            }
            print(json.dumps(output, indent=2 if args.pretty else None))
        else:
            print(str(result))

        if not result.is_valid:
            sys.exit(1)

    except Exception as e:
        log.error("sql_validation_failed", error=str(e))
        sys.exit(1)


def handle_execute(args: argparse.Namespace) -> None:
    """Handle SQL execution command.

    Args:
        args: Command line arguments
    """
    try:
        from sens.execution import SQLExecutor
        from sens.execution.types import serialize_value

        # Initialize executor
        executor = SQLExecutor()

        # Get SQL input
        if args.file:
            with open(args.file) as f:
                sql = f.read().strip()
        else:
            sql = args.sql.strip()

        if not sql:
            log.error("empty_sql_input")
            sys.exit(1)

        # Execute query
        result = executor.execute(sql)

        # Format output
        if args.pretty:
            # Pretty print table format
            if not result.error and result.columns:
                # Calculate column widths
                widths = [len(col) for col in result.columns]
                for row in result.rows:
                    for i, val in enumerate(row):
                        # Serialize value before calculating width
                        str_val = str(serialize_value(val))
                        widths[i] = max(widths[i], len(str_val))

                # Print header
                header = " | ".join(
                    f"{col:{widths[i]}}" for i, col in enumerate(result.columns)
                )
                print(header)
                print("-" * len(header))

                # Print rows
                for row in result.rows:
                    print(
                        " | ".join(
                            f"{str(serialize_value(val)):{widths[i]}}"
                            for i, val in enumerate(row)
                        )
                    )

                print(f"\nTotal rows: {result.row_count}")
            else:
                print(json.dumps(result.to_dict(), indent=2))
        else:
            print(json.dumps(result.to_dict()))

    except Exception as e:
        log.error("sql_execution_failed", error=str(e))
        sys.exit(1)


def main() -> None:
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Sens - Semantic Natural SQL CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Global options
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # nl2sql command
    nl2sql_parser = subparsers.add_parser(
        "nl2sql",
        help="Convert natural language to SQL",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    nl2sql_parser.add_argument(
        "-q",
        "--question",
        type=str,
        help="Natural language question to convert",
    )
    nl2sql_parser.add_argument(
        "-k",
        type=int,
        default=5,
        help="Number of top results to retrieve",
    )
    nl2sql_parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Enter interactive mode for multiple queries",
    )
    nl2sql_parser.add_argument(
        "-p",
        "--pretty",
        action="store_true",
        help="Pretty print JSON output",
    )

    # extract-schema command
    extract_parser = subparsers.add_parser(
        "extract-schema",
        help="Extract database schema to JSON",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    extract_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output path for schema JSON",
    )

    # build-index command
    build_parser = subparsers.add_parser(
        "build-index",
        help="Build embedding search index",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    build_parser.add_argument(
        "-s",
        "--schema",
        type=Path,
        help="Input schema JSON path",
    )
    build_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output directory for index files",
    )

    # validate command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate SQL queries",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    sql_group = validate_parser.add_mutually_exclusive_group(required=True)
    sql_group.add_argument(
        "-s",
        "--sql",
        type=str,
        help="SQL query to validate",
    )
    sql_group.add_argument(
        "-f",
        "--file",
        type=Path,
        help="File containing SQL query",
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
        "--json",
        action="store_true",
        help="Output results in JSON format",
    )
    validate_parser.add_argument(
        "-p",
        "--pretty",
        action="store_true",
        help="Pretty print output",
    )

    # SQL execution
    execute_parser = subparsers.add_parser("execute", help="Execute SQL query")
    execute_parser.add_argument("sql", nargs="?", help="SQL query to execute")
    execute_parser.add_argument("-f", "--file", type=Path, help="Read SQL from file")
    execute_parser.add_argument(
        "--pretty", action="store_true", help="Pretty print output in table format"
    )

    args = parser.parse_args()

    # Configure logging
    setup_logging(args.verbose)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "nl2sql":
            if not args.question and not args.interactive:
                nl2sql_parser.error(
                    "either --question or --interactive must be specified"
                )
            asyncio.run(handle_nl2sql(args))
        elif args.command == "extract-schema":
            handle_extract_schema(args)
        elif args.command == "build-index":
            handle_build_index(args)
        elif args.command == "validate":
            if not args.sql and not args.file:
                validate_parser.error("either SQL query or --file is required")
            handle_validate(args)
        elif args.command == "execute":
            if not args.sql and not args.file:
                execute_parser.error("either SQL query or --file is required")
            handle_execute(args)

    except Exception as e:
        log.error("command_failed", command=args.command, error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
