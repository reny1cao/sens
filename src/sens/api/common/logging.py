"""Logging configuration for the API."""

import logging
import sys
import time
from typing import Any, Awaitable, Callable

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send


def configure_logging() -> None:
    """Configure structured logging for the application."""
    # Set up basic logging level
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )

    # Configure structlog
    structlog.configure(
        processors=[
            # If log level is too low, abort pipeline and throw away log entry.
            structlog.stdlib.filter_by_level,
            # Add log level to event dict.
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            # Add timestamps
            structlog.processors.TimeStamper(fmt="iso"),
            # If the "stack_info" key in the event dict is true, remove it and
            # render the current stack trace in the "stack" key.
            structlog.processors.StackInfoRenderer(),
            # If the "exc_info" key in the event dict is either true or a
            # sys.exc_info() tuple, remove "exc_info" and render the exception
            # with traceback into the "exception" key.
            structlog.processors.format_exc_info,
            # If some value is in bytes, decode it to unicode
            structlog.processors.UnicodeDecoder(),
            # Convert to JSON format
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a logger instance with the given name.

    Args:
        name: Name for the logger, typically __name__

    Returns:
        A configured structured logger
    """
    return structlog.get_logger(name)


class RequestLoggingMiddleware:
    """ASGI middleware for logging request information."""

    def __init__(self, app: ASGIApp) -> None:
        """Initialize the middleware.

        Args:
            app: ASGI application
        """
        self.app = app
        self.logger = get_logger("request")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Process the ASGI request.

        Args:
            scope: ASGI scope
            receive: ASGI receive function
            send: ASGI send function
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()

        # Extract request info from scope
        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "UNKNOWN")
        client = scope.get("client", ("UNKNOWN", 0))[0]

        # Log request start
        self.logger.info("request_start", method=method, path=path, client_ip=client)

        # Intercept the send to capture response status
        response_status = 0

        async def send_wrapper(message: Message) -> None:
            nonlocal response_status
            if message["type"] == "http.response.start":
                response_status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)

            # Log request completion
            self.logger.info(
                "request_complete",
                method=method,
                path=path,
                status_code=response_status,
                duration=time.time() - start_time,
            )

        except Exception as e:
            # Log any unhandled exceptions
            self.logger.error(
                "request_error",
                method=method,
                path=path,
                error=str(e),
                duration=time.time() - start_time,
            )
            raise
