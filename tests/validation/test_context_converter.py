"""Tests for schema context conversion."""

import pytest

from sens.retrieval.models import RetrievedColumn, RetrievedContext, RetrievedTable
from sens.validation.context_converter import to_validator_schema


def test_basic_context_conversion():
    """Test basic conversion of RetrievedContext to ValidatorSchemaContext."""
    context = RetrievedContext(
        query="test query",
        tables=[
            RetrievedTable(table_name="users", reason="direct_hit"),
            RetrievedTable(table_name="orders", reason="join_expansion"),
        ],
        columns=[
            RetrievedColumn(
                table_name="users",
                column_name="id",
                score=1.0,
                source="embedding",
                metadata={"type": "PK"},
            ),
            RetrievedColumn(
                table_name="users",
                column_name="name",
                score=0.8,
                source="embedding",
                metadata={},
            ),
        ],
    )

    validator_schema = to_validator_schema(context)

    assert "users" in validator_schema.tables
    assert "orders" in validator_schema.tables
    assert "id" in validator_schema.columns_per_table["users"]
    assert "name" in validator_schema.columns_per_table["users"]
    assert len(validator_schema.columns_per_table["orders"]) == 0


def test_foreign_key_conversion():
    """Test conversion of foreign key relationships."""
    context = RetrievedContext(
        query="test query",
        tables=[
            RetrievedTable(table_name="tv_show", reason="direct_hit"),
            RetrievedTable(table_name="season", reason="join_expansion"),
            RetrievedTable(table_name="view_summary", reason="join_expansion"),
        ],
        columns=[
            # TV Show columns
            RetrievedColumn(
                table_name="tv_show",
                column_name="id",
                score=1.0,
                source="embedding",
                metadata={"type": "PK"},
            ),
            RetrievedColumn(
                table_name="tv_show",
                column_name="title",
                score=0.8,
                source="embedding",
                metadata={},
            ),
            # Season columns with FK to tv_show
            RetrievedColumn(
                table_name="season",
                column_name="tv_show_id",
                score=0.0,
                source="schema_expansion",
                metadata={
                    "type": "FK",
                    "references_table": "tv_show",
                    "references_column": "id",
                },
            ),
            # View summary columns with FK to season
            RetrievedColumn(
                table_name="view_summary",
                column_name="season_id",
                score=0.0,
                source="schema_expansion",
                metadata={
                    "type": "FK",
                    "references_table": "season",
                    "references_column": "id",
                },
            ),
        ],
    )

    validator_schema = to_validator_schema(context)

    # Check tables are present
    assert "tv_show" in validator_schema.tables
    assert "season" in validator_schema.tables
    assert "view_summary" in validator_schema.tables

    # Check foreign keys are properly converted
    assert "season" in validator_schema.foreign_keys
    assert "tv_show_id" in validator_schema.foreign_keys["season"]
    assert validator_schema.foreign_keys["season"]["tv_show_id"] == ("tv_show", "id")

    assert "view_summary" in validator_schema.foreign_keys
    assert "season_id" in validator_schema.foreign_keys["view_summary"]
    assert validator_schema.foreign_keys["view_summary"]["season_id"] == (
        "season",
        "id",
    )


def test_foreign_key_validation():
    """Test that foreign keys are only included when both tables are in context."""
    context = RetrievedContext(
        query="test query",
        tables=[
            RetrievedTable(table_name="season", reason="direct_hit"),
        ],
        columns=[
            RetrievedColumn(
                table_name="season",
                column_name="tv_show_id",
                score=0.0,
                source="schema_expansion",
                metadata={
                    "type": "FK",
                    "references_table": "tv_show",  # Table not in context
                    "references_column": "id",
                },
            ),
        ],
    )

    validator_schema = to_validator_schema(context)

    # Check that FK is not included since referenced table is not in context
    assert (
        "season" not in validator_schema.foreign_keys
        or not validator_schema.foreign_keys["season"]
    )
