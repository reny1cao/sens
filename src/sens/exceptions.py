"""Custom exceptions for the Sens pipeline."""

from typing import Any, Dict, Optional


class SensError(Exception):
    """Base exception for all Sens errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        """Initialize a SensError.

        Args:
            message: Error message describing what went wrong
            details: Optional dictionary containing additional error context
        """
        super().__init__(message)
        self.details = details or {}


class RetrievalError(SensError):
    """Raised when schema retrieval fails."""

    pass


class IntentExtractionError(SensError):
    """Raised when intent extraction fails."""

    pass


class ValidationError(SensError):
    """Raised when SQL validation fails."""

    pass


class ExecutionError(SensError):
    """Raised when SQL execution fails."""

    pass


class PipelineError(SensError):
    """Raised when the pipeline encounters an unrecoverable error."""

    pass
