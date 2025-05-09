from unittest.mock import MagicMock, patch

import pytest
import redis

from sens.chat.session import SessionManager
from sens.chat.state import ConversationState


@pytest.fixture
def session_manager():
    # Patch redis.Redis for all tests
    with patch("redis.Redis") as MockRedis:
        mock_redis = MockRedis.from_url.return_value
        # Simulate successful ping by default
        mock_redis.ping.return_value = True
        yield SessionManager()


def test_save_and_get_roundtrip(session_manager):
    session_id = "test-session"
    state = ConversationState(conversation_id=session_id)
    # Mock setex and get
    session_manager.redis_client.setex = MagicMock()
    session_manager.redis_client.get = MagicMock(
        return_value=state.model_dump_json().encode("utf-8")
    )
    session_manager.save(session_id, state)
    loaded = session_manager.get(session_id)
    assert loaded == state
    session_manager.redis_client.setex.assert_called_once()
    session_manager.redis_client.get.assert_called_once_with(session_id)


def test_save_sets_ttl(session_manager):
    session_id = "ttl-session"
    state = ConversationState(conversation_id=session_id)
    session_manager.redis_client.setex = MagicMock()
    session_manager.save(session_id, state)
    args, kwargs = session_manager.redis_client.setex.call_args
    assert args[0] == session_id
    assert args[1] == session_manager._ttl_seconds


def test_get_returns_none_if_not_found(session_manager):
    session_id = "missing-session"
    session_manager.redis_client.get = MagicMock(return_value=None)
    assert session_manager.get(session_id) is None


def test_fallback_mode(monkeypatch):
    # Simulate Redis unavailable at init
    with patch("redis.Redis.from_url", side_effect=redis.exceptions.ConnectionError):
        mgr = SessionManager(redis_url="redis://badhost:6379")
        assert not mgr.redis_available
        assert mgr.get("any") is None
        # save should not raise
        mgr.save("any", ConversationState(conversation_id="any"))


def test_get_invalid_json(session_manager):
    session_id = "corrupt-session"
    # Return invalid JSON
    session_manager.redis_client.get = MagicMock(return_value=b"{bad json")
    assert session_manager.get(session_id) is None


def test_redis_error_on_save(session_manager):
    session_id = "err-session"
    state = ConversationState(conversation_id=session_id)
    session_manager.redis_client.setex = MagicMock(
        side_effect=redis.exceptions.RedisError
    )
    # Should not raise
    session_manager.save(session_id, state)


def test_redis_error_on_get(session_manager):
    session_id = "err-session"
    session_manager.redis_client.get = MagicMock(
        side_effect=redis.exceptions.RedisError
    )
    assert session_manager.get(session_id) is None
