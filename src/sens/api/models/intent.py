"""Models for intent extraction API."""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class SchemaSnippet(BaseModel):
    """Schema information for a database table."""

    table_name: str = Field(..., description="Name of the table")
    columns: List[str] = Field(..., description="List of column names")
    description: Optional[str] = Field(None, description="Optional table description")


class IntentRequest(BaseModel):
    """Request model for intent extraction."""

    query: str = Field(..., description="Natural language query to analyze")
    schema_snippets: List[SchemaSnippet] = Field(
        ..., description="Available schema information"
    )
    context: Optional[Dict[str, str]] = Field(
        default={}, description="Additional context for intent extraction"
    )


class IntentResponse(BaseModel):
    """Response model for intent extraction."""

    intent: str = Field(
        ...,
        description="Extracted intent (e.g., 'aggregation', 'lookup', 'relationship')",
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    relevant_tables: List[str] = Field(..., description="Tables relevant to the intent")
    operations: List[str] = Field(
        default_factory=list,
        description="Operations to perform (e.g., ['COUNT', 'SUM', 'AVG'] for aggregations)",
    )
    metadata: Dict[str, str] = Field(
        default_factory=dict, description="Additional metadata about the extraction"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "intent": "aggregation",
                "confidence": 0.95,
                "relevant_tables": ["orders", "customers"],
                "operations": ["SUM"],
                "metadata": {"context": "financial analysis"},
            }
        }
    }
