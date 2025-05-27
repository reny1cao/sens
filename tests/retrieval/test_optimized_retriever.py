"""Tests for optimized schema retriever."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sens.caching.manager import CacheManager
from sens.retrieval.models import RetrievedColumn, RetrievedContext, RetrievedTable
from sens.retrieval.optimized_retriever import OptimizedSchemaRetriever
from sens.schema.context import LLMSchemaContext
from sens.schema.graph import SchemaGraph
from sens.schema.precomputed_index import PrecomputedSchemaIndex, TableIndex


@pytest.fixture
def mock_token_index():
    """Create mock token index."""
    mock = MagicMock()
    mock.search = AsyncMock()
    return mock


@pytest.fixture
def mock_embedding_index():
    """Create mock embedding index."""
    mock = MagicMock()
    mock.search = AsyncMock()
    return mock


@pytest.fixture
def mock_schema_graph():
    """Create mock schema graph."""
    mock = MagicMock(spec=SchemaGraph)
    return mock


@pytest.fixture
def mock_cache_manager():
    """Create mock cache manager."""
    mock = MagicMock(spec=CacheManager)
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock()
    mock.generate_key = MagicMock(return_value="test_cache_key")
    return mock


@pytest.fixture
def sample_search_results():
    """Create sample search results."""
    token_hits = [
        RetrievedColumn(
            table_name="users",
            column_name="username",
            score=0.9,
            source="token",
        ),
        RetrievedColumn(
            table_name="posts",
            column_name="title",
            score=0.8,
            source="token",
        ),
    ]

    embedding_hits = [
        RetrievedColumn(
            table_name="users",
            column_name="email",
            score=0.85,
            source="embedding",
        ),
        RetrievedColumn(
            table_name="posts",
            column_name="content",
            score=0.75,
            source="embedding",
        ),
    ]

    return token_hits, embedding_hits


@pytest.fixture
def mock_precomputed_index():
    """Create mock pre-computed index."""
    mock = MagicMock(spec=PrecomputedSchemaIndex)

    # Mock table indexes
    mock.table_indexes = {
        "users": TableIndex(
            table_name="users",
            columns=["user_id", "username", "email"],
            primary_keys=["user_id"],
            sticky_columns=["username"],
            foreign_key_columns={},
            column_descriptions={"username": "User's display name"},
        ),
        "posts": TableIndex(
            table_name="posts",
            columns=["post_id", "user_id", "title", "content"],
            primary_keys=["post_id"],
            sticky_columns=["title"],
            foreign_key_columns={"user_id": ("users", "user_id")},
            column_descriptions={"title": "Post title"},
        ),
    }

    mock.get_table_index = lambda t: mock.table_indexes.get(t)
    mock.get_expanded_schema_fast = MagicMock(
        return_value=(
            {"users", "posts"},
            {"users": ["username"], "posts": ["title"]},
        )
    )

    return mock


class TestOptimizedSchemaRetriever:
    """Test OptimizedSchemaRetriever functionality."""

    @pytest.mark.asyncio
    async def test_init(
        self,
        mock_token_index,
        mock_embedding_index,
        mock_schema_graph,
        mock_cache_manager,
    ):
        """Test retriever initialization."""
        retriever = OptimizedSchemaRetriever(
            token_index=mock_token_index,
            embedding_index=mock_embedding_index,
            schema_graph=mock_schema_graph,
            cache_manager=mock_cache_manager,
            enable_caching=True,
        )

        assert retriever.token_index == mock_token_index
        assert retriever.embedding_index == mock_embedding_index
        assert retriever.schema_graph == mock_schema_graph
        assert retriever.cache_manager == mock_cache_manager
        assert retriever.enable_caching is True

    @pytest.mark.asyncio
    async def test_cache_hit(
        self,
        mock_token_index,
        mock_embedding_index,
        mock_schema_graph,
        mock_cache_manager,
    ):
        """Test retrieval with cache hit."""
        # Setup cache hit
        cached_context = {
            "query": "test query",
            "tables": [{"table_name": "users", "reason": "direct_hit"}],
            "columns": [
                {
                    "table_name": "users",
                    "column_name": "username",
                    "score": 0.9,
                    "source": "token",
                }
            ],
        }
        mock_cache_manager.get.return_value = cached_context

        retriever = OptimizedSchemaRetriever(
            token_index=mock_token_index,
            embedding_index=mock_embedding_index,
            schema_graph=mock_schema_graph,
            cache_manager=mock_cache_manager,
            enable_caching=True,
        )

        result = await retriever.get_relevant_context("test query", k=5)

        # Verify cache was checked
        mock_cache_manager.get.assert_called_once()

        # Verify search methods were not called
        mock_token_index.search.assert_not_called()
        mock_embedding_index.search.assert_not_called()

        # Verify result
        assert result.query == "test query"
        assert len(result.tables) == 1
        assert len(result.columns) == 1

    @pytest.mark.asyncio
    async def test_parallel_search(
        self,
        mock_token_index,
        mock_embedding_index,
        mock_schema_graph,
        mock_cache_manager,
        sample_search_results,
        mock_precomputed_index,
    ):
        """Test parallel search execution."""
        token_hits, embedding_hits = sample_search_results
        mock_token_index.search.return_value = token_hits
        mock_embedding_index.search.return_value = embedding_hits

        with patch(
            "sens.retrieval.optimized_retriever.PrecomputedSchemaIndex",
            return_value=mock_precomputed_index,
        ):
            retriever = OptimizedSchemaRetriever(
                token_index=mock_token_index,
                embedding_index=mock_embedding_index,
                schema_graph=mock_schema_graph,
                cache_manager=mock_cache_manager,
                enable_caching=True,
            )

            result = await retriever.get_relevant_context("find users and posts", k=5)

        # Verify both searches were called
        mock_token_index.search.assert_called_once_with("find users and posts", k=10)
        mock_embedding_index.search.assert_called_once_with(
            "find users and posts", k=10
        )

        # Verify result contains columns from both sources
        assert len(result.columns) > 0
        assert any(col.source == "token" for col in result.columns)
        assert any(col.source == "embedding" for col in result.columns)

    @pytest.mark.asyncio
    async def test_schema_expansion(
        self,
        mock_token_index,
        mock_embedding_index,
        mock_schema_graph,
        mock_cache_manager,
        sample_search_results,
        mock_precomputed_index,
    ):
        """Test schema expansion with pre-computed indexes."""
        token_hits, embedding_hits = sample_search_results
        mock_token_index.search.return_value = token_hits
        mock_embedding_index.search.return_value = embedding_hits

        with patch(
            "sens.retrieval.optimized_retriever.PrecomputedSchemaIndex",
            return_value=mock_precomputed_index,
        ):
            retriever = OptimizedSchemaRetriever(
                token_index=mock_token_index,
                embedding_index=mock_embedding_index,
                schema_graph=mock_schema_graph,
                cache_manager=mock_cache_manager,
                enable_caching=True,
            )

            result = await retriever.get_relevant_context("test query", k=5)

        # Verify expansion was called
        mock_precomputed_index.get_expanded_schema_fast.assert_called_once()

        # Verify sticky columns were added
        sticky_columns = [col for col in result.columns if col.is_sticky]
        assert len(sticky_columns) > 0

        # Verify structural columns were added
        structural_columns = [
            col for col in result.columns if col.metadata.get("type") in ("PK", "FK")
        ]
        assert len(structural_columns) > 0

    @pytest.mark.asyncio
    async def test_convert_to_llm_context(
        self,
        mock_token_index,
        mock_embedding_index,
        mock_schema_graph,
        mock_cache_manager,
        mock_precomputed_index,
    ):
        """Test conversion to LLM schema context."""
        with patch(
            "sens.retrieval.optimized_retriever.PrecomputedSchemaIndex",
            return_value=mock_precomputed_index,
        ):
            retriever = OptimizedSchemaRetriever(
                token_index=mock_token_index,
                embedding_index=mock_embedding_index,
                schema_graph=mock_schema_graph,
                cache_manager=mock_cache_manager,
            )

            # Create a sample retrieved context
            retrieved_context = RetrievedContext(
                query="test query",
                tables=[
                    RetrievedTable(table_name="users", reason="direct_hit"),
                    RetrievedTable(table_name="posts", reason="join_expansion"),
                ],
                columns=[
                    RetrievedColumn(
                        table_name="users",
                        column_name="user_id",
                        score=0.0,
                        source="structural",
                        metadata={"type": "PK"},
                    ),
                    RetrievedColumn(
                        table_name="users",
                        column_name="username",
                        score=0.9,
                        source="token",
                    ),
                    RetrievedColumn(
                        table_name="posts",
                        column_name="post_id",
                        score=0.0,
                        source="structural",
                        metadata={"type": "PK"},
                    ),
                    RetrievedColumn(
                        table_name="posts",
                        column_name="user_id",
                        score=0.0,
                        source="structural",
                        metadata={"type": "FK"},
                    ),
                ],
            )

            llm_context = retriever.convert_to_llm_context(retrieved_context)

        # Verify LLM context structure
        assert isinstance(llm_context, LLMSchemaContext)
        assert llm_context.tables == {"users", "posts"}
        assert "users" in llm_context.tables_columns
        assert "posts" in llm_context.tables_columns
        assert llm_context.primary_keys["users"] == ["user_id"]
        assert llm_context.primary_keys["posts"] == ["post_id"]
        assert len(llm_context.foreign_keys) > 0
        assert llm_context.sticky_columns["users"] == ["username"]

    @pytest.mark.asyncio
    async def test_fallback_on_error(
        self,
        mock_token_index,
        mock_embedding_index,
        mock_schema_graph,
        mock_cache_manager,
    ):
        """Test fallback to original orchestrator on error."""
        # Make token search fail
        mock_token_index.search.side_effect = Exception("Search failed")

        with patch(
            "sens.retrieval.optimized_retriever.RetrievalOrchestrator"
        ) as mock_orchestrator_class:
            mock_orchestrator = MagicMock()
            mock_orchestrator.get_relevant_context = AsyncMock(
                return_value=RetrievedContext(
                    query="test query",
                    tables=[],
                    columns=[],
                )
            )
            mock_orchestrator_class.return_value = mock_orchestrator

            retriever = OptimizedSchemaRetriever(
                token_index=mock_token_index,
                embedding_index=mock_embedding_index,
                schema_graph=mock_schema_graph,
                cache_manager=mock_cache_manager,
            )

            result = await retriever.get_relevant_context("test query", k=5)

        # Verify fallback was used
        mock_orchestrator.get_relevant_context.assert_called_once_with("test query", 5)
        assert result.query == "test query"
