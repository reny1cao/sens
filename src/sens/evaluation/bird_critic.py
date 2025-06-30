"""
BIRD-CRITIC evaluation module for SENS.

This module provides functionality to evaluate the SENS NL2SQL system
against the BIRD-CRITIC benchmark dataset.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import psycopg2
from datasets import load_dataset
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from sens.cli.enhanced_pipeline import EnhancedNL2SQLPipeline
from sens.exceptions import ExecutionError, PipelineError
from sens.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class BirdCriticTask:
    """Represents a single BIRD-CRITIC evaluation task."""

    instance_id: str
    db_id: str
    query: str
    issue_sql: str
    sol_sql: Optional[str] = None
    preprocess_sql: Optional[str] = None
    clean_up_sql: Optional[str] = None


@dataclass
class EvaluationResult:
    """Results from evaluating a single task."""

    task_id: str
    db_id: str
    query: str
    generated_sql: str
    execution_success: bool
    execution_error: Optional[str] = None
    result_count: Optional[int] = None
    execution_time_ms: Optional[float] = None


class BirdCriticEvaluator:
    """Evaluates SENS against the BIRD-CRITIC benchmark."""

    def __init__(
        self,
        settings=None,
        schema_file_path: Optional[str] = None,
        database_prefix: str = "bird_",
    ):
        """
        Initialize the evaluator.

        Args:
            settings: SENS settings configuration (optional, will use defaults)
            schema_file_path: Path to post_schema.jsonl file
            database_prefix: Prefix for database names
        """
        self.settings = settings or get_settings()
        self.database_prefix = database_prefix
        self.pipeline = EnhancedNL2SQLPipeline(
            metrics_enabled=False,
            debug_mode=False,
        )

        # Load schema mapping
        self.schema_by_db: Dict[str, Dict] = {}
        if schema_file_path:
            self._load_schema_mapping(schema_file_path)

        # Load tasks
        self.tasks: List[BirdCriticTask] = []
        self._load_tasks()

    def _load_schema_mapping(self, schema_file_path: str) -> None:
        """Load database schema mapping from JSONL file."""
        schema_path = Path(schema_file_path)
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_file_path}")

        with schema_path.open() as f:
            for line in f:
                if line.strip():
                    obj = json.loads(line)
                    if "instance_id" in obj:
                        # Extract db_id from instance_id (e.g., "PostgreSQL_0" -> "0")
                        db_id = obj["instance_id"].split("_")[-1]
                        self.schema_by_db[db_id] = obj.get("preprocess_schema", "")

    def _load_tasks(self) -> None:
        """Load BIRD-CRITIC tasks from Hugging Face dataset."""
        try:
            ds = load_dataset(
                "birdsql/bird-critic-1.0-postgresql", split="pg", trust_remote_code=True
            )

            for item in ds:
                task = BirdCriticTask(
                    instance_id=item.get("instance_id", ""),
                    db_id=item.get("db_id", ""),
                    query=item.get("query", ""),
                    issue_sql=item.get("issue_sql", ""),
                    sol_sql=item.get("sol_sql"),
                    preprocess_sql=item.get("preprocess_sql"),
                    clean_up_sql=item.get("clean_up_sql"),
                )
                self.tasks.append(task)

            logger.info(f"Loaded {len(self.tasks)} BIRD-CRITIC tasks")

        except Exception as e:
            raise PipelineError(f"Failed to load BIRD-CRITIC dataset: {e}")

    def _get_database_connection(self, db_id: str) -> psycopg2.extensions.connection:
        """Get connection to a specific database."""
        db_name = f"{self.database_prefix}{db_id}"

        try:
            conn = psycopg2.connect(
                host=self.settings.db_host,
                port=self.settings.db_port,
                database=db_name,
                user=self.settings.db_user,
                password=self.settings.db_password,
            )
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            return conn
        except psycopg2.Error as e:
            raise ExecutionError(f"Failed to connect to database {db_name}: {e}")

    def _execute_sql(
        self, conn: psycopg2.extensions.connection, sql: str
    ) -> Dict[str, Any]:
        """Execute SQL and return results with metadata."""
        import time

        start_time = time.time()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql)

                # Get results if available
                try:
                    results = cursor.fetchall()
                    result_count = len(results)
                except psycopg2.ProgrammingError:
                    # No results to fetch (e.g., INSERT, UPDATE, DELETE)
                    results = []
                    result_count = cursor.rowcount

                execution_time = (time.time() - start_time) * 1000

                return {
                    "success": True,
                    "results": results,
                    "result_count": result_count,
                    "execution_time_ms": execution_time,
                    "error": None,
                }

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            return {
                "success": False,
                "results": [],
                "result_count": 0,
                "execution_time_ms": execution_time,
                "error": str(e),
            }

    def evaluate_task(self, task: BirdCriticTask) -> EvaluationResult:
        """Evaluate a single BIRD-CRITIC task."""
        logger.info(f"Evaluating task {task.instance_id} for database {task.db_id}")

        try:
            # Get database connection
            conn = self._get_database_connection(task.db_id)

            # Get schema context for this database
            schema_context = self.schema_by_db.get(task.db_id, "")

            # Generate SQL using SENS pipeline
            result = self.pipeline.process_query(
                query=task.query,
                session_id=f"bird_critic_{task.instance_id}",
                schema_context=schema_context,
            )

            generated_sql = result.sql

            # Execute the generated SQL
            exec_result = self._execute_sql(conn, generated_sql)

            conn.close()

            return EvaluationResult(
                task_id=task.instance_id,
                db_id=task.db_id,
                query=task.query,
                generated_sql=generated_sql,
                execution_success=exec_result["success"],
                execution_error=exec_result["error"],
                result_count=exec_result["result_count"],
                execution_time_ms=exec_result["execution_time_ms"],
            )

        except Exception as e:
            logger.error(f"Failed to evaluate task {task.instance_id}: {e}")
            return EvaluationResult(
                task_id=task.instance_id,
                db_id=task.db_id,
                query=task.query,
                generated_sql="",
                execution_success=False,
                execution_error=str(e),
                result_count=0,
                execution_time_ms=0.0,
            )

    def evaluate_all(self, limit: Optional[int] = None) -> List[EvaluationResult]:
        """Evaluate all tasks (or up to limit)."""
        tasks_to_evaluate = self.tasks[:limit] if limit else self.tasks
        results = []

        logger.info(f"Starting evaluation of {len(tasks_to_evaluate)} tasks")

        for i, task in enumerate(tasks_to_evaluate, 1):
            logger.info(f"Progress: {i}/{len(tasks_to_evaluate)}")
            result = self.evaluate_task(task)
            results.append(result)

        return results

    def get_success_rate(self, results: List[EvaluationResult]) -> float:
        """Calculate success rate from evaluation results."""
        if not results:
            return 0.0

        successful = sum(1 for r in results if r.execution_success)
        return successful / len(results)

    def save_results(self, results: List[EvaluationResult], output_path: str) -> None:
        """Save evaluation results to JSON file."""
        output_data = []

        for result in results:
            output_data.append(
                {
                    "task_id": result.task_id,
                    "db_id": result.db_id,
                    "query": result.query,
                    "generated_sql": result.generated_sql,
                    "execution_success": result.execution_success,
                    "execution_error": result.execution_error,
                    "result_count": result.result_count,
                    "execution_time_ms": result.execution_time_ms,
                }
            )

        with open(output_path, "w") as f:
            json.dump(output_data, f, indent=2)

        logger.info(f"Results saved to {output_path}")


def main():
    """Main evaluation function."""
    settings = get_settings()

    # Path to schema file from cloned repository
    schema_file = "external/BIRD-CRITIC-1/baseline/data/post_schema.jsonl"

    evaluator = BirdCriticEvaluator(settings=settings, schema_file_path=schema_file)

    # Evaluate first 10 tasks as a test
    results = evaluator.evaluate_all(limit=10)

    # Print summary
    success_rate = evaluator.get_success_rate(results)
    print("Evaluation complete!")
    print(f"Success rate: {success_rate:.2%}")
    print(f"Total tasks: {len(results)}")
    print(f"Successful: {sum(1 for r in results if r.execution_success)}")
    print(f"Failed: {sum(1 for r in results if not r.execution_success)}")

    # Save results
    evaluator.save_results(results, "bird_critic_results.json")


if __name__ == "__main__":
    main()
