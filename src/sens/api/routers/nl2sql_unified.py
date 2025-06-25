"""
Unified NL2SQL router that consolidates all nl2sql endpoints.

This router replaces:
- nl2sql.py (standard queries)
- nl2sql_simple.py (simplified interface)
- nl2sql_agent.py (agent-based queries)
- nl2sql_simple_agent.py (simple agent with notes)
- nl2sql_session.py (session-aware queries)
- nl2sql_dev.py (development/mock mode)

All functionality is preserved while reducing code duplication
and using the new standardized architecture.
"""

import json
import time
from datetime import datetime
from decimal import Decimal
from typing import Any, AsyncGenerator, Dict, Optional

import structlog
from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

# Agent imports
from ...agents.event_emitter import EventEmittingAgent
from ...agents.tools import AgentTools
from ...api.models import NL2SQLRequest, NL2SQLResponse, QueryMetadata, QueryMode
from ...chat.session import SessionManager
from ...common import (
    MetricsCollector,
    ResponseBuilder,
    error_handler,
    handle_exceptions,
)
from ...common.errors import DatabaseError, NotFoundError, ValidationError
from ...common.response_builder import format_sql_results
from ...datasource.manager import DataSourceManager
from ...interfaces import Pipeline, PipelineContext, PipelineResult
from ...registry import component_registry
from ...registry.component_registry import ComponentType
from ...schema.graph import SchemaGraph
from ...settings import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

# Router configuration
router = APIRouter(
    prefix="/nl2sql",
    tags=["nl2sql-unified"],
    responses={
        400: {"description": "Bad request"},
        404: {"description": "Not found"},
        500: {"description": "Internal server error"},
    },
)

# Component singletons
_components_initialized = False
_orchestrator_pipeline: Optional[Pipeline] = None
_agent_pipeline: Optional[Pipeline] = None
_session_pipeline: Optional[Pipeline] = None
_session_manager: Optional[SessionManager] = None
_agent: Optional[Any] = None  # EventEmittingAgent when available

# In-memory storage for agent results (with TTL)
_agent_results: Dict[str, Dict[str, Any]] = {}
_result_cleanup_times: Dict[str, float] = {}


def store_agent_result(query_id: str, result: Dict[str, Any], ttl_seconds: int = 300):
    """Store agent result with TTL."""
    _agent_results[query_id] = result
    _result_cleanup_times[query_id] = time.time() + ttl_seconds

    # Clean up expired results
    current_time = time.time()
    expired_keys = [k for k, v in _result_cleanup_times.items() if v < current_time]
    for key in expired_keys:
        _agent_results.pop(key, None)
        _result_cleanup_times.pop(key, None)


async def initialize_components():
    """Initialize all required components."""
    global _components_initialized, _orchestrator_pipeline, _agent_pipeline
    global _session_pipeline, _session_manager, _agent

    if not _components_initialized:
        # Ensure schema is loaded
        datasource_manager = DataSourceManager()
        await datasource_manager.ensure_default_schema_extracted()

        # Initialize session manager
        _session_manager = SessionManager()

        # Get pipelines from registry
        try:
            _orchestrator_pipeline = component_registry.get_by_type(
                ComponentType.PIPELINE,
                name="orchestrator_pipeline",
                config={"session_manager": _session_manager},
            )
        except NotFoundError:
            logger.warning("Orchestrator pipeline not found in registry")

        # Initialize agent if needed
        if settings.mock_mode:
            logger.info("Mock mode enabled - agent features disabled")
        else:
            try:
                # Initialize agent with tools
                tools = AgentTools()
                _agent = EventEmittingAgent(tools=tools, max_iterations=5)
                logger.info("Agent initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize agent: {e}")
                _agent = None

        _components_initialized = True
        logger.info("NL2SQL components initialized")


