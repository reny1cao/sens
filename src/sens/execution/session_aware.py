"""
Session-aware query executor.
"""

from typing import Any, Dict, Optional

from ..interfaces import ExecutionContext, ExecutionResult, QueryExecutor


class SessionAwareExecutor(QueryExecutor):
    """Executes queries with session context."""

    def __init__(self, **kwargs):
        self.config = kwargs

    async def execute(
        self, sql: str, context: ExecutionContext, **kwargs
    ) -> ExecutionResult:
        """Execute SQL with session awareness."""
        # For now, return a mock result
        # TODO: Implement actual session-aware execution
        return ExecutionResult(
            success=True,
            rows=[],
            columns=[],
            row_count=0,
            execution_time_ms=5.0,
            metadata={"executor": "session_aware"},
        )

    async def test_connection(self, datasource_id: Optional[str] = None) -> bool:
        """Test connection."""
        return True

    async def get_datasource_info(
        self, datasource_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get datasource info."""
        return {"type": "session", "status": "connected"}
