"""Tests for the column search API endpoint."""

import pytest
from fastapi.testclient import TestClient

from sens.api.app_unified import app

client = TestClient(app)


@patch("src.sens.api.routers.column_search.router.top_columns")
def test_column_search_success(mock_top_columns):
    """Test successful column search."""
    # Configure the mock
    mock_top_columns.return_value = [
        ("table1", "columnA", 0.9),
        ("table2", "columnB", 0.8),
    ]

    response = client.get("/column-search/search?query=find%20me&limit=5")

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "find me"
    assert data["limit"] == 5
    assert len(data["results"]) == 2
    assert data["results"][0]["table"] == "table1"
    assert data["results"][0]["column"] == "columnA"
    assert data["results"][0]["score"] == 0.9
    assert data["execution_time_ms"] > 0

    # Verify mock was called correctly
    mock_top_columns.assert_called_once_with(query="find me", k=5)


@patch("src.sens.api.routers.column_search.router.top_columns")
def test_column_search_index_not_found(mock_top_columns):
    """Test column search when the index file is not found."""
    # Configure the mock to raise FileNotFoundError
    mock_top_columns.side_effect = FileNotFoundError("Index file missing")

    response = client.get("/column-search/search?query=index%20missing")

    assert response.status_code == 503
    assert "Embedding index not loaded" in response.json()["detail"]
    mock_top_columns.assert_called_once_with(
        query="index missing", k=20
    )  # Default limit


@patch("src.sens.api.routers.column_search.router.top_columns")
def test_column_search_generic_error(mock_top_columns):
    """Test column search with an unexpected internal error."""
    # Configure the mock to raise a generic Exception
    mock_top_columns.side_effect = Exception("Something broke")

    response = client.get("/column-search/search?query=internal%20error")

    assert response.status_code == 500
    assert "Internal server error" in response.json()["detail"]
    assert "Something broke" in response.json()["detail"]
    mock_top_columns.assert_called_once_with(query="internal error", k=20)


def test_column_search_invalid_limit():
    """Test providing an invalid limit parameter."""
    response_zero = client.get("/column-search/search?query=test&limit=0")
    assert response_zero.status_code == 422  # Unprocessable Entity

    response_high = client.get("/column-search/search?query=test&limit=101")
    assert response_high.status_code == 422
