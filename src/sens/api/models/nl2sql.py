"""
NL2SQL API models shared across all nl2sql endpoints.
"""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from .common import QueryMetadata


class QueryMode(str, Enum):
    """Query processing modes."""

    STANDARD = "standard"  # Direct ChatOrchestrator
    AGENT = "agent"  # Agent with self-correction
    SESSION = "session"  # Session-aware with custom datasources
    SIMPLE = "simple"  # Simplified interface
    MOCK = "mock"  # Mock mode for testing


class NL2SQLRequest(BaseModel):
    """Unified request model for all NL2SQL endpoints."""

    question: str = Field(..., min_length=1, description="Natural language query")
    session_id: Optional[str] = Field(None, description="Session ID for context")
    datasource_id: Optional[str] = Field(None, description="Specific datasource to use")
    mode: QueryMode = Field(default=QueryMode.STANDARD, description="Processing mode")
    stream: bool = Field(default=False, description="Enable streaming response")
    use_cache: bool = Field(default=True, description="Enable result caching")
    include_metadata: bool = Field(
        default=False, description="Include processing metadata"
    )
    max_rows: Optional[int] = Field(
        None, ge=1, le=10000, description="Maximum rows to return"
    )
    timeout_seconds: Optional[int] = Field(
        None, ge=1, le=300, description="Query timeout"
    )
    query_id: Optional[str] = Field(None, description="Query ID for result retrieval")


class SQLResult(BaseModel):
    """SQL query result."""

    column_names: List[str] = Field(..., description="Column names in order")
    rows: List[List[Any]] = Field(..., description="Result rows")
    row_count: int = Field(..., description="Total rows returned")
    affected_rows: Optional[int] = Field(
        None, description="Rows affected (for mutations)"
    )


class NL2SQLResponse(BaseModel):
    """Unified response model for NL2SQL endpoints."""

    success: bool = Field(..., description="Query success status")
    sql: str = Field(..., description="Generated SQL query")
    results: Optional[SQLResult] = Field(None, description="Query execution results")
    error: Optional[str] = Field(None, description="Error message if failed")
    session_id: Optional[str] = Field(None, description="Session ID for follow-ups")
    metadata: Optional[QueryMetadata] = Field(None, description="Processing metadata")


class AgentThought(BaseModel):
    """Agent reasoning step."""

    thought: str = Field(..., description="Agent's reasoning")
    action: Optional[str] = Field(None, description="Action taken")
    observation: Optional[str] = Field(None, description="Result observed")


class AgentEvent(BaseModel):
    """Event emitted during agent processing."""

    type: Literal["thought", "action", "observation", "result", "error"] = Field(...)
    content: str = Field(..., description="Event content")
    metadata: Optional[Dict[str, Any]] = Field(None)
    timestamp: float = Field(..., description="Event timestamp")


class NL2SQLStreamEvent(BaseModel):
    """Server-sent event for streaming responses."""

    event: str = Field(..., description="Event type")
    data: Any = Field(..., description="Event data")
    id: Optional[str] = Field(None, description="Event ID")
    retry: Optional[int] = Field(None, description="Retry interval in ms")
