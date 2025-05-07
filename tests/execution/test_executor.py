from unittest.mock import Mock, patch

import pytest

from sens.execution import QueryResult, SQLExecutor


@pytest.fixture
def mock_cursor():
    cursor = Mock()
    cursor.description = [
        ("id", None, None, None, None, None, None),
        ("name", None, None, None, None, None, None),
    ]
    cursor.fetchall.return_value = [(1, "test"), (2, "example")]
    return cursor


@pytest.fixture
def mock_connection(mock_cursor):
    conn = Mock()
    conn.cursor.return_value.__enter__.return_value = mock_cursor
    return conn


def test_successful_query_execution(mock_connection):
    with patch("psycopg2.connect", return_value=mock_connection):
        executor = SQLExecutor(db_url="mock://test")
        result = executor.execute("SELECT id, name FROM test")

        assert isinstance(result, QueryResult)
        assert result.columns == ["id", "name"]
        assert result.rows == [(1, "test"), (2, "example")]
        assert result.row_count == 2
        assert result.error is None


def test_failed_query_execution(mock_connection):
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
    with patch("psycopg2.connect") as mock_connect:
        executor = SQLExecutor(db_url="mock://test")
        _ = executor.conn  # Access connection property

        mock_connect.assert_called_once_with(
            "mock://test", options="-c default_transaction_read_only=on"
        )
