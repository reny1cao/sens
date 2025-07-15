#!/usr/bin/env python3
"""
Unified BIRD Evaluation CLI.

Command-line interface for running evaluations on multiple BIRD datasets.
"""

import asyncio
import sys
from pathlib import Path
from typing import List, Optional

import click
import structlog

from sens.evaluation.unified_bird_evaluator import DatasetType, UnifiedBirdEvaluator
from sens.settings import get_settings

logger = structlog.get_logger(__name__)


@click.group()
def unified_bird_eval():
    """Unified BIRD evaluation commands."""
    pass


@unified_bird_eval.command()
@click.option(
    "--bird-critic", is_flag=True, help="Include BIRD-CRITIC tasks (SQL debugging)"
)
@click.option("--bird-sql-dev", type=str, help="Path to BIRD-SQL-DEV JSON file")
@click.option("--limit", type=int, help="Limit number of tasks to evaluate")
@click.option(
    "--output",
    type=str,
    default="unified_bird_evaluation.json",
    help="Output file path",
)
@click.option(
    "--database-prefix", type=str, default="bird_", help="Database name prefix"
)
@click.option("--debug", is_flag=True, help="Enable debug logging")
def run(
    bird_critic: bool,
    bird_sql_dev: Optional[str],
    limit: Optional[int],
    output: str,
    database_prefix: str,
    debug: bool,
):
    """Run unified BIRD evaluation on selected datasets."""
    if debug:
        import logging

        logging.basicConfig(level=logging.DEBUG)
        structlog.configure(
            wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
        )

    if not bird_critic and not bird_sql_dev:
        click.echo(
            "Error: Must specify at least one dataset (--bird-critic or --bird-sql-dev)"
        )
        sys.exit(1)

    asyncio.run(
        _run_evaluation(
            bird_critic=bird_critic,
            bird_sql_dev=bird_sql_dev,
            limit=limit,
            output=output,
            database_prefix=database_prefix,
        )
    )


async def _run_evaluation(
    bird_critic: bool,
    bird_sql_dev: Optional[str],
    limit: Optional[int],
    output: str,
    database_prefix: str,
):
    """Run the unified evaluation."""
    click.echo("🚀 Starting Unified BIRD Evaluation")
    click.echo("=" * 50)

    # Initialize evaluator
    evaluator = UnifiedBirdEvaluator(
        settings=get_settings(),
        database_prefix=database_prefix,
    )

    # Load datasets
    dataset_types = []

    if bird_critic:
        click.echo("📥 Loading BIRD-CRITIC tasks...")
        try:
            evaluator.load_bird_critic_tasks()
            dataset_types.append(DatasetType.BIRD_CRITIC)
            click.echo("✅ BIRD-CRITIC tasks loaded")
        except Exception as e:
            click.echo(f"❌ Failed to load BIRD-CRITIC: {e}")
            sys.exit(1)

    if bird_sql_dev:
        click.echo(f"📥 Loading BIRD-SQL-DEV tasks from {bird_sql_dev}...")
        try:
            if not Path(bird_sql_dev).exists():
                click.echo(f"❌ File not found: {bird_sql_dev}")
                sys.exit(1)

            evaluator.load_bird_sql_dev_tasks(bird_sql_dev)
            dataset_types.append(DatasetType.BIRD_SQL_DEV)
            click.echo("✅ BIRD-SQL-DEV tasks loaded")
        except Exception as e:
            click.echo(f"❌ Failed to load BIRD-SQL-DEV: {e}")
            sys.exit(1)

    # Show task summary
    total_tasks = len(evaluator.tasks)
    bird_critic_count = len(
        [t for t in evaluator.tasks if t.dataset_type == DatasetType.BIRD_CRITIC]
    )
    bird_sql_dev_count = len(
        [t for t in evaluator.tasks if t.dataset_type == DatasetType.BIRD_SQL_DEV]
    )

    click.echo("\n📊 Task Summary:")
    click.echo(f"   Total tasks: {total_tasks}")
    if bird_critic_count > 0:
        click.echo(f"   BIRD-CRITIC: {bird_critic_count} (SQL debugging)")
    if bird_sql_dev_count > 0:
        click.echo(f"   BIRD-SQL-DEV: {bird_sql_dev_count} (with golden SQL)")

    if limit:
        click.echo(f"   Evaluating first {limit} tasks")

    # Run evaluation
    click.echo("\n🔬 Starting evaluation...")
    try:
        results = await evaluator.evaluate_all(
            limit=limit, dataset_types=dataset_types if dataset_types else None
        )

        # Calculate and display metrics
        metrics = evaluator.get_unified_metrics(results)

        click.echo("\n📈 Evaluation Results:")
        click.echo(f"   Tasks completed: {len(results)}")
        click.echo(
            f"   Overall execution success: {metrics.get('overall_execution_success_rate', 0):.3f}"
        )

        if bird_critic_count > 0:
            bc_rate = metrics.get("bird_critic_execution_success_rate")
            if bc_rate is not None:
                click.echo(f"   BIRD-CRITIC success rate: {bc_rate:.3f}")

        if bird_sql_dev_count > 0:
            bd_exec_rate = metrics.get("bird_sql_dev_execution_success_rate")
            bd_sql_rate = metrics.get("bird_sql_dev_sql_match_rate")
            bd_exact_rate = metrics.get("bird_sql_dev_exact_match_rate")

            if bd_exec_rate is not None:
                click.echo(f"   BIRD-SQL-DEV execution rate: {bd_exec_rate:.3f}")
            if bd_sql_rate is not None:
                click.echo(f"   BIRD-SQL-DEV SQL match rate: {bd_sql_rate:.3f}")
            if bd_exact_rate is not None:
                click.echo(f"   BIRD-SQL-DEV exact match rate: {bd_exact_rate:.3f}")

        avg_time = metrics.get("avg_execution_time_ms")
        if avg_time:
            click.echo(f"   Average execution time: {avg_time:.1f}ms")

        # Save results
        evaluator.save_unified_results(results, output)

        click.echo("\n💾 Results saved:")
        click.echo(f"   Results: {output}")
        click.echo(f"   Metrics: {output.replace('.json', '_metrics.json')}")
        click.echo("\n✅ Evaluation completed successfully!")

    except Exception as e:
        click.echo(f"\n❌ Evaluation failed: {e}")
        sys.exit(1)


