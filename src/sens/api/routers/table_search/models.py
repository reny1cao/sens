"""Models for table search domain."""

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class TableSearchResponse(BaseModel):
    """Response model for table search results."""

    query: str = Field(..., description="The search query that was used")
    matches: List[str] = Field(..., description="List of matching table names")
    total_matches: int = Field(..., description="Total number of matches found")
    execution_time_ms: float = Field(
        ..., description="Search execution time in milliseconds"
    )


class IndexStatsResponse(BaseModel):
    """Response model for index statistics."""

    table_count: int = Field(..., description="Total number of indexed tables")
    memory_usage_bytes: int = Field(..., description="Current memory usage in bytes")
    case_formats: Dict[str, int] = Field(
        ..., description="Count of tables by case format"
    )


class RefreshResponse(BaseModel):
    """Response model for index refresh operation."""

    status: str = Field(..., description="Operation status")
    execution_time_ms: float = Field(
        ..., description="Refresh execution time in milliseconds"
    )
    table_count: int = Field(..., description="Total number of indexed tables")
    memory_usage_bytes: int = Field(..., description="Current memory usage in bytes")
    case_formats: Dict[str, int] = Field(
        ..., description="Count of tables by case format"
    )
