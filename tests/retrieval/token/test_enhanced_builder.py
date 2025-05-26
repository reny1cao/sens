"""Tests for the enhanced token index implementation."""

import pytest

from sens.retrieval.token.enhanced_builder import EnhancedTokenIndexBuilder
from sens.retrieval.token.enhanced_models import SchemaItem, TokenMatch


@pytest.fixture
def sample_schema_items():
    """Create a sample set of schema items for testing."""
    return [
        SchemaItem(name="user", item_type="table"),
        SchemaItem(name="post", item_type="table"),
        SchemaItem(
            name="user_id",
            item_type="column",
            parent_table="user",
            metadata={"is_pk": True, "is_fk": False},
        ),
        SchemaItem(
            name="username",
            item_type="column",
            parent_table="user",
            metadata={"is_pk": False, "is_fk": False},
        ),
        SchemaItem(
            name="post_id",
            item_type="column",
            parent_table="post",
            metadata={"is_pk": True, "is_fk": False},
        ),
        SchemaItem(
            name="author_id",
            item_type="column",
            parent_table="post",
            metadata={"is_pk": False, "is_fk": True},
        ),
        SchemaItem(
            name="view_count",
            item_type="column",
            parent_table="post",
            metadata={"is_pk": False, "is_fk": False},
        ),
    ]


def test_index_initialization():
    """Test basic initialization of the enhanced token index builder."""
    builder = EnhancedTokenIndexBuilder()
    assert builder.index is not None
    assert isinstance(builder.index.column_token_map, dict)
    assert isinstance(builder.index.column_metadata, dict)


def test_build_index(sample_schema_items):
    """Test building the index with sample schema items."""
    builder = EnhancedTokenIndexBuilder()
    builder.build_index(sample_schema_items)

    # Check table indexing
    assert "user" in builder.index.table_formats
    assert "post" in builder.index.table_formats

    # Check column indexing
    assert ("user", "user_id") in builder.index.column_metadata
    assert ("post", "view_count") in builder.index.column_metadata

    # Check token maps
    assert "user" in builder.index.token_map
    assert "view" in builder.index.column_token_map
    assert "count" in builder.index.column_token_map


def test_search_exact_table_match(sample_schema_items):
    """Test exact table name matches."""
    builder = EnhancedTokenIndexBuilder()
    builder.build_index(sample_schema_items)

    results = builder.search("user")
    assert len(results) > 0
    assert any(
        match.table_name == "user"
        and match.column_name is None
        and match.match_type == "exact"
        and match.score == 1.0
        for match in results
    )


def test_search_exact_column_match(sample_schema_items):
    """Test exact column name matches."""
    builder = EnhancedTokenIndexBuilder()
    builder.build_index(sample_schema_items)

    results = builder.search("view_count")
    assert len(results) > 0
    assert any(
        match.table_name == "post"
        and match.column_name == "view_count"
        and match.match_type == "exact"
        and match.score == 0.95  # Column exact match score
        for match in results
    )


def test_search_partial_matches(sample_schema_items):
    """Test partial matches for both tables and columns."""
    builder = EnhancedTokenIndexBuilder()
    builder.build_index(sample_schema_items)

    results = builder.search("view")
    assert len(results) > 0
    # Should match view_count column
    assert any(
        match.table_name == "post"
        and match.column_name == "view_count"
        and match.match_type == "prefix"
        for match in results
    )


def test_search_no_matches(sample_schema_items):
    """Test search with no matches."""
    builder = EnhancedTokenIndexBuilder()
    builder.build_index(sample_schema_items)

    results = builder.search("nonexistent")
    assert len(results) == 0


def test_search_ranking(sample_schema_items):
    """Test that search results are properly ranked."""
    builder = EnhancedTokenIndexBuilder()
    builder.build_index(sample_schema_items)

    # Search for "id" should find multiple matches
    results = builder.search("id")
    assert len(results) >= 3  # Should find user_id, post_id, author_id

    # Verify ordering: exact matches > prefix matches > partial matches
    scores = [match.score for match in results]
    assert scores == sorted(scores, reverse=True)


def test_column_metadata(sample_schema_items):
    """Test that column metadata is properly stored and accessible."""
    builder = EnhancedTokenIndexBuilder()
    builder.build_index(sample_schema_items)

    # Check primary key metadata
    user_id_metadata = builder.index.get_column_metadata("user", "user_id")
    assert user_id_metadata is not None
    assert user_id_metadata["is_pk"] is True
    assert user_id_metadata["is_fk"] is False

    # Check foreign key metadata
    author_id_metadata = builder.index.get_column_metadata("post", "author_id")
    assert author_id_metadata is not None
    assert author_id_metadata["is_pk"] is False
    assert author_id_metadata["is_fk"] is True


def test_empty_query():
    """Test handling of empty search queries."""
    builder = EnhancedTokenIndexBuilder()
    builder.build_index([])  # Empty schema

    results = builder.search("")
    assert len(results) == 0

    results = builder.search("   ")
    assert len(results) == 0
