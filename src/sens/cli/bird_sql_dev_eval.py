#!/usr/bin/env python3
"""
CLI for BIRD-SQL-DEV evaluation system.

This module provides command-line interface for evaluating the SENS system
against the BIRD-SQL-DEV dataset using SQLite databases.
"""

import asyncio
import json
from pathlib import Path

import click
import structlog

from sens.evaluation.bird_sql_dev_evaluator import BirdSqlDevEvaluator

logger = structlog.get_logger(__name__)


@click.group()
@click.pass_context
def bird_sql_dev(ctx):
    """BIRD-SQL-DEV evaluation commands."""
    ctx.ensure_object(dict)


@bird_sql_dev.command()
@click.option(
    "--dataset",
    "-d",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Path to BIRD-SQL-DEV dev.json file",
)
@click.option(
    "--database-dir",
    default="external/BIRD-SQL-DEV/dev_databases",
    type=click.Path(path_type=Path),
    help="Directory containing SQLite database files",
)
@click.option(
    "--limit",
    "-l",
    type=int,
    help="Limit number of tasks to evaluate (for testing)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output path for results JSON file",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug mode with verbose logging",
)
def run(dataset, database_dir, limit, output, debug):
    """Run BIRD-SQL-DEV evaluation."""
    if debug:
        import logging

        logging.basicConfig(level=logging.DEBUG)

    click.echo("🐦 Starting BIRD-SQL-DEV Evaluation")
    click.echo("=" * 40)

    async def run_evaluation():
        try:
            # Initialize evaluator
            evaluator = BirdSqlDevEvaluator(database_dir=str(database_dir))

            # Load tasks
            click.echo(f"📥 Loading tasks from {dataset}")
            evaluator.load_tasks(str(dataset))

            total_tasks = len(evaluator.tasks)
            tasks_to_run = min(limit, total_tasks) if limit else total_tasks

            click.echo(f"📊 Loaded {total_tasks} tasks, evaluating {tasks_to_run}")

            if limit and limit < total_tasks:
                click.echo(f"⚠️  Limiting evaluation to first {limit} tasks for testing")

            # Check database availability
            click.echo("🔍 Checking database availability...")
            db_check_count = 0
            missing_dbs = []

            for task in evaluator.tasks[:5]:  # Check first 5
                db_path = evaluator._get_database_path(task.db_id)
                if db_path.exists():
                    db_check_count += 1
                else:
                    missing_dbs.append(f"{task.db_id} -> {db_path}")

            if missing_dbs:
                click.echo("⚠️  Some databases not found:")
                for missing in missing_dbs:
                    click.echo(f"   {missing}")
            else:
                click.echo(f"✅ Database check passed ({db_check_count}/5 checked)")

            # Run evaluation
            click.echo(f"\n🚀 Starting evaluation of {tasks_to_run} tasks...")

            with click.progressbar(
                length=tasks_to_run,
                label="Evaluating tasks",
                show_eta=True,
                show_percent=True,
            ) as bar:
                results = []

                for i, task in enumerate(evaluator.tasks[:tasks_to_run]):
                    if debug:
                        click.echo(
                            f"\n🔄 Task {i+1}/{tasks_to_run}: {task.question_id} ({task.db_id})"
                        )

                    result = await evaluator.evaluate_task(task)
                    results.append(result)

                    if debug:
                        status = (
                            "✅ Success" if result.execution_success else "❌ Failed"
                        )
                        click.echo(f"   {status}: {result.execution_error or 'OK'}")
                        if result.generated_sql:
                            click.echo(f"   SQL: {result.generated_sql[:100]}...")

                    bar.update(1)

            # Calculate metrics
            click.echo("\n📊 Calculating metrics...")
            metrics = evaluator.calculate_metrics(results)

            # Display results
            click.echo("\n🎯 BIRD-SQL-DEV Evaluation Results")
            click.echo("=" * 40)
            click.echo(f"Total tasks: {metrics['total_tasks']}")
            click.echo(
                f"Execution success rate: {metrics['execution_success_rate']:.1%}"
            )
            click.echo(f"Exact match rate: {metrics['exact_match_rate']:.1%}")
            click.echo(f"Normalized match rate: {metrics['normalized_match_rate']:.1%}")
            click.echo(f"Execution match rate: {metrics['execution_match_rate']:.1%}")

            if "avg_execution_time_ms" in metrics:
                click.echo(
                    f"Average execution time: {metrics['avg_execution_time_ms']:.1f}ms"
                )

            # Show difficulty breakdown
            if metrics.get("difficulty_breakdown"):
                click.echo("\n📈 Performance by Difficulty:")
                for difficulty, stats in metrics["difficulty_breakdown"].items():
                    click.echo(
                        f"  {difficulty.capitalize()}: "
                        f"{stats['success_rate']:.1%} success, "
                        f"{stats['exact_match_rate']:.1%} exact match "
                        f"({stats['total']} tasks)"
                    )

            # Save results if output path provided
            if output:
                click.echo(f"\n💾 Saving results to {output}")
                evaluator.save_results(results, str(output))
                click.echo("✅ Results saved!")

                # Also save metrics separately
                metrics_path = str(output).replace(".json", "_metrics.json")
                with open(metrics_path, "w") as f:
                    json.dump(metrics, f, indent=2)
                click.echo(f"📊 Metrics saved to {metrics_path}")

            click.echo("\n🎉 BIRD-SQL-DEV evaluation completed!")

        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            click.echo(f"❌ Evaluation failed: {e}")
            raise click.ClickException(str(e))

    # Run the async evaluation
    asyncio.run(run_evaluation())


