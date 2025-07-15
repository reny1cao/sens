"""
Common API models shared across endpoints.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Detailed error information."""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    field: Optional[str] = Field(None, description="Field that caused the error")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")


class ErrorResponse(BaseModel):
    """Standard error response."""

    success: bool = Field(default=False, description="Always false for errors")
    error: str = Field(..., description="Main error message")
    details: Optional[List[ErrorDetail]] = Field(None, description="Detailed errors")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: Optional[str] = Field(None, description="Request tracking ID")


class SuccessResponse(BaseModel):
    """Standard success response wrapper."""

    success: bool = Field(default=True, description="Always true for success")
    data: Any = Field(..., description="Response data")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PaginationParams(BaseModel):
    """Standard pagination parameters."""

    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")
    sort_by: Optional[str] = Field(None, description="Sort field")
    sort_order: str = Field(default="asc", pattern="^(asc|desc)$")


class QueryMetadata(BaseModel):
    """Metadata about query processing."""

    query_id: str = Field(..., description="Unique query identifier")
    processing_time_ms: float = Field(..., description="Total processing time")
    steps_timing: Dict[str, float] = Field(default_factory=dict)
    cache_hit: bool = Field(default=False)
    model_used: Optional[str] = Field(None)
    tokens_used: Optional[int] = Field(None)
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)

    # Agent-specific fields
    iterations: Optional[int] = Field(None, description="Number of agent iterations")
    agent_trace: Optional[List[Dict[str, Any]]] = Field(
        None, description="Agent action trace"
    )
