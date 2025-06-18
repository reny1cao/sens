"""Natural Language to SQL API router with Agent support and SSE streaming."""

import asyncio
import time
import uuid
from typing import Dict, Optional

import structlog
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from sens.agents.event_emitter import EventEmittingAgent
from sens.agents.memory import AgentMemory
from sens.agents.reasoning import ReasoningEngine
from sens.agents.tools import AgentTools
from sens.api.common.message_formatter import AgentMessageFormatter
from sens.api.common.sse import (
    AgentEventType,
    SSEMessage,
    create_agent_event,
    heartbeat_generator,
)
from sens.exceptions import AgentError
from sens.settings import get_settings

log = structlog.get_logger()


def transform_agent_result_to_api_format(agent_result: Dict) -> Dict:
    """Transform agent result to match frontend QueryResponse format."""
    log.info(
        "transform_agent_result_start",
        success=agent_result.get("success"),
        has_result=bool(agent_result.get("result")),
        result_keys=(
            list(agent_result.get("result", {}).keys())
            if isinstance(agent_result.get("result"), dict)
            else None
        ),
        full_agent_result_keys=list(agent_result.keys()),
        result_content=(
            agent_result.get("result") if agent_result.get("result") else "No result"
        ),
    )

    # If there's no result at all, return error
    if not agent_result.get("result"):
        log.warning(
            "transform_agent_no_result",
            success=agent_result.get("success"),
            error=agent_result.get("error"),
            iterations=agent_result.get("iterations"),
        )
        # Provide more context about why the query failed
        error_message = agent_result.get("error", "")
        if not error_message and agent_result.get("iterations") >= 10:
            error_message = "Unable to find the requested data after exploring the database. The table or data you're looking for may not exist."
        elif not error_message:
            error_message = "Agent failed to process query"

        return {
            "error": {
                "code": "AGENT_ERROR",
                "message": error_message,
            }
        }

    # Extract the actual result from agent response
    result_data = agent_result.get("result", {})

    # Transform rows to data format expected by frontend
    rows = result_data.get("rows", [])
    columns = result_data.get("columns", [])

    log.info(
        "transform_data_extraction",
        has_rows=bool(rows),
        row_count=len(rows),
        columns=columns,
        first_row=rows[0] if rows else None,
    )

    # Convert rows (list of lists) to data (list of dicts)
    data = []
    for row in rows:
        if isinstance(row, list) and len(row) == len(columns):
            data.append(dict(zip(columns, row)))
        elif isinstance(row, dict):
            data.append(row)

    log.info(
        "transform_data_conversion",
        data_count=len(data),
        first_data_item=data[0] if data else None,
    )

    transformed_result = {
        "sql": agent_result.get("sql", ""),
        "results": {
            "columns": columns,
            "data": data,
            "row_count": result_data.get("row_count", len(data)),
            "truncated": len(rows) >= 100,  # Agent limits to 100 rows
        },
        "metadata": {
            "execution_time_ms": 0,  # Agent doesn't track this currently
            "tables_used": [],  # Could extract from SQL
            "query_type": "select",
            "confidence_score": 0.9 if agent_result.get("success") else 0.3,
        },
        "summary": f"Found {result_data.get('row_count', 0)} results",
        "answer": agent_result.get("answer"),  # Include natural language answer
    }

    log.info(
        "transform_result_complete",
        has_sql=bool(transformed_result.get("sql")),
        result_columns=transformed_result.get("results", {}).get("columns"),
        result_data_count=len(transformed_result.get("results", {}).get("data", [])),
        result_row_count=transformed_result.get("results", {}).get("row_count"),
    )

    return transformed_result


# Initialize router
router = APIRouter(
    prefix="/nl2sql/agent",
    tags=["nl2sql-agent"],
    responses={
        400: {"description": "Bad Request"},
        422: {"description": "Validation Error"},
        500: {"description": "Internal Server Error"},
    },
)


# Request/Response models
class AgentQueryRequest(BaseModel):
    question: str
    max_iterations: Optional[int] = 10
    session_id: Optional[str] = None


class AgentQueryResponse(BaseModel):
    query_id: str
    status: str = "processing"
    message: str = "Query processing started"


# In-memory storage for active queries (use Redis in production)
active_queries: Dict[str, Dict] = {}
query_results: Dict[str, Dict] = {}


