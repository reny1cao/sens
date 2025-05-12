"""Tests for schema retrieval functionality."""

import pytest

from sens.retrieval.schema_retriever import SchemaRetriever
from sens.schema.graph import SchemaGraph


def test_schema_retriever_sticky_columns(schema_graph):
    """Test that schema retriever correctly identifies and includes sticky columns."""
    retriever = SchemaRetriever(schema_graph)

    # Test with a movie-related query
    context = retriever.retrieve_schema_context(
        "Show me movie titles and their release dates", top_k=3
    )

    # Verify sticky columns are present
    assert "movies" in context.sticky_columns
    assert "title" in context.sticky_columns["movies"]

    # Test with a user-related query
    context = retriever.retrieve_schema_context(
        "Find users and their profile information", top_k=3
    )

    # Verify sticky columns are present
    assert "users" in context.sticky_columns
    assert any(
        col in context.sticky_columns["users"]
        for col in ["name", "username", "display_name"]
    )


def test_schema_context_formatting(schema_graph):
    """Test that schema context correctly formats sticky columns for LLM consumption."""
    retriever = SchemaRetriever(schema_graph)

    context = retriever.retrieve_schema_context("Show movie information", top_k=2)

    formatted = context.format_for_llm()

    # Check that sticky columns are included in the formatted output
    assert "Primary identifiers:" in formatted
    for table in context.sticky_columns:
        for col in context.sticky_columns[table]:
            assert col in formatted


def test_sticky_columns_with_foreign_keys(schema_graph):
    """Test that sticky columns work correctly with foreign key relationships."""
    retriever = SchemaRetriever(schema_graph)

    # Query that should involve joined tables
    context = retriever.retrieve_schema_context("Show movies and their genres", top_k=3)

    # Verify sticky columns for both tables
    assert "movies" in context.sticky_columns
    assert "genres" in context.sticky_columns

    # Movie title should be sticky
    assert "title" in context.sticky_columns["movies"]

    # Genre name should be sticky
    assert "name" in context.sticky_columns["genres"]

    # Foreign key columns should not be sticky
    assert "genre_id" not in context.sticky_columns["movies"]


def test_sticky_columns_priority(schema_graph):
    """Test that sticky columns are prioritized correctly."""
    retriever = SchemaRetriever(schema_graph)

    context = retriever.retrieve_schema_context("List all movies", top_k=2)

    # Check movies table
    assert "movies" in context.sticky_columns
    movie_sticky = context.sticky_columns["movies"]

    # Title should be first (highest priority)
    assert movie_sticky[0] == "title"

    # System columns should not be sticky
    assert "created_at" not in movie_sticky
    assert "updated_at" not in movie_sticky

    # Technical IDs should not be sticky
    assert "id" not in movie_sticky
