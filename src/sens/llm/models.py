"""Data models for LLM interactions, intents, and schema context."""

from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, confloat


class QueryType(str, Enum):
    """
    Categorizes the primary intent behind a user's natural language query.

    - AGGREGATION: Summarizing or calculating over data (e.g., COUNT, AVG).
    - LOOKUP: Retrieving specific records or fields based on criteria.
    - RELATIONSHIP: Exploring connections between different data entities.
    """

    AGGREGATION = "aggregation"
    LOOKUP = "lookup"
    RELATIONSHIP = "relationship"


class Intent(BaseModel):
    """
    Represents the structured understanding of a user's query intent.

    Extracted from natural language and validated against a schema.
    """

    query_type: QueryType = Field(
        ...,
        description="The primary goal of the user query (aggregation, lookup, or relationship).",
    )
    tables: List[str] = Field(
        ...,
        description="List of database table names likely relevant to the query.",
    )
    operations: List[str] = Field(
        default_factory=list,
        description="Suggested operations, like aggregate functions (e.g., 'COUNT', 'AVG') or specific fields to select.",
    )
    conditions: List[str] = Field(
        default_factory=list,
        description="Filtering conditions derived from the query, often mapping to WHERE clauses (e.g., 'release_year = 2023').",
    )
    confidence: confloat(ge=0.0, le=1.0) = Field(
        ...,
        description="The LLM's confidence score (0.0 to 1.0) in the accuracy of the extracted intent.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "query_type": "aggregation",
                "tables": ["movie"],
                "operations": ["COUNT"],
                "conditions": ["release_year = 2023"],
                "confidence": 0.93,
            }
        },
        "use_enum_values": True,
    }


class SchemaContext(BaseModel):
    """Focused view of database schema information relevant for SQL generation."""

    tables: Dict[str, List[str]] = Field(
        ...,
        description="Dictionary mapping table names to their column names",
    )
    primary_keys: Dict[str, List[str]] = Field(
        ...,
        description="Dictionary mapping table names to their primary key column(s)",
    )
    foreign_keys: List[Dict[str, Union[str, List[str]]]] = Field(
        default_factory=list,
        description="List of foreign key relationships between tables",
    )
    column_descriptions: Dict[str, Dict[str, str]] = Field(
        default_factory=dict,
        description="Nested dictionary mapping table.column to its description",
    )

    def to_validator_schema(self) -> "SchemaContext":
        """Convert to validator's SchemaContext format."""
        from sens.validation.sql_validator import (
            SchemaContext as ValidatorSchemaContext,
        )

        # Convert tables and columns
        tables = set(self.tables.keys())
        columns_per_table = {
            table: set(columns) for table, columns in self.tables.items()
        }

        # Convert foreign keys to validator format
        foreign_keys = {}
        for fk in self.foreign_keys:
            from_table = fk["from_table"]
            to_table = fk["to_table"]
            from_cols = fk["from_columns"]
            to_cols = fk["to_columns"]

            # Handle both single column and multi-column foreign keys
            if isinstance(from_cols, str) and isinstance(to_cols, str):
                from_cols = [from_cols]
                to_cols = [to_cols]

            # Add each column pair as a foreign key
            if from_table not in foreign_keys:
                foreign_keys[from_table] = {}
            for from_col, to_col in zip(from_cols, to_cols):
                foreign_keys[from_table][from_col] = (to_table, to_col)

        return ValidatorSchemaContext(
            tables=tables,
            columns_per_table=columns_per_table,
            foreign_keys=foreign_keys,
        )

    model_config = {
        "json_schema_extra": {
            "example": {
                "tables": {
                    "users": ["id", "name", "email"],
                    "orders": ["id", "user_id", "total"],
                },
                "primary_keys": {
                    "users": ["id"],
                    "orders": ["id"],
                },
                "foreign_keys": [
                    {
                        "from_table": "orders",
                        "from_columns": ["user_id"],
                        "to_table": "users",
                        "to_columns": ["id"],
                    }
                ],
                "column_descriptions": {
                    "users": {
                        "id": "Unique identifier for the user",
                        "name": "User's full name",
                    }
                },
            }
        }
    }


