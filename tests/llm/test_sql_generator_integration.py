from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sens.llm.models import Intent, SchemaContext, TokenUsage, ValidIntent
from sens.llm.sql_generator import GeneratedSQL, SQLGenerationError, SQLGenerator
from sens.settings import Settings


@pytest.fixture
def mock_settings_with_llm_config():
    """Fixture to provide mock settings with LLM config."""
    settings_data = {
        "llm": {
            "sql_generator": {
                "primary_model": "openai/gpt-4-test",
                "fallback_model": "openai/gpt-3.5-turbo-test",
            },
        },
        "openrouter": {  # Add a default OpenRouter config if SQLGenerator expects it
            "base_url": "https://openrouter.ai/api/v1",
            "api_key": "test_api_key",  # Placeholder
            "headers": {"HTTP-Referer": "http://localhost"},
        },
    }
    # Mock get_settings and get_llm_settings to use this data
    # This might require patching where these functions are imported in sql_generator.py
    # or providing a more comprehensive mock Settings object.
    # For now, we'll assume SQLGenerator can be instantiated and these are handled/mocked elsewhere
    # or directly in the SQLGenerator fixture.
    return settings_data


@pytest.fixture
def mock_schema_graph(mocker):
    """Fixture to mock SchemaGraph."""
    mock = mocker.MagicMock()
    mock.get_instance.return_value = mock  # Return self for get_instance
    # Define default return values for schema methods
    mock.get_table_columns.return_value = []
    mock.get_table_pks.return_value = []
    mock.get_column_comment.return_value = None
    mock.get_referenced_tables.return_value = set()
    mock.get_referencing_tables.return_value = set()
    mock.get_table_fks_involved.return_value = []
    return mock


@pytest.fixture
def sql_generator_instance(mocker, mock_settings_with_llm_config):
    """Fixture to create an SQLGenerator instance with mocked dependencies."""
    # Patch settings functions used by SQLGenerator
    mocker.patch(
        "sens.llm.sql_generator.get_settings",
        return_value=Settings(**mock_settings_with_llm_config),
    )
    mocker.patch(
        "sens.llm.sql_generator.get_llm_settings",
        return_value=mock_settings_with_llm_config["llm"],
    )

    # Patch SchemaGraph.get_instance() to return a controllable mock
    # This is important so SQLGenerator uses our mock_schema_graph
    mocker.patch("sens.schema.graph.SchemaGraph.get_instance")

    # Mock the OpenAI client directly on the SQLGenerator instance after creation
    # or patch 'openai.OpenAI' if it's easier to control its instantiation globally for tests.
    # For this example, we'll assume it's done within the test or a more specific fixture.

    generator = SQLGenerator(
        prompt_dir=Path(__file__).parent.parent.parent
        / "src/sens/llm/prompts",  # Adjust path as needed
        prompt_filename="sql_generation.prompt.txt",  # Assuming default prompt
    )
    # Mock the client after instantiation
    generator.client = AsyncMock()  # For async _call_llm
    return generator


@pytest.mark.asyncio
async def test_generate_simple_select_query(
    sql_generator_instance, mock_schema_graph, mocker
):
    """
    Test generating a simple SELECT query.
    Verifies schema interaction, prompt rendering, LLM call, and SQL extraction.
    """
    # 1. Setup Mock SchemaGraph
    # Replace the globally patched SchemaGraph.get_instance with our specific mock for this test
    # This ensures that the SQLGenerator instance uses this particular mock_schema_graph
    mocker.patch(
        "sens.schema.graph.SchemaGraph.get_instance", return_value=mock_schema_graph
    )

    mock_schema_graph.get_table_columns.return_value = ["id", "name", "email"]
    mock_schema_graph.get_table_pks.return_value = ["id"]
    # Configure other mock_schema_graph methods as needed for this test...

    # 2. Prepare Test Inputs
    question = "Show me all users"
    original_intent = Intent(
        query="Show me all users",
        query_type="SELECT",
        tables=["users"],
        columns=[],
        filters={},
        confidence=1.0,
    )
    valid_intent = ValidIntent(original_intent=original_intent, validation_passed=True)

    # 3. Configure Mock LLM Response
    expected_sql = "SELECT id, name, email FROM users;"
    mock_llm_response = MagicMock()
    mock_llm_response.choices = [MagicMock()]
    mock_llm_response.choices[0].message.content = f"```sql\n{expected_sql}\n```"
    mock_llm_response.usage.prompt_tokens = 50
    mock_llm_response.usage.completion_tokens = 20
    # Ensure the client mock is correctly configured on the instance
    sql_generator_instance.client.chat.completions.create = AsyncMock(
        return_value=mock_llm_response
    )

    # 4. Call the Method Under Test
    generated_sql_result = await sql_generator_instance.generate(question, valid_intent)

    # 5. Assertions
    assert isinstance(generated_sql_result, GeneratedSQL)
    assert generated_sql_result.sql == expected_sql
    assert generated_sql_result.tables_used == ["users"]
    assert generated_sql_result.columns_used == {
        "users": ["id", "name", "email"]
    }  # This will depend on _extract_query_metadata logic
    assert generated_sql_result.model_used == "openai/gpt-4-test"  # From mock_settings
    assert generated_sql_result.token_usage.prompt_tokens == 50
    assert generated_sql_result.token_usage.completion_tokens == 20
    assert generated_sql_result.token_usage.total_tokens == 70

    # Assert that schema methods were called
    mock_schema_graph.get_table_columns.assert_called_with("users")
    # Add more assertions for schema graph interactions if necessary

    # Assert LLM client was called
    sql_generator_instance.client.chat.completions.create.assert_called_once()
    # We could also assert the prompt passed to the LLM if needed, by inspecting the call_args


# Add more test cases here following the plan:
# - test_generate_query_with_where_clause
# - test_generate_query_with_join
# - test_generate_handles_llm_extraction_error
# - test_generate_uses_fallback_model_on_primary_failure
