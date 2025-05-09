"""Tests for performance monitoring and metrics tracking."""

import time
from datetime import UTC, datetime, timedelta

import pytest
import structlog
from structlog.testing import capture_logs

from sens.monitoring.metrics import PipelineMetrics, StepMetrics, track_step


def test_step_metrics_creation():
    """Test creating step metrics."""
    step = StepMetrics(step_name="test_step")
    assert step.step_name == "test_step"
    assert isinstance(step.start_time, datetime)
    assert step.end_time is None
    assert step.duration_ms is None
    assert not step.success
    assert step.error is None
    assert step.metadata == {}


def test_pipeline_metrics_creation():
    """Test creating pipeline metrics."""
    metrics = PipelineMetrics(conversation_id="test-123")
    assert metrics.conversation_id == "test-123"
    assert isinstance(metrics.start_time, datetime)
    assert metrics.end_time is None
    assert metrics.total_duration_ms is None
    assert metrics.steps == []
    assert not metrics.success
    assert metrics.error is None
    assert metrics.metadata == {}


def test_pipeline_metrics_add_step():
    """Test adding steps to pipeline metrics."""
    metrics = PipelineMetrics(conversation_id="test-123")
    step = StepMetrics(step_name="test_step")
    metrics.add_step(step)
    assert len(metrics.steps) == 1
    assert metrics.steps[0] is step


def test_pipeline_metrics_complete():
    """Test completing pipeline metrics."""
    metrics = PipelineMetrics(conversation_id="test-123")
    step = StepMetrics(step_name="test_step")
    step.duration_ms = 100
    step.success = True
    metrics.add_step(step)

    with capture_logs() as cap_logs:
        metrics.complete(success=True)

    assert metrics.success
    assert metrics.error is None
    assert isinstance(metrics.end_time, datetime)
    assert isinstance(metrics.total_duration_ms, float)
    assert metrics.total_duration_ms > 0

    # Verify structured logging
    assert len(cap_logs) == 1
    assert cap_logs[0]["event"] == "pipeline_metrics"
    assert cap_logs[0]["conversation_id"] == "test-123"
    assert cap_logs[0]["success"] is True
    assert cap_logs[0]["step_count"] == 1
    assert len(cap_logs[0]["steps"]) == 1
    assert cap_logs[0]["steps"][0]["name"] == "test_step"
    assert cap_logs[0]["steps"][0]["duration_ms"] == 100


def test_pipeline_metrics_complete_with_error():
    """Test completing pipeline metrics with error."""
    metrics = PipelineMetrics(conversation_id="test-123")

    with capture_logs() as cap_logs:
        metrics.complete(success=False, error="Test error")

    assert not metrics.success
    assert metrics.error == "Test error"
    assert isinstance(metrics.end_time, datetime)
    assert isinstance(metrics.total_duration_ms, float)

    # Verify structured logging
    assert len(cap_logs) == 1
    assert cap_logs[0]["event"] == "pipeline_metrics"
    assert cap_logs[0]["success"] is False
    assert cap_logs[0]["error"] == "Test error"


def test_track_step_success():
    """Test tracking a successful step."""
    metrics = PipelineMetrics(conversation_id="test-123")

    with capture_logs() as cap_logs:
        with track_step(metrics, "test_step") as step:
            time.sleep(0.1)  # Simulate some work
            step.metadata["test_key"] = "test_value"

    assert len(metrics.steps) == 1
    step = metrics.steps[0]
    assert step.step_name == "test_step"
    assert step.success
    assert step.error is None
    assert isinstance(step.duration_ms, float)
    assert step.duration_ms >= 100  # At least 100ms
    assert step.metadata["test_key"] == "test_value"

    # Verify structured logging
    assert len(cap_logs) == 1
    assert cap_logs[0]["event"] == "step_metrics"
    assert cap_logs[0]["step_name"] == "test_step"
    assert cap_logs[0]["success"] is True
    assert cap_logs[0]["metadata"]["test_key"] == "test_value"


def test_track_step_error():
    """Test tracking a step that raises an error."""
    metrics = PipelineMetrics(conversation_id="test-123")

    with capture_logs() as cap_logs:
        with pytest.raises(ValueError, match="Test error"):
            with track_step(metrics, "error_step") as step:
                step.metadata["before_error"] = "test"
                raise ValueError("Test error")

    assert len(metrics.steps) == 1
    step = metrics.steps[0]
    assert step.step_name == "error_step"
    assert not step.success
    assert step.error == "Test error"
    assert isinstance(step.duration_ms, float)
    assert step.metadata["before_error"] == "test"

    # Verify structured logging
    assert len(cap_logs) == 1
    assert cap_logs[0]["event"] == "step_metrics"
    assert cap_logs[0]["step_name"] == "error_step"
    assert cap_logs[0]["success"] is False
    assert cap_logs[0]["error"] == "Test error"
    assert cap_logs[0]["metadata"]["before_error"] == "test"


def test_track_step_nested():
    """Test tracking nested steps."""
    metrics = PipelineMetrics(conversation_id="test-123")

    with track_step(metrics, "outer_step") as outer:
        outer.metadata["outer_key"] = "outer_value"
        with track_step(metrics, "inner_step") as inner:
            inner.metadata["inner_key"] = "inner_value"
            time.sleep(0.1)  # Simulate work

    assert len(metrics.steps) == 2
    assert metrics.steps[0].step_name == "inner_step"
    assert metrics.steps[0].metadata["inner_key"] == "inner_value"
    assert metrics.steps[1].step_name == "outer_step"
    assert metrics.steps[1].metadata["outer_key"] == "outer_value"

    # Inner step duration should be less than outer step
    assert metrics.steps[0].duration_ms <= metrics.steps[1].duration_ms
