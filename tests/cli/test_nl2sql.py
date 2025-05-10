"""Tests for NL2SQL pipeline CLI module."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sens.cli.nl2sql import NL2SQLPipeline
from sens.execution.types import QueryResult
from sens.llm.models import Intent, TokenUsage
from sens.postprocessing.response_builder import FinalResponse


@pytest.fixture
def mock_schema_graph():
    """Mock schema graph instance."""
    with patch("sens.cli.nl2sql.SchemaGraph") as mock:
        instance = MagicMock()
        instance.schema_path = "/tmp/schema.json"
        mock.get_instance.return_value = instance
        yield instance


@pytest.fixture
def mock_token_index():
    """Mock token index adapter."""
    mock = MagicMock()
    mock.initialize = AsyncMock()
    mock.search = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def mock_embedding_search():
    """Mock embedding search adapter."""
    mock = MagicMock()
    mock.initialize = AsyncMock()
    mock.search_similar = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def mock_intent_extractor():
    """Mock intent extractor."""
    mock = MagicMock()
    mock.extract = AsyncMock(
        return_value=Intent(
            query_type="lookup",
            tables=["users"],
            operations=[],
            conditions=[],
            confidence=0.9,
        )
    )
    return mock


@pytest.fixture
def mock_sql_generator():
    """Mock SQL generator."""
    mock = MagicMock()
    mock.generate = AsyncMock(
        return_value=MagicMock(
            sql="SELECT * FROM users",
            tables_used=["users"],
            columns_used={"users": ["id", "name"]},
            model_used="gpt-4",
            generation_ms=100,
            token_usage=TokenUsage(prompt_tokens=50, completion_tokens=20),
        )
    )
    return mock


@pytest.fixture
def mock_sql_executor():
    """Mock SQL executor."""
    mock = MagicMock()
    mock.execute = MagicMock(
        return_value=QueryResult(
            columns=["id", "name"],
            rows=[[1, "Alice"], [2, "Bob"]],
            row_count=2,
        )
    )
    return mock


@pytest.fixture
def mock_response_builder():
    """Mock response builder."""
    mock = MagicMock()
    mock.build = MagicMock(
        return_value=FinalResponse(
            summary="Found 2 users.",
            table_preview=[[1, "Alice"], [2, "Bob"]],
            row_count=2,
            sql="SELECT * FROM users",
            execution_time_ms=50.0,
            generated_at="2024-03-14T12:00:00Z",
            metadata={
                "intent_type": "lookup",
                "columns": ["id", "name"],
                "total_rows": 2,
                "truncated": False,
            },
        )
    )
    return mock


@pytest.fixture
async def pipeline(
    mock_schema_graph,
    mock_token_index,
    mock_embedding_search,
    mock_intent_extractor,
    mock_sql_generator,
    mock_sql_executor,
    mock_response_builder,
):
    """Create a pipeline instance with mocked components."""
    with (
        patch("sens.cli.nl2sql.TokenIndexCLIAdapter") as mock_token_cls,
        patch("sens.cli.nl2sql.EmbeddingSearchCLIAdapter") as mock_embedding_cls,
        patch("sens.cli.nl2sql.SQLExecutor") as mock_executor_cls,
        patch("sens.cli.nl2sql.ResponseBuilder") as mock_builder_cls,
    ):
        mock_token_cls.return_value = mock_token_index
        mock_embedding_cls.return_value = mock_embedding_search
        mock_executor_cls.return_value = mock_sql_executor
        mock_builder_cls.return_value = mock_response_builder

        pipeline = NL2SQLPipeline()
        await pipeline.initialize()
        return pipeline


@pytest.mark.asyncio
async def test_pipeline_process_question_success(pipeline):
    """Test successful question processing through the pipeline."""
    # Process a test question
    result = await pipeline.process_question("List all users")

    assert result["status"] == "success"
    assert result["summary"] == "Found 2 users."
    assert result["sql"] == "SELECT * FROM users"
    assert result["result"]["preview"] == [(1, "Alice"), (2, "Bob")]
    assert result["result"]["row_count"] == 2
    assert result["metadata"]["tables_used"] == ["users"]
    assert result["metadata"]["columns_used"] == {"users": ["id", "name"]}
    assert result["metadata"]["model_used"] == "gpt-4"
    assert result["metadata"]["generation_ms"] == 100
    assert result["metadata"]["execution_ms"] > 0
    assert result["metadata"]["intent_type"] == "lookup"


@pytest.mark.asyncio
async def test_pipeline_process_question_needs_clarification(pipeline):
    """Test question processing that requires clarification."""
    # Mock intent validation to request clarification
    pipeline.intent_validator.validate = MagicMock(
        return_value=MagicMock(
            needs_clarification=True,
            message="Please be more specific",
            reason="ambiguous_intent",
        )
    )

    # Process a test question
    result = await pipeline.process_question("Show me everything")

    assert result["status"] == "clarification_needed"
    assert result["message"] == "Please be more specific"
    assert result["reason"] == "ambiguous_intent"


@pytest.mark.asyncio
async def test_pipeline_process_question_execution_error(pipeline):
    """Test error handling during query execution."""
    # Mock executor to return error
    pipeline.sql_executor.execute = MagicMock(
        return_value=QueryResult(
            columns=[],
            rows=[],
            row_count=0,
            error="Table 'users' does not exist",
        )
    )

    # Process a test question
    result = await pipeline.process_question("List all users")

    assert result["status"] == "error"
    assert "Table 'users' does not exist" in result["message"]
    assert result["sql"] == "SELECT * FROM users"


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
