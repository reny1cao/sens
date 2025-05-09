"""Custom exceptions for the chat module."""

from typing import Optional


class ChatError(Exception):
    """Base class for all chat-related errors."""

    def __init__(self, message: str, details: Optional[dict] = None):
        """Initialize with message and optional details."""
        super().__init__(message)
        self.details = details or {}


class UnexpectedError(Exception):
    """Represents an unexpected error that should not be wrapped in a ChatError."""

    pass


class SchemaRetrievalError(ChatError):
    """Raised when schema context retrieval fails."""

    pass


class IntentExtractionError(ChatError):
    """Raised when intent extraction fails."""

    pass


class SQLGenerationError(ChatError):
    """Raised when SQL generation fails."""

    pass


class SQLValidationError(ChatError):
    """Raised when SQL validation fails."""

    pass


class SQLExecutionError(ChatError):
    """Raised when SQL execution fails."""

    pass


class ResponseBuildingError(ChatError):
    """Raised when response building fails."""

    pass
