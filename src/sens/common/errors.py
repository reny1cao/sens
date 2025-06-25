"""
Centralized error handling utilities for SENS.
"""

import logging
import traceback
from functools import wraps
from typing import Any, Callable, Dict, Optional, Type

from fastapi import HTTPException
from fastapi.responses import JSONResponse

from ..api.models.common import ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)


class SENSError(Exception):
    """Base exception for all SENS errors."""

    def __init__(
        self,
        message: str,
        code: str = "SENS_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class ValidationError(SENSError):
    """Validation errors."""

    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        super().__init__(message, code="VALIDATION_ERROR", status_code=400, **kwargs)
        if field:
            self.details["field"] = field


class NotFoundError(SENSError):
    """Resource not found errors."""

    def __init__(self, message: str, resource_type: Optional[str] = None, **kwargs):
        super().__init__(message, code="NOT_FOUND", status_code=404, **kwargs)
        if resource_type:
            self.details["resource_type"] = resource_type


class AuthenticationError(SENSError):
    """Authentication errors."""

    def __init__(self, message: str = "Authentication required", **kwargs):
        super().__init__(
            message, code="AUTHENTICATION_ERROR", status_code=401, **kwargs
        )


class AuthorizationError(SENSError):
    """Authorization errors."""

    def __init__(self, message: str = "Permission denied", **kwargs):
        super().__init__(message, code="AUTHORIZATION_ERROR", status_code=403, **kwargs)


class DatabaseError(SENSError):
    """Database-related errors."""

    def __init__(self, message: str, query: Optional[str] = None, **kwargs):
        super().__init__(message, code="DATABASE_ERROR", status_code=500, **kwargs)
        if query:
            self.details["query"] = query


class ExternalServiceError(SENSError):
    """External service errors (LLM, etc)."""

    def __init__(self, message: str, service: Optional[str] = None, **kwargs):
        super().__init__(
            message, code="EXTERNAL_SERVICE_ERROR", status_code=502, **kwargs
        )
        if service:
            self.details["service"] = service


class ErrorHandler:
    """Centralized error handler for consistent error responses."""

    @staticmethod
    def handle_error(
        error: Exception, request_id: Optional[str] = None
    ) -> ErrorResponse:
        """Convert exception to ErrorResponse."""
        if isinstance(error, SENSError):
            return ErrorResponse(
                error=error.message,
                details=[
                    ErrorDetail(
                        code=error.code, message=error.message, context=error.details
                    )
                ],
                request_id=request_id,
            )
        elif isinstance(error, HTTPException):
            return ErrorResponse(
                error=error.detail,
                details=[
                    ErrorDetail(code=f"HTTP_{error.status_code}", message=error.detail)
                ],
                request_id=request_id,
            )
        else:
            # Generic error handling
            logger.error(f"Unhandled error: {str(error)}", exc_info=True)
            return ErrorResponse(
                error="An unexpected error occurred",
                details=[
                    ErrorDetail(
                        code="INTERNAL_ERROR",
                        message=str(error),
                        context={"traceback": traceback.format_exc()},
                    )
                ],
                request_id=request_id,
            )

    @staticmethod
    def to_http_response(
        error: Exception, request_id: Optional[str] = None
    ) -> JSONResponse:
        """Convert exception to FastAPI JSONResponse."""
        error_response = ErrorHandler.handle_error(error, request_id)

        status_code = 500
        if isinstance(error, SENSError):
            status_code = error.status_code
        elif isinstance(error, HTTPException):
            status_code = error.status_code

        return JSONResponse(status_code=status_code, content=error_response.dict())


def handle_exceptions(
    exceptions: Dict[Type[Exception], Callable] = None,
    default_message: str = "Operation failed",
    log_errors: bool = True,
):
    """
    Decorator for consistent exception handling.

    Args:
        exceptions: Mapping of exception types to handler functions
        default_message: Default error message
        log_errors: Whether to log errors
    """

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if log_errors:
                    logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)

                if exceptions and type(e) in exceptions:
                    handler = exceptions[type(e)]
                    if callable(handler):
                        return handler(e)
                    else:
                        raise SENSError(str(handler))

                # Re-raise SENS errors
                if isinstance(e, SENSError):
                    raise

                # Wrap other errors
                raise SENSError(
                    message=default_message, details={"original_error": str(e)}
                )

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_errors:
                    logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)

                if exceptions and type(e) in exceptions:
                    handler = exceptions[type(e)]
                    if callable(handler):
                        return handler(e)
                    else:
                        raise SENSError(str(handler))

                # Re-raise SENS errors
                if isinstance(e, SENSError):
                    raise

                # Wrap other errors
                raise SENSError(
                    message=default_message, details={"original_error": str(e)}
                )

        # Return appropriate wrapper based on function type
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# Singleton error handler instance
error_handler = ErrorHandler()
