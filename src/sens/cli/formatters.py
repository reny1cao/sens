"""Response formatting utilities for CLI output."""

import json
from typing import Any, Dict, List, Optional

from tabulate import tabulate


def _format_json_response(
    result: Dict[str, Any], pretty: bool = False, show_preview: bool = True
) -> str:
    """Format response as JSON."""
    if not show_preview and "result" in result:
        # Remove preview but keep row count and columns
        preview = result["result"].pop("preview", None)
        if preview is not None:
            result["result"]["preview_hidden"] = True

    return json.dumps(result, indent=2 if pretty else None)


def _format_table_response(
    result: Dict[str, Any],
    max_rows: int = 5,
    show_preview: bool = True,
) -> str:
    """Format response with table preview."""
    output = []

    # Add summary if available
    if "summary" in result:
        output.append(f"Summary: {result['summary']}\n")

    # Add SQL query
    if "sql" in result:
        output.append(f"SQL: {result['sql']}\n")

    # Add result preview
    if show_preview and "result" in result and result["result"].get("preview"):
        preview = result["result"]["preview"][:max_rows]
        columns = result["result"].get("columns", [])
        if preview and columns:
            output.append("Results:")
            output.append(tabulate(preview, headers=columns, tablefmt="grid"))
            total_rows = result["result"].get("row_count", 0)
            if total_rows > len(preview):
                output.append(f"\n(Showing {len(preview)} of {total_rows} rows)")

    # Add metadata
    if "metadata" in result:
        meta = result["metadata"]
        output.append("\nMetadata:")
        output.append(f"- Intent Type: {meta.get('intent_type', 'unknown')}")
        output.append(f"- Tables Used: {', '.join(meta.get('tables_used', []))}")
        output.append(f"- Generation Time: {meta.get('generation_ms', 0):.0f}ms")
        output.append(f"- Execution Time: {meta.get('execution_ms', 0):.0f}ms")

    return "\n".join(output)


def _format_summary_response(result: Dict[str, Any]) -> str:
    """Format response with just the summary."""
    if result.get("status") == "error":
        return f"Error: {result.get('message', 'Unknown error')}"
    elif result.get("status") == "clarification_needed":
        return f"Clarification needed: {result.get('message', 'Please provide more details')}"
    else:
        return result.get("summary", "No summary available")


def format_nl2sql_response(
    result: Dict[str, Any],
    format: str = "json",
    show_preview: bool = True,
    max_rows: int = 5,
    pretty: bool = False,
) -> str:
    """
    Format NL2SQL response according to specified format.

    Args:
        result: The response dictionary from NL2SQL pipeline
        format: Output format ("json", "table", or "summary")
        show_preview: Whether to include result preview
        max_rows: Maximum number of preview rows to show
        pretty: Whether to pretty-print JSON output

    Returns:
        Formatted string representation of the response
    """
    if result.get("status") == "error":
        # Always show errors in a consistent format
        return f"Error: {result.get('message', 'Unknown error')}"
    elif result.get("status") == "clarification_needed":
        return f"Clarification needed: {result.get('message', 'Please provide more details')}"

    if format == "json":
        return _format_json_response(result, pretty, show_preview)
    elif format == "table":
        return _format_table_response(result, max_rows, show_preview)
    elif format == "summary":
        return _format_summary_response(result)
    else:
        raise ValueError(f"Unknown format: {format}")
