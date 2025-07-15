"""
SQLite-specific schema extractor for BIRD-SQL-DEV evaluation.

This module extracts schema information from SQLite databases for use in NL2SQL generation.
"""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import structlog

from .schema_extractor import (
    ColumnInfo,
    DatabaseSchema,
    ForeignKeyColumnPair,
    ForeignKeyConstraint,
    TableInfo,
)

logger = structlog.get_logger(__name__)


class SQLiteSchemaExtractor:
    """Extracts schema information from SQLite databases."""

    def __init__(self, db_path: str):
        """Initialize with SQLite database path.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"SQLite database file not found: {db_path}")
        
        logger.info(f"Initialized SQLite schema extractor for: {db_path}")

    def extract_schema(self) -> DatabaseSchema:
        """Extract complete schema from SQLite database.
        
        Returns:
            DatabaseSchema object with complete schema information
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                
                # Extract all tables
                tables = self._get_all_tables(conn)
                table_info = {}
                all_relationships = []
                
                for table_name in tables:
                    logger.debug(f"Processing table: {table_name}")
                    
                    # Get table info
                    table_data = self._get_table_info(conn, table_name)
                    table_info[table_name] = table_data
                    
                    # Collect foreign key relationships
                    all_relationships.extend(table_data.foreign_keys)
                
                # Create database schema
                schema = DatabaseSchema(
                    tables=table_info,
                    relationships=all_relationships,
                    metadata={
                        "database_type": "sqlite",
                        "database_path": str(self.db_path),
                        "table_count": len(table_info),
                        "extraction_timestamp": None,  # Will be set by caller if needed
                    }
                )
                
                logger.info(f"Extracted schema for {len(table_info)} tables from SQLite database")
                return schema
                
        except Exception as e:
            logger.error(f"Failed to extract schema from SQLite database: {e}")
            raise

    def _get_all_tables(self, conn: sqlite3.Connection) -> List[str]:
        """Get all table names from the database.
        
        Args:
            conn: SQLite database connection
            
        Returns:
            List of table names
        """
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)
        
        tables = [row['name'] for row in cursor.fetchall()]
        logger.debug(f"Found tables: {tables}")
        return tables

    def _get_table_info(self, conn: sqlite3.Connection, table_name: str) -> TableInfo:
        """Get detailed information about a table.
        
        Args:
            conn: SQLite database connection
            table_name: Name of the table
            
        Returns:
            TableInfo object with complete table information
        """
        cursor = conn.cursor()
        
        # Get column information
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns_data = cursor.fetchall()
        
        columns = []
        primary_keys = []
        
        for col_data in columns_data:
            # Extract column info from PRAGMA result
            col_name = col_data['name']
            col_type = col_data['type']
            is_nullable = not col_data['notnull']
            default_value = col_data['dflt_value']
            is_primary = bool(col_data['pk'])
            
            if is_primary:
                primary_keys.append(col_name)
            
            # Create column info
            column_info = ColumnInfo(
                name=col_name,
                data_type=col_type,
                is_nullable=is_nullable,
                default_value=default_value,
                is_primary=is_primary,
                foreign_key=None,  # Will be set below
                description=None,
            )
            columns.append(column_info)
        
        # Get foreign key information
        foreign_keys = self._get_foreign_keys(conn, table_name)
        
        # Update column foreign key references
        for column in columns:
            for fk in foreign_keys:
                # Check if this column is part of any FK constraint
                for col_pair in fk.columns:
                    if col_pair.from_column == column.name:
                        column.foreign_key = {
                            "table": fk.to_table,
                            "column": col_pair.to_column,
                        }
                        break
        
        # Get row count
        try:
            cursor.execute(f"SELECT COUNT(*) as count FROM {table_name}")
            row_count = cursor.fetchone()['count']
        except Exception:
            row_count = None
        
        # Identify sticky columns (important identifier columns)
        sticky_columns = self._identify_sticky_columns(columns)
        
        return TableInfo(
            name=table_name,
            columns=columns,
            primary_keys=primary_keys,
            foreign_keys=foreign_keys,
            row_count=row_count,
            description=None,
            sticky_columns=sticky_columns,
        )

    def _get_foreign_keys(self, conn: sqlite3.Connection, table_name: str) -> List[ForeignKeyConstraint]:
        """Get foreign key constraints for a table.
        
        Args:
            conn: SQLite database connection
            table_name: Name of the table
            
        Returns:
            List of ForeignKeyConstraint objects
        """
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA foreign_key_list({table_name})")
        fk_data = cursor.fetchall()
        
        # Group foreign keys by constraint (id field)
        fk_groups = {}
        for fk_row in fk_data:
            fk_id = fk_row['id']
            if fk_id not in fk_groups:
                fk_groups[fk_id] = []
            fk_groups[fk_id].append(fk_row)
        
        # Create ForeignKeyConstraint objects
        constraints = []
        for fk_id, fk_rows in fk_groups.items():
            # All rows in a group should have the same target table
            to_table = fk_rows[0]['table']
            
            # Create column pairs
            column_pairs = []
            for fk_row in fk_rows:
                # Handle case where 'to' column might be None
                to_column = fk_row['to'] or fk_row['from']  # Use from_column as fallback
                column_pairs.append(ForeignKeyColumnPair(
                    from_column=fk_row['from'],
                    to_column=to_column,
                ))
            
            # Create constraint
            constraint = ForeignKeyConstraint(
                constraint_name=f"{table_name}_fk_{fk_id}",
                from_table=table_name,
                to_table=to_table,
                columns=column_pairs,
            )
            constraints.append(constraint)
        
        return constraints

    def _identify_sticky_columns(self, columns: List[ColumnInfo]) -> List[str]:
        """Identify important identifier columns (sticky columns).
        
        Args:
            columns: List of column information
            
        Returns:
            List of column names that are important identifiers
        """
        sticky_columns = []
        
        for column in columns:
            col_name_lower = column.name.lower()
            
            # Primary keys are always sticky
            if column.is_primary:
                sticky_columns.append(column.name)
                continue
            
            # Common identifier patterns
            identifier_patterns = [
                'id', 'name', 'title', 'code', 'number', 'email', 'username',
                'phone', 'address', 'city', 'state', 'country', 'zip',
                'description', 'type', 'status', 'category', 'class',
            ]
            
            # Check if column name matches common patterns
            for pattern in identifier_patterns:
                if pattern in col_name_lower:
                    sticky_columns.append(column.name)
                    break
        
        return sticky_columns

    def get_schema_context(self) -> str:
        """Get a formatted schema context string for LLM consumption.
        
        Returns:
            Formatted schema context string
        """
        schema = self.extract_schema()
        
        context_parts = [
            f"Database: SQLite ({self.db_path.name})",
            f"Tables: {len(schema.tables)}",
            "",
            "=== SCHEMA STRUCTURE ===",
            ""
        ]
        
        # Add table information
        for table_name, table_info in schema.tables.items():
            context_parts.append(f"TABLE: {table_name}")
            context_parts.append(f"  Rows: {table_info.row_count or 'Unknown'}")
            context_parts.append("  Columns:")
            
            for column in table_info.columns:
                col_desc = f"    {column.name}: {column.data_type}"
                if column.is_primary:
                    col_desc += " (PRIMARY KEY)"
                if column.foreign_key:
                    col_desc += f" -> {column.foreign_key['table']}.{column.foreign_key['column']}"
                if not column.is_nullable:
                    col_desc += " NOT NULL"
                context_parts.append(col_desc)
            
            if table_info.sticky_columns:
                context_parts.append(f"  Key columns: {', '.join(table_info.sticky_columns)}")
            
            context_parts.append("")
        
        # Add relationships
        if schema.relationships:
            context_parts.append("=== RELATIONSHIPS ===")
            for rel in schema.relationships:
                context_parts.append(f"{rel.from_table} -> {rel.to_table}")
                for col_pair in rel.columns:
                    context_parts.append(f"  {col_pair.from_column} -> {col_pair.to_column}")
            context_parts.append("")
        
        return "\n".join(context_parts)

    def save_schema_to_file(self, output_path: str) -> None:
        """Save extracted schema to a JSON file.
        
        Args:
            output_path: Path to save the schema file
        """
        schema = self.extract_schema()
        
        # Convert to dict for JSON serialization
        schema_dict = schema.model_dump()
        
        with open(output_path, 'w') as f:
            json.dump(schema_dict, f, indent=2)
        
        logger.info(f"Schema saved to: {output_path}")