@bird_sql_dev.command()
@click.argument("results_file", type=click.Path(exists=True, path_type=Path))
def analyze(results_file):
    """Analyze BIRD-SQL-DEV evaluation results."""
    click.echo("📊 Analyzing BIRD-SQL-DEV Results")
    click.echo("=" * 35)

    try:
        # Load results
        with open(results_file, "r") as f:
            results = json.load(f)

        if not results:
            click.echo("No results found in file")
            return

        # Basic statistics
        total_tasks = len(results)
        execution_success = sum(1 for r in results if r.get("execution_success", False))
        exact_matches = sum(1 for r in results if r.get("exact_match", False))
        normalized_matches = sum(1 for r in results if r.get("normalized_match", False))
        execution_matches = sum(1 for r in results if r.get("execution_match", False))

        click.echo(f"Total tasks: {total_tasks}")
        click.echo(
            f"Execution success: {execution_success} ({execution_success/total_tasks:.1%})"
        )
        click.echo(f"Exact matches: {exact_matches} ({exact_matches/total_tasks:.1%})")
        click.echo(
            f"Normalized matches: {normalized_matches} ({normalized_matches/total_tasks:.1%})"
        )
        click.echo(
            f"Execution matches: {execution_matches} ({execution_matches/total_tasks:.1%})"
        )

        # Error analysis
        errors = {}
        for result in results:
            if not result.get("execution_success", True) and result.get(
                "execution_error"
            ):
                error = result["execution_error"]
                # Simplify error message
                if "no such table" in error.lower():
                    error_type = "Missing table"
                elif "no such column" in error.lower():
                    error_type = "Missing column"
                elif "syntax error" in error.lower():
                    error_type = "Syntax error"
                elif "database" in error.lower() and "not found" in error.lower():
                    error_type = "Database not found"
                else:
                    error_type = "Other error"

                errors[error_type] = errors.get(error_type, 0) + 1

        if errors:
            click.echo("\n❌ Error breakdown:")
            for error_type, count in sorted(
                errors.items(), key=lambda x: x[1], reverse=True
            ):
                click.echo(f"  {error_type}: {count} ({count/total_tasks:.1%})")

        # Difficulty analysis
        difficulties = {}
        for result in results:
            difficulty = result.get("difficulty", "Unknown")
            if difficulty not in difficulties:
                difficulties[difficulty] = {"total": 0, "success": 0, "exact": 0}

            difficulties[difficulty]["total"] += 1
            if result.get("execution_success", False):
                difficulties[difficulty]["success"] += 1
            if result.get("exact_match", False):
                difficulties[difficulty]["exact"] += 1

        if difficulties:
            click.echo("\n📈 Performance by difficulty:")
            for difficulty, stats in difficulties.items():
                success_rate = (
                    stats["success"] / stats["total"] if stats["total"] > 0 else 0
                )
                exact_rate = (
                    stats["exact"] / stats["total"] if stats["total"] > 0 else 0
                )
                click.echo(
                    f"  {difficulty}: {success_rate:.1%} success, {exact_rate:.1%} exact ({stats['total']} tasks)"
                )

        # Database analysis
        databases = {}
        for result in results:
            db_id = result.get("db_id", "Unknown")
            if db_id not in databases:
                databases[db_id] = {"total": 0, "success": 0}

            databases[db_id]["total"] += 1
            if result.get("execution_success", False):
                databases[db_id]["success"] += 1

        # Show top/bottom performing databases
        db_performance = []
        for db_id, stats in databases.items():
            if stats["total"] >= 3:  # Only show databases with 3+ tasks
                success_rate = stats["success"] / stats["total"]
                db_performance.append((db_id, success_rate, stats["total"]))

        if db_performance:
            db_performance.sort(key=lambda x: x[1], reverse=True)

            click.echo("\n🏆 Top performing databases:")
            for db_id, rate, total in db_performance[:5]:
                click.echo(f"  {db_id}: {rate:.1%} ({total} tasks)")

            if len(db_performance) > 5:
                click.echo("\n⚠️  Bottom performing databases:")
                for db_id, rate, total in db_performance[-5:]:
                    click.echo(f"  {db_id}: {rate:.1%} ({total} tasks)")

    except Exception as e:
        click.echo(f"❌ Analysis failed: {e}")
        raise click.ClickException(str(e))


