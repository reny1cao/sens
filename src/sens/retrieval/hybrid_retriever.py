"""
Hybrid retriever that combines token and embedding search.
"""

from typing import Optional

from ..interfaces import RetrievalResult, RetrievalStrategy, Retriever


class HybridRetriever(Retriever):
    """Combines token and embedding retrievers."""

    def __init__(
        self, token_retriever: Retriever, embedding_retriever: Retriever, **kwargs
    ):
        self.token_retriever = token_retriever
        self.embedding_retriever = embedding_retriever
        self.config = kwargs

    async def retrieve(
        self,
        query: str,
        limit: int = 10,
        strategy: Optional[RetrievalStrategy] = None,
        **kwargs,
    ) -> RetrievalResult:
        """Retrieve using both token and embedding search."""
        # For now, return a mock result
        # TODO: Implement actual hybrid retrieval
        return RetrievalResult(
            tables=[],
            columns=[],
            context={},
            score=0.0,
            strategy_used=RetrievalStrategy.HYBRID,
            metadata={"adapter": "hybrid"},
        )

    async def initialize(self) -> None:
        """Initialize both retrievers."""
        await self.token_retriever.initialize()
        await self.embedding_retriever.initialize()

    async def close(self) -> None:
        """Clean up resources."""
        await self.token_retriever.close()
        await self.embedding_retriever.close()
