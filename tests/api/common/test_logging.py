"""Tests for logging configuration."""

import json
import logging
import sys
from io import StringIO
from unittest.mock import patch

import pytest
import structlog
from fastapi import FastAPI
from starlette.testclient import TestClient

from sens.api.common.logging import (
    RequestLoggingMiddleware,
    configure_logging,
    get_logger,
)
from sens.settings import Settings
from sens.settings.models import LoggingConfig


@pytest.fixture
def capture_logs():
    """Capture logs written to stdout."""
    string_io = StringIO()
    with patch("sys.stdout", string_io):
        yield string_io


@pytest.fixture
def test_app():
    """Create a test FastAPI application with logging middleware."""
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/test")
    async def test_endpoint():
        return {"message": "success"}

    @app.get("/error")
    async def error_endpoint():
        raise ValueError("Test error")

    return app


def test_json_logging(capture_logs):
    """Test JSON format logging configuration."""
    with patch.dict(
        "os.environ", {"SENS_LOG_FORMAT": "json", "SENS_LOG_LEVEL": "INFO"}
    ):
        configure_logging()
        log = structlog.get_logger()
        log.info("test_message", key="value")

        output = capture_logs.getvalue()
        log_entry = json.loads(output)

        assert log_entry["event"] == "test_message"
        assert log_entry["key"] == "value"
        assert "timestamp" in log_entry
        assert log_entry["level"] == "info"


def test_pretty_logging(capture_logs):
    """Test pretty format logging configuration."""
    with patch.dict(
        "os.environ",
        {
            "SENS_LOG_FORMAT": "pretty",
            "SENS_LOG_LEVEL": "DEBUG",
            "SENS_LOG_COLORS": "true",
        },
    ):
        configure_logging()
        log = structlog.get_logger()
        log.debug("test_debug_message", key="value")

        output = capture_logs.getvalue()
        assert "test_debug_message" in output
        assert "value" in output
        assert "[debug]" in output.lower()


def test_log_level_propagation():
    """Test log level is correctly propagated."""
    with patch.dict(
        "os.environ", {"SENS_LOG_LEVEL": "DEBUG", "SENS_LOG_FORMAT": "json"}
    ):
        configure_logging()
        assert logging.getLogger().getEffectiveLevel() == logging.DEBUG


def test_invalid_log_format():
    """Test that invalid log format raises ValueError."""
    with patch.dict("os.environ", {"SENS_LOG_FORMAT": "invalid"}):
        with pytest.raises(
            ValueError, match="Log format must be either 'json' or 'pretty'"
        ):
            configure_logging()


def test_invalid_log_level():
    """Test that invalid log level raises ValueError."""
    with patch.dict("os.environ", {"SENS_LOG_LEVEL": "INVALID"}):
        with pytest.raises(ValueError, match="Log level must be one of:"):
            configure_logging()


def test_request_logging_middleware_success(test_app, capture_logs):
    """Test request logging middleware for successful requests."""
    with patch.dict("os.environ", {"SENS_LOG_FORMAT": "json"}):
        configure_logging()
        client = TestClient(test_app)

        response = client.get("/test")
        assert response.status_code == 200

        output = capture_logs.getvalue()
        log_entries = [json.loads(line) for line in output.strip().split("\n")]

        # Check request start log
        start_log = log_entries[0]
        assert start_log["event"] == "request_start"
        assert start_log["method"] == "GET"
        assert start_log["path"] == "/test"

        # Check request complete log
        complete_log = log_entries[1]
        assert complete_log["event"] == "request_complete"
        assert complete_log["status_code"] == 200
        assert "duration" in complete_log


def test_request_logging_middleware_error(test_app, capture_logs):
    """Test request logging middleware for error requests."""
    with patch.dict("os.environ", {"SENS_LOG_FORMAT": "json"}):
        configure_logging()
        client = TestClient(test_app)

        with pytest.raises(ValueError, match="Test error"):
            client.get("/error")

        output = capture_logs.getvalue()
        log_entries = [json.loads(line) for line in output.strip().split("\n")]

        # Check error log
        error_log = log_entries[-1]
        assert error_log["event"] == "request_error"
        assert error_log["method"] == "GET"
        assert error_log["path"] == "/error"
        assert "Test error" in error_log["error"]
        assert "duration" in error_log
