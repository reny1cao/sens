"""LLM response caching with semantic similarity."""

import hashlib
import json
from datetime import timedelta
from typing import Any, Dict, Optional, Tuple

import numpy as np
import structlog

from ..llm.models import GeneratedSQL, TokenUsage
from .factory import get_cache_manager, get_cache_ttl
from .manager import CacheManager

log = structlog.get_logger()


class LLMResponseCache:
    """Cache for LLM responses with semantic similarity matching."""

    def __init__(self, cache_manager: Optional[CacheManager] = None):
        """Initialize LLM response cache.

        Args:
            cache_manager: Optional cache manager instance
        """
        self.cache_manager = cache_manager or get_cache_manager()
        self._embedding_model = None

    @property
    def embedding_model(self):
        """Lazy load the embedding model for semantic similarity."""
        if self._embedding_model is None:
            from sentence_transformers import SentenceTransformer

            self._embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        return self._embedding_model

    def _compute_cache_key(
        self,
        intent_hash: str,
        schema_hash: str,
        model: str,
    ) -> str:
        """Compute cache key for LLM response.

        Args:
            intent_hash: Hash of the intent
            schema_hash: Hash of the schema context
            model: Model name

        Returns:
            Cache key string
        """
        # Combine all components into a single hash
        combined = f"{intent_hash}:{schema_hash}:{model}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    def _hash_intent(self, intent: Dict[str, Any]) -> str:
        """Create a stable hash of the intent.

        Args:
            intent: Intent dictionary

        Returns:
            Hash string
        """
        # Extract key intent components
        intent_key = {
            "query_type": intent.get("query_type"),
            "tables": sorted(intent.get("tables", [])),
            "columns": sorted(intent.get("columns", [])),
            "filters": intent.get("filters", []),
            "aggregations": intent.get("aggregations", []),
            "group_by": intent.get("group_by", []),
            "order_by": intent.get("order_by", []),
            "limit": intent.get("limit"),
        }

        # Create stable JSON representation
        intent_json = json.dumps(intent_key, sort_keys=True)
        return hashlib.sha256(intent_json.encode()).hexdigest()[:16]

    def _hash_schema(self, schema_context: Dict[str, Any]) -> str:
        """Create a stable hash of the schema context.

        Args:
            schema_context: Schema context dictionary

        Returns:
            Hash string
        """
        # Extract table and column names
        schema_key = {
            "tables": sorted(schema_context.get("tables_columns", {}).keys()),
            "columns": {
                table: sorted(cols)
                for table, cols in schema_context.get("tables_columns", {}).items()
            },
        }

        # Create stable JSON representation
        schema_json = json.dumps(schema_key, sort_keys=True)
        return hashlib.sha256(schema_json.encode()).hexdigest()[:16]

    async def get_cached_sql(
        self,
        question: str,
        intent: Dict[str, Any],
        schema_context: Dict[str, Any],
        model: str,
        similarity_threshold: float = 0.95,
    ) -> Optional[GeneratedSQL]:
        """Get cached SQL for similar query.

        Args:
            question: Original question
            intent: Extracted intent
            schema_context: Schema context
            model: Model name
            similarity_threshold: Minimum similarity score

        Returns:
            Cached GeneratedSQL if found, None otherwise
        """
        # Compute hashes
        intent_hash = self._hash_intent(intent)
        schema_hash = self._hash_schema(schema_context)

        # Try exact match first
        cache_key = self.cache_manager.generate_key(
            "llm_sql",
            intent_hash=intent_hash,
            schema_hash=schema_hash,
            model=model,
        )

        cached_result = await self.cache_manager.get(cache_key)
        if cached_result:
            log.info(
                "llm_cache_exact_hit",
                intent_hash=intent_hash,
                schema_hash=schema_hash,
                model=model,
            )

            # Reconstruct GeneratedSQL from cached data
            return GeneratedSQL(
                sql=cached_result["sql"],
                tables_used=cached_result["tables_used"],
                columns_used=cached_result["columns_used"],
                model_used=cached_result["model_used"],
                generation_ms=0,  # Cached, so no generation time
                token_usage=TokenUsage(
                    prompt_tokens=0,
                    completion_tokens=0,
                ),
                cached=True,
            )

        # TODO: Implement semantic similarity search for near matches
        # This would involve:
        # 1. Encoding the current question
        # 2. Searching for similar questions in cache
        # 3. Returning if similarity > threshold

        return None

    async def cache_sql(
        self,
        question: str,
        intent: Dict[str, Any],
        schema_context: Dict[str, Any],
        model: str,
        generated_sql: GeneratedSQL,
    ) -> None:
        """Cache generated SQL.

        Args:
            question: Original question
            intent: Extracted intent
            schema_context: Schema context
            model: Model name
            generated_sql: Generated SQL result
        """
        # Compute hashes
        intent_hash = self._hash_intent(intent)
        schema_hash = self._hash_schema(schema_context)

        # Create cache entry
        cache_entry = {
            "sql": generated_sql.sql,
            "tables_used": generated_sql.tables_used,
            "columns_used": generated_sql.columns_used,
            "model_used": generated_sql.model_used,
            "question": question,
            "intent": intent,
            "timestamp": json.dumps(
                generated_sql.timestamp.isoformat() if generated_sql.timestamp else None
            ),
        }

        # Store with appropriate TTL
        cache_key = self.cache_manager.generate_key(
            "llm_sql",
            intent_hash=intent_hash,
            schema_hash=schema_hash,
            model=model,
        )

        ttl = get_cache_ttl("llm")
        await self.cache_manager.set(cache_key, cache_entry, ttl)

        log.info(
            "llm_response_cached",
            intent_hash=intent_hash,
            schema_hash=schema_hash,
            model=model,
            ttl_hours=ttl.total_seconds() / 3600,
        )