@router.post("/query", response_model=AgentQueryResponse)
async def start_agent_query(request: AgentQueryRequest):
    """Start an agent-based query processing."""
    query_id = str(uuid.uuid4())

    # Store query info
    active_queries[query_id] = {
        "question": request.question,
        "status": "processing",
        "started_at": time.time(),
        "events": [],
        "session_id": request.session_id or query_id,
    }

    # Start processing in background
    asyncio.create_task(
        process_agent_query(
            query_id=query_id,
            question=request.question,
            max_iterations=request.max_iterations,
        )
    )

    return AgentQueryResponse(
        query_id=query_id, status="processing", message="Agent is processing your query"
    )


async def process_agent_query(query_id: str, question: str, max_iterations: int):
    """Process query using agent in background."""
    try:
        # Create event-emitting agent with our notes system
        tools = AgentTools()
        memory = AgentMemory()
        reasoning_engine = ReasoningEngine()

        try:
            agent = EventEmittingAgent(
                tools=tools,
                memory=memory,
                reasoning_engine=reasoning_engine,
                max_iterations=max_iterations,
            )
            log.info("agent_created_successfully", query_id=query_id)
        except TypeError as e:
            log.error("agent_construction_failed", query_id=query_id, error=str(e))
            raise AgentError(f"Failed to create agent: {e}")

        # Add event handler to store events
        def store_event(event):
            if query_id in active_queries:
                active_queries[query_id]["events"].append(event)
                log.debug(
                    "event_stored",
                    query_id=query_id,
                    event_type=event.get("type"),
                    total_events=len(active_queries[query_id]["events"]),
                )

        agent.add_event_handler(store_event)

        # Process the query
        result = await agent.process_query(
            user_query=question, conversation_id=active_queries[query_id]["session_id"]
        )

        # Transform result to API format
        transformed_result = transform_agent_result_to_api_format(result)

        # Store results
        query_results[query_id] = {
            "status": "completed",
            "result": transformed_result,
            "completed_at": time.time(),
        }

        # Update status
        if query_id in active_queries:
            active_queries[query_id]["status"] = "completed"

    except Exception as e:
        log.error("agent_query_failed", query_id=query_id, error=str(e))

        # Store error
        query_results[query_id] = {
            "status": "error",
            "error": str(e),
            "completed_at": time.time(),
        }

        # Update status
        if query_id in active_queries:
            active_queries[query_id]["status"] = "error"
            active_queries[query_id]["error"] = str(e)


