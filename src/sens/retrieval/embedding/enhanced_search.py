"""Enhanced embedding-based semantic search with keyword fallback."""

import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from sens.caching.factory import get_cache_manager, get_cache_ttl
from sens.settings import get_settings

# Configure structured logging
logger = logging.getLogger(__name__)


class EnhancedEmbeddingSearch:
    """Enhanced semantic search with fallback to keyword search when embeddings fail."""

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        index_dir: Optional[str] = None,
        dimension: int = 384,
    ):
        """Initialize the enhanced embedding search component.

        Args:
            model_name: Name of the sentence-transformer model to use
            index_dir: Directory to store/load the FAISS index and lookup map. If None, uses settings.
            dimension: Embedding dimension (384 for MiniLM-L6)
        """
        self.model_name = model_name
        self._model = None
        if index_dir is None:
            self.index_dir = get_settings().index_dir
        else:
            self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)

        self.dimension = dimension
        self.index = None
        self.lookup: Dict[int, Tuple[str, str]] = {}  # id -> (table, column)
        self._cache_manager = None
        self._faiss_available = self._check_faiss_availability()
        self._model_available = self._check_model_availability()

    def _check_faiss_availability(self) -> bool:
        """Check if FAISS is available."""
        try:
            import faiss
            return True
        except ImportError:
            logger.warning("FAISS not available, will use keyword fallback")
            return False

    def _check_model_availability(self) -> bool:
        """Check if sentence transformers is available."""
        try:
            from sentence_transformers import SentenceTransformer
            return True
        except ImportError:
            logger.warning("SentenceTransformers not available, will use keyword fallback")
            return False

    @property
    def model(self):
        """Lazy load the SentenceTransformer model."""
        if self._model is None and self._model_available:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        return self._model

    @property
    def cache_manager(self):
        """Lazy load the cache manager."""
        if self._cache_manager is None:
            self._cache_manager = get_cache_manager()
        return self._cache_manager

    def _build_column_text(self, table: str, column: str, description: str = "") -> str:
        """Build the text representation for a column.

        Args:
            table: Table name
            column: Column name
            description: Optional column description

        Returns:
            Formatted column text for embedding
        """
        # Humanize names by splitting on underscores/camelCase
        humanized_name = " ".join(
            word.lower() for word in column.replace("_", " ").split()
        )

        if description:
            return f"{table}.{column} – {humanized_name} – {description}"
        return f"{table}.{column} – {humanized_name}"

    def build_index(self, schema_path: str) -> None:
        """Build the embedding index from a schema metadata file.

        Args:
            schema_path: Path to the schema metadata JSON file
        """
        # Load schema metadata
        with open(schema_path) as f:
            schema = json.load(f)

        # Handle both dict and list formats for tables
        tables_data = schema["tables"]
        if isinstance(tables_data, list):
            # Convert list to dict format
            tables_dict = {table["name"]: table for table in tables_data}
        else:
            tables_dict = tables_data

        # Build column texts
        columns = []
        for table_details in tables_dict.values():
            table_name = table_details["name"]
            for col in table_details.get("columns", []):
                col_name = col["name"]
                description = col.get("description", "")
                columns.append(
                    (
                        table_name,
                        col_name,
                        self._build_column_text(table_name, col_name, description),
                    )
                )

        # Save lookup dictionary regardless of embedding availability
        self.lookup = {i: (col[0], col[1]) for i, col in enumerate(columns)}
        np.save(str(self.index_dir / "lookup.npy"), self.lookup)

        if self._faiss_available and self._model_available:
            import faiss

            # Create embeddings
            texts = [col[2] for col in columns]
            embeddings = self.model.encode(
                texts, convert_to_tensor=True, show_progress_bar=True
            )
            embeddings = embeddings.cpu().numpy()

            # Build FAISS index
            self.index = faiss.IndexHNSWFlat(self.dimension, 32, faiss.METRIC_INNER_PRODUCT)
            self.index.hnsw.efConstruction = 200
            self.index.add(embeddings)

            # Save index
            faiss.write_index(self.index, str(self.index_dir / "columns.index"))

            logger.info(
                "Built embedding index",
                extra={
                    "phase": "embed_search",
                    "action": "build_index",
                    "num_columns": len(columns),
                    "model": self.model.get_sentence_embedding_dimension(),
                },
            )
        else:
            logger.info(
                "Built keyword-only index (embeddings unavailable)",
                extra={
                    "phase": "embed_search",
                    "action": "build_keyword_index",
                    "num_columns": len(columns),
                },
            )

    def load_index(self) -> None:
        """Load the pre-built index and lookup from disk."""
        # Load lookup
        lookup_path = self.index_dir / "lookup.npy"
        if lookup_path.exists():
            self.lookup = np.load(str(lookup_path), allow_pickle=True).item()

        if self._faiss_available:
            import faiss
            
            index_path = self.index_dir / "columns.index"
            if index_path.exists():
                self.index = faiss.read_index(str(index_path))
                logger.info(
                    "Loaded embedding index",
                    extra={
                        "phase": "embed_search",
                        "action": "load_index",
                        "num_columns": len(self.lookup),
                    },
                )
            else:
                logger.warning(
                    "No embedding index found, will use keyword search",
                    extra={"phase": "embed_search", "action": "index_not_found"},
                )

    async def search(self, query: str, k: int = 20) -> List[Tuple[str, str, float]]:
        """Search for the most relevant columns given a query.

        Args:
            query: The search query
            k: Number of results to return

        Returns:
            List of (table, column, score) tuples sorted by relevance
        """
        # Try to get from cache first
        cache_key = self.cache_manager.generate_key(
            "embedding_search", query=query, k=k
        )
        cached_results = await self.cache_manager.get(cache_key)

        if cached_results is not None:
            logger.info(
                "Embedding search cache hit",
                extra={
                    "phase": "embed_search",
                    "action": "cache_hit",
                    "query": query,
                    "num_results": len(cached_results),
                },
            )
            return cached_results

        # Try embedding search first if available
        if self._faiss_available and self._model_available and self.index is not None:
            try:
                results = await self._embedding_search(query, k)
                # Cache the results
                ttl = get_cache_ttl("embedding")
                await self.cache_manager.set(cache_key, results, ttl)
                return results
            except Exception as e:
                logger.warning(
                    f"Embedding search failed, falling back to keyword search: {e}",
                    extra={
                        "phase": "embed_search",
                        "action": "fallback",
                        "error": str(e),
                        "query": query,
                    },
                )

        # Fallback to keyword search
        results = await self._keyword_fallback(query, k)
        # Cache the results
        ttl = get_cache_ttl("embedding")
        await self.cache_manager.set(cache_key, results, ttl)
        return results

    async def _embedding_search(self, query: str, k: int) -> List[Tuple[str, str, float]]:
        """Internal embedding search method."""
        # Load index if needed
        if self.index is None:
            self.load_index()
            if self.index is None:
                raise RuntimeError("No embedding index available")

        # Encode query
        query_embedding = self.model.encode(query, convert_to_tensor=True)
        query_embedding = query_embedding.cpu().numpy().reshape(1, -1)

        # Search
        start_time = time.time()
        scores, indices = self.index.search(query_embedding, k)
        duration_ms = (time.time() - start_time) * 1000

        # Format results
        results = [
            (self.lookup[idx][0], self.lookup[idx][1], float(score))
            for score, idx in zip(scores[0], indices[0])
            if idx >= 0 and idx in self.lookup
        ]

        logger.info(
            "Performed embedding search",
            extra={
                "phase": "embed_search",
                "action": "search",
                "query": query,
                "num_results": len(results),
                "duration_ms": duration_ms,
                "top_candidates": [
                    f"{table}.{column}" for table, column, _ in results[:5]
                ],
            },
        )

        return results

    async def _keyword_fallback(self, query: str, k: int = 20) -> List[Tuple[str, str, float]]:
        """Fallback keyword-based search when embedding search fails.
        
        Args:
            query: The search query
            k: Number of results to return
            
        Returns:
            List of (table, column, score) tuples sorted by relevance
        """
        # Load lookup if not loaded
        if not self.lookup:
            lookup_path = self.index_dir / "lookup.npy"
            if lookup_path.exists():
                self.lookup = np.load(str(lookup_path), allow_pickle=True).item()
            else:
                logger.warning(
                    "No lookup data available for keyword fallback",
                    extra={
                        "phase": "embed_search",
                        "action": "keyword_fallback_failed",
                    },
                )
                return []
        
        # Simple keyword matching
        query_tokens = query.lower().split()
        results = []
        
        for idx, (table, column) in self.lookup.items():
            # Create searchable text
            searchable = f"{table} {column}".lower().replace("_", " ")
            
            # Calculate score based on token matches
            score = 0.0
            matched_tokens = 0
            
            for token in query_tokens:
                if token in searchable:
                    score += 1.0
                    matched_tokens += 1
                elif any(token in word for word in searchable.split()):
                    score += 0.5
                    matched_tokens += 0.5
            
            if score > 0:
                # Normalize score to 0-1 range with boost for more matches
                score = (score / len(query_tokens)) * (matched_tokens / len(query_tokens))
                results.append((table, column, score))
        
        # Sort by score descending and limit to k results
        results.sort(key=lambda x: x[2], reverse=True)
        results = results[:k]
        
        logger.info(
            "Performed keyword fallback search",
            extra={
                "phase": "embed_search",
                "action": "keyword_search",
                "query": query,
                "num_results": len(results),
                "top_candidates": [
                    f"{table}.{column}" for table, column, _ in results[:5]
                ],
            },
        )
        
        return results

    def search_sync(self, query: str, k: int = 20) -> List[Tuple[str, str, float]]:
        """Synchronous version of search for backward compatibility."""
        import asyncio

        # Get or create event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Run async method in sync context
        if loop.is_running():
            # If loop is already running, use keyword search directly
            return self._keyword_fallback_sync(query, k)
        else:
            return loop.run_until_complete(self.search(query, k))

    def _keyword_fallback_sync(self, query: str, k: int = 20) -> List[Tuple[str, str, float]]:
        """Synchronous keyword fallback."""
        # Same logic as async version but without await
        if not self.lookup:
            lookup_path = self.index_dir / "lookup.npy"
            if lookup_path.exists():
                self.lookup = np.load(str(lookup_path), allow_pickle=True).item()
            else:
                return []
        
        query_tokens = query.lower().split()
        results = []
        
        for idx, (table, column) in self.lookup.items():
            searchable = f"{table} {column}".lower().replace("_", " ")
            score = 0.0
            matched_tokens = 0
            
            for token in query_tokens:
                if token in searchable:
                    score += 1.0
                    matched_tokens += 1
                elif any(token in word for word in searchable.split()):
                    score += 0.5
                    matched_tokens += 0.5
            
            if score > 0:
                score = (score / len(query_tokens)) * (matched_tokens / len(query_tokens))
                results.append((table, column, score))
        
        results.sort(key=lambda x: x[2], reverse=True)
        return results[:k]