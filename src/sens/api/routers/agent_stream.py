"""Clean SSE streaming for agent queries following 2025 best practices."""

import asyncio
import json
import uuid
from typing import Any, AsyncGenerator, Dict

import structlog
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from sens.agents.event_emitter import EventEmittingAgent
from sens.agents.memory import AgentMemory
from sens.agents.reasoning import ReasoningEngine
from sens.agents.tools import AgentTools

log = structlog.get_logger()

router = APIRouter(prefix="/nl2sql/agent/v2", tags=["agent-stream"])


class StreamQueryRequest(BaseModel):
    question: str
    max_iterations: int = 10
    session_id: str = None


async def generate_agent_stream(
    query: str, max_iterations: int = 10, session_id: str = None
) -> AsyncGenerator[str, None]:
    """Generate clean SSE events following 2025 best practices."""
    # Generate transaction ID
    tx_id = uuid.uuid4().hex
    yield f"event: start\ndata: {tx_id}\n\n"

    try:
        # Initialize agent
        tools = AgentTools()
        memory = AgentMemory()
        reasoning_engine = ReasoningEngine()

        agent = EventEmittingAgent(
            tools=tools,
            memory=memory,
            reasoning_engine=reasoning_engine,
            max_iterations=max_iterations,
        )

        # Collect all thinking content
        all_thinking = []

        def handle_agent_event(event):
            """Handle agent events and collect thinking content."""
            event_type = event["type"]
            event_data = event["data"]

            if event_type == "reasoning":
                reasoning_text = event_data.get("reasoning", "")
                if reasoning_text:
                    all_thinking.append(
                        f"Iteration {event_data['iteration']}: {reasoning_text}\n"
                    )

            elif event_type == "action":
                action_type = event_data.get("action_type", "unknown")
                all_thinking.append(f"Action: {action_type}\n")

            elif event_type == "observation":
                success = event_data.get("success", False)
                all_thinking.append(f"Result: {'Success' if success else 'Failed'}\n")

            elif event_type == "generating_answer":
                all_thinking.append("Generating natural language response...\n")

        agent.add_event_handler(handle_agent_event)

        # Process the query
        result = await agent.process_query(
            user_query=query, conversation_id=session_id or tx_id
        )

        # Stream all thinking content at once (can be improved later for real-time)
        if all_thinking:
            thinking_text = "".join(all_thinking)
            yield f"event: thinking\ndata: {thinking_text}\n\n"

        # Emit SQL if generated
        if result.get("sql"):
            yield f"event: sql\ndata: {result['sql']}\n\n"

        # Emit data if available
        if result.get("success") and result.get("result"):
            # Transform to frontend format
            data_payload = {
                "sql": result.get("sql", ""),
                "results": {
                    "columns": result["result"].get("columns", []),
                    "data": [
                        dict(zip(result["result"].get("columns", []), row))
                        for row in result["result"].get("rows", [])
                    ],
                    "row_count": result["result"].get("row_count", 0),
                },
                "metadata": {
                    "execution_time_ms": 0,
                    "confidence_score": 0.9 if result.get("success") else 0.3,
                },
            }
            yield f"event: data\ndata: {json.dumps(data_payload)}\n\n"

        # Emit answer if generated
        if result.get("answer"):
            yield f"event: answer\ndata: {result['answer']}\n\n"

        # Completion
        yield f"event: done\ndata: {json.dumps('')}\n\n"

    except Exception as e:
        log.error("stream_generation_error", error=str(e))
        yield f"event: error\ndata: {str(e)}\n\n"


@router.get("/stream")
async def stream_agent_query(
    question: str, max_iterations: int = 10, session_id: str = None, req: Request = None
):
    """Start streaming agent query processing."""

    async def event_publisher():
        try:
            async for event_data in generate_agent_stream(
                query=question, max_iterations=max_iterations, session_id=session_id
            ):
                yield event_data
                await asyncio.sleep(0)  # Yield control back to event loop

                # Check for client disconnect
                if await req.is_disconnected():
                    break

        except asyncio.CancelledError:
            log.info("client_disconnected")
            pass

    return StreamingResponse(
        event_publisher(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering
        },
    )
