"""Unit tests for the ResponseBuilder class."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from openai import OpenAI

from sens.execution.types import QueryResult
from sens.llm.models import Intent, TokenUsage
from sens.postprocessing.response_builder import FinalResponse, ResponseBuilder
from sens.settings import Settings, get_settings


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    return Settings(
        openrouter_api_key="test-key",
        openrouter_base_url="https://api.test.com",
        openrouter_referer="https://test.com",
        openrouter_title="Test",
    )


@pytest.fixture
def mock_openai_client():
    """Create a mock OpenAI client."""
    mock_client = Mock(spec=OpenAI)
    # Set up the chat.completions attribute structure
    mock_client.chat = Mock()
    mock_client.chat.completions = Mock()
    mock_client.chat.completions.create = Mock()
    return mock_client


@pytest.fixture
def response_builder(mock_settings, mock_openai_client, tmp_path):
    """Create a ResponseBuilder instance with mocked dependencies."""
    # Create test prompt directory and file
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    prompt_file = prompt_dir / "summary.prompt.txt"
    prompt_file.write_text(
        """
You are a professional data analyst summarizing SQL query results.
Question: {{ question }}
SQL: {{ sql }}
Data: {{ result.rows[:5] }}
"""
    )

    with patch(
        "sens.postprocessing.response_builder.get_settings", return_value=mock_settings
    ):
        builder = ResponseBuilder(
            prompt_dir=prompt_dir, prompt_filename=prompt_file.name
        )
        builder.client = mock_openai_client
        return builder


@pytest.fixture
def sample_query_result():
    """Create a sample query result for testing."""
    return QueryResult(
        columns=["title", "release_year"],
        rows=[
            {"title": "Oppenheimer", "release_year": 2023},
            {"title": "Barbie", "release_year": 2023},
            {"title": "Dune: Part Two", "release_year": 2024},
        ],
        row_count=3,
    )


@pytest.fixture
def sample_intent():
    """Create a sample intent for testing."""
    return Intent(
        query_type="lookup",
        tables=["movies"],
        operations=[],
        conditions=[],
        confidence=0.9,
    )


def test_empty_response_creation():
    """Test creating an empty response."""
    sql = "SELECT * FROM movies WHERE year = 2025"
    response = FinalResponse.create_empty_response(sql)

    assert response.summary == "No matching records were found."
    assert response.table_preview == []
    assert response.row_count == 0
    assert response.sql == sql
    assert response.metadata["status"] == "empty"
    assert isinstance(response.generated_at, str)


def test_successful_response_building(
    response_builder, sample_query_result, sample_intent, mock_openai_client
):
    """Test building a response with successful LLM completion."""
    # Mock LLM response
    mock_completion = Mock()
    mock_completion.choices = [Mock()]
    mock_completion.choices[0].message.content = (
        "Found 3 movies released between 2023 and 2024."
    )
    mock_completion.usage.prompt_tokens = 50
    mock_completion.usage.completion_tokens = 20
    mock_openai_client.chat.completions.create.return_value = mock_completion

    response = response_builder.build(
        question="What movies were released recently?",
        intent=sample_intent,
        result=sample_query_result,
        sql="SELECT title, release_year FROM movies",
        execution_time_ms=42.5,
    )

    assert "Found 3 movies" in response.summary
    assert len(response.table_preview) == 3
    assert response.row_count == 3
    assert response.execution_time_ms == 42.5
    assert response.metadata["intent_type"] == "lookup"
    assert not response.metadata["truncated"]


def test_failed_llm_completion(
    response_builder, sample_query_result, sample_intent, mock_openai_client
):
    """Test fallback behavior when LLM completion fails."""
    # Mock LLM failure
    mock_openai_client.chat.completions.create.side_effect = Exception("LLM Error")

    response = response_builder.build(
        question="What movies were released recently?",
        intent=sample_intent,
        result=sample_query_result,
        sql="SELECT title, release_year FROM movies",
    )

    expected_msg = (
        "Found 3 records matching your query. Please see the data preview for details."
    )
    assert response.summary == expected_msg
    assert len(response.table_preview) == 3


def test_response_json_serialization(sample_query_result):
    """Test that FinalResponse can be properly serialized to JSON."""
    response = FinalResponse(
        summary="Test summary",
        table_preview=sample_query_result.rows,
        row_count=3,
        sql="SELECT * FROM movies",
        execution_time_ms=100.0,
        generated_at=datetime.utcnow().isoformat(),
        metadata={"intent_type": "lookup"},
    )

    json_str = response.to_json()
    parsed = json.loads(json_str)

    assert parsed["summary"] == "Test summary"
    assert len(parsed["table_preview"]) == 3
    assert parsed["row_count"] == 3


def test_prompt_generation_by_intent(response_builder, sample_query_result):
    """Test that different intents generate appropriate prompts."""
    intents = [
        Intent(
            query_type="aggregation",
            tables=["movies"],
            operations=["COUNT"],
            confidence=0.9,
        ),
        Intent(
            query_type="relationship",
            tables=["movies", "directors"],
            operations=[],
            confidence=0.9,
        ),
        Intent(query_type="lookup", tables=["movies"], operations=[], confidence=0.9),
    ]

    for intent in intents:
        prompt = response_builder._build_summary_prompt(
            question="Test question",
            sql="SELECT * FROM movies",
            result=sample_query_result,
            intent=intent,
        )

        assert "Test question" in prompt
        assert "SELECT * FROM movies" in prompt
        assert str(sample_query_result.rows[:5]) in prompt


def test_json_filter_in_template(response_builder, sample_query_result):
    """Test that the JSON filter works correctly in template rendering."""
    # Create a test template that uses the json filter
    test_template = """
