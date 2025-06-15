"""Simplified NL2SQL endpoint that properly handles ChatOrchestrator responses."""

import time
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sens.chat.orchestrator import ChatOrchestrator
from sens.chat.session import SessionManager
from sens.chat.state import ConversationState

# Initialize router
router = APIRouter(
    prefix="/nl2sql",
    tags=["nl2sql"],
)


class NL2SQLRequest(BaseModel):
    question: str
    session_id: Optional[str] = None


class NL2SQLResponse(BaseModel):
    sql: str
    results: dict
    metadata: dict
    summary: Optional[str] = None
    error: Optional[dict] = None


# Initialize components
_orchestrator = None
_session_manager = None
_schema_initialized = False


async def ensure_schema_initialized():
    """Ensure default schema is initialized before creating orchestrator."""
    global _schema_initialized, _orchestrator, _session_manager
    if not _schema_initialized:
        from sens.datasource.manager import DataSourceManager

        datasource_manager = DataSourceManager()
        await datasource_manager.ensure_default_schema_extracted()
        _schema_initialized = True
        # Reset orchestrator to pick up new schema
        _orchestrator = None
        _session_manager = None


def get_orchestrator():
    """Get or create the ChatOrchestrator instance."""
    global _orchestrator, _session_manager

    if _orchestrator is None:
        try:
            _session_manager = SessionManager()
            _orchestrator = ChatOrchestrator(
                session_manager=_session_manager, use_optimized_retriever=True
            )
        except Exception:
            # If initialization fails, we'll handle it in the endpoint
            pass

    return _orchestrator, _session_manager


@router.get("/test-schema")
async def test_schema():
    """Test endpoint to check schema status."""
    from sens.datasource.manager import DataSourceManager
    from sens.schema.graph import SchemaGraph

    # Get current schema graph state
    schema_graph = SchemaGraph.get_instance()
    current_tables = list(schema_graph._all_tables)

    # Try to load default database schema
    datasource_manager = DataSourceManager()
    await datasource_manager.ensure_default_schema_extracted()

    # Check again
    schema_graph_after = SchemaGraph.get_instance()
    tables_after = list(schema_graph_after._all_tables)

    return {
        "before_extraction": {
            "table_count": len(current_tables),
            "tables": sorted(current_tables)[:10],  # First 10 tables
        },
        "after_extraction": {
            "table_count": len(tables_after),
            "tables": sorted(tables_after)[:10],  # First 10 tables
        },
    }


@router.post("/", response_model=NL2SQLResponse)
async def nl2sql(request: NL2SQLRequest):
    """Convert natural language to SQL and execute it."""
    start_time = time.time()

    try:
        # Ensure schema is initialized before getting orchestrator
        await ensure_schema_initialized()
        # Get orchestrator
        orchestrator, session_manager = get_orchestrator()
        if not orchestrator:
            raise HTTPException(500, "Service temporarily unavailable")

        # Get or create conversation state
        session_id = request.session_id or "default"
        state = session_manager.get(session_id) if session_manager else None

        if state is None:
            state = ConversationState(conversation_id=session_id, user_id="web_user")

        # Process query
        response, updated_state = await orchestrator.step(state, request.question)

        # Save state if possible
        if session_manager:
            try:
                session_manager.save(session_id, updated_state)
            except Exception:
                pass  # Ignore save errors

        # Handle different response types
        if response.get("status") == "error":
            return NL2SQLResponse(
                sql="",
                results={"columns": [], "data": [], "row_count": 0},
                metadata={"execution_time_ms": int((time.time() - start_time) * 1000)},
                error={
                    "code": "QUERY_FAILED",
                    "message": response.get("message", "Query failed"),
                },
            )

        if response.get("status") == "clarification_needed":
            return NL2SQLResponse(
                sql="",
                results={"columns": [], "data": [], "row_count": 0},
                metadata={"execution_time_ms": int((time.time() - start_time) * 1000)},
                error={
                    "code": "CLARIFICATION_NEEDED",
                    "message": response.get("message", "Please clarify"),
                    "suggestions": response.get("suggestions", []),
                },
            )

        # Success response - extract from FinalResponse structure
        sql = response.get("sql", "")
        table_preview = response.get("table_preview", [])
        row_count = response.get("row_count", 0)

        # Extract metadata and columns
        metadata_info = response.get("metadata", {})
        columns = metadata_info.get("columns", [])

        # Log for debugging
        import structlog

        logger = structlog.get_logger(__name__)
        logger.info(
            "response_structure",
            response_keys=list(response.keys()),
            metadata_keys=list(metadata_info.keys()) if metadata_info else None,
            table_preview_type=type(table_preview).__name__,
            table_preview_len=len(table_preview),
            first_row=table_preview[0] if table_preview else None,
            columns=columns,
            row_count=row_count,
        )

        # Convert table_preview to our format
        data = []
        if table_preview:
            # table_preview is a list of lists (rows of values)
            for row in table_preview:
                if isinstance(row, list) and columns and len(row) == len(columns):
                    data.append(dict(zip(columns, row)))
                elif isinstance(row, dict):
                    # Already in dict format
                    data.append(row)

        results = {
            "columns": columns,
            "data": data,
            "row_count": row_count,
            "truncated": False,  # Don't complicate with truncation for now
        }

        # Log what we're sending
        logger.info(
            "sending_results",
            columns_count=len(columns),
            data_count=len(data),
            first_data_row=data[0] if data else None,
        )

        # Determine visualizations
        suggested_visualizations = ["table"]
        if row_count == 1 and len(columns) == 1:
            suggested_visualizations = ["single_value"]

        metadata = {
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "tables_used": [],  # Would need to extract from response
            "query_type": "select",
            "suggested_visualizations": suggested_visualizations,
        }

        # Include pipeline metrics if available
        if "pipeline_metrics" in metadata_info:
            metadata["pipeline_metrics"] = metadata_info["pipeline_metrics"]

        # Extract summary from the response
        summary = response.get("summary", "")

        return NL2SQLResponse(
            sql=sql, results=results, metadata=metadata, summary=summary
        )

    except Exception as e:
        import structlog

        logger = structlog.get_logger(__name__)
        logger.error("nl2sql_error", error=str(e), question=request.question)

        return NL2SQLResponse(
            sql="",
            results={"columns": [], "data": [], "row_count": 0},
            metadata={"execution_time_ms": int((time.time() - start_time) * 1000)},
            error={
                "code": "INTERNAL_ERROR",
                "message": f"Failed to process query: {str(e)}",
            },
        )
