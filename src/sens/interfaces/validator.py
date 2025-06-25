"""
Standard interface for validation components.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Dict, List, Optional


class ValidationLevel(IntEnum):
    """Validation levels from least to most strict."""

    SYNTAX = 1  # Basic SQL syntax check
    SCHEMA = 2  # Schema compatibility check
    SAFETY = 3  # Safety and security check
    SEMANTIC = 4  # Semantic correctness check


@dataclass
class ValidationError:
    """Single validation error."""

    level: ValidationLevel
    message: str
    line: Optional[int] = None
    column: Optional[int] = None
    suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """Result from validation operation."""

    is_valid: bool
    errors: List[ValidationError]
    warnings: List[ValidationError]
    level_passed: ValidationLevel
    metadata: Optional[Dict[str, Any]] = None


class Validator(ABC):
    """
    Abstract base class for SQL validation implementations.

    Validators can check syntax, schema compatibility, safety,
    and semantic correctness of generated SQL.
    """

    @abstractmethod
    async def validate(
        self,
        sql: str,
        level: ValidationLevel = ValidationLevel.SAFETY,
        schema_context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> ValidationResult:
        """
        Validate SQL at the specified level.

        Args:
            sql: SQL query to validate
            level: Maximum validation level to apply
            schema_context: Optional schema information
            **kwargs: Additional validator-specific parameters

        Returns:
            ValidationResult with errors and warnings
        """
        pass

    @abstractmethod
    def get_supported_levels(self) -> List[ValidationLevel]:
        """Get validation levels supported by this validator."""
        pass
