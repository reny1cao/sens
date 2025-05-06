"""Intent validation and clarification request handling."""

from typing import List, Optional, Union

import structlog
from pydantic import BaseModel, Field

from sens.schema.graph import SchemaGraph

from .models import Intent, QueryType

log = structlog.get_logger()


class ClarificationRequest(BaseModel):
    """Request for user clarification when intent validation fails."""

    message: str = Field(
        ..., description="User-friendly explanation of what needs clarification"
    )
    reason: str = Field(
        ..., description="Internal reason code for the clarification request"
    )
    missing_fields: List[str] = Field(
        default_factory=list, description="List of required fields that are missing"
    )
    ambiguous_fields: List[str] = Field(
        default_factory=list, description="List of fields that need disambiguation"
    )


class ValidIntent(BaseModel):
    """Wrapper for an intent that has passed validation."""

    original_intent: Intent = Field(..., description="The validated intent object")
    enhanced_metadata: dict = Field(
        default_factory=dict, description="Additional metadata added during validation"
    )


class IntentValidator:
    """
    Validates the logical consistency and completeness of an LLM-extracted Intent.
    Acts as a deterministic safety gate before SQL generation.
    """

    def __init__(self, confidence_threshold: float = 0.75):
        """
        Initialize the IntentValidator.

        Args:
            confidence_threshold: Minimum confidence score required (0.0 to 1.0)
        """
        self.confidence_threshold = confidence_threshold
        self.schema = SchemaGraph.get_instance()
        log.info(
            "intent_validator_initialized", confidence_threshold=confidence_threshold
        )

    def _check_confidence(self, intent: Intent) -> Optional[ClarificationRequest]:
        """Validate the confidence score meets minimum threshold."""
        if intent.confidence < self.confidence_threshold:
            return ClarificationRequest(
                message=f"The system's confidence ({intent.confidence:.2f}) in understanding your query "
                f"is below the required threshold ({self.confidence_threshold}). "
                "Could you please rephrase your question?",
                reason="low_confidence",
            )
        return None

    def _validate_tables(self, intent: Intent) -> Optional[ClarificationRequest]:
        """Validate that all referenced tables exist in the schema."""
        if not intent.tables:
            return ClarificationRequest(
                message="No relevant tables were identified from your query. "
                "Could you specify which tables you'd like to query?",
                reason="missing_tables",
                missing_fields=["tables"],
            )

        all_tables = set(self.schema.list_all_tables())
        invalid_tables = [table for table in intent.tables if table not in all_tables]

        if invalid_tables:
            valid_tables_str = ", ".join(sorted(all_tables))
            return ClarificationRequest(
                message=f"The following tables were not found in the database: {', '.join(invalid_tables)}. "
                f"Available tables are: {valid_tables_str}",
                reason="invalid_tables",
                ambiguous_fields=["tables"],
            )
        return None

    def _validate_operations(self, intent: Intent) -> Optional[ClarificationRequest]:
        """Validate that required operations are present for the query type."""
        if intent.query_type == QueryType.AGGREGATION and not intent.operations:
            return ClarificationRequest(
                message="An aggregation query was detected, but no specific operations "
                "(like COUNT, SUM, AVG) were specified. What type of aggregation "
                "would you like to perform?",
                reason="missing_operations",
                missing_fields=["operations"],
            )
        return None

    def _enhance_metadata(self, intent: Intent) -> dict:
        """Add helpful metadata for downstream processing."""
        metadata = {}

        # Add information about table relationships
        for table in intent.tables:
            referenced = self.schema.get_referenced_tables(table)
            if referenced:
                metadata.setdefault("table_relationships", {})[table] = {
                    "referenced_tables": list(referenced)
                }

        return metadata

    def validate(self, intent: Intent) -> Union[ValidIntent, ClarificationRequest]:
        """
        Validates the intent against schema and predefined rules.

        Args:
            intent: The Intent object to validate

        Returns:
            Either a ValidIntent if validation passes, or a ClarificationRequest if
            clarification is needed.
        """
        log.debug("validating_intent", intent=intent.model_dump())

        # Run validation checks in sequence
        # 1. Check confidence first
        if result := self._check_confidence(intent):
            log.info("validation_failed", reason=result.reason, message=result.message)
            return result

        # 2. Check if tables are present (missing tables)
        if not intent.tables:
            result = self._validate_tables(
                intent
            )  # This will return missing_tables error
            log.info("validation_failed", reason=result.reason, message=result.message)
            return result

        # 3. Check operations before table validation to catch missing operations early
        if result := self._validate_operations(intent):
            log.info("validation_failed", reason=result.reason, message=result.message)
            return result

        # 4. Finally validate table existence
        if result := self._validate_tables(
            intent
        ):  # This will return invalid_tables error
            log.info("validation_failed", reason=result.reason, message=result.message)
            return result

        # If all checks pass, enhance with metadata and return
        enhanced_metadata = self._enhance_metadata(intent)
        valid_intent = ValidIntent(
            original_intent=intent, enhanced_metadata=enhanced_metadata
        )

        log.info(
            "intent_validated",
            query_type=intent.query_type,
            tables=intent.tables,
            enhanced_metadata=enhanced_metadata,
        )

        return valid_intent
