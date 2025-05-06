"""Tests for the IntentValidator class."""

import pytest

from sens.llm.intent_validator import ClarificationRequest, IntentValidator, ValidIntent
from sens.llm.models import Intent, QueryType
from sens.schema.graph import SchemaGraph


# Mock the schema graph for testing
@pytest.fixture
def mock_schema(monkeypatch):
    """Create a mock schema with known tables for testing."""
    schema = SchemaGraph.get_instance()

    # Mock the list_all_tables method
    def mock_list_all_tables():
        return ["orders", "customers", "products"]

    monkeypatch.setattr(schema, "list_all_tables", mock_list_all_tables)

    # Mock the get_referenced_tables method
    def mock_get_referenced_tables(table):
        references = {
            "orders": {"customers"},
            "customers": {"orders"},
            "products": set(),
        }
        return references.get(table, set())

    monkeypatch.setattr(schema, "get_referenced_tables", mock_get_referenced_tables)

    return schema


@pytest.fixture
def validator():
    """Create an IntentValidator instance for testing."""
    return IntentValidator(confidence_threshold=0.75)


def create_intent(
    query_type: QueryType = QueryType.LOOKUP,
    tables: list[str] = None,
    operations: list[str] = None,
    conditions: list[str] = None,
    confidence: float = 0.9,
) -> Intent:
    """Helper to create Intent objects for testing."""
    return Intent(
        query_type=query_type,
        tables=tables or ["orders"],
        operations=operations or [],
        conditions=conditions or [],
        confidence=confidence,
    )


def test_validate_low_confidence(validator):
    """Test that low confidence triggers a ClarificationRequest."""
    intent = create_intent(confidence=0.6)
    result = validator.validate(intent)

    assert isinstance(result, ClarificationRequest)
    assert result.reason == "low_confidence"
    assert "confidence" in result.message.lower()


def test_validate_missing_tables(validator):
    """Test that empty tables list triggers a ClarificationRequest."""
    intent = create_intent(tables=[])
    result = validator.validate(intent)

    assert isinstance(result, ClarificationRequest)
    assert result.reason == "missing_tables"
    assert "tables" in result.missing_fields


def test_validate_invalid_tables(validator, mock_schema):
    """Test that invalid table names trigger a ClarificationRequest."""
    intent = create_intent(tables=["invalid_table"])
    result = validator.validate(intent)

    assert isinstance(result, ClarificationRequest)
    assert result.reason == "invalid_tables"
    assert "tables" in result.ambiguous_fields
    assert "invalid_table" in result.message


def test_validate_aggregation_missing_operations(validator):
    """Test that aggregation without operations triggers ClarificationRequest."""
    intent = create_intent(query_type=QueryType.AGGREGATION, operations=[])
    result = validator.validate(intent)

    assert isinstance(result, ClarificationRequest)
    assert result.reason == "missing_operations"
    assert "operations" in result.missing_fields


def test_validate_valid_lookup(validator, mock_schema):
    """Test that a valid lookup intent passes validation."""
    intent = create_intent(
        query_type=QueryType.LOOKUP, tables=["orders"], confidence=0.9
    )
    result = validator.validate(intent)

    assert isinstance(result, ValidIntent)
    assert result.original_intent == intent
    assert "table_relationships" in result.enhanced_metadata


def test_validate_valid_aggregation(validator, mock_schema):
    """Test that a valid aggregation intent passes validation."""
    intent = create_intent(
        query_type=QueryType.AGGREGATION,
        tables=["orders"],
        operations=["COUNT"],
        confidence=0.85,
    )
    result = validator.validate(intent)

    assert isinstance(result, ValidIntent)
    assert result.original_intent == intent


def test_enhanced_metadata_includes_relationships(validator, mock_schema):
    """Test that valid intents include relationship metadata."""
    intent = create_intent(tables=["orders"])
    result = validator.validate(intent)

    assert isinstance(result, ValidIntent)
    assert "table_relationships" in result.enhanced_metadata
    assert "orders" in result.enhanced_metadata["table_relationships"]
    assert (
        "referenced_tables" in result.enhanced_metadata["table_relationships"]["orders"]
    )


def test_multiple_invalid_conditions(validator, mock_schema):
    """Test handling multiple validation failures."""
    intent = create_intent(
        query_type=QueryType.AGGREGATION, tables=["invalid_table"], confidence=0.6
    )
    result = validator.validate(intent)

    # Should fail fast on the first validation error (low confidence)
    assert isinstance(result, ClarificationRequest)
    assert result.reason == "low_confidence"
