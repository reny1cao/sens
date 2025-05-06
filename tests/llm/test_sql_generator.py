"""Unit tests for the SQL Generator."""

import json
from pathlib import Path
from typing import Dict, List

import pytest
from pydantic import ValidationError

from sens.llm.intent_validator import ValidIntent
from sens.llm.models import (
    GeneratedSQL,
    Intent,
    QueryType,
    SchemaContext,
    SQLGenerationError,
)
from sens.llm.sql_generator import SQLGenerator
from sens.schema.graph import SchemaGraph


@pytest.fixture
def sample_schema_context() -> SchemaContext:
    """Create a sample schema context for testing."""
    return SchemaContext(
        tables={
            "users": ["id", "name", "email", "created_at"],
            "orders": ["id", "user_id", "total", "status", "created_at"],
        },
        primary_keys={
            "users": ["id"],
            "orders": ["id"],
        },
        foreign_keys=[
            {
                "from_table": "orders",
                "from_columns": ["user_id"],
                "to_table": "users",
                "to_columns": ["id"],
            }
        ],
        column_descriptions={
            "users": {
                "id": "Primary key",
                "name": "User's full name",
                "email": "User's email address",
            },
            "orders": {
                "id": "Primary key",
                "user_id": "Reference to users.id",
                "total": "Order total amount",
            },
        },
    )


