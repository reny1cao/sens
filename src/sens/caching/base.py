"""Base caching interfaces and types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Optional, Union

import structlog

log = structlog.get_logger()


@dataclass
class CacheKey:
    """Represents a cache key with namespace and identifier."""

    namespace: str
    key: str

    def __str__(self) -> str:
        """Convert to string representation."""
        return f"{self.namespace}:{self.key}"


class CacheBackend(ABC):
    """Abstract base class for cache backends."""

    @abstractmethod
    async def get(self, key: Union[str, CacheKey]) -> Optional[Any]:
        """Get value from cache."""
        pass

    @abstractmethod
    async def set(
        self, key: Union[str, CacheKey], value: Any, ttl: Optional[timedelta] = None
    ) -> bool:
        """Set value in cache with optional TTL."""
        pass

    @abstractmethod
    async def delete(self, key: Union[str, CacheKey]) -> bool:
        """Delete value from cache."""
        pass

    @abstractmethod
    async def exists(self, key: Union[str, CacheKey]) -> bool:
        """Check if key exists in cache."""
        pass

    @abstractmethod
    async def clear_namespace(self, namespace: str) -> int:
        """Clear all keys in a namespace."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close cache connection."""
        pass

    def _normalize_key(self, key: Union[str, CacheKey]) -> str:
        """Normalize key to string format."""
        if isinstance(key, CacheKey):
            return str(key)
        return key