@unified_bird_eval.command()
@click.argument("results_file", type=str)
def analyze(results_file: str):
    """Analyze unified evaluation results."""
    if not Path(results_file).exists():
        click.echo(f"❌ Results file not found: {results_file}")
        sys.exit(1)

    try:
        import json

        with open(results_file, "r") as f:
            results = json.load(f)

        click.echo("📊 Unified BIRD Evaluation Analysis")
        click.echo("=" * 40)

        # Dataset breakdown
        bird_critic_results = [
            r for r in results if r.get("dataset_type") == "bird_critic"
        ]
        bird_sql_dev_results = [
            r for r in results if r.get("dataset_type") == "bird_sql_dev"
        ]

        click.echo("\n📋 Dataset Breakdown:")
        click.echo(f"   Total tasks: {len(results)}")
        click.echo(f"   BIRD-CRITIC: {len(bird_critic_results)}")
        click.echo(f"   BIRD-SQL-DEV: {len(bird_sql_dev_results)}")

        # BIRD-CRITIC Analysis
        if bird_critic_results:
            click.echo("\n🐛 BIRD-CRITIC (SQL Debugging) Results:")
            bc_success = sum(
                1 for r in bird_critic_results if r.get("execution_success")
            )
            click.echo(
                f"   Execution success rate: {bc_success}/{len(bird_critic_results)} ({bc_success/len(bird_critic_results):.3f})"
            )

            # Error analysis
            bc_errors = [
                r for r in bird_critic_results if not r.get("execution_success")
            ]
            if bc_errors:
                click.echo(f"   Failed tasks: {len(bc_errors)}")
                # TODO: Add error categorization

        # BIRD-SQL-DEV Analysis
        if bird_sql_dev_results:
            click.echo("\n🎯 BIRD-SQL-DEV (Text-to-SQL) Results:")
            bd_exec_success = sum(
                1 for r in bird_sql_dev_results if r.get("execution_success")
            )
            bd_sql_match = sum(1 for r in bird_sql_dev_results if r.get("sql_match"))
            bd_exact_match = sum(
                1 for r in bird_sql_dev_results if r.get("sql_equivalence")
            )

            total_bd = len(bird_sql_dev_results)
            click.echo(
                f"   Execution success: {bd_exec_success}/{total_bd} ({bd_exec_success/total_bd:.3f})"
            )
            click.echo(
                f"   SQL match (normalized): {bd_sql_match}/{total_bd} ({bd_sql_match/total_bd:.3f})"
            )
            click.echo(
                f"   Exact SQL match: {bd_exact_match}/{total_bd} ({bd_exact_match/total_bd:.3f})"
            )

            # Difficulty breakdown
            difficulties = {}
            for r in bird_sql_dev_results:
                diff = r.get("difficulty", "unknown")
                if diff not in difficulties:
                    difficulties[diff] = {"total": 0, "success": 0}
                difficulties[diff]["total"] += 1
                if r.get("execution_success"):
                    difficulties[diff]["success"] += 1

            if difficulties:
                click.echo("\n   By difficulty:")
                for diff, stats in difficulties.items():
                    rate = (
                        stats["success"] / stats["total"] if stats["total"] > 0 else 0
                    )
                    click.echo(
                        f"     {diff}: {stats['success']}/{stats['total']} ({rate:.3f})"
                    )

        click.echo("\n✅ Analysis completed!")

    except Exception as e:
        click.echo(f"❌ Analysis failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    unified_bird_eval()
