#!/usr/bin/env python3
"""
Unified BIRD Evaluation System.

Supports multiple BIRD datasets:
- BIRD-CRITIC: SQL debugging/fixing tasks (execution-based evaluation)
- BIRD-SQL-DEV: Traditional text-to-SQL tasks (with golden SQL comparison)
"""

import json
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import structlog
from datasets import load_dataset

from sens.cli.agent_pipeline import AgentNL2SQLPipeline
from sens.evaluation.bird_critic import BirdCriticEvaluator, EvaluationResult
from sens.exceptions import PipelineError
from sens.settings import get_settings

logger = structlog.get_logger(__name__)


class DatasetType(Enum):
    """Supported BIRD dataset types."""

    BIRD_CRITIC = "bird_critic"
    BIRD_SQL_DEV = "bird_sql_dev"


@dataclass
class UnifiedTask:
    """Unified task representation for different BIRD datasets."""

    # Common fields
    task_id: str
    db_id: str
    question: str

    # Dataset-specific fields
    dataset_type: DatasetType
    golden_sql: Optional[str] = None  # For BIRD-SQL-DEV
    issue_sql: Optional[str] = None  # For BIRD-CRITIC
    evidence: Optional[str] = None  # For BIRD-SQL-DEV
    difficulty: Optional[str] = None  # For BIRD-SQL-DEV
    preprocess_sql: Optional[str] = None  # For BIRD-CRITIC
    clean_up_sql: Optional[str] = None  # For BIRD-CRITIC


@dataclass
class UnifiedEvaluationResult:
    """Unified evaluation result for both dataset types."""

    # Common fields
    task_id: str
    db_id: str
    question: str
    dataset_type: DatasetType
    generated_sql: Optional[str]
    execution_success: bool
    execution_error: Optional[str] = None
    result_count: Optional[int] = None
    execution_time_ms: Optional[float] = None

    # Golden SQL comparison (for BIRD-SQL-DEV)
    golden_sql: Optional[str] = None
    sql_match: Optional[bool] = None
    sql_equivalence: Optional[bool] = None

    # Additional metadata
    difficulty: Optional[str] = None
    prompt_flow: Optional[List[Dict[str, str]]] = None


