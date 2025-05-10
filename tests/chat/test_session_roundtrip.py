"""Integration tests for session management and persistence."""

import uuid
from datetime import UTC, datetime, timedelta

import fakeredis
import pytest

from sens.chat.orchestrator import ChatOrchestrator
from sens.chat.session import SessionManager
from sens.chat.state import ConversationState


@pytest.fixture
def fake_redis():
    """Create a fake Redis instance for testing."""
    server = fakeredis.FakeServer()
    redis_client = fakeredis.FakeStrictRedis(server=server)
    return redis_client


@pytest.fixture
def session_manager(fake_redis):
    """Create a SessionManager with fake Redis for testing."""
    manager = SessionManager()
    manager.redis_client = fake_redis
    manager.redis_available = True
    return manager


@pytest.mark.asyncio
async def test_session_roundtrip(session_manager):
    """Test that conversation state persists across multiple interactions."""
    # Setup
    session_id = str(uuid.uuid4())
    initial_state = ConversationState(conversation_id=session_id)
    orchestrator = ChatOrchestrator(session_manager=session_manager)

    # First interaction
    response1, updated_state = await orchestrator.step(
        state=initial_state,
        user_input="Show me all users",
    )
    assert len(updated_state.history) == 1
    assert updated_state.conversation_id == session_id

    # Verify state was saved
    saved_state = session_manager.get(session_id)
    assert saved_state is not None
    assert len(saved_state.history) == 1

    # Second interaction using the saved state
    response2, final_state = await orchestrator.step(
        state=saved_state,
        user_input="How many are active?",
    )
    assert len(final_state.history) == 2
    assert final_state.conversation_id == session_id

    # Verify final state was saved
    final_saved_state = session_manager.get(session_id)
    assert final_saved_state is not None
    assert len(final_saved_state.history) == 2


@pytest.mark.asyncio
async def test_session_ttl(session_manager):
    """Test that sessions expire after TTL."""
    session_id = str(uuid.uuid4())

    # Save state with a short TTL for testing
    test_ttl = 1  # 1 second TTL
    session_manager.redis_client.set(session_id, "test_data", ex=test_ttl)

    # Verify it exists
    assert session_manager.redis_client.get(session_id) is not None

    # Wait for TTL to expire
    import time

    time.sleep(test_ttl + 0.1)  # Wait slightly longer than TTL

    # State should be expired
    assert session_manager.redis_client.get(session_id) is None


@pytest.mark.asyncio
async def test_corrupt_session_data(session_manager, fake_redis):
    """Test handling of corrupt session data in Redis."""
    session_id = str(uuid.uuid4())

    # Directly insert invalid JSON
    fake_redis.set(session_id, b"not valid json{")

    # Attempt to get state
    state = session_manager.get(session_id)
    assert state is None  # Invalid data should return None