async def get_pipeline(mode: QueryMode = QueryMode.STANDARD) -> Pipeline:
    """Get appropriate pipeline based on query mode."""
    await initialize_components()

    if mode == QueryMode.STANDARD or mode == QueryMode.SIMPLE:
        if not _orchestrator_pipeline:
            raise ValidationError("Standard pipeline not available")
        return _orchestrator_pipeline
    elif mode == QueryMode.AGENT:
        # Agent mode doesn't use a pipeline - it uses the agent directly
        # Return None to signal agent mode
        return None
    elif mode == QueryMode.SESSION:
        # For now, use orchestrator pipeline for session mode too
        # TODO: Implement actual session-aware pipeline
        if not _orchestrator_pipeline:
            raise ValidationError("Session pipeline not available")
        return _orchestrator_pipeline
    else:
        raise ValidationError(f"Unknown query mode: {mode}")


async def get_request_id(x_request_id: Optional[str] = Header(None)) -> str:
    """Extract or generate request ID."""
    import uuid

    return x_request_id or str(uuid.uuid4())


# Main query endpoint
@router.post("/query", response_model=NL2SQLResponse)
@handle_exceptions(
    {
        ValidationError: lambda e: error_handler.to_http_response(e),
        DatabaseError: lambda e: error_handler.to_http_response(e),
    }
)
async def query(
    request: NL2SQLRequest,
    request_id: str = Depends(get_request_id),
) -> NL2SQLResponse:
    """
    Main NL2SQL query endpoint with mode-based processing.

    Modes:
    - standard: Uses ChatOrchestrator for queries
    - simple: Same as standard but with simplified response
    - agent: Uses agent-based processing with self-correction
    - session: Session-aware with custom datasources
    - mock: Returns mock responses for testing
    """

    # Handle mock mode
    if settings.mock_mode or request.mode == QueryMode.MOCK:
        return _mock_response(request, request_id)

    # Handle agent mode separately
    if request.mode == QueryMode.AGENT:
        await initialize_components()
        if not _agent:
            raise ValidationError("Agent not available")

        # Process with agent
        conversation_id = request.session_id or request_id
        result = await _agent.process_query(request.question, conversation_id)

        # Convert agent result to API response
        sql_result = None
        if result.get("success") and result.get("result"):
            agent_result = result["result"]
            # Check if it's a SQL execution result
            if (
                isinstance(agent_result, dict)
                and "rows" in agent_result
                and "columns" in agent_result
            ):
                # Convert rows from list of lists to list of dicts for format_sql_results
                rows_as_dicts = []
                columns = agent_result.get("columns", [])
                for row in agent_result.get("rows", []):
                    row_dict = {}
                    for i, col in enumerate(columns):
                        row_dict[col] = row[i] if i < len(row) else None
                    rows_as_dicts.append(row_dict)
                sql_result = format_sql_results(rows_as_dicts, columns)
            # Otherwise, it might be a conversational response - pass it through
            else:
                sql_result = agent_result

        return NL2SQLResponse(
            success=result.get("success", False),
            sql=result.get("sql", ""),
            results=sql_result,
            error=result.get("error"),
            session_id=request.session_id,
            metadata=(
                QueryMetadata(
                    query_id=request_id,
                    processing_time_ms=100.0,  # TODO: Add actual timing
                    steps_timing={},
                    iterations=result.get("iterations", 0),
                    agent_trace=result.get("actions_taken", []),
                )
                if request.include_metadata
                else None
            ),
        )

    # Get appropriate pipeline
    pipeline = await get_pipeline(request.mode)

    with MetricsCollector(f"nl2sql.query.{request.mode.value}") as metrics:
        metrics.add_tag("mode", request.mode.value)
        metrics.add_tag("request_id", request_id)

        # Create pipeline context
        context = PipelineContext(
            query=request.question,
            session_id=request.session_id,
            datasource_id=request.datasource_id,
            use_cache=request.use_cache,
            stream_events=False,
            metadata={
                "request_id": request_id,
                "mode": request.mode.value,
                "max_rows": request.max_rows,
                "timeout_seconds": request.timeout_seconds,
            },
        )

        # Process through pipeline
        result = await pipeline.process(context)

        # Build response
        return _build_response(result, request, request_id)


# Store for agent queries (in-memory with TTL)
_agent_queries: Dict[str, Dict[str, Any]] = {}
_query_cleanup_times: Dict[str, float] = {}


