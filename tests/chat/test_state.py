"""Tests for chat state management models."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from sens.chat.state import ClarificationRequest, ConversationState
from sens.llm.models import Intent, QueryType


def test_clarification_request_creation():
    """Test creating a clarification request."""
    request = ClarificationRequest(
        message="Could you specify which year?",
        reason="missing_temporal_filter",
        suggestions=["Show orders from 2023", "Show orders from last year"],
        context={"understood_tables": ["orders"]},
    )

    assert request.message == "Could you specify which year?"
    assert request.reason == "missing_temporal_filter"
    assert len(request.suggestions) == 2
    assert request.context["understood_tables"] == ["orders"]


def test_clarification_request_validation():
    """Test validation of required fields."""
    with pytest.raises(ValidationError):
        ClarificationRequest()  # Missing required fields

    with pytest.raises(ValidationError):
        ClarificationRequest(message="Test")  # Missing reason

    # Should work with minimal required fields
    request = ClarificationRequest(
        message="Test message",
        reason="test_reason",
    )
    assert request.suggestions == []
    assert request.context == {}


def test_conversation_state_creation():
    """Test creating a conversation state."""
    state = ConversationState(conversation_id="test-123")

    assert state.conversation_id == "test-123"
    assert state.history == []
    assert state.last_valid_intent is None
    assert state.pending_clarification is None
    assert isinstance(state.created_at, datetime)
    assert isinstance(state.updated_at, datetime)


def test_conversation_state_add_interaction():
    """Test adding interactions to conversation state."""
    state = ConversationState(conversation_id="test-123")
    intent = Intent(
        query_type=QueryType.LOOKUP,
        tables=["orders"],
        confidence=0.9,
    )
    clarification = ClarificationRequest(
        message="Which year?",
        reason="missing_year",
    )

    # Add interaction with intent
    state.add_interaction(
        user_input="Show me orders",
        response={"status": "success"},
        intent=intent,
    )
    assert len(state.history) == 1
    assert state.last_valid_intent == intent
    assert state.pending_clarification is None

    # Add interaction with clarification
    state.add_interaction(
        user_input="Show me old orders",
        response={"status": "clarification_needed"},
        clarification=clarification,
    )
    assert len(state.history) == 2
    assert state.pending_clarification == clarification


def test_conversation_state_clear_clarification():
    """Test clearing pending clarification."""
    state = ConversationState(conversation_id="test-123")
    clarification = ClarificationRequest(
        message="Which year?",
        reason="missing_year",
    )

    state.add_interaction(
        user_input="Show old orders",
        response={"status": "clarification_needed"},
        clarification=clarification,
    )
    assert state.pending_clarification is not None

    state.clear_clarification()
    assert state.pending_clarification is None


def test_conversation_state_get_recent_context():
    """Test getting recent conversation context."""
    state = ConversationState(conversation_id="test-123")

    # Add multiple interactions
    for i in range(10):
        state.add_interaction(
            user_input=f"Question {i}",
            response={"status": "success", "answer": f"Answer {i}"},
        )

    # Get recent context with default limit
    recent = state.get_recent_context()
    assert len(recent) == 5
    assert recent[0]["user_input"] == "Question 9"  # Most recent first

    # Get recent context with custom limit
    recent = state.get_recent_context(limit=3)
    assert len(recent) == 3
    assert recent[0]["user_input"] == "Question 9"
