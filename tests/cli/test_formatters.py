"""Tests for CLI response formatters."""

import json
from datetime import datetime

import pytest

from sens.cli.formatters import (
    _format_json_response,
    _format_summary_response,
    _format_table_response,
    format_nl2sql_response,
)


@pytest.fixture
def sample_success_response():
    """Create a sample successful response."""
    return {
        "status": "success",
        "summary": "Found 2 users with orders.",
        "sql": "SELECT * FROM users",
        "result": {
            "preview": [(1, "Alice"), (2, "Bob")],
            "columns": ["id", "name"],
            "row_count": 2,
        },
        "metadata": {
            "tables_used": ["users"],
            "columns_used": {"users": ["id", "name"]},
            "model_used": "gpt-4",
            "generation_ms": 1000,
            "execution_ms": 50,
            "intent_type": "lookup",
            "generated_at": datetime.utcnow().isoformat(),
        },
    }


@pytest.fixture
def sample_error_response():
    """Create a sample error response."""
    return {
        "status": "error",
        "message": "Failed to execute query",
    }


@pytest.fixture
def sample_clarification_response():
    """Create a sample clarification response."""
    return {
        "status": "clarification_needed",
        "message": "Please specify which user",
        "reason": "ambiguous_intent",
    }


def test_json_format(sample_success_response):
    """Test JSON formatting of successful response."""
    # Test with preview
    formatted = _format_json_response(sample_success_response, pretty=True)
    parsed = json.loads(formatted)
    assert parsed["status"] == "success"
    assert "preview" in parsed["result"]

    # Test without preview
    formatted = _format_json_response(sample_success_response, show_preview=False)
    parsed = json.loads(formatted)
    assert "preview" not in parsed["result"]
    assert parsed["result"]["preview_hidden"] is True


def test_table_format(sample_success_response):
    """Test table formatting of successful response."""
    formatted = _format_table_response(sample_success_response)

    # Check key components
    assert "Summary: Found 2 users with orders" in formatted
    assert "SQL: SELECT * FROM users" in formatted
    assert "Results:" in formatted
    assert "Metadata:" in formatted
    assert "Intent Type: lookup" in formatted
    assert "Tables Used: users" in formatted


def test_summary_format(
    sample_success_response, sample_error_response, sample_clarification_response
):
    """Test summary-only formatting."""
    # Test success case
    formatted = _format_summary_response(sample_success_response)
    assert formatted == "Found 2 users with orders"

    # Test error case
    formatted = _format_summary_response(sample_error_response)
    assert formatted == "Error: Failed to execute query"

    # Test clarification case
    formatted = _format_summary_response(sample_clarification_response)
    assert formatted == "Clarification needed: Please specify which user"


def test_format_nl2sql_response_error_handling(
    sample_error_response, sample_clarification_response
):
    """Test error and clarification handling in main formatter."""
    # Test error response
    formatted = format_nl2sql_response(sample_error_response)
    assert formatted == "Error: Failed to execute query"

    # Test clarification response
    formatted = format_nl2sql_response(sample_clarification_response)
    assert formatted == "Clarification needed: Please specify which user"


def test_format_nl2sql_response_formats(sample_success_response):
    """Test different output formats."""
    # Test JSON format
    json_output = format_nl2sql_response(sample_success_response, format="json")
    assert json.loads(json_output)["status"] == "success"

    # Test table format
    table_output = format_nl2sql_response(sample_success_response, format="table")
    assert "Summary:" in table_output
    assert "Results:" in table_output

    # Test summary format
    summary_output = format_nl2sql_response(sample_success_response, format="summary")
    assert summary_output == "Found 2 users with orders"

    # Test invalid format
    with pytest.raises(ValueError, match="Unknown format"):
        format_nl2sql_response(sample_success_response, format="invalid")
