"""SQL execution module for safe, read-only query processing."""

import logging
from typing import Optional

import psycopg2
from psycopg2.extensions import connection as pg_connection

from sens.execution.types import QueryResult
from sens.settings import get_settings

logger = logging.getLogger(__name__)


class SQLExecutor:
    """Executes SQL queries in a safe, read-only mode."""

    def __init__(self, db_url: Optional[str] = None):
        """Initialize the executor with database connection.

        Args:
            db_url: Optional database URL. If not provided, uses settings.
        """
        settings = get_settings()
        self.db_url = db_url or settings.db_url
        self._conn: Optional[pg_connection] = None

    @property
    def conn(self) -> pg_connection:
        """Lazy connection initialization with read-only mode enforced."""
        if self._conn is None or self._conn.closed:
            try:
                self._conn = psycopg2.connect(
                    self.db_url, options="-c default_transaction_read_only=on"
                )
            except Exception as e:
                logger.error(f"Failed to connect to database: {str(e)}")
                raise
        return self._conn

    def execute(self, sql: str) -> QueryResult:
        """Execute a SQL query and return structured results.

        Args:
            sql: The SQL query to execute

        Returns:
            QueryResult containing columns, rows, and metadata
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall()
                columns = [desc[0] for desc in cur.description]
                return QueryResult(columns=columns, rows=rows, row_count=len(rows))
        except Exception as e:
            logger.error(f"Query execution failed: {str(e)}")
            return QueryResult(columns=[], rows=[], row_count=0, error=str(e))

    def execute_with_params(self, sql: str, params: tuple) -> QueryResult:
        """Execute a SQL query with parameters.

        Args:
            sql: The SQL query with placeholders
            params: Parameters to substitute

        Returns:
            QueryResult containing columns, rows, and metadata
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
                columns = (
                    [desc[0] for desc in cur.description] if cur.description else []
                )
                return QueryResult(columns=columns, rows=rows, row_count=len(rows))
        except Exception as e:
            logger.error(f"Query execution failed: {str(e)}")
            return QueryResult(columns=[], rows=[], row_count=0, error=str(e))

    def close(self) -> None:
        """Close the database connection if open."""
        if self._conn and not self._conn.closed:
            self._conn.close()
            self._conn = None
