"""Tests for the intent extraction router."""

import pytest
from fastapi.testclient import TestClient

from sens.api.app_unified import app
from sens.api.models.intent import IntentRequest, SchemaSnippet

client = TestClient(app)


def test_sample_request():
    """Test the sample request endpoint."""
    response = client.get("/intent/sample")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data["query"], str)
    assert len(data["schema_snippets"]) == 2
    assert data["schema_snippets"][0]["table_name"] == "orders"
    assert data["schema_snippets"][1]["table_name"] == "customers"


def test_extract_intent_with_sample():
    """Test intent extraction using the sample request."""
    # First get the sample request
    sample = client.get("/intent/sample").json()

    # Use it to make an extraction request
    response = client.post("/intent/extract", json=sample)
    assert response.status_code == 200

    data = response.json()
    assert "intent" in data
    assert "confidence" in data
    assert isinstance(data["confidence"], float)
    assert 0 <= data["confidence"] <= 1
    assert "relevant_tables" in data
    assert isinstance(data["relevant_tables"], list)


def test_extract_intent_validation():
    """Test input validation for intent extraction."""
    # Test with empty query
    bad_request = {"query": "", "schema_snippets": []}
    response = client.post("/intent/extract", json=bad_request)
    assert response.status_code == 400


def test_extract_intent_with_custom_schema():
    """Test intent extraction with a custom schema."""
    request = IntentRequest(
        query="How many customers joined this year?",
        schema_snippets=[
            SchemaSnippet(
                table_name="customers",
                columns=["customer_id", "name", "join_date"],
                description="Customer information",
            )
        ],
    )

    response = client.post("/intent/extract", json=request.model_dump())
    assert response.status_code == 200

    data = response.json()
    assert "customers" in data["relevant_tables"]
