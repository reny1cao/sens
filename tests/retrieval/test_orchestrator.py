import logging
from unittest.mock import MagicMock

import pytest

from src.sens.retrieval.models import RetrievedColumn, RetrievedContext, RetrievedTable

# Assume these are the correct import paths
from src.sens.retrieval.orchestrator import RetrievalOrchestrator

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
    },
    "rating": {
        "pks": ["id"],
        "fks_involved": {"movie_id": [("movie", "id")]},
        "neighbors": {"movie"},
    },
    # Add other tables if needed for more complex tests
    "actor": {"pks": ["id"], "fks_involved": {}, "neighbors": set()},
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

    graph.get_neighbor_tables.side_effect = get_neighbor_tables
    graph.get_table_pks.side_effect = get_table_pks
    graph.get_table_fks_involved.side_effect = get_table_fks_involved
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
                    score=0.9,
                    source="token",
                ),
                RetrievedColumn(
                    table_name="movie", column_name="title", score=0.7, source="token"
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
                    score=0.85,
                    source="embedding",
                ),
                RetrievedColumn(
                    table_name="movie",
                    column_name="title",
                    score=0.75,
                    source="embedding",
                ),  # Higher score than token
                RetrievedColumn(
                    table_name="actor",
                    column_name="name",
                    score=0.6,
                    source="embedding",
                ),  # Lower score, potentially filtered out
            ]
        return []

    index.search.side_effect = search
    return index


# --- Test Cases ---


def test_retrieval_orchestrator_basic(
    mock_token_index, mock_embedding_index, mock_schema_graph, caplog
):
    """Tests the orchestrator with the query from AC6.

    Verifies merging, schema expansion (movie<->rating), ranking, and final context.
    Also checks for the structured log message.
    """
    caplog.set_level(logging.INFO)

    orchestrator = RetrievalOrchestrator(
        token_index=mock_token_index,
        embedding_index=mock_embedding_index,
        schema_graph=mock_schema_graph,
    )

    k = 2  # Request top 2 columns initially
    result: RetrievedContext = orchestrator.get_relevant_context(TEST_QUERY, k=k)

    assert result.query == TEST_QUERY

    # Verify selected columns (top k=2 based on score after merge)
    # Expected order after merge:
    # 1. movie.release_year (0.9, token)
    # 2. rating.score (0.85, embedding)
    # 3. movie.title (0.75, embedding - higher score kept)
    # 4. actor.name (0.6, embedding)
    # --- Schema expansion columns (score 0.0) ---
    # movie.id (PK)
    # rating.id (PK)
    # rating.movie_id (FK)
    # Expected top 2 selected: movie.release_year, rating.score
    assert len(result.columns) == k
    selected_col_keys = {(c.table_name, c.column_name) for c in result.columns}
    expected_top_cols = {("movie", "release_year"), ("rating", "score")}
    assert selected_col_keys == expected_top_cols
    assert (
        result.columns[0].table_name == "movie"
        and result.columns[0].column_name == "release_year"
    )
    assert (
        result.columns[1].table_name == "rating"
        and result.columns[1].column_name == "score"
    )

    # Verify included tables based on selected columns and expansion
    # Selected columns are from 'movie' and 'rating'. Expansion connects them.
    # Should include 'movie' and 'rating'. Actor table should not be included.
    final_table_names = {t.table_name for t in result.tables}
    expected_tables = {"movie", "rating"}
    assert final_table_names == expected_tables

    # Check table reasons (might need refinement based on exact expansion logic)
    table_reasons = {t.table_name: t.reason for t in result.tables}
    assert (
        table_reasons.get("movie") == "direct_hit"
    )  # Because movie.release_year was a hit
    assert table_reasons.get("rating") == "direct_hit"  # Because rating.score was a hit
    # (or 'join_expansion' if only movie was hit initially - test depends on mock data)

    # Verify PK/FK columns from selected tables are present *if* they were added during expansion
    # (Need to inspect the intermediate all_involved_columns if needed, but selection is primary check)
    # Let's check the log instead for simplicity

    # Verify logging (AC5)
    assert len(caplog.records) > 0
    found_log = False
    for record in caplog.records:
        # Check if the message is a dictionary and has the correct phase
        if (
            record.levelname == "INFO"
            and isinstance(record.msg, dict)
            and record.msg.get("phase") == "retrieval_orchestration"
        ):
            log_dict = record.msg
            assert log_dict["question"] == TEST_QUERY
            assert log_dict["k_requested"] == k
            # Check structure of final context in log
            assert "selected_columns" in log_dict["final_context"]
            assert "included_tables" in log_dict["final_context"]
            log_selected_cols = set(
                (c[0], c[1]) for c in log_dict["final_context"]["selected_columns"]
            )
            log_included_tables = set(
                t[0] for t in log_dict["final_context"]["included_tables"]
            )
            assert log_selected_cols == expected_top_cols
            assert log_included_tables == expected_tables
            found_log = True
            break  # Found the log message, exit loop

    assert (
        found_log
    ), "Structured log message for retrieval_orchestration not found or malformed."


# TODO: Add more tests:
# - Test case with no results from indices
# - Test case with only token or only embedding results
# - Test case where schema expansion is crucial to connect tables
# - Test case with k > number of available high-scoring columns
# - Test case with errors from underlying indices or schema graph

# Removed erroneous closing tag
