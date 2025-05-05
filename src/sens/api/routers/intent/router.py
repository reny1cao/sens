"""Intent extraction router."""

from typing import List

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from ....llm.intent_extractor import IntentExtractor
from ...common.logging import get_logger
from ...common.rate_limit import rate_limiter
from ...models.intent import IntentRequest, IntentResponse, SchemaSnippet

router = APIRouter(
    prefix="/intent",
    tags=["intent"],
    responses={
        400: {"description": "Bad Request"},
        422: {"description": "Validation Error"},
        429: {"description": "Too Many Requests"},
        500: {"description": "Internal Server Error"},
    },
)

logger = get_logger(__name__)

# Sample schema for testing
SAMPLE_SCHEMA = [
    SchemaSnippet(
        table_name="orders",
        columns=["order_id", "customer_id", "total_amount", "order_date"],
        description="Customer orders table with order details",
    ),
    SchemaSnippet(
        table_name="customers",
        columns=["customer_id", "name", "email", "join_date"],
        description="Customer information and metadata",
    ),
]

# Create an instance of IntentExtractor with error handling
try:
    intent_extractor_instance = IntentExtractor()
except FileNotFoundError as e:
    logger.error("config_error_startup", error=str(e), detail="Intent prompt missing")
    intent_extractor_instance = None
except Exception as e:
    logger.error(
        "config_error_startup", error=str(e), detail="Failed to init IntentExtractor"
    )
    intent_extractor_instance = None


def format_schema_snippet(snippet: SchemaSnippet) -> str:
    """Format a SchemaSnippet object into a string for the LLM.

    Args:
        snippet: SchemaSnippet object containing table information

    Returns:
        Formatted string in pseudo-SQL format
    """
    columns_str = ", ".join(snippet.columns)
    base = f"TABLE {snippet.table_name} ({columns_str});"
    if snippet.description:
        return f"{base} -- {snippet.description}"
    return base


@router.post(
    "/extract",
    response_model=IntentResponse,
    summary="Extract intent from natural language query",
    description="Analyzes a natural language query and relevant schema to extract user intent",
)
async def extract_intent_endpoint(
    request: IntentRequest,
    rate_limit: bool = Depends(rate_limiter),
) -> IntentResponse:
    """Extract intent from natural language query.

    Args:
        request: Intent extraction request containing query and schema
        rate_limit: Rate limiting dependency

    Returns:
        Extracted intent with confidence score and relevant tables

    Raises:
        HTTPException: If intent extraction fails
    """
    if intent_extractor_instance is None:
        raise HTTPException(
            status_code=500,
            detail="Internal configuration error: Intent Extractor unavailable",
        )

    try:
        logger.info(
            "processing_intent_request",
            query=request.query,
            schema_count=len(request.schema_snippets),
        )

        # Format schema snippets into strings
        formatted_snippets = [format_schema_snippet(s) for s in request.schema_snippets]
        schema_snippet_str = "\n\n".join(formatted_snippets)

        # Extract intent using the IntentExtractor instance
        intent_result = intent_extractor_instance.extract(
            question=request.query, schema_snippet=schema_snippet_str
        )

        # Convert to API response model
        # Note: query_type is already a string due to use_enum_values=True in Intent model
        response = IntentResponse(
            intent=intent_result.query_type,  # No need for .value
            confidence=intent_result.confidence,
            relevant_tables=intent_result.tables,
            operations=getattr(intent_result, "operations", []),
        )

        logger.info(
            "intent_extracted",
            intent=response.intent,
            confidence=response.confidence,
            tables=response.relevant_tables,
            operations=response.operations,
        )

        return response

    except ValueError as e:
        logger.warning("validation_error", error=str(e), query=request.query)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("intent_extraction_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500, detail="Internal server error during intent extraction"
        )


@router.get(
    "/sample",
    response_model=IntentRequest,
    summary="Get a sample intent request",
    description="Returns a sample intent request for testing the API",
)
async def get_sample_request() -> IntentRequest:
    """Get a sample intent request for testing.

    Returns:
        Sample IntentRequest object with pre-configured schema and query
    """
    return IntentRequest(
        query="What is the total amount of orders per customer?",
        schema_snippets=SAMPLE_SCHEMA,
        context={"mode": "test"},
    )
