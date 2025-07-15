"""
Unified BIRD Evaluation API Router.

Provides REST API endpoints for running evaluations on multiple BIRD datasets
with real-time SSE streaming and comprehensive metrics.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from sens.api.common.sse import create_sse_response
from sens.evaluation.unified_bird_evaluator import (
    DatasetType,
    UnifiedBirdEvaluator,
    UnifiedEvaluationResult,
)
from sens.settings import get_settings

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/evaluation/unified-bird", tags=["unified-evaluation"])


class UnifiedEvaluationConfig(BaseModel):
    """Configuration for unified BIRD evaluation run."""

    # Dataset selection
    include_bird_critic: bool = Field(
        default=True, description="Include BIRD-CRITIC tasks"
    )
    bird_sql_dev_path: Optional[str] = Field(
        default=None, description="Path to BIRD-SQL-DEV JSON file"
    )

    # Evaluation settings
    limit: Optional[int] = Field(None, description="Limit number of tasks to evaluate")
    database_prefix: str = Field(default="bird_", description="Database name prefix")
    debug_mode: bool = Field(
        default=True, description="Enable debug mode for detailed logs"
    )
    max_iterations: int = Field(default=25, description="Max agent iterations per task")


class UnifiedEvaluationStatus(BaseModel):
    """Current status of a unified evaluation run."""

    evaluation_id: str
    status: str  # "running", "completed", "failed"

    # Task counts by type
    total_tasks: int
    bird_critic_tasks: int
    bird_sql_dev_tasks: int

    # Progress
    completed_tasks: int
    successful_tasks: int
    failed_tasks: int
    current_task: Optional[str] = None
    current_dataset_type: Optional[str] = None

    # Timing
    start_time: datetime
    end_time: Optional[datetime] = None

    # Metrics
    metrics: Dict[str, Any] = {}


# In-memory storage for evaluation runs
unified_evaluation_runs: Dict[str, UnifiedEvaluationStatus] = {}
unified_evaluation_configs: Dict[str, UnifiedEvaluationConfig] = {}


async def stream_unified_evaluation_events(
    evaluator: UnifiedBirdEvaluator, config: UnifiedEvaluationConfig, evaluation_id: str
):
    """Stream unified evaluation progress as SSE events."""
    try:
        # Send initial status
        yield create_sse_response(
            {
                "type": "evaluation_start",
                "evaluation_id": evaluation_id,
                "total_tasks": (
                    len(evaluator.tasks[: config.limit])
                    if config.limit
                    else len(evaluator.tasks)
                ),
                "bird_critic_tasks": len(
                    [
                        t
                        for t in evaluator.tasks
                        if t.dataset_type == DatasetType.BIRD_CRITIC
                    ]
                ),
                "bird_sql_dev_tasks": len(
                    [
                        t
                        for t in evaluator.tasks
                        if t.dataset_type == DatasetType.BIRD_SQL_DEV
                    ]
                ),
                "config": config.model_dump(),
            }
        )

        # Determine which tasks to evaluate
        tasks_to_evaluate = (
            evaluator.tasks[: config.limit] if config.limit else evaluator.tasks
        )
        results = []

        for i, task in enumerate(tasks_to_evaluate, 1):
            # Update status
            unified_evaluation_runs[evaluation_id].current_task = task.task_id
            unified_evaluation_runs[evaluation_id].current_dataset_type = (
                task.dataset_type.value
            )
            unified_evaluation_runs[evaluation_id].completed_tasks = i - 1

            # Send task start event
            yield create_sse_response(
                {
                    "type": "task_start",
                    "task_number": i,
                    "total_tasks": len(tasks_to_evaluate),
                    "task_id": task.task_id,
                    "db_id": task.db_id,
                    "question": task.question,
                    "dataset_type": task.dataset_type.value,
                    "has_golden_sql": task.golden_sql is not None,
                }
            )

            # Create event queue for real-time streaming (for agent events if available)
            # events_queue = []  # Reserved for future agent event streaming

            # For BIRD-CRITIC tasks, we can potentially capture agent events
            # For BIRD-SQL-DEV tasks, the evaluation is more direct

            try:
                # Evaluate the task
                result = await evaluator.evaluate_task(task)
                results.append(result)

                # Send task completion event
                completion_data = {
                    "type": "task_complete",
                    "task_id": task.task_id,
                    "dataset_type": task.dataset_type.value,
                    "success": result.execution_success,
                    "generated_sql": result.generated_sql,
                    "error": result.execution_error,
                    "execution_time_ms": result.execution_time_ms,
                    "result_count": result.result_count,
                }

                # Add dataset-specific fields
                if result.dataset_type == DatasetType.BIRD_SQL_DEV:
                    completion_data.update(
                        {
                            "golden_sql": result.golden_sql,
                            "sql_match": result.sql_match,
                            "sql_equivalence": result.sql_equivalence,
                            "difficulty": result.difficulty,
                        }
                    )

                yield create_sse_response(completion_data)

                # Update running metrics
                metrics = evaluator.get_unified_metrics(results)
                unified_evaluation_runs[evaluation_id].metrics = metrics

                # Send metrics update
                yield create_sse_response(
                    {"type": "metrics_update", "metrics": metrics}
                )

                # Update success/failure counts
                if result.execution_success:
                    unified_evaluation_runs[evaluation_id].successful_tasks += 1
                else:
                    unified_evaluation_runs[evaluation_id].failed_tasks += 1

            except Exception as e:
                logger.error(
                    "Task evaluation failed", task_id=task.task_id, error=str(e)
                )
                yield create_sse_response(
                    {
                        "type": "task_error",
                        "task_id": task.task_id,
                        "dataset_type": task.dataset_type.value,
                        "error": str(e),
                    }
                )
                unified_evaluation_runs[evaluation_id].failed_tasks += 1

        # Save results
        output_file = f"unified_evaluation_{evaluation_id}.json"
        evaluator.save_unified_results(results, output_file)

        # Send completion event
        final_metrics = evaluator.get_unified_metrics(results)
        yield create_sse_response(
            {
                "type": "evaluation_complete",
                "evaluation_id": evaluation_id,
                "total_tasks": len(results),
                "successful_tasks": sum(1 for r in results if r.execution_success),
                "bird_critic_tasks": len(
                    [r for r in results if r.dataset_type == DatasetType.BIRD_CRITIC]
                ),
                "bird_sql_dev_tasks": len(
                    [r for r in results if r.dataset_type == DatasetType.BIRD_SQL_DEV]
                ),
                "output_files": {
                    "detailed": output_file,
                    "metrics": output_file.replace(".json", "_metrics.json"),
                },
                "final_metrics": final_metrics,
            }
        )

        # Update final status
        unified_evaluation_runs[evaluation_id].status = "completed"
        unified_evaluation_runs[evaluation_id].end_time = datetime.now()
        unified_evaluation_runs[evaluation_id].completed_tasks = len(results)
        unified_evaluation_runs[evaluation_id].metrics = final_metrics

    except Exception as e:
        logger.error(
            "Unified evaluation failed", evaluation_id=evaluation_id, error=str(e)
        )
        unified_evaluation_runs[evaluation_id].status = "failed"
        unified_evaluation_runs[evaluation_id].end_time = datetime.now()

        yield create_sse_response({"type": "evaluation_error", "error": str(e)})


@router.post("/start", response_model=UnifiedEvaluationStatus)
async def start_unified_evaluation(
    config: UnifiedEvaluationConfig, settings=Depends(get_settings)
):
    """Start a new unified BIRD evaluation run."""
    try:
        # Validate configuration
        if not config.include_bird_critic and not config.bird_sql_dev_path:
            raise HTTPException(
                status_code=400, detail="Must include at least one dataset type"
            )

        # Initialize evaluator
        evaluator = UnifiedBirdEvaluator(
            settings=settings,
            database_prefix=config.database_prefix,
        )

        # Load datasets
        dataset_counts = {"bird_critic": 0, "bird_sql_dev": 0}

        if config.include_bird_critic:
            evaluator.load_bird_critic_tasks()
            dataset_counts["bird_critic"] = len(
                [
                    t
                    for t in evaluator.tasks
                    if t.dataset_type == DatasetType.BIRD_CRITIC
                ]
            )

        if config.bird_sql_dev_path:
            evaluator.load_bird_sql_dev_tasks(config.bird_sql_dev_path)
            dataset_counts["bird_sql_dev"] = len(
                [
                    t
                    for t in evaluator.tasks
                    if t.dataset_type == DatasetType.BIRD_SQL_DEV
                ]
            )

        # Create evaluation ID
        evaluation_id = str(uuid.uuid4())

        # Calculate total tasks
        total_tasks = (
            len(evaluator.tasks[: config.limit])
            if config.limit
            else len(evaluator.tasks)
        )

        # Initialize status
        status = UnifiedEvaluationStatus(
            evaluation_id=evaluation_id,
            status="running",
            total_tasks=total_tasks,
            bird_critic_tasks=dataset_counts["bird_critic"],
            bird_sql_dev_tasks=dataset_counts["bird_sql_dev"],
            completed_tasks=0,
            successful_tasks=0,
            failed_tasks=0,
            start_time=datetime.now(),
        )

        unified_evaluation_runs[evaluation_id] = status
        unified_evaluation_configs[evaluation_id] = config

        return status

    except Exception as e:
        logger.error("Failed to start unified evaluation", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stream/{evaluation_id}")
async def stream_unified_evaluation(evaluation_id: str):
    """Stream unified evaluation progress using SSE."""
    if evaluation_id not in unified_evaluation_runs:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    try:
        # Get settings and config
        settings = get_settings()
        config = unified_evaluation_configs.get(evaluation_id)
        if not config:
            raise HTTPException(status_code=404, detail="Evaluation config not found")

        # Initialize evaluator
        evaluator = UnifiedBirdEvaluator(
            settings=settings,
            database_prefix=config.database_prefix,
        )

        # Load datasets (same as start)
        if config.include_bird_critic:
            evaluator.load_bird_critic_tasks()

        if config.bird_sql_dev_path:
            evaluator.load_bird_sql_dev_tasks(config.bird_sql_dev_path)

        # Return SSE stream
        return StreamingResponse(
            stream_unified_evaluation_events(evaluator, config, evaluation_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    except Exception as e:
        logger.error(
            "Failed to stream unified evaluation",
            evaluation_id=evaluation_id,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{evaluation_id}", response_model=UnifiedEvaluationStatus)
async def get_unified_evaluation_status(evaluation_id: str):
    """Get current status of a unified evaluation run."""
    if evaluation_id not in unified_evaluation_runs:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    return unified_evaluation_runs[evaluation_id]


@router.get("/list", response_model=List[UnifiedEvaluationStatus])
async def list_unified_evaluations():
    """List all unified evaluation runs."""
    return list(unified_evaluation_runs.values())


@router.get("/export/{evaluation_id}/{format}")
async def export_unified_evaluation_results(
    evaluation_id: str, format: str = "detailed"  # "detailed", "metrics"
):
    """Export unified evaluation results in specified format."""
    if evaluation_id not in unified_evaluation_runs:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    if unified_evaluation_runs[evaluation_id].status != "completed":
        raise HTTPException(status_code=400, detail="Evaluation not completed")

    # Determine file path based on format
    base_file = f"unified_evaluation_{evaluation_id}.json"

    if format == "detailed":
        file_path = base_file
        media_type = "application/json"
    elif format == "metrics":
        file_path = base_file.replace(".json", "_metrics.json")
        media_type = "application/json"
    else:
        raise HTTPException(
            status_code=400, detail="Invalid format. Use 'detailed' or 'metrics'"
        )

    try:
        with open(file_path, "r") as f:
            content = f.read()

        return StreamingResponse(
            iter([content]),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={file_path}"},
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Export file not found")
