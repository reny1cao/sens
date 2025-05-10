from dataclasses import dataclass
from typing import Optional


@dataclass
class ColumnReference:
    """Represents a column reference in a SQL query."""

    table: Optional[str]  # Table name, None if unqualified
    column: str  # Column name


@dataclass
class JoinCondition:
    """Represents a JOIN condition between two tables."""

    left_table: str
    right_table: str
    left_column: str
    right_column: str