class UnifiedBirdEvaluator:
    """Unified evaluator supporting multiple BIRD datasets."""

    def __init__(
        self,
        settings=None,
        database_prefix: str = "bird_",
    ):
        """Initialize the unified evaluator."""
        self.settings = settings or get_settings()
        self.database_prefix = database_prefix
        self.tasks: List[UnifiedTask] = []

        # Initialize specific evaluators
        self.bird_critic_evaluator = None

    def load_bird_critic_tasks(
        self,
        dataset_name: str = "birdsql/bird-critic-1.0-postgresql",
        split: str = "pg",
    ) -> None:
        """Load BIRD-CRITIC tasks from Hugging Face."""
        try:
            ds = load_dataset(dataset_name, split=split, trust_remote_code=True)

            for item in ds:
                task = UnifiedTask(
                    task_id=item.get("instance_id", ""),
                    db_id=item.get("db_id", ""),
                    question=item.get("query", ""),
                    dataset_type=DatasetType.BIRD_CRITIC,
                    issue_sql=item.get("issue_sql", ""),
                    preprocess_sql=item.get("preprocess_sql"),
                    clean_up_sql=item.get("clean_up_sql"),
                )
                self.tasks.append(task)

            logger.info(
                f"Loaded {len([t for t in self.tasks if t.dataset_type == DatasetType.BIRD_CRITIC])} BIRD-CRITIC tasks"
            )

        except Exception as e:
            raise PipelineError(f"Failed to load BIRD-CRITIC dataset: {e}")

    def load_bird_sql_dev_tasks(self, json_path: str) -> None:
        """Load BIRD-SQL-DEV tasks from JSON file."""
        try:
            with open(json_path, "r") as f:
                data = json.load(f)

            for item in data:
                task = UnifiedTask(
                    task_id=str(item.get("question_id", "")),
                    db_id=item.get("db_id", ""),
                    question=item.get("question", ""),
                    dataset_type=DatasetType.BIRD_SQL_DEV,
                    golden_sql=item.get("SQL"),
                    evidence=item.get("evidence"),
                    difficulty=item.get("difficulty"),
                )
                self.tasks.append(task)

            bird_sql_count = len(
                [t for t in self.tasks if t.dataset_type == DatasetType.BIRD_SQL_DEV]
            )
            logger.info(f"Loaded {bird_sql_count} BIRD-SQL-DEV tasks")

        except Exception as e:
            raise PipelineError(f"Failed to load BIRD-SQL-DEV dataset: {e}")

    def _normalize_sql(self, sql: str) -> str:
        """Normalize SQL for comparison."""
        if not sql:
            return ""

        # Basic normalization
        normalized = sql.strip().lower()
        # Remove extra whitespace
        normalized = " ".join(normalized.split())
        # Remove trailing semicolon
        normalized = normalized.rstrip(";")

        return normalized

    def _compare_sql(self, generated_sql: str, golden_sql: str) -> Dict[str, bool]:
        """Compare generated SQL with golden SQL."""
        result = {
            "exact_match": False,
            "normalized_match": False,
        }

        if not generated_sql or not golden_sql:
            return result

        # Exact string match
        result["exact_match"] = generated_sql.strip() == golden_sql.strip()

        # Normalized match
        norm_generated = self._normalize_sql(generated_sql)
        norm_golden = self._normalize_sql(golden_sql)
        result["normalized_match"] = norm_generated == norm_golden

        return result

    async def evaluate_task(self, task: UnifiedTask) -> UnifiedEvaluationResult:
        """Evaluate a single unified task."""
        logger.info(f"Evaluating {task.dataset_type.value} task {task.task_id}")

        if task.dataset_type == DatasetType.BIRD_CRITIC:
            return await self._evaluate_bird_critic_task(task)
        elif task.dataset_type == DatasetType.BIRD_SQL_DEV:
            return await self._evaluate_bird_sql_dev_task(task)
        else:
            raise ValueError(f"Unsupported dataset type: {task.dataset_type}")

    async def _evaluate_bird_critic_task(
        self, task: UnifiedTask
    ) -> UnifiedEvaluationResult:
        """Evaluate BIRD-CRITIC task (execution-based)."""
        if not self.bird_critic_evaluator:
            self.bird_critic_evaluator = BirdCriticEvaluator(
                settings=self.settings,
                database_prefix=self.database_prefix,
                schema_file_path="external/BIRD-CRITIC-1/baseline/data/post_schema.jsonl",
            )

        # Convert to BIRD-CRITIC format and evaluate
        from sens.evaluation.bird_critic import BirdCriticTask

        bird_critic_task = BirdCriticTask(
            instance_id=task.task_id,
            db_id=task.db_id,
            query=task.question,
            issue_sql=task.issue_sql or "",
            sol_sql=None,  # No golden SQL in BIRD-CRITIC
            preprocess_sql=task.preprocess_sql,
            clean_up_sql=task.clean_up_sql,
        )

        result = await self.bird_critic_evaluator.evaluate_task_with_pipeline(
            bird_critic_task,
            AgentNL2SQLPipeline(
                metrics_enabled=False,
                debug_mode=True,
                max_iterations=25,
            ),
        )

        return UnifiedEvaluationResult(
            task_id=task.task_id,
            db_id=task.db_id,
            question=task.question,
            dataset_type=task.dataset_type,
            generated_sql=result.generated_sql,
            execution_success=result.execution_success,
            execution_error=result.execution_error,
            result_count=result.result_count,
            execution_time_ms=result.execution_time_ms,
            prompt_flow=result.prompt_flow,
        )

    async def _evaluate_bird_sql_dev_task(
        self, task: UnifiedTask
    ) -> UnifiedEvaluationResult:
        """Evaluate BIRD-SQL-DEV task (with golden SQL comparison)."""
        # Create pipeline for SQL generation
        pipeline = AgentNL2SQLPipeline(
            metrics_enabled=False,
            debug_mode=True,
            max_iterations=25,
        )

        try:
            # Generate SQL using the pipeline
            result = await pipeline.process_question(task.question)

            generated_sql = result.get("sql")
            execution_success = result.get("status") == "success"
            execution_error = result.get("error")

            # SQL comparison with golden SQL
            sql_comparison = self._compare_sql(
                generated_sql or "", task.golden_sql or ""
            )

            return UnifiedEvaluationResult(
                task_id=task.task_id,
                db_id=task.db_id,
                question=task.question,
                dataset_type=task.dataset_type,
                generated_sql=generated_sql,
                execution_success=execution_success,
                execution_error=execution_error,
                golden_sql=task.golden_sql,
                sql_match=sql_comparison["normalized_match"],
                sql_equivalence=sql_comparison["exact_match"],
                difficulty=task.difficulty,
                # TODO: Extract prompt flow from pipeline
                prompt_flow=[],
            )

        except Exception as e:
            logger.error(f"Failed to evaluate BIRD-SQL-DEV task {task.task_id}: {e}")
            return UnifiedEvaluationResult(
                task_id=task.task_id,
                db_id=task.db_id,
                question=task.question,
                dataset_type=task.dataset_type,
                generated_sql=None,
                execution_success=False,
                execution_error=str(e),
                golden_sql=task.golden_sql,
                sql_match=False,
                sql_equivalence=False,
                difficulty=task.difficulty,
                prompt_flow=[],
            )

    async def evaluate_all(
        self,
        limit: Optional[int] = None,
        dataset_types: Optional[List[DatasetType]] = None,
    ) -> List[UnifiedEvaluationResult]:
        """Evaluate all tasks or filtered by dataset type."""
        tasks_to_evaluate = self.tasks

        # Filter by dataset type if specified
        if dataset_types:
            tasks_to_evaluate = [
                t for t in tasks_to_evaluate if t.dataset_type in dataset_types
            ]

        # Apply limit
        if limit:
            tasks_to_evaluate = tasks_to_evaluate[:limit]

        results = []
        total_tasks = len(tasks_to_evaluate)

        logger.info(f"Starting evaluation of {total_tasks} tasks")

        for i, task in enumerate(tasks_to_evaluate, 1):
            logger.info(f"Progress: {i}/{total_tasks} - {task.dataset_type.value}")
            result = await self.evaluate_task(task)
            results.append(result)

        return results

    def get_unified_metrics(
        self, results: List[UnifiedEvaluationResult]
    ) -> Dict[str, Any]:
        """Calculate unified metrics across dataset types."""
        if not results:
            return {}

        # Separate results by dataset type
        bird_critic_results = [
            r for r in results if r.dataset_type == DatasetType.BIRD_CRITIC
        ]
        bird_sql_dev_results = [
            r for r in results if r.dataset_type == DatasetType.BIRD_SQL_DEV
        ]

        metrics = {
            "total_tasks": len(results),
            "bird_critic_tasks": len(bird_critic_results),
            "bird_sql_dev_tasks": len(bird_sql_dev_results),
        }

        # Overall execution metrics
        successful_executions = sum(1 for r in results if r.execution_success)
        metrics["overall_execution_success_rate"] = (
            successful_executions / len(results) if results else 0.0
        )

        # BIRD-CRITIC specific metrics (execution-based)
        if bird_critic_results:
            bc_successful = sum(1 for r in bird_critic_results if r.execution_success)
            metrics["bird_critic_execution_success_rate"] = bc_successful / len(
                bird_critic_results
            )

        # BIRD-SQL-DEV specific metrics (golden SQL comparison)
        if bird_sql_dev_results:
            bd_successful = sum(1 for r in bird_sql_dev_results if r.execution_success)
            bd_sql_match = sum(1 for r in bird_sql_dev_results if r.sql_match)
            bd_sql_exact = sum(1 for r in bird_sql_dev_results if r.sql_equivalence)

            metrics["bird_sql_dev_execution_success_rate"] = bd_successful / len(
                bird_sql_dev_results
            )
            metrics["bird_sql_dev_sql_match_rate"] = bd_sql_match / len(
                bird_sql_dev_results
            )
            metrics["bird_sql_dev_exact_match_rate"] = bd_sql_exact / len(
                bird_sql_dev_results
            )

        # Performance metrics
        execution_times = [
            r.execution_time_ms for r in results if r.execution_time_ms is not None
        ]
        if execution_times:
            metrics["avg_execution_time_ms"] = sum(execution_times) / len(
                execution_times
            )

        return metrics

    def save_unified_results(
        self, results: List[UnifiedEvaluationResult], output_path: str
    ) -> None:
        """Save unified evaluation results."""
        output_data = []

        for result in results:
            result_dict = {
                "task_id": result.task_id,
                "db_id": result.db_id,
                "question": result.question,
                "dataset_type": result.dataset_type.value,
                "generated_sql": result.generated_sql,
                "execution_success": result.execution_success,
                "execution_error": result.execution_error,
                "result_count": result.result_count,
                "execution_time_ms": result.execution_time_ms,
                "difficulty": result.difficulty,
            }

            # Add dataset-specific fields
            if result.dataset_type == DatasetType.BIRD_SQL_DEV:
                result_dict.update(
                    {
                        "golden_sql": result.golden_sql,
                        "sql_match": result.sql_match,
                        "sql_equivalence": result.sql_equivalence,
                    }
                )

            output_data.append(result_dict)

        # Save unified results
        with open(output_path, "w") as f:
            json.dump(output_data, f, indent=2)

        # Save metrics
        metrics = self.get_unified_metrics(results)
        metrics_path = output_path.replace(".json", "_metrics.json")
        with open(metrics_path, "w") as f:
            json.dump(metrics, f, indent=2)

        logger.info(f"Saved unified results to {output_path}")
        logger.info(f"Saved unified metrics to {metrics_path}")
