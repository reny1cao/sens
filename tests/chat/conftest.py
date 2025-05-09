"""Shared test fixtures for chat module tests."""

from datetime import datetime

import pytest

from sens.chat.state import ClarificationRequest, ConversationState
from sens.llm.models import Intent, QueryType


@pytest.fixture
def sample_intent():
    """Create a sample intent for testing."""
    return Intent(
        query_type=QueryType.LOOKUP,
        tables=["orders"],
        confidence=0.9,
    )


@pytest.fixture
def sample_clarification():
    """Create a sample clarification request for testing."""
    return ClarificationRequest(
        message="Which year would you like to see orders from?",
        reason="missing_temporal_filter",
        suggestions=["Show orders from 2023", "Show orders from last year"],
        context={"understood_tables": ["orders"]},
    )


@pytest.fixture
def sample_conversation_state(sample_intent, sample_clarification):
    """Create a sample conversation state with history."""
    state = ConversationState(conversation_id="test-123")

    # Add a successful interaction
    state.add_interaction(
        user_input="Show me orders",
        response={
            "status": "success",
            "summary": "Found 10 orders",
            "sql": "SELECT * FROM orders LIMIT 10",
        },
        intent=sample_intent,
    )

    # Add an interaction needing clarification
    state.add_interaction(
        user_input="Show me old orders",
        response={"status": "clarification_needed"},
        clarification=sample_clarification,
    )

    return state
