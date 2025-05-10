"""Tests for the response builder module."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionMessage,
    Choice,
    CompletionUsage,
)

from sens.execution.types import QueryResult
from sens.llm.models import Intent, TokenUsage
from sens.postprocessing.response_builder import FinalResponse, ResponseBuilder
from sens.settings import Settings
from sens.settings.models import OpenRouterConfig, ResponseBuilderConfig


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    with patch("sens.postprocessing.response_builder.get_settings") as mock_settings:
        mock_settings.return_value = Settings(
            openrouter=OpenRouterConfig(
                api_key="test_key",
                base_url="https://test.openrouter.ai/v1",
                referer="https://test.sens.ai",
                title="Test Sens",
            ),
            response_builder=ResponseBuilderConfig(
                primary_model="test/gpt-4",
                fallback_model="test/gpt-3.5-turbo",
                max_tokens=300,
                temperature=0.3,
                timeout_seconds=30,
            ),
        )
        yield mock_settings


@pytest.fixture
def mock_llm_settings():
    """Mock LLM settings for testing."""
    with patch("sens.postprocessing.response_builder.get_llm_settings") as mock_llm:
        mock_llm.return_value = {
            "response_builder": {
                "primary_model": "test/gpt-4",
                "fallback_model": "test/gpt-3.5-turbo",
                "max_tokens": 300,
                "temperature": 0.3,
                "timeout_seconds": 30,
            }
        }
        yield mock_llm


@pytest.fixture
def sample_query_result():
    """Create a sample query result for testing."""
    return QueryResult(
        columns=["id", "name", "value"],
        rows=[[1, "Test 1", 100], [2, "Test 2", 200]],
        row_count=2,
    )


@pytest.fixture
def mock_openai_response():
    """Create a mock OpenAI API response."""
    return ChatCompletion(
        id="test-completion",
        model="test/gpt-4",
        object="chat.completion",
        created=int(datetime.now().timestamp()),
        choices=[
            Choice(
                finish_reason="stop",
                index=0,
                message=ChatCompletionMessage(
                    role="assistant",
                    content="Found 2 records with a total value of 300.",
                ),
            )
        ],
        usage=CompletionUsage(
            prompt_tokens=50,
            completion_tokens=20,
            total_tokens=70,
        ),
    )


def test_response_builder_initialization(mock_settings):
    """Test ResponseBuilder initialization."""
    builder = ResponseBuilder()
    assert builder.config.primary_model == "test/gpt-4"
    assert builder.config.fallback_model == "test/gpt-3.5-turbo"
    assert builder.config.max_tokens == 300
    assert builder.config.temperature == 0.3


def test_empty_result_handling(mock_settings):
    """Test handling of empty query results."""
    builder = ResponseBuilder()
    empty_result = QueryResult(columns=["id", "name"], rows=[], row_count=0)

    response = builder.build(
        question="What records match?",
        intent=Intent(
            query_type="lookup",
            tables=["test"],
            operations=[],
            conditions=[],
            confidence=0.9,
        ),
        result=empty_result,
        sql="SELECT * FROM test WHERE 1=0",
    )

    assert isinstance(response, FinalResponse)
    assert response.row_count == 0
    assert "No matching records" in response.summary
    assert response.table_preview == []


def test_successful_response_generation(
    mock_settings, mock_llm_settings, sample_query_result, mock_openai_response
):
    """Test successful response generation with LLM."""
    builder = ResponseBuilder()

    with patch.object(builder.client.chat.completions, "create") as mock_create:
        mock_create.return_value = mock_openai_response

        response = builder.build(
            question="What are the test values?",
            intent=Intent(type="lookup", confidence=0.9),
            result=sample_query_result,
            sql="SELECT * FROM test",
            execution_time_ms=100.5,
        )

        assert isinstance(response, FinalResponse)
        assert response.row_count == 2
        assert response.summary == "Found 2 records with a total value of 300."
        assert len(response.table_preview) == 2
        assert response.execution_time_ms == 100.5
        assert "lookup" in response.metadata["intent_type"]


def test_llm_failure_fallback(mock_settings, mock_llm_settings, sample_query_result):
    """Test fallback behavior when LLM calls fail."""
    builder = ResponseBuilder()

    with patch.object(builder.client.chat.completions, "create") as mock_create:
        mock_create.side_effect = Exception("API Error")

        response = builder.build(
            question="What are the test values?",
            intent=Intent(type="lookup", confidence=0.9),
            result=sample_query_result,
            sql="SELECT * FROM test",
        )

        assert isinstance(response, FinalResponse)
        assert "Found 2 records" in response.summary
        assert "data preview" in response.summary.lower()


def test_response_serialization(mock_settings):
    """Test FinalResponse serialization to JSON."""
    response = FinalResponse(
        summary="Test summary",
        table_preview=[[1, "Test 1"], [2, "Test 2"]],
        row_count=2,
        sql="SELECT * FROM test",
        execution_time_ms=100.5,
        generated_at=datetime.utcnow().isoformat(),
        metadata={"test": "metadata"},
    )

    json_str = response.to_json()
    data = json.loads(json_str)

    assert data["summary"] == "Test summary"
    assert len(data["table_preview"]) == 2
    assert data["row_count"] == 2
    assert data["execution_time_ms"] == 100.5
    assert "metadata" in data


def test_custom_config():
    """Test ResponseBuilder with custom config."""
    custom_config = ResponseBuilderConfig(
        primary_model="custom/model",
        fallback_model=None,
        max_tokens=500,
        temperature=0.5,
        timeout_seconds=60,
    )

    with patch("sens.postprocessing.response_builder.get_settings") as mock_settings:
        mock_settings.return_value = Settings(
            openrouter=OpenRouterConfig(
                api_key="test_key",
                base_url="https://test.openrouter.ai/v1",
                referer="https://test.sens.ai",
                title="Test Sens",
            ),
        )

        builder = ResponseBuilder(config=custom_config)
        assert builder.config.primary_model == "custom/model"
        assert builder.config.fallback_model is None
        assert builder.config.max_tokens == 500
        assert builder.config.temperature == 0.5
        assert builder.config.timeout_seconds == 60
