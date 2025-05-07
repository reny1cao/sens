"""SQL execution module for safe, read-only query processing."""

from sens.execution.executor import SQLExecutor
from sens.execution.types import QueryResult

__all__ = ["SQLExecutor", "QueryResult"]
