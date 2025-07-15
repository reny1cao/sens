"""
Adapter to make TokenIndex implement the Retriever interface.
"""

from typing import Optional

from ..interfaces import RetrievalResult, RetrievalStrategy, Retriever
from .token import TokenIndex


class TokenRetrieverAdapter(Retriever):
    """Adapts TokenIndex to implement Retriever interface."""

    def __init__(self, token_index: TokenIndex, **kwargs):
        self.token_index = token_index
        self.config = kwargs

    async def retrieve(
        self,
        query: str,
        limit: int = 10,
        strategy: Optional[RetrievalStrategy] = None,
        **kwargs,
    ) -> RetrievalResult:
        """Retrieve using token-based search."""
        # For now, return a mock result
        # TODO: Implement actual token-based retrieval
        return RetrievalResult(
            tables=[],
            columns=[],
            context={},
            score=0.0,
            strategy_used=RetrievalStrategy.TOKEN,
            metadata={"adapter": "token"},
        )

    async def initialize(self) -> None:
        """Initialize the token index."""
        # Token index initializes on creation
        pass

    async def close(self) -> None:
        """Clean up resources."""
        # No cleanup needed for token index
        pass
