"""
Common utilities shared across SENS components.
"""

from .errors import ErrorHandler, SENSError, error_handler, handle_exceptions
from .metrics import MetricsCollector, track_event, track_timing
from .response_builder import (
    ResponseBuilder,
    build_error_response,
    build_success_response,
    format_sql_results,
)

__all__ = [
    # Errors
    "SENSError",
    "ErrorHandler",
    "error_handler",
    "handle_exceptions",
    # Response building
    "ResponseBuilder",
    "format_sql_results",
    "build_error_response",
    "build_success_response",
    # Metrics
    "MetricsCollector",
    "track_timing",
    "track_event",
]
