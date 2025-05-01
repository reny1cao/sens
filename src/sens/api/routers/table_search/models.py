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


class TokenDetail(BaseModel):
    """Details about a specific token in the index."""

    token: str = Field(..., description="The token string")
    tables: List[str] = Field(..., description="Tables containing this token")
    frequency: int = Field(..., description="Number of tables containing this token")
    memory_bytes: int = Field(
        ..., description="Memory usage of this token and its references"
    )


class TableTokenization(BaseModel):
    """How a table name is tokenized."""

    table_name: str = Field(..., description="Original table name")
    tokens: List[str] = Field(..., description="Tokens extracted from the table name")
    case_format: str = Field(..., description="Detected case format")
    memory_bytes: int = Field(..., description="Memory usage for this table's entries")


class DetailedIndexResponse(BaseModel):
    """Detailed view of the index structure."""

    total_tables: int = Field(..., description="Total number of indexed tables")
    total_tokens: int = Field(..., description="Total number of unique tokens")
    total_memory_bytes: int = Field(..., description="Total memory usage in bytes")
    tokens: Dict[str, TokenDetail] = Field(..., description="Details for each token")
    tables: Dict[str, TableTokenization] = Field(
        ..., description="Details for each table"
    )
    most_common_tokens: List[TokenDetail] = Field(
        ..., description="Top 10 most frequent tokens"
    )
    memory_distribution: Dict[str, int] = Field(
        ..., description="Memory usage breakdown"
    )
