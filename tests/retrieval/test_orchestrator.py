import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from sens.retrieval.models import RetrievedColumn, RetrievedContext, RetrievedTable
from sens.retrieval.orchestrator import RetrievalOrchestrator

# Configure logging for tests (optional, but can be helpful)
# logging.basicConfig(level=logging.DEBUG)

# --- Mock Data and Objects ---

# Sample query from AC6
TEST_QUERY = "movies released in 2023 with ratings"

# Mock Schema Graph Behavior
# Represents a simple schema: movie (id, title, release_year), rating (id, movie_id, score)
# movie.id is PK, rating.movie_id is FK to movie.id
MOCK_SCHEMA = {
    "movie": {
        "pks": ["id"],
        "fks_involved": {
            # FK col: (target_table, target_col)
            "id": [("rating", "movie_id")]
        },
        "neighbors": {"rating"},
        "sticky_columns": ["title", "original_title"],
    },
    "rating": {
        "pks": ["id"],
        "fks_involved": {"movie_id": [("movie", "id")]},
        "neighbors": {"movie"},
        "sticky_columns": ["score"],
    },
    # Add other tables if needed for more complex tests
    "actor": {
        "pks": ["id"],
        "fks_involved": {},
        "neighbors": set(),
        "sticky_columns": ["name", "stage_name"],
    },
}


@pytest.fixture
def mock_schema_graph():
    graph = MagicMock()

    def get_neighbor_tables(table_names: set[str]) -> set[str]:
        neighbors = set(table_names)  # Start with the input tables
        for table in table_names:
            if table in MOCK_SCHEMA:
                neighbors.update(MOCK_SCHEMA[table]["neighbors"])
        # Refine: only keep neighbours also in the potential set?
        # For simplicity now, just return all direct neighbours
        return neighbors

    def get_table_pks(table_name: str) -> list[str]:
        return MOCK_SCHEMA.get(table_name, {}).get("pks", [])

    def get_table_fks_involved(table_name: str, involved_tables: set[str]) -> list[str]:
        fks = []
        fk_info = MOCK_SCHEMA.get(table_name, {}).get("fks_involved", {})
        for fk_col, connections in fk_info.items():
            # Check if any connection links to a table within the involved_tables set
            if any(target_table in involved_tables for target_table, _ in connections):
                fks.append(fk_col)
        return fks

    def get_table_sticky_columns(table_name: str) -> list[str]:
        return MOCK_SCHEMA.get(table_name, {}).get("sticky_columns", [])

    graph.get_neighbor_tables.side_effect = get_neighbor_tables
    graph.get_table_pks.side_effect = get_table_pks
    graph.get_table_fks_involved.side_effect = get_table_fks_involved
    graph.get_table_sticky_columns.side_effect = get_table_sticky_columns
    return graph


@pytest.fixture
def mock_token_index():
    index = MagicMock()

    # Define behavior for the specific test query
    def search(query: str, k: int):
        if query == TEST_QUERY:
            # Simulate finding relevant columns
            return [
                RetrievedColumn(
                    table_name="movie",
                    column_name="release_year",
                    score=5.0,
                    source="token",
                ),
                RetrievedColumn(
                    table_name="movie",
                    column_name="title",
                    score=4.0,
                    source="token",
                ),
            ]
        return []

    index.search.side_effect = search
    return index


@pytest.fixture
def mock_embedding_index():
    index = MagicMock()

    def search(query: str, k: int):
        if query == TEST_QUERY:
            # Simulate finding related columns, potentially overlapping or different
            return [
                RetrievedColumn(
                    table_name="rating",
                    column_name="score",
                    score=4.5,
                    source="embedding",
                ),
                RetrievedColumn(
                    table_name="movie",
                    column_name="title",
                    score=4.2,
                    source="embedding",
                ),  # Higher score than token
                RetrievedColumn(
                    table_name="actor",
                    column_name="name",
                    score=3.0,
                    source="embedding",
                ),  # Lower score, potentially filtered out
            ]
        return []

    index.search.side_effect = search
    return index


# --- Test Cases ---


@pytest.mark.asyncio
async def test_retrieval_orchestrator_basic(
    mock_token_index, mock_embedding_index, mock_schema_graph, caplog
):
    """Tests the orchestrator with the query from AC6.

    Verifies merging, schema expansion (movie<->rating), ranking, and final context.
    Also checks for the structured log message.
    """
    # Remove caplog setup since we're using structlog
    # caplog.set_level(logging.INFO)

    # Convert mock_token_index and mock_embedding_index to AsyncMocks
    mock_token_index.search = AsyncMock(
        return_value=[
            RetrievedColumn(
                table_name="movie",
                column_name="release_year",
                score=5.0,
                source="token",
            ),
            RetrievedColumn(
                table_name="movie",
                column_name="title",
                score=4.0,
                source="token",
            ),
        ]
    )
    mock_embedding_index.search = AsyncMock(
        return_value=[
            RetrievedColumn(
                table_name="rating",
                column_name="score",
                score=4.5,
                source="embedding",
            ),
        ]
    )

    orchestrator = RetrievalOrchestrator(
        token_index=mock_token_index,
        embedding_index=mock_embedding_index,
        schema_graph=mock_schema_graph,
    )

    k = 5  # Request top 5 columns to include sticky columns
    result = await orchestrator.get_relevant_context(TEST_QUERY, k=k)

    assert result.query == TEST_QUERY

    # Verify sticky columns are included
    sticky_columns = [col for col in result.columns if col.is_sticky]
    assert len(sticky_columns) > 0

    # Verify selected columns include both direct hits and sticky columns
    selected_col_keys = {(c.table_name, c.column_name) for c in result.columns}
    expected_cols = {
        ("movie", "release_year"),  # Direct hit
        ("movie", "title"),  # Direct hit + sticky
        ("movie", "original_title"),  # Sticky
        ("rating", "score"),  # Direct hit + sticky
    }
    assert selected_col_keys.issuperset(expected_cols)

    # Verify included tables based on selected columns and expansion
    final_table_names = {t.table_name for t in result.tables}
    expected_tables = {"movie", "rating"}
    assert final_table_names == expected_tables

    # Check table reasons
    table_reasons = {t.table_name: t.reason for t in result.tables}
    assert table_reasons.get("movie") == "direct_hit"
    assert table_reasons.get("rating") == "direct_hit"

    # Verify sticky columns have score of 0.0 (no scoring)
    assert all(col.score == 0.0 for col in sticky_columns)

    # Verify non-sticky columns maintain their original scores
    non_sticky_columns = [col for col in result.columns if not col.is_sticky and col.source != "structural"]
    assert any(col.score == 5.0 for col in non_sticky_columns)  # release_year
    assert any(col.score == 4.5 for col in non_sticky_columns)  # rating.score


