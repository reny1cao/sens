"""Tests for enhanced NL2SQL pipeline."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sens.chat.exceptions import ChatError
from sens.chat.state import ConversationState
from sens.cli.enhanced_pipeline import EnhancedNL2SQLPipeline
from sens.monitoring.metrics import PipelineMetrics


@pytest.fixture
def mock_orchestrator():
    """Mock ChatOrchestrator instance."""
    with patch("sens.cli.enhanced_pipeline.ChatOrchestrator") as mock:
        instance = AsyncMock()
        mock.return_value = instance
        yield instance


@pytest.fixture
def sample_success_response():
    """Sample successful response from ChatOrchestrator."""
    return {
        "status": "success",
        "summary": "Found 5 users",
        "sql": "SELECT * FROM users LIMIT 5",
        "result": {
            "preview": [["1", "user1"], ["2", "user2"]],
            "columns": ["id", "name"],
            "row_count": 2,
        },
        "metadata": {
            "pipeline_metrics": {
                "conversation_id": "test-123",
                "total_duration_ms": 1234.56,
                "success": True,
                "steps": [
                    {
                        "name": "schema_retrieval",
                        "duration_ms": 100.0,
                        "success": True,
                    }
                ],
            },
            "debug": {
                "conversation_id": "test-123",
                "interaction_count": 1,
            },
        },
    }


@pytest.fixture
def sample_error_response():
    """Sample error response from ChatOrchestrator."""
    return {
        "status": "error",
        "message": "Failed to process query",
        "metadata": {
            "pipeline_metrics": {
                "conversation_id": "test-123",
                "total_duration_ms": 500.0,
                "success": False,
                "error": "Schema retrieval failed",
            },
            "debug": {
                "error_type": "SchemaRetrievalError",
                "conversation_id": "test-123",
            },
        },
    }


async def test_pipeline_initialization():
    """Test pipeline initialization with various options."""
    # Test default initialization
    pipeline = EnhancedNL2SQLPipeline()
    assert pipeline.metrics_enabled is False
    assert pipeline.debug_mode is False
    assert pipeline.orchestrator is not None

    # Test with options
    pipeline = EnhancedNL2SQLPipeline(
        conversation_id="test-123",
        metrics_enabled=True,
        debug_mode=True,
    )
    assert pipeline.metrics_enabled is True
    assert pipeline.debug_mode is True
    assert pipeline.orchestrator is not None


async def test_successful_question_processing(
    mock_orchestrator, sample_success_response
):
    """Test successful processing of a question."""
    mock_orchestrator.step.return_value = sample_success_response
    pipeline = EnhancedNL2SQLPipeline(
        conversation_id="test-123",
        metrics_enabled=True,
        debug_mode=True,
    )

    result = await pipeline.process_question(
        question="How many users are there?",
        format_type="json",
        show_preview=True,
        max_rows=5,
    )

    assert result["status"] == "success"
    assert "pipeline_metrics" in result["metadata"]
    assert "debug" in result["metadata"]
    assert result["metadata"]["pipeline_metrics"]["success"] is True


async def test_error_handling(mock_orchestrator, sample_error_response):
    """Test error handling during question processing."""
    mock_orchestrator.step.return_value = sample_error_response
    pipeline = EnhancedNL2SQLPipeline(
        conversation_id="test-123",
        metrics_enabled=True,
        debug_mode=True,
    )

    result = await pipeline.process_question(
        question="Invalid question",
        format_type="json",
    )

    assert result["status"] == "error"
    assert "Failed to process query" in result["message"]
    assert "pipeline_metrics" in result["metadata"]
    assert result["metadata"]["pipeline_metrics"]["success"] is False


async def test_metrics_disabled(mock_orchestrator, sample_success_response):
    """Test response when metrics are disabled."""
    mock_orchestrator.step.return_value = sample_success_response
    pipeline = EnhancedNL2SQLPipeline(
        conversation_id="test-123",
        metrics_enabled=False,
        debug_mode=False,
    )

    result = await pipeline.process_question(
        question="How many users are there?",
        format_type="json",
    )

    assert result["status"] == "success"
    assert "pipeline_metrics" not in result["metadata"]
    assert "debug" not in result["metadata"]


async def test_debug_mode(mock_orchestrator, sample_success_response):
    """Test response in debug mode."""
    mock_orchestrator.step.return_value = sample_success_response
    pipeline = EnhancedNL2SQLPipeline(
        conversation_id="test-123",
        metrics_enabled=False,
        debug_mode=True,
    )

    result = await pipeline.process_question(
        question="How many users are there?",
        format_type="json",
    )

    assert result["status"] == "success"
    assert "debug" in result["metadata"]
    assert "conversation_id" in result["metadata"]["debug"]
    assert "interaction_count" in result["metadata"]["debug"]


async def test_unexpected_error(mock_orchestrator):
    """Test handling of unexpected errors."""
    mock_orchestrator.step.side_effect = Exception("Unexpected error")
    pipeline = EnhancedNL2SQLPipeline(
        conversation_id="test-123",
        metrics_enabled=True,
        debug_mode=True,
    )

    result = await pipeline.process_question(
        question="How many users are there?",
        format_type="json",
    )

    assert result["status"] == "error"
    assert "Unexpected error" in result["message"]
    assert "pipeline_metrics" in result["metadata"]
    assert "debug" in result["metadata"]
    assert result["metadata"]["debug"]["error_type"] == "Exception"
