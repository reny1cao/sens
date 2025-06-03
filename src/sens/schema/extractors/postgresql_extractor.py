"""Schema extractor for PostgreSQL databases."""

import asyncio
from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2.extras import DictCursor
import structlog

from sens.schema.unified_schema import (
    UnifiedSchema, TableInfo, ColumnInfo, DataType, 
    DataSourceType, ForeignKeyInfo, IndexInfo
)
from sens.schema.identifier_scorer import IdentifierScorer
from .base import SchemaExtractor, SchemaExtractionError

logger = structlog.get_logger(__name__)


class PostgreSQLExtractor(SchemaExtractor):
    """Extract schema from PostgreSQL database."""
    
    # Type mappings from PostgreSQL to unified types
    TYPE_MAPPINGS = {
        'bigint': DataType.BIGINT,
        'int8': DataType.BIGINT,
        'bigserial': DataType.BIGINT,
        'serial8': DataType.BIGINT,
        'integer': DataType.INTEGER,
        'int': DataType.INTEGER,
        'int4': DataType.INTEGER,
        'serial': DataType.INTEGER,
        'serial4': DataType.INTEGER,
        'smallint': DataType.SMALLINT,
        'int2': DataType.SMALLINT,
        'smallserial': DataType.SMALLINT,
        'serial2': DataType.SMALLINT,
        'numeric': DataType.NUMERIC,
        'decimal': DataType.DECIMAL,
        'real': DataType.FLOAT,
        'float4': DataType.FLOAT,
        'double precision': DataType.DOUBLE,
        'float8': DataType.DOUBLE,
        'float': DataType.FLOAT,
        'character varying': DataType.VARCHAR,
        'varchar': DataType.VARCHAR,
        'character': DataType.CHAR,
        'char': DataType.CHAR,
        'text': DataType.TEXT,
        'date': DataType.DATE,
        'time': DataType.TIME,
        'time without time zone': DataType.TIME,
        'time with time zone': DataType.TIME,
        'timestamp': DataType.TIMESTAMP,
        'timestamp without time zone': DataType.TIMESTAMP,
        'timestamp with time zone': DataType.TIMESTAMPTZ,
        'timestamptz': DataType.TIMESTAMPTZ,
        'boolean': DataType.BOOLEAN,
        'bool': DataType.BOOLEAN,
        'uuid': DataType.UUID,
        'json': DataType.JSON,
        'jsonb': DataType.JSONB,
        'array': DataType.ARRAY,
        'bytea': DataType.TEXT,
    }
    
    def __init__(self, 
                 db_url: str,
                 source_id: str,
                 schema_name: str = "public",
                 include_views: bool = False,
                 include_sample_data: bool = True,
                 sample_rows: int = 5,
                 analyze_sticky_columns: bool = True):
        """Initialize PostgreSQL extractor.
        
        Args:
            db_url: PostgreSQL connection URL
            source_id: Unique identifier for this source
            schema_name: Schema to extract (default: public)
            include_views: Whether to include views
            include_sample_data: Whether to include sample data
            sample_rows: Number of sample rows to include
            analyze_sticky_columns: Whether to analyze for sticky columns
        """
        super().__init__(DataSourceType.POSTGRESQL, source_id)
        self.db_url = db_url
        self.schema_name = schema_name
        self.include_views = include_views
        self.include_sample_data = include_sample_data
        self.sample_rows = sample_rows
        self.analyze_sticky_columns = analyze_sticky_columns
        self._connection = None
        self._identifier_scorer = IdentifierScorer() if analyze_sticky_columns else None
    
    def _connect(self):
        """Create database connection."""
        if not self._connection:
            self._connection = psycopg2.connect(self.db_url)
        return self._connection
    
    def _close(self):
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
    
    async def extract(self) -> UnifiedSchema:
        """Extract schema from PostgreSQL database."""
        try:
            conn = self._connect()
            
            # Get database name
            with conn.cursor() as cursor:
                cursor.execute("SELECT current_database()")
                database_name = cursor.fetchone()[0]
            
            # Extract tables
            tables = await self._extract_tables(conn)
            
            # Analyze sticky columns if requested
            if self.analyze_sticky_columns and self._identifier_scorer:
                await self._analyze_sticky_columns(conn, tables)
            
            return UnifiedSchema(
                source_type=self.source_type,
                source_id=self.source_id,
                tables=tables,
                database_name=database_name,
                schema_name=self.schema_name,
                metadata={
                    "include_views": self.include_views,
                    "include_sample_data": self.include_sample_data,
                    "analyze_sticky_columns": self.analyze_sticky_columns
                }
            )
            
        finally:
            self._close()
    
    async def _extract_tables(self, conn) -> List[TableInfo]:
        """Extract all tables from the database."""
        tables = []
        
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            # Get all tables (and optionally views)
            table_type_filter = "IN ('BASE TABLE')"
            if self.include_views:
                table_type_filter = "IN ('BASE TABLE', 'VIEW')"
            
            cursor.execute(f"""
                SELECT 
                    t.table_name,
                    obj_description(c.oid) as table_comment
                FROM information_schema.tables t
                JOIN pg_class c ON c.relname = t.table_name
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE t.table_schema = %s
                AND t.table_type {table_type_filter}
                AND n.nspname = %s
                ORDER BY t.table_name
            """, (self.schema_name, self.schema_name))
            
            table_data = cursor.fetchall()
            
            for row in table_data:
                table_info = await self._extract_table_info(
                    conn, row['table_name'], row['table_comment']
                )
                tables.append(table_info)
        
        return tables
    
    async def _extract_table_info(self, conn, table_name: str, 
                                  table_comment: Optional[str]) -> TableInfo:
        """Extract information for a single table."""
        # Get columns
        columns = await self._extract_columns(conn, table_name)
        
        # Get primary keys
        primary_keys = await self._extract_primary_keys(conn, table_name)
        
        # Update column info with primary key flags
        for col in columns:
            if col.name in primary_keys:
                col.is_primary_key = True
        
        # Get foreign keys
        foreign_keys = await self._extract_foreign_keys(conn, table_name)
        
        # Update column info with foreign key flags
        fk_columns = set()
        for fk in foreign_keys:
            fk_columns.update(fk.from_columns)
        for col in columns:
            if col.name in fk_columns:
                col.is_foreign_key = True
        
        # Get indexes
        indexes = await self._extract_indexes(conn, table_name)
        
        # Get row count
        with conn.cursor() as cursor:
            cursor.execute(f'SELECT COUNT(*) FROM "{self.schema_name}"."{table_name}"')
            row_count = cursor.fetchone()[0]
        
        # Check if table is partitioned or is a partition
        partition_info = await self._extract_partition_info(conn, table_name)
        
        # Get sample data if requested
        sample_data = None
        if self.include_sample_data and row_count > 0:
            sample_data = await self._extract_sample_data(conn, table_name)
        
        return TableInfo(
            name=table_name,
            columns=columns,
            primary_keys=primary_keys,
            foreign_keys=foreign_keys,
            indexes=indexes,
            row_count=row_count,
            description=table_comment,
            sample_data=sample_data,
            is_partitioned=partition_info['is_partitioned'],
            partition_key=partition_info['partition_key'],
            is_partition=partition_info['is_partition'],
            parent_table=partition_info['parent_table']
        )
    
    async def _extract_columns(self, conn, table_name: str) -> List[ColumnInfo]:
        """Extract column information for a table."""
        columns = []
        
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("""
                SELECT 
                    c.column_name,
                    c.data_type,
                    c.is_nullable,
                    c.column_default,
                    c.character_maximum_length,
                    c.numeric_precision,
                    c.numeric_scale,
                    c.udt_name,
                    col_description(pgc.oid, c.ordinal_position) as column_comment,
                    CASE 
                        WHEN pk.column_name IS NOT NULL THEN true 
                        ELSE false 
                    END as is_primary_key,
                    CASE 
                        WHEN uc.column_name IS NOT NULL THEN true 
                        ELSE false 
                    END as is_unique
                FROM information_schema.columns c
                JOIN pg_class pgc ON pgc.relname = c.table_name
                JOIN pg_namespace n ON n.oid = pgc.relnamespace AND n.nspname = c.table_schema
                LEFT JOIN (
                    SELECT ku.table_schema, ku.table_name, ku.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage ku
                        ON tc.constraint_name = ku.constraint_name
                        AND tc.table_schema = ku.table_schema
                    WHERE tc.constraint_type = 'PRIMARY KEY'
                ) pk ON pk.table_schema = c.table_schema 
                    AND pk.table_name = c.table_name 
                    AND pk.column_name = c.column_name
                LEFT JOIN (
                    SELECT ku.table_schema, ku.table_name, ku.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage ku
                        ON tc.constraint_name = ku.constraint_name
                        AND tc.table_schema = ku.table_schema
                    WHERE tc.constraint_type = 'UNIQUE'
                ) uc ON uc.table_schema = c.table_schema 
                    AND uc.table_name = c.table_name 
                    AND uc.column_name = c.column_name
                WHERE c.table_schema = %s AND c.table_name = %s
                ORDER BY c.ordinal_position
            """, (self.schema_name, table_name))
            
            for row in cursor.fetchall():
                col_type = row['data_type'].lower()
                
                # Handle array types
                if row['udt_name'] and row['udt_name'].startswith('_'):
                    col_type = 'array'
                
                # Map to unified type
                unified_type = self.TYPE_MAPPINGS.get(col_type, DataType.UNKNOWN)
                
                columns.append(ColumnInfo(
                    name=row['column_name'],
                    data_type=unified_type,
                    is_nullable=row['is_nullable'] == 'YES',
                    is_primary_key=row['is_primary_key'],
                    is_unique=row['is_unique'],
                    default_value=row['column_default'],
                    description=row['column_comment'],
                    max_length=row['character_maximum_length'],
                    numeric_precision=row['numeric_precision'],
                    numeric_scale=row['numeric_scale'],
                    original_type=row['data_type']
                ))
        
        return columns
    
    async def _extract_primary_keys(self, conn, table_name: str) -> List[str]:
        """Extract primary key columns for a table."""
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT ku.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage ku
                    ON tc.constraint_name = ku.constraint_name
                    AND tc.table_schema = ku.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                    AND tc.table_schema = %s
                    AND tc.table_name = %s
                ORDER BY ku.ordinal_position
            """, (self.schema_name, table_name))
            
            return [row[0] for row in cursor.fetchall()]
    
    async def _extract_foreign_keys(self, conn, table_name: str) -> List[ForeignKeyInfo]:
        """Extract foreign key information for a table."""
        foreign_keys = []
        
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("""
                SELECT 
                    tc.constraint_name,
                    kcu.column_name as from_column,
                    ccu.table_name as to_table,
                    ccu.column_name as to_column
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage ccu
                    ON ccu.constraint_name = tc.constraint_name
                    AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                    AND tc.table_schema = %s
                    AND tc.table_name = %s
                ORDER BY tc.constraint_name, kcu.ordinal_position
            """, (self.schema_name, table_name))
            
            # Group by constraint name to handle composite foreign keys
            fk_dict = {}
            for row in cursor.fetchall():
                constraint_name = row['constraint_name']
                if constraint_name not in fk_dict:
                    fk_dict[constraint_name] = {
                        'from_columns': [],
                        'to_table': row['to_table'],
                        'to_columns': []
                    }
                fk_dict[constraint_name]['from_columns'].append(row['from_column'])
                fk_dict[constraint_name]['to_columns'].append(row['to_column'])
            
            # Convert to ForeignKeyInfo objects
            for constraint_name, fk_data in fk_dict.items():
                foreign_keys.append(ForeignKeyInfo(
                    from_table=table_name,
                    from_columns=fk_data['from_columns'],
                    to_table=fk_data['to_table'],
                    to_columns=fk_data['to_columns'],
                    constraint_name=constraint_name
                ))
        
        return foreign_keys
    
    async def _extract_indexes(self, conn, table_name: str) -> List[IndexInfo]:
        """Extract index information for a table."""
        indexes = []
        
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("""
                SELECT 
                    i.relname as index_name,
                    a.attname as column_name,
                    ix.indisunique as is_unique,
                    ix.indisprimary as is_primary
                FROM pg_class t
                JOIN pg_index ix ON t.oid = ix.indrelid
                JOIN pg_class i ON i.oid = ix.indexrelid
                JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
                JOIN pg_namespace n ON n.oid = t.relnamespace
                WHERE t.relname = %s AND n.nspname = %s
                ORDER BY i.relname, a.attnum
            """, (table_name, self.schema_name))
            
            # Group by index name
            index_dict = {}
            for row in cursor.fetchall():
                index_name = row['index_name']
                if index_name not in index_dict:
                    index_dict[index_name] = {
                        'columns': [],
                        'is_unique': row['is_unique'],
                        'is_primary': row['is_primary']
                    }
                index_dict[index_name]['columns'].append(row['column_name'])
            
            # Convert to IndexInfo objects
            for index_name, index_data in index_dict.items():
                indexes.append(IndexInfo(
                    name=index_name,
                    table=table_name,
                    columns=index_data['columns'],
                    is_unique=index_data['is_unique'],
                    is_primary=index_data['is_primary']
                ))
        
        return indexes
    
    async def _extract_partition_info(self, conn, table_name: str) -> Dict[str, Any]:
        """Extract partition information for a table."""
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            # Check if table is partitioned (is a parent)
            cursor.execute("""
                SELECT 
                    pg_get_partkeydef(c.oid) as partition_key
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = %s AND c.relname = %s AND c.relkind = 'p'
            """, (self.schema_name, table_name))
            
            partitioned_result = cursor.fetchone()
            
            # Check if table is a partition (has a parent)
            cursor.execute("""
                SELECT 
                    p.relname as parent_table
                FROM pg_class c
                JOIN pg_inherits i ON c.oid = i.inhrelid
                JOIN pg_class p ON i.inhparent = p.oid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = %s AND c.relname = %s
            """, (self.schema_name, table_name))
            
            partition_result = cursor.fetchone()
            
            return {
                'is_partitioned': partitioned_result is not None,
                'partition_key': partitioned_result['partition_key'] if partitioned_result else None,
                'is_partition': partition_result is not None,
                'parent_table': partition_result['parent_table'] if partition_result else None
            }
    
    async def _extract_sample_data(self, conn, table_name: str) -> List[Dict[str, Any]]:
        """Extract sample data from a table."""
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute(
                f'SELECT * FROM "{self.schema_name}"."{table_name}" LIMIT %s',
                (self.sample_rows,)
            )
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def _analyze_sticky_columns(self, conn, tables: List[TableInfo]):
        """Analyze and mark sticky columns using IdentifierScorer."""
        for table in tables:
            # Score each column individually
            column_scores = {}
            for col in table.columns:
                score = self._identifier_scorer.score_column(col, table)
                column_scores[col.name] = score.score
            
            # Mark columns with score > 0.5 as sticky
            sticky_columns = []
            for col in table.columns:
                if column_scores[col.name] > 0.5:
                    col.is_sticky = True
                    sticky_columns.append(col.name)
                    
            if sticky_columns:
                logger.info("sticky_columns_identified",
                           table=table.name,
                           sticky_columns=sticky_columns)