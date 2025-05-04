from enum import Enum
from typing import List

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

    class Config:
        """Configuration for the Intent model."""

        json_schema_extra = {
            "example": {
                "query_type": "aggregation",
                "tables": ["movie"],
                "operations": ["COUNT"],
                "conditions": ["release_year = 2023"],
                "confidence": 0.93,
            }
        }
        use_enum_values = True