def store_agent_query(
    query_id: str, query_data: Dict[str, Any], ttl_seconds: int = 300
):
    """Store agent query data with TTL."""
    _agent_queries[query_id] = query_data
    _query_cleanup_times[query_id] = time.time() + ttl_seconds

    # Clean up expired queries
    current_time = time.time()
    expired_keys = [k for k, v in _query_cleanup_times.items() if v < current_time]
    for key in expired_keys:
        _agent_queries.pop(key, None)
        _query_cleanup_times.pop(key, None)


# Agent query endpoint - initiates the query and returns query_id
@router.post("/agent/query")
async def agent_query(
    request: Dict[str, Any],  # Accept raw dict to handle extra fields
    request_id: str = Depends(get_request_id),
):
    """
    Initiate agent query processing.

    Returns a query_id that can be used to stream events via SSE.
    """
    if settings.mock_mode:
        return JSONResponse(
            status_code=503, content={"error": "Agent mode not available in mock mode"}
        )

    # Extract fields from the request
    question = request.get("question")
    if not question:
        return JSONResponse(
            status_code=400, content={"error": "question field is required"}
        )

    # Store the query data for the streaming endpoint
    store_agent_query(
        request_id,
        {
            "question": question,
            "session_id": request.get("session_id"),
            "max_iterations": request.get("max_iterations", 10),
        },
    )

    return {"query_id": request_id, "status": "initiated"}


