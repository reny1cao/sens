"""Types for SQL execution module."""

import json
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, List, Optional


def serialize_value(value: Any) -> Any:
    """Serialize special database types to JSON-compatible format.

    Args:
        value: The value to serialize

    Returns:
        JSON-serializable value
    """
    if value is None:
        return None
    elif isinstance(value, (datetime, date)):
        return value.isoformat()
    elif isinstance(value, time):
        return value.strftime("%H:%M:%S.%f")
    elif isinstance(value, Decimal):
        return str(value)
    elif isinstance(value, bytes):
        return value.hex()
    return value


@dataclass
class QueryResult:
    """Represents the result of a SQL query execution."""

    columns: List[str]
    rows: List[List[Any]]
    row_count: int
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert the query result to a dictionary format with serialized values."""
        return {
            "columns": self.columns,
            "rows": [[serialize_value(val) for val in row] for row in self.rows],
            "row_count": self.row_count,
            "error": self.error,
        }