class TokenUsage(BaseModel):
    """Token usage information for LLM API calls."""

    prompt_tokens: int = Field(
        ...,
        description="Number of tokens in the prompt",
    )
    completion_tokens: int = Field(
        ...,
        description="Number of tokens in the completion",
    )

    @property
    def total_tokens(self) -> int:
        """Calculate total tokens used."""
        return self.prompt_tokens + self.completion_tokens


class GeneratedSQL(BaseModel):
    """Container for a generated SQL query and its associated metadata."""

    sql: str = Field(
        ...,
        description="The generated SQL query string",
    )
    tables_used: List[str] = Field(
        ...,
        description="List of tables referenced in the generated query",
    )
    columns_used: Dict[str, List[str]] = Field(
        ...,
        description="Dictionary mapping tables to their columns used in the query",
    )
    token_usage: Optional[TokenUsage] = Field(
        None,
        description="Token usage information for the generation",
    )
    model_used: str = Field(
        ...,
        description="Identifier of the LLM model used for generation",
    )
    generation_ms: Optional[int] = Field(
        None,
        description="Time taken to generate the SQL in milliseconds",
    )
    cached: bool = Field(
        False,
        description="Whether this result was retrieved from cache",
    )
    timestamp: Optional[Any] = Field(
        None,
        description="Timestamp when the SQL was generated",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "sql": "SELECT name, COUNT(*) as order_count FROM users u JOIN orders o ON u.id = o.user_id GROUP BY name",
                "tables_used": ["users", "orders"],
                "columns_used": {"users": ["id", "name"], "orders": ["user_id"]},
                "token_usage": {
                    "prompt_tokens": 150,
                    "completion_tokens": 50,
                    "total_tokens": 200,
                },
                "model_used": "gemini-2.0-flash-001",
                "generation_ms": 2500,
            }
        }
    }


class RetrievedSchemaContext(BaseModel):
    """Schema context from retrieval system."""

    query: str = Field(..., description="The original query")
    tables: List[Dict[str, Any]] = Field(
        ..., description="Retrieved tables with metadata"
    )
    columns: List[Dict[str, Any]] = Field(
        ..., description="Retrieved columns with metadata"
    )

    def format_for_llm(self) -> str:
        """Format the schema context for LLM consumption."""
        parts = []

        # Group columns by table
        table_columns: Dict[str, List[str]] = {}
        for col in self.columns:
            table_name = col["table_name"]
            column_name = col["column_name"]
            if table_name not in table_columns:
                table_columns[table_name] = []
            table_columns[table_name].append(column_name)

        # Format each table
        for table in self.tables:
            table_name = table["table_name"]
            columns_str = ", ".join(table_columns.get(table_name, []))
            table_def = f"TABLE {table_name} ({columns_str})"
            if table.get("metadata", {}).get("description"):
                table_def += f"\n-- {table['metadata']['description']}"
            parts.append(table_def)

        return "\n\n".join(parts)

    model_config = {
        "json_schema_extra": {
            "example": {
                "query": "Show top movies",
                "tables": [
                    {"table_name": "movie", "reason": "direct_hit", "metadata": {}}
                ],
                "columns": [
                    {
                        "table_name": "movie",
                        "column_name": "title",
                        "score": 0.8,
                        "source": "embedding",
                        "metadata": {},
                    }
                ],
            }
        }
    }


class SQLGenerationError(Exception):
    """Custom exception for errors during SQL generation."""

    def __init__(self, message: str, details: Optional[Dict] = None):
        """Initialize the SQL generation error with a message and optional details."""
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class IntentExtractionError(Exception):
    """Custom exception for errors during intent extraction."""

    def __init__(self, message: str, details: Optional[Dict] = None):
        """Initialize the intent extraction error with a message and optional details."""
        self.message = message
        self.details = details or {}
        super().__init__(self.message)
