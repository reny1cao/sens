"""CLI commands for BIRD-CRITIC evaluation."""

import json
import os
import subprocess
from pathlib import Path

import click

from sens.evaluation import BirdCriticEvaluator, BirdDatabaseSetup


@click.group()
def bird_critic():
    """BIRD-CRITIC evaluation commands."""
    pass


@bird_critic.command()
@click.option("--cleanup", is_flag=True, help="Clean up existing databases")
@click.option("--limit", type=int, help="Limit number of databases to set up")
@click.option("--prefix", default="bird_", help="Database name prefix")
@click.option("--db-host", default="localhost", help="PostgreSQL host")
@click.option("--db-port", type=int, default=5432, help="PostgreSQL port")
@click.option("--db-user", default="postgres", help="PostgreSQL user")
@click.option("--db-password", default="", help="PostgreSQL password")
def setup_db(
    cleanup: bool,
    limit: int,
    prefix: str,
    db_host: str,
    db_port: int,
    db_user: str,
    db_password: str,
):
    """Set up BIRD-CRITIC databases from dump files."""
    # Validate environment configuration first
    from sens.settings.environment import (
        log_environment_status,
        validate_bird_critic_environment,
    )

    click.echo("🔍 Validating environment configuration...")
    log_environment_status()

    if not validate_bird_critic_environment():
        click.echo(
            "❌ Environment not properly configured for BIRD-CRITIC database setup"
        )
        click.echo(
            "Please ensure local PostgreSQL is configured with SENS_DB_* environment variables"
        )
        return

    click.echo("✅ Environment configuration validated")

    # Use environment variables if available, otherwise use command line args
    db_host = os.getenv("SENS_DB_HOST", db_host)
    db_port = int(os.getenv("SENS_DB_PORT", db_port))
    db_user = os.getenv("SENS_DB_USER", db_user)
    db_password = os.getenv("SENS_DB_PASSWORD", db_password)

    # Check if BIRD-CRITIC repository exists, clone if not
    bird_critic_dir = Path("external/BIRD-CRITIC-1")
    if not bird_critic_dir.exists():
        click.echo("BIRD-CRITIC repository not found. Cloning...")
        try:
            # Create external directory if it doesn't exist
            Path("external").mkdir(exist_ok=True)

            subprocess.run(
                [
                    "git",
                    "clone",
                    "https://github.com/bird-bench/BIRD-CRITIC-1.git",
                    str(bird_critic_dir),
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            click.echo("Successfully cloned BIRD-CRITIC repository")
        except subprocess.CalledProcessError as e:
            click.echo(f"Error cloning repository: {e}")
            click.echo(f"stderr: {e.stderr}")
            return
        except Exception as e:
            click.echo(f"Unexpected error: {e}")
            return

    # Check if database dumps exist
    dumps_dir = bird_critic_dir / "evaluation" / "postgre_table_dumps"
    if not dumps_dir.exists():
        click.echo("⚠️  PostgreSQL database dumps not found!")
        click.echo()
        click.echo("The BIRD-CRITIC database dumps need to be downloaded separately:")
        click.echo(
            "1. Visit: https://drive.google.com/drive/folders/1nJReLrvZVVrnfgBYwwNEgYvLroPGbcPD?usp=sharing"
        )
        click.echo("2. Download the complete database folder")
        click.echo("3. Extract it to: external/BIRD-CRITIC-1/evaluation/")
        click.echo(
            "4. Make sure you have a 'postgre_table_dumps' folder with SQL dump files"
        )
        click.echo()
        click.echo("After downloading, run this command again.")
        return

    setup = BirdDatabaseSetup(
        db_host=db_host,
        db_port=db_port,
        db_user=db_user,
        db_password=db_password,
    )

    if cleanup:
        removed = setup.cleanup_databases(prefix)
        click.echo(f"Cleaned up {removed} databases with prefix '{prefix}'")
        return

    # List available dumps
    dumps = setup.list_available_dumps()
    click.echo(f"Found {len(dumps)} dump files")

    if limit:
        click.echo(f"Setting up first {limit} databases...")
    else:
        click.echo("Setting up all databases...")

    successful = setup.setup_all_databases(prefix, limit)
    click.echo(f"Successfully set up {len(successful)} databases")

    if successful:
        click.echo("Database names:")
        for db_name in successful[:10]:  # Show first 10
            click.echo(f"  - {db_name}")
        if len(successful) > 10:
            click.echo(f"  ... and {len(successful) - 10} more")


@bird_critic.command()
@click.option("--limit", type=int, help="Limit number of tasks to evaluate")
@click.option(
    "--output", "-o", default="bird_critic_results.json", help="Output file for results"
)
@click.option("--schema-file", help="Path to post_schema.jsonl file")
def evaluate(limit: int, output: str, schema_file: str):
    """Run BIRD-CRITIC evaluation."""
    # Validate environment configuration first
    from sens.settings.environment import (
        log_environment_status,
        validate_bird_critic_environment,
    )

    click.echo("🔍 Validating environment configuration...")
    log_environment_status()

    if not validate_bird_critic_environment():
        click.echo("❌ Environment not properly configured for BIRD-CRITIC evaluation")
        click.echo(
            "Please ensure local PostgreSQL is configured with SENS_DB_* environment variables"
        )
        return

    click.echo("✅ Environment configuration validated")

    try:
        from sens.settings import get_settings

        settings = get_settings()
    except Exception as e:
        click.echo(f"Error: Could not load SENS settings: {e}")
        click.echo(
            "Make sure you have configured SENS_OPENROUTER_API_KEY and other required settings in your .env file"
        )
        return

    # Default schema file path
    if not schema_file:
        schema_file = "external/BIRD-CRITIC-1/baseline/data/post_schema.jsonl"

    # Check if schema file exists
    if not Path(schema_file).exists():
        click.echo(f"Error: Schema file not found: {schema_file}")
        click.echo("Run 'sens bird-critic setup-db' first to clone the repository")
        return

    click.echo("Initializing BIRD-CRITIC evaluator...")
    evaluator = BirdCriticEvaluator(settings=settings, schema_file_path=schema_file)

    total_tasks = len(evaluator.tasks)
    tasks_to_run = limit if limit else total_tasks

    click.echo(
        f"Starting evaluation of {tasks_to_run} tasks (out of {total_tasks} total)"
    )

    # Run evaluation
    import asyncio

    results = asyncio.run(evaluator.evaluate_all(limit=limit))

    # Calculate metrics
    success_rate = evaluator.get_success_rate(results)
    successful = sum(1 for r in results if r.execution_success)
    failed = len(results) - successful

    # Calculate comprehensive metrics
    metrics = evaluator.get_comprehensive_metrics(results)

    # Display results
    click.echo("\n" + "=" * 50)
    click.echo("BIRD-CRITIC EVALUATION RESULTS")
    click.echo("=" * 50)
    click.echo(f"Total tasks evaluated: {len(results)}")
    click.echo(f"Successful executions: {successful}")
    click.echo(f"Failed executions: {failed}")
    click.echo(f"Success rate: {success_rate:.2%}")
    click.echo(f"SQL generation rate: {metrics.get('sql_generation_rate', 0):.2%}")

    if results:
        avg_time = sum(r.execution_time_ms or 0 for r in results) / len(results)
        click.echo(f"Average execution time: {avg_time:.2f}ms")
        click.echo(f"Total results returned: {metrics.get('total_result_count', 0)}")

    # Display submission-ready metrics
    click.echo("\n" + "=" * 50)
    click.echo("SUBMISSION-READY METRICS")
    click.echo("=" * 50)
    submission_metrics = metrics.get("submission_ready", {})
    click.echo(
        f"Execution Accuracy: {submission_metrics.get('execution_accuracy', 0):.3f}"
    )
    click.echo(
        f"SQL Generation Coverage: {submission_metrics.get('sql_generation_coverage', 0):.3f}"
    )
    click.echo(
        f"Performance (avg ms): {submission_metrics.get('performance_ms', 0):.2f}"
    )

    # Save results in multiple formats
    evaluator.save_results(results, output)
    click.echo(f"\nDetailed results saved to: {output}")
    click.echo(
        f"BIRD-CRITIC submission format (JSONL) saved to: {output.replace('.json', '_submission.jsonl')}"
    )
    click.echo(f"SQL-only format saved to: {output.replace('.json', '_sql_only.json')}")

    # Save metrics summary
    metrics_file = output.replace(".json", "_metrics.json")
    with open(metrics_file, "w") as f:
        json.dump(metrics, f, indent=2)
    click.echo(f"Comprehensive metrics saved to: {metrics_file}")

    # Display submission instructions
    click.echo("\n" + "=" * 60)
    click.echo("🚀 BIRD-CRITIC SUBMISSION READY")
    click.echo("=" * 60)
    click.echo(
        "Email title: [BIRD-CRITIC-1.0-postgresql][SENS Team][Agent-Based NL2SQL]"
    )
    click.echo(f"Attach file: {output.replace('.json', '_submission.jsonl')}")
    click.echo("Send to: bird.bench25@gmail.com")
    click.echo("")
    click.echo("✅ JSONL format with instance_id, predicted_sql, prompt_flow")
    click.echo("✅ All required fields included")
    click.echo("✅ Ready for validation")

    # Show some failed cases for debugging
    failed_results = [r for r in results if not r.execution_success]
    if failed_results:
        click.echo("\nFirst few failed cases:")
        for i, result in enumerate(failed_results[:3], 1):
            click.echo(f"\n{i}. Task: {result.task_id}")
            click.echo(f"   Query: {result.query}")
            click.echo(f"   Generated SQL: {result.generated_sql}")
            click.echo(f"   Error: {result.execution_error}")


@bird_critic.command()
@click.argument("results_file")
def analyze(results_file: str):
    """Analyze BIRD-CRITIC evaluation results."""
    if not Path(results_file).exists():
        click.echo(f"Error: Results file not found: {results_file}")
        return

    with open(results_file) as f:
        results = json.load(f)

    if not results:
        click.echo("No results found in file")
        return

    # Basic statistics
    total = len(results)
    successful = sum(1 for r in results if r["execution_success"])
    failed = total - successful
    success_rate = successful / total if total > 0 else 0

    click.echo("BIRD-CRITIC EVALUATION ANALYSIS")
    click.echo("=" * 40)
    click.echo(f"Total tasks: {total}")
    click.echo(f"Successful: {successful}")
    click.echo(f"Failed: {failed}")
    click.echo(f"Success rate: {success_rate:.2%}")

    # Timing statistics
    times = [r["execution_time_ms"] for r in results if r["execution_time_ms"]]
    if times:
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)
        click.echo("\nExecution Time Statistics:")
        click.echo(f"Average: {avg_time:.2f}ms")
        click.echo(f"Min: {min_time:.2f}ms")
        click.echo(f"Max: {max_time:.2f}ms")

    # Error analysis
    failed_results = [r for r in results if not r["execution_success"]]
    if failed_results:
        error_types = {}
        for result in failed_results:
            error = result.get("execution_error", "Unknown error")
            # Categorize errors
            if "syntax error" in error.lower():
                error_type = "Syntax Error"
            elif "does not exist" in error.lower():
                error_type = "Schema Error"
            elif "permission denied" in error.lower():
                error_type = "Permission Error"
            elif "connection" in error.lower():
                error_type = "Connection Error"
            else:
                error_type = "Other Error"

            error_types[error_type] = error_types.get(error_type, 0) + 1

        click.echo("\nError Types:")
        for error_type, count in sorted(
            error_types.items(), key=lambda x: x[1], reverse=True
        ):
            percentage = count / failed * 100
            click.echo(f"  {error_type}: {count} ({percentage:.1f}%)")

    # Database statistics
    db_stats = {}
    for result in results:
        db_id = result["db_id"]
        if db_id not in db_stats:
            db_stats[db_id] = {"total": 0, "successful": 0}
        db_stats[db_id]["total"] += 1
        if result["execution_success"]:
            db_stats[db_id]["successful"] += 1

    click.echo("\nPer-Database Success Rates:")
    for db_id, stats in sorted(db_stats.items()):
        success_rate = stats["successful"] / stats["total"] if stats["total"] > 0 else 0
        click.echo(
            f"  {db_id}: {stats['successful']}/{stats['total']} ({success_rate:.1%})"
        )


if __name__ == "__main__":
    bird_critic()
