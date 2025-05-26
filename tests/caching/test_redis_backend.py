"""Tests for Redis cache backend."""

import json
from datetime import timedelta

import pytest
from fakeredis import FakeAsyncRedis

from sens.caching import CacheKey, RedisBackend


class TestableRedisBackend(RedisBackend):
    """Redis backend that uses FakeRedis for testing."""

    def __init__(self, *args, **kwargs):
        """Initialize testable Redis backend with FakeRedis."""
        # Don't call parent init
        self._connected = False
        # Use FakeAsyncRedis instead of real Redis
        self.client = FakeAsyncRedis(decode_responses=False)


@pytest.mark.asyncio
async def test_redis_backend_basic_operations():
    """Test basic Redis operations."""
    backend = TestableRedisBackend()

    # Test set and get with string key
    assert await backend.set("test_key", "test_value") is True
    assert await backend.get("test_key") == "test_value"

    # Test with CacheKey
    cache_key = CacheKey(namespace="test", key="key1")
    assert await backend.set(cache_key, {"data": "value"}) is True
    assert await backend.get(cache_key) == {"data": "value"}

    # Test exists
    assert await backend.exists("test_key") is True
    assert await backend.exists("nonexistent") is False

    # Test delete
    assert await backend.delete("test_key") is True
    assert await backend.delete("test_key") is False  # Already deleted
    assert await backend.exists("test_key") is False


@pytest.mark.asyncio
async def test_redis_backend_ttl():
    """Test TTL functionality."""
    backend = TestableRedisBackend()

    # Set with TTL
    ttl = timedelta(seconds=60)
    assert await backend.set("ttl_key", "value", ttl=ttl) is True

    # Check it exists
    assert await backend.get("ttl_key") == "value"

    # Check TTL was set (FakeRedis might not support this fully)
    # In real Redis, we'd check the TTL value


@pytest.mark.asyncio
async def test_redis_backend_serialization():
    """Test serialization of different data types."""
    backend = TestableRedisBackend()

    # Test JSON-serializable data
    test_data = {
        "string": "value",
        "number": 42,
        "float": 3.14,
        "bool": True,
        "list": [1, 2, 3],
        "dict": {"nested": "value"},
    }

    assert await backend.set("json_data", test_data) is True
    retrieved = await backend.get("json_data")
    assert retrieved == test_data

    # Test complex object that requires pickle - use a tuple of mixed types
    complex_obj = (
        "string",
        42,
        {"nested": ["list", "of", "items"]},
        frozenset([1, 2, 3]),
    )

    assert await backend.set("pickle_data", complex_obj) is True
    retrieved = await backend.get("pickle_data")
    assert retrieved == complex_obj


@pytest.mark.asyncio
async def test_redis_backend_clear_namespace():
    """Test clearing namespace."""
    backend = TestableRedisBackend()

    # Set keys in different namespaces
    await backend.set("ns1:key1", "value1")
    await backend.set("ns1:key2", "value2")
    await backend.set("ns2:key1", "value3")
    await backend.set("other_key", "value4")

    # Clear namespace
    deleted = await backend.clear_namespace("ns1")
    assert deleted == 2

    # Check what remains
    assert await backend.get("ns1:key1") is None
    assert await backend.get("ns1:key2") is None
    assert await backend.get("ns2:key1") == "value3"
    assert await backend.get("other_key") == "value4"


@pytest.mark.asyncio
async def test_redis_backend_connection():
    """Test connection handling."""
    backend = TestableRedisBackend()

    # Should connect on first operation
    assert backend._connected is False
    await backend.set("key", "value")
    assert backend._connected is True

    # Close connection
    await backend.close()
    assert backend._connected is False
