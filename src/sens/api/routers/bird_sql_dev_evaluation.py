"""
API router for BIRD-SQL-DEV evaluation with streaming support.

This module provides endpoints for running BIRD-SQL-DEV evaluations
with real-time streaming of agent thinking steps and progress updates.
"""

import asyncio
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from sens.api.common.sse import create_sse_response
from sens.evaluation.bird_sql_dev_evaluator import BirdSqlDevEvaluator
from sens.settings import get_settings

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/evaluation/bird-sql-dev", tags=["evaluation"])


class BirdSqlDevConfig(BaseModel):
    """Configuration for BIRD-SQL-DEV evaluation run."""

    dataset_path: str = Field(..., description="Path to BIRD-SQL-DEV dev.json file")
    database_dir: str = Field(
        default="external/BIRD-SQL-DEV/dev_databases",
        description="Directory containing SQLite databases",
    )
    limit: Optional[int] = Field(None, description="Limit number of tasks to evaluate")
    debug_mode: bool = Field(
        default=True, description="Enable debug mode for detailed logs"
    )
    max_iterations: int = Field(default=25, description="Max agent iterations per task")


class BirdSqlDevStatus(BaseModel):
    """Current status of a BIRD-SQL-DEV evaluation run."""

    evaluation_id: str
    status: str  # "running", "completed", "failed"
    total_tasks: int
    completed_tasks: int
    successful_tasks: int
    failed_tasks: int
    current_task: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    metrics: Dict[str, Any] = {}


# In-memory storage for evaluation runs (in production, use Redis/DB)
bird_sql_dev_runs: Dict[str, BirdSqlDevStatus] = {}
bird_sql_dev_configs: Dict[str, BirdSqlDevConfig] = {}


def _transform_agent_event_for_bird_sql_dev(
    event: Dict, task_id: str
) -> Optional[Dict]:
    """Transform agent events for BIRD-SQL-DEV evaluation streaming."""
    event_type = event.get("type")

    if event_type == "reasoning":
        return {
            "event_type": "thought",
            "data": {
                "content": event["data"]["content"],
                "task_id": task_id,
                "timestamp": event.get("timestamp"),
                "iteration": event["data"].get("step", 1),
            },
        }
    elif event_type == "action":
        return {
            "event_type": "action",
            "data": {
                "content": event["data"].get(
                    "reasoning", event["data"]["action_type"].replace("_", " ").title()
                ),
                "task_id": task_id,
                "timestamp": event.get("timestamp"),
                "iteration": event["data"].get("step", 1),
                "metadata": {
                    "action_type": event["data"]["action_type"],
                    "parameters": event["data"].get("parameters", {}),
                },
            },
        }
    elif event_type == "observation":
        success = event["data"].get("success", True)
        error = event["data"].get("error")

        if error:
            content = f"Error: {error}"
        elif success:
            content = "Action completed successfully"
        else:
            content = "Action failed"

        return {
            "event_type": "observation",
            "data": {
                "content": content,
                "task_id": task_id,
                "timestamp": event.get("timestamp"),
                "iteration": event["data"].get("step", 1),
            },
        }
    elif event_type == "sql_generated":
        return {
            "event_type": "sql_generated",
            "data": {
                "content": event["data"]["sql"],
                "sql": event["data"]["sql"],
                "task_id": task_id,
                "timestamp": event.get("timestamp"),
                "iteration": event["data"].get("step", 1),
            },
        }

    return None


