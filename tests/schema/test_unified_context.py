"""Tests for unified schema context building."""

import pytest

from sens.llm.intent_validator import ValidIntent
from sens.llm.models import Intent
from sens.retrieval.models import RetrievedColumn, RetrievedContext, RetrievedTable
from sens.schema.unified_context import (
    SchemaContextStrategy,
    UnifiedSchemaContextBuilder,
)


@pytest.fixture
def retrieved_context():
    """Create a sample retrieved context."""
    return RetrievedContext(
        query="Show me all tv_show",
        tables=[
            RetrievedTable(table_name="tv_show", reason="direct_hit", metadata={}),
            RetrievedTable(table_name="season", reason="direct_hit", metadata={}),
        ],
        columns=[
            RetrievedColumn(
                table_name="tv_show",
                column_name="title",
                score=0.68,
                source="embedding",
                metadata={},
                is_sticky=False,
            ),
            RetrievedColumn(
                table_name="tv_show",
                column_name="id",
                score=0.55,
                source="embedding",
                metadata={},
                is_sticky=False,
            ),
            RetrievedColumn(
                table_name="tv_show",
                column_name="locale",
                score=0.54,
                source="embedding",
                metadata={},
                is_sticky=False,
            ),
            RetrievedColumn(
                table_name="tv_show",
                column_name="original_title",
                score=0.1,
                source="sticky",
                metadata={"type": "sticky"},
                is_sticky=True,
            ),
            RetrievedColumn(
                table_name="season",
                column_name="tv_show_id",
                score=0.63,
                source="embedding",
                metadata={},
                is_sticky=False,
            ),
            RetrievedColumn(
                table_name="season",
                column_name="title",
                score=0.1,
                source="sticky",
                metadata={"type": "sticky"},
                is_sticky=True,
            ),
            RetrievedColumn(
                table_name="season",
                column_name="id",
                score=0.0,
                source="structural",
                metadata={"type": "PK"},
                is_sticky=False,
            ),
        ],
    )


@pytest.fixture
def valid_intent():
    """Create a sample valid intent."""
    return ValidIntent(
        original_intent=Intent(
            query_type="lookup",
            tables=["tv_show"],
            operations=[],
            conditions=[],
            confidence=0.95,
        ),
        enhanced_metadata={},
    )


class TestUnifiedSchemaContextBuilder:
    """Test the unified schema context builder."""

    def test_build_from_retrieval_conservative(self, retrieved_context, valid_intent):
        """Test building context with conservative strategy (only retrieved columns)."""
        builder = UnifiedSchemaContextBuilder()

        llm_context, validator_context = builder.build_from_retrieval(
            retrieved_context=retrieved_context,
            intent=valid_intent,
            include_all_columns=False,
        )

        # Check LLM context
        assert "tv_show" in llm_context.tables_columns
        assert "season" in llm_context.tables_columns

        # Should only have retrieved columns
        assert set(llm_context.tables_columns["tv_show"]) == {
            "title",
            "id",
            "locale",
            "original_title",
        }
        assert set(llm_context.tables_columns["season"]) == {
            "tv_show_id",
            "title",
            "id",
        }

        # Check validator context
        assert validator_context.tables == llm_context.tables
        assert validator_context.columns_per_table["tv_show"] == set(
            llm_context.tables_columns["tv_show"]
        )
        assert validator_context.columns_per_table["season"] == set(
            llm_context.tables_columns["season"]
        )

    def test_build_from_retrieval_aggressive(self, retrieved_context, valid_intent):
        """Test building context with aggressive strategy (all columns)."""
        builder = UnifiedSchemaContextBuilder()

        llm_context, validator_context = builder.build_from_retrieval(
            retrieved_context=retrieved_context,
            intent=valid_intent,
            include_all_columns=True,
        )

        # Check LLM context
        assert "tv_show" in llm_context.tables_columns

        # Should have all columns from schema (including date columns)
        tv_show_columns = llm_context.tables_columns["tv_show"]
        assert "created_date" in tv_show_columns
        assert "modified_date" in tv_show_columns
        assert "release_date" in tv_show_columns
        assert "title" in tv_show_columns
        assert "id" in tv_show_columns

        # Validator context should match
        assert validator_context.columns_per_table["tv_show"] == set(tv_show_columns)

    def test_context_consistency(self, retrieved_context, valid_intent):
        """Test that LLM and validator contexts are consistent."""
        builder = UnifiedSchemaContextBuilder()

        llm_context, validator_context = builder.build_from_retrieval(
            retrieved_context=retrieved_context,
            intent=valid_intent,
            include_all_columns=True,
        )

        # Tables should match
        assert llm_context.tables == validator_context.tables

        # Columns should match
        for table in llm_context.tables:
            assert (
                set(llm_context.tables_columns[table])
                == validator_context.columns_per_table[table]
            )

    def test_foreign_key_expansion(self, retrieved_context, valid_intent):
        """Test that foreign key relationships are properly built."""
        builder = UnifiedSchemaContextBuilder()

        llm_context, validator_context = builder.build_from_retrieval(
            retrieved_context=retrieved_context,
            intent=valid_intent,
            include_all_columns=False,
        )

        # Should have foreign keys
        assert len(llm_context.foreign_keys) > 0

        # Check for specific FK relationship
        fk_found = False
        for fk in llm_context.foreign_keys:
            if fk["from_table"] == "season" and fk["to_table"] == "tv_show":
                assert "tv_show_id" in fk["from_columns"]
                assert "id" in fk["to_columns"]
                fk_found = True

        assert fk_found, "Expected foreign key relationship not found"
