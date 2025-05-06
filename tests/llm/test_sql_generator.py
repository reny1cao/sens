"""Unit tests for the SQL Generator."""

import json
from pathlib import Path
from typing import Dict, List, Set
from unittest.mock import AsyncMock, MagicMock

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
def mock_llm_response():
    """Create a mock LLM response with a valid SQL query."""
    return """Here's the SQL query to answer your question:
```sql
SELECT u.name, COUNT(o.id) as order_count
FROM users u
JOIN orders o ON u.id = o.user_id
GROUP BY u.name
ORDER BY order_count DESC;
```
This query will show all users and their order counts."""


@pytest.fixture
def mock_llm_error_response():
    """Create a mock LLM response indicating an error."""
    return "ERROR: Unable to generate SQL for the given schema."


@pytest.fixture
def mock_llm_invalid_response():
    """Create a mock LLM response without SQL."""
    return "I understand you want to query the database."


@pytest.fixture
def mock_openai_response(mock_llm_response):
    """Create a mock OpenAI API response object."""

    class MockUsage:
        def __init__(self):
            self.prompt_tokens = 100
            self.completion_tokens = 50
            self.total_tokens = 150

    class MockMessage:
        def __init__(self):
            self.content = mock_llm_response

    class MockChoice:
        def __init__(self):
            self.message = MockMessage()

    class MockResponse:
        def __init__(self):
            self.choices = [MockChoice()]
            self.usage = MockUsage()
            self.model = "openai/gpt-4"

    return MockResponse()


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
    assert generator.primary_model == "openai/gpt-4"  # Default from settings
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

        def get_table_columns(self, table: str) -> List[str]:
            if table == "users":
                return ["id", "name", "email"]
            elif table == "orders":
                return ["id", "user_id", "total"]
            return []

        def get_table_pks(self, table: str) -> List[str]:
            return ["id"]

        def get_column_comment(self, table: str, column: str) -> str:
            return f"Description for {table}.{column}"

        def get_table_fks_involved(self, table: str, ref_tables: Set[str]) -> List[str]:
            if table == "orders" and "users" in ref_tables:
                return ["user_id"]
            return []

    mock_graph = MockSchemaGraph()
    monkeypatch.setattr(SchemaGraph, "get_instance", mock_graph.get_instance)

    # Create generator with mocked schema
    generator = SQLGenerator()
    context = generator._build_schema_context(sample_valid_intent)

    # Verify tables are included
    assert "users" in context.tables
    assert "orders" in context.tables

    # Verify columns
    assert "id" in context.tables["users"]
    assert "name" in context.tables["users"]
    assert "user_id" in context.tables["orders"]

    # Verify primary keys
    assert context.primary_keys["users"] == ["id"]
    assert context.primary_keys["orders"] == ["id"]

    # Verify foreign keys
    assert len(context.foreign_keys) == 1
    fk = context.foreign_keys[0]
    assert fk["from_table"] == "orders"
    assert fk["to_table"] == "users"
    assert fk["from_columns"] == ["user_id"]
    assert fk["to_columns"] == ["id"]

    # Verify column descriptions
    assert "users" in context.column_descriptions
    assert "orders" in context.column_descriptions


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
async def test_call_llm_api_error(sql_generator, monkeypatch):
    """Test LLM API error handling."""

    async def mock_error(*args, **kwargs):
        raise Exception("API Error")

    mock_create = AsyncMock(side_effect=mock_error)
    monkeypatch.setattr(sql_generator.client.chat.completions, "create", mock_create)

    with pytest.raises(
        SQLGenerationError, match="Failed to generate SQL with all available models"
    ):
        await sql_generator._call_llm("Test prompt")


@pytest.mark.asyncio
async def test_generate_validation_error(
    sql_generator, valid_intent, mock_openai_response, monkeypatch
):
    def mock_create(*args, **kwargs):
        return mock_openai_response

    monkeypatch.setattr(sql_generator.client.chat.completions, "create", mock_create)

    # Mock the schema graph to return valid data
    class MockSchemaGraph:
        def get_instance(self):
            return self

        def get_referenced_tables(self, table: str) -> set:
            return set()

        def get_referencing_tables(self, table: str) -> set:
            return set()

        def get_table_columns(self, table: str) -> List[str]:
            if table == "users":
                return ["id", "name"]
            return []

        def get_table_pks(self, table: str) -> List[str]:
            return ["id"]

        def get_column_comment(self, table: str, column: str) -> str:
            return ""

        def get_table_fks_involved(self, table: str, ref_tables: Set[str]) -> List[str]:
            return []

    mock_graph = MockSchemaGraph()
    monkeypatch.setattr(SchemaGraph, "get_instance", mock_graph.get_instance)

    # Mock the validation to return False
    def mock_validate(*args, **kwargs):
        return False, "Invalid SQL syntax"

    monkeypatch.setattr(
        sql_generator,
        "_validate_generated_sql",
        mock_validate,
    )

    with pytest.raises(SQLGenerationError, match="Generated SQL failed validation"):
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
    assert sql_generator.primary_model == "openai/gpt-4"  # Default from settings
    assert sql_generator.max_tokens == 500  # Default value
    assert sql_generator.temperature == 0.1  # Default value


@pytest.mark.asyncio
async def test_call_llm_success(sql_generator, mock_openai_response, monkeypatch):
    """Test successful LLM API call."""

    def mock_create(*args, **kwargs):
        return mock_openai_response

    monkeypatch.setattr(sql_generator.client.chat.completions, "create", mock_create)

    result = await sql_generator._call_llm("Test prompt")
    assert "SELECT u.name" in result[0]
    assert "FROM users" in result[0]


@pytest.mark.asyncio
async def test_call_llm_fallback(sql_generator, mock_openai_response, monkeypatch):
    """Test fallback to secondary model on primary model failure."""
    call_count = {"count": 0}

    def mock_create(*args, **kwargs):
        call_count["count"] += 1
        if call_count["count"] == 1:
            raise Exception("Primary model error")
        return mock_openai_response

    monkeypatch.setattr(sql_generator.client.chat.completions, "create", mock_create)

    result = await sql_generator._call_llm("Test prompt")
    assert call_count["count"] == 2  # Verify both models were tried
    assert "SELECT u.name" in result[0]


@pytest.mark.asyncio
async def test_generate_end_to_end(
    sql_generator, valid_intent, mock_openai_response, monkeypatch
):
    """Test the complete generation flow with mocked LLM."""

    def mock_create(*args, **kwargs):
        return mock_openai_response

    monkeypatch.setattr(sql_generator.client.chat.completions, "create", mock_create)

    # Patch _build_schema_context to return a schema context matching the mock SQL
    from sens.llm.models import SchemaContext, TokenUsage

    schema_context = SchemaContext(
        tables={"users": ["id", "name"], "orders": ["id", "user_id"]},
        primary_keys={"users": ["id"], "orders": ["id"]},
        foreign_keys=[
            {
                "from_table": "orders",
                "from_columns": ["user_id"],
                "to_table": "users",
                "to_columns": ["id"],
            }
        ],
        column_descriptions={
            "users": {"id": "", "name": ""},
            "orders": {"id": "", "user_id": ""},
        },
    )
    monkeypatch.setattr(
        sql_generator, "_build_schema_context", lambda intent: schema_context
    )

    result = await sql_generator.generate(
        "How many orders does each user have?",
        valid_intent,
    )

    assert isinstance(result, GeneratedSQL)
    assert "SELECT u.name" in result.sql
    assert "users" in result.tables_used
    assert "orders" in result.tables_used
    assert result.model_used == sql_generator.primary_model
    assert result.generation_ms > 0
