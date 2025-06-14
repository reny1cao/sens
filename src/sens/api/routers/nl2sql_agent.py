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
from sens.api.common.sse import (
    AgentEventType,
    SSEMessage,
    create_agent_event,
    heartbeat_generator,
)
from sens.settings import get_settings

log = structlog.get_logger()

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
        # Create event-emitting agent
        agent = EventEmittingAgent(max_iterations=max_iterations)

        # Add event handler to store events
        def store_event(event):
            if query_id in active_queries:
                active_queries[query_id]["events"].append(event)

        agent.add_event_handler(store_event)

        # Process the query
        result = await agent.process_query(
            user_query=question, conversation_id=active_queries[query_id]["session_id"]
        )

        # Store results
        query_results[query_id] = {
            "status": "completed",
            "result": result,
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
                if event_type == "thought":
                    sse_event = create_agent_event(
                        event_type=AgentEventType.THOUGHT,
                        iteration=event["data"]["iteration"],
                        content=event["data"]["content"],
                        metadata=event["data"].get("metadata", {}),
                        event_id=f"{query_id}_{last_event_idx}",
                    )
                elif event_type == "action":
                    sse_event = create_agent_event(
                        event_type=AgentEventType.ACTION,
                        iteration=event["data"]["iteration"],
                        content=f"{event['data']['action_type']}: {event['data'].get('reasoning', '')}",
                        metadata={
                            "action_type": event["data"]["action_type"],
                            "parameters": event["data"]["parameters"],
                        },
                        event_id=f"{query_id}_{last_event_idx}",
                    )
                elif event_type == "observation":
                    sse_event = create_agent_event(
                        event_type=AgentEventType.OBSERVATION,
                        iteration=event["data"]["iteration"],
                        content=f"Result: {'Success' if event['data']['success'] else 'Failed'}",
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
                # Send final event if not already sent
                if query_info["status"] == "completed" and last_event_idx == len(
                    events
                ):
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

    if query_id not in query_results:
        if query_id in active_queries:
            return {
                "status": active_queries[query_id]["status"],
                "message": "Query still processing",
            }
        else:
            raise HTTPException(status_code=404, detail="Query not found")

    result = query_results[query_id]

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
