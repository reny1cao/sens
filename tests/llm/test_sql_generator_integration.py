"""Integration tests for the SQL Generator."""

import json
from typing import Dict, List, Set
from unittest.mock import AsyncMock, MagicMock

import pytest

from sens.llm.intent_validator import ValidIntent
from sens.llm.models import Intent, QueryType, TokenUsage
from sens.llm.sql_generator import SQLGenerationError, SQLGenerator
from sens.schema.graph import SchemaGraph
from sens.settings import Settings


@pytest.fixture
def mock_settings_with_llm_config() -> Dict:
    """Mock settings for testing."""
    return {
        "llm": {
            "sql_generator": {
                "primary_model": "openai/gpt-4-test",
                "fallback_model": "openai/gpt-3.5-turbo-test",
            },
        },
        "openrouter": {
            "api_key": "sk-test-api-key",  # Valid format for OpenRouter API key
            "base_url": "https://openrouter.ai/api/v1",
            "headers": {
                "HTTP-Referer": "http://localhost",
            },
        },
    }


@pytest.fixture
def mock_schema_graph():
    """Mock schema graph for testing."""
    mock = MagicMock(spec=SchemaGraph)
    # Set up default behaviors
    mock.get_referenced_tables.return_value = set()
    mock.get_referencing_tables.return_value = set()
    mock.get_table_columns.return_value = ["id", "title"]
    mock.get_table_pks.return_value = ["id"]
    mock.get_column_comment.return_value = None
    mock.get_table_fks_involved.return_value = []
    return mock


@pytest.fixture
def sql_generator_instance(mocker, mock_settings_with_llm_config, mock_schema_graph):
    """Fixture to create an SQLGenerator instance with mocked dependencies."""
    # Patch settings functions used by SQLGenerator
    mocker.patch(
        "sens.llm.sql_generator.get_settings",
        return_value=Settings(**mock_settings_with_llm_config),
    )

    # Patch SchemaGraph.get_instance to return our mock
    mocker.patch(
        "sens.schema.graph.SchemaGraph.get_instance", return_value=mock_schema_graph
    )

    # Create SQLGenerator instance
    generator = SQLGenerator()

    # Mock the OpenAI client
    generator.client = AsyncMock()

    return generator


@pytest.fixture
def basic_intent():
    """Fixture for a basic intent."""
    return ValidIntent(
        original_intent=Intent(
            query_type=QueryType.LOOKUP,
            tables=["movie"],
            columns=["title"],
            filters={},
            confidence=1.0,
        ),
        enhanced_metadata={},
    )


@pytest.mark.asyncio
async def test_generate_simple_select_query(
    sql_generator_instance: SQLGenerator,
    mock_schema_graph,
    basic_intent,
):
    """Test generating a simple SELECT query."""
    # Mock LLM response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[
        0
    ].message.content = """```sql
    SELECT movie.title FROM movie;
    ```"""
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 30

    sql_generator_instance.client.chat.completions.create = AsyncMock(
        return_value=mock_response
    )

    # Execute
    result = await sql_generator_instance.generate("Show all movies", basic_intent)

    # Verify
    assert "SELECT movie.title" in result.sql
    assert "FROM movie" in result.sql
    assert result.model_used == sql_generator_instance.primary_model
    assert result.token_usage.prompt_tokens == 100
    assert result.token_usage.completion_tokens == 30


@pytest.mark.asyncio
async def test_generate_handles_insufficient_schema_error(
    sql_generator_instance: SQLGenerator,
    mock_schema_graph,
):
    """Verify that SQLGenerator correctly handles INSUFFICIENT_SCHEMA errors."""
    # Setup test data
    question = "Show movie titles and their start dates"
    intent = ValidIntent(
        original_intent=Intent(
            query_type=QueryType.LOOKUP,
            tables=["movie"],
            columns=["title", "start_date"],
            filters={},
            confidence=1.0,
        ),
        enhanced_metadata={},
    )

    # Mock the error JSON that LLM should return
    error_json = {
        "error_type": "INSUFFICIENT_SCHEMA",
        "missing_elements": ["view_summary.start_date"],
        "reason": "The column 'view_summary.start_date' is required but not available in the schema.",
    }

    # Mock LLM response to return the error JSON
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps(error_json)
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 30

    sql_generator_instance.client.chat.completions.create = AsyncMock(
        return_value=mock_response
    )

    # Execute and verify
    with pytest.raises(SQLGenerationError) as exc_info:
        await sql_generator_instance.generate(question, intent)

    # Verify error details
    assert exc_info.value.error_type == "INSUFFICIENT_SCHEMA"
    assert "missing_elements" in exc_info.value.details
    assert exc_info.value.details["missing_elements"] == ["view_summary.start_date"]


