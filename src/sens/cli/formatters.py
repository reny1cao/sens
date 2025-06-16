"""Response formatting utilities for CLI output."""

import json
from typing import Any, Dict, List, Optional

from tabulate import tabulate


def format_metrics(metrics: Dict[str, Any], indent: int = 0) -> str:
    """Format pipeline metrics into a readable string.

    Args:
        metrics: Pipeline metrics dictionary
        indent: Number of spaces to indent

    Returns:
        Formatted metrics string
    """
    if not metrics:
        return ""

    lines = []
    pad = " " * indent

    # Format total duration and status
    lines.append(f"{pad}Total Duration: {metrics.get('total_duration_ms', 0):.2f}ms")
    lines.append(f"{pad}Success: {metrics.get('success', False)}")

    # Format steps if present
    steps = metrics.get("steps", [])
    if steps:
        lines.append(f"{pad}Steps:")
        for step in steps:
            lines.append(
                f"{pad}  - {step['name']}: {step.get('duration_ms', 0):.2f}ms "
                f"({'success' if step.get('success') else 'failed'})"
            )
            if step.get("error"):
                lines.append(f"{pad}    Error: {step['error']}")

    # Format error if present
    if metrics.get("error"):
        lines.append(f"{pad}Error: {metrics['error']}")

    return "\n".join(lines)


def format_agent_trace(metadata: Dict[str, Any], indent: int = 0) -> str:
    """Format agent reasoning trace for display.

    Args:
        metadata: Metadata containing agent trace
        indent: Number of spaces to indent

    Returns:
        Formatted agent trace string
    """
    if not metadata or "agent_trace" not in metadata:
        return ""

    trace = metadata["agent_trace"]
    lines = []
    pad = " " * indent

    # Format iterations
    iterations = metadata.get("iterations", 0)
    lines.append(f"{pad}Agent completed in {iterations} iteration(s)")

    # Format thoughts
    if trace.get("thoughts"):
        lines.append(f"\n{pad}Reasoning Steps:")
        for i, thought in enumerate(trace["thoughts"], 1):
            lines.append(f"{pad}  {i}. {thought['content']}")

    # Format actions
    if trace.get("actions"):
        lines.append(f"\n{pad}Actions Taken:")
        for action in trace["actions"]:
            action_type = action["type"]
            params = action.get("parameters", {})
            if params:
                param_str = ", ".join(f"{k}={v}" for k, v in params.items() if v)
                lines.append(f"{pad}  - {action_type}({param_str})")
            else:
                lines.append(f"{pad}  - {action_type}")

    # Format discovered mappings
    if trace.get("key_discoveries", {}).get("value_mappings"):
        mappings = trace["key_discoveries"]["value_mappings"]
        lines.append(f"\n{pad}Discovered Mappings:")
        for user_term, db_value in mappings.items():
            lines.append(f"{pad}  - '{user_term}' → '{db_value}'")

    return "\n".join(lines)


def format_debug_info(debug: Dict[str, Any], indent: int = 0) -> str:
    """Format debug information into a readable string.

    Args:
        debug: Debug information dictionary
        indent: Number of spaces to indent

    Returns:
        Formatted debug string
    """
    if not debug:
        return ""

    lines = []
    pad = " " * indent

    # Format basic info
    lines.append(f"{pad}Debug Information:")
    for key, value in debug.items():
        if isinstance(value, dict):
            lines.append(f"{pad}  {key}:")
            for k, v in value.items():
                lines.append(f"{pad}    {k}: {v}")
        else:
            lines.append(f"{pad}  {key}: {value}")

    return "\n".join(lines)


def _format_json_response(
    result: Dict[str, Any],
    pretty: bool = False,
    show_preview: bool = True,
    show_metrics: bool = False,
    show_debug: bool = False,
) -> str:
    """Format response as JSON."""
    if not show_preview and "result" in result:
        # Remove preview but keep row count and columns
        preview = result["result"].pop("preview", None)
        if preview is not None:
            result["result"]["preview_hidden"] = True

    # Handle metrics and debug info
    if not show_metrics and "metadata" in result:
        result["metadata"].pop("pipeline_metrics", None)

    if not show_debug and "metadata" in result:
        result["metadata"].pop("debug", None)

    return json.dumps(result, indent=2 if pretty else None)


