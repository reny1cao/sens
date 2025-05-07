"""Tests for the NL2SQL CLI module."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sens.cli.nl2sql import (
    EmbeddingSearchCLIAdapter,
    NL2SQLPipeline,
    TokenIndexCLIAdapter,
)


@pytest.fixture
def mock_schema_graph():
    """Mock SchemaGraph instance."""
    with patch("sens.cli.nl2sql.SchemaGraph") as mock:
        mock_instance = MagicMock()
        mock.get_instance.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_token_index():
    """Mock TokenIndexCLIAdapter."""
    mock = AsyncMock(spec=TokenIndexCLIAdapter)
    return mock


@pytest.fixture
def mock_embedding_search():
    """Mock EmbeddingSearchCLIAdapter."""
    mock = AsyncMock(spec=EmbeddingSearchCLIAdapter)
    return mock


@pytest.fixture
def mock_intent_extractor():
    """Mock IntentExtractor."""
    with patch("sens.cli.nl2sql.IntentExtractor") as mock:
        mock_instance = AsyncMock()
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_sql_generator():
    """Mock SQLGenerator."""
    with patch("sens.cli.nl2sql.SQLGenerator") as mock:
        mock_instance = AsyncMock()
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
async def pipeline(
    mock_schema_graph,
    mock_token_index,
    mock_embedding_search,
    mock_intent_extractor,
    mock_sql_generator,
):
    """Create a pipeline instance with mocked components."""
    with (
        patch("sens.cli.nl2sql.TokenIndexCLIAdapter") as mock_token_cls,
        patch("sens.cli.nl2sql.EmbeddingSearchCLIAdapter") as mock_embedding_cls,
    ):

        mock_token_cls.return_value = mock_token_index
        mock_embedding_cls.return_value = mock_embedding_search

        pipeline = NL2SQLPipeline()
        await pipeline.initialize()
        return pipeline


@pytest.mark.asyncio
async def test_pipeline_initialization(pipeline):
    """Test that pipeline initializes all components correctly."""
    assert pipeline.schema_graph is not None
    assert pipeline.token_index is not None
    assert pipeline.embedding_search is not None
    assert pipeline.orchestrator is not None


@pytest.mark.asyncio
async def test_pipeline_process_question_success(pipeline):
    """Test successful question processing through the pipeline."""
    # Mock the orchestrator's get_relevant_context
    pipeline.orchestrator.get_relevant_context = AsyncMock(
        return_value=MagicMock(tables=["users", "orders"])
    )

    # Mock schema extraction
    pipeline.schema_extractor.format_for_llm = MagicMock(return_value="mock schema")

    # Mock intent extraction
    mock_intent = MagicMock()
    pipeline.intent_extractor.extract.return_value = mock_intent

    # Mock intent validation
    mock_validated_intent = MagicMock(needs_clarification=False)
    pipeline.intent_validator.validate = MagicMock(return_value=mock_validated_intent)

    # Mock SQL generation
    mock_sql_result = MagicMock(
        sql="SELECT * FROM users",
        tables_used=["users"],
        columns_used={"users": ["id", "name"]},
        model_used="gpt-4",
        generation_ms=100,
        token_usage=None,
    )
    pipeline.sql_generator.generate.return_value = mock_sql_result

    # Process a test question
    result = await pipeline.process_question("List all users")

    assert result["status"] == "success"
    assert result["sql"] == "SELECT * FROM users"
    assert result["metadata"]["tables_used"] == ["users"]
    assert result["metadata"]["columns_used"] == {"users": ["id", "name"]}


@pytest.mark.asyncio
async def test_pipeline_process_question_needs_clarification(pipeline):
    """Test question processing that requires clarification."""
    # Mock the orchestrator's get_relevant_context
    pipeline.orchestrator.get_relevant_context = AsyncMock(
        return_value=MagicMock(tables=["users"])
    )

    # Mock schema extraction
    pipeline.schema_extractor.format_for_llm = MagicMock(return_value="mock schema")

    # Mock intent extraction
    mock_intent = MagicMock()
    pipeline.intent_extractor.extract.return_value = mock_intent

    # Mock intent validation to request clarification
    mock_validated_intent = MagicMock(
        needs_clarification=True,
        clarification_request=MagicMock(
            message="Please be more specific", reason="ambiguous_intent"
        ),
    )
    pipeline.intent_validator.validate = MagicMock(return_value=mock_validated_intent)

    # Process a test question
    result = await pipeline.process_question("Show me everything")

    assert result["status"] == "clarification_needed"
    assert result["message"] == "Please be more specific"
    assert result["reason"] == "ambiguous_intent"


@pytest.mark.asyncio
async def test_pipeline_process_question_error(pipeline):
    """Test error handling during question processing."""
    # Mock the orchestrator to raise an exception
    pipeline.orchestrator.get_relevant_context = AsyncMock(
        side_effect=Exception("Failed to retrieve context")
    )

    # Process a test question
    result = await pipeline.process_question("List all users")

    assert result["status"] == "error"
    assert "Failed to retrieve context" in result["message"]
