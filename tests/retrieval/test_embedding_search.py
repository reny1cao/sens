"""Tests for the embedding-based semantic search functionality."""

import json
import tempfile
import time
from pathlib import Path

import pytest

from sens.retrieval import EmbeddingSearch, top_columns


@pytest.fixture
def sample_schema():
    """Create a sample schema for testing."""
    return {
        "tables": [
            {
                "name": "movie",
                "columns": [
                    {"name": "rating", "description": "Movie rating from 1 to 5 stars"},
                    {"name": "title", "description": "The title of the movie"},
                ],
            },
            {
                "name": "user",
                "columns": [
                    {
                        "name": "user_id",
                        "description": "Unique identifier for the user",
                    },
                    {"name": "username", "description": "User's display name"},
                ],
            },
        ]
    }


@pytest.fixture
def schema_file(sample_schema, tmp_path):
    """Create a temporary schema file."""
    schema_path = tmp_path / "schema.json"
    with open(schema_path, "w") as f:
        json.dump(sample_schema, f)
    return schema_path


@pytest.fixture
def index_dir(tmp_path):
    """Create a temporary directory for indices."""
    return tmp_path / "indices"


def test_build_and_search(schema_file, index_dir):
    """Test building the index and searching."""
    # Initialize search
    search = EmbeddingSearch(index_dir=str(index_dir))

    # Build index
    search.build_index(str(schema_file))

    # Verify index files exist
    assert (index_dir / "columns.index").exists()
    assert (index_dir / "lookup.npy").exists()

    # Test search
    results = search.search("rating", k=3)
    assert len(results) == 3

    # Verify movie.rating is in top results
    top_hits = [(table, column) for table, column, _ in results]
    assert ("movie", "rating") in top_hits


def test_top_columns_api(schema_file, index_dir, monkeypatch):
    """Test the top_columns API function."""
    # Set up search with test directory
    search = EmbeddingSearch(index_dir=str(index_dir))
    search.build_index(str(schema_file))

    # Patch the global instance
    monkeypatch.setattr("sens.retrieval.embedding_search._embedding_search", search)

    # Test API
    results = top_columns("user name", k=2)
    assert len(results) == 2

    # Verify username is in results
    top_hits = [(table, column) for table, column, _ in results]
    assert ("user", "username") in top_hits


def test_search_performance(schema_file, index_dir):
    """Test search performance meets latency requirements."""
    # Initialize and build index
    search = EmbeddingSearch(index_dir=str(index_dir))
    search.build_index(str(schema_file))

    # Measure search time
    start_time = time.time()
    search.search("test query", k=20)  # Call search, but ignore results
    duration_ms = (time.time() - start_time) * 1000

    # Verify latency requirement (relaxed for test dataset)
    assert duration_ms < 100, f"Search took {duration_ms:.2f}ms, exceeding 100ms limit"