async def stream_bird_sql_dev_events(
    evaluator: BirdSqlDevEvaluator, config: BirdSqlDevConfig, evaluation_id: str
):
    """Stream BIRD-SQL-DEV evaluation progress as SSE events."""
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
                "config": config.model_dump(),
            }
        )

        tasks_to_evaluate = (
            evaluator.tasks[: config.limit] if config.limit else evaluator.tasks
        )
        results = []

        for i, task in enumerate(tasks_to_evaluate, 1):
            # Update status
            bird_sql_dev_runs[evaluation_id].current_task = task.question_id
            bird_sql_dev_runs[evaluation_id].completed_tasks = i - 1

            # Send task start event
            yield create_sse_response(
                {
                    "type": "task_start",
                    "task_number": i,
                    "total_tasks": len(tasks_to_evaluate),
                    "task_id": task.question_id,
                    "instance_id": task.question_id,  # Add for compatibility
                    "db_id": task.db_id,
                    "question": task.question,
                    "query": task.question,  # Add for compatibility
                    "difficulty": task.difficulty,
                    "golden_sql": task.golden_sql,
                }
            )

            # Create event queue for real-time streaming
            events_queue = []

            def event_callback(event):
                """Callback to capture and queue agent events for real-time streaming."""
                if event.get("type") in [
                    "reasoning",
                    "action",
                    "observation",
                    "sql_generated",
                ]:
                    events_queue.append(event)

            # Run evaluation for this task with real-time event streaming
            try:
                # Start the task asynchronously
                async def process_task():
                    return await evaluator.evaluate_task(
                        task, event_callback=event_callback
                    )

                # Start processing
                task_future = asyncio.create_task(process_task())

                # Stream events in real-time while processing
                while not task_future.done() or events_queue:
                    # Yield any pending events immediately
                    while events_queue:
                        event = events_queue.pop(0)

                        # Transform event for BIRD-SQL-DEV evaluation
                        transformed_event = _transform_agent_event_for_bird_sql_dev(
                            event, task.question_id
                        )
                        if transformed_event:
                            yield create_sse_response(
                                data=transformed_event["data"],
                                event=transformed_event["event_type"],
                            )

                    # Small delay to prevent busy waiting
                    if not task_future.done():
                        await asyncio.sleep(0.1)

                # Get the result
                result = await task_future
                results.append(result)

                # Send any remaining events
                while events_queue:
                    event = events_queue.pop(0)

                    # Transform event for BIRD-SQL-DEV evaluation
                    transformed_event = _transform_agent_event_for_bird_sql_dev(
                        event, task.question_id
                    )
                    if transformed_event:
                        yield create_sse_response(
                            data=transformed_event["data"],
                            event=transformed_event["event_type"],
                        )

                # Send task completion event
                yield create_sse_response(
                    {
                        "type": "task_complete",
                        "task_id": task.question_id,
                        "instance_id": task.question_id,  # Add for compatibility
                        "db_id": task.db_id,
                        "question": task.question,
                        "query": task.question,  # Add for compatibility
                        "success": result.execution_success,
                        "execution_success": result.execution_success,
                        "generated_sql": result.generated_sql,
                        "sql": result.generated_sql,  # Add for compatibility
                        "golden_sql": result.golden_sql,
                        "exact_match": result.exact_match,
                        "normalized_match": result.normalized_match,
                        "execution_match": result.execution_match,
                        "error": result.execution_error,
                        "execution_error": result.execution_error,
                        "execution_time_ms": result.execution_time_ms,
                        "result_count": result.result_count,
                        "difficulty": result.difficulty,
                    },
                    event="task_complete",
                )

                # Update running metrics
                metrics = evaluator.calculate_metrics(results)
                bird_sql_dev_runs[evaluation_id].metrics = metrics

                # Send metrics update
                yield create_sse_response(
                    {"type": "metrics_update", "metrics": metrics}
                )

                # Update success/failure counts
                if result.execution_success:
                    bird_sql_dev_runs[evaluation_id].successful_tasks += 1
                else:
                    bird_sql_dev_runs[evaluation_id].failed_tasks += 1

            except Exception as e:
                logger.error(
                    "Task evaluation failed", task_id=task.question_id, error=str(e)
                )
                yield create_sse_response(
                    {"type": "task_error", "task_id": task.question_id, "error": str(e)}
                )

        # Save results
        output_file = f"bird_sql_dev_evaluation_{evaluation_id}.json"
        evaluator.save_results(results, output_file)

        # Send completion event
        yield create_sse_response(
            {
                "type": "evaluation_complete",
                "evaluation_id": evaluation_id,
                "total_tasks": len(results),
                "successful_tasks": sum(1 for r in results if r.execution_success),
                "exact_matches": sum(1 for r in results if r.exact_match),
                "normalized_matches": sum(1 for r in results if r.normalized_match),
                "execution_matches": sum(1 for r in results if r.execution_match),
                "output_files": {
                    "detailed": output_file,
                    "metrics": output_file.replace(".json", "_metrics.json"),
                },
                "final_metrics": bird_sql_dev_runs[evaluation_id].metrics,
            }
        )

        # Update final status
        bird_sql_dev_runs[evaluation_id].status = "completed"
        bird_sql_dev_runs[evaluation_id].end_time = datetime.now()
        bird_sql_dev_runs[evaluation_id].completed_tasks = len(results)

    except Exception as e:
        logger.error(
            "BIRD-SQL-DEV evaluation failed", evaluation_id=evaluation_id, error=str(e)
        )
        bird_sql_dev_runs[evaluation_id].status = "failed"
        bird_sql_dev_runs[evaluation_id].end_time = datetime.now()

        yield create_sse_response({"type": "evaluation_error", "error": str(e)})


