"""Data models for datasource management."""

from enum import Enum
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class DataSourceType(Enum):
    """Types of data sources supported."""
    DEFAULT_POSTGRES = "default_postgres"
    UPLOADED_FILE = "uploaded_file"
    CONNECTED_DB = "connected_db"


class DataSourceInfo(BaseModel):
    """Information about a data source."""
    id: str
    type: DataSourceType
    name: str
    tables: List[str] = Field(default_factory=list)
    row_count: int = 0
    created_at: datetime
    config: Dict[str, Any] = Field(default_factory=dict)
    schema_extracted: bool = False


class SessionInfo(BaseModel):
    """Session information for tracking user data sources."""
    session_id: str
    source_id: str
    created_at: datetime
    last_accessed: datetime
    expires_at: datetime


class TableInfo(BaseModel):
    """Information about a table in a data source."""
    name: str
    columns: List[Dict[str, str]]
    row_count: int
    sample_data: Optional[List[Dict[str, Any]]] = None


class DataSourceResponse(BaseModel):
    """API response for data source operations."""
    session_id: str
    source_id: str
    type: DataSourceType
    name: str
    tables: List[TableInfo]
    total_rows: int
    message: str = "Data source created successfully"