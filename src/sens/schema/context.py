"""Schema context definitions and type hierarchies."""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Union


@dataclass
class BaseSchemaContext:
    """Base class for all schema context representations."""

    tables: Set[str]


@dataclass
class ValidatorSchemaContext(BaseSchemaContext):
    """Schema context specifically for SQL validation."""

    columns_per_table: Dict[str, Set[str]]
    foreign_keys: Dict[str, Dict[str, Tuple[str, str]]] = field(default_factory=dict)


@dataclass
class LLMSchemaContext(BaseSchemaContext):
    """Schema context optimized for LLM consumption."""

    tables_columns: Dict[str, List[str]]
    primary_keys: Dict[str, List[str]]
    foreign_keys: List[Dict[str, Union[str, List[str]]]] = field(default_factory=list)
    column_descriptions: Dict[str, Dict[str, str]] = field(default_factory=dict)

    def to_validator_schema(self) -> ValidatorSchemaContext:
        """Convert to validator schema format."""
        return ValidatorSchemaContext(
            tables=set(self.tables_columns.keys()),
            columns_per_table={
                table: set(columns) for table, columns in self.tables_columns.items()
            },
            foreign_keys=self._convert_foreign_keys(),
        )

    def _convert_foreign_keys(self) -> Dict[str, Dict[str, Tuple[str, str]]]:
        """Convert foreign keys to validator format."""
        result = {}
        for fk in self.foreign_keys:
            from_table = fk["from_table"]
            to_table = fk["to_table"]
            from_cols = fk["from_columns"]
            to_cols = fk["to_columns"]

            # Handle both single column and multi-column foreign keys
            if isinstance(from_cols, str) and isinstance(to_cols, str):
                from_cols = [from_cols]
                to_cols = [to_cols]

            # Add each column pair as a foreign key
            if from_table not in result:
                result[from_table] = {}
            for from_col, to_col in zip(from_cols, to_cols):
                result[from_table][from_col] = (to_table, to_col)

        return result


@dataclass
class TableContext:
    """Represents a table in the schema context."""

    name: str
    columns: List[str]
    description: Optional[str] = None


class SchemaContext:
    """Manages schema context for LLM interactions."""

    def __init__(self, tables: List[TableContext]):
        """Initialize schema context.

        Args:
            tables: List of TableContext objects

        Raises:
            ValueError: If no valid tables are provided
        """
        if not tables:
            raise ValueError("Schema context must contain at least one table")
        self.tables = tables

    def format_for_llm(self) -> str:
        """Format schema context for LLM consumption."""
        parts = []
        for table in self.tables:
            columns_str = ", ".join(table.columns)
            table_def = f"TABLE {table.name} ({columns_str})"
            if table.description:
                table_def += f"\n-- {table.description}"
            parts.append(table_def)
        return "\n\n".join(parts)

    @classmethod
    def validate_snippet(cls, snippet: str) -> bool:
        """Validate if a schema snippet is well-formed.

        Args:
            snippet: Schema snippet to validate

        Returns:
            bool: True if snippet is valid
        """
        if not snippet or not snippet.strip():
            return False

        # Must contain at least one valid table definition
        table_pattern = r"TABLE\s+(\w+)\s*\(([\w\s,]+)\)"
        matches = re.findall(table_pattern, snippet, re.IGNORECASE)
        if not matches:
            return False

        # Each matched table should have at least one column
        for _, columns in matches:
            if not columns.strip():
                return False

        return True
