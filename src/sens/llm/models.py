"""Data models for LLM interactions, intents, and schema context."""

from enum import Enum
from typing import Dict, List, Optional, Union

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
    prompt_tokens: Optional[int] = Field(
        None,
        description="Number of tokens used in the generation prompt",
    )
    completion_tokens: Optional[int] = Field(
        None,
        description="Number of tokens in the LLM completion",
    )
    model_used: str = Field(
        ...,
        description="Identifier of the LLM model used for generation",
    )
    generation_ms: Optional[int] = Field(
        None,
        description="Time taken to generate the SQL in milliseconds",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "sql": "SELECT name, COUNT(*) as order_count FROM users u JOIN orders o ON u.id = o.user_id GROUP BY name",
                "tables_used": ["users", "orders"],
                "columns_used": {"users": ["id", "name"], "orders": ["user_id"]},
                "prompt_tokens": 150,
                "completion_tokens": 50,
                "model_used": "gpt-4",
                "generation_ms": 2500,
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
