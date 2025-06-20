"""File-based cache backend for persistent caching."""

import json
import os
import pickle
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import structlog

from .base import CacheBackend

log = structlog.get_logger()


class FileBackend(CacheBackend):
    """File-based cache backend that persists across restarts."""

    def __init__(self, cache_dir: str = "/tmp/sens_cache"):
        """Initialize file-based cache backend.

        Args:
            cache_dir: Directory to store cache files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        log.info("file_cache_initialized", cache_dir=str(self.cache_dir))

    def _get_cache_path(self, key: str) -> Path:
        """Get the file path for a cache key."""
        # Convert CacheKey to string if needed
        key_str = str(key)
        # Replace problematic characters in key
        safe_key = key_str.replace("/", "_").replace(":", "_")
        return self.cache_dir / f"{safe_key}.cache"

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        cache_path = self._get_cache_path(key)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "rb") as f:
                data = pickle.load(f)

            # Check if expired
            if data["expires_at"] and datetime.utcnow() > data["expires_at"]:
                log.debug("cache_expired", key=key)
                os.unlink(cache_path)
                return None

            log.debug("cache_hit", key=key)
            return data["value"]

        except Exception as e:
            log.error("cache_read_error", key=key, error=str(e))
            # Remove corrupted cache file
            try:
                os.unlink(cache_path)
            except:
                pass
            return None

    async def set(self, key: str, value: Any, ttl: Optional[timedelta] = None) -> bool:
        """Set value in cache with optional TTL."""
        cache_path = self._get_cache_path(key)

        try:
            expires_at = None
            if ttl:
                expires_at = datetime.utcnow() + ttl

            data = {
                "value": value,
                "created_at": datetime.utcnow(),
                "expires_at": expires_at,
            }

            # Write atomically by writing to temp file first
            temp_path = cache_path.with_suffix(".tmp")
            with open(temp_path, "wb") as f:
                pickle.dump(data, f)

            # Move to final location
            temp_path.rename(cache_path)

            log.debug("cache_set", key=key, ttl=str(ttl) if ttl else "no_ttl")
            return True

        except Exception as e:
            log.error("cache_write_error", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        cache_path = self._get_cache_path(key)

        try:
            if cache_path.exists():
                os.unlink(cache_path)
                log.debug("cache_deleted", key=key)
                return True
            return False

        except Exception as e:
            log.error("cache_delete_error", key=key, error=str(e))
            return False

    async def clear(self) -> bool:
        """Clear all cached values."""
        try:
            for cache_file in self.cache_dir.glob("*.cache"):
                os.unlink(cache_file)
            log.info("cache_cleared")
            return True

        except Exception as e:
            log.error("cache_clear_error", error=str(e))
            return False

    async def ping(self) -> bool:
        """Check if cache backend is available."""
        try:
            # Try to write a test file
            test_path = self.cache_dir / ".ping"
            test_path.write_text("ping")
            os.unlink(test_path)
            return True
        except:
            return False

    async def cleanup_expired(self) -> int:
        """Clean up expired cache entries."""
        cleaned = 0

        try:
            for cache_file in self.cache_dir.glob("*.cache"):
                try:
                    with open(cache_file, "rb") as f:
                        data = pickle.load(f)

                    # Check if expired
                    if (
                        data.get("expires_at")
                        and datetime.utcnow() > data["expires_at"]
                    ):
                        os.unlink(cache_file)
                        cleaned += 1

                except Exception:
                    # Remove corrupted files
                    os.unlink(cache_file)
                    cleaned += 1

            log.info("cache_cleanup_complete", cleaned=cleaned)
            return cleaned

        except Exception as e:
            log.error("cache_cleanup_error", error=str(e))
            return cleaned

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        cache_path = self._get_cache_path(key)

        if not cache_path.exists():
            return False

        try:
            with open(cache_path, "rb") as f:
                data = pickle.load(f)

            # Check if expired
            if data["expires_at"] and datetime.utcnow() > data["expires_at"]:
                log.debug("cache_expired", key=key)
                os.unlink(cache_path)
                return False

            return True

        except Exception as e:
            log.error("cache_exists_error", key=key, error=str(e))
            return False

    async def clear_namespace(self, namespace: str) -> int:
        """Clear all keys in a namespace."""
        cleared = 0

        try:
            # Match files with namespace prefix
            pattern = f"{namespace}_*.cache"
            for cache_file in self.cache_dir.glob(pattern):
                try:
                    os.unlink(cache_file)
                    cleared += 1
                except Exception as e:
                    log.error(
                        "cache_clear_file_error", file=str(cache_file), error=str(e)
                    )

            log.info("cache_namespace_cleared", namespace=namespace, cleared=cleared)
            return cleared

        except Exception as e:
            log.error("cache_clear_namespace_error", namespace=namespace, error=str(e))
            return cleared

    async def close(self) -> None:
        """Close cache connection (no-op for file backend)."""
        # File backend doesn't maintain persistent connections
        pass
