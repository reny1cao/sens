"""Type definitions for SQL validation."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class ColumnReference:
    """Reference to a column in a table."""

    table: Optional[str]  # Table name, None if unqualified
    column: str  # Column name


@dataclass
class JoinCondition:
    """Join condition between two tables."""

    left_table: str
    right_table: str
    left_column: str
    right_column: str


@dataclass
class ContextBypassInfo:
    """Information about schema context bypass detection."""

    is_bypass: bool = False
    used_but_missing_columns: List[Tuple[str, str]] = field(
        default_factory=list
    )  # List of (table, column)
    prompted_tables: List[str] = field(default_factory=list)
    full_schema_version: Optional[str] = None  # From schema metadata
    bypass_score: float = 0.0  # Ratio of missing columns to total used columns

    def to_log_dict(self, query_id: str) -> Dict:
        """Convert to a structured log dictionary format."""
        return {
            "type": "context_bypass",
            "query_id": query_id,
            "used_but_missing_columns": [
                f"{t}.{c}" for t, c in self.used_but_missing_columns
            ],
            "llm_prompt_tables": self.prompted_tables,
            "full_schema_version": self.full_schema_version,
            "bypass_score": self.bypass_score,
        }
