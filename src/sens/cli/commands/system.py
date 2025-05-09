"""System-related CLI commands for debugging, metrics, and status."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Dict, List, Optional

import structlog
from tabulate import tabulate

from sens.chat.orchestrator import ChatOrchestrator
from sens.cli.metrics_store import MetricsStore
from sens.monitoring.metrics import PipelineMetrics
from sens.retrieval.embedding.search import EmbeddingSearch
from sens.retrieval.token.builder import TokenIndexBuilder
from sens.schema.graph import SchemaGraph
from sens.settings import get_settings

log = structlog.get_logger()


class SystemStatus:
    """System status checker."""

    def __init__(self):
        """Initialize system status checker."""
        self.settings = get_settings()
        self.schema_graph = SchemaGraph.get_instance()

    def check_schema(self) -> Dict:
        """Check schema status."""
        schema_path = self.settings.schema_path
        status = {
            "exists": schema_path.exists(),
            "path": str(schema_path),
            "size": schema_path.stat().st_size if schema_path.exists() else 0,
            "modified": (
                datetime.fromtimestamp(schema_path.stat().st_mtime, UTC).isoformat()
                if schema_path.exists()
                else None
            ),
        }

        if status["exists"]:
            tables = self.schema_graph.list_all_tables()
            status.update(
                {
                    "table_count": len(tables),
                    "tables": tables,
                }
            )

        return status

    def check_indices(self) -> Dict:
        """Check search indices status."""
        index_dir = self.settings.index_dir
        token_index = TokenIndexBuilder()
        embedding_search = EmbeddingSearch()

        status = {
            "index_dir": {
                "path": str(index_dir),
                "exists": index_dir.exists(),
            },
            "token_index": {
                "ready": token_index.index is not None,
            },
            "embedding_index": {
                "ready": embedding_search.index is not None,
            },
        }

        return status

    def check_database(self) -> Dict:
        """Check database connection and status."""
        from sens.execution import SQLExecutor

        executor = SQLExecutor()
        try:
            # Test connection with simple query
            result = executor.execute("SELECT 1")
            connected = result.error is None
        except Exception:
            connected = False

        return {
            "connected": connected,
            "url": self.settings.db_url.replace_secret_fields(),  # Hide sensitive parts
        }

    def get_full_status(self) -> Dict:
        """Get complete system status."""
        return {
            "schema": self.check_schema(),
            "indices": self.check_indices(),
            "database": self.check_database(),
            "settings": self.settings.model_dump(exclude_secrets=True),
        }


def handle_debug(args) -> None:
    """Handle debug command.

    Args:
        args: Command line arguments
    """
    try:
        # Get conversation history if ID provided
        if args.conversation_id:
            orchestrator = ChatOrchestrator(conversation_id=args.conversation_id)
            state = orchestrator.state
            if not state or not state.interactions:
                print(f"No conversation found with ID: {args.conversation_id}")
                return

            print(f"Conversation {args.conversation_id}:")
            print(f"Total interactions: {len(state.interactions)}")
            print("\nInteractions:")
            for i, interaction in enumerate(state.interactions, 1):
                print(f"\n[{i}] User: {interaction.user_input}")
                if interaction.intent:
                    print(f"Intent: {interaction.intent.query_type}")
                    print(f"Confidence: {interaction.intent.confidence}")
                    print(f"Tables: {', '.join(interaction.intent.tables)}")
                if interaction.response:
                    status = interaction.response.get("status", "unknown")
                    if status == "success":
                        print(
                            f"Response: {interaction.response.get('summary', 'No summary')}"
                        )
                    else:
                        print(
                            f"Response: {status} - {interaction.response.get('message', 'No message')}"
                        )

        # Show component status
        if args.component:
            status = SystemStatus()
            if args.component == "schema":
                result = status.check_schema()
            elif args.component == "indices":
                result = status.check_indices()
            elif args.component == "database":
                result = status.check_database()
            else:
                print(f"Unknown component: {args.component}")
                return

            print(json.dumps(result, indent=2))
            return

        # Default to full system status
        status = SystemStatus()
        result = status.get_full_status()
        print(json.dumps(result, indent=2))

    except Exception as e:
        log.error("debug_command_failed", error=str(e))
        print(f"Error: {e}")


def handle_metrics(args) -> None:
    """Handle metrics command.

    Args:
        args: Command line arguments
    """
    try:
        if args.conversation_id:
            # Show metrics for specific conversation
            orchestrator = ChatOrchestrator(conversation_id=args.conversation_id)
            state = orchestrator.state
            if not state or not state.interactions:
                print(f"No conversation found with ID: {args.conversation_id}")
                return

            metrics_list = []
            for interaction in state.interactions:
                if interaction.response and "metadata" in interaction.response:
                    meta = interaction.response["metadata"]
                    if "pipeline_metrics" in meta:
                        metrics = meta["pipeline_metrics"]
                        metrics_list.append(
                            {
                                "success": metrics.get("success", False),
                                "duration_ms": metrics.get("total_duration_ms", 0),
                                "step_count": len(metrics.get("steps", [])),
                                "error": metrics.get("error"),
                            }
                        )

            if not metrics_list:
                print("No metrics found for this conversation")
                return

            # Calculate statistics
            success_count = sum(1 for m in metrics_list if m["success"])
            total_duration = sum(m["duration_ms"] for m in metrics_list)
            avg_duration = total_duration / len(metrics_list)

            print(f"\nMetrics for conversation {args.conversation_id}:")
            print(f"Total interactions: {len(metrics_list)}")
            print(f"Successful: {success_count}/{len(metrics_list)}")
            print(f"Average duration: {avg_duration:.2f}ms")
            print(f"Total duration: {total_duration:.2f}ms")

            if args.detailed:
                print("\nDetailed metrics:")
                headers = ["Success", "Duration (ms)", "Steps", "Error"]
                rows = [
                    [
                        "✓" if m["success"] else "✗",
                        f"{m['duration_ms']:.2f}",
                        m["step_count"],
                        m["error"] or "-",
                    ]
                    for m in metrics_list
                ]
                print(tabulate(rows, headers=headers, tablefmt="grid"))

        else:
            # Show system-wide metrics
            metrics_store = MetricsStore()
            summary = metrics_store.get_summary()
            print("\nSystem-wide CLI Metrics:")
            print(f"  Created:      {summary['created_at']}")
            print(f"  Last updated: {summary['last_updated']}")
            print(f"  Total commands: {summary['total_commands']}")
            print(f"  Errors:         {summary['errors']}")
            print("  Command counts:")
            for cmd, count in summary["commands"].items():
                print(f"    {cmd}: {count}")

    except Exception as e:
        log.error("metrics_command_failed", error=str(e))
        print(f"Error: {e}")


def handle_status(args) -> None:
    """Handle status command.

    Args:
        args: Command line arguments
    """
    try:
        status = SystemStatus()
        result = status.get_full_status()

        if args.json:
            print(json.dumps(result, indent=2))
            return

        # Format status as human-readable output
        print("Sens System Status")
        print("=================")

        # Schema status
        schema = result["schema"]
        print("\nSchema:")
        print(f"  Path: {schema['path']}")
        print(f"  Status: {'✓ Ready' if schema['exists'] else '✗ Not found'}")
        if schema["exists"]:
            print(f"  Tables: {schema['table_count']}")
            print(f"  Last modified: {schema['modified']}")

        # Indices status
        indices = result["indices"]
        print("\nSearch Indices:")
        print(f"  Directory: {indices['index_dir']['path']}")
        print(
            f"  Token Index: {'✓ Ready' if indices['token_index']['ready'] else '✗ Not ready'}"
        )
        print(
            f"  Embedding Index: {'✓ Ready' if indices['embedding_index']['ready'] else '✗ Not ready'}"
        )

        # Database status
        db = result["database"]
        print("\nDatabase:")
        print(
            f"  Connection: {'✓ Connected' if db['connected'] else '✗ Not connected'}"
        )
        print(f"  URL: {db['url']}")

        # Settings overview
        settings = result["settings"]
        print("\nSettings:")
        for key, value in settings.items():
            if isinstance(value, (str, int, float, bool)):
                print(f"  {key}: {value}")

    except Exception as e:
        log.error("status_command_failed", error=str(e))
        print(f"Error: {e}")
