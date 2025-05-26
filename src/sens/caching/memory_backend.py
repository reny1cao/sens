"""In-memory implementation of cache backend for testing and development."""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple, Union

import structlog

from .base import CacheBackend, CacheKey

log = structlog.get_logger()


class MemoryBackend(CacheBackend):
    """In-memory cache backend for testing and development."""

    def __init__(self):
        """Initialize in-memory cache."""
        self._cache: Dict[str, Tuple[Any, Optional[datetime]]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: Union[str, CacheKey]) -> Optional[Any]:
        """Get value from memory cache."""
        key_str = self._normalize_key(key)

        async with self._lock:
            if key_str not in self._cache:
                return None

            value, expiry = self._cache[key_str]

            # Check expiry
            if expiry and datetime.utcnow() > expiry:
                del self._cache[key_str]
                return None

            return value

    async def set(
        self, key: Union[str, CacheKey], value: Any, ttl: Optional[timedelta] = None
    ) -> bool:
        """Set value in memory cache with optional TTL."""
        key_str = self._normalize_key(key)

        async with self._lock:
            expiry = None
            if ttl:
                expiry = datetime.utcnow() + ttl

            self._cache[key_str] = (value, expiry)
            return True

    async def delete(self, key: Union[str, CacheKey]) -> bool:
        """Delete value from memory cache."""
        key_str = self._normalize_key(key)

        async with self._lock:
            if key_str in self._cache:
                del self._cache[key_str]
                return True
            return False

    async def exists(self, key: Union[str, CacheKey]) -> bool:
        """Check if key exists in memory cache."""
        key_str = self._normalize_key(key)

        async with self._lock:
            if key_str not in self._cache:
                return False

            _, expiry = self._cache[key_str]
            if expiry and datetime.utcnow() > expiry:
                del self._cache[key_str]
                return False

            return True

    async def clear_namespace(self, namespace: str) -> int:
        """Clear all keys in a namespace."""
        prefix = f"{namespace}:"
        deleted = 0

        async with self._lock:
            keys_to_delete = [k for k in self._cache.keys() if k.startswith(prefix)]
            for key in keys_to_delete:
                del self._cache[key]
                deleted += 1

        return deleted

    async def close(self) -> None:
        """Close cache (no-op for memory backend)."""
        pass
