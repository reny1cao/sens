"""Tests for SQL validation CLI command."""

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from sens.cli.main import handle_validate
from sens.schema.context import ValidatorSchemaContext
from sens.schema.graph import SchemaGraph


@pytest.fixture
def mock_schema_graph():
    """Create a mock schema graph."""
    mock = Mock(spec=SchemaGraph)
    mock.list_all_tables.return_value = ["users", "orders", "products"]
    mock.get_table_columns.side_effect = lambda table: {
        "users": ["id", "name", "email", "created_at"],
        "orders": ["id", "user_id", "total", "status", "created_at"],
        "products": ["id", "name", "price", "description"],
    }[table]
    mock._schema_data.metadata = {"version": "v1.2.3"}
    return mock


@pytest.fixture
def prompted_schema_file(tmp_path):
    """Create a temporary prompted schema file."""
    schema_data = {
        "tables": ["users", "orders"],
        "columns_per_table": {
            "users": ["id", "name"],
            "orders": ["id", "user_id", "total"],
        },
    }
    schema_file = tmp_path / "prompted_schema.json"
    schema_file.write_text(json.dumps(schema_data))
    return schema_file


@pytest.fixture
def sql_file(tmp_path):
    """Create a temporary SQL file."""
    sql = """
    SELECT u.email, u.name, o.status, o.total
    FROM users u
    JOIN orders o ON u.id = o.user_id
    WHERE u.created_at > '2024-01-01'
    """
    sql_file = tmp_path / "query.sql"
    sql_file.write_text(sql)
    return sql_file


def test_validation_with_context_bypass(
    mock_schema_graph, prompted_schema_file, sql_file, capsys
):
    """Test validation command with context bypass detection."""
    with patch("sens.cli.main.SchemaGraph") as mock_schema_class:
        mock_schema_class.get_instance.return_value = mock_schema_graph

        args = Mock(
            sql=None,
            file=sql_file,
            syntax=True,
            schema=True,
            safety=True,
            allow=None,
            allow_unfiltered=False,
            prompted_schema=prompted_schema_file,
        )

        with pytest.raises(SystemExit) as exc_info:
            handle_validate(args)

        assert exc_info.value.code == 0  # Valid against full schema

        captured = capsys.readouterr()
        output = captured.out

        # Check for bypass information in output
        assert "Context Bypass Analysis:" in output
        assert "Score:" in output
        assert "users.email" in output
        assert "users.created_at" in output
        assert "orders.status" in output


def test_validation_without_context_bypass(mock_schema_graph, sql_file, capsys):
    """Test validation command without prompted schema."""
    with patch("sens.cli.main.SchemaGraph") as mock_schema_class:
        mock_schema_class.get_instance.return_value = mock_schema_graph

        args = Mock(
            sql=None,
            file=sql_file,
            syntax=True,
            schema=True,
            safety=True,
            allow=None,
            allow_unfiltered=False,
            prompted_schema=None,  # No prompted schema
        )

        with pytest.raises(SystemExit) as exc_info:
            handle_validate(args)

        assert exc_info.value.code == 0  # Valid against full schema

        captured = capsys.readouterr()
        output = captured.out

        # Should not show bypass information
        assert "Context Bypass Analysis:" not in output


def test_validation_with_invalid_sql(
    mock_schema_graph, prompted_schema_file, tmp_path, capsys
):
    """Test validation command with invalid SQL."""
    # Create SQL file with invalid query
    sql = """
    SELECT u.name, o.invalid_column
    FROM users u
    JOIN orders o ON u.id = o.user_id
    """
    sql_file = tmp_path / "invalid_query.sql"
    sql_file.write_text(sql)

    with patch("sens.cli.main.SchemaGraph") as mock_schema_class:
        mock_schema_class.get_instance.return_value = mock_schema_graph

        args = Mock(
            sql=None,
            file=sql_file,
            syntax=True,
            schema=True,
            safety=True,
            allow=None,
            allow_unfiltered=False,
            prompted_schema=prompted_schema_file,
        )

        with pytest.raises(SystemExit) as exc_info:
            handle_validate(args)

        assert exc_info.value.code == 1  # Invalid SQL

        captured = capsys.readouterr()
        output = captured.out

        # Should show validation error
        assert "INVALID" in output
        assert "invalid_column" in output
