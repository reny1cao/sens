"""Integration tests for the SQL Generator with OpenRouter API.

These tests make actual API calls to OpenRouter and verify the complete functionality
of the SQL generation pipeline. Requires valid API credentials to run.
"""

import json
import os
from pathlib import Path
from typing import Dict, List

import pytest

from sens.llm.intent_validator import ValidIntent
from sens.llm.models import GeneratedSQL, Intent, QueryType, SQLGenerationError
from sens.llm.sql_generator import SQLGenerator
from sens.schema.graph import SchemaGraph
from sens.settings import Settings
from sens.settings.models import SQLGeneratorConfig

# Skip all tests if no API key is present
pytestmark = pytest.mark.skipif(
    os.getenv("SENS_OPENROUTER_API_KEY") is None,
    reason="SENS_OPENROUTER_API_KEY environment variable not set",
)

# Test Data
SAMPLE_SCHEMA = {
    "tables": {
        "users": {
            "name": "users",
            "columns": [
                {
                    "name": "id",
                    "data_type": "integer",
                    "is_nullable": False,
                    "is_primary": True,
                },
                {"name": "name", "data_type": "varchar", "is_nullable": False},
                {"name": "email", "data_type": "varchar", "is_nullable": False},
                {"name": "created_at", "data_type": "timestamp", "is_nullable": False},
            ],
            "primary_keys": ["id"],
        },
        "orders": {
            "name": "orders",
            "columns": [
                {
                    "name": "id",
                    "data_type": "integer",
                    "is_nullable": False,
                    "is_primary": True,
                },
                {"name": "user_id", "data_type": "integer", "is_nullable": False},
                {"name": "total_amount", "data_type": "decimal", "is_nullable": False},
                {"name": "created_at", "data_type": "timestamp", "is_nullable": False},
            ],
            "primary_keys": ["id"],
        },
    },
    "relationships": [
        {
            "constraint_name": "fk_orders_user",
            "from_table": "orders",
            "to_table": "users",
            "columns": [{"from_column": "user_id", "to_column": "id"}],
        }
    ],
    "metadata": {"database": "netflixdb", "extracted_at": "2024-03-20T00:00:00Z"},
}


@pytest.fixture(scope="session", autouse=True)
def reset_schema_graph():
    """Reset SchemaGraph singleton before all tests."""
    SchemaGraph.reset_instance()


@pytest.fixture(scope="session")
def schema_file(tmp_path_factory) -> Path:
    """Create a temporary schema file for testing."""
    schema_dir = tmp_path_factory.mktemp("schemas")
    schema_file = schema_dir / "schema_metadata.json"
    schema_file.write_text(json.dumps(SAMPLE_SCHEMA))
    return schema_file


@pytest.fixture(scope="session")
def schema_graph(schema_file: Path) -> SchemaGraph:
    """Initialize SchemaGraph with test schema."""
    # Since we reset the singleton, this will be the first initialization
    return SchemaGraph.get_instance(str(schema_file))


@pytest.fixture
def test_settings(schema_file: Path, monkeypatch) -> Settings:
    """Create test-specific settings."""
    settings = Settings(
        openrouter_api_key=os.getenv("SENS_OPENROUTER_API_KEY", ""),
        db_host="localhost",
        db_port=5432,
        db_name="netflixdb",
        db_user="postgres",
        db_password="",
        schema_path=schema_file,
        sql_generator=SQLGeneratorConfig(
            primary_model="anthropic/claude-3-sonnet",  # Use Claude as primary for tests
            fallback_model="openai/gpt-4o",
            max_tokens=1000,
            temperature=0.1,
        ),
    )
    # Patch global settings
    monkeypatch.setattr("sens.settings.core._settings", settings)
    return settings


@pytest.fixture
def sql_generator(test_settings: Settings, schema_graph: SchemaGraph) -> SQLGenerator:
    """Create a SQLGenerator instance configured for integration testing."""
    # Ensure schema_graph is initialized before creating SQLGenerator
    generator = SQLGenerator(max_tokens=1000, temperature=0.1)
    # Force the generator to use our test schema graph
    generator.schema = schema_graph
    return generator


@pytest.fixture
def basic_intent() -> ValidIntent:
    """Create a basic intent for simple queries."""
    intent = Intent(
        query_type=QueryType.LOOKUP,
        tables=["users"],
        operations=["SELECT"],
        conditions=[],
        confidence=0.95,
    )
    return ValidIntent(
        original_intent=intent,
        enhanced_metadata={"table_relationships": {}},
    )


@pytest.fixture
def join_intent() -> ValidIntent:
    """Create an intent for queries requiring joins."""
    intent = Intent(
        query_type=QueryType.LOOKUP,
        tables=["users", "orders"],
        operations=["COUNT", "GROUP BY"],
        conditions=["created_at > '2023-01-01'"],
        confidence=0.95,
    )
    return ValidIntent(
        original_intent=intent,
        enhanced_metadata={
            "table_relationships": {
                "orders": {"referenced_tables": ["users"]},
            }
        },
    )