@router.post("/start", response_model=BirdSqlDevStatus)
async def start_bird_sql_dev_evaluation(
    config: BirdSqlDevConfig, settings=Depends(get_settings)
):
    """Start a new BIRD-SQL-DEV evaluation run."""
    try:
        # Validate dataset path
        dataset_path = Path(config.dataset_path)
        if not dataset_path.exists():
            raise HTTPException(
                status_code=400, detail=f"Dataset file not found: {config.dataset_path}"
            )

        # Validate database directory
        db_dir = Path(config.database_dir)
        if not db_dir.exists():
            raise HTTPException(
                status_code=400,
                detail=f"Database directory not found: {config.database_dir}",
            )

        # Initialize evaluator
        evaluator = BirdSqlDevEvaluator(database_dir=config.database_dir)

        # Create evaluation ID
        evaluation_id = str(uuid.uuid4())

        # Load tasks
        evaluator.load_tasks(config.dataset_path)

        # Store configuration
        bird_sql_dev_configs[evaluation_id] = config

        # Initialize status
        status = BirdSqlDevStatus(
            evaluation_id=evaluation_id,
            status="running",
            total_tasks=(
                len(evaluator.tasks[: config.limit])
                if config.limit
                else len(evaluator.tasks)
            ),
            completed_tasks=0,
            successful_tasks=0,
            failed_tasks=0,
            start_time=datetime.now(),
        )
        bird_sql_dev_runs[evaluation_id] = status

        # Start evaluation asynchronously
        async def run_evaluation():
            async for _ in stream_bird_sql_dev_events(evaluator, config, evaluation_id):
                pass  # Events are handled in the streaming endpoint

        asyncio.create_task(run_evaluation())

        logger.info(
            "Started BIRD-SQL-DEV evaluation",
            evaluation_id=evaluation_id,
            total_tasks=status.total_tasks,
            limit=config.limit,
        )

        return status

    except Exception as e:
        logger.error("Failed to start BIRD-SQL-DEV evaluation", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stream/{evaluation_id}")
async def stream_bird_sql_dev_evaluation(evaluation_id: str):
    """Stream BIRD-SQL-DEV evaluation progress."""
    if evaluation_id not in bird_sql_dev_runs:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    config = bird_sql_dev_configs.get(evaluation_id)
    if not config:
        raise HTTPException(status_code=404, detail="Evaluation config not found")

    # Initialize evaluator
    evaluator = BirdSqlDevEvaluator(database_dir=config.database_dir)
    evaluator.load_tasks(config.dataset_path)

    async def generate():
        async for event in stream_bird_sql_dev_events(evaluator, config, evaluation_id):
            yield event

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )


@router.get("/status/{evaluation_id}", response_model=BirdSqlDevStatus)
async def get_bird_sql_dev_status(evaluation_id: str):
    """Get current status of BIRD-SQL-DEV evaluation."""
    if evaluation_id not in bird_sql_dev_runs:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    return bird_sql_dev_runs[evaluation_id]


@router.get("/active", response_model=List[BirdSqlDevStatus])
async def get_active_bird_sql_dev_evaluations():
    """Get all active BIRD-SQL-DEV evaluation runs."""
    return [
        status for status in bird_sql_dev_runs.values() if status.status == "running"
    ]


@router.delete("/{evaluation_id}")
async def cancel_bird_sql_dev_evaluation(evaluation_id: str):
    """Cancel a running BIRD-SQL-DEV evaluation."""
    if evaluation_id not in bird_sql_dev_runs:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    status = bird_sql_dev_runs[evaluation_id]
    if status.status == "running":
        status.status = "cancelled"
        status.end_time = datetime.now()

    return {"message": "Evaluation cancelled", "evaluation_id": evaluation_id}
