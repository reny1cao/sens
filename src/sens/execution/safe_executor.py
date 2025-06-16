"""Safe SQL executor with proper transaction handling."""

import logging
from typing import Optional

import psycopg2
from psycopg2.extensions import connection as pg_connection

from sens.execution.types import QueryResult
from sens.settings import get_settings

logger = logging.getLogger(__name__)


class SafeSQLExecutor:
    """Executes SQL queries with proper transaction handling and automatic rollback."""

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
                # Set autocommit to True to avoid transaction issues
                self._conn.autocommit = True
            except Exception as e:
                logger.error(f"Failed to connect to database: {str(e)}")
                raise
        return self._conn

    def execute(self, sql: str) -> QueryResult:
        """Execute a SQL query with automatic transaction handling.

        Args:
            sql: The SQL query to execute

        Returns:
            QueryResult containing columns, rows, and metadata
        """
        conn = None
        cur = None
        try:
            # Get connection
            conn = self.conn

            # Create cursor for this specific query
            cur = conn.cursor()

            # Execute query
            cur.execute(sql)

            # Fetch results
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description] if cur.description else []

            return QueryResult(columns=columns, rows=rows, row_count=len(rows))

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Query execution failed: {error_msg}")

            # If transaction is aborted, we need to rollback
            if "current transaction is aborted" in error_msg:
                try:
                    if conn and not conn.closed and not conn.autocommit:
                        conn.rollback()
                        logger.info("Rolled back aborted transaction")
                except Exception as rollback_error:
                    logger.error(f"Rollback failed: {str(rollback_error)}")

            return QueryResult(columns=[], rows=[], row_count=0, error=error_msg)

        finally:
            # Always close cursor
            if cur:
                try:
                    cur.close()
                except Exception:
                    pass

    def execute_with_params(self, sql: str, params: tuple) -> QueryResult:
        """Execute a SQL query with parameters and automatic transaction handling.

        Args:
            sql: The SQL query with placeholders
            params: Parameters to substitute

        Returns:
            QueryResult containing columns, rows, and metadata
        """
        conn = None
        cur = None
        try:
            # Get connection
            conn = self.conn

            # Create cursor for this specific query
            cur = conn.cursor()

            # Execute query with parameters
            cur.execute(sql, params)

            # Fetch results
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description] if cur.description else []

            return QueryResult(columns=columns, rows=rows, row_count=len(rows))

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Query execution failed: {error_msg}")

            # If transaction is aborted, we need to rollback
            if "current transaction is aborted" in error_msg:
                try:
                    if conn and not conn.closed and not conn.autocommit:
                        conn.rollback()
                        logger.info("Rolled back aborted transaction")
                except Exception as rollback_error:
                    logger.error(f"Rollback failed: {str(rollback_error)}")

            return QueryResult(columns=[], rows=[], row_count=0, error=error_msg)

        finally:
            # Always close cursor
            if cur:
                try:
                    cur.close()
                except Exception:
                    pass

    def close(self) -> None:
        """Close the database connection if open."""
        if self._conn and not self._conn.closed:
            try:
                self._conn.close()
            except Exception as e:
                logger.error(f"Error closing connection: {str(e)}")
            finally:
                self._conn = None
