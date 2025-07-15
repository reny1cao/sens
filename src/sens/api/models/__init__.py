"""API models package."""

from .common import ErrorResponse, PaginationParams, QueryMetadata, SuccessResponse
from .datasource import (
    ConnectionStatus,
    DataSourceInfo,
    DataSourceRequest,
    DataSourceResponse,
)
from .intent import IntentRequest, IntentResponse, SchemaSnippet
from .nl2sql import (
    AgentEvent,
    NL2SQLRequest,
    NL2SQLResponse,
    NL2SQLStreamEvent,
    QueryMode,
)
from .schema import ColumnInfo, SchemaRequest, SchemaResponse, TableInfo

__all__ = [
    # Intent (existing)
    "IntentRequest",
    "IntentResponse",
    "SchemaSnippet",
    # Common
    "ErrorResponse",
    "SuccessResponse",
    "PaginationParams",
    "QueryMetadata",
    # NL2SQL
    "NL2SQLRequest",
    "NL2SQLResponse",
    "NL2SQLStreamEvent",
    "QueryMode",
    "AgentEvent",
    # Schema
    "SchemaRequest",
    "SchemaResponse",
    "TableInfo",
    "ColumnInfo",
    # DataSource
    "DataSourceRequest",
    "DataSourceResponse",
    "DataSourceInfo",
    "ConnectionStatus",
]
