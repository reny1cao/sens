"""Cache manager for coordinating caching operations."""

import asyncio
import hashlib
import json
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any, AsyncIterator, Callable, Optional, TypeVar, Union

import structlog

from .base import CacheBackend, CacheKey
from .memory_backend import MemoryBackend

log = structlog.get_logger()

T = TypeVar("T")


class CacheManager:
    """Manages caching operations with various backends."""

    def __init__(self, backend: Optional[CacheBackend] = None):
        """Initialize cache manager.

        Args:
            backend: Cache backend to use (defaults to MemoryBackend)
        """
        self.backend = backend or MemoryBackend()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
        }

    def generate_key(self, namespace: str, *args, **kwargs) -> CacheKey:
        """Generate a cache key from namespace and arguments.

        Args:
            namespace: Cache namespace
            *args: Positional arguments to include in key
            **kwargs: Keyword arguments to include in key

        Returns:
            CacheKey object
        """
        # Create a stable hash from arguments
        key_data = {
            "args": args,
            "kwargs": kwargs,
        }
        key_json = json.dumps(key_data, sort_keys=True)
        key_hash = hashlib.sha256(key_json.encode()).hexdigest()[:16]

        return CacheKey(namespace=namespace, key=key_hash)

    async def get(
        self, key: Union[str, CacheKey], default: Optional[T] = None
    ) -> Optional[T]:
        """Get value from cache.

        Args:
            key: Cache key
            default: Default value if not found

        Returns:
            Cached value or default
        """
        value = await self.backend.get(key)

        if value is None:
            self._stats["misses"] += 1
            return default

        self._stats["hits"] += 1
        return value

    async def set(
        self, key: Union[str, CacheKey], value: Any, ttl: Optional[timedelta] = None
    ) -> bool:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live

        Returns:
            True if successful
        """
        result = await self.backend.set(key, value, ttl)
        if result:
            self._stats["sets"] += 1
        return result

    async def delete(self, key: Union[str, CacheKey]) -> bool:
        """Delete value from cache.

        Args:
            key: Cache key

        Returns:
            True if key existed and was deleted
        """
        result = await self.backend.delete(key)
        if result:
            self._stats["deletes"] += 1
        return result

    async def get_or_compute(
        self,
        key: Union[str, CacheKey],
        compute_fn: Callable[[], Union[T, Any]],
        ttl: Optional[timedelta] = None,
    ) -> T:
        """Get value from cache or compute it if missing.

        Args:
            key: Cache key
            compute_fn: Function to compute value if not cached
            ttl: Time to live for computed value

        Returns:
            Cached or computed value
        """
        # Try to get from cache
        value = await self.get(key)
        if value is not None:
            return value

        # Compute value
        if asyncio.iscoroutinefunction(compute_fn):
            value = await compute_fn()
        else:
            value = compute_fn()

        # Cache the computed value
        await self.set(key, value, ttl)

        return value

    @asynccontextmanager
    async def cached_context(
        self,
        namespace: str,
        ttl: Optional[timedelta] = None,
        key_args: Optional[tuple] = None,
        key_kwargs: Optional[dict] = None,
    ) -> AsyncIterator[dict]:
        """Context manager for caching operations.

        Example:
            async with cache.cached_context("embeddings", ttl=timedelta(hours=1)) as ctx:
                if ctx["cached"]:
                    return ctx["value"]

                # Compute value
                value = await compute_embeddings()
                ctx["value"] = value

        Args:
            namespace: Cache namespace
            ttl: Time to live
            key_args: Arguments for key generation
            key_kwargs: Keyword arguments for key generation

        Yields:
            Context dict with cached status and value
        """
        key = self.generate_key(namespace, *(key_args or ()), **(key_kwargs or {}))

        # Try to get cached value
        value = await self.get(key)

        ctx = {
            "cached": value is not None,
            "value": value,
            "key": key,
        }

        yield ctx

        # If value was set, cache it
        if not ctx["cached"] and "value" in ctx and ctx["value"] is not None:
            await self.set(key, ctx["value"], ttl)

    def get_stats(self) -> dict:
        """Get cache statistics."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total if total > 0 else 0

        return {
            **self._stats,
            "total_requests": total,
            "hit_rate": hit_rate,
        }

    async def clear_namespace(self, namespace: str) -> int:
        """Clear all keys in a namespace."""
        return await self.backend.clear_namespace(namespace)

    async def close(self) -> None:
        """Close cache backend."""
        await self.backend.close()
