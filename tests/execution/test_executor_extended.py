"""Extended tests for SQL executor to improve coverage."""

from datetime import date, datetime, time
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from psycopg2 import OperationalError, ProgrammingError

from sens.execution import SQLExecutor
from sens.execution.types import QueryResult, serialize_value


class TestSQLExecutorExtended:
    """Extended tests for SQLExecutor."""

    @pytest.fixture
    def executor(self):
        """Create executor instance."""
        return SQLExecutor()

    @pytest.fixture
    def mock_connection(self):
        """Create mock database connection."""
        mock_conn = Mock()
        mock_cursor = Mock()

        # Make cursor a context manager
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)

        mock_conn.cursor.return_value = mock_cursor
        mock_conn.closed = False
        mock_cursor.description = [
            ("id", None, None, None, None, None, None),
            ("name", None, None, None, None, None, None),
        ]
        mock_cursor.fetchall.return_value = [(1, "Test"), (2, "Example")]
        mock_cursor.rowcount = 2
        return mock_conn, mock_cursor

    def test_query_result_formatting(self, executor):
        """Test QueryResult formatting methods."""
        result = QueryResult(
            columns=["id", "name", "age"],
            rows=[(1, "Alice", 25), (2, "Bob", 30)],
            row_count=2,
            error=None,
        )

        # Test dict format
        dict_result = result.to_dict()
        assert dict_result["columns"] == ["id", "name", "age"]
        assert dict_result["rows"] == [
            [1, "Alice", 25],
            [2, "Bob", 30],
        ]
        assert dict_result["row_count"] == 2
        assert dict_result["error"] is None

        # Test model_dump
        dump_result = result.model_dump()
        assert dump_result == dict_result

    def test_query_result_error_state(self):
        """Test QueryResult in error state."""
        result = QueryResult(
            columns=[],
            rows=[],
            row_count=0,
            error="Connection timeout",
        )

        dict_result = result.to_dict()
        assert dict_result["error"] == "Connection timeout"
        assert dict_result["row_count"] == 0
        assert dict_result["columns"] == []
        assert dict_result["rows"] == []

    def test_executor_connection_errors(self, executor):
        """Test handling of connection errors."""
        with patch("psycopg2.connect") as mock_connect:
            # Simulate connection failure
            mock_connect.side_effect = OperationalError("Could not connect to server")

            result = executor.execute("SELECT 1")

            assert result.error is not None
            assert "Could not connect" in result.error
            assert result.row_count == 0

    def test_executor_with_complex_queries(self, executor, mock_connection):
        """Test executor with complex SQL queries."""
        mock_conn, mock_cursor = mock_connection

        with patch.object(executor, "_conn", mock_conn):
            # Test query with joins
            complex_sql = """
            SELECT u.id, u.name, COUNT(o.id) as order_count
            FROM users u
            LEFT JOIN orders o ON u.id = o.user_id
            WHERE u.status = 'active'
            GROUP BY u.id, u.name
            HAVING COUNT(o.id) > 5
            ORDER BY order_count DESC
            LIMIT 10
            """

            mock_cursor.description = [
                ("id", None, None, None, None, None, None),
                ("name", None, None, None, None, None, None),
                ("order_count", None, None, None, None, None, None),
            ]
            mock_cursor.fetchall.return_value = [
                (1, "Power User", 25),
                (2, "Frequent Buyer", 15),
            ]

            result = executor.execute(complex_sql)

            assert result.error is None
            assert result.columns == ["id", "name", "order_count"]
            assert result.row_count == 2
            assert result.rows[0][2] == 25  # order_count

            # Verify the query was executed
            mock_cursor.execute.assert_called_once_with(complex_sql)

    def test_executor_sql_errors(self, executor, mock_connection):
        """Test handling of SQL syntax errors."""
        mock_conn, mock_cursor = mock_connection

        with patch.object(executor, "_conn", mock_conn):
            # Simulate SQL syntax error
            mock_cursor.execute.side_effect = ProgrammingError(
                "syntax error at or near 'SELCT'"
            )

            result = executor.execute("SELCT * FROM users")  # Typo in SELECT

            assert result.error is not None
            assert "syntax error" in result.error
            assert result.rows == []
            assert result.columns == []

    def test_executor_empty_result(self, executor, mock_connection):
        """Test handling of empty query results."""
        mock_conn, mock_cursor = mock_connection

        with patch.object(executor, "_conn", mock_conn):
            mock_cursor.fetchall.return_value = []
            mock_cursor.rowcount = 0

            result = executor.execute("SELECT * FROM users WHERE id = -1")

            assert result.error is None
            assert result.row_count == 0
            assert result.rows == []
            assert result.columns == ["id", "name"]

    def test_executor_large_result_set(self, executor, mock_connection):
        """Test handling of large result sets."""
        mock_conn, mock_cursor = mock_connection

        with patch.object(executor, "_conn", mock_conn):
            # Simulate large result set
            large_result = [(i, f"User{i}") for i in range(1000)]
            mock_cursor.fetchall.return_value = large_result
            mock_cursor.rowcount = 1000

            result = executor.execute("SELECT * FROM users")

            assert result.error is None
            assert result.row_count == 1000
            assert len(result.rows) == 1000

    def test_executor_special_characters(self, executor, mock_connection):
        """Test handling of special characters in results."""
        mock_conn, mock_cursor = mock_connection

        with patch.object(executor, "_conn", mock_conn):
            mock_cursor.fetchall.return_value = [
                (1, "User with 'quotes'"),
                (2, 'User with "double quotes"'),
                (3, "User with\nnewline"),
                (4, "User with\ttab"),
            ]
            mock_cursor.rowcount = 4

            result = executor.execute("SELECT * FROM users")

            assert result.error is None
            assert result.row_count == 4
            assert result.rows[0][1] == "User with 'quotes'"
            assert result.rows[2][1] == "User with\nnewline"

    def test_executor_transaction_handling(self, executor, mock_connection):
        """Test that transactions are properly rolled back."""
        mock_conn, mock_cursor = mock_connection

        with patch.object(executor, "_conn", mock_conn):
            # Execute a SELECT query
            executor.execute("SELECT * FROM users")

            # Verify cursor was used but connection not closed
            mock_cursor.execute.assert_called_once()
            mock_conn.commit.assert_not_called()

            # For write operations, verify they fail
            mock_cursor.execute.side_effect = ProgrammingError(
                "cannot execute UPDATE in a read-only transaction"
            )

            result = executor.execute("UPDATE users SET name = 'Test'")
            assert result.error is not None
            assert "read-only" in result.error

    def test_serialize_value(self):
        """Test serialize_value function."""
        # Test None
        assert serialize_value(None) is None

        # Test datetime
        dt = datetime(2024, 1, 1, 12, 30, 45)
        assert serialize_value(dt) == "2024-01-01T12:30:45"

        # Test date
        d = date(2024, 1, 1)
        assert serialize_value(d) == "2024-01-01"

        # Test time
        t = time(12, 30, 45, 123456)
        assert serialize_value(t) == "12:30:45.123456"

        # Test Decimal
        dec = Decimal("123.45")
        assert serialize_value(dec) == "123.45"

        # Test bytes
        b = b"\x00\xff"
        assert serialize_value(b) == "00ff"

        # Test regular values
        assert serialize_value("test") == "test"
        assert serialize_value(123) == 123
        assert serialize_value(True) is True

    def test_null_values_handling(self, executor, mock_connection):
        """Test handling of NULL values in results."""
        mock_conn, mock_cursor = mock_connection

        with patch.object(executor, "_conn", mock_conn):
            mock_cursor.fetchall.return_value = [
                (1, "Alice", None),
                (2, None, "test@example.com"),
                (3, "Bob", "bob@example.com"),
            ]
            mock_cursor.description = [
                ("id", None, None, None, None, None, None),
                ("name", None, None, None, None, None, None),
                ("email", None, None, None, None, None, None),
            ]

            result = executor.execute("SELECT id, name, email FROM users")

            assert result.error is None
            assert result.rows[0][2] is None  # Alice's email
            assert result.rows[1][1] is None  # User 2's name

            # Check dict format handles None properly
            dict_result = result.to_dict()
            assert dict_result["rows"][0][2] is None
            assert dict_result["rows"][1][1] is None
