"""Schema extractor for DuckDB (uploaded files)."""

import re
from typing import List, Dict, Any, Optional
import duckdb
import structlog

from sens.schema.unified_schema import (
    UnifiedSchema, TableInfo, ColumnInfo, DataType, 
    DataSourceType, ForeignKeyInfo, IndexInfo
)
from .base import SchemaExtractor, SchemaExtractionError

logger = structlog.get_logger(__name__)


class DuckDBExtractor(SchemaExtractor):
    """Extract schema from DuckDB database (typically for uploaded files)."""
    
    # Type mappings from DuckDB to unified types
    TYPE_MAPPINGS = {
        'BIGINT': DataType.BIGINT,
        'INTEGER': DataType.INTEGER,
        'INT': DataType.INTEGER,
        'SMALLINT': DataType.SMALLINT,
        'TINYINT': DataType.SMALLINT,
        'HUGEINT': DataType.BIGINT,
        'UBIGINT': DataType.BIGINT,
        'UINTEGER': DataType.INTEGER,
        'USMALLINT': DataType.SMALLINT,
        'UTINYINT': DataType.SMALLINT,
        'DOUBLE': DataType.DOUBLE,
        'REAL': DataType.FLOAT,
        'FLOAT': DataType.FLOAT,
        'DECIMAL': DataType.DECIMAL,
        'NUMERIC': DataType.NUMERIC,
        'VARCHAR': DataType.VARCHAR,
        'CHAR': DataType.CHAR,
        'BPCHAR': DataType.CHAR,
        'TEXT': DataType.TEXT,
        'STRING': DataType.TEXT,
        'DATE': DataType.DATE,
        'TIMESTAMP': DataType.TIMESTAMP,
        'TIMESTAMP WITHOUT TIME ZONE': DataType.TIMESTAMP,
        'TIMESTAMP WITH TIME ZONE': DataType.TIMESTAMPTZ,
        'TIME': DataType.TIME,
        'TIME WITHOUT TIME ZONE': DataType.TIME,
        'TIME WITH TIME ZONE': DataType.TIME,
        'BOOLEAN': DataType.BOOLEAN,
        'BOOL': DataType.BOOLEAN,
        'UUID': DataType.UUID,
        'JSON': DataType.JSON,
        'BLOB': DataType.TEXT,
        'BIT': DataType.VARCHAR,
    }
    
    # Patterns for identifying sticky columns
    STICKY_PATTERNS = [
        r'.*_id$', r'^id$', r'.*_code$', r'.*_number$', r'.*_no$',
        r'^uuid$', r'^guid$', r'.*_key$', r'^identifier$'
    ]
    
    STICKY_NAME_PATTERNS = ['name', 'title', 'email', 'username', 'phone']
    
    def __init__(self, connection: duckdb.DuckDBPyConnection, 
                 source_id: str,
                 database_name: Optional[str] = None,
                 include_sample_data: bool = True,
                 sample_rows: int = 5):
        """Initialize DuckDB extractor.
        
        Args:
            connection: DuckDB connection object
            source_id: Unique identifier for this source
            database_name: Optional database name
            include_sample_data: Whether to include sample data
            sample_rows: Number of sample rows to include
        """
        super().__init__(DataSourceType.DUCKDB, source_id)
        self.connection = connection
        self.database_name = database_name
        self.include_sample_data = include_sample_data
        self.sample_rows = sample_rows
    
    async def extract(self) -> UnifiedSchema:
        """Extract schema from DuckDB database."""
        tables = await self._extract_tables()
        
        return UnifiedSchema(
            source_type=self.source_type,
            source_id=self.source_id,
            tables=tables,
            database_name=self.database_name,
            metadata={
                "include_sample_data": self.include_sample_data,
                "sample_rows": self.sample_rows
            }
        )
    
    async def _extract_tables(self) -> List[TableInfo]:
        """Extract all tables from the database."""
        tables = []
        
        # Get all tables
        table_names = self.connection.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'main'
            ORDER BY table_name
        """).fetchall()
        
        for (table_name,) in table_names:
            table_info = await self._extract_table_info(table_name)
            tables.append(table_info)
        
        return tables
    
    async def _extract_table_info(self, table_name: str) -> TableInfo:
        """Extract information for a single table."""
        # Get columns
        columns = await self._extract_columns(table_name)
        
        # Get primary keys
        primary_keys = await self._extract_primary_keys(table_name)
        
        # Get foreign keys
        foreign_keys = await self._extract_foreign_keys(table_name)
        
        # Get indexes
        indexes = await self._extract_indexes(table_name)
        
        # Get row count
        row_count = self.connection.execute(
            f'SELECT COUNT(*) FROM "{table_name}"'
        ).fetchone()[0]
        
        # Get sample data if requested
        sample_data = None
        if self.include_sample_data and row_count > 0:
            sample_data = await self._extract_sample_data(table_name)
        
        return TableInfo(
            name=table_name,
            columns=columns,
            primary_keys=primary_keys,
            foreign_keys=foreign_keys,
            indexes=indexes,
            row_count=row_count,
            sample_data=sample_data
        )
    
    async def _extract_columns(self, table_name: str) -> List[ColumnInfo]:
        """Extract column information for a table."""
        columns = []
        
        # Get column information
        result = self.connection.execute(f"""
            SELECT 
                column_name,
                data_type,
                is_nullable,
                column_default,
                character_maximum_length,
                numeric_precision,
                numeric_scale
            FROM information_schema.columns 
            WHERE table_name = '{table_name}'
            ORDER BY ordinal_position
        """).fetchall()
        
        for row in result:
            col_name = row[0]
            col_type = row[1].upper()
            is_nullable = row[2] == 'YES'
            default_value = row[3]
            max_length = row[4]
            numeric_precision = row[5]
            numeric_scale = row[6]
            
            # Map to unified type
            unified_type = self._map_data_type(col_type)
            
            # Check if it's a sticky column
            is_sticky = self._is_sticky_column(col_name, col_type)
            
            columns.append(ColumnInfo(
                name=col_name,
                data_type=unified_type,
                is_nullable=is_nullable,
                is_sticky=is_sticky,
                default_value=default_value,
                max_length=max_length,
                numeric_precision=numeric_precision,
                numeric_scale=numeric_scale,
                original_type=col_type
            ))
        
        return columns
    
    async def _extract_primary_keys(self, table_name: str) -> List[str]:
        """Extract primary key columns for a table."""
        # DuckDB doesn't always expose primary keys through information_schema
        # Try to infer from unique not-null columns or return empty
        try:
            # Check for columns that are not nullable and potentially primary keys
            result = self.connection.execute(f"""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = '{table_name}'
                AND is_nullable = 'NO'
                AND (
                    column_name = 'id' OR 
                    column_name LIKE '%_id' OR
                    column_name = 'uuid' OR
                    column_name = 'guid'
                )
                ORDER BY ordinal_position
                LIMIT 1
            """).fetchall()
            
            return [row[0] for row in result]
        except:
            return []
    
    async def _extract_foreign_keys(self, table_name: str) -> List[ForeignKeyInfo]:
        """Extract foreign key information for a table."""
        # DuckDB doesn't always expose foreign keys through information_schema
        # For uploaded files, we typically don't have foreign keys
        return []
    
    async def _extract_indexes(self, table_name: str) -> List[IndexInfo]:
        """Extract index information for a table."""
        # DuckDB automatically creates indexes, but they're not always exposed
        # For uploaded files, we typically don't have explicit indexes
        return []
    
    async def _extract_sample_data(self, table_name: str) -> List[Dict[str, Any]]:
        """Extract sample data from a table."""
        result = self.connection.execute(
            f'SELECT * FROM "{table_name}" LIMIT {self.sample_rows}'
        )
        
        # Get column names
        column_names = [desc[0] for desc in result.description]
        
        # Convert rows to dictionaries
        rows = result.fetchall()
        sample_data = []
        for row in rows:
            sample_data.append(dict(zip(column_names, row)))
        
        return sample_data
    
    def _map_data_type(self, duckdb_type: str) -> DataType:
        """Map DuckDB data type to unified data type."""
        # Handle parameterized types
        base_type = duckdb_type.split('(')[0].strip().upper()
        
        # Check for array types
        if base_type.endswith('[]'):
            return DataType.ARRAY
        
        # Map to unified type
        return self.TYPE_MAPPINGS.get(base_type, DataType.UNKNOWN)
    
    def _is_sticky_column(self, column_name: str, data_type: str) -> bool:
        """Determine if a column should be marked as sticky."""
        col_lower = column_name.lower()
        
        # Check ID patterns
        for pattern in self.STICKY_PATTERNS:
            if re.match(pattern, col_lower):
                return True
        
        # Check for likely unique text fields
        if data_type in ['VARCHAR', 'TEXT', 'CHAR', 'STRING']:
            for pattern in self.STICKY_NAME_PATTERNS:
                if pattern in col_lower:
                    return True
        
        return False