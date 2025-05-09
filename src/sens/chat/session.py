"""Session management module for persisting conversation state in Redis."""

import logging
import os
from typing import Optional

import redis
from pydantic import ValidationError

from sens.chat.state import ConversationState

log = logging.getLogger(__name__)


class SessionManager:
    """Manages the persistence and retrieval of ConversationState using Redis."""

    def __init__(
        self,
        redis_url: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
    ):
        """Initialize the session manager and Redis client."""
        self._redis_url = redis_url or os.getenv(
            "SENS_REDIS_URL", "redis://localhost:6379"
        )
        self._ttl_seconds = ttl_seconds or int(
            os.getenv("SENS_SESSION_TTL_SECONDS", 24 * 60 * 60)
        )
        self.redis_client: Optional[redis.Redis] = None
        self.redis_available = False
        try:
            self.redis_client = redis.Redis.from_url(
                self._redis_url, socket_connect_timeout=1
            )
            if self.redis_client.ping():
                self.redis_available = True
                log.info(f"Successfully connected to Redis at {self._redis_url}")
            else:
                log.warning(
                    f"Connected to Redis at {self._redis_url} but ping failed. "
                    "Session persistence might be unreliable."
                )
        except redis.exceptions.ConnectionError as e:
            log.warning(
                f"Could not connect to Redis at {self._redis_url}: {e}. "
                "SessionManager will operate in a degraded mode (no session persistence)."
            )
        except Exception as e:
            log.error(
                f"An unexpected error occurred while initializing Redis client with URL {self._redis_url}: {e}. "
                "SessionManager will operate in a degraded mode."
            )
            self.redis_client = None

    def save(self, session_id: str, state: ConversationState) -> None:
        """Save the ConversationState to Redis with a TTL."""
        if not self.redis_available or not self.redis_client:
            log.warning(
                "Redis is unavailable. Cannot save session state for session_id: %s",
                session_id,
            )
            return
        try:
            json_state = state.model_dump_json()
            self.redis_client.setex(session_id, self._ttl_seconds, json_state)
            log.debug("Session state saved for session_id: %s", session_id)
        except redis.exceptions.RedisError as e:
            log.error(
                "Redis error while saving session state for session_id %s: %s",
                session_id,
                e,
            )
        except Exception as e:
            log.error(
                "Unexpected error while saving session state for session_id %s: %s",
                session_id,
                e,
            )

    def get(self, session_id: str) -> Optional[ConversationState]:
        """Retrieve the ConversationState from Redis."""
        if not self.redis_available or not self.redis_client:
            log.warning(
                "Redis is unavailable. Cannot get session state for session_id: %s",
                session_id,
            )
            return None
        try:
            json_state = self.redis_client.get(session_id)
            if json_state is None:
                log.debug(
                    "No session state found in Redis for session_id: %s", session_id
                )
                return None
            if isinstance(json_state, bytes):
                json_state_str = json_state.decode("utf-8")
            else:
                json_state_str = str(json_state)
            state = ConversationState.model_validate_json(json_state_str)
            log.debug("Session state retrieved for session_id: %s", session_id)
            return state
        except redis.exceptions.RedisError as e:
            log.error(
                "Redis error while retrieving session state for session_id %s: %s",
                session_id,
                e,
            )
            return None
        except ValidationError as e:
            log.error(
                "Failed to validate session data from Redis for session_id %s (data might be corrupt or outdated): %s",
                session_id,
                e,
            )
            return None
        except Exception as e:
            log.error(
                "Unexpected error while retrieving or deserializing session state for session_id %s: %s",
                session_id,
                e,
            )
            return None
