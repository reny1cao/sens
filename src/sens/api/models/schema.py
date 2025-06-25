"""
Schema-related API models.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ColumnInfo(BaseModel):
    """Information about a database column."""

    name: str = Field(..., description="Column name")
    type: str = Field(..., description="Data type")
    nullable: bool = Field(default=True, description="Whether column allows NULL")
    primary_key: bool = Field(default=False, description="Is primary key")
    foreign_key: Optional[str] = Field(None, description="Referenced table.column")
    description: Optional[str] = Field(None, description="Column description")
    sample_values: Optional[List[Any]] = Field(None, description="Example values")


class TableInfo(BaseModel):
    """Information about a database table."""

    name: str = Field(..., description="Table name")
    schema: Optional[str] = Field(None, description="Schema name")
    columns: List[ColumnInfo] = Field(..., description="Table columns")
    row_count: Optional[int] = Field(None, description="Approximate row count")
    description: Optional[str] = Field(None, description="Table description")
    relationships: Optional[Dict[str, str]] = Field(
        None, description="Foreign key relationships"
    )


class SchemaRequest(BaseModel):
    """Request for schema information."""

    datasource_id: Optional[str] = Field(None, description="Specific datasource")
    include_tables: Optional[List[str]] = Field(None, description="Tables to include")
    exclude_tables: Optional[List[str]] = Field(None, description="Tables to exclude")
    include_system_tables: bool = Field(
        default=False, description="Include system tables"
    )
    include_sample_data: bool = Field(
        default=False, description="Include sample values"
    )


class SchemaResponse(BaseModel):
    """Response with schema information."""

    tables: List[TableInfo] = Field(..., description="Database tables")
    total_tables: int = Field(..., description="Total number of tables")
    datasource_id: Optional[str] = Field(None, description="Datasource ID")
    last_updated: Optional[str] = Field(None, description="Schema last update time")