# Agent streaming endpoint (POST)
@router.post("/agent/stream")
async def agent_stream_post(
    request: NL2SQLRequest,
    request_id: str = Depends(get_request_id),
):
    """
    Stream agent processing events via Server-Sent Events.

    This is the POST version that accepts the query directly.
    """
    if settings.mock_mode:
        return JSONResponse(
            status_code=503, content={"error": "Agent mode not available in mock mode"}
        )

    if not _agent:
        await initialize_components()
        if not _agent:
            return JSONResponse(
                status_code=503, content={"error": "Agent not available"}
            )

    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events from agent processing."""
        try:
            # Start event
            yield _format_sse_event(
                {
                    "type": "start",
                    "content": "Starting agent processing",
                    "timestamp": time.time(),
                }
            )

            # Set up event handler for the agent
            events_queue = []

            def event_handler(event: Dict[str, Any]):
                """Capture events from the agent."""
                # Transform agent event to frontend format
                transformed = _transform_agent_event(event)
                if transformed:
                    events_queue.append(transformed)

            # Add event handler to agent
            _agent.add_event_handler(event_handler)

            # Process query in background task
            import asyncio

            # Use query_id if provided (from frontend), otherwise session_id or request_id
            conversation_id = request.query_id or request.session_id or request_id

            async def process_agent():
                return await _agent.process_query(request.question, conversation_id)

            # Start processing
            task = asyncio.create_task(process_agent())

            # Stream events while processing
            while not task.done() or events_queue:
                # Yield any pending events
                while events_queue:
                    event = events_queue.pop(0)
                    yield _format_sse_event(event)

                # Small delay to prevent busy waiting
                if not task.done():
                    await asyncio.sleep(0.1)

            # Get final result
            result = await task
            logger.info(
                f"Agent processing complete. Result keys: {list(result.keys()) if result else 'None'}"
            )
            logger.info(f"Result success: {result.get('success') if result else 'N/A'}")
            logger.info(
                f"Has SQL result: {bool(result.get('result')) if result else False}"
            )
            logger.info(
                f"Has answer: {bool(result.get('answer')) if result else False}"
            )

            # Ensure all pending events are sent first
            while events_queue:
                event = events_queue.pop(0)
                yield _format_sse_event(event)

            # Small delay to ensure events are processed
            await asyncio.sleep(0.1)

            # Send final result event
            # Ensure result has proper structure
            if result and not result.get("success") and not result.get("error"):
                # If no explicit success/error, determine from content
                if result.get("result") or result.get("answer"):
                    result["success"] = True
                else:
                    result["success"] = False

            # Store result for retrieval endpoint BEFORE sending events
            if result:
                # Use query_id from request if provided, otherwise use request_id
                result_id = request.query_id if request.query_id else request_id
                store_agent_result(result_id, result)
                logger.info(f"Stored result for query_id: {result_id}")

            logger.info(
                f"Sending result event with success={result.get('success') if result else 'N/A'}"
            )

            yield _format_sse_event(
                {
                    "type": "result",
                    "content": result,
                    "timestamp": time.time(),
                }
            )

            # Small delay to ensure events are processed
            await asyncio.sleep(0.1)

            # End event
            yield _format_sse_event(
                {
                    "type": "complete",
                    "content": "Agent processing complete",
                    "timestamp": time.time(),
                }
            )

        except Exception as e:
            logger.error(f"Agent streaming error: {e}")
            yield _format_sse_event(
                {"type": "error", "content": str(e), "timestamp": time.time()}
            )

    return EventSourceResponse(event_generator())


# Agent streaming endpoint
@router.get("/agent/stream/{query_id}")
async def agent_stream(
    query_id: str,
):
    """
    Stream agent processing events via Server-Sent Events.

    Returns real-time agent thoughts, actions, and observations.
    """
    if settings.mock_mode:
        return JSONResponse(
            status_code=503, content={"error": "Agent mode not available in mock mode"}
        )

    # Retrieve the stored query data
    query_data = _agent_queries.get(query_id)
    if not query_data:
        return JSONResponse(
            status_code=404, content={"error": "Query not found or expired"}
        )

    # Clean up the stored query data after retrieval
    _agent_queries.pop(query_id, None)
    _query_cleanup_times.pop(query_id, None)

    if not _agent:
        await initialize_components()
        if not _agent:
            return JSONResponse(
                status_code=503, content={"error": "Agent not available"}
            )

    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events from agent processing."""
        try:
            # Start event
            yield _format_sse_event(
                {
                    "type": "start",
                    "content": "Starting agent processing",
                    "timestamp": time.time(),
                }
            )

            # Set up event handler for the agent
            events_queue = []

            def event_handler(event: Dict[str, Any]):
                """Capture events from the agent."""
                # Transform agent event to frontend format
                transformed = _transform_agent_event(event)
                if transformed:
                    events_queue.append(transformed)

            # Add event handler to agent
            _agent.add_event_handler(event_handler)

            # Process query in background task
            import asyncio

            # Use query_id as conversation_id, or fall back to session_id
            conversation_id = query_id or query_data.get("session_id") or query_id

            async def process_agent():
                return await _agent.process_query(
                    query_data.get("question"), conversation_id
                )

            # Start processing
            task = asyncio.create_task(process_agent())

            # Stream events while processing
            while not task.done() or events_queue:
                # Yield any pending events
                while events_queue:
                    event = events_queue.pop(0)
                    yield _format_sse_event(event)

                # Small delay to prevent busy waiting
                if not task.done():
                    await asyncio.sleep(0.1)

            # Get final result
            result = await task
            logger.info(
                f"Agent processing complete. Result keys: {list(result.keys()) if result else 'None'}"
            )
            logger.info(f"Result success: {result.get('success') if result else 'N/A'}")
            logger.info(
                f"Has SQL result: {bool(result.get('result')) if result else False}"
            )
            logger.info(
                f"Has answer: {bool(result.get('answer')) if result else False}"
            )

            # Ensure all pending events are sent first
            while events_queue:
                event = events_queue.pop(0)
                yield _format_sse_event(event)

            # Small delay to ensure events are processed
            await asyncio.sleep(0.1)

            # Send final result event
            # Ensure result has proper structure
            if result and not result.get("success") and not result.get("error"):
                # If no explicit success/error, determine from content
                if result.get("result") or result.get("answer"):
                    result["success"] = True
                else:
                    result["success"] = False

            # Store result for retrieval endpoint BEFORE sending events
            if result:
                # Use the query_id from the URL parameter
                store_agent_result(query_id, result)
                logger.info(f"Stored result for query_id: {query_id}")

            logger.info(
                f"Sending result event with success={result.get('success') if result else 'N/A'}"
            )

            yield _format_sse_event(
                {
                    "type": "result",
                    "content": result,
                    "timestamp": time.time(),
                }
            )

            # Small delay to ensure events are processed
            await asyncio.sleep(0.1)

            # End event
            yield _format_sse_event(
                {
                    "type": "complete",
                    "content": "Agent processing complete",
                    "timestamp": time.time(),
                }
            )

        except Exception as e:
            logger.error(f"Agent streaming error: {e}")
            yield _format_sse_event(
                {"type": "error", "content": str(e), "timestamp": time.time()}
            )

    return EventSourceResponse(event_generator())


