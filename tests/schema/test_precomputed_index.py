"""Tests for pre-computed schema indexes."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sens.schema.graph import SchemaGraph
from sens.schema.precomputed_index import (
    PrecomputedSchemaIndex,
    RelationshipIndex,
    TableIndex,
)


@pytest.fixture
def sample_schema_data():
    """Create sample schema data for testing."""
    return {
        "tables": {
            "users": {
                "columns": [
                    {"name": "user_id", "type": "INTEGER"},
                    {"name": "username", "type": "VARCHAR(50)"},
                    {"name": "email", "type": "VARCHAR(100)"},
                    {"name": "created_at", "type": "TIMESTAMP"},
                ],
                "primary_keys": ["user_id"],
                "sticky_columns": ["username", "email"],
            },
            "posts": {
                "columns": [
                    {"name": "post_id", "type": "INTEGER"},
                    {"name": "user_id", "type": "INTEGER"},
                    {"name": "title", "type": "VARCHAR(200)"},
                    {"name": "content", "type": "TEXT"},
                    {"name": "created_at", "type": "TIMESTAMP"},
                ],
                "primary_keys": ["post_id"],
                "sticky_columns": ["title"],
            },
            "comments": {
                "columns": [
                    {"name": "comment_id", "type": "INTEGER"},
                    {"name": "post_id", "type": "INTEGER"},
                    {"name": "user_id", "type": "INTEGER"},
                    {"name": "content", "type": "TEXT"},
                    {"name": "created_at", "type": "TIMESTAMP"},
                ],
                "primary_keys": ["comment_id"],
                "sticky_columns": [],
            },
        },
        "relationships": [
            {
                "constraint_name": "fk_posts_user",
                "from_table": "posts",
                "to_table": "users",
                "columns": [{"from_column": "user_id", "to_column": "user_id"}],
            },
            {
                "constraint_name": "fk_comments_post",
                "from_table": "comments",
                "to_table": "posts",
                "columns": [{"from_column": "post_id", "to_column": "post_id"}],
            },
            {
                "constraint_name": "fk_comments_user",
                "from_table": "comments",
                "to_table": "users",
                "columns": [{"from_column": "user_id", "to_column": "user_id"}],
            },
        ],
        "metadata": {},
    }


@pytest.fixture
def mock_schema_graph(sample_schema_data):
    """Create a mock SchemaGraph instance."""
    mock_graph = MagicMock(spec=SchemaGraph)

    # Mock list_all_tables
    mock_graph.list_all_tables.return_value = list(sample_schema_data["tables"].keys())

    # Mock get_table_columns
    def get_columns(table_name):
        table = sample_schema_data["tables"].get(table_name, {})
        return [col["name"] for col in table.get("columns", [])]

    mock_graph.get_table_columns.side_effect = get_columns

    # Mock get_table_pks
    def get_pks(table_name):
        table = sample_schema_data["tables"].get(table_name, {})
        return table.get("primary_keys", [])

    mock_graph.get_table_pks.side_effect = get_pks

    # Mock get_table_sticky_columns
    def get_sticky(table_name):
        table = sample_schema_data["tables"].get(table_name, {})
        return table.get("sticky_columns", [])

    mock_graph.get_table_sticky_columns.side_effect = get_sticky

    # Mock relationship methods
    mock_graph.get_referenced_tables.side_effect = lambda t: {
        "posts": {"users"},
        "comments": {"posts", "users"},
    }.get(t, set())

    mock_graph.get_referencing_tables.side_effect = lambda t: {
        "users": {"posts", "comments"},
        "posts": {"comments"},
    }.get(t, set())

    mock_graph.get_neighbor_tables.side_effect = lambda tables: {
        "users": {"posts", "comments"},
        "posts": {"users", "comments"},
        "comments": {"posts", "users"},
    }.get(next(iter(tables)), set())

    # Mock FK map
    mock_graph._fk_map = {
        "posts": [(["user_id"], "users", ["user_id"])],
        "comments": [
            (["post_id"], "posts", ["post_id"]),
            (["user_id"], "users", ["user_id"]),
        ],
    }

    # Mock column comments
    mock_graph.get_column_comment.return_value = None

    return mock_graph


class TestPrecomputedSchemaIndex:
    """Test PrecomputedSchemaIndex functionality."""

    def test_init_builds_indexes(self, mock_schema_graph):
        """Test that initialization builds all indexes."""
        with patch(
            "sens.schema.precomputed_index.SchemaGraph.get_instance",
            return_value=mock_schema_graph,
        ):
            index = PrecomputedSchemaIndex()

        # Verify table indexes were built
        assert len(index.table_indexes) == 3
        assert "users" in index.table_indexes
        assert "posts" in index.table_indexes
        assert "comments" in index.table_indexes

    def test_table_index_content(self, mock_schema_graph):
        """Test that table indexes contain correct information."""
        with patch(
            "sens.schema.precomputed_index.SchemaGraph.get_instance",
            return_value=mock_schema_graph,
        ):
            index = PrecomputedSchemaIndex()

        # Check users table index
        users_index = index.table_indexes["users"]
        assert users_index.table_name == "users"
        assert users_index.columns == ["user_id", "username", "email", "created_at"]
        assert users_index.primary_keys == ["user_id"]
        assert users_index.sticky_columns == ["username", "email"]
        assert users_index.referenced_tables == set()
        assert users_index.referencing_tables == {"posts", "comments"}

    def test_relationship_index_content(self, mock_schema_graph):
        """Test that relationship indexes are built correctly."""
        with patch(
            "sens.schema.precomputed_index.SchemaGraph.get_instance",
            return_value=mock_schema_graph,
        ):
            index = PrecomputedSchemaIndex()

        # Check foreign keys
        assert ("posts", "users") in index.relationship_index.foreign_keys
        assert ("comments", "posts") in index.relationship_index.foreign_keys
        assert ("comments", "users") in index.relationship_index.foreign_keys

        # Check join graph
        assert "users" in index.relationship_index.join_graph["posts"]
        assert "posts" in index.relationship_index.join_graph["users"]

    def test_join_distances(self, mock_schema_graph):
        """Test that join distances are computed correctly."""
        with patch(
            "sens.schema.precomputed_index.SchemaGraph.get_instance",
            return_value=mock_schema_graph,
        ):
            index = PrecomputedSchemaIndex()

        # Check distances from users
        users_distances = index.relationship_index.join_distances["users"]
        assert users_distances["users"] == 0
        assert users_distances["posts"] == 1
        assert users_distances["comments"] == 1

    def test_get_tables_within_distance(self, mock_schema_graph):
        """Test getting tables within a certain distance."""
        with patch(
            "sens.schema.precomputed_index.SchemaGraph.get_instance",
            return_value=mock_schema_graph,
        ):
            index = PrecomputedSchemaIndex()

        # Tables within distance 1 of users
        tables = index.get_tables_within_distance({"users"}, max_distance=1)
        assert tables == {"users", "posts", "comments"}

        # Tables within distance 0 of users (only itself)
        tables = index.get_tables_within_distance({"users"}, max_distance=0)
        assert tables == {"users"}

    def test_get_join_path(self, mock_schema_graph):
        """Test finding join paths between tables."""
        with patch(
            "sens.schema.precomputed_index.SchemaGraph.get_instance",
            return_value=mock_schema_graph,
        ):
            index = PrecomputedSchemaIndex()

        # Direct path
        path = index.get_join_path("posts", "users")
        assert path == ["posts", "users"]

        # Same table
        path = index.get_join_path("users", "users")
        assert path == ["users"]

        # Invalid table
        path = index.get_join_path("users", "invalid_table")
        assert path is None

    def test_get_common_join_tables(self, mock_schema_graph):
        """Test finding common join tables."""
        with patch(
            "sens.schema.precomputed_index.SchemaGraph.get_instance",
            return_value=mock_schema_graph,
        ):
            index = PrecomputedSchemaIndex()

        # Common tables that can join with both posts and comments
        common = index.get_common_join_tables({"posts", "comments"})
        assert "users" in common  # Both posts and comments join with users

    def test_get_expanded_schema_fast(self, mock_schema_graph):
        """Test fast schema expansion."""
        with patch(
            "sens.schema.precomputed_index.SchemaGraph.get_instance",
            return_value=mock_schema_graph,
        ):
            index = PrecomputedSchemaIndex()

        # Expand from users table
        tables, sticky_by_table = index.get_expanded_schema_fast(
            {"users"}, max_expansion=1
        )

        assert "users" in tables
        assert "posts" in tables
        assert "comments" in tables

        assert sticky_by_table["users"] == ["username", "email"]
        assert sticky_by_table["posts"] == ["title"]

    def test_cache_save_and_load(self, mock_schema_graph, tmp_path):
        """Test caching functionality."""
        cache_file = tmp_path / "test_cache.pkl"

        with patch(
            "sens.schema.precomputed_index.SchemaGraph.get_instance",
            return_value=mock_schema_graph,
        ):
            # Create and save index
            index1 = PrecomputedSchemaIndex()
            index1._save_to_cache(cache_file)

            # Create new index and load from cache
            index2 = PrecomputedSchemaIndex()
            index2._load_from_cache(cache_file)

            # Verify loaded data matches
            assert len(index2.table_indexes) == len(index1.table_indexes)
            assert index2.table_indexes["users"].sticky_columns == ["username", "email"]
