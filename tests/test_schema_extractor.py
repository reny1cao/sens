"""Tests for schema extractor functionality."""

from pathlib import Path

import pytest

from sens.schema import DatabaseSchema, SchemaExtractor


def test_schema_extraction(schema_extractor):
    """Test basic schema extraction."""
    schema = schema_extractor.extract_and_save()

    # Basic validation
    assert isinstance(schema, DatabaseSchema)
    assert len(schema.tables) > 0
    assert len(schema.relationships) > 0
    assert "metadata" in schema.model_dump()

    # Check if files were created
    assert Path("config/schema_metadata.json").exists()
    assert Path("config/schema_for_llm.txt").exists()


def test_table_structure(schema_extractor):
    """Test extracted table structure."""
    schema = schema_extractor.extract_and_save()

    # Check movie table
    assert "movie" in schema.tables
    movie = schema.tables["movie"]
    assert "id" in [col.name for col in movie.columns]
    assert "title" in [col.name for col in movie.columns]
    assert "runtime" in [col.name for col in movie.columns]

    # Check primary keys
    assert "id" in movie.primary_keys


def test_relationships(schema_extractor):
    """Test relationship extraction."""
    schema = schema_extractor.extract_and_save()

    # Check view_summary -> movie relationship
    view_to_movie = any(
        rel["from_table"] == "view_summary"
        and rel["to_table"] == "movie"
        and rel["from_column"] == "movie_id"
        and rel["to_column"] == "id"
        for rel in schema.relationships
    )
    assert view_to_movie, "View summary to movie relationship not found"


def test_llm_formatting(schema_extractor):
    """Test LLM-friendly schema formatting."""
    schema = schema_extractor.extract_and_save()

    # Test full schema format
    full_format = schema_extractor.format_for_llm(schema)
    assert "Database Schema:" in full_format
    assert "Table movie" in full_format
    assert "Table tv_show" in full_format

    # Test filtered schema format
    movie_format = schema_extractor.format_for_llm(schema, tables={"movie"})
    assert "Table movie" in movie_format
    assert "tv_show" not in movie_format
    assert "id: bigint (primary key)" in movie_format.lower()


def test_error_handling():
    """Test error handling with invalid connection."""
    with pytest.raises(Exception):
        extractor = SchemaExtractor(db_url="postgresql://invalid/db")
        extractor.extract_and_save()


def test_mock_schema_formatting(schema_extractor, mock_schema_data):
    """Test schema formatting with mock data."""
    schema = DatabaseSchema(**mock_schema_data)
    formatted = schema_extractor.format_for_llm(schema)

    # Verify mock schema format
    assert "Table movie" in formatted
    assert "Table view_summary" in formatted
    assert "movie_id: bigint" in formatted
    assert "→ movie via movie_id" in formatted


@pytest.mark.parametrize(
    "tables,expected",
    [
        ({"movie"}, {"movie"}),
        ({"view_summary"}, {"view_summary"}),
        ({"movie", "view_summary"}, {"movie", "view_summary"}),
    ],
)
def test_table_filtering(schema_extractor, mock_schema_data, tables, expected):
    """Test table filtering in schema formatting."""
    schema = DatabaseSchema(**mock_schema_data)
    formatted = schema_extractor.format_for_llm(schema, tables=tables)

    # Check that only expected tables are included
    for table in expected:
        assert f"Table {table}" in formatted

    # Check that other tables are excluded
    all_tables = set(mock_schema_data["tables"].keys())
    for table in all_tables - expected:
        assert f"Table {table}" not in formatted
