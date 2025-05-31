"""Schema format adapter for converting UnifiedSchema to component-specific formats."""

from typing import Dict, List, Any, Optional, Set
import structlog

from sens.schema.unified_schema import UnifiedSchema, TableInfo, ColumnInfo
from sens.schema.context import LLMSchemaContext, ValidatorSchemaContext
from sens.llm.models import Intent

logger = structlog.get_logger(__name__)


class SchemaFormatAdapter:
    """Converts UnifiedSchema to various formats required by different components."""
    
    @staticmethod
    def for_intent_extractor(schema: UnifiedSchema) -> Dict[str, Any]:
        """Convert UnifiedSchema to format expected by IntentExtractor.
        
        IntentExtractor expects:
        {
            "query": "placeholder",
            "tables": [{"name": "table1"}, ...],
            "columns": [{"table": "t1", "column": "c1"}, ...]
        }
        """
        tables = []
        columns = []
        
        for table in schema.tables:
            # Add table
            tables.append({"name": table.name})
            
            # Add columns
            for column in table.columns:
                columns.append({
                    "table": table.name,
                    "column": column.name
                })
        
        return {
            "query": f"{schema.source_type.value}_schema",  # Placeholder query
            "tables": tables,
            "columns": columns
        }
    
    @staticmethod
    def for_sql_generator(schema: UnifiedSchema, 
                         intent: Optional[Intent] = None) -> LLMSchemaContext:
        """Convert UnifiedSchema to LLMSchemaContext for SQLGenerator.
        
        Args:
            schema: The unified schema
            intent: Optional intent to filter relevant tables
            
        Returns:
            LLMSchemaContext with all necessary information
        """
        # Filter tables if intent is provided
        if intent and intent.tables:
            relevant_tables = [t for t in schema.tables if t.name in intent.tables]
        else:
            relevant_tables = schema.tables
        
        # Build the context
        tables_columns = {}
        primary_keys = {}
        column_descriptions = {}
        sticky_columns = {}
        column_types = {}  # Add column types
        sample_data = {}  # Add sample data
        
        for table in relevant_tables:
            # Table columns
            tables_columns[table.name] = [col.name for col in table.columns]
            
            # Primary keys
            if table.primary_keys:
                primary_keys[table.name] = table.primary_keys
            
            # Column descriptions
            table_descriptions = {}
            table_types = {}
            for col in table.columns:
                if col.description:
                    table_descriptions[col.name] = col.description
                # Include data type information
                table_types[col.name] = col.data_type.value
            if table_descriptions:
                column_descriptions[table.name] = table_descriptions
            column_types[table.name] = table_types
            
            # Sticky columns
            sticky_cols = table.get_sticky_columns()
            if sticky_cols:
                sticky_columns[table.name] = sticky_cols
                
            # Sample data
            if table.sample_data:
                sample_data[table.name] = table.sample_data
        
        # Convert foreign keys
        foreign_keys = []
        for table in relevant_tables:
            for fk in table.foreign_keys:
                foreign_keys.append({
                    "from_table": fk.from_table,
                    "from_columns": fk.from_columns,
                    "to_table": fk.to_table,
                    "to_columns": fk.to_columns
                })
        
        # Create LLMSchemaContext with proper table set
        return LLMSchemaContext(
            tables=set(tables_columns.keys()),  # Set of table names
            tables_columns=tables_columns,
            primary_keys=primary_keys,
            foreign_keys=foreign_keys,
            column_descriptions=column_descriptions,
            sticky_columns=sticky_columns,
            column_types=column_types,
            sample_data=sample_data
        )
    
    @staticmethod
    def for_validator(schema: UnifiedSchema, 
                     relevant_tables: Optional[List[str]] = None) -> ValidatorSchemaContext:
        """Convert UnifiedSchema to ValidatorSchemaContext for SQL validation.
        
        Args:
            schema: The unified schema
            relevant_tables: Optional list of table names to include
            
        Returns:
            ValidatorSchemaContext for SQL validation
        """
        # Filter tables if specified
        if relevant_tables:
            tables_to_include = [t for t in schema.tables if t.name in relevant_tables]
        else:
            tables_to_include = schema.tables
        
        # Build context
        tables = set()
        columns_per_table = {}
        foreign_keys = {}
        
        for table in tables_to_include:
            tables.add(table.name)
            
            # Columns as set
            columns_per_table[table.name] = set(col.name for col in table.columns)
            
            # Foreign keys in validator format
            table_fks = {}
            for fk in table.foreign_keys:
                # Handle composite foreign keys
                for from_col, to_col in zip(fk.from_columns, fk.to_columns):
                    table_fks[from_col] = (fk.to_table, to_col)
            
            if table_fks:
                foreign_keys[table.name] = table_fks
        
        return ValidatorSchemaContext(
            tables=tables,
            columns_per_table=columns_per_table,
            foreign_keys=foreign_keys
        )
    
    @staticmethod
    def for_retrieval(schema: UnifiedSchema) -> Dict[str, Any]:
        """Convert UnifiedSchema to format suitable for retrieval systems.
        
        Returns a simplified format optimized for search and retrieval.
        """
        retrieval_format = {
            "tables": [],
            "columns": [],
            "relationships": [],
            "metadata": {
                "source_type": schema.source_type.value,
                "source_id": schema.source_id,
                "total_tables": len(schema.tables),
                "total_columns": sum(len(t.columns) for t in schema.tables)
            }
        }
        
        # Add tables with metadata
        for table in schema.tables:
            table_info = {
                "name": table.name,
                "description": table.description,
                "row_count": table.row_count,
                "column_count": len(table.columns),
                "has_primary_key": bool(table.primary_keys),
                "sticky_columns": table.get_sticky_columns()
            }
            retrieval_format["tables"].append(table_info)
            
            # Add columns with search-friendly format
            for col in table.columns:
                col_info = {
                    "table": table.name,
                    "column": col.name,
                    "type": col.data_type.value,
                    "is_primary": col.is_primary_key,
                    "is_foreign": col.is_foreign_key,
                    "is_sticky": col.is_sticky,
                    "is_nullable": col.is_nullable,
                    "description": col.description
                }
                retrieval_format["columns"].append(col_info)
        
        # Add relationships
        for fk in schema.get_foreign_keys():
            rel_info = {
                "from_table": fk.from_table,
                "from_columns": fk.from_columns,
                "to_table": fk.to_table,
                "to_columns": fk.to_columns
            }
            retrieval_format["relationships"].append(rel_info)
        
        return retrieval_format
    
    @staticmethod
    def to_text_format(schema: UnifiedSchema, 
                      include_descriptions: bool = True,
                      include_relationships: bool = True) -> str:
        """Convert UnifiedSchema to human-readable text format.
        
        Similar to the schema_for_llm.txt format.
        """
        lines = [f"Database Schema ({schema.source_type.value}):\n"]
        
        if schema.database_name:
            lines.append(f"Database: {schema.database_name}")
        if schema.description:
            lines.append(f"Description: {schema.description}")
        lines.append("")
        
        # Add each table
        for table in sorted(schema.tables, key=lambda t: t.name):
            lines.append(f"Table {table.name} {{")
            
            # Add table description
            if include_descriptions and table.description:
                lines.append(f"  -- {table.description}")
            
            # Add sticky columns comment if any
            sticky_cols = table.get_sticky_columns()
            if sticky_cols:
                lines.append(f"  # Primary identifiers:")
                lines.append(f"  #   - {', '.join(sticky_cols)}")
            
            # Add columns
            for col in table.columns:
                col_def_parts = [f"  {col.name}: {col.data_type.value}"]
                
                # Add constraints
                constraints = []
                if col.is_primary_key:
                    constraints.append("primary key")
                if col.is_foreign_key:
                    constraints.append("foreign key")
                if col.is_unique:
                    constraints.append("unique")
                if not col.is_nullable:
                    constraints.append("not null")
                if col.is_sticky:
                    constraints.append("sticky")
                
                if constraints:
                    col_def_parts.append(f"({', '.join(constraints)})")
                
                # Add description
                if include_descriptions and col.description:
                    col_def_parts.append(f"-- {col.description}")
                
                lines.append(" ".join(col_def_parts))
            
            lines.append("}\n")
        
        # Add relationships section
        if include_relationships:
            relationships = schema.get_relationships()
            if relationships:
                lines.append("Relationships:")
                for from_table, to_tables in sorted(relationships.items()):
                    for to_table in sorted(to_tables):
                        lines.append(f"  {from_table} -> {to_table}")
                lines.append("")
        
        return "\n".join(lines)
    
    @staticmethod
    def to_schema_dict(schema: UnifiedSchema) -> Dict[str, Any]:
        """Convert UnifiedSchema to dictionary format for storage/serialization.
        
        This is the format used for schema caching and persistence.
        """
        return schema.to_dict()