"""Unified schema model for all data sources."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Any
from datetime import datetime
from pydantic import BaseModel, Field


class DataType(str, Enum):
    """Unified data types across all data sources."""
    # Numeric types
    INTEGER = "integer"
    BIGINT = "bigint"
    SMALLINT = "smallint"
    NUMERIC = "numeric"
    DECIMAL = "decimal"
    FLOAT = "float"
    DOUBLE = "double"
    
    # String types
    VARCHAR = "varchar"
    CHAR = "char"
    TEXT = "text"
    
    # Date/Time types
    DATE = "date"
    TIME = "time"
    TIMESTAMP = "timestamp"
    TIMESTAMPTZ = "timestamptz"
    
    # Boolean
    BOOLEAN = "boolean"
    
    # JSON/JSONB
    JSON = "json"
    JSONB = "jsonb"
    
    # Other
    UUID = "uuid"
    ARRAY = "array"
    UNKNOWN = "unknown"


class ColumnInfo(BaseModel):
    """Unified column information."""
    name: str
    data_type: DataType
    is_nullable: bool = True
    is_primary_key: bool = False
    is_foreign_key: bool = False
    is_unique: bool = False
    is_sticky: bool = False  # High-value identifier
    default_value: Optional[str] = None
    description: Optional[str] = None
    max_length: Optional[int] = None
    numeric_precision: Optional[int] = None
    numeric_scale: Optional[int] = None
    # Original type from source database for reference
    original_type: Optional[str] = None


class ForeignKeyInfo(BaseModel):
    """Foreign key relationship information."""
    from_table: str
    from_columns: List[str]
    to_table: str
    to_columns: List[str]
    constraint_name: Optional[str] = None


class IndexInfo(BaseModel):
    """Index information."""
    name: str
    table: str
    columns: List[str]
    is_unique: bool = False
    is_primary: bool = False


class TableInfo(BaseModel):
    """Unified table information."""
    name: str
    columns: List[ColumnInfo]
    primary_keys: List[str] = Field(default_factory=list)
    foreign_keys: List[ForeignKeyInfo] = Field(default_factory=list)
    indexes: List[IndexInfo] = Field(default_factory=list)
    row_count: Optional[int] = None
    description: Optional[str] = None
    sample_data: Optional[List[Dict[str, Any]]] = None
    # Partition information
    is_partitioned: bool = False
    partition_key: Optional[str] = None
    is_partition: bool = False
    parent_table: Optional[str] = None
    
    def get_column(self, column_name: str) -> Optional[ColumnInfo]:
        """Get column info by name."""
        for col in self.columns:
            if col.name == column_name:
                return col
        return None
    
    def get_sticky_columns(self) -> List[str]:
        """Get list of sticky column names."""
        return [col.name for col in self.columns if col.is_sticky]


class DataSourceType(str, Enum):
    """Types of data sources."""
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLITE = "sqlite"
    DUCKDB = "duckdb"
    CSV = "csv"
    EXCEL = "excel"
    UPLOADED_FILE = "uploaded_file"
    DEFAULT_POSTGRES = "default_postgres"
    

class UnifiedSchema(BaseModel):
    """Unified schema representation for all data sources."""
    # Metadata
    source_type: DataSourceType
    source_id: str
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    extraction_duration_ms: Optional[int] = None
    
    # Schema information
    tables: List[TableInfo]
    
    # Optional metadata
    database_name: Optional[str] = None
    schema_name: Optional[str] = "public"
    description: Optional[str] = None
    version: Optional[str] = None
    
    # Additional metadata for specific sources
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def get_table(self, table_name: str) -> Optional[TableInfo]:
        """Get table info by name."""
        for table in self.tables:
            if table.name == table_name:
                return table
        return None
    
    def get_all_tables(self) -> List[str]:
        """Get list of all table names."""
        return [table.name for table in self.tables]
    
    def get_all_columns(self, table_name: Optional[str] = None) -> List[tuple[str, str]]:
        """Get list of (table, column) tuples."""
        columns = []
        for table in self.tables:
            if table_name is None or table.name == table_name:
                for col in table.columns:
                    columns.append((table.name, col.name))
        return columns
    
    def get_foreign_keys(self) -> List[ForeignKeyInfo]:
        """Get all foreign keys across all tables."""
        fks = []
        for table in self.tables:
            fks.extend(table.foreign_keys)
        return fks
    
    def get_relationships(self) -> Dict[str, List[str]]:
        """Get table relationships as adjacency list."""
        relationships = {}
        for fk in self.get_foreign_keys():
            if fk.from_table not in relationships:
                relationships[fk.from_table] = []
            if fk.to_table not in relationships[fk.from_table]:
                relationships[fk.from_table].append(fk.to_table)
        return relationships
    
    def get_sticky_columns_by_table(self) -> Dict[str, List[str]]:
        """Get sticky columns grouped by table."""
        sticky = {}
        for table in self.tables:
            sticky_cols = table.get_sticky_columns()
            if sticky_cols:
                sticky[table.name] = sticky_cols
        return sticky
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return self.model_dump(mode='json')
    
    @classmethod
    def from_dict(cls, data: dict) -> "UnifiedSchema":
        """Create from dictionary."""
        return cls.model_validate(data)