"""Logging configuration for the API."""

import logging
import sys
import time
from typing import Any, Awaitable, Callable, List

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from sens.settings import get_settings


def configure_logging() -> None:
    """Configure structured logging for the application.

    Uses settings to determine:
    - Log format (json/pretty)
    - Log level
    - Color output (for pretty format)

    Always logs to stdout for compatibility with container environments.
    """
    settings = get_settings()
    log_config = settings.logging

    # Set up shared processors
    shared_processors: List[structlog.typing.Processor] = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    # Configure format-specific processors
    if log_config.format == "pretty":
        final_processors = shared_processors + [
            structlog.dev.ConsoleRenderer(
                colors=log_config.enable_colors,
                exception_formatter=structlog.dev.plain_traceback,
            ),
        ]
    else:  # "json" format
        final_processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]

    # Configure structlog
    structlog.configure(
        processors=final_processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure standard logging to use structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_config.level),
    )

    # Log initial configuration
    log = structlog.get_logger(__name__)
    log.info(
        "logging_configured",
        format=log_config.format,
        level=log_config.level,
        colors_enabled=log_config.enable_colors,
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
