"""
Standard interface for SQL generation components.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .retriever import RetrievalResult


@dataclass
class GenerationContext:
    """Context provided to SQL generators."""

    retrieval_result: RetrievalResult
    query: str
    intent: Optional[Dict[str, Any]] = None
    session_context: Optional[Dict[str, Any]] = None
    constraints: Optional[Dict[str, Any]] = None


@dataclass
class GenerationResult:
    """Result from SQL generation."""

    sql: str
    confidence: float
    explanation: Optional[str] = None
    alternatives: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class SQLGenerator(ABC):
    """
    Abstract base class for SQL generation implementations.

    This interface allows different generation strategies while
    maintaining consistent input/output contracts.
    """

    @abstractmethod
    async def generate(self, context: GenerationContext, **kwargs) -> GenerationResult:
        """
        Generate SQL from the provided context.

        Args:
            context: Generation context with query and retrieval results
            **kwargs: Additional generator-specific parameters

        Returns:
            GenerationResult with SQL and metadata
        """
        pass

    @abstractmethod
    async def extract_intent(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Extract intent from natural language query.

        Args:
            query: Natural language query
            **kwargs: Additional parameters

        Returns:
            Dictionary containing intent information
        """
        pass
