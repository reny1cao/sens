from dataclasses import dataclass
from typing import Any, List, Optional


@dataclass
class QueryResult:
    """Represents the result of a SQL query execution."""

    columns: List[str]
    rows: List[List[Any]]
    row_count: int
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert the query result to a dictionary format."""
        return {
            "columns": self.columns,
            "rows": self.rows,
            "row_count": self.row_count,
            "error": self.error,
        }
