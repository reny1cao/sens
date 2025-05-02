"""Pydantic models for the column search API endpoints."""

from typing import List

from pydantic import BaseModel, Field


class ColumnSearchResult(BaseModel):
    """Represents a single column search result."""

    table: str = Field(..., description="Name of the table containing the column.")
    column: str = Field(..., description="Name of the relevant column.")
    score: float = Field(..., description="Similarity score (higher is better).")


class ColumnSearchResponse(BaseModel):
    """Response model for the column search endpoint."""

    query: str = Field(..., description="The original search query.")
    results: List[ColumnSearchResult] = Field(
        ..., description="List of relevant columns found, sorted by score."
    )
    limit: int = Field(..., description="Maximum number of results requested.")
    execution_time_ms: float = Field(
        ..., description="Search execution time in milliseconds."
    )
