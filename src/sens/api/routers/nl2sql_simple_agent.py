"""Simple direct agent API for testing our notes system."""

from typing import Any, Dict

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sens.cli.agent_pipeline import AgentNL2SQLPipeline

log = structlog.get_logger()


def transform_cli_result_to_api_format(cli_result: Dict[str, Any]) -> Dict[str, Any]:
    """Transform CLI agent result to match frontend QueryResponse format."""
    if cli_result.get("status") == "error":
        return {
            "error": {
                "code": "AGENT_ERROR",
                "message": cli_result.get("error", "Agent failed to process query"),
            }
        }

    # Transform table_preview (list of rows) to data format
    table_preview = cli_result.get("table_preview", [])
    columns = cli_result.get("columns", [])

    return {
        "sql": cli_result.get("sql", ""),
        "results": {
            "columns": columns,
            "data": table_preview,  # Already in correct format (list of dicts)
            "row_count": cli_result.get("row_count", 0),
            "truncated": False,  # CLI limits by max_rows parameter
        },
        "metadata": {
            "execution_time_ms": 0,  # Not tracked by CLI
            "tables_used": [],
            "query_type": "select",
            "confidence_score": 0.9,
            "pipeline_metrics": {
                "iterations": cli_result.get("metadata", {}).get("iterations", 0),
            },
        },
        "summary": cli_result.get("summary", ""),
    }


router = APIRouter(
    prefix="/nl2sql/simple-agent",
    tags=["nl2sql-simple-agent"],
)


class SimpleAgentRequest(BaseModel):
    question: str
    max_iterations: int = 10
    session_id: str = None
    debug: bool = True


@router.post("/query")
async def simple_agent_query(request: SimpleAgentRequest):
    """Direct agent query using our new notes system."""
    try:
        # Create agent pipeline
        pipeline = AgentNL2SQLPipeline(
            session_id=request.session_id,
            max_iterations=request.max_iterations,
            debug_mode=request.debug,
        )

        # Process the question
        result = await pipeline.process_question(
            question=request.question,
            format_type="json",
            show_preview=True,
            max_rows=100,  # Increase to get more results
        )

        # Transform to API format
        return transform_cli_result_to_api_format(result)

    except Exception as e:
        log.error("simple_agent_query_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
