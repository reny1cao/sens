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
    event_data = event.get("data", {})

    if event_type == "reasoning":
        # Agent emits reasoning events with "reasoning" field, not "content"
        reasoning_text = event_data.get("reasoning", "")
        return {
            "event_type": "thought",
            "data": {
                "content": reasoning_text,
                "task_id": task_id,
                "timestamp": event.get("timestamp"),
                "iteration": event_data.get("iteration", 1),
            },
        }
    elif event_type == "action":
        # Agent emits action events with "action_type" field
        action_type = event_data.get("action_type", "unknown")
        parameters = event_data.get("parameters", {})

        # Create a more informative action description
        action_desc = action_type.replace("_", " ").title()
        if action_type == "EXECUTE_SQL" and "sql" in parameters:
            content = "Executing SQL query"
        elif action_type == "SWITCH_DATABASE" and "db_path" in parameters:
            content = f"Switching to database: {parameters.get('db_path', 'unknown')}"
        elif action_type == "EXPLORE_DATABASE":
            table_name = parameters.get("table_name")
            content = f"Exploring {'table ' + table_name if table_name else 'database schema'}"
        else:
            content = f"Performing action: {action_desc}"

        return {
            "event_type": "action",
            "data": {
                "content": content,
                "task_id": task_id,
                "timestamp": event.get("timestamp"),
                "iteration": event_data.get("iteration", 1),
                "metadata": {
                    "action_type": action_type,
                    "parameters": parameters,
                },
            },
        }
    elif event_type == "observation":
        success = event_data.get("success", True)
        error = event_data.get("error")

        # Extract more details from observation
        if error:
            content = f"Error: {error}"
        elif success:
            # Check if this is a SQL execution result
            if "row_count" in event_data:
                row_count = event_data.get("row_count", 0)
                execution_time = event_data.get("execution_time_ms")
                if execution_time:
                    content = f"Query executed successfully: {row_count} rows returned in {execution_time:.1f}ms"
                else:
                    content = f"Query executed successfully: {row_count} rows returned"
            elif "table_count" in event_data:
                # Database exploration result
                table_count = event_data.get("table_count", 0)
                content = f"Found {table_count} tables in database"
            elif "databases_found" in event_data:
                # Database discovery result
                db_count = event_data.get("databases_found", 0)
                content = f"Found {db_count} database(s)"
            else:
                content = "Action completed successfully"
        else:
            content = "Action failed"

        return {
            "event_type": "observation",
            "data": {
                "content": content,
                "task_id": task_id,
                "timestamp": event.get("timestamp"),
                "iteration": event_data.get("iteration", 1),
                "metadata": (
                    event_data
                    if success and ("row_count" in event_data or "rows" in event_data)
                    else None
                ),
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
                "failed_tasks": sum(
                    1 for r in results if not r.execution_success
                ),  # Add missing field
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


@router.get("/export/{evaluation_id}/{format}")
async def export_bird_sql_dev_results(
    evaluation_id: str,
    format: str = "submission",  # "submission", "detailed", "sql_only", "metrics", "analysis"
):
    """Export BIRD-SQL-DEV evaluation results in specified format."""
    # Check if evaluation file exists (more reliable than memory check)
    base_file = f"bird_sql_dev_evaluation_{evaluation_id}.json"
    if not Path(base_file).exists():
        raise HTTPException(status_code=404, detail="Evaluation results not found")

    # Check if evaluation is still in memory and completed
    if evaluation_id in bird_sql_dev_runs:
        if bird_sql_dev_runs[evaluation_id].status != "completed":
            raise HTTPException(status_code=400, detail="Evaluation not completed")

    # Handle new analysis format
    if format == "analysis":
        return await export_bird_sql_dev_analysis_format(evaluation_id)

    # Determine file path based on format
    base_file = f"bird_sql_dev_evaluation_{evaluation_id}.json"

    if format == "submission":
        file_path = base_file.replace(".json", "_submission.jsonl")
        media_type = "application/x-ndjson"
    elif format == "detailed":
        file_path = base_file
        media_type = "application/json"
    elif format == "sql_only":
        file_path = base_file.replace(".json", "_sql_only.json")
        media_type = "application/json"
    elif format == "metrics":
        file_path = base_file.replace(".json", "_metrics.json")
        media_type = "application/json"
    else:
        raise HTTPException(status_code=400, detail="Invalid format")

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


async def export_bird_sql_dev_analysis_format(evaluation_id: str):
    """Export BIRD-SQL-DEV results in a comprehensive analysis format for Claude."""
    import json

    from fastapi.responses import StreamingResponse

    try:
        # Load detailed results
        base_file = f"bird_sql_dev_evaluation_{evaluation_id}.json"

        with open(base_file, "r") as f:
            detailed_results = json.load(f)

        # Get evaluation status (if available in memory, otherwise use file data)
        if evaluation_id in bird_sql_dev_runs:
            status = bird_sql_dev_runs[evaluation_id]
            evaluation_summary = {
                "evaluation_id": evaluation_id,
                "dataset": "BIRD-SQL-DEV",
                "status": status.status,
                "total_tasks": status.total_tasks,
                "completed_tasks": status.completed_tasks,
                "successful_tasks": status.successful_tasks,
                "failed_tasks": status.failed_tasks,
                "start_time": (
                    status.start_time.isoformat() if status.start_time else None
                ),
                "end_time": status.end_time.isoformat() if status.end_time else None,
                "metrics": status.metrics,
            }
        else:
            # Use data from results file if not in memory
            # Handle both array format (BIRD-SQL-DEV) and object format (other evaluations)
            if isinstance(detailed_results, list):
                results = detailed_results
            else:
                results = detailed_results.get("results", [])
            total_tasks = len(results)
            successful_tasks = sum(
                1 for r in results if r.get("execution_success", False)
            )
            failed_tasks = total_tasks - successful_tasks

            evaluation_summary = {
                "evaluation_id": evaluation_id,
                "dataset": "BIRD-SQL-DEV",
                "status": "completed",  # Assume completed since file exists
                "total_tasks": total_tasks,
                "completed_tasks": total_tasks,
                "successful_tasks": successful_tasks,
                "failed_tasks": failed_tasks,
                "start_time": (
                    detailed_results.get("start_time")
                    if isinstance(detailed_results, dict)
                    else None
                ),
                "end_time": (
                    detailed_results.get("end_time")
                    if isinstance(detailed_results, dict)
                    else None
                ),
                "metrics": (
                    detailed_results.get("metrics", {})
                    if isinstance(detailed_results, dict)
                    else {}
                ),
            }

        # Create comprehensive analysis export for BIRD-SQL-DEV
        analysis_data = {"evaluation_summary": evaluation_summary, "task_details": []}

        # Process each task result
        # Handle both array format (BIRD-SQL-DEV) and object format (other evaluations)
        if isinstance(detailed_results, list):
            results_list = detailed_results
        else:
            results_list = detailed_results.get("results", [])

        for result in results_list:
            task_analysis = {
                "task_info": {
                    "task_id": result.get("question_id", result.get("task_id")),
                    "db_id": result.get("db_id"),
                    "difficulty": result.get("difficulty"),
                    "question": result.get("question"),
                },
                "sql_analysis": {
                    "generated_sql": result.get("generated_sql"),
                    "golden_sql": result.get("golden_sql"),
                    "execution_success": result.get("execution_success"),
                    "execution_error": result.get("execution_error"),
                    "execution_time_ms": result.get("execution_time_ms"),
                    "result_count": result.get("result_count"),
                },
                "match_analysis": {
                    "exact_match": result.get("exact_match"),
                    "normalized_match": result.get("normalized_match"),
                    "execution_match": result.get("execution_match"),
                },
                "thinking_steps": [],
                "performance_metrics": {
                    "execution_success": result.get("execution_success"),
                    "execution_time_ms": result.get("execution_time_ms"),
                    "result_count": result.get("result_count"),
                    "exact_match": result.get("exact_match"),
                    "normalized_match": result.get("normalized_match"),
                    "execution_match": result.get("execution_match"),
                },
            }

            # Extract thinking steps from agent events if available
            if "agent_events" in result and result["agent_events"]:
                for i, event in enumerate(result["agent_events"]):
                    step = {
                        "step_number": i + 1,
                        "event_type": event.get("type"),
                        "content": event.get("content"),
                        "iteration": event.get("iteration", 1),
                        "timestamp": event.get("timestamp"),
                        "metadata": event.get("metadata", {}),
                    }
                    task_analysis["thinking_steps"].append(step)
            # Note: agent_events are typically not saved in the final results file
            # They're only available during real-time streaming

            # Add SQL comparison analysis
            if (
                task_analysis["sql_analysis"]["generated_sql"]
                and task_analysis["sql_analysis"]["golden_sql"]
            ):
                task_analysis["sql_comparison"] = {
                    "generated_length": len(
                        task_analysis["sql_analysis"]["generated_sql"]
                    ),
                    "golden_length": len(task_analysis["sql_analysis"]["golden_sql"]),
                    "exact_match": task_analysis["match_analysis"]["exact_match"],
                    "normalized_match": task_analysis["match_analysis"][
                        "normalized_match"
                    ],
                    "execution_match": task_analysis["match_analysis"][
                        "execution_match"
                    ],
                }

            analysis_data["task_details"].append(task_analysis)

        # Create filename and return as downloadable JSON
        filename = f"bird_sql_dev_evaluation_{evaluation_id}_analysis.json"
        content = json.dumps(analysis_data, indent=2, ensure_ascii=False)

        return StreamingResponse(
            iter([content]),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": "application/json; charset=utf-8",
            },
        )

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Evaluation results not found")
    except Exception as e:
        logger.error("Failed to export BIRD-SQL-DEV analysis format", error=str(e))
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
