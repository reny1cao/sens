"""API routes for embedding-based semantic search."""

from typing import List, Tuple

from fastapi import APIRouter, Query
from pydantic import BaseModel

from sens.embedding import top_columns

router = APIRouter(prefix="/embedding", tags=["embedding"])


class ColumnMatch(BaseModel):
    """Schema for a column match result."""

    table: str
    column: str
    score: float

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {"table": "movie", "column": "rating", "score": 0.85}
        }


@router.get("/search", response_model=List[ColumnMatch])
async def search_columns(
    query: str = Query(..., description="The search query"),
    k: int = Query(20, description="Number of results to return", ge=1, le=100),
) -> List[ColumnMatch]:
    """Search for relevant columns using semantic similarity.

    Args:
        query: The search query
        k: Number of results to return (default: 20)

    Returns:
        List of column matches sorted by relevance score
    """
    results = top_columns(query, k)
    return [
        ColumnMatch(table=table, column=column, score=score)
        for table, column, score in results
    ]