@bird_sql_dev.command()
@click.option(
    "--database-dir",
    default="external/BIRD-SQL-DEV/dev_databases",
    type=click.Path(path_type=Path),
    help="Directory containing SQLite database files",
)
def status(database_dir):
    """Show BIRD-SQL-DEV setup status."""
    click.echo("🔍 BIRD-SQL-DEV Setup Status")
    click.echo("=" * 30)

    # Check dataset file
    dataset_path = Path("external/BIRD-SQL-DEV/dev.json")
    if dataset_path.exists():
        try:
            with open(dataset_path, "r") as f:
                data = json.load(f)
            click.echo(f"✅ Dataset file: {len(data)} tasks")
        except Exception as e:
            click.echo(f"❌ Dataset file corrupted: {e}")
    else:
        click.echo(f"❌ Dataset file not found: {dataset_path}")

    # Check database directory
    db_dir = Path(database_dir)
    if db_dir.exists():
        # Count database files
        db_files = (
            list(db_dir.glob("*.sqlite"))
            + list(db_dir.glob("*.db"))
            + list(db_dir.glob("*.sqlite3"))
        )
        click.echo(f"✅ Database directory: {len(db_files)} SQLite files")

        if db_files:
            click.echo("   Sample databases:")
            for db_file in sorted(db_files)[:5]:
                size_mb = db_file.stat().st_size / (1024 * 1024)
                click.echo(f"     {db_file.name} ({size_mb:.1f}MB)")
            if len(db_files) > 5:
                click.echo(f"     ... and {len(db_files) - 5} more")
    else:
        click.echo(f"❌ Database directory not found: {db_dir}")

    # Check if we can load tasks and match them to databases
    if dataset_path.exists() and db_dir.exists():
        try:
            evaluator = BirdSqlDevEvaluator(database_dir=str(database_dir))
            evaluator.load_tasks(str(dataset_path))

            # Check database availability for first 10 tasks
            available_count = 0
            total_checked = min(10, len(evaluator.tasks))

            for task in evaluator.tasks[:total_checked]:
                db_path = evaluator._get_database_path(task.db_id)
                if db_path.exists():
                    available_count += 1

            click.echo(
                f"📊 Database availability: {available_count}/{total_checked} checked tasks have databases"
            )

            if available_count < total_checked:
                click.echo(
                    "⚠️  Some databases may be missing or have different file extensions"
                )

        except Exception as e:
            click.echo(f"❌ Failed to check database availability: {e}")


if __name__ == "__main__":
    bird_sql_dev()
