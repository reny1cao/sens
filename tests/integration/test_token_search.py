"""Integration tests for the token search pipeline."""

import pytest

from sens.cli.nl2sql import TokenIndexCLIAdapter
from sens.retrieval.models import RetrievedColumn
from sens.schema.graph import SchemaGraph


@pytest.fixture
async def token_adapter():
    """Create and initialize a TokenIndexCLIAdapter instance."""
    adapter = TokenIndexCLIAdapter()
    await adapter.initialize()
    return adapter


@pytest.mark.asyncio
async def test_token_search_pipeline(token_adapter):
    """Test the complete token search pipeline with various queries."""
    # Test table name search
    results = await token_adapter.search("view_summary")
    assert len(results) > 0
    assert any(
        result.table_name == "view_summary"
        and result.column_name == "*"
        and result.metadata["match_type"] == "exact"
        for result in results
    )

    # Test column name search
    results = await token_adapter.search("cumulative_weeks")
    assert len(results) > 0
    assert any(
        result.column_name == "cumulative_weeks_in_top10"
        and result.metadata["match_type"] in ["prefix", "partial"]
        for result in results
    )

    # Test combined table and column search
    results = await token_adapter.search("season number")
    assert len(results) > 0
    # Should find both the season table and season_number column
    table_match = False
    column_match = False
    for result in results:
        if result.table_name == "season" and result.column_name == "*":
            table_match = True
        if result.column_name == "season_number":
            column_match = True
    assert table_match and column_match

    # Test no matches
    results = await token_adapter.search("nonexistent_table_or_column")
    assert len(results) == 0


@pytest.mark.asyncio
async def test_token_search_metadata(token_adapter):
    """Test that token search results include appropriate metadata."""
    results = await token_adapter.search("id")
    assert len(results) > 0
    for result in results:
        assert "match_type" in result.metadata
        assert "token_overlap" in result.metadata
        assert result.metadata["match_type"] in ["exact", "prefix", "partial"]
        assert isinstance(result.metadata["token_overlap"], int)


@pytest.mark.asyncio
async def test_token_search_ranking(token_adapter):
    """Test that token search results are properly ranked."""
    # Search for a term that should match multiple items
    results = await token_adapter.search("view")
    assert len(results) > 0

    # Verify scores are in descending order
    scores = [result.score for result in results]
    assert scores == sorted(scores, reverse=True)

    # Verify exact matches come before partial matches
    for i in range(len(results) - 1):
        if results[i].metadata["match_type"] == "exact":
            if results[i + 1].metadata["match_type"] != "exact":
                assert results[i].score > results[i + 1].score


@pytest.mark.asyncio
async def test_token_search_with_special_characters(token_adapter):
    """Test token search with special characters and edge cases."""
    # Test with mixed case
    results = await token_adapter.search("ViewSummary")
    assert any(result.table_name == "view_summary" for result in results)

    # Test with underscores
    results = await token_adapter.search("view_rank")
    assert any(
        result.column_name == "view_rank" and result.metadata["match_type"] == "exact"
        for result in results
    )

    # Test with spaces
    results = await token_adapter.search("view rank")
    assert len(results) > 0  # Should find relevant matches

    # Test with empty string
    results = await token_adapter.search("")
    assert len(results) == 0

    # Test with only spaces
    results = await token_adapter.search("   ")
    assert len(results) == 0
