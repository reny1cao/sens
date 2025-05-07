"""Embedding-based semantic search for database schema components."""

import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Defer FAISS and SentenceTransformer imports
import numpy as np

from sens.settings import get_settings

# Configure structured logging
logger = logging.getLogger(__name__)


class EmbeddingSearch:
    """Manages semantic search over database schema components using SBERT embeddings."""

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        index_dir: Optional[str] = None,
        dimension: int = 384,
    ):
        """Initialize the embedding search component.

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

    @property
    def model(self):
        """Lazy load the SentenceTransformer model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

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
        import faiss  # Import only when needed

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

        # Create embeddings
        texts = [col[2] for col in columns]
        embeddings = self.model.encode(
            texts, convert_to_tensor=True, show_progress_bar=True
        )
        embeddings = embeddings.cpu().numpy()

        # Build FAISS index using Inner Product (Cosine Similarity for normalized vectors)
        # Note: Higher scores will now indicate greater similarity.
        self.index = faiss.IndexHNSWFlat(self.dimension, 32, faiss.METRIC_INNER_PRODUCT)
        self.index.hnsw.efConstruction = 200  # More thorough index construction
        self.index.add(embeddings)

        # Build lookup dictionary
        self.lookup = {i: (col[0], col[1]) for i, col in enumerate(columns)}

        # Save index and lookup
        faiss.write_index(self.index, str(self.index_dir / "columns.index"))
        np.save(str(self.index_dir / "lookup.npy"), self.lookup)

        logger.info(
            "Built embedding index",
            extra={
                "phase": "embed_search",
                "action": "build_index",
                "num_columns": len(columns),
                "model": self.model.get_sentence_embedding_dimension(),
            },
        )

    def load_index(self) -> None:
        """Load the pre-built index and lookup map from disk."""
        import faiss  # Import only when needed

        index_path = self.index_dir / "columns.index"
        lookup_path = self.index_dir / "lookup.npy"

        if not (index_path.exists() and lookup_path.exists()):
            raise FileNotFoundError(
                f"Index files not found in {self.index_dir}. Run build_index() first."
            )

        self.index = faiss.read_index(str(index_path))
        self.lookup = np.load(str(lookup_path), allow_pickle=True).item()

        logger.info(
            "Loaded embedding index",
            extra={
                "phase": "embed_search",
                "action": "load_index",
                "num_columns": len(self.lookup),
            },
        )

    def search(self, query: str, k: int = 20) -> List[Tuple[str, str, float]]:
        """Search for the most relevant columns given a query.

        Args:
            query: The search query
            k: Number of results to return

        Returns:
            List of (table, column, score) tuples sorted by relevance
        """
        if self.index is None:
            self.load_index()

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
            if idx >= 0  # Filter out invalid indices
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


# Global instance for the top_columns API
_embedding_search: Optional[EmbeddingSearch] = None


def get_embedding_search() -> EmbeddingSearch:
    """Get or create the global EmbeddingSearch instance.

    This function is used internally by the top_columns API and should not be
    called directly unless you need explicit control over the instance lifecycle.

    Returns:
        The global EmbeddingSearch instance
    """
    global _embedding_search
    if _embedding_search is None:
        _embedding_search = EmbeddingSearch()
    return _embedding_search


def top_columns(query: str, k: int = 20) -> List[Tuple[str, str, float]]:
    """Get the top-K most relevant columns for a query.

    This is the main API function that automatically handles index loading.

    Args:
        query: The search query
        k: Number of results to return

    Returns:
        List of (table, column, score) tuples sorted by relevance
    """
    search = get_embedding_search()
    return search.search(query, k)
