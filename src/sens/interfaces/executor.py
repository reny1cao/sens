"""
Standard interface for query execution components.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ExecutionContext:
    """Context for query execution."""

    datasource_id: Optional[str] = None
    session_id: Optional[str] = None
    timeout_seconds: Optional[int] = None
    max_rows: Optional[int] = None
    dry_run: bool = False


@dataclass
class ExecutionResult:
    """Result from query execution."""

    success: bool
    rows: List[Dict[str, Any]]
    columns: List[str]
    row_count: int
    execution_time_ms: float
    error: Optional[str] = None
    warnings: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class QueryExecutor(ABC):
    """
    Abstract base class for query execution implementations.

    Executors handle the actual database interaction, including
    connection management, query execution, and result formatting.
    """

    @abstractmethod
    async def execute(
        self, sql: str, context: ExecutionContext, **kwargs
    ) -> ExecutionResult:
        """
        Execute SQL query with the given context.

        Args:
            sql: SQL query to execute
            context: Execution context with datasource and options
            **kwargs: Additional executor-specific parameters

        Returns:
            ExecutionResult with data or error information
        """
        pass

    @abstractmethod
    async def test_connection(self, datasource_id: Optional[str] = None) -> bool:
        """Test if connection to datasource is working."""
        pass

    @abstractmethod
    async def get_datasource_info(
        self, datasource_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get information about the datasource."""
        pass
