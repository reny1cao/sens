"""
API router for BIRD-CRITIC evaluation with streaming support.

This module provides endpoints for running BIRD-CRITIC evaluations
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
from sens.cli.agent_pipeline import AgentNL2SQLPipeline
from sens.evaluation import BirdCriticEvaluator
from sens.settings import get_settings

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/evaluation/bird-critic", tags=["evaluation"])


class EvaluationConfig(BaseModel):
    """Configuration for BIRD-CRITIC evaluation run."""

    limit: Optional[int] = Field(None, description="Limit number of tasks to evaluate")
    database_prefix: str = Field(default="bird_", description="Database name prefix")
    debug_mode: bool = Field(
        default=True, description="Enable debug mode for detailed logs"
    )
    max_iterations: int = Field(default=5, description="Max agent iterations per task")


class EvaluationStatus(BaseModel):
    """Current status of an evaluation run."""

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
evaluation_runs: Dict[str, EvaluationStatus] = {}
evaluation_configs: Dict[str, EvaluationConfig] = {}


async def stream_evaluation_events(
    evaluator: BirdCriticEvaluator, config: EvaluationConfig, evaluation_id: str
):
    """Stream evaluation progress as SSE events."""
    try:
        # Send initial status
        yield create_sse_response(
            {
                "type": "evaluation_start",
                "evaluation_id": evaluation_id,
                "total_tasks": len(evaluator.tasks[: config.limit]),
                "config": config.model_dump(),
            }
        )

        tasks_to_evaluate = (
            evaluator.tasks[: config.limit] if config.limit else evaluator.tasks
        )
        results = []

        for i, task in enumerate(tasks_to_evaluate, 1):
            # Update status
            evaluation_runs[evaluation_id].current_task = task.instance_id
            evaluation_runs[evaluation_id].completed_tasks = i - 1

            # Send task start event
            yield create_sse_response(
                {
                    "type": "task_start",
                    "task_number": i,
                    "total_tasks": len(tasks_to_evaluate),
                    "task_id": task.instance_id,
                    "db_id": task.db_id,
                    "query": task.query,
                }
            )

            # Create event queue for real-time streaming (like chat system)
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

            # Create pipeline with event streaming
            pipeline = AgentNL2SQLPipeline(
                metrics_enabled=False,
                debug_mode=config.debug_mode,
                max_iterations=config.max_iterations,
                event_callback=event_callback,
            )

            # Run evaluation for this task with real-time event streaming
            try:
                # Start the task asynchronously

                async def process_task():
                    return await evaluator.evaluate_task_with_pipeline(task, pipeline)

                # Start processing
                task_future = asyncio.create_task(process_task())

                # Stream events in real-time while processing (like chat system)
                while not task_future.done() or events_queue:
                    # Yield any pending events immediately
                    while events_queue:
                        event = events_queue.pop(0)

                        # Transform event using the same logic as unified router
                        transformed_event = _transform_agent_event_for_evaluation(
                            event, task.instance_id
                        )
                        if transformed_event:
                            yield create_sse_response(
                                data=transformed_event["data"],
                                event=transformed_event["event_type"],
                            )

                    # Small delay to prevent busy waiting (like chat system)
                    if not task_future.done():
                        await asyncio.sleep(0.1)

                # Get the result
                result = await task_future
                results.append(result)

                # Send any remaining events
                while events_queue:
                    event = events_queue.pop(0)

                    # Transform event using the same logic as unified router
                    transformed_event = _transform_agent_event_for_evaluation(
                        event, task.instance_id
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
                        "task_id": task.instance_id,
                        "db_id": task.db_id,  # Add missing field for frontend
                        "query": task.query,  # Add missing field for frontend
                        "success": result.execution_success,
                        "execution_success": result.execution_success,  # Add for compatibility
                        "generated_sql": result.generated_sql,
                        "sql": result.generated_sql,  # Add for compatibility
                        "error": result.execution_error,
                        "execution_error": result.execution_error,  # Add for compatibility
                        "execution_time_ms": result.execution_time_ms,
                        "result_count": result.result_count,
                        "prompt_flow": result.prompt_flow,
                    }
                )

                # Update running metrics
                metrics = evaluator.get_comprehensive_metrics(results)
                evaluation_runs[evaluation_id].metrics = metrics

                # Send metrics update
                yield create_sse_response(
                    {"type": "metrics_update", "metrics": metrics}
                )

                # Update success/failure counts
                if result.execution_success:
                    evaluation_runs[evaluation_id].successful_tasks += 1
                else:
                    evaluation_runs[evaluation_id].failed_tasks += 1

            except Exception as e:
                logger.error(
                    "Task evaluation failed", task_id=task.instance_id, error=str(e)
                )
                yield create_sse_response(
                    {"type": "task_error", "task_id": task.instance_id, "error": str(e)}
                )

        # Save results
        output_file = f"evaluation_{evaluation_id}.json"
        evaluator.save_results(results, output_file)

        # Send completion event
        yield create_sse_response(
            {
                "type": "evaluation_complete",
                "evaluation_id": evaluation_id,
                "total_tasks": len(results),
                "successful_tasks": sum(1 for r in results if r.execution_success),
                "output_files": {
                    "detailed": output_file,
                    "submission": output_file.replace(".json", "_submission.jsonl"),
                    "sql_only": output_file.replace(".json", "_sql_only.json"),
                    "metrics": output_file.replace(".json", "_metrics.json"),
                },
                "final_metrics": evaluation_runs[evaluation_id].metrics,
            }
        )

        # Update final status
        evaluation_runs[evaluation_id].status = "completed"
        evaluation_runs[evaluation_id].end_time = datetime.now()
        evaluation_runs[evaluation_id].completed_tasks = len(results)

    except Exception as e:
        logger.error("Evaluation failed", evaluation_id=evaluation_id, error=str(e))
        evaluation_runs[evaluation_id].status = "failed"
        evaluation_runs[evaluation_id].end_time = datetime.now()

        yield create_sse_response({"type": "evaluation_error", "error": str(e)})


@router.post("/start", response_model=EvaluationStatus)
async def start_evaluation(config: EvaluationConfig, settings=Depends(get_settings)):
    """Start a new BIRD-CRITIC evaluation run."""
    try:
        # Initialize evaluator
        evaluator = BirdCriticEvaluator(
            settings=settings,
            database_prefix=config.database_prefix,
            schema_file_path="external/BIRD-CRITIC-1/baseline/data/post_schema.jsonl",
        )

        # Create evaluation ID
        evaluation_id = str(uuid.uuid4())

        # Initialize status
        total_tasks = (
            len(evaluator.tasks[: config.limit])
            if config.limit
            else len(evaluator.tasks)
        )

        status = EvaluationStatus(
            evaluation_id=evaluation_id,
            status="running",
            total_tasks=total_tasks,
            completed_tasks=0,
            successful_tasks=0,
            failed_tasks=0,
            start_time=datetime.now(),
        )

        evaluation_runs[evaluation_id] = status
        evaluation_configs[evaluation_id] = config  # Store the original config

        return status

    except Exception as e:
        logger.error("Failed to start evaluation", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stream/{evaluation_id}")
async def stream_evaluation(evaluation_id: str):
    """Stream evaluation progress using SSE."""
    if evaluation_id not in evaluation_runs:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    try:
        # Get settings and initialize evaluator
        settings = get_settings()
        evaluator = BirdCriticEvaluator(
            settings=settings,
            database_prefix="bird_",
            schema_file_path="external/BIRD-CRITIC-1/baseline/data/post_schema.jsonl",
        )

        # Get original config from stored configurations
        config = evaluation_configs.get(evaluation_id)
        if not config:
            # Fallback to basic config if not found
            config = EvaluationConfig(limit=evaluation_runs[evaluation_id].total_tasks)

        # Return SSE stream
        return StreamingResponse(
            stream_evaluation_events(evaluator, config, evaluation_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",  # Disable Nginx buffering
            },
        )

    except Exception as e:
        logger.error(
            "Failed to stream evaluation", evaluation_id=evaluation_id, error=str(e)
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{evaluation_id}", response_model=EvaluationStatus)
async def get_evaluation_status(evaluation_id: str):
    """Get current status of an evaluation run."""
    if evaluation_id not in evaluation_runs:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    return evaluation_runs[evaluation_id]


@router.get("/list", response_model=List[EvaluationStatus])
async def list_evaluations():
    """List all evaluation runs."""
    return list(evaluation_runs.values())


@router.get("/export/{evaluation_id}/{format}")
async def export_evaluation_results(
    evaluation_id: str,
    format: str = "submission",  # "submission", "detailed", "sql_only", "metrics", "analysis"
):
    """Export evaluation results in specified format."""
    # Check if evaluation file exists (more reliable than memory check)
    base_file = f"evaluation_{evaluation_id}.json"
    if not Path(base_file).exists():
        raise HTTPException(status_code=404, detail="Evaluation results not found")

    # Check if evaluation is still in memory and completed
    if evaluation_id in evaluation_runs:
        if evaluation_runs[evaluation_id].status != "completed":
            raise HTTPException(status_code=400, detail="Evaluation not completed")

    # Handle new analysis format
    if format == "analysis":
        return await export_analysis_format(evaluation_id)

    # Determine file path based on format
    base_file = f"evaluation_{evaluation_id}.json"

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


async def export_analysis_format(evaluation_id: str):
    """Export evaluation results in a comprehensive analysis format for Claude."""
    import json

    from fastapi.responses import JSONResponse

    try:
        # Load detailed results
        base_file = f"evaluation_{evaluation_id}.json"

        with open(base_file, "r") as f:
            detailed_results = json.load(f)

        # Get evaluation status (if available in memory, otherwise use file data)
        if evaluation_id in evaluation_runs:
            status = evaluation_runs[evaluation_id]
            evaluation_summary = {
                "evaluation_id": evaluation_id,
                "dataset": "BIRD-CRITIC",
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
            results = detailed_results.get("results", [])
            total_tasks = len(results)
            successful_tasks = sum(
                1 for r in results if r.get("execution_success", False)
            )
            failed_tasks = total_tasks - successful_tasks

            evaluation_summary = {
                "evaluation_id": evaluation_id,
                "dataset": "BIRD-CRITIC",
                "status": "completed",  # Assume completed since file exists
                "total_tasks": total_tasks,
                "completed_tasks": total_tasks,
                "successful_tasks": successful_tasks,
                "failed_tasks": failed_tasks,
                "start_time": detailed_results.get("start_time"),
                "end_time": detailed_results.get("end_time"),
                "metrics": detailed_results.get("metrics", {}),
            }

        # Create comprehensive analysis export
        analysis_data = {"evaluation_summary": evaluation_summary, "task_details": []}

        # Process each task result
        for result in detailed_results.get("results", []):
            task_analysis = {
                "task_info": {
                    "task_id": result.get("instance_id", result.get("task_id")),
                    "db_id": result.get("db_id"),
                    "difficulty": result.get("difficulty"),
                    "question": result.get("query", result.get("question")),
                },
                "sql_analysis": {
                    "generated_sql": result.get("generated_sql"),
                    "execution_success": result.get("execution_success"),
                    "execution_error": result.get("execution_error"),
                    "execution_time_ms": result.get("execution_time_ms"),
                    "result_count": result.get("result_count"),
                },
                "thinking_steps": [],
                "performance_metrics": {
                    "execution_success": result.get("execution_success"),
                    "execution_time_ms": result.get("execution_time_ms"),
                    "result_count": result.get("result_count"),
                },
            }

            # Extract thinking steps from prompt flow
            if "prompt_flow" in result and result["prompt_flow"]:
                for i, flow_item in enumerate(result["prompt_flow"]):
                    step = {
                        "step_number": i + 1,
                        "model": flow_item.get("model"),
                        "prompt": flow_item.get("prompt"),
                        "response": flow_item.get("response"),
                        "step_type": (
                            "reasoning"
                            if "reasoning" in flow_item.get("prompt", "").lower()
                            else "action"
                        ),
                    }
                    task_analysis["thinking_steps"].append(step)

            analysis_data["task_details"].append(task_analysis)

        # Create filename and return as downloadable JSON
        filename = f"evaluation_{evaluation_id}_analysis.json"
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
        logger.error("Failed to export analysis format", error=str(e))
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.delete("/{evaluation_id}")
async def cancel_evaluation(evaluation_id: str):
    """Cancel a running BIRD-CRITIC evaluation."""
    if evaluation_id not in evaluation_runs:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    status = evaluation_runs[evaluation_id]
    if status.status == "running":
        status.status = "cancelled"
        status.end_time = datetime.now()

    return {"message": "Evaluation cancelled", "evaluation_id": evaluation_id}


def _transform_agent_event_for_evaluation(
    event: Dict[str, Any], task_id: str
) -> Optional[Dict[str, Any]]:
    """Transform agent event to chat-compatible format for evaluation UI."""
    from datetime import datetime

    event_type = event.get("type")
    event_data = event.get("data", {})
    timestamp = event.get("timestamp", datetime.utcnow().isoformat())

    # Map agent event types to frontend event types (same as unified router)
    if event_type == "reasoning":
        return {
            "event_type": "thought",
            "data": {
                "task_id": task_id,
                "content": event_data.get("reasoning", ""),
                "iteration": event_data.get("iteration", 1),
                "timestamp": timestamp,
            },
        }
    elif event_type == "action":
        action_type = event_data.get("action_type", "unknown")
        parameters = event_data.get("parameters", {})

        # Format action content based on type (same logic as unified router)
        if action_type == "EXPLORE_DATABASE":
            query = parameters.get("query", "")
            content = f"Exploring database: {query}"
        elif action_type == "EXECUTE_SQL":
            sql = parameters.get("sql", "")
            content = "Executing SQL query" if sql else "Executing SQL"
        elif action_type == "GENERATE_SQL":
            content = "Generating SQL query based on the available schema"
        elif action_type == "SEARCH_SCHEMA":
            search_term = parameters.get("search_term", "")
            content = (
                f"Searching schema for: {search_term}"
                if search_term
                else "Searching schema"
            )
        elif action_type == "EXPLORE_TABLE":
            table = parameters.get("table_name", "")
            content = (
                f"Exploring table: {table}" if table else "Exploring table structure"
            )
        elif action_type == "VALIDATE_SQL":
            content = "Validating SQL query"
        elif action_type == "ANSWER":
            content = "Generating answer based on results"
        elif action_type == "CLARIFY_QUERY":
            content = "Requesting clarification"
        elif action_type == "SEARCH_VALUES":
            table = parameters.get("table_name", "")
            column = parameters.get("column_name", "")
            if table and column:
                content = f"Searching values in {table}.{column}"
            else:
                content = "Searching for matching values"
        else:
            content = action_type.replace("_", " ").title()
            if parameters and action_type not in ["PROVIDE_ANSWER", "SUGGEST_OPTIONS"]:
                # For other actions, show concise parameter info
                key_params = []
                for k, v in parameters.items():
                    if k in ["table_name", "column_name", "search_term", "query"]:
                        key_params.append(f"{k}={v}")
                if key_params:
                    content += f" ({', '.join(key_params[:2])})"

        return {
            "event_type": "action",
            "data": {
                "task_id": task_id,
                "content": content,
                "iteration": event_data.get("iteration", 1),
                "timestamp": timestamp,
                "metadata": {"action_type": action_type, "parameters": parameters},
            },
        }
    elif event_type == "observation":
        # Get the actual observation content
        content_preview = event_data.get("content_preview", "")

        # Format based on what's in the observation (same logic as unified router)
        if event_data.get("error"):
            content = f"Error: {event_data['error']}"
        elif isinstance(content_preview, dict):
            # Handle structured observation data
            if content_preview.get("error"):
                content = content_preview["error"]
            elif content_preview.get("row_count") is not None:
                row_count = content_preview.get("row_count", 0)
                columns = content_preview.get("columns", [])

                # Generate descriptive content based on result structure
                if row_count == 0:
                    content = "No results found"
                else:
                    # Simple, clear messaging
                    if row_count == 1:
                        content = "Found 1 result"
                    else:
                        content = f"Found {row_count} results"

                    # Add column info only if it helps understanding
                    if columns and len(columns) > 1:
                        content += f" ({len(columns)} fields)"
            elif content_preview.get("success") is False:
                error_msg = content_preview.get("error", "Unknown error")
                content = error_msg
            else:
                # Generic successful observation
                content = "Action completed successfully"
        elif event_data.get("row_count") is not None:
            # Direct row count from event data
            row_count = event_data.get("row_count", 0)
            if row_count == 0:
                content = "Query executed successfully. No results found."
            else:
                content = f"Found {row_count} result{'s' if row_count != 1 else ''}"
        else:
            # Fallback to string representation
            if isinstance(content_preview, str):
                # Check if it looks like SQL (common SQL keywords)
                sql_keywords = [
                    "SELECT",
                    "FROM",
                    "WHERE",
                    "JOIN",
                    "INSERT",
                    "UPDATE",
                    "DELETE",
                ]
                if any(keyword in content_preview.upper() for keyword in sql_keywords):
                    # It's SQL, just show that it was generated
                    content = "SQL query generated successfully"
                else:
                    content = (
                        content_preview[:200] + "..."
                        if len(content_preview) > 200
                        else content_preview
                    )
            else:
                content = (
                    str(content_preview) if content_preview else "Action completed"
                )

        return {
            "event_type": "observation",
            "data": {
                "task_id": task_id,
                "content": content,
                "iteration": event_data.get("iteration", 1),
                "timestamp": timestamp,
            },
        }
    elif event_type == "sql_generated":
        return {
            "event_type": "sql_generated",
            "data": {
                "task_id": task_id,
                "content": event_data.get("sql", "SQL query generated"),
                "sql": event_data.get("sql", ""),
                "iteration": event_data.get("iteration", 1),
                "timestamp": timestamp,
            },
        }
    elif event_type == "generating_answer":
        return {
            "event_type": "answer",
            "data": {
                "task_id": task_id,
                "content": event_data.get("content", "Generating answer..."),
                "iteration": event_data.get("iteration", 1),
                "timestamp": timestamp,
            },
        }

    # Return None for unsupported event types
    return None
