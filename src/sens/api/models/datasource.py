"""
DataSource-related API models.
"""

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ConnectionStatus(str, Enum):
    """Database connection status."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    CONNECTING = "connecting"


class DataSourceType(str, Enum):
    """Supported datasource types."""

    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLITE = "sqlite"
    CSV = "csv"
    EXCEL = "excel"
    CUSTOM = "custom"


class DataSourceInfo(BaseModel):
    """Information about a datasource."""

    id: str = Field(..., description="Unique datasource ID")
    name: str = Field(..., description="Display name")
    type: DataSourceType = Field(..., description="Datasource type")
    status: ConnectionStatus = Field(..., description="Connection status")
    created_at: str = Field(..., description="Creation timestamp")
    last_connected: Optional[str] = Field(
        None, description="Last successful connection"
    )
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class DataSourceRequest(BaseModel):
    """Request to create/update a datasource."""

    name: str = Field(..., min_length=1, description="Datasource name")
    type: DataSourceType = Field(..., description="Datasource type")
    connection_params: Dict[str, Any] = Field(..., description="Connection parameters")
    test_connection: bool = Field(default=True, description="Test connection on create")


class DataSourceResponse(BaseModel):
    """Response for datasource operations."""

    datasource: DataSourceInfo = Field(..., description="Datasource information")
    message: Optional[str] = Field(None, description="Operation message")
    test_result: Optional[Dict[str, Any]] = Field(
        None, description="Connection test results"
    )
