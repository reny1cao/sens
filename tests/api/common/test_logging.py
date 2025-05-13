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
        "os.environ",
        {
            "SENS_LOG_FORMAT": "json",
            "SENS_LOG_LEVEL": "INFO",
            "SENS_LOG_COLORS": "false",
        },
    ):
        configure_logging()
        log = structlog.get_logger()
        log.info("test_message", key="value")

        output = capture_logs.getvalue()
        log_lines = [line for line in output.strip().split("\n") if line]
        assert len(log_lines) > 0

        # Parse the last log line (our test message)
        log_entry = json.loads(log_lines[-1])
        assert "event" in log_entry
        assert "key" in log_entry
        assert "timestamp" in log_entry
        assert "level" in log_entry
        assert log_entry["level"] == "info"
        assert log_entry["key"] == "value"


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
        assert "debug" in output.lower()


def test_log_level_propagation():
    """Test log level is correctly propagated."""
    with patch.dict(
        "os.environ",
        {
            "SENS_LOG_LEVEL": "DEBUG",
            "SENS_LOG_FORMAT": "json",
            "SENS_LOG_COLORS": "false",
        },
    ):
        configure_logging()
        root_logger = logging.getLogger()
        assert root_logger.getEffectiveLevel() == logging.DEBUG


def test_invalid_log_format():
    """Test that invalid log format raises ValueError."""
    with patch.dict(
        "os.environ",
        {
            "SENS_LOG_FORMAT": "invalid",
            "SENS_LOG_LEVEL": "INFO",
        },
    ):
        with pytest.raises(ValueError) as exc_info:
            LoggingConfig(format="invalid")
        assert "Log format must be either 'json' or 'pretty'" in str(exc_info.value)


def test_invalid_log_level():
    """Test that invalid log level raises ValueError."""
    with patch.dict(
        "os.environ",
        {
            "SENS_LOG_FORMAT": "json",
            "SENS_LOG_LEVEL": "INVALID",
        },
    ):
        with pytest.raises(ValueError) as exc_info:
            LoggingConfig(level="INVALID")
        assert "Log level must be one of:" in str(exc_info.value)


def test_request_logging_middleware_success(test_app, capture_logs):
    """Test request logging middleware for successful requests."""
    with patch.dict(
        "os.environ",
        {
            "SENS_LOG_FORMAT": "json",
            "SENS_LOG_LEVEL": "INFO",
            "SENS_LOG_COLORS": "false",
        },
    ):
        configure_logging()
        client = TestClient(test_app)

        response = client.get("/test")
        assert response.status_code == 200

        output = capture_logs.getvalue()
        log_lines = [line for line in output.strip().split("\n") if line]
        log_entries = []
        for line in log_lines:
            try:
                log_entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        # Find request logs
        request_logs = [
            log
            for log in log_entries
            if isinstance(log, dict) and log.get("logger") == "request"
        ]

        # Check request start log
        start_logs = [
            log for log in request_logs if log.get("event") == "request_start"
        ]
        assert len(start_logs) > 0
        start_log = start_logs[0]
        assert start_log["method"] == "GET"
        assert start_log["path"] == "/test"
        assert start_log["client_ip"] == "testclient"

        # Check request complete log
        complete_logs = [
            log for log in request_logs if log.get("event") == "request_complete"
        ]
        assert len(complete_logs) > 0
        complete_log = complete_logs[0]
        assert complete_log["method"] == "GET"
        assert complete_log["path"] == "/test"
        assert complete_log["status_code"] == 200
        assert "duration" in complete_log


def test_request_logging_middleware_error(test_app, capture_logs):
    """Test request logging middleware for error requests."""
    with patch.dict(
        "os.environ",
        {
            "SENS_LOG_FORMAT": "json",
            "SENS_LOG_LEVEL": "INFO",
            "SENS_LOG_COLORS": "false",
        },
    ):
        configure_logging()
        client = TestClient(test_app)

        with pytest.raises(ValueError, match="Test error"):
            client.get("/error")

        output = capture_logs.getvalue()
        log_lines = [line for line in output.strip().split("\n") if line]
        log_entries = []
        for line in log_lines:
            try:
                log_entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        # Find request logs
        request_logs = [
            log
            for log in log_entries
            if isinstance(log, dict) and log.get("logger") == "request"
        ]

        # Check error log
        error_logs = [
            log for log in request_logs if log.get("event") == "request_error"
        ]
        assert len(error_logs) > 0
        error_log = error_logs[0]
        assert error_log["method"] == "GET"
        assert error_log["path"] == "/error"
        assert "Test error" in error_log["error"]
        assert "duration" in error_log
