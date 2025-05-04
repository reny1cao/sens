import pytest

from sens.llm.intent_extractor import IntentExtractor
from sens.llm.models import QueryType


@pytest.fixture
def extractor():
    return IntentExtractor()


@pytest.fixture
def schema():
    return """
    TABLE movie(
        id INTEGER PRIMARY KEY,
        title TEXT,
        release_year INTEGER,
        director_id INTEGER REFERENCES person(id)
    )
    TABLE person(
        id INTEGER PRIMARY KEY,
        name TEXT,
        birth_year INTEGER
    )
    """


def test_aggregation_intent(extractor, schema):
    """Test extraction of aggregation intent."""
    intent = extractor.extract("How many movies were released in 2023?", schema)
    assert intent.query_type == QueryType.AGGREGATION
    assert "movie" in intent.tables
    assert "COUNT" in [op.upper() for op in intent.operations]
    assert any("2023" in cond for cond in intent.conditions)
    assert intent.confidence > 0.8


def test_lookup_intent(extractor, schema):
    """Test extraction of lookup intent."""
    intent = extractor.extract("List movies directed by Christopher Nolan", schema)
    assert intent.query_type == QueryType.LOOKUP
    assert set(intent.tables) == {"movie", "person"}
    assert any("Nolan" in cond for cond in intent.conditions)
    assert intent.confidence > 0.8


def test_relationship_intent(extractor, schema):
    """Test extraction of relationship intent."""
    intent = extractor.extract("Which directors have made more than 3 movies?", schema)
    assert intent.query_type == QueryType.RELATIONSHIP
    assert set(intent.tables) == {"movie", "person"}
    assert any("COUNT" in op.upper() for op in intent.operations)
    assert any("3" in cond for cond in intent.conditions)
    assert intent.confidence > 0.8


def test_invalid_table_handling(extractor, schema):
    """Test handling of queries referencing non-existent tables."""
    with pytest.raises(Exception):
        extractor.extract("List all books", schema)  # 'books' table does not exist


def test_missing_required_fields(extractor, schema):
    """Test handling of malformed LLM responses."""
    with pytest.raises(Exception):
        # Simulate LLM returning incomplete JSON
        extractor.extract("Invalid query that should fail", schema)