@router.get("/stream/{query_id}")
async def stream_agent_events(query_id: str, request: Request):
    """Stream agent events via Server-Sent Events."""
    if query_id not in active_queries:
        raise HTTPException(status_code=404, detail="Query not found")

    async def event_generator():
        """Generate SSE events for the agent processing."""
        last_event_idx = 0

        # Send initial connection event
        yield SSEMessage(
            data={
                "type": "connection",
                "query_id": query_id,
                "message": "Connected to agent event stream",
            },
            event="connection",
        ).format()

        # Stream events as they happen
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                break

            # Get query info
            query_info = active_queries.get(query_id)
            if not query_info:
                break

            # Send new events
            events = query_info.get("events", [])
            while last_event_idx < len(events):
                event = events[last_event_idx]

                # Map internal events to SSE events
                event_type = event["type"]
                if event_type in ("reasoning", "reasoning_start"):
                    # Format reasoning message for user
                    formatted_content = AgentMessageFormatter.format_reasoning(
                        event["data"]
                    )
                    sse_event = create_agent_event(
                        event_type=AgentEventType.THOUGHT,
                        iteration=event["data"]["iteration"],
                        content=formatted_content,
                        metadata=event["data"],
                        event_id=f"{query_id}_{last_event_idx}",
                    )
                elif event_type == "thought":
                    sse_event = create_agent_event(
                        event_type=AgentEventType.THOUGHT,
                        iteration=event["data"]["iteration"],
                        content=event["data"]["content"],
                        metadata=event["data"].get("metadata", {}),
                        event_id=f"{query_id}_{last_event_idx}",
                    )
                elif event_type == "action":
                    # Format action message for user
                    formatted_content = AgentMessageFormatter.format_action(
                        event["data"]
                    )

                    # Include SQL in metadata if it's a generate or execute action
                    metadata = {
                        "action_type": event["data"]["action_type"],
                        "parameters": event["data"]["parameters"],
                    }

                    # Add formatted SQL for display
                    if event["data"]["action_type"] in ["GENERATE_SQL", "EXECUTE_SQL"]:
                        if "query" in event["data"].get("parameters", {}):
                            metadata["sql"] = (
                                AgentMessageFormatter.format_sql_for_display(
                                    event["data"]["parameters"]["query"]
                                )
                            )

                    sse_event = create_agent_event(
                        event_type=AgentEventType.ACTION,
                        iteration=event["data"]["iteration"],
                        content=formatted_content,
                        metadata=metadata,
                        event_id=f"{query_id}_{last_event_idx}",
                    )
                elif event_type == "observation":
                    # Format observation message for user
                    formatted_content = AgentMessageFormatter.format_observation(
                        event["data"]
                    )
                    sse_event = create_agent_event(
                        event_type=AgentEventType.OBSERVATION,
                        iteration=event["data"]["iteration"],
                        content=formatted_content,
                        metadata=event["data"],
                        event_id=f"{query_id}_{last_event_idx}",
                    )
                elif event_type == "generating_answer":
                    sse_event = create_agent_event(
                        event_type=AgentEventType.THOUGHT,
                        iteration=event["data"]["iteration"],
                        content=event["data"]["content"],
                        metadata=event["data"],
                        event_id=f"{query_id}_{last_event_idx}",
                    )
                elif event_type == "query_start":
                    # Map query start to thought for frontend
                    sse_event = create_agent_event(
                        event_type=AgentEventType.THOUGHT,
                        iteration=0,
                        content="Starting query processing...",
                        metadata=event["data"],
                        event_id=f"{query_id}_{last_event_idx}",
                    )
                elif event_type == "answer_generated":
                    sse_event = create_agent_event(
                        event_type=AgentEventType.ANSWER,
                        iteration=event["data"]["iteration"],
                        content=event["data"]["content"],
                        metadata=event["data"],
                        event_id=f"{query_id}_{last_event_idx}",
                    )
                elif event_type == "query_complete":
                    sse_event = create_agent_event(
                        event_type=AgentEventType.COMPLETE,
                        iteration=event["data"]["iterations"],
                        content="Query processing completed",
                        metadata=event["data"],
                        event_id=f"{query_id}_{last_event_idx}",
                    )
                elif event_type == "query_error":
                    sse_event = create_agent_event(
                        event_type=AgentEventType.ERROR,
                        iteration=0,
                        content=event["data"]["error"],
                        metadata=event["data"],
                        event_id=f"{query_id}_{last_event_idx}",
                    )
                else:
                    # Skip other event types
                    last_event_idx += 1
                    continue

                yield sse_event.format()
                last_event_idx += 1

            # Check if processing is complete
            if query_info["status"] in ["completed", "error"]:
                log.info(
                    "query_completion_detected",
                    query_id=query_id,
                    status=query_info["status"],
                    total_events=len(events),
                    last_event_idx=last_event_idx,
                )

                # Send final event if not already sent
                if query_info["status"] == "completed" and last_event_idx == len(
                    events
                ):
                    log.info("sending_final_completion_event", query_id=query_id)
                    yield create_agent_event(
                        event_type=AgentEventType.COMPLETE,
                        iteration=0,
                        content="Processing finished",
                        event_id=f"{query_id}_final",
                    ).format()
                break

            # Small delay to prevent busy waiting
            await asyncio.sleep(0.1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering
        },
    )


@router.get("/result/{query_id}")
async def get_agent_result(query_id: str):
    """Get the final result of an agent query."""
    log.info("get_agent_result_called", query_id=query_id)

    if query_id not in query_results:
        if query_id in active_queries:
            log.info(
                "query_still_processing",
                query_id=query_id,
                status=active_queries[query_id]["status"],
            )
            return {
                "status": active_queries[query_id]["status"],
                "message": "Query still processing",
            }
        else:
            log.warning("query_not_found", query_id=query_id)
            raise HTTPException(status_code=404, detail="Query not found")

    result = query_results[query_id]

    log.info(
        "returning_query_result",
        query_id=query_id,
        status=result.get("status"),
        has_result=bool(result.get("result")),
        result_keys=(
            list(result.get("result", {}).keys())
            if isinstance(result.get("result"), dict)
            else None
        ),
    )

    # Clean up old data (in production, use TTL in Redis)
    if result.get("completed_at", 0) < time.time() - 3600:  # 1 hour
        del query_results[query_id]
        if query_id in active_queries:
            del active_queries[query_id]

    return result


@router.get("/status/{query_id}")
async def get_query_status(query_id: str):
    """Get the current status of a query."""
    if query_id in active_queries:
        query_info = active_queries[query_id]
        return {
            "status": query_info["status"],
            "started_at": query_info["started_at"],
            "event_count": len(query_info.get("events", [])),
            "last_event": (
                query_info["events"][-1] if query_info.get("events") else None
            ),
        }
    elif query_id in query_results:
        return {"status": query_results[query_id]["status"], "completed": True}
    else:
        raise HTTPException(status_code=404, detail="Query not found")
