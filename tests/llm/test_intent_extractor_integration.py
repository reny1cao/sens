"""Integration tests for the IntentExtractor class using real OpenRouter API."""

import os

import pytest

from sens.llm.intent_extractor import IntentExtractor
from sens.llm.models import QueryType

# Skip all tests in this module if no API key
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        "OPENROUTER_API_KEY" not in os.environ,
        reason="Integration tests require OPENROUTER_API_KEY",
    ),
]


@pytest.fixture
def real_extractor():
    """Create a real IntentExtractor instance."""
    if "OPENROUTER_API_KEY" not in os.environ:
        pytest.skip("OPENROUTER_API_KEY not set")
    return IntentExtractor()


@pytest.fixture
def sample_schema():
    """Real-world schema example."""
    return """
    TABLE orders(
        id INTEGER PRIMARY KEY,
        customer_id INTEGER REFERENCES customers(id),
        order_date DATE,
        total_amount DECIMAL
    )
    TABLE customers(
        id INTEGER PRIMARY KEY,
        name TEXT,
        email TEXT,
        created_at TIMESTAMP
    )
    """


def test_real_aggregation_query(real_extractor, sample_schema):
    """Test aggregation query with real API."""
    question = "What is the total amount of orders per customer?"
    intent = real_extractor.extract(question, sample_schema)

    assert intent.query_type == QueryType.AGGREGATION
    assert set(intent.tables) >= {"orders", "customers"}
    assert any(op.upper() in ["SUM", "COUNT"] for op in intent.operations)
    assert intent.confidence > 0.7


def test_real_lookup_query(real_extractor, sample_schema):
    """Test lookup query with real API."""
    question = "Find the customer with ID 123"
    intent = real_extractor.extract(question, sample_schema)

    assert intent.query_type == QueryType.LOOKUP
    assert "customers" in intent.tables
    assert not intent.operations  # Should be empty for lookup
    assert intent.confidence > 0.7


def test_real_relationship_query(real_extractor, sample_schema):
    """Test relationship query with real API."""
    question = "Show me all orders for customer 'John Doe'"
    intent = real_extractor.extract(question, sample_schema)

    assert intent.query_type == QueryType.RELATIONSHIP
    assert set(intent.tables) >= {"orders", "customers"}
    assert intent.confidence > 0.7


@pytest.mark.timeout(10)
def test_api_timeout(real_extractor, sample_schema):
    """Test API call completes within reasonable time."""
    question = "What is the average order amount?"
    intent = real_extractor.extract(question, sample_schema)
    assert intent is not None


def test_invalid_schema_handling(real_extractor):
    """Test handling of invalid schema."""
    invalid_schema = "INVALID SCHEMA FORMAT"
    question = "What are the total orders?"

    with pytest.raises(ValueError):
        real_extractor.extract(question, invalid_schema)


def test_complex_query(real_extractor, sample_schema):
    """Test handling of complex multi-table query."""
    question = "What is the average order amount for customers who joined in 2023?"
    intent = real_extractor.extract(question, sample_schema)

    assert intent.query_type == QueryType.AGGREGATION
    assert set(intent.tables) >= {"orders", "customers"}
    assert any(op.upper() in ["AVG", "MEAN"] for op in intent.operations)
    assert intent.confidence > 0.7


def test_ambiguous_query(real_extractor, sample_schema):
    """Test handling of potentially ambiguous queries."""
    question = "Show me customer orders"
    intent = real_extractor.extract(question, sample_schema)

    # Should still give a reasonable interpretation
    assert intent.query_type in [QueryType.RELATIONSHIP, QueryType.LOOKUP]
    assert set(intent.tables) >= {"orders", "customers"}
    assert intent.confidence > 0.5  # Might be lower confidence due to ambiguity


def test_error_handling(real_extractor, sample_schema):
    """Test proper error handling with empty or invalid inputs."""
    # Test with empty question
    with pytest.raises(ValueError):
        real_extractor.extract("", sample_schema)

    # Test with empty schema
    with pytest.raises(ValueError):
        real_extractor.extract("Show all orders", "")