Data: {{ result.rows | json }}
"""
    # Write the test template to the temporary file
    with open(response_builder.prompt_path, "w") as f:
        f.write(test_template)

    prompt = response_builder._build_summary_prompt(
        question="Test question",
        sql="SELECT * FROM movies",
        result=sample_query_result,
        intent=Intent(
            query_type="lookup", tables=["movies"], operations=[], confidence=0.9
        ),
    )

    # Verify that the JSON was properly rendered
    assert "Data:" in prompt
    # Parse the JSON from the rendered template to verify it's valid
    try:
        rendered_json = prompt.split("Data:")[1].strip()
        parsed_data = json.loads(rendered_json)
        assert isinstance(parsed_data, list)
        assert len(parsed_data) == len(sample_query_result.rows)
    except json.JSONDecodeError:
        pytest.fail("Template did not produce valid JSON")


def test_large_result_truncation(response_builder, sample_intent, mock_openai_client):
    """Test that large results are properly truncated in preview."""
    large_result = QueryResult(
        columns=["id"], rows=[{"id": i} for i in range(10)], row_count=10
    )

    # Mock LLM response
    mock_completion = Mock()
    mock_completion.choices = [Mock()]
    mock_completion.choices[0].message.content = "Test summary"
    mock_completion.usage.prompt_tokens = 50
    mock_completion.usage.completion_tokens = 20
    mock_openai_client.chat.completions.create.return_value = mock_completion

    response = response_builder.build(
        question="Test question",
        intent=sample_intent,
        result=large_result,
        sql="SELECT id FROM large_table",
    )

    assert len(response.table_preview) == 5  # Should be truncated
    assert response.row_count == 10  # But full count preserved
    assert response.metadata["truncated"] is True


def test_response_builder_initialization(tmp_path):
    """Test ResponseBuilder initialization with settings."""
    # Create test prompt
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    prompt_file = prompt_dir / "summary.prompt.txt"
    prompt_file.write_text("Test prompt")

    with patch("sens.postprocessing.response_builder.get_settings") as mock_settings:
        mock_settings.return_value = Settings(
            openrouter_api_key="test-key",
            openrouter_base_url="https://api.test.com",
            openrouter_referer="https://test.com",
            openrouter_title="Test",
        )

        builder = ResponseBuilder(
            prompt_dir=prompt_dir, prompt_filename=prompt_file.name
        )

        assert builder.prompt_path.exists()
        assert builder.jinja_env is not None
        assert builder.config.primary_model == "openai/gpt-4"  # Default from settings
        assert builder.config.max_tokens == 300  # Default value
        assert builder.config.temperature == 0.3  # Default value


def test_empty_result_handling(mock_settings, mock_openai_client, tmp_path):
    """Test handling of empty query results."""
    # Create test prompt directory and file
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    prompt_file = prompt_dir / "summary.prompt.txt"
    prompt_file.write_text("Test prompt")

    with patch(
        "sens.postprocessing.response_builder.get_settings", return_value=mock_settings
    ):
        builder = ResponseBuilder(
            prompt_dir=prompt_dir, prompt_filename=prompt_file.name
        )
        builder.client = mock_openai_client

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