def _format_table_response(
    result: Dict[str, Any],
    show_preview: bool = True,
    max_rows: int = 5,
    show_metrics: bool = False,
    show_debug: bool = False,
) -> str:
    """Format response as a table."""
    lines = []

    # Add summary if present
    if "summary" in result:
        lines.append("Summary:")
        lines.append(result["summary"])
        lines.append("")

    # Add SQL if present
    if "sql" in result:
        lines.append("SQL:")
        lines.append(result["sql"])
        lines.append("")

    # Add preview if enabled and present
    if show_preview and (
        "table_preview" in result
        or ("result" in result and "preview" in result["result"])
    ):
        # Handle both new format (table_preview) and old format (result.preview)
        preview = result.get("table_preview") or result.get("result", {}).get(
            "preview", []
        )
        headers = result.get("columns") or result.get("result", {}).get("columns", [])
        row_count = result.get("row_count") or result.get("result", {}).get(
            "row_count", 0
        )

        if preview:
            lines.append("Preview:")
            table = tabulate(
                preview[:max_rows],
                headers=headers,
                tablefmt="grid",
            )
            lines.append(table)
            lines.append(f"\nShowing {len(preview[:max_rows])} of {row_count} rows")
            lines.append("")

    # Add metrics if enabled
    if (
        show_metrics
        and "metadata" in result
        and "pipeline_metrics" in result["metadata"]
    ):
        lines.append("Metrics:")
        lines.append(format_metrics(result["metadata"]["pipeline_metrics"], indent=2))
        lines.append("")

    # Add debug info if enabled
    if show_debug and "metadata" in result and "debug" in result["metadata"]:
        lines.append(format_debug_info(result["metadata"]["debug"], indent=2))
        lines.append("")

    # Add agent trace if present
    if "metadata" in result and "agent_trace" in result["metadata"]:
        lines.append("Agent Reasoning:")
        lines.append(format_agent_trace(result["metadata"], indent=2))
        lines.append("")

    return "\n".join(lines)


def _format_summary_response(
    result: Dict[str, Any],
    show_metrics: bool = False,
    show_debug: bool = False,
) -> str:
    """Format response as a summary only."""
    lines = []

    # Add summary if present
    if "summary" in result:
        lines.append(result["summary"])

    # Add metrics if enabled
    if (
        show_metrics
        and "metadata" in result
        and "pipeline_metrics" in result["metadata"]
    ):
        lines.append("\nMetrics:")
        lines.append(format_metrics(result["metadata"]["pipeline_metrics"], indent=2))

    # Add debug info if enabled
    if show_debug and "metadata" in result and "debug" in result["metadata"]:
        lines.append("")
        lines.append(format_debug_info(result["metadata"]["debug"], indent=2))

    # Add agent trace if present (compact version for summary)
    if "metadata" in result and "agent_trace" in result["metadata"]:
        iterations = result["metadata"].get("iterations", 0)
        mappings = (
            result["metadata"]
            .get("agent_trace", {})
            .get("key_discoveries", {})
            .get("value_mappings", {})
        )
        if iterations > 0:
            lines.append(f"\n(Agent used {iterations} reasoning steps)")
        if mappings:
            lines.append(f"(Discovered {len(mappings)} value mapping(s))")

    return "\n".join(lines)


def format_nl2sql_response(
    result: Dict[str, Any],
    format: str = "json",
    show_preview: bool = True,
    max_rows: int = 5,
    pretty: bool = False,
    show_metrics: bool = False,
    show_debug: bool = False,
) -> str:
    """Format NL2SQL response according to specified format.

    Args:
        result: The response dictionary to format
        format: Output format (json, table, or summary)
        show_preview: Whether to include result preview
        max_rows: Maximum number of preview rows
        pretty: Whether to pretty-print JSON output
        show_metrics: Whether to include metrics in output
        show_debug: Whether to include debug information

    Returns:
        Formatted response string
    """
    # Handle error responses
    if result.get("status") == "error":
        error_msg = f"Error: {result.get('message', 'Unknown error')}"
        if (
            show_metrics
            and "metadata" in result
            and "pipeline_metrics" in result["metadata"]
        ):
            error_msg += "\n\nMetrics:\n"
            error_msg += format_metrics(
                result["metadata"]["pipeline_metrics"], indent=2
            )
        if show_debug and "metadata" in result and "debug" in result["metadata"]:
            error_msg += "\n\nDebug Info:\n"
            error_msg += format_debug_info(result["metadata"]["debug"], indent=2)
        return error_msg

    # Handle clarification requests
    if result.get("status") == "clarification_needed":
        return f"Clarification needed: {result.get('message', '')}"

    # Format successful responses
    if format == "json":
        return _format_json_response(
            result,
            pretty=pretty,
            show_preview=show_preview,
            show_metrics=show_metrics,
            show_debug=show_debug,
        )
    elif format == "table":
        return _format_table_response(
            result,
            show_preview=show_preview,
            max_rows=max_rows,
            show_metrics=show_metrics,
            show_debug=show_debug,
        )
    elif format == "summary":
        return _format_summary_response(
            result,
            show_metrics=show_metrics,
            show_debug=show_debug,
        )
    else:
        raise ValueError(f"Unsupported format: {format}")