@pytest.fixture
def sample_valid_intent() -> ValidIntent:
    """Create a sample validated intent for testing."""
    intent = Intent(
        query_type=QueryType.LOOKUP,
        tables=["users", "orders"],
        operations=["COUNT"],
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
def temp_prompt_file(tmp_path: Path) -> Path:
    """Create a temporary prompt file for testing."""
    prompt_dir = tmp_path / "prompts"
    prompt_dir.mkdir()
    prompt_file = prompt_dir / "sql_generation.prompt.txt"

    # Simple test prompt template
    prompt_content = """
Question: {{ question }}

Schema:
{% for table, columns in schema.tables.items() %}
Table: {{ table }}
Columns: {{ columns|join(', ') }}
{% endfor %}

Intent:
Type: {{ intent.query_type }}
Tables: {{ intent.tables|join(', ') }}

SQL:
```sql
SELECT * FROM {{ intent.tables[0] }};
```
"""
    prompt_file.write_text(prompt_content)
    return prompt_file


@pytest.fixture
def sql_generator(temp_prompt_file: Path) -> SQLGenerator:
    """Create a SQLGenerator instance for testing."""
    return SQLGenerator(
        prompt_dir=temp_prompt_file.parent,
        prompt_filename=temp_prompt_file.name,
    )


@pytest.fixture
def valid_intent() -> ValidIntent:
    """Create a sample validated intent for testing."""
    intent = Intent(
        query_type=QueryType.LOOKUP,
        tables=["users", "orders"],
        operations=["COUNT"],
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


def test_sql_generator_initialization(temp_prompt_file: Path):
    """Test successful initialization of SQLGenerator."""
    generator = SQLGenerator(
        prompt_dir=temp_prompt_file.parent,
        prompt_filename=temp_prompt_file.name,
    )
    assert generator.prompt_path.exists()
    assert generator.jinja_env is not None
    assert generator.primary_model == "gpt-4"  # Default from settings
    assert generator.max_tokens == 500  # Default value
    assert generator.temperature == 0.1  # Default value


def test_sql_generator_missing_prompt():
    """Test initialization fails when prompt file is missing."""
    with pytest.raises(FileNotFoundError):
        SQLGenerator(prompt_dir=Path("/nonexistent"))


def test_build_schema_context(sample_valid_intent: ValidIntent, monkeypatch):
    """Test building schema context from intent."""

    class MockSchemaGraph:
        def get_instance(self):
            return self

        def get_referenced_tables(self, table: str) -> set:
            if table == "orders":
                return {"users"}
            return set()

        def get_referencing_tables(self, table: str) -> set:
            if table == "users":
                return {"orders"}
            return set()

        def get_table_pks(self, table: str) -> List[str]:
            return ["id"]

        def get_column_comment(self, table: str, column: str) -> str:
            return f"Comment for {table}.{column}"

    monkeypatch.setattr("sens.schema.graph.SchemaGraph", MockSchemaGraph)

    generator = SQLGenerator()
    schema_context = generator._build_schema_context(sample_valid_intent)

    assert isinstance(schema_context, SchemaContext)
    assert "users" in schema_context.tables
    assert "orders" in schema_context.tables
    assert schema_context.primary_keys["users"] == ["id"]
    assert schema_context.primary_keys["orders"] == ["id"]


def test_render_prompt(
    temp_prompt_file: Path,
    sample_valid_intent: ValidIntent,
    sample_schema_context: SchemaContext,
):
    """Test rendering the prompt template."""
    generator = SQLGenerator(
        prompt_dir=temp_prompt_file.parent,
        prompt_filename=temp_prompt_file.name,
    )

    question = "How many orders per user?"
    rendered = generator._render_prompt(
        question, sample_valid_intent, sample_schema_context
    )

    assert question in rendered
    assert "users" in rendered
    assert "orders" in rendered
    assert "lookup" in rendered.lower()  # QueryType
    assert "id" in rendered  # Column name


def test_extract_sql_from_completion(sql_generator):
    """Test extracting SQL from various completion formats."""
    # Test markdown format
    completion = "Here's the SQL:\n```sql\nSELECT * FROM users;\n```"
    sql = sql_generator._extract_sql_from_completion(completion)
    assert sql == "SELECT * FROM users;"

    # Test direct SQL
    completion = "SELECT * FROM users;"
    sql = sql_generator._extract_sql_from_completion(completion)
    assert sql == "SELECT * FROM users;"

    # Test error message
    with pytest.raises(SQLGenerationError) as exc:
        sql_generator._extract_sql_from_completion("ERROR: Invalid table name")
    assert "Invalid table name" in str(exc.value)

    # Test invalid format
    with pytest.raises(SQLGenerationError) as exc:
        sql_generator._extract_sql_from_completion("This is not SQL")
    assert "Could not extract valid SQL" in str(exc.value)


@pytest.mark.asyncio
async def test_generate_extraction_error(sql_generator, valid_intent, monkeypatch):
    """Test error during SQL extraction."""

    def mock_extract(*args, **kwargs):
        raise SQLGenerationError("Could not extract valid SQL")

    monkeypatch.setattr(
        sql_generator,
        "_extract_sql_from_completion",
        mock_extract,
    )

    with pytest.raises(SQLGenerationError, match="Could not extract valid SQL"):
        await sql_generator.generate("Show me top shows", valid_intent)


@pytest.mark.asyncio
async def test_generate_validation_error(sql_generator, valid_intent, monkeypatch):
    """Test error during SQL validation."""

    def mock_validate(*args, **kwargs):
        return False, "Invalid SQL syntax"

    monkeypatch.setattr(
        sql_generator,
        "_validate_generated_sql",
        mock_validate,
    )

    with pytest.raises(SQLGenerationError, match="Invalid SQL syntax"):
        await sql_generator.generate("Show me top shows", valid_intent)


def test_extract_query_metadata(sample_schema_context: SchemaContext):
    """Test extracting metadata from generated SQL."""
    generator = SQLGenerator()

    sql = """
    SELECT u.name, COUNT(o.id) as order_count
    FROM users u
    JOIN orders o ON u.id = o.user_id
    WHERE o.created_at > '2023-01-01'
    GROUP BY u.name;
    """

    tables, columns = generator._extract_query_metadata(sql, sample_schema_context)

    assert "users" in tables
    assert "orders" in tables
    assert "name" in columns["users"]
    assert "user_id" in columns["orders"]


def test_sql_generator_init(sql_generator):
    """Test SQLGenerator initialization."""
    assert sql_generator.prompt_path.name == "sql_generation.prompt.txt"
    assert sql_generator.prompt_path.exists()
    assert sql_generator.jinja_env is not None
    assert sql_generator.primary_model == "gpt-4"  # Default from settings
    assert sql_generator.max_tokens == 500  # Default value
    assert sql_generator.temperature == 0.1  # Default value
