"""Schema formatting utilities for uploaded files to make them LLM-compatible."""

import re
from typing import Dict, List, Any, Set, Optional
import structlog

logger = structlog.get_logger(__name__)


class UploadedSchemaFormatter:
    """Formats DuckDB schema to be compatible with LLM components."""
    
    def __init__(self):
        # Common patterns for identifying sticky columns
        self.id_patterns = [
            r'.*_id$', r'^id$', r'.*_code$', r'.*_number$', r'.*_no$',
            r'^uuid$', r'^guid$', r'.*_key$', r'^identifier$'
        ]
        
        # Type mappings from DuckDB to semantic types
        self.type_mappings = {
            'BIGINT': 'integer',
            'INTEGER': 'integer',
            'SMALLINT': 'integer',
            'TINYINT': 'integer',
            'DOUBLE': 'numeric',
            'REAL': 'numeric',
            'FLOAT': 'numeric',
            'DECIMAL': 'numeric',
            'NUMERIC': 'numeric',
            'VARCHAR': 'text',
            'CHAR': 'text',
            'TEXT': 'text',
            'STRING': 'text',
            'DATE': 'date',
            'TIMESTAMP': 'timestamp',
            'TIME': 'time',
            'BOOLEAN': 'boolean',
            'BOOL': 'boolean'
        }
    
    def format_for_llm(self, duckdb_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Convert DuckDB schema to LLM-compatible format.
        
        Args:
            duckdb_schema: Schema dict from DuckDB with structure:
                {
                    "tables": {
                        "table_name": {
                            "columns": [
                                {"name": "col1", "data_type": "VARCHAR"},
                                ...
                            ]
                        }
                    }
                }
        
        Returns:
            LLM-compatible schema dict with structure:
                {
                    "tables": ["table1", "table2"],
                    "columns": [
                        {"table": "table1", "column": "col1", "type": "text"},
                        ...
                    ],
                    "sticky_columns": {"table1": ["id", "name"]},
                    "relationships": []  # Empty for uploaded files
                }
        """
        formatted = {
            "tables": [],
            "columns": [],
            "sticky_columns": {},
            "relationships": [],  # No relationships in uploaded files
            "metadata": {
                "source_type": "uploaded_file",
                "extraction_method": "duckdb_information_schema"
            }
        }
        
        if not duckdb_schema or "tables" not in duckdb_schema:
            logger.warning("empty_or_invalid_schema", schema=duckdb_schema)
            return formatted
        
        # Process each table
        for table_name, table_info in duckdb_schema["tables"].items():
            formatted["tables"].append(table_name)
            sticky_columns = []
            
            # Process columns
            for col in table_info.get("columns", []):
                col_name = col["name"]
                col_type = col.get("data_type", "VARCHAR").upper()
                
                # Map to semantic type
                semantic_type = self.type_mappings.get(col_type, "text")
                
                # Add to columns list
                formatted["columns"].append({
                    "table": table_name,
                    "column": col_name,
                    "type": semantic_type,
                    "original_type": col_type
                })
                
                # Check if it's a sticky column
                if self._is_sticky_column(col_name, col_type):
                    sticky_columns.append(col_name)
            
            # Add sticky columns for this table
            if sticky_columns:
                formatted["sticky_columns"][table_name] = sticky_columns
        
        return formatted
    
    def _is_sticky_column(self, column_name: str, data_type: str) -> bool:
        """Determine if a column should be marked as sticky (high-value identifier).
        
        Args:
            column_name: Name of the column
            data_type: DuckDB data type
            
        Returns:
            True if column is likely a sticky column
        """
        col_lower = column_name.lower()
        
        # Check ID patterns
        for pattern in self.id_patterns:
            if re.match(pattern, col_lower):
                return True
        
        # Check for likely unique text fields
        if data_type in ['VARCHAR', 'TEXT', 'CHAR']:
            unique_patterns = ['name', 'title', 'email', 'username', 'phone']
            for pattern in unique_patterns:
                if pattern in col_lower:
                    return True
        
        return False
    
    def format_for_intent_extractor(self, duckdb_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Format schema specifically for IntentExtractor requirements.
        
        The IntentExtractor expects:
        {
            "query": "placeholder",  # Required by IntentExtractor validation
            "tables": ["table1", "table2"],
            "columns": [
                {"table": "table1", "column": "col1"},
                ...
            ]
        }
        """
        formatted = self.format_for_llm(duckdb_schema)
        
        # Simplify columns for intent extractor
        simple_columns = []
        for col in formatted["columns"]:
            simple_columns.append({
                "table": col["table"],
                "column": col["column"]
            })
        
        # Format tables as objects with 'name' field for IntentExtractor
        table_objects = [{"name": table_name} for table_name in formatted["tables"]]
        
        return {
            "query": "uploaded_file_schema",  # Required placeholder
            "tables": table_objects,
            "columns": simple_columns
        }
    
    def generate_llm_text_format(self, duckdb_schema: Dict[str, Any]) -> str:
        """Generate human-readable schema format for LLM prompts.
        
        Similar to schema_for_llm.txt format used by PostgreSQL schemas.
        """
        formatted = self.format_for_llm(duckdb_schema)
        lines = ["Database Schema (Uploaded File):\n"]
        
        for table_name in formatted["tables"]:
            lines.append(f"Table {table_name} {{")
            
            # Add sticky columns comment if any
            sticky_cols = formatted["sticky_columns"].get(table_name, [])
            if sticky_cols:
                lines.append(f"  # Primary identifiers:")
                lines.append(f"  #   - {', '.join(sticky_cols)}")
            
            # Add columns
            table_columns = [c for c in formatted["columns"] if c["table"] == table_name]
            for col in table_columns:
                col_name = col["column"]
                col_type = col["type"]
                
                # Add sticky marker
                sticky_marker = " (sticky)" if col_name in sticky_cols else ""
                lines.append(f"  {col_name}: {col_type}{sticky_marker}")
            
            lines.append("}\n")
        
        return "\n".join(lines)