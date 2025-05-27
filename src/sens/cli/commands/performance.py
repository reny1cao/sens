"""Performance metrics command for SENS CLI."""

import json
from datetime import datetime
from typing import Dict, Optional

import click
import structlog
from rich.console import Console
from rich.table import Table
from rich.text import Text

from sens.monitoring.performance_metrics import get_performance_tracker

log = structlog.get_logger()
console = Console()


@click.group()
def performance():
    """Performance monitoring commands."""
    pass


@performance.command()
@click.option(
    "--format",
    "-f",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format",
)
@click.option(
    "--component",
    "-c",
    help="Filter by specific component",
)
def metrics(format: str, component: Optional[str]):
    """Display performance metrics summary."""
    try:
        tracker = get_performance_tracker()
        summary = tracker.get_performance_summary()

        if format == "json":
            click.echo(json.dumps(summary, indent=2))
        else:
            _display_metrics_table(summary, component)

    except Exception as e:
        log.error("failed_to_get_metrics", error=str(e))
        click.echo(f"Error: {str(e)}", err=True)


def _display_metrics_table(summary: Dict, component_filter: Optional[str]):
    """Display metrics in a formatted table."""
    # Latency table
    if summary.get("latency_percentiles"):
        latency_table = Table(title="Component Latency (ms)")
        latency_table.add_column("Component", style="cyan", no_wrap=True)
        latency_table.add_column("P50", justify="right", style="green")
        latency_table.add_column("P95", justify="right", style="yellow")
        latency_table.add_column("P99", justify="right", style="red")
        latency_table.add_column("Avg", justify="right")
        latency_table.add_column("Count", justify="right")

        for comp, stats in summary["latency_percentiles"].items():
            if component_filter and component_filter not in comp:
                continue
            latency_table.add_row(
                comp,
                f"{stats['p50']:.2f}",
                f"{stats['p95']:.2f}",
                f"{stats['p99']:.2f}",
                f"{stats['avg']:.2f}",
                str(stats["count"]),
            )

        console.print(latency_table)
        console.print()

    # Cache hit rates
    if summary.get("cache_hit_rates"):
        cache_table = Table(title="Cache Hit Rates")
        cache_table.add_column("Cache Type", style="cyan", no_wrap=True)
        cache_table.add_column("Hit Rate", justify="right", style="green")

        for cache_type, hit_rate in summary["cache_hit_rates"].items():
            cache_table.add_row(
                cache_type,
                f"{hit_rate * 100:.1f}%",
            )

        console.print(cache_table)
        console.print()

    # Recall rates
    if summary.get("recall_rates"):
        recall_table = Table(title="Retrieval Recall Rates")
        recall_table.add_column("Metric", style="cyan", no_wrap=True)
        recall_table.add_column("Value", justify="right", style="green")

        recall_data = summary["recall_rates"]
        recall_table.add_row(
            "Table Recall", f"{recall_data.get('table_recall', 0) * 100:.1f}%"
        )
        recall_table.add_row(
            "Column Recall", f"{recall_data.get('column_recall', 0) * 100:.1f}%"
        )
        recall_table.add_row("Sample Count", str(recall_data.get("sample_count", 0)))

        console.print(recall_table)
        console.print()

    # Query complexity
    if summary.get("complexity_stats"):
        complexity_table = Table(title="Query Complexity Statistics")
        complexity_table.add_column("Metric", style="cyan", no_wrap=True)
        complexity_table.add_column("Value", justify="right")

        comp_stats = summary["complexity_stats"]
        complexity_table.add_row(
            "Avg Complexity", f"{comp_stats.get('avg_complexity', 0):.2f}"
        )
        complexity_table.add_row(
            "Max Complexity", f"{comp_stats.get('max_complexity', 0):.2f}"
        )
        complexity_table.add_row(
            "Min Complexity", f"{comp_stats.get('min_complexity', 0):.2f}"
        )
        complexity_table.add_row("Query Count", str(comp_stats.get("query_count", 0)))

        console.print(complexity_table)
        console.print()

    # Time window
    if summary.get("time_window"):
        window = summary["time_window"]
        console.print(
            f"[dim]Metrics collected from {window['start']} to {window['end']}[/dim]"
        )


@performance.command()
@click.option(
    "--top",
    "-n",
    default=10,
    help="Number of slowest queries to show",
)
def slowest(top: int):
    """Show slowest queries by component."""
    try:
        tracker = get_performance_tracker()
        summary = tracker.get_performance_summary()

        if not summary.get("latency_percentiles"):
            click.echo("No latency data available yet.")
            return

        # Find components with highest P99 latencies
        components = []
        for comp, stats in summary["latency_percentiles"].items():
            components.append((comp, stats["p99"], stats["count"]))

        components.sort(key=lambda x: x[1], reverse=True)

        table = Table(title=f"Top {top} Slowest Components (by P99)")
        table.add_column("Component", style="cyan", no_wrap=True)
        table.add_column("P99 Latency (ms)", justify="right", style="red")
        table.add_column("Query Count", justify="right")

        for comp, p99, count in components[:top]:
            table.add_row(comp, f"{p99:.2f}", str(count))

        console.print(table)

    except Exception as e:
        log.error("failed_to_get_slowest_queries", error=str(e))
        click.echo(f"Error: {str(e)}", err=True)


@performance.command()
def reset():
    """Reset performance metrics."""
    try:
        from sens.monitoring.performance_metrics import reset_performance_tracker

        reset_performance_tracker()
        click.echo("Performance metrics have been reset.")
    except Exception as e:
        log.error("failed_to_reset_metrics", error=str(e))
        click.echo(f"Error: {str(e)}", err=True)


if __name__ == "__main__":
    performance()
