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
from sens.cli.commands.config import handle_config_command
from sens.cli.enhanced_pipeline import EnhancedNL2SQLPipeline
from sens.cli.formatters import format_nl2sql_response
from sens.execution import SQLExecutor
from sens.schema.context import ValidatorSchemaContext
from sens.schema.graph import SchemaGraph
from sens.settings import get_settings, reload_settings
from sens.validation.sql_validator import SQLValidator, ValidationLevel


def setup_logging(verbose: bool = False) -> structlog.BoundLogger:
    """Configure logging level and format.

    Args:
        verbose: If True, set logging level to DEBUG

    Returns:
        A configured logger instance
    """
    from sens.api.common.logging import configure_logging
    from sens.settings import get_settings

    # Get current settings
    settings = get_settings()

    # Update logging configuration with verbose flag
    settings.update_logging(verbose=verbose)

    # Force reconfigure structlog with updated settings
    configure_logging(force=True)

    # Get logger after configuration
    log = structlog.get_logger(__name__)
    log.info(
        "cli_logging_configured",
        level=settings.logging.level,
        format=settings.logging.format,
        colors_enabled=settings.logging.enable_colors,
        environment=settings.environment,
        verbose_mode=verbose,
    )
    return log


def check_redis_availability(session_id: Optional[str] = None, log=None) -> None:
    """Check Redis availability if session persistence is needed.

    Args:
        session_id: Optional session ID. If provided and Redis is unavailable,
                   the function will exit with an error.
        log: Logger instance to use
    """
    if not log:
        log = structlog.get_logger(__name__)

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
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    log: Optional[structlog.BoundLogger] = None,
) -> None:
    """Handle natural language to SQL conversion command.

    Args:
        args: Command line arguments
        parser: The argument parser instance
        log: Optional logger instance
    """
    if log is None:
        log = structlog.get_logger(__name__)
    try:
        # Check Redis availability if session ID is provided
        check_redis_availability(args.session_id)

        # Choose pipeline based on agent flag
        if args.agent:
            # Use agent-based pipeline
            from sens.cli.agent_pipeline import AgentNL2SQLPipeline

            pipeline = AgentNL2SQLPipeline(
                session_id=args.session_id,
                metrics_enabled=args.metrics,
                debug_mode=args.debug,
                max_iterations=(
                    args.max_iterations if hasattr(args, "max_iterations") else 10
                ),
            )
            print(
                f"🤖 Using Agent mode with up to {pipeline.max_iterations} iterations"
            )
        else:
            # Use regular pipeline
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


async def handle_extract_schema(
    args: argparse.Namespace, log: structlog.BoundLogger
) -> None:
    """Handle schema extraction command.

    Args:
        args: Command line arguments
        log: Logger instance
    """
    try:
        # Use datasource manager for extraction with caching
        import time

        from sens.datasource.manager import DataSourceManager
        from sens.schema.graph import SchemaGraph

        start_time = time.time()
        log.info("extracting_schema_with_cache_support")

        # Force extraction if requested
        if args.force:
            log.info("force_flag_set_clearing_cache")
            from sens.caching.factory import get_cache_manager
            from sens.schema.cache_utils import SchemaCache

            settings = get_settings()
            db_config = {
                "host": settings.db_host,
                "port": settings.db_port,
                "database": settings.db_name,
                "user": settings.db_user,
            }
            cache_key = SchemaCache.get_cache_key("default", db_config)

            cache_manager = get_cache_manager()
            await cache_manager.delete(cache_key)
            log.info("schema_cache_cleared")

        # Extract schema using datasource manager
        datasource_manager = DataSourceManager()
        await datasource_manager.ensure_default_schema_extracted()

        # Verify extraction
        schema_graph = SchemaGraph.get_instance()
        table_count = len(schema_graph._all_tables)

        elapsed_time = time.time() - start_time

        log.info(
            "schema_extracted_successfully",
            table_count=table_count,
            elapsed_seconds=f"{elapsed_time:.2f}",
            cached=not args.force,
        )

        print(f"\nSchema extraction completed:")
        print(f"- Tables found: {table_count}")
        print(f"- Time taken: {elapsed_time:.2f} seconds")
        if not args.force:
            print("- Using cached schema (use --force to re-extract)")

    except Exception as e:
        log.error("schema_extraction_failed", error=str(e))
        sys.exit(1)


