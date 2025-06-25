"""
Standard interface for retrieval components.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class RetrievalStrategy(str, Enum):
    """Supported retrieval strategies."""

    TOKEN = "token"
    EMBEDDING = "embedding"
    HYBRID = "hybrid"


@dataclass
class RetrievalResult:
    """Standard result from retrieval operations."""

    tables: List[str]
    columns: List[Dict[str, Any]]
    context: Dict[str, Any]
    score: float
    strategy_used: RetrievalStrategy
    metadata: Optional[Dict[str, Any]] = None


class Retriever(ABC):
    """
    Abstract base class for all retrieval implementations.

    This interface ensures consistent behavior across different
    retrieval strategies (token-based, embedding-based, hybrid).
    """

    @abstractmethod
    async def retrieve(
        self,
        query: str,
        limit: int = 10,
        strategy: Optional[RetrievalStrategy] = None,
        **kwargs,
    ) -> RetrievalResult:
        """
        Retrieve relevant schema information for a query.

        Args:
            query: Natural language query
            limit: Maximum number of results
            strategy: Optional strategy override
            **kwargs: Additional strategy-specific parameters

        Returns:
            RetrievalResult with tables, columns, and metadata
        """
        pass

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the retriever (load indices, models, etc)."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Clean up resources."""
        pass
