"""Natural Language to SQL API router."""

import time
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sens.chat.orchestrator import ChatOrchestrator
from sens.chat.session import SessionManager
from sens.execution.types import QueryResult

# Initialize router
router = APIRouter(
    prefix="/nl2sql",
    tags=["nl2sql"],
    responses={
        400: {"description": "Bad Request"},
        422: {"description": "Validation Error"},
        500: {"description": "Internal Server Error"},
    },
)


# Request/Response models
class NL2SQLRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    limit: Optional[int] = 100


class NL2SQLResponse(BaseModel):
    sql: str
    results: dict
    metadata: dict
    error: Optional[dict] = None


# Initialize components (singleton pattern)
_orchestrator = None
_session_manager = None


def reset_orchestrator():
    """Reset the orchestrator instance (used when schema changes)."""
    global _orchestrator, _session_manager
    _orchestrator = None
    _session_manager = None


def get_orchestrator():
    """Get or create the ChatOrchestrator instance."""
    global _orchestrator, _session_manager

    if _orchestrator is None:
        import structlog

        logger = structlog.get_logger(__name__)

        try:
            # Initialize session manager
            # SessionManager will use Redis if available, otherwise degrade gracefully
            _session_manager = SessionManager()

            # Initialize orchestrator with minimal setup
            # The orchestrator will handle its own initialization
            _orchestrator = ChatOrchestrator(
                session_manager=_session_manager,
                use_optimized_retriever=True,  # Use optimized retriever for better performance
            )
            logger.info("chat_orchestrator_initialized")
        except Exception as e:
            logger.error("failed_to_initialize_orchestrator", error=str(e))
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initialize query processor: {str(e)}",
            )

    return _orchestrator


@router.get("/test-schema")
async def test_schema():
    """Test endpoint to check schema status."""
    from sens.schema.graph import SchemaGraph
    from sens.datasource.manager import DataSourceManager
    
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
            "tables": current_tables[:10]  # First 10 tables
        },
        "after_extraction": {
            "table_count": len(tables_after),
            "tables": tables_after[:10]  # First 10 tables
        }
    }


@router.post("/", response_model=NL2SQLResponse)
async def nl2sql(request: NL2SQLRequest):
    """Convert natural language question to SQL and execute it."""
    start_time = time.time()

    try:
        # Get or create conversation state
        session_id = request.session_id or "default"
        
        # Get orchestrator instance (schema is loaded at startup)
        orchestrator = get_orchestrator()

        # Try to load existing state or create new one
        state = orchestrator.session_manager.get(session_id) if orchestrator.session_manager else None
        if state is None:
            from sens.chat.state import ConversationState

            state = ConversationState(
                conversation_id=session_id,
                user_id="web_user",  # Default user for web interface
            )

        # Process the query through the orchestrator
        response, updated_state = await orchestrator.step(
            state=state, user_input=request.question
        )

        # Save updated state
        orchestrator.session_manager.save(session_id, updated_state)

        # Check if it's a clarification request
        if response.get("status") == "clarification_needed":
            return NL2SQLResponse(
                sql="",
                results={
                    "columns": [],
                    "data": [],
                    "row_count": 0,
                },
                metadata={
                    "execution_time_ms": int((time.time() - start_time) * 1000),
                    "clarification_needed": True,
                },
                error={
                    "code": "CLARIFICATION_NEEDED",
                    "message": response.get("message", "Please clarify your question"),
                    "suggestions": response.get("suggestions", []),
                },
            )

        # Check for errors
        if response.get("status") == "error":
            return NL2SQLResponse(
                sql="",
                results={
                    "columns": [],
                    "data": [],
                    "row_count": 0,
                },
                metadata={
                    "execution_time_ms": int((time.time() - start_time) * 1000),
                    "error": True,
                },
                error={
                    "code": "QUERY_FAILED",
                    "message": response.get("error", "Query processing failed"),
                },
            )

        # Extract results from successful response
        sql = response.get("sql", "")
        
        # ResponseBuilder returns the data in table_preview and row_count
        table_preview = response.get("table_preview", [])
        row_count = response.get("row_count", 0)
        columns = response.get("metadata", {}).get("columns", [])
        
        # Log response structure for debugging
        import structlog
        log = structlog.get_logger(__name__)
        log.info(
            "response_data",
            response_keys=list(response.keys()),
            has_table_preview=bool(table_preview),
            has_row_count=bool(row_count),
            columns_count=len(columns)
        )

        # Format results for frontend using table_preview from ResponseBuilder
        if table_preview and columns:
            # Convert table_preview to list of dicts
            data = []
            for row in table_preview[:request.limit]:
                if isinstance(row, list) and len(row) == len(columns):
                    data.append(dict(zip(columns, row)))
                elif isinstance(row, dict):
                    data.append(row)
            
            results = {
                "columns": columns,
                "data": data,
                "row_count": row_count,
                "truncated": row_count > request.limit if request.limit else False,
            }
        else:
            results = {
                "columns": [],
                "data": [],
                "row_count": 0,
                "truncated": False,
            }

        # Determine query type
        sql_upper = sql.upper() if sql else ""
        if "COUNT(" in sql_upper or "SUM(" in sql_upper or "AVG(" in sql_upper:
            query_type = "aggregate"
        elif "SELECT" in sql_upper and "FROM" in sql_upper:
            query_type = "select"
        else:
            query_type = "complex"

        # Suggest visualizations
        suggested_visualizations = []
        if results["row_count"] == 1 and len(results["columns"]) == 1:
            suggested_visualizations = ["single_value"]
        elif results["row_count"] > 1:
            suggested_visualizations = ["table"]
            # Check if there's a time column for time series
            for col in results["columns"]:
                if "date" in col.lower() or "time" in col.lower():
                    suggested_visualizations.append("time_series")
                    break

        # Extract metadata
        schema_context = response.get("metadata", {}).get("schema_context", {})
        tables_used = []
        if schema_context and isinstance(schema_context, dict):
            tables_used = list(schema_context.get("tables", {}).keys())

        metadata = {
            "execution_time_ms": int((time.time() - start_time) * 1000),
            "tables_used": tables_used,
            "query_type": query_type,
            "suggested_visualizations": suggested_visualizations,
        }

        return NL2SQLResponse(
            sql=sql,
            results=results,
            metadata=metadata,
        )

    except Exception as e:
        # Log the error
        import structlog

        logger = structlog.get_logger(__name__)
        logger.error("nl2sql_error", error=str(e), question=request.question)

        # Return error response
        return NL2SQLResponse(
            sql="",
            results={
                "columns": [],
                "data": [],
                "row_count": 0,
            },
            metadata={
                "execution_time_ms": int((time.time() - start_time) * 1000),
                "error": True,
            },
            error={
                "code": "INTERNAL_ERROR",
                "message": str(e),
            },
        )
