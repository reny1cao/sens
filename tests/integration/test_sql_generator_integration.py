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
from sens.settings import Settings
from sens.settings.models import SQLGeneratorConfig

# Skip all tests if no API key is present
pytestmark = pytest.mark.skipif(
    os.getenv("SENS_LLM_API_KEY") is None,
    reason="SENS_LLM_API_KEY environment variable not set",
)


@pytest.fixture
def integration_intent() -> ValidIntent:
    """Create a realistic intent for integration testing."""
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
def sql_generator() -> SQLGenerator:
    """Create a SQLGenerator instance configured for integration testing."""
    return SQLGenerator(max_tokens=1000, temperature=0.1)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_basic_sql_generation(
    sql_generator: SQLGenerator, integration_intent: ValidIntent
):
    """Test basic SQL generation with a simple query."""
    question = "How many orders does each user have?"

    result = await sql_generator.generate(question, integration_intent)

    assert isinstance(result, GeneratedSQL)
    assert result.sql is not None
    assert len(result.sql) > 0
    assert "SELECT" in result.sql.upper()
    assert "FROM" in result.sql.upper()
    assert "users" in result.tables_used
    assert "orders" in result.tables_used
    assert result.generation_ms > 0
    assert result.model_used in [
        sql_generator.primary_model,
        sql_generator.fallback_model,
    ]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_complex_query_generation(
    sql_generator: SQLGenerator, integration_intent: ValidIntent
):
    """Test SQL generation with a more complex query involving multiple operations."""
    question = "Show me the top 5 users by order value, including their total order count and average order amount"

    result = await sql_generator.generate(question, integration_intent)

    assert isinstance(result, GeneratedSQL)
    assert "SELECT" in result.sql.upper()
    assert "JOIN" in result.sql.upper()
    assert "GROUP BY" in result.sql.upper()
    assert "ORDER BY" in result.sql.upper()
    assert "LIMIT" in result.sql.upper()
    assert result.generation_ms > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_error_handling(
    sql_generator: SQLGenerator, integration_intent: ValidIntent
):
    """Test error handling with an intentionally problematic query."""
    # Modify intent to include a non-existent table
    invalid_intent = ValidIntent(
        original_intent=Intent(
            query_type=QueryType.LOOKUP,
            tables=["users", "nonexistent_table"],
            operations=["COUNT"],
            conditions=[],
            confidence=0.95,
        ),
        enhanced_metadata={"table_relationships": {}},
    )

    with pytest.raises(SQLGenerationError):
        await sql_generator.generate(
            "Show data from non-existent table", invalid_intent
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_model_fallback(
    sql_generator: SQLGenerator, integration_intent: ValidIntent
):
    """Test fallback behavior by forcing primary model to fail."""
    # Temporarily set primary model to an invalid model to force fallback
    original_primary = sql_generator.primary_model
    sql_generator.primary_model = "invalid/model"

    try:
        result = await sql_generator.generate(
            "How many orders does each user have?", integration_intent
        )

        assert isinstance(result, GeneratedSQL)
        assert result.model_used == sql_generator.fallback_model
        assert result.sql is not None
        assert len(result.sql) > 0
    finally:
        # Restore original primary model
        sql_generator.primary_model = original_primary


@pytest.mark.integration
@pytest.mark.asyncio
async def test_token_usage_tracking(
    sql_generator: SQLGenerator, integration_intent: ValidIntent
):
    """Test that token usage is properly tracked."""
    result = await sql_generator.generate(
        "Show total order value per user", integration_intent
    )

    assert isinstance(result, GeneratedSQL)
    assert result.token_usage is not None
    assert result.token_usage.prompt_tokens > 0
    assert result.token_usage.completion_tokens > 0
    assert result.token_usage.total_tokens == (
        result.token_usage.prompt_tokens + result.token_usage.completion_tokens
    )
