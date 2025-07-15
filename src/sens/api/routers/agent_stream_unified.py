"""
Unified agent streaming endpoint - replaces agent_stream.py and agent_stream_enhanced.py
Clean SSE implementation with full memory integration.
"""

import asyncio
import json
import uuid
from typing import Any, AsyncGenerator, Dict, Optional

import structlog
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from sens.agents.reasoning import ReasoningEngine
from sens.agents.tools import AgentTools
from sens.agents.unified import UnifiedSENSAgent
from sens.chat.session import SessionManager
from sens.memory import AgentMemory, AgentMemoryTools
from sens.settings import get_settings

log = structlog.get_logger()

router = APIRouter(prefix="/nl2sql/agent/v2", tags=["agent-unified"])
# Add compatibility router with original prefix for frontend
compat_router = APIRouter(prefix="/nl2sql/agent", tags=["agent-compat"])


class StreamQueryRequest(BaseModel):
    question: str
    max_iterations: int = 10
    session_id: Optional[str] = None
    enable_memory: bool = True
    enable_reflection: bool = True


class QueryStartRequest(BaseModel):
    question: str
    max_iterations: int = 10


class QueryStartResponse(BaseModel):
    query_id: str


class AgentStreamManager:
    """Manages agent streaming with clean event generation."""

    def __init__(self, enable_memory: bool = None):
        """Initialize stream manager with configurable memory."""

        # Get settings for memory configuration
        self.settings = get_settings()
        self.memory_config = self.settings.memory

        # Use settings to determine if memory should be enabled
        if enable_memory is None:
            enable_memory = self.memory_config.enabled

        # Initialize tools and engines
        self.tools = AgentTools()
        self.reasoning_engine = ReasoningEngine()

        # Initialize session manager for conversation context
        self.session_manager = SessionManager()

        # Memory management - use shared memory manager to avoid database locks
        self.memory_enabled = enable_memory
        self.global_memory_tools = None
        self.session_memories = {}  # Cache for session-specific memories

        # Get shared memory manager if enabled
        if enable_memory:
            try:
                # Import here to avoid circular imports and use the same memory manager as the API
                from .memory_management import get_memory_manager

                # Use the exact same memory manager as the memory API to avoid database locks
                self.global_memory_tools = get_memory_manager("global")
                if self.global_memory_tools:
                    log.info(
                        "using_same_memory_manager_as_api",
                        session_isolation=self.memory_config.session_isolation,
                    )
                else:
                    log.warning("memory_manager_not_available")
                    self.memory_enabled = False
            except Exception as e:
                log.warning("memory_manager_access_failed", error=str(e))
                self.memory_enabled = False

    def get_memory_tools(self, session_id: str) -> Optional[AgentMemoryTools]:
        """Get memory tools for a specific session."""
        if not self.memory_enabled:
            return None

        # If session isolation is disabled, use global memory
        if not self.memory_config.session_isolation:
            return self.global_memory_tools

        # Check cache first
        if session_id in self.session_memories:
            return self.session_memories[session_id]

        try:
            # Create session-specific memory
            session_db_path = f"memory_session_{session_id}.db"
            session_memory = AgentMemory(db_path=session_db_path)
            session_memory_tools = AgentMemoryTools(session_memory)

            # Cache for future use
            self.session_memories[session_id] = session_memory_tools

            log.info(
                "session_memory_created", session_id=session_id, db_path=session_db_path
            )

            # Bootstrap with global knowledge if this is a new session
            if self.memory_config.cross_session_sharing and self.global_memory_tools:
                asyncio.create_task(
                    self._bootstrap_session_memory(session_memory_tools, session_id)
                )

            return session_memory_tools

        except Exception as e:
            log.warning(
                "session_memory_creation_failed", session_id=session_id, error=str(e)
            )
            # Fallback to global memory
            return self.global_memory_tools

    async def _bootstrap_session_memory(
        self, session_memory_tools: AgentMemoryTools, session_id: str
    ):
        """Bootstrap new session with successful patterns from global memory."""
        try:
            if not self.global_memory_tools:
                return

            # Get top successful patterns from global memory
            global_patterns = await self.global_memory_tools.recall_knowledge(
                query="", memory_types=["pattern", "concept", "mapping"], limit=20
            )

            if global_patterns.success and global_patterns.data["memories"]:
                inherited_count = 0
                for memory in global_patterns.data["memories"]:
                    # Only inherit highly successful memories
                    if (
                        memory["success_rate"]
                        > self.memory_config.min_confidence_threshold
                    ):
                        memory_type = memory["type"]
                        content = memory["content"]

                        if memory_type == "pattern":
                            await session_memory_tools.remember_pattern(
                                name=f"inherited_{memory['name']}",
                                trigger_phrase=content.get("trigger_phrase", ""),
                                sql_template=content.get("sql_template", ""),
                                tables_used=content.get("tables_used", []),
                                success_context=content.get("success_context", {}),
                                context={
                                    "inherited_from": "global",
                                    "original_confidence": memory["confidence"],
                                    "original_success_rate": memory["success_rate"],
                                },
                            )
                            inherited_count += 1
                        elif memory_type == "concept":
                            await session_memory_tools.remember_concept(
                                name=f"inherited_{memory['name']}",
                                description=content.get("description", ""),
                                business_terms=content.get("business_terms", []),
                                database_mapping=content.get("database_mapping", {}),
                                context={
                                    "inherited_from": "global",
                                    "original_confidence": memory["confidence"],
                                },
                            )
                            inherited_count += 1
                        elif memory_type == "mapping":
                            await session_memory_tools.remember_mapping(
                                name=f"inherited_{memory['name']}",
                                user_term=content.get("user_term", ""),
                                database_value=content.get("database_value", ""),
                                mapping_type=content.get("mapping_type", ""),
                                context={
                                    "inherited_from": "global",
                                    "original_confidence": memory["confidence"],
                                },
                            )
                            inherited_count += 1

                log.info(
                    "session_memory_bootstrapped",
                    session_id=session_id,
                    inherited_memories=inherited_count,
                )

        except Exception as e:
            log.warning(
                "session_memory_bootstrap_failed", session_id=session_id, error=str(e)
            )

    async def generate_stream(
        self,
        query: str,
        max_iterations: int = 10,
        session_id: Optional[str] = None,
        enable_reflection: bool = True,
    ) -> AsyncGenerator[str, None]:
        """Generate SSE events for agent processing."""

        # Generate transaction ID
        tx_id = session_id or uuid.uuid4().hex
        yield f"event: start\ndata: {tx_id}\n\n"

        try:
            # Get session-specific memory tools
            memory_tools = self.get_memory_tools(session_id or tx_id)

            # Debug logging for memory tools
            log.info(
                "agent_stream_memory_debug",
                session_id=session_id or tx_id,
                memory_tools_available=memory_tools is not None,
                memory_enabled=self.memory_enabled,
                global_memory_tools_available=self.global_memory_tools is not None,
            )

            # Create unified agent with session-specific memory
            agent = UnifiedSENSAgent(
                tools=self.tools,
                memory_tools=memory_tools,
                reasoning_engine=self.reasoning_engine,
                session_manager=self.session_manager,
                max_iterations=max_iterations,
                streaming_enabled=True,
                memory_enabled=memory_tools is not None,
                conversation_enabled=True,
                reflection_enabled=enable_reflection,
                minimal_mode=False,  # Full features for web UI
            )

            # Additional debug logging after agent creation
            log.info(
                "unified_agent_memory_debug",
                agent_memory_enabled=agent.memory_enabled,
                agent_memory_tools_available=agent.memory_tools is not None,
                agent_memory_tools_type=(
                    type(agent.memory_tools).__name__ if agent.memory_tools else None
                ),
            )

            # Collect all thinking content (matching original behavior)
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
                    all_thinking.append(
                        f"Result: {'Success' if success else 'Failed'}\n"
                    )

                elif event_type == "generating_answer":
                    all_thinking.append("Generating natural language response...\n")

                elif event_type == "answer_provided":
                    all_thinking.append("Answer provided\n")

            agent.add_event_handler(handle_agent_event)

            # Process the query
            result = await agent.process_query(query, tx_id)

            # Stream all thinking content at once (matching original behavior)
            if all_thinking:
                thinking_text = "".join(all_thinking)
                yield f"event: thinking\ndata: {thinking_text}\n\n"

            # Result is already available from process_query above

            # Stream SQL if generated
            if result.get("sql"):
                yield f"event: sql\ndata: {result['sql']}\n\n"

            # Stream data if available
            if result.get("success") and result.get("result"):
                data_payload = self._format_data_payload(result)
                yield f"event: data\ndata: {json.dumps(data_payload)}\n\n"

            # Stream answer if generated
            if result.get("answer"):
                yield f"event: answer\ndata: {result['answer']}\n\n"

            # Stream performance metrics
            if hasattr(agent, "get_performance_metrics"):
                metrics = agent.get_performance_metrics()
                yield f"event: metrics\ndata: {json.dumps(metrics)}\n\n"

            # Completion
            yield f"event: done\ndata: {json.dumps('')}\n\n"

        except Exception as e:
            log.error("stream_generation_error", error=str(e), query=query)
            yield f"event: error\ndata: {str(e)}\n\n"

    def _format_data_payload(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Format result data for frontend consumption."""

        query_result = result.get("result", {})

        # Handle different result types
        if query_result.get("clarification_needed"):
            return {
                "type": "clarification",
                "message": query_result.get("message", ""),
                "options": query_result.get("options", []),
            }

        elif query_result.get("direct_answer"):
            return {"type": "direct_answer", "answer": query_result.get("answer", "")}

        elif query_result.get("suggestions"):
            return {
                "type": "suggestions",
                "suggestions": query_result.get("suggestions", []),
                "context": query_result.get("context", ""),
            }

        else:
            # Standard SQL results
            return {
                "sql": result.get("sql", ""),
                "results": {
                    "columns": query_result.get("columns", []),
                    "data": [
                        dict(zip(query_result.get("columns", []), row))
                        for row in query_result.get("rows", [])
                    ],
                    "row_count": query_result.get("row_count", 0),
                },
                "metadata": {
                    "execution_time_ms": 0,
                    "confidence_score": 0.9 if result.get("success") else 0.3,
                    "iterations": result.get("iterations", 0),
                    "memory_used": result.get("discovered_mappings") is not None,
                },
            }


# Global stream manager instance (memory configuration from settings)
stream_manager = AgentStreamManager()

# Simple in-memory storage for active queries (no persistence needed for chat)
query_runs: Dict[str, Dict] = {}


def _transform_agent_event_for_chat(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Transform agent event to chat-compatible format (copied from evaluation.py)."""
    from datetime import datetime

    event_type = event.get("type")
    event_data = event.get("data", {})
    timestamp = event.get("timestamp", datetime.utcnow().isoformat())

    # Map agent event types to frontend event types (same as evaluation router)
    if event_type == "reasoning":
        return {
            "event_type": "thought",
            "data": {
                "content": event_data.get("reasoning", ""),
                "iteration": event_data.get("iteration", 1),
                "timestamp": timestamp,
            },
        }
    elif event_type == "action":
        action_type = event_data.get("action_type", "unknown")
        content = f"Executing {action_type.replace('_', ' ').lower()}"
        return {
            "event_type": "action",
            "data": {
                "content": content,
                "iteration": event_data.get("iteration", 1),
                "timestamp": timestamp,
            },
        }
    elif event_type == "observation":
        content_preview = event_data.get("content_preview", "")
        if event_data.get("error"):
            content = f"Error: {event_data['error']}"
        elif (
            isinstance(content_preview, dict)
            and content_preview.get("row_count") is not None
        ):
            row_count = content_preview.get("row_count", 0)
            content = (
                "No results found"
                if row_count == 0
                else f"Found {row_count} result{'s' if row_count != 1 else ''}"
            )
        else:
            content = "Action completed"

        return {
            "event_type": "observation",
            "data": {
                "content": content,
                "iteration": event_data.get("iteration", 1),
                "timestamp": timestamp,
            },
        }
    elif event_type == "generating_answer":
        return {
            "event_type": "answer",
            "data": {
                "content": event_data.get("content", "Generating answer..."),
                "iteration": event_data.get("iteration", 1),
                "timestamp": timestamp,
            },
        }
    elif event_type == "answer_provided":
        return {
            "event_type": "answer",
            "data": {
                "content": event_data.get("content", ""),
                "iteration": event_data.get("iteration", 1),
                "timestamp": timestamp,
            },
        }

    return None


def format_result_for_frontend(result: Dict[str, Any]) -> Dict[str, Any]:
    """Format agent result for frontend consumption."""
    if not result:
        return {"success": True, "answer": "No result available"}

    # For agent results, we want to show success even if SQL execution failed
    # The agent did its job by reasoning and generating SQL
    formatted = {
        "success": True,  # Always true for completed agent runs
        "sql": result.get("sql"),
        "iterations": result.get("iterations", 0),
    }

    # Handle different result types
    if result.get("result") and isinstance(result["result"], dict):
        inner_result = result["result"]

        # Clarification case
        if inner_result.get("clarification_needed"):
            formatted.update(
                {
                    "clarification_needed": True,
                    "message": inner_result.get("message", ""),
                    "options": inner_result.get("options", []),
                }
            )

        # SQL execution results
        elif inner_result.get("columns") and inner_result.get("rows"):
            formatted["results"] = {
                "columns": inner_result["columns"],
                "rows": inner_result["rows"],
                "data": [
                    dict(zip(inner_result["columns"], row))
                    for row in inner_result["rows"]
                ],
                "row_count": inner_result.get("row_count", len(inner_result["rows"])),
            }

        # Direct answer
        elif inner_result.get("answer"):
            formatted["answer"] = inner_result["answer"]

    # If we have actions but no clear result, show that the agent worked
    if (
        result.get("actions_taken")
        and not formatted.get("answer")
        and not formatted.get("clarification_needed")
    ):
        actions = result["actions_taken"]
        if actions:
            last_action = actions[-1]
            action_type = last_action.get("type", "")

            if action_type == "generate_sql" and result.get("sql"):
                formatted["answer"] = f"Generated SQL query: {result['sql']}"
            elif "error" in last_action.get("reasoning", "").lower():
                formatted["answer"] = (
                    "Query processed but encountered database issues. Check the generated SQL."
                )
            else:
                formatted["answer"] = (
                    f"Completed {len(actions)} reasoning steps. Check the generated SQL."
                )

    # Fallback answer
    if not formatted.get("answer") and not formatted.get("clarification_needed"):
        if result.get("sql"):
            formatted["answer"] = "Query processed successfully. SQL generated."
        else:
            formatted["answer"] = "Query processed."

    return formatted


async def stream_agent_events(question: str, max_iterations: Optional[int] = None):
    """Stream agent processing events (simplified - no storage needed)."""
    from sens.api.common.sse import create_sse_response
    from sens.cli.agent_pipeline import AgentNL2SQLPipeline

    try:
        # Create event queue for real-time streaming (like evaluation system)
        events_queue = []

        def event_callback(event):
            """Callback to capture and queue agent events for real-time streaming."""
            if event.get("type") in [
                "reasoning",
                "action",
                "observation",
                "generating_answer",
            ]:
                events_queue.append(event)

        # Create pipeline with event streaming (same as evaluation)
        pipeline = AgentNL2SQLPipeline(
            metrics_enabled=False,
            debug_mode=True,
            max_iterations=max_iterations,
            event_callback=event_callback,
        )

        # Start the query asynchronously
        async def process_query():
            return await pipeline.process_question(question)

        # Start processing
        query_task = asyncio.create_task(process_query())

        # Stream events in real-time while processing (same logic as evaluation)
        while not query_task.done() or events_queue:
            # Yield any pending events immediately
            while events_queue:
                event = events_queue.pop(0)

                # Transform event using the same logic as evaluation router
                transformed_event = _transform_agent_event_for_chat(event)
                if transformed_event:
                    yield create_sse_response(
                        data=transformed_event["data"],
                        event=transformed_event["event_type"],
                    )

            # Small delay to prevent busy waiting (same as evaluation)
            if not query_task.done():
                await asyncio.sleep(0.1)

        # Get the result
        result = await query_task

        # Send any remaining events
        while events_queue:
            event = events_queue.pop(0)
            transformed_event = _transform_agent_event_for_chat(event)
            if transformed_event:
                yield create_sse_response(
                    data=transformed_event["data"],
                    event=transformed_event["event_type"],
                )

        # Send result event with proper formatting for frontend
        formatted_result = format_result_for_frontend(result)
        yield create_sse_response(
            {"type": "result", "content": formatted_result, "timestamp": ""}
        )

        # Send completion
        yield create_sse_response({"type": "complete"})

    except Exception as e:
        log.error("stream_agent_events_error", error=str(e))
        yield create_sse_response({"type": "error", "content": str(e), "error": str(e)})


@router.get("/stream")
async def stream_agent_query(
    question: str,
    max_iterations: int = 10,
    session_id: Optional[str] = None,
    enable_memory: bool = True,
    enable_reflection: bool = True,
    req: Request = None,
):
    """
    Stream agent query processing with real-time events.

    This endpoint replaces both /v2/stream and /memory/stream with a unified implementation.
    """

    async def event_publisher():
        try:
            async for event_data in stream_manager.generate_stream(
                query=question,
                max_iterations=max_iterations,
                session_id=session_id,
                enable_reflection=enable_reflection,
            ):
                yield event_data

                # Check for client disconnect
                if req and await req.is_disconnected():
                    log.info("client_disconnected", session_id=session_id)
                    break

        except asyncio.CancelledError:
            log.info("stream_cancelled", session_id=session_id)
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


@router.post("/stream")
async def stream_agent_query_post(request: StreamQueryRequest, req: Request = None):
    """POST endpoint for streaming with request body."""

    return await stream_agent_query(
        question=request.question,
        max_iterations=request.max_iterations,
        session_id=request.session_id,
        enable_memory=True,
        enable_reflection=True,
        req=req,
    )


# Frontend compatibility endpoints - simplified approach
@compat_router.post("/query")
async def start_agent_query(request: QueryStartRequest) -> QueryStartResponse:
    """Start an agent query and return a query ID for streaming."""
    query_id = str(uuid.uuid4())

    # Store minimal info just for the streaming endpoint to access
    query_runs[query_id] = {
        "question": request.question,
        "max_iterations": request.max_iterations,
    }

    return QueryStartResponse(query_id=query_id)


@compat_router.get("/stream/{query_id}")
async def stream_agent_query_by_id(query_id: str):
    """Stream events for a specific query ID."""
    if query_id not in query_runs:
        raise HTTPException(status_code=404, detail="Query not found")

    query_info = query_runs[query_id]

    # Return SSE stream directly (no storage needed)
    return StreamingResponse(
        stream_agent_events(
            question=query_info["question"], max_iterations=query_info["max_iterations"]
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@compat_router.get("/result/{query_id}")
async def get_agent_result(query_id: str):
    """Get result - not needed for chat but frontend expects it."""
    # For chat, result comes via the stream, but keep endpoint for compatibility
    return {"message": "Result provided via stream", "query_id": query_id}
