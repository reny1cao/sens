"""
BIRD-CRITIC evaluation module for SENS.

This module provides functionality to evaluate the SENS NL2SQL system
against the BIRD-CRITIC benchmark dataset.
"""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import psycopg2
from datasets import load_dataset
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from sens.cli.agent_pipeline import AgentNL2SQLPipeline
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
    # Add prompt flow tracking for BIRD-CRITIC submission
    prompt_flow: Optional[List[Dict[str, str]]] = None


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
        # Pipeline will be created per task to use correct database
        self.pipeline = None

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

    async def evaluate_task_with_pipeline(
        self, task: BirdCriticTask, pipeline: AgentNL2SQLPipeline
    ) -> EvaluationResult:
        """Evaluate a single BIRD-CRITIC task with provided pipeline for streaming."""
        logger.info(f"Evaluating task {task.instance_id} for database {task.db_id}")

        target_db_name = f"{self.database_prefix}{task.db_id}"

        try:
            # Get schema context for this database (if available)
            schema_context = self.schema_by_db.get(task.db_id, "")

            # Use the provided pipeline instead of creating a new one
            # This preserves the max_iterations and other config from the caller

            # Create a detailed question that instructs the agent to discover and switch databases
            detailed_question = f"""
BIRD-CRITIC EVALUATION TASK

USER REQUEST: {task.query}

CONTEXT: You are working on a BIRD-CRITIC evaluation task. This requires you to work with a specific database that contains the data for this task.

CRITICAL INSTRUCTIONS - FOLLOW THESE STEPS IN ORDER:

1. FIRST: Use the get_current_database tool to see which database you're currently connected to

2. SECOND: Use the discover_databases tool with prefix "bird_" to find all available BIRD-CRITIC databases

3. THIRD: Use the switch_database tool to switch to the database named "{target_db_name}"
   - This is the correct database for this specific evaluation task
   - The database should contain the data needed to answer the user's question

4. FOURTH: After switching, use the explore_database tool to understand the schema and available tables in the target database

5. FIFTH: Generate and execute a SQL query that addresses the user's request using the discovered schema

6. FINAL: Provide the complete SQL query as your answer

TARGET DATABASE: {target_db_name}
TASK ID: {task.instance_id}

ADDITIONAL CONTEXT:
{schema_context if schema_context else "No additional schema context available."}

Remember: You MUST switch to the correct database ({target_db_name}) before exploring or querying data. This is essential for the evaluation to work correctly.

USER'S QUESTION TO SOLVE: {task.query}
"""

            # Generate SQL using provided pipeline
            result = await pipeline.process_question(
                question=detailed_question.strip(),
                format_type="json",
                show_preview=False,
                max_rows=0,
            )

            generated_sql = result.get("sql", "")

            # Extract prompt flow from agent events for BIRD-CRITIC submission
            prompt_flow = []
            if hasattr(pipeline, "events") and pipeline.events:
                for event in pipeline.events:
                    if event.get("type") in [
                        "reasoning",
                        "sql_generated",
                        "answer_generated",
                    ]:
                        # Create prompt flow entry
                        if event.get("type") == "reasoning":
                            prompt_flow.append(
                                {
                                    "model": "google/gemini-2.0-flash-001",  # Our reasoning model
                                    "prompt": f"Reasoning step {event.get('data', {}).get('iteration', 'N/A')}: {detailed_question[:200]}...",
                                    "response": event.get("data", {}).get(
                                        "content", ""
                                    ),
                                }
                            )
                        elif event.get("type") == "sql_generated":
                            prompt_flow.append(
                                {
                                    "model": "google/gemini-2.0-flash-001",  # Our SQL generation model
                                    "prompt": f"Generate SQL for: {task.query[:200]}...",
                                    "response": event.get("data", {}).get(
                                        "sql", generated_sql
                                    ),
                                }
                            )

            # If no prompt flow captured, create a basic one
            if not prompt_flow:
                prompt_flow = [
                    {
                        "model": "google/gemini-2.0-flash-001",
                        "prompt": detailed_question,
                        "response": f"Generated SQL: {generated_sql}",
                    }
                ]

            # Execute the generated SQL using direct database connection to verify results
            execution_success = True
            execution_error = None
            result_count = 0
            execution_time_ms = 0.0

            if generated_sql:
                try:
                    conn = self._get_database_connection(task.db_id)
                    exec_result = self._execute_sql(conn, generated_sql)
                    conn.close()

                    execution_success = exec_result["success"]
                    execution_error = exec_result["error"]
                    result_count = exec_result["result_count"]
                    execution_time_ms = exec_result["execution_time_ms"]

                except Exception as e:
                    execution_success = False
                    execution_error = f"Direct execution failed: {str(e)}"

            return EvaluationResult(
                task_id=task.instance_id,
                db_id=task.db_id,
                query=task.query,
                generated_sql=generated_sql,
                execution_success=execution_success,
                execution_error=execution_error,
                result_count=result_count,
                execution_time_ms=execution_time_ms,
                prompt_flow=prompt_flow,
            )

        except Exception as e:
            logger.error(f"Failed to evaluate task {task.instance_id}: {e}")
            return EvaluationResult(
                task_id=task.instance_id,
                db_id=task.db_id,
                query=task.query,
                generated_sql=None,
                execution_success=False,
                execution_error=str(e),
                result_count=0,
                execution_time_ms=0.0,
                prompt_flow=[],
            )

    async def evaluate_task(self, task: BirdCriticTask) -> EvaluationResult:
        """Evaluate a single BIRD-CRITIC task with agent-driven database discovery."""
        logger.info(f"Evaluating task {task.instance_id} for database {task.db_id}")

        target_db_name = f"{self.database_prefix}{task.db_id}"

        try:
            # Create pipeline for this specific task
            pipeline = AgentNL2SQLPipeline(
                metrics_enabled=False,
                debug_mode=True,  # Enable debug to see agent's database switching
                max_iterations=5,  # Allow more iterations for database discovery
            )

            # Get schema context for this database (if available)
            schema_context = self.schema_by_db.get(task.db_id, "")

            # Create a detailed question that instructs the agent to discover and switch databases
            detailed_question = f"""
BIRD-CRITIC EVALUATION TASK

USER REQUEST: {task.query}

CONTEXT: You are working on a BIRD-CRITIC evaluation task. This requires you to work with a specific database that contains the data for this task.

CRITICAL INSTRUCTIONS - FOLLOW THESE STEPS IN ORDER:

1. FIRST: Use the get_current_database tool to see which database you're currently connected to

2. SECOND: Use the discover_databases tool with prefix "bird_" to find all available BIRD-CRITIC databases

3. THIRD: Use the switch_database tool to switch to the database named "{target_db_name}"
   - This is the correct database for this specific evaluation task
   - The database should contain the data needed to answer the user's question

4. FOURTH: After switching, use the explore_database tool to understand the schema and available tables in the target database

5. FIFTH: Generate and execute a SQL query that addresses the user's request using the discovered schema

6. FINAL: Provide the complete SQL query as your answer

TARGET DATABASE: {target_db_name}
TASK ID: {task.instance_id}

ADDITIONAL CONTEXT:
{schema_context if schema_context else "No additional schema context available."}

Remember: You MUST switch to the correct database ({target_db_name}) before exploring or querying data. This is essential for the evaluation to work correctly.

USER'S QUESTION TO SOLVE: {task.query}
"""

            # Generate SQL using SENS agent pipeline with database discovery
            result = await pipeline.process_question(
                question=detailed_question.strip(),
                format_type="json",
                show_preview=False,
                max_rows=0,
            )

            generated_sql = result.get("sql", "")

            # Extract prompt flow from agent events for BIRD-CRITIC submission
            prompt_flow = []
            if hasattr(pipeline, "events") and pipeline.events:
                for event in pipeline.events:
                    if event.get("type") in [
                        "reasoning",
                        "sql_generated",
                        "answer_generated",
                    ]:
                        # Create prompt flow entry
                        if event.get("type") == "reasoning":
                            prompt_flow.append(
                                {
                                    "model": "google/gemini-2.0-flash-001",  # Our reasoning model
                                    "prompt": f"Reasoning step {event.get('data', {}).get('iteration', 'N/A')}: {detailed_question[:200]}...",
                                    "response": event.get("data", {}).get(
                                        "content", ""
                                    ),
                                }
                            )
                        elif event.get("type") == "sql_generated":
                            prompt_flow.append(
                                {
                                    "model": "google/gemini-2.0-flash-001",  # Our SQL generation model
                                    "prompt": f"Generate SQL for: {task.query[:200]}...",
                                    "response": event.get("data", {}).get(
                                        "sql", generated_sql
                                    ),
                                }
                            )

            # If no prompt flow captured, create a basic one
            if not prompt_flow:
                prompt_flow = [
                    {
                        "model": "google/gemini-2.0-flash-001",
                        "prompt": detailed_question,
                        "response": f"Generated SQL: {generated_sql}",
                    }
                ]

            # Execute the generated SQL using direct database connection to verify results
            execution_success = True
            execution_error = None
            result_count = 0
            execution_time_ms = 0.0

            if generated_sql:
                try:
                    conn = self._get_database_connection(task.db_id)
                    exec_result = self._execute_sql(conn, generated_sql)
                    conn.close()

                    execution_success = exec_result["success"]
                    execution_error = exec_result["error"]
                    result_count = exec_result["result_count"]
                    execution_time_ms = exec_result["execution_time_ms"]

                except Exception as e:
                    execution_success = False
                    execution_error = f"Direct execution failed: {str(e)}"

            return EvaluationResult(
                task_id=task.instance_id,
                db_id=task.db_id,
                query=task.query,
                generated_sql=generated_sql,
                execution_success=execution_success,
                execution_error=execution_error,
                result_count=result_count,
                execution_time_ms=execution_time_ms,
                prompt_flow=prompt_flow,
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
                prompt_flow=[],
            )

    async def evaluate_all(self, limit: Optional[int] = None) -> List[EvaluationResult]:
        """Evaluate all tasks (or up to limit)."""
        tasks_to_evaluate = self.tasks[:limit] if limit else self.tasks
        results = []

        logger.info(f"Starting evaluation of {len(tasks_to_evaluate)} tasks")

        for i, task in enumerate(tasks_to_evaluate, 1):
            logger.info(f"Progress: {i}/{len(tasks_to_evaluate)}")
            result = await self.evaluate_task(task)
            results.append(result)

        return results

    def get_success_rate(self, results: List[EvaluationResult]) -> float:
        """Calculate success rate from evaluation results."""
        if not results:
            return 0.0

        successful = sum(1 for r in results if r.execution_success)
        return successful / len(results)

    def get_comprehensive_metrics(
        self, results: List[EvaluationResult]
    ) -> Dict[str, Any]:
        """Calculate comprehensive evaluation metrics for BIRD-CRITIC submission."""
        if not results:
            return {}

        total_tasks = len(results)
        successful_executions = sum(1 for r in results if r.execution_success)
        failed_executions = total_tasks - successful_executions

        # Basic metrics
        success_rate = successful_executions / total_tasks if total_tasks > 0 else 0.0

        # Timing metrics
        execution_times = [
            r.execution_time_ms for r in results if r.execution_time_ms is not None
        ]
        avg_execution_time = (
            sum(execution_times) / len(execution_times) if execution_times else 0.0
        )

        # SQL generation metrics
        sql_generated = sum(
            1 for r in results if r.generated_sql and r.generated_sql.strip()
        )
        sql_generation_rate = sql_generated / total_tasks if total_tasks > 0 else 0.0

        # Result counts
        total_result_count = sum(
            r.result_count for r in results if r.result_count is not None
        )
        avg_result_count = (
            total_result_count / successful_executions
            if successful_executions > 0
            else 0.0
        )

        # Error analysis
        error_types = {}
        for result in results:
            if not result.execution_success and result.execution_error:
                error = result.execution_error.lower()
                if "syntax error" in error:
                    error_types["syntax_errors"] = (
                        error_types.get("syntax_errors", 0) + 1
                    )
                elif "does not exist" in error:
                    error_types["schema_errors"] = (
                        error_types.get("schema_errors", 0) + 1
                    )
                elif "permission" in error:
                    error_types["permission_errors"] = (
                        error_types.get("permission_errors", 0) + 1
                    )
                else:
                    error_types["other_errors"] = error_types.get("other_errors", 0) + 1

        return {
            "total_tasks": total_tasks,
            "successful_executions": successful_executions,
            "failed_executions": failed_executions,
            "success_rate": success_rate,
            "sql_generation_rate": sql_generation_rate,
            "avg_execution_time_ms": avg_execution_time,
            "avg_result_count": avg_result_count,
            "total_result_count": total_result_count,
            "error_breakdown": error_types,
            "submission_ready": {
                "execution_accuracy": success_rate,
                "sql_generation_coverage": sql_generation_rate,
                "performance_ms": avg_execution_time,
            },
        }

    def save_results(self, results: List[EvaluationResult], output_path: str) -> None:
        """Save evaluation results in multiple formats for submission."""
        # Standard format for our analysis
        output_data = []

        for result in results:
            # Our internal format
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
                    "prompt_flow": result.prompt_flow,
                }
            )

        # Save internal format
        with open(output_path, "w") as f:
            json.dump(output_data, f, indent=2)

        # Save BIRD-CRITIC official submission format (JSONL)
        submission_path = output_path.replace(".json", "_submission.jsonl")
        with open(submission_path, "w") as f:
            for result in results:
                # Handle SQL list format - wrap single SQL in list
                predicted_sql = [result.generated_sql] if result.generated_sql else []

                # Create BIRD-CRITIC submission entry
                submission_entry = {
                    "instance_id": result.task_id,
                    "predicted_sql": predicted_sql,
                    "prompt_flow": result.prompt_flow or [],
                }

                # Write as JSONL (one JSON object per line)
                f.write(json.dumps(submission_entry) + "\n")

        # Save SQL-only format for quick reference
        sql_only_path = output_path.replace(".json", "_sql_only.json")
        sql_only_data = {result.task_id: result.generated_sql for result in results}
        with open(sql_only_path, "w") as f:
            json.dump(sql_only_data, f, indent=2)

        logger.info(f"Results saved to {output_path}")
        logger.info(f"BIRD-CRITIC submission format (JSONL) saved to {submission_path}")
        logger.info(f"SQL-only format saved to {sql_only_path}")


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