@pytest.fixture
def aggregate_intent() -> ValidIntent:
    """Create an intent for aggregate queries."""
    intent = Intent(
        query_type=QueryType.AGGREGATION,  # Fixed: Using AGGREGATION instead of AGGREGATE
        tables=["orders"],
        operations=["SUM", "AVG", "GROUP BY"],
        conditions=[],
        confidence=0.95,
    )
    return ValidIntent(
        original_intent=intent,
        enhanced_metadata={
            "table_relationships": {
                "orders": {"referenced_tables": ["users"]},
            }
        },
    )


# Basic Query Tests
@pytest.mark.integration
@pytest.mark.asyncio
async def test_basic_select(sql_generator: SQLGenerator, basic_intent: ValidIntent):
    """Test basic SELECT query generation."""
    question = "Show me all users"

    result = await sql_generator.generate(question, basic_intent)

    assert isinstance(result, GeneratedSQL)
    assert result.sql is not None
    assert result.sql.upper().startswith("SELECT")
    assert "FROM users" in result.sql
    assert "users" in result.tables_used
    assert result.generation_ms > 0
    assert result.model_used == sql_generator.primary_model


@pytest.mark.integration
@pytest.mark.asyncio
async def test_join_query(sql_generator: SQLGenerator, join_intent: ValidIntent):
    """Test query generation with table joins."""
    question = "How many orders does each user have?"

    result = await sql_generator.generate(question, join_intent)

    assert isinstance(result, GeneratedSQL)
    assert "JOIN" in result.sql.upper()
    assert "GROUP BY" in result.sql.upper()
    assert "COUNT" in result.sql.upper()
    assert "users" in result.tables_used
    assert "orders" in result.tables_used
    assert any("user_id" in cols for cols in result.columns_used.values())


@pytest.mark.integration
@pytest.mark.asyncio
async def test_aggregate_query(
    sql_generator: SQLGenerator, aggregate_intent: ValidIntent
):
    """Test aggregate query generation."""
    question = "What is the total and average order amount per user?"

    result = await sql_generator.generate(question, aggregate_intent)

    assert isinstance(result, GeneratedSQL)
    assert "SUM" in result.sql.upper()
    assert "AVG" in result.sql.upper()
    assert "GROUP BY" in result.sql.upper()
    assert "total_amount" in str(result.columns_used)


# Error Handling Tests
@pytest.mark.integration
@pytest.mark.asyncio
async def test_invalid_table(sql_generator: SQLGenerator, basic_intent: ValidIntent):
    """Test error handling with non-existent table."""
    invalid_intent = ValidIntent(
        original_intent=Intent(
            query_type=QueryType.LOOKUP,
            tables=["nonexistent_table"],
            operations=["SELECT"],
            conditions=[],
            confidence=0.95,
        ),
        enhanced_metadata={"table_relationships": {}},
    )

    with pytest.raises(SQLGenerationError, match="table"):
        await sql_generator.generate("Show data from invalid table", invalid_intent)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_invalid_column(sql_generator: SQLGenerator, basic_intent: ValidIntent):
    """Test error handling with non-existent column."""
    question = "Show me the invalid_column from users"

    with pytest.raises(SQLGenerationError, match="column"):
        await sql_generator.generate(question, basic_intent)


# Model Fallback Tests
@pytest.mark.integration
@pytest.mark.asyncio
async def test_model_fallback(sql_generator: SQLGenerator, basic_intent: ValidIntent):
    """Test fallback to secondary model when primary fails."""
    original_primary = sql_generator.primary_model
    sql_generator.primary_model = "invalid/model"

    try:
        result = await sql_generator.generate("List all users", basic_intent)
        assert isinstance(result, GeneratedSQL)
        assert result.model_used == sql_generator.fallback_model
        assert result.sql is not None
    finally:
        sql_generator.primary_model = original_primary


# Performance and Token Usage Tests
@pytest.mark.integration
@pytest.mark.asyncio
async def test_token_usage_tracking(
    sql_generator: SQLGenerator, join_intent: ValidIntent
):
    """Test token usage tracking in complex query."""
    question = "Show me the top 5 users by total order value"

    result = await sql_generator.generate(question, join_intent)

    assert isinstance(result, GeneratedSQL)
    assert result.token_usage is not None
    assert result.token_usage.prompt_tokens > 0
    assert result.token_usage.completion_tokens > 0
    assert result.token_usage.total_tokens == (
        result.token_usage.prompt_tokens + result.token_usage.completion_tokens
    )
    assert result.generation_ms > 0


# Schema Context Tests
@pytest.mark.integration
@pytest.mark.asyncio
async def test_schema_context_handling(
    sql_generator: SQLGenerator, join_intent: ValidIntent, schema_graph: SchemaGraph
):
    """Test proper handling of schema context in query generation."""
    question = "Show total orders and revenue per user"

    result = await sql_generator.generate(question, join_intent)

    assert isinstance(result, GeneratedSQL)
    # Verify proper table relationships are used
    assert "JOIN" in result.sql.upper()
    assert "user_id" in str(result.columns_used)
    assert "total_amount" in str(result.columns_used)
    # Verify proper column qualifiers
    assert "users." in result.sql or "u." in result.sql
    assert "orders." in result.sql or "o." in result.sql
