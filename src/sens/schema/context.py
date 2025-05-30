"""Schema context definitions and type hierarchies."""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Union


@dataclass
class BaseSchemaContext:
    """Base class for all schema context representations."""

    # Fields without defaults must come first, both in the base class and in derived classes
    tables: Set[str]
    # Fields with defaults must come after all non-default fields, including those in derived classes
    metadata: Dict[str, Any] = field(
        default_factory=dict,
        init=False,  # This prevents the field from being part of __init__
    )

    def __post_init__(self):
        """Initialize default values after dataclass initialization."""
        # Initialize metadata with an empty dict if not set
        self.metadata = {}


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
    sticky_columns: Dict[str, List[str]] = field(
        default_factory=dict,
        metadata={"description": "High-value identifier columns per table"},
    )
    column_types: Dict[str, Dict[str, str]] = field(
        default_factory=dict,
        metadata={"description": "Column data types per table"},
    )

    def to_validator_schema(self) -> ValidatorSchemaContext:
        """Convert to validator schema format."""
        # Use inherited tables from BaseSchemaContext
        current_tables = self.tables
        columns_per_table = {}

        for table, columns in self.tables_columns.items():
            # Convert to set and ensure primary keys are included
            column_set = set(columns)
            if table in self.primary_keys:
                column_set.update(self.primary_keys[table])

            # Ensure foreign key columns are included
            for fk in self.foreign_keys:
                if fk["from_table"] == table:
                    if isinstance(fk["from_columns"], list):
                        column_set.update(fk["from_columns"])
                    else:
                        column_set.add(fk["from_columns"])
                elif fk["to_table"] == table:
                    if isinstance(fk["to_columns"], list):
                        column_set.update(fk["to_columns"])
                    else:
                        column_set.add(fk["to_columns"])

            columns_per_table[table] = column_set

        # Ensure all tables from self.tables (inherited) are in columns_per_table
        for table in current_tables:
            if table not in columns_per_table:
                columns_per_table[table] = set()

        return ValidatorSchemaContext(
            tables=current_tables,  # Pass the inherited tables
            columns_per_table=columns_per_table,
            foreign_keys=self._convert_foreign_keys(),
            # metadata is inherited and handled by BaseSchemaContext's __post_init__
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

    def format_for_llm(self) -> str:
        """Format schema context for LLM consumption, including sticky columns."""
        parts = []

        # Format tables and their columns
        for table, columns in self.tables_columns.items():
            # Start with table definition
            table_def = [f"TABLE {table} ({', '.join(columns)})"]

            # Add column descriptions if available
            if table in self.column_descriptions:
                for col, desc in self.column_descriptions[table].items():
                    table_def.append(f"-- {col}: {desc}")

            # Add sticky columns if available
            if table in self.sticky_columns and self.sticky_columns[table]:
                sticky_cols = ", ".join(self.sticky_columns[table])
                table_def.append(f"-- Primary identifiers: {sticky_cols}")

            parts.append("\n".join(table_def))

        return "\n\n".join(parts)


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
