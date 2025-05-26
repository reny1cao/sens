"""Tests for cache manager functionality."""

import asyncio
from datetime import timedelta

import pytest

from sens.caching import CacheKey, CacheManager, MemoryBackend


@pytest.mark.asyncio
async def test_cache_manager_basic_operations():
    """Test basic cache operations."""
    cache = CacheManager(backend=MemoryBackend())

    # Test set and get
    key = CacheKey(namespace="test", key="key1")
    await cache.set(key, "value1")
    assert await cache.get(key) == "value1"

    # Test get with default
    assert await cache.get("nonexistent", default="default") == "default"

    # Test delete
    assert await cache.delete(key) is True
    assert await cache.get(key) is None
    assert await cache.delete(key) is False  # Already deleted


@pytest.mark.asyncio
async def test_cache_manager_ttl():
    """Test TTL functionality."""
    import freezegun

    cache = CacheManager(backend=MemoryBackend())
    key = CacheKey(namespace="test", key="ttl_key")

    with freezegun.freeze_time("2024-01-01 00:00:00"):
        await cache.set(key, "value", ttl=timedelta(seconds=60))
        assert await cache.get(key) == "value"

        # Move forward 30 seconds - should still exist
        with freezegun.freeze_time("2024-01-01 00:00:30"):
            assert await cache.get(key) == "value"

        # Move forward 61 seconds - should be expired
        with freezegun.freeze_time("2024-01-01 00:01:01"):
            assert await cache.get(key) is None


@pytest.mark.asyncio
async def test_cache_manager_key_generation():
    """Test cache key generation."""
    cache = CacheManager()

    # Same arguments should generate same key
    key1 = cache.generate_key("namespace", "arg1", "arg2", kwarg1="value1")
    key2 = cache.generate_key("namespace", "arg1", "arg2", kwarg1="value1")
    assert str(key1) == str(key2)

    # Different arguments should generate different keys
    key3 = cache.generate_key("namespace", "arg1", "arg3", kwarg1="value1")
    assert str(key1) != str(key3)

    # Different namespace should generate different keys
    key4 = cache.generate_key("other_namespace", "arg1", "arg2", kwarg1="value1")
    assert str(key1) != str(key4)


@pytest.mark.asyncio
async def test_cache_manager_get_or_compute():
    """Test get_or_compute functionality."""
    cache = CacheManager()
    key = CacheKey(namespace="test", key="compute")

    # First call should compute
    compute_called = False

    def compute_fn():
        nonlocal compute_called
        compute_called = True
        return "computed_value"

    result = await cache.get_or_compute(key, compute_fn)
    assert result == "computed_value"
    assert compute_called is True

    # Second call should use cache
    compute_called = False
    result = await cache.get_or_compute(key, compute_fn)
    assert result == "computed_value"
    assert compute_called is False

    # Test with async compute function
    async def async_compute_fn():
        await asyncio.sleep(0.01)
        return "async_computed"

    key2 = CacheKey(namespace="test", key="async_compute")
    result = await cache.get_or_compute(key2, async_compute_fn)
    assert result == "async_computed"


@pytest.mark.asyncio
async def test_cache_manager_cached_context():
    """Test cached_context context manager."""
    cache = CacheManager()

    # First time - not cached
    async with cache.cached_context("test_namespace", key_args=("arg1",)) as ctx:
        assert ctx["cached"] is False
        assert ctx["value"] is None

        # Set a value
        ctx["value"] = "computed_result"

    # Second time - should be cached
    async with cache.cached_context("test_namespace", key_args=("arg1",)) as ctx:
        assert ctx["cached"] is True
        assert ctx["value"] == "computed_result"


@pytest.mark.asyncio
async def test_cache_manager_stats():
    """Test cache statistics."""
    cache = CacheManager()

    # Initial stats
    stats = cache.get_stats()
    assert stats["hits"] == 0
    assert stats["misses"] == 0

    # Generate some activity
    key = CacheKey(namespace="test", key="stats")
    await cache.get(key)  # Miss
    await cache.set(key, "value")
    await cache.get(key)  # Hit
    await cache.get(key)  # Hit
    await cache.get("nonexistent")  # Miss

    stats = cache.get_stats()
    assert stats["hits"] == 2
    assert stats["misses"] == 2
    assert stats["sets"] == 1
    assert stats["hit_rate"] == 0.5


@pytest.mark.asyncio
async def test_cache_manager_namespace_clear():
    """Test clearing a namespace."""
    cache = CacheManager()

    # Set some keys in different namespaces
    await cache.set(CacheKey("ns1", "key1"), "value1")
    await cache.set(CacheKey("ns1", "key2"), "value2")
    await cache.set(CacheKey("ns2", "key1"), "value3")

    # Clear namespace 1
    deleted = await cache.clear_namespace("ns1")
    assert deleted == 2

    # Check keys
    assert await cache.get(CacheKey("ns1", "key1")) is None
    assert await cache.get(CacheKey("ns1", "key2")) is None
    assert await cache.get(CacheKey("ns2", "key1")) == "value3"
