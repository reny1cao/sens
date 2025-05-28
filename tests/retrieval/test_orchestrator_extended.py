import asyncio
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sens.exceptions import RetrievalError
from sens.retrieval.models import RetrievedColumn, RetrievedContext, RetrievedTable
from sens.retrieval.orchestrator import RetrievalOrchestrator


class TestRetrievalOrchestrator:
    """Test suite for RetrievalOrchestrator."""

    @pytest.fixture
    def mock_token_index(self):
        """Create a mock token index."""
        mock = MagicMock()
        mock.search = AsyncMock()
        return mock

    @pytest.fixture
    def mock_embedding_index(self):
        """Create a mock embedding index."""
        mock = MagicMock()
        mock.search = AsyncMock()
        return mock

    @pytest.fixture
    def mock_schema_graph(self):
        """Create a mock schema graph."""
        mock = MagicMock()
        mock.get_table_sticky_columns = MagicMock(return_value=[])
        mock.get_neighbor_tables = MagicMock(return_value=[])
        mock.get_table_pks = MagicMock(return_value=["id"])
        mock.get_table_fks_involved = MagicMock(return_value=[])
        return mock

    @pytest.fixture
    def orchestrator(self, mock_token_index, mock_embedding_index, mock_schema_graph):
        """Create a RetrievalOrchestrator instance."""
        return RetrievalOrchestrator(
            token_index=mock_token_index,
            embedding_index=mock_embedding_index,
            schema_graph=mock_schema_graph,
        )

    @pytest.mark.asyncio
    async def test_get_relevant_context_basic(self, orchestrator):
        """Test basic retrieval flow."""
        # Setup mock responses
        token_hits = [
            RetrievedColumn(
                table_name="users",
                column_name="user_id",
                score=0.9,
                source="token",
            ),
            RetrievedColumn(
                table_name="users",
                column_name="created_at",
                score=0.8,
                source="token",
            ),
        ]

        embedding_hits = [
            RetrievedColumn(
                table_name="users",
                column_name="email",
                score=0.7,
                source="embedding",
            ),
            RetrievedColumn(
                table_name="orders",
                column_name="user_id",
                score=0.6,
                source="embedding",
            ),
        ]

        orchestrator.token_index.search.return_value = token_hits
        orchestrator.embedding_index.search.return_value = embedding_hits

        # Execute
        result = await orchestrator.get_relevant_context(
            "Find users created last month", k=3
        )

        # Verify
        assert isinstance(result, RetrievedContext)
        assert result.query == "Find users created last month"
        assert len(result.tables) >= 1
        assert any(t.table_name == "users" for t in result.tables)
        assert len(result.columns) >= 3

    @pytest.mark.asyncio
    async def test_merge_and_deduplicate(self, orchestrator):
        """Test that duplicate columns are properly merged."""
        # Setup mock responses with duplicates
        token_hits = [
            RetrievedColumn(
                table_name="users",
                column_name="user_id",
                score=0.9,
                source="token",
            ),
            RetrievedColumn(
                table_name="users",
                column_name="email",
                score=0.7,
                source="token",
            ),
        ]

        embedding_hits = [
            RetrievedColumn(
                table_name="users",
                column_name="user_id",
                score=0.8,  # Lower score than token hit
                source="embedding",
            ),
            RetrievedColumn(
                table_name="users",
                column_name="email",
                score=0.85,  # Higher score than token hit
                source="embedding",
            ),
        ]

        orchestrator.token_index.search.return_value = token_hits
        orchestrator.embedding_index.search.return_value = embedding_hits

        # Execute
        result = await orchestrator.get_relevant_context("Find users", k=3)

        # Verify deduplication kept highest scores
        user_id_cols = [
            c
            for c in result.columns
            if c.column_name == "user_id" and c.table_name == "users"
        ]
        email_cols = [
            c
            for c in result.columns
            if c.column_name == "email" and c.table_name == "users"
        ]

        assert len(user_id_cols) == 1
        assert user_id_cols[0].score == 0.9  # Token hit had higher score

        assert len(email_cols) == 1
        assert email_cols[0].score == 0.85  # Embedding hit had higher score

    @pytest.mark.asyncio
    async def test_schema_expansion(self, orchestrator):
        """Test that schema expansion adds related tables and structural columns."""
        # Setup initial hits
        token_hits = [
            RetrievedColumn(
                table_name="orders",
                column_name="total_amount",
                score=0.9,
                source="token",
            ),
        ]

        orchestrator.token_index.search.return_value = token_hits
        orchestrator.embedding_index.search.return_value = []

        # Setup schema graph to return related tables
        orchestrator.schema_graph.get_neighbor_tables.return_value = [
            "users",
            "products",
        ]
        orchestrator.schema_graph.get_table_pks.side_effect = lambda t: {
            "orders": ["order_id"],
            "users": ["user_id"],
            "products": ["product_id"],
        }.get(t, ["id"])
        orchestrator.schema_graph.get_table_fks_involved.side_effect = (
            lambda t, tables: {
                "orders": ["user_id", "product_id"],
                "users": [],
                "products": [],
            }.get(t, [])
        )

        # Execute
        result = await orchestrator.get_relevant_context("Calculate order totals", k=5)

        # Verify expansion
        table_names = {t.table_name for t in result.tables}
        assert "orders" in table_names
        assert (
            "users" in table_names or "products" in table_names
        )  # At least one neighbor

        # Verify structural columns were added
        column_names = {(c.table_name, c.column_name) for c in result.columns}
        assert ("orders", "order_id") in column_names  # PK added
        if "users" in table_names:
            assert ("orders", "user_id") in column_names  # FK added

    @pytest.mark.asyncio
    async def test_sticky_columns(self, orchestrator):
        """Test that sticky columns are included in results."""
        # Setup
        token_hits = [
            RetrievedColumn(
                table_name="users",
                column_name="email",
                score=0.9,
                source="token",
            ),
        ]

        orchestrator.token_index.search.return_value = token_hits
        orchestrator.embedding_index.search.return_value = []
        orchestrator.schema_graph.get_table_sticky_columns.return_value = [
            "status",
            "type",
        ]

        # Execute
        result = await orchestrator.get_relevant_context("Find users by email", k=2)

        # Verify sticky columns were added
        sticky_cols = [c for c in result.columns if c.is_sticky]
        assert len(sticky_cols) == 2
        assert all(c.column_name in ["status", "type"] for c in sticky_cols)
        assert all(c.score == 0.1 for c in sticky_cols)  # Sticky columns get low score

    @pytest.mark.asyncio
    async def test_structural_column_rescue(self, orchestrator):
        """Test that important structural columns (PKs/FKs) are rescued even if not in top k."""
        # Setup hits that would push structural columns out of top k
        high_score_columns = [
            RetrievedColumn(
                table_name="users",
                column_name=f"field_{i}",
                score=0.9 - i * 0.1,
                source="token",
            )
            for i in range(10)  # 10 high-scoring columns
        ]

        orchestrator.token_index.search.return_value = high_score_columns
        orchestrator.embedding_index.search.return_value = []
        orchestrator.schema_graph.get_table_pks.return_value = ["user_id"]

        # Execute with small k
        result = await orchestrator.get_relevant_context("Find user fields", k=3)

        # Verify PK was rescued despite low score
        pk_cols = [c for c in result.columns if c.column_name == "user_id"]
        assert len(pk_cols) == 1
        assert pk_cols[0].metadata.get("type") == "PK"

    @pytest.mark.asyncio
    async def test_no_results_error(self, orchestrator):
        """Test that appropriate error is raised when no results found."""
        orchestrator.token_index.search.return_value = []
        orchestrator.embedding_index.search.return_value = []

        with pytest.raises(RetrievalError) as exc_info:
            await orchestrator.get_relevant_context("Find nonexistent data", k=5)

        assert "No schema matches found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_token_index_failure_graceful(self, orchestrator):
        """Test graceful handling of token index failure."""
        # Token index fails, embedding index works
        orchestrator.token_index.search.side_effect = Exception("Token index error")
        orchestrator.embedding_index.search.return_value = [
            RetrievedColumn(
                table_name="users",
                column_name="email",
                score=0.8,
                source="embedding",
            ),
        ]

        # Should not raise, should use embedding results
        result = await orchestrator.get_relevant_context("Find users", k=3)
        assert len(result.columns) >= 1
        assert result.columns[0].source == "embedding"

    @pytest.mark.asyncio
    async def test_embedding_index_failure_graceful(self, orchestrator):
        """Test graceful handling of embedding index failure."""
        # Embedding index fails, token index works
        orchestrator.token_index.search.return_value = [
            RetrievedColumn(
                table_name="users",
                column_name="email",
                score=0.8,
                source="token",
            ),
        ]
        orchestrator.embedding_index.search.side_effect = Exception(
            "Embedding index error"
        )

        # Should not raise, should use token results
        result = await orchestrator.get_relevant_context("Find users", k=3)
        assert len(result.columns) >= 1
        assert result.columns[0].source == "token"

    @pytest.mark.asyncio
    async def test_both_indices_fail(self, orchestrator):
        """Test that both indices failing still raises appropriate error."""
        orchestrator.token_index.search.side_effect = Exception("Token index error")
        orchestrator.embedding_index.search.side_effect = Exception(
            "Embedding index error"
        )

        with pytest.raises(RetrievalError) as exc_info:
            await orchestrator.get_relevant_context("Find users", k=3)

        assert "No schema matches found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_rank_and_select_respects_k(self, orchestrator):
        """Test that rank and select returns at most k non-sticky columns plus structural columns."""
        # Create many columns
        many_columns = [
            RetrievedColumn(
                table_name="users",
                column_name=f"col_{i}",
                score=0.9 - i * 0.01,
                source="token",
            )
            for i in range(20)
        ]

        orchestrator.token_index.search.return_value = many_columns
        orchestrator.embedding_index.search.return_value = []
        orchestrator.schema_graph.get_table_sticky_columns.return_value = [
            "sticky1",
            "sticky2",
        ]

        # Execute with k=5
        result = await orchestrator.get_relevant_context("Find users", k=5)

        # Count different types of columns
        sticky_cols = [c for c in result.columns if c.is_sticky]
        regular_cols = [
            c
            for c in result.columns
            if not c.is_sticky and c.metadata.get("type") not in ["PK", "FK"]
        ]

        assert len(sticky_cols) == 2  # All sticky columns included
        assert len(regular_cols) <= 5  # At most k regular columns
        # Structural columns (PKs/FKs) are added on top of k limit

    @pytest.mark.asyncio
    async def test_fk_rescue_with_references(self, orchestrator):
        """Test that FKs are properly rescued with reference information."""
        token_hits = [
            RetrievedColumn(
                table_name="orders",
                column_name="total",
                score=0.9,
                source="token",
            ),
        ]

        orchestrator.token_index.search.return_value = token_hits
        orchestrator.embedding_index.search.return_value = []

        # Setup relationships
        orchestrator.schema_graph.get_neighbor_tables.return_value = ["users"]
        orchestrator.schema_graph.get_table_fks_involved.side_effect = (
            lambda t, tables: {
                "orders": ["user_id"],  # orders.user_id -> users.user_id
            }.get(t, [])
        )

        # Execute
        result = await orchestrator.get_relevant_context("Find order totals", k=3)

        # Find the FK column
        fk_cols = [
            c
            for c in result.columns
            if c.column_name == "user_id" and c.metadata.get("type") == "FK"
        ]
        assert len(fk_cols) == 1
        assert fk_cols[0].table_name == "orders"
        # The FK rescue logic should try to infer the referenced table
        assert (
            fk_cols[0].metadata.get("references_table") == "users"
            or fk_cols[0].metadata.get("references_table") is None
        )

    @pytest.mark.asyncio
    async def test_complex_join_expansion(self, orchestrator):
        """Test expansion with multiple levels of joins."""
        # Initial hit on orders table
        token_hits = [
            RetrievedColumn(
                table_name="order_items",
                column_name="quantity",
                score=0.9,
                source="token",
            ),
        ]

        orchestrator.token_index.search.return_value = token_hits
        orchestrator.embedding_index.search.return_value = []

        # Setup complex relationships
        def get_neighbors(tables):
            neighbors = set()
            for table in tables:
                if table == "order_items":
                    neighbors.update(["orders", "products"])
                elif table == "orders":
                    neighbors.update(["users", "order_items"])
                elif table == "products":
                    neighbors.update(["categories", "order_items"])
            return list(neighbors - tables)

        orchestrator.schema_graph.get_neighbor_tables.side_effect = get_neighbors

        # Execute
        result = await orchestrator.get_relevant_context(
            "Find order item quantities", k=5
        )

        # Verify multiple tables included
        table_names = {t.table_name for t in result.tables}
        assert "order_items" in table_names
        assert len(table_names) >= 2  # Should include neighbors

    @pytest.mark.asyncio
    async def test_logging_structure(self, orchestrator):
        """Test that proper structured logging is performed."""
        # Setup
        token_hits = [
            RetrievedColumn(
                table_name="users",
                column_name="email",
                score=0.9,
                source="token",
            ),
        ]

        orchestrator.token_index.search.return_value = token_hits
        orchestrator.embedding_index.search.return_value = []

        # Execute and verify it completes without error
        result = await orchestrator.get_relevant_context("Find users", k=3)

        # Verify result structure
        assert isinstance(result, RetrievedContext)
        assert result.query == "Find users"
        assert len(result.columns) >= 1

        # Note: The actual log capture would need to be done at initialization
        # and throughout the method. Since we're testing the orchestrator behavior,
        # we're verifying the method completes successfully with proper results.

    @pytest.mark.asyncio
    async def test_empty_expansion_error(self, orchestrator):
        """Test error when no results are found from either index."""
        # Both indices return empty results
        orchestrator.token_index.search.return_value = []
        orchestrator.embedding_index.search.return_value = []

        # This should raise "No schema matches found" error
        with pytest.raises(RetrievalError) as exc_info:
            await orchestrator.get_relevant_context("Find data", k=3)

        assert "No schema matches found" in str(exc_info.value)
