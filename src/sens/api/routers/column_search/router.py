"""Router for column semantic search endpoints."""

import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

# Import the core retrieval function
from sens.retrieval.embedding import top_columns

from ...common.errors import ServiceError
from .models import ColumnSearchResponse, ColumnSearchResult

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/column-search",
    tags=["column-search"],
    responses={404: {"description": "Not found"}},
)


@router.get("/search", response_model=ColumnSearchResponse)
async def search_columns(
    query: str = Query(
        ..., description="Natural language query to search for columns."
    ),
    limit: Optional[int] = Query(
        20, description="Maximum number of column results to return.", ge=1, le=100
    ),
) -> ColumnSearchResponse:
    """Perform semantic search for relevant columns based on the query."""
    start_time = time.time()
    try:
        # Call the core embedding search function
        results_raw = top_columns(query=query, k=limit)

        # Format results into Pydantic models
        results_formatted = [
            ColumnSearchResult(table=table, column=column, score=score)
            for table, column, score in results_raw
        ]

    except FileNotFoundError as e:
        logger.error(f"Column search failed: Index not found. {e}")
        raise HTTPException(
            status_code=503,
            detail="Embedding index not loaded. Please build or load the index first.",
        )
    except Exception as e:
        logger.exception(
            f"Column search failed unexpectedly: {e}"
        )  # Log full traceback
        raise HTTPException(
            status_code=500, detail=f"Internal server error during column search: {e}"
        )

    execution_time_ms = (time.time() - start_time) * 1000

    logger.info(
        "Column search performed",
        extra={
            "query": query,
            "limit": limit,
            "results_count": len(results_formatted),
            "duration_ms": execution_time_ms,
        },
    )

    return ColumnSearchResponse(
        query=query,
        results=results_formatted,
        limit=limit,
        execution_time_ms=execution_time_ms,
    )
