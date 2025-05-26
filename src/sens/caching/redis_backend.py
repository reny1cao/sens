"""Redis implementation of cache backend."""

import json
import pickle
from datetime import timedelta
from typing import Any, Optional, Union

import redis.asyncio as redis
import structlog
from redis.exceptions import RedisError

from .base import CacheBackend, CacheKey

log = structlog.get_logger()


class RedisBackend(CacheBackend):
    """Redis-based cache backend implementation."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        decode_responses: bool = False,
        max_connections: int = 50,
        socket_timeout: int = 5,
        socket_connect_timeout: int = 5,
    ):
        """Initialize Redis backend.

        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
            password: Redis password if required
            decode_responses: Whether to decode responses
            max_connections: Maximum number of connections
            socket_timeout: Socket timeout in seconds
            socket_connect_timeout: Socket connection timeout in seconds
        """
        self.client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=decode_responses,
            max_connections=max_connections,
            socket_timeout=socket_timeout,
            socket_connect_timeout=socket_connect_timeout,
            auto_close_connection_pool=True,
        )
        self._connected = False

    async def _ensure_connected(self) -> None:
        """Ensure Redis connection is established."""
        if not self._connected:
            try:
                await self.client.ping()
                self._connected = True
                log.info(
                    "redis_connected",
                    host=self.client.connection_pool.connection_kwargs["host"],
                )
            except RedisError as e:
                log.error("redis_connection_failed", error=str(e))
                raise

    async def get(self, key: Union[str, CacheKey]) -> Optional[Any]:
        """Get value from Redis cache."""
        await self._ensure_connected()
        key_str = self._normalize_key(key)

        try:
            value = await self.client.get(key_str)
            if value is None:
                return None

            # Try to deserialize as JSON first, then pickle
            try:
                # If it's bytes and starts with pickle magic bytes, use pickle
                if isinstance(value, bytes) and value.startswith(b"\x80"):
                    return pickle.loads(value)
                # Otherwise try JSON
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                # Fall back to pickle for any other case
                return pickle.loads(value)

        except RedisError as e:
            log.error("redis_get_error", key=key_str, error=str(e))
            return None

    async def set(
        self, key: Union[str, CacheKey], value: Any, ttl: Optional[timedelta] = None
    ) -> bool:
        """Set value in Redis cache with optional TTL."""
        await self._ensure_connected()
        key_str = self._normalize_key(key)

        try:
            # Try to serialize as JSON first for better interoperability
            try:
                serialized = json.dumps(value)
            except (TypeError, ValueError):
                # Fall back to pickle for complex objects
                serialized = pickle.dumps(value)

            if ttl:
                return await self.client.setex(
                    key_str, int(ttl.total_seconds()), serialized
                )
            else:
                return await self.client.set(key_str, serialized)

        except RedisError as e:
            log.error("redis_set_error", key=key_str, error=str(e))
            return False

    async def delete(self, key: Union[str, CacheKey]) -> bool:
        """Delete value from Redis cache."""
        await self._ensure_connected()
        key_str = self._normalize_key(key)

        try:
            result = await self.client.delete(key_str)
            return result > 0
        except RedisError as e:
            log.error("redis_delete_error", key=key_str, error=str(e))
            return False

    async def exists(self, key: Union[str, CacheKey]) -> bool:
        """Check if key exists in Redis cache."""
        await self._ensure_connected()
        key_str = self._normalize_key(key)

        try:
            return await self.client.exists(key_str) > 0
        except RedisError as e:
            log.error("redis_exists_error", key=key_str, error=str(e))
            return False

    async def clear_namespace(self, namespace: str) -> int:
        """Clear all keys matching namespace pattern."""
        await self._ensure_connected()
        pattern = f"{namespace}:*"

        try:
            # Use SCAN for memory-efficient deletion
            deleted = 0
            async for key in self.client.scan_iter(match=pattern, count=100):
                if await self.client.delete(key):
                    deleted += 1

            log.info("redis_namespace_cleared", namespace=namespace, deleted=deleted)
            return deleted

        except RedisError as e:
            log.error("redis_clear_namespace_error", namespace=namespace, error=str(e))
            return 0

    async def close(self) -> None:
        """Close Redis connection."""
        if self._connected:
            await self.client.close()
            self._connected = False
            log.info("redis_connection_closed")