async def handle_cache_status(
    args: argparse.Namespace, log: structlog.BoundLogger
) -> None:
    """Handle cache status command.

    Args:
        args: Command line arguments
        log: Logger instance
    """
    try:
        from datetime import datetime

        from sens.caching.factory import get_cache_manager
        from sens.schema.cache_utils import SchemaCache

        settings = get_settings()
        cache_manager = get_cache_manager()

        print("\nCache Configuration:")
        print(f"- Backend: {settings.cache.backend}")
        if settings.cache.backend == "file":
            print(f"- Cache directory: {settings.cache.file_cache_dir}")
        print(f"- Schema TTL: {settings.cache.schema_ttl_hours} hours")

        # Check default schema cache
        db_config = {
            "host": settings.db_host,
            "port": settings.db_port,
            "database": settings.db_name,
            "user": settings.db_user,
        }
        cache_key = SchemaCache.get_cache_key("default", db_config)

        print("\nDefault Schema Cache:")
        cached_schema = await cache_manager.get(cache_key)
        if cached_schema:
            print("- Status: CACHED")
            print(f"- Tables: {len(cached_schema.tables)}")
            if cached_schema.extracted_at:
                age = datetime.utcnow() - cached_schema.extracted_at
                print(f"- Age: {age.total_seconds() / 3600:.1f} hours")
                print(f"- Extracted at: {cached_schema.extracted_at}")

            # Check if needs refresh
            needs_refresh = await SchemaCache.should_refresh_schema(
                cached_schema, max_age_hours=settings.cache.schema_ttl_hours
            )
            print(f"- Needs refresh: {'Yes' if needs_refresh else 'No'}")
        else:
            print("- Status: NOT CACHED")

        # Clear cache if requested
        if args.clear:
            if args.clear == "all":
                await cache_manager.clear()
                print("\nAll cache cleared.")
            elif args.clear == "schema":
                await cache_manager.delete(cache_key)
                print("\nSchema cache cleared.")

    except Exception as e:
        log.error("cache_status_failed", error=str(e))
        sys.exit(1)


def handle_build_index(args: argparse.Namespace, log: structlog.BoundLogger) -> None:
    """Handle embedding index building command.

    Args:
        args: Command line arguments
        log: Logger instance
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


def handle_build_schema_index(
    args: argparse.Namespace, log: structlog.BoundLogger
) -> None:
    """Handle schema index building command.

    Args:
        args: Command line arguments
        log: Logger instance
    """
    try:
        # Import here to avoid loading dependencies unless needed
        from sens.schema.precomputed_index import PrecomputedSchemaIndex

        settings = get_settings()
        schema_path = args.schema or Path(settings.schema_path)

        if not schema_path.exists():
            log.error("schema_file_not_found", path=str(schema_path))
            sys.exit(1)

        # Clear cache if force flag is set
        if args.force:
            cache_dir = Path.home() / ".sens" / "schema_cache"
            cache_file = cache_dir / "precomputed_index.pkl"
            if cache_file.exists():
                cache_file.unlink()
                log.info("cleared_existing_cache")

        # Build pre-computed indexes
        index = PrecomputedSchemaIndex()

        # Log statistics
        log.info(
            "schema_index_built",
            schema_path=str(schema_path),
            table_count=len(index.table_indexes),
            relationship_count=len(index.relationship_index.foreign_keys),
            join_graph_entries=len(index.relationship_index.join_graph),
        )

        # Display summary
        print("\nSchema indexes built successfully!")
        print(f"- Tables indexed: {len(index.table_indexes)}")
        print(f"- Relationships indexed: {len(index.relationship_index.foreign_keys)}")
        print(f"- Join graph entries: {len(index.relationship_index.join_graph)}")

    except Exception as e:
        log.error("schema_index_build_failed", error=str(e))
        sys.exit(1)


def handle_validate(args: argparse.Namespace, log: structlog.BoundLogger) -> None:
    """Handle SQL validation command.

    Args:
        args: Command line arguments
        log: Logger instance
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


def handle_performance(args: argparse.Namespace, log: structlog.BoundLogger) -> None:
    """Handle performance metrics command.

    Args:
        args: Command line arguments
        log: Logger instance
    """
    try:
        from sens.cli.commands.performance import metrics, performance, reset, slowest

        if args.perf_command == "metrics":
            # Convert args to click context
            import click

            ctx = click.Context(metrics)
            ctx.params = {
                "format": args.format,
                "component": args.component,
            }
            metrics.invoke(ctx)
        elif args.perf_command == "slowest":
            import click

            ctx = click.Context(slowest)
            ctx.params = {"top": args.top}
            slowest.invoke(ctx)
        elif args.perf_command == "reset":
            import click

            ctx = click.Context(reset)
            reset.invoke(ctx)
        else:
            log.error("unknown_performance_subcommand", command=args.perf_command)
            sys.exit(1)

    except Exception as e:
        log.error("performance_command_failed", error=str(e))
        sys.exit(1)


