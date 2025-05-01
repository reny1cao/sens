"""Tests for the embedding search API routes."""

from fastapi.testclient import TestClient

from sens.api import app

client = TestClient(app)


def test_search_columns():
    """Test the column search endpoint."""
    # Test basic search
    response = client.get("/embedding/search", params={"query": "rating"})
    assert response.status_code == 200
    results = response.json()
    assert isinstance(results, list)
    assert len(results) == 20  # Default k

    # Verify result schema
    first_result = results[0]
    assert "table" in first_result
    assert "column" in first_result
    assert "score" in first_result
    assert isinstance(first_result["score"], float)

    # Test custom k
    response = client.get("/embedding/search", params={"query": "rating", "k": 5})
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 5

    # Test invalid k
    response = client.get("/embedding/search", params={"query": "rating", "k": 0})
    assert response.status_code == 422  # Validation error

    response = client.get("/embedding/search", params={"query": "rating", "k": 101})
    assert response.status_code == 422  # Validation error

    # Test missing query
    response = client.get("/embedding/search")
    assert response.status_code == 422  # Validation error
