"""Simple direct agent API for testing our notes system."""

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sens.cli.agent_pipeline import AgentNL2SQLPipeline

log = structlog.get_logger()

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
            max_rows=5,
        )

        return result

    except Exception as e:
        log.error("simple_agent_query_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