def handle_execute(args: argparse.Namespace, log: structlog.BoundLogger) -> None:
    """Handle SQL execution command.

    Args:
        args: Command line arguments
        log: Logger instance
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
    nl2sql_parser.add_argument(
        "--agent",
        action="store_true",
        help="Use agent-based reasoning for complex queries (experimental)",
    )
    nl2sql_parser.add_argument(
        "--max-iterations",
        type=int,
        default=10,
        help="Maximum iterations for agent reasoning (only used with --agent)",
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
    extract_parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Force re-extraction (ignore cache)",
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

    # Schema index building command
    build_schema_parser = subparsers.add_parser(
        "build-schema-index",
        help="Build pre-computed schema indexes for optimized retrieval",
    )
    build_schema_parser.add_argument(
        "-s",
        "--schema",
        type=Path,
        help="Path to schema file",
    )
    build_schema_parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Force rebuild even if cache exists",
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

    # Performance metrics command
    perf_parser = subparsers.add_parser("performance", help="View performance metrics")
    perf_subparsers = perf_parser.add_subparsers(
        dest="perf_command", help="Performance subcommands"
    )

    # Performance metrics subcommand
    metrics_parser = perf_subparsers.add_parser(
        "metrics", help="Show performance metrics summary"
    )
    metrics_parser.add_argument(
        "-f",
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format",
    )
    metrics_parser.add_argument("-c", "--component", help="Filter by component")

    # Slowest queries subcommand
    slowest_parser = perf_subparsers.add_parser("slowest", help="Show slowest queries")
    slowest_parser.add_argument(
        "-n", "--top", type=int, default=10, help="Number of queries to show"
    )

    # Reset metrics subcommand
    perf_subparsers.add_parser("reset", help="Reset performance metrics")

    # Configuration command
    config_parser = subparsers.add_parser("config", help="Manage configuration")
    config_subparsers = config_parser.add_subparsers(
        dest="config_command", help="Configuration subcommands"
    )

    # Config set subcommand
    config_set_parser = config_subparsers.add_parser(
        "set", help="Set a configuration value"
    )
    config_set_parser.add_argument("key", help="Configuration key (e.g., api_key)")
    config_set_parser.add_argument("value", help="Configuration value")

    # Config get subcommand
    config_get_parser = config_subparsers.add_parser(
        "get", help="Get configuration value(s)"
    )
    config_get_parser.add_argument(
        "key", nargs="?", help="Optional specific key to get"
    )

    # Financial data management command (handled by click)
    subparsers.add_parser("financial", help="Financial data management", add_help=False)
    # Note: Financial subcommands are handled by click, not argparse

    # Cache management command
    cache_parser = subparsers.add_parser("cache", help="Cache management")
    cache_parser.add_argument(
        "--clear",
        choices=["all", "schema"],
        help="Clear cache (all or just schema)",
    )

    # Handle financial command specially to pass through to click
    if len(sys.argv) > 1 and sys.argv[1] == "financial":
        # Import and run financial commands using click directly
        from sens.cli.commands.financial import financial

        # Remove 'sens' from argv and call financial with remaining args
        sys.argv = ["financial"] + sys.argv[2:]
        financial()
        return

    args = parser.parse_args()

    # Configure logging first, before any other operations
    log = setup_logging(args.verbose)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "nl2sql":
        asyncio.run(handle_nl2sql(args, parser, log))
    elif args.command == "extract-schema":
        asyncio.run(handle_extract_schema(args, log))
    elif args.command == "build-index":
        handle_build_index(args, log)
    elif args.command == "build-schema-index":
        handle_build_schema_index(args, log)
    elif args.command == "validate":
        handle_validate(args, log)
    elif args.command == "execute":
        handle_execute(args, log)
    elif args.command == "performance":
        handle_performance(args, log)
    elif args.command == "config":
        handle_config_command(args, log)
    elif args.command == "cache":
        asyncio.run(handle_cache_status(args, log))
    # Financial command is handled above before argparse


if __name__ == "__main__":
    main()
