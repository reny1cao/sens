"""Types for SQL execution module."""

import json
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


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


class ExecutionMetrics(BaseModel):
    """Metrics for query execution."""
    
    execution_time: float = Field(..., description="Time taken to execute query in seconds")
    rows_returned: int = Field(..., description="Number of rows returned")
    data_source: Optional[str] = Field(None, description="Name of the data source")
    source_type: Optional[str] = Field(None, description="Type of data source")


class QueryResult(BaseModel):
    """Represents the result of a SQL query execution."""

    columns: List[str] = Field(..., description="List of column names in the result")
    rows: List[List[Any]] = Field(
        ..., description="List of rows containing the query results"
    )
    row_count: int = Field(..., description="Total number of rows in the result")
    error: Optional[str] = Field(
        None, description="Error message if query execution failed"
    )
    execution_time: Optional[float] = Field(None, description="Execution time in seconds")
    success: bool = Field(True, description="Whether the query succeeded")
    metrics: Optional[ExecutionMetrics] = Field(None, description="Execution metrics")

    def to_dict(self) -> Dict[str, Any]:
        """Convert the query result to a dictionary format with serialized values."""
        return {
            "columns": self.columns,
            "rows": [[serialize_value(val) for val in row] for row in self.rows],
            "row_count": self.row_count,
            "error": self.error,
        }

    def model_dump(self) -> Dict[str, Any]:
        """Convert the instance to a dictionary representation."""
        return self.to_dict()