# Session endpoints
@router.post("/session/query", response_model=NL2SQLResponse)
async def session_query(
    request: NL2SQLRequest,
    request_id: str = Depends(get_request_id),
) -> NL2SQLResponse:
    """
    Session-aware query endpoint with custom datasource support.
    """
    # Force session mode
    request.mode = QueryMode.SESSION

    # Ensure session_id is provided
    if not request.session_id:
        raise ValidationError("session_id is required for session queries")

    # Process through main query endpoint
    return await query(request, request_id)


@router.post("/session/{session_id}/datasource")
async def add_session_datasource(
    session_id: str,
    datasource_config: Dict[str, Any],
) -> Dict[str, Any]:
    """Add a custom datasource to a session."""
    # TODO: Implement session datasource management
    return {
        "message": "Session datasource management not yet implemented",
        "session_id": session_id,
    }


# Simple endpoint (backward compatibility)
@router.post("/simple", response_model=NL2SQLResponse)
async def simple_query(
    request: NL2SQLRequest,
    request_id: str = Depends(get_request_id),
) -> NL2SQLResponse:
    """Simplified query endpoint (backward compatibility)."""
    request.mode = QueryMode.SIMPLE
    return await query(request, request_id)


# Development/testing endpoints
@router.get("/test-schema")
async def test_schema():
    """Test schema loading status."""
    schema_graph = SchemaGraph.get_instance()
    tables = list(schema_graph._all_tables)

    return {
        "status": "ok",
        "table_count": len(tables),
        "tables": sorted(tables)[:10],  # First 10 tables
        "mock_mode": settings.mock_mode,
    }


@router.get("/agent/result/{query_id}")
async def get_agent_result(query_id: str):
    """Get agent query result by ID."""
    # Clean up expired results
    current_time = time.time()
    expired_ids = [
        id for id, expiry in _result_cleanup_times.items() if expiry < current_time
    ]
    for id in expired_ids:
        _agent_results.pop(id, None)
        _result_cleanup_times.pop(id, None)

    # Check if result exists
    result = _agent_results.get(query_id)
    if not result:
        logger.warning(f"Result not found for query_id: {query_id}")
        return JSONResponse(
            status_code=404,
            content={"error": "Result not found or expired", "query_id": query_id},
        )

    # Return the stored result
    return {"query_id": query_id, "status": "completed", "result": result}


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        await initialize_components()

        status = {
            "status": "healthy",
            "version": "2.0-unified",
            "components": {
                "orchestrator_pipeline": _orchestrator_pipeline is not None,
                "agent": _agent is not None,
                "session_manager": _session_manager is not None,
            },
            "mock_mode": settings.mock_mode,
        }

        return status

    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return JSONResponse(
            status_code=503, content={"status": "unhealthy", "error": str(e)}
        )


# Helper functions
def _build_response(
    result: PipelineResult, request: NL2SQLRequest, request_id: str
) -> NL2SQLResponse:
    """Build standardized response from pipeline result."""
    if not result.success:
        return NL2SQLResponse(
            success=False,
            sql="",
            error=result.error,
            session_id=request.session_id,
            metadata=_build_metadata(result, request, request_id),
        )

    # Convert execution results
    sql_result = None
    if result.execution_result and result.execution_result.success:
        sql_result = format_sql_results(
            result.execution_result.rows, result.execution_result.columns
        )

    return NL2SQLResponse(
        success=True,
        sql=result.sql,
        results=sql_result,
        session_id=request.session_id,
        metadata=_build_metadata(result, request, request_id),
    )