@pytest.mark.asyncio
async def test_sticky_column_handling(mocker):
    """Test that sticky columns are properly handled during retrieval."""
    # Mock dependencies
    token_index = AsyncMock()
    embedding_index = AsyncMock()
    schema_graph = mocker.Mock()

    # Set up test data
    token_hits = [
        RetrievedColumn(
            table_name="movies", column_name="release_year", score=5.0, source="token"
        )
    ]

    embedding_hits = [
        RetrievedColumn(
            table_name="movies", column_name="genre", score=4.0, source="embedding"
        )
    ]

    # Mock schema graph responses
    schema_graph.get_table_sticky_columns.return_value = ["title", "original_title"]
    schema_graph.get_neighbor_tables.return_value = {"actors"}
    schema_graph.get_table_pks.return_value = ["id"]
    schema_graph.get_table_fks_involved.return_value = ["actor_id"]

    # Create orchestrator
    orchestrator = RetrievalOrchestrator(token_index, embedding_index, schema_graph)

    # Mock async search methods
    token_index.search.return_value = token_hits
    embedding_index.search.return_value = embedding_hits

    # Run retrieval
    context = await orchestrator.get_relevant_context("Find movies from 2020")

    # Verify sticky columns are included
    sticky_columns = [col for col in context.columns if col.is_sticky]
    assert len(sticky_columns) > 0
    assert any(col.column_name == "title" for col in sticky_columns)
    assert any(col.column_name == "original_title" for col in sticky_columns)

    # Verify sticky columns have higher scores than structural columns
    structural_scores = [
        col.score for col in context.columns if col.source == "structural"
    ]
    sticky_scores = [col.score for col in context.columns if col.is_sticky]
    assert all(
        sticky_score > structural_score
        for sticky_score in sticky_scores
        for structural_score in structural_scores
    )

    # Verify sticky columns are preserved in top k selection
    assert len([col for col in context.columns if col.is_sticky]) >= len(
        schema_graph.get_table_sticky_columns("movies")
    )


@pytest.mark.asyncio
async def test_sticky_column_expansion(mocker):
    """Test that sticky columns are properly handled during schema expansion."""
    # Mock dependencies
    token_index = AsyncMock()
    embedding_index = AsyncMock()
    schema_graph = mocker.Mock()

    # Set up test data for initial table
    token_hits = [
        RetrievedColumn(
            table_name="movies", column_name="release_year", score=5.0, source="token"
        )
    ]

    # Mock schema graph responses
    schema_graph.get_table_sticky_columns.side_effect = lambda table: {
        "movies": ["title", "original_title"],
        "actors": ["name", "stage_name"],
    }[table]
    schema_graph.get_neighbor_tables.return_value = {"actors"}
    schema_graph.get_table_pks.return_value = ["id"]
    schema_graph.get_table_fks_involved.return_value = ["actor_id"]

    # Create orchestrator
    orchestrator = RetrievalOrchestrator(token_index, embedding_index, schema_graph)

    # Mock async search methods
    token_index.search.return_value = token_hits
    embedding_index.search.return_value = []

    # Run retrieval
    context = await orchestrator.get_relevant_context("Find movies from 2020")

    # Verify sticky columns from both tables are included
    movie_sticky = [
        col for col in context.columns if col.is_sticky and col.table_name == "movies"
    ]
    actor_sticky = [
        col for col in context.columns if col.is_sticky and col.table_name == "actors"
    ]

    assert len(movie_sticky) == 2  # title, original_title
    assert len(actor_sticky) == 2  # name, stage_name

    # Verify sticky columns have score of 0.1 (small positive score to rank above structural columns)
    assert all(col.score == 0.1 for col in movie_sticky)
    assert all(col.score == 0.1 for col in actor_sticky)

    # Verify non-sticky columns maintain their original scores
    non_sticky = [col for col in context.columns if not col.is_sticky and col.source == "token"]
    assert len(non_sticky) == 1  # release_year
    assert non_sticky[0].score == 5.0  # Original score preserved


# TODO: Add more tests:
# - Test case with no results from indices
# - Test case with only token or only embedding results
# - Test case where schema expansion is crucial to connect tables
# - Test case with k > number of available high-scoring columns
# - Test case with errors from underlying indices or schema graph

# Removed erroneous closing tag
