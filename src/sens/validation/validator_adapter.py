"""
Adapter to make SQLValidator implement the Validator interface.
"""

from typing import Any, Dict, List, Optional

from ..interfaces import ValidationLevel, ValidationResult, Validator
from .sql_validator import SQLValidator


class ValidatorAdapter(Validator):
    """Adapts SQLValidator to implement Validator interface."""

    def __init__(self, sql_validator: SQLValidator, **kwargs):
        self.sql_validator = sql_validator
        self.config = kwargs

    async def validate(
        self,
        sql: str,
        level: ValidationLevel = ValidationLevel.SAFETY,
        schema_context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> ValidationResult:
        """Validate SQL query."""
        # For now, return a mock result
        # TODO: Implement actual validation
        return ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
            level_passed=level,
            metadata={"adapter": "sql_validator"},
        )

    def get_supported_levels(self) -> List[ValidationLevel]:
        """Get supported validation levels."""
        return [ValidationLevel.SYNTAX, ValidationLevel.SCHEMA, ValidationLevel.SAFETY]
