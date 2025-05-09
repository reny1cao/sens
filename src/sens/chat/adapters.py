"""Adapters for chat pipeline components."""

import asyncio
from typing import List

from sens.retrieval.embedding.search import EmbeddingSearch
from sens.retrieval.models import RetrievedColumn
from sens.retrieval.token import TokenIndexBuilder
from sens.schema.graph import SchemaGraph


class ChatTokenIndexAdapter:
    """Adapter for TokenIndexBuilder to provide async search for ChatOrchestrator."""

    def __init__(self):
        """Initialize the ChatTokenIndexAdapter."""
        self.builder = TokenIndexBuilder()
        self.schema_graph = SchemaGraph.get_instance()
        self._initialized = False

    async def _initialize(self):
        if not self._initialized:
            table_names = await asyncio.to_thread(self.schema_graph.list_all_tables)
            await asyncio.to_thread(self.builder.build_index, table_names)
            self._initialized = True

    async def search(self, query: str, k: int = 5) -> List[RetrievedColumn]:
        if not self._initialized:
            await self._initialize()
        matched_table_names = await asyncio.to_thread(self.builder.guess_tables, query)
        results = []
        for i, table_name in enumerate(matched_table_names[:k]):
            results.append(
                RetrievedColumn(
                    table_name=table_name,
                    column_name="*",
                    score=1.0 - (i / (k + 1e-9)),
                    source="token",
                )
            )
        return results


class ChatEmbeddingAdapter:
    """Adapter for EmbeddingSearch to provide async search for ChatOrchestrator."""

    def __init__(self):
        """Initialize the ChatEmbeddingAdapter."""
        self.embedding_search = EmbeddingSearch()
        self._initialized = False

    async def _initialize(self):
        if not self._initialized:
            # Load the embedding index (synchronous, so run in thread)
            await asyncio.to_thread(self.embedding_search.load_index)
            self._initialized = True

    async def search(self, query: str, k: int = 5) -> List[RetrievedColumn]:
        if not self._initialized:
            await self._initialize()
        # Run the synchronous search in a thread
        results = await asyncio.to_thread(self.embedding_search.search, query, k)
        # Convert List[Tuple[str, str, float]] to List[RetrievedColumn]
        return [
            RetrievedColumn(table_name=t, column_name=c, score=s, source="embedding")
            for t, c, s in results
        ]