@pytest.mark.asyncio
async def test_extract_sql_from_different_markdown_formats(
    sql_generator_instance: SQLGenerator,
    mock_schema_graph,
    basic_intent,
):
    """Test SQL extraction from various markdown code block formats."""
    test_cases = [
        # Standard markdown SQL block
        """```sql
        SELECT movie.title FROM movie;
        ```""",
        # Uppercase SQL marker
        """```SQL
        SELECT movie.title FROM movie;
        ```""",
        # No language marker
        """```
        SELECT movie.title FROM movie;
        ```""",
        # Direct SQL without markdown
        "SELECT movie.title FROM movie;",
        # SQL with extra text
        """Here's your query:
        ```sql
        SELECT movie.title FROM movie;
        ```
        This will show all movie titles.""",
    ]

    for sql_response in test_cases:
        # Mock LLM response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = sql_response
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 30

        sql_generator_instance.client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        # Execute
        result = await sql_generator_instance.generate("Show all movies", basic_intent)

        # Verify the SQL was correctly extracted
        sql_lower = result.sql.lower()
        assert "select movie.title" in sql_lower
        assert "from movie" in sql_lower


@pytest.mark.asyncio
async def test_generate_complex_join_query(
    sql_generator_instance: SQLGenerator,
    mock_schema_graph,
):
    """Test generating a complex query with joins."""
    # Setup test data
    question = "Show movie titles and their view counts"
    intent = ValidIntent(
        original_intent=Intent(
            query_type=QueryType.LOOKUP,
            tables=["movie", "view_summary"],
            columns=["title", "views"],
            filters={},
            confidence=1.0,
        ),
        enhanced_metadata={},
    )

    # Mock schema graph to return join-related data
    mock_schema_graph.get_table_fks_involved.return_value = ["movie_id"]
    mock_schema_graph.get_table_columns.side_effect = lambda table: {
        "movie": ["id", "title"],
        "view_summary": ["id", "movie_id", "views"],
    }[table]

    # Mock LLM response with a join query
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[
        0
    ].message.content = """```sql
    SELECT m.title, vs.views
    FROM movie m
    JOIN view_summary vs ON vs.movie_id = m.id;
    ```"""
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 30

    sql_generator_instance.client.chat.completions.create = AsyncMock(
        return_value=mock_response
    )

    # Execute
    result = await sql_generator_instance.generate(question, intent)

    # Verify
    assert "SELECT m.title, vs.views" in result.sql
    assert "JOIN view_summary" in result.sql
    assert "movie_id = m.id" in result.sql
    assert len(result.tables_used) == 2
    assert "movie" in result.tables_used
    assert "view_summary" in result.tables_used


@pytest.mark.asyncio
async def test_generate_with_validation_error(
    sql_generator_instance: SQLGenerator,
    mock_schema_graph,
):
    """Test handling of SQL validation errors."""
    # Setup test data
    question = "Show all movies and invalid_column"
    intent = ValidIntent(
        original_intent=Intent(
            query_type=QueryType.LOOKUP,
            tables=["movie"],
            columns=["title", "invalid_column"],
            filters={},
            confidence=1.0,
        ),
        enhanced_metadata={},
    )

    # Mock LLM response with invalid column
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[
        0
    ].message.content = """```sql
    SELECT movie.title, movie.invalid_column
    FROM movie;
    ```"""
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 30

    sql_generator_instance.client.chat.completions.create = AsyncMock(
        return_value=mock_response
    )

    # Execute and verify
    with pytest.raises(SQLGenerationError) as exc_info:
        await sql_generator_instance.generate(question, intent)

    assert exc_info.value.error_type == "SQL_VALIDATION_ERROR"
    assert "invalid_column" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_generate_with_llm_api_error(
    sql_generator_instance: SQLGenerator,
    mock_schema_graph,
    basic_intent,
):
    """Test handling of LLM API errors with fallback."""
    # Mock primary model to fail
    primary_error = Exception("API Error")

    # Mock fallback model to succeed
    fallback_response = MagicMock()
    fallback_response.choices = [MagicMock()]
    # Create a mock message with proper __str__ behavior
    message = MagicMock()
    message.content = "SELECT movie.title FROM movie;"
    message.__str__.return_value = message.content
    fallback_response.choices[0].message = message
    fallback_response.usage.prompt_tokens = 100
    fallback_response.usage.completion_tokens = 30

    # Set up the mock to fail for primary model and succeed for fallback
    sql_generator_instance.client.chat.completions.create = AsyncMock(
        side_effect=[primary_error, fallback_response]
    )

    # Execute
    result = await sql_generator_instance.generate("Show all movies", basic_intent)

    # Verify fallback was used
    assert result.model_used == sql_generator_instance.fallback_model
    assert "SELECT movie.title" in result.sql


@pytest.mark.asyncio
async def test_generate_with_multiple_code_blocks(
    sql_generator_instance: SQLGenerator,
    mock_schema_graph,
    basic_intent,
):
    """Test handling of responses with multiple SQL code blocks."""
    # Mock LLM response with multiple code blocks
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[
        0
    ].message.content = """Here are two equivalent queries:
    ```sql
    SELECT movie.title FROM movie;
    ```
    Or with an alias:
    ```sql
    SELECT m.title FROM movie m;
    ```"""
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 30

    sql_generator_instance.client.chat.completions.create = AsyncMock(
        return_value=mock_response
    )

    # Execute
    result = await sql_generator_instance.generate("Show all movies", basic_intent)

    # Verify it uses the first SQL block
    assert "SELECT movie.title FROM movie" in result.sql
    assert "m.title" not in result.sql