def _build_metadata(
    result: PipelineResult, request: NL2SQLRequest, request_id: str
) -> Optional[QueryMetadata]:
    """Build metadata if requested."""
    if not request.include_metadata:
        return None

    return QueryMetadata(
        query_id=request_id,
        processing_time_ms=result.total_time_ms,
        steps_timing=result.steps_timing or {},
        cache_hit=result.metadata.get("cache_hit", False) if result.metadata else False,
        model_used=result.metadata.get("model_used") if result.metadata else None,
        tokens_used=result.metadata.get("tokens_used") if result.metadata else None,
        confidence_score=(
            result.generation_result.confidence if result.generation_result else None
        ),
    )


def _mock_response(request: NL2SQLRequest, request_id: str) -> NL2SQLResponse:
    """Generate mock response for testing."""
    return NL2SQLResponse(
        success=True,
        sql="SELECT * FROM mock_table LIMIT 10",
        results=format_sql_results([{"id": 1, "name": "Mock Result"}], ["id", "name"]),
        session_id=request.session_id,
        metadata=(
            QueryMetadata(
                query_id=request_id,
                processing_time_ms=100.0,
                steps_timing={"mock": 100.0},
                cache_hit=False,
                model_used="mock",
                confidence_score=1.0,
            )
            if request.include_metadata
            else None
        ),
    )


def _transform_agent_event(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Transform agent event to frontend-compatible format."""
    event_type = event.get("type")
    event_data = event.get("data", {})
    timestamp = event.get("timestamp", datetime.utcnow().isoformat())

    # Map agent event types to frontend event types
    if event_type == "reasoning":
        return {
            "type": "thought",
            "content": event_data.get("reasoning", ""),
            "iteration": event_data.get("iteration", 1),
            "timestamp": timestamp,
        }
    elif event_type == "action":
        action_type = event_data.get("action_type", "unknown")
        parameters = event_data.get("parameters", {})

        # Format action content based on type
        if action_type == "EXPLORE_DATABASE":
            query = parameters.get("query", "")
            content = f"Exploring database: {query}"
        elif action_type == "EXECUTE_SQL":
            sql = parameters.get("sql", "")
            content = f"Executing SQL query" if sql else "Executing SQL"
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
            "type": "action",
            "content": content,
            "iteration": event_data.get("iteration", 1),
            "timestamp": timestamp,
        }
    elif event_type == "observation":
        # Get the actual observation content
        content_preview = event_data.get("content_preview", "")

        # Format based on what's in the observation
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
            "type": "observation",
            "content": content,
            "iteration": event_data.get("iteration", 1),
            "timestamp": timestamp,
        }
    elif event_type == "generating_answer":
        return {
            "type": "answer",
            "content": event_data.get("content", "Generating answer..."),
            "iteration": event_data.get("iteration", 1),
            "timestamp": timestamp,
        }
    elif event_type == "answer_generated":
        return {
            "type": "answer",
            "content": event_data.get("content", ""),
            "iteration": event_data.get("iteration", 1),
            "timestamp": timestamp,
        }
    elif event_type == "query_complete":
        return {
            "type": "complete",
            "content": "Query processing complete",
            "timestamp": timestamp,
        }
    elif event_type == "query_error":
        return {
            "type": "error",
            "content": event_data.get("error", "Unknown error"),
            "timestamp": timestamp,
        }

    # Skip other event types
    return None


def _json_serializer(obj: Any) -> Any:
    """Custom JSON serializer for non-serializable objects."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, Decimal):
        return float(obj)
    elif hasattr(obj, "__dict__"):
        return obj.__dict__
    else:
        return str(obj)


def _format_sse_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Format event for EventSourceResponse."""
    event_type = event.get("type", "message")
    event_data = {k: v for k, v in event.items() if k != "type"}

    # Add iteration number if not present (for agent events)
    if (
        event_type in ["thought", "action", "observation", "answer"]
        and "iteration" not in event_data
    ):
        event_data["iteration"] = event_data.get("iteration", 1)

    # Return dict for EventSourceResponse with event type
    return {
        "event": event_type,
        "data": json.dumps(event_data, default=_json_serializer),
    }
