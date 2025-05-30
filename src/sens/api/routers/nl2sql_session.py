"""NL2SQL endpoint with session-based data source support."""

import time
from typing import Optional
import uuid

from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel

from sens.chat.orchestrator import ChatOrchestrator
from sens.chat.session import SessionManager
from sens.datasource import DataSourceManager, DataSourceType
from sens.datasource.executor import MultiSourceExecutor
from sens.schema.context import SchemaContext, TableContext
from sens.datasource.session_pipeline import SessionAwarePipeline
from sens.execution.types import QueryResult
from sens.api.routers.datasource import get_datasource_manager
import structlog

logger = structlog.get_logger(__name__)

# Initialize router
router = APIRouter(
    prefix="/nl2sql/session",
    tags=["nl2sql-session"],
)


class NL2SQLRequest(BaseModel):
    question: str


class NL2SQLResponse(BaseModel):
    session_id: str
    sql: str
    results: dict
    metadata: dict
    data_source: dict
    error: Optional[dict] = None


# Global instances
_multi_executor: Optional[MultiSourceExecutor] = None


def get_multi_executor(
    datasource_manager: DataSourceManager = Depends(get_datasource_manager)
) -> MultiSourceExecutor:
    """Get or create the multi-source executor."""
    global _multi_executor
    if _multi_executor is None:
        _multi_executor = MultiSourceExecutor(datasource_manager)
    return _multi_executor


@router.post("/query", response_model=NL2SQLResponse)
async def process_nl2sql_with_session(
    request: NL2SQLRequest,
    session_id: Optional[str] = Header(None, alias="X-Session-Id"),
    datasource_manager: DataSourceManager = Depends(get_datasource_manager),
    executor: MultiSourceExecutor = Depends(get_multi_executor)
) -> NL2SQLResponse:
    """Process NL2SQL request using session-specific data source."""
    
    # Generate session ID if not provided
    if not session_id:
        session_id = str(uuid.uuid4())
    
    start_time = time.time()
    
    try:
        # Get the data source for this session
        source = datasource_manager.get_session_source(session_id)
        if not source:
            raise HTTPException(
                status_code=404,
                detail="No data source found for session. Please upload data first."
            )
        
        logger.info("processing_nl2sql", 
                   session_id=session_id,
                   source_id=source.id,
                   source_type=source.type.value,
                   question=request.question)
        
        # Check if schema is extracted
        if not source.schema_extracted:
            raise HTTPException(
                status_code=400,
                detail="Schema not yet extracted for this data source. Please wait."
            )
        
        # Check if unified schema exists
        if not source.unified_schema:
            raise HTTPException(
                status_code=500,
                detail="Schema not loaded. This is an internal error."
            )
        
        # Create pipeline with unified schema
        pipeline = SessionAwarePipeline(
            unified_schema=source.unified_schema,
            sql_executor=executor,
            use_optimized_retriever=True
        )
        
        # Process the query
        result = await pipeline.process(
            request.question, 
            session_id=session_id
        )
        
        # Format response
        if result.get("error"):
            return NL2SQLResponse(
                session_id=session_id,
                sql="",
                results={},
                metadata={
                    "processing_time": time.time() - start_time,
                    "pipeline_steps": result.get("pipeline_steps", [])
                },
                data_source={
                    "id": source.id,
                    "name": source.name,
                    "type": source.type.value
                },
                error={
                    "message": result["error"],
                    "type": result.get("error_type", "processing_error")
                }
            )
        
        # Extract query results
        query_result: QueryResult = result.get("query_result", {})
        
        return NL2SQLResponse(
            session_id=session_id,
            sql=result.get("sql", ""),
            results={
                "columns": query_result.columns if query_result else [],
                "rows": query_result.rows if query_result else [],
                "row_count": query_result.row_count if query_result else 0,
                "summary": result.get("summary", "")
            },
            metadata={
                "processing_time": time.time() - start_time,
                "execution_time": query_result.execution_time if query_result else 0,
                "pipeline_steps": result.get("pipeline_steps", []),
                "intent": result.get("intent", {}),
                "schema_context": result.get("schema_context", {})
            },
            data_source={
                "id": source.id,
                "name": source.name,
                "type": source.type.value,
                "tables": source.unified_schema.get_all_tables() if source.unified_schema else []
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("nl2sql_processing_failed",
                    session_id=session_id,
                    error=str(e),
                    exc_info=True)
        
        return NL2SQLResponse(
            session_id=session_id,
            sql="",
            results={},
            metadata={
                "processing_time": time.time() - start_time
            },
            data_source={
                "id": source.id if 'source' in locals() else "unknown",
                "name": source.name if 'source' in locals() else "Unknown",
                "type": source.type.value if 'source' in locals() else "unknown"
            },
            error={
                "message": str(e),
                "type": type(e).__name__
            }
        )