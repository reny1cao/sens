"""Tests for SQL execution module."""

from unittest.mock import Mock, patch

import pytest

from sens.execution import QueryResult, SQLExecutor


@pytest.fixture
def mock_cursor():
    """Create a mock cursor with test data."""
    cursor = Mock()
    cursor.description = [
        ("id", None, None, None, None, None, None),
        ("name", None, None, None, None, None, None),
    ]
    cursor.fetchall.return_value = [(1, "test"), (2, "example")]
    return cursor


@pytest.fixture
def mock_connection(mock_cursor):
    """Create a mock connection with context manager support."""
    cursor_context = Mock()
    cursor_context.__enter__ = Mock(return_value=mock_cursor)
    cursor_context.__exit__ = Mock(return_value=None)

    conn = Mock()
    conn.cursor.return_value = cursor_context
    return conn


def test_successful_query_execution(mock_connection):
    """Test successful query execution with mock data."""
    with patch("psycopg2.connect", return_value=mock_connection):
        executor = SQLExecutor(db_url="mock://test")
        result = executor.execute("SELECT id, name FROM test")

        assert isinstance(result, QueryResult)
        assert result.columns == ["id", "name"]
        assert result.rows == [(1, "test"), (2, "example")]
        assert result.row_count == 2
        assert result.error is None


def test_failed_query_execution(mock_connection):
    """Test failed query execution with mock error."""
    mock_connection.cursor.return_value.__enter__.return_value.execute.side_effect = (
        Exception("Test error")
    )

    with patch("psycopg2.connect", return_value=mock_connection):
        executor = SQLExecutor(db_url="mock://test")
        result = executor.execute("SELECT invalid")

        assert isinstance(result, QueryResult)
        assert result.columns == []
        assert result.rows == []
        assert result.row_count == 0
        assert result.error == "Test error"


def test_connection_is_read_only():
    """Test that connection is created with read-only mode."""
    with patch("psycopg2.connect") as mock_connect:
        executor = SQLExecutor(db_url="mock://test")
        _ = executor.conn  # Access connection property

        mock_connect.assert_called_once_with(
            "mock://test", options="-c default_transaction_read_only=on"
        )
