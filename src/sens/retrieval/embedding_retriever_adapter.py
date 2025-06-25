"""
Adapter to make EmbeddingSearch implement the Retriever interface.
"""

from typing import Optional

from ..interfaces import RetrievalResult, RetrievalStrategy, Retriever


class EmbeddingRetrieverAdapter(Retriever):
    """Adapts EmbeddingSearch to implement Retriever interface."""

    def __init__(self, embedding_search, **kwargs):
        self.embedding_search = embedding_search
        self.config = kwargs

    async def retrieve(
        self,
        query: str,
        limit: int = 10,
        strategy: Optional[RetrievalStrategy] = None,
        **kwargs,
    ) -> RetrievalResult:
        """Retrieve using embedding-based search."""
        # For now, return a mock result
        # TODO: Implement actual embedding-based retrieval
        return RetrievalResult(
            tables=[],
            columns=[],
            context={},
            score=0.0,
            strategy_used=RetrievalStrategy.EMBEDDING,
            metadata={"adapter": "embedding"},
        )

    async def initialize(self) -> None:
        """Initialize the embedding search."""
        # Load index if needed
        try:
            self.embedding_search.load_index()
        except Exception:
            pass  # Index might not exist yet

    async def close(self) -> None:
        """Clean up resources."""
        # No cleanup needed
        pass
