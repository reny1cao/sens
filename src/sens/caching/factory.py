"""Factory for creating cache backends based on configuration."""

from datetime import timedelta

import structlog

from ..settings.core import get_settings
from .base import CacheBackend
from .file_backend import FileBackend
from .manager import CacheManager
from .memory_backend import MemoryBackend
from .redis_backend import RedisBackend

log = structlog.get_logger()


def create_cache_backend() -> CacheBackend:
    """Create a cache backend based on current settings.

    Returns:
        CacheBackend instance
    """
    settings = get_settings()
    cache_config = settings.cache

    if cache_config.backend == "redis":
        log.info(
            "Creating Redis cache backend",
            host=cache_config.redis_host,
            port=cache_config.redis_port,
            db=cache_config.redis_db,
        )

        return RedisBackend(
            host=cache_config.redis_host,
            port=cache_config.redis_port,
            db=cache_config.redis_db,
            password=cache_config.redis_password,
        )
    elif cache_config.backend == "file":
        log.info(
            "Creating file-based cache backend",
            cache_dir=cache_config.file_cache_dir,
        )
        return FileBackend(cache_dir=cache_config.file_cache_dir or "/tmp/sens_cache")
    else:
        log.info("Creating in-memory cache backend")
        return MemoryBackend()


def get_cache_manager() -> CacheManager:
    """Get a configured cache manager instance.

    Returns:
        CacheManager with appropriate backend
    """
    backend = create_cache_backend()
    return CacheManager(backend=backend)


def get_cache_ttl(cache_type: str) -> timedelta:
    """Get TTL for specific cache type from settings.

    Args:
        cache_type: Type of cache (embedding, llm, schema)

    Returns:
        timedelta for TTL
    """
    settings = get_settings()
    cache_config = settings.cache

    if cache_type == "embedding":
        return timedelta(hours=cache_config.embedding_ttl_hours)
    elif cache_type == "llm":
        return timedelta(hours=cache_config.llm_ttl_hours)
    elif cache_type == "schema":
        return timedelta(hours=cache_config.schema_ttl_hours)
    else:
        # Default TTL
        return timedelta(seconds=cache_config.ttl_seconds)
