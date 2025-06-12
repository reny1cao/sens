"""Agent memory system for learning from past queries."""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import structlog
from redis import Redis

from sens.caching.factory import get_cache_manager
from sens.settings import get_settings

log = structlog.get_logger()


class AgentMemory:
    """Manages agent's memory of past queries, mappings, and patterns."""

    def __init__(self, ttl_days: int = 30):
        """Initialize agent memory.

        Args:
            ttl_days: How long to keep memories (default 30 days)
        """
        self.ttl = timedelta(days=ttl_days)
        self.cache_manager = get_cache_manager()

        # In-memory caches for fast access
        self._value_mappings: Dict[str, Dict[str, str]] = {}
        self._successful_patterns: List[Dict[str, Any]] = []
        self._failed_queries: List[Dict[str, Any]] = []

        # Load from persistent storage
        self._load_memories()

        log.info("agent_memory_initialized", ttl_days=ttl_days)

    async def store_mapping(
        self,
        user_term: str,
        db_value: str,
        context: str,
        confidence: float = 1.0,
    ) -> None:
        """Store a successful value mapping.

        Args:
            user_term: What the user said (e.g., "Apple")
            db_value: Database value (e.g., "AAPL")
            context: Context where this mapping was learned
            confidence: Confidence in this mapping
        """
        key = f"agent:mapping:{user_term.lower()}"

        mapping = {
            "user_term": user_term,
            "db_value": db_value,
            "context": context,
            "confidence": confidence,
            "learned_at": datetime.utcnow().isoformat(),
            "usage_count": 1,
        }

        # Check if mapping exists
        existing = await self.cache_manager.get(key)
        if existing:
            # Update usage count
            mapping["usage_count"] = existing.get("usage_count", 0) + 1
            # Update confidence based on repeated success
            mapping["confidence"] = min(1.0, existing["confidence"] + 0.1)

        # Store in cache
        await self.cache_manager.set(key, mapping, self.ttl)

        # Update in-memory cache
        if context not in self._value_mappings:
            self._value_mappings[context] = {}
        self._value_mappings[context][user_term.lower()] = db_value

        log.info(
            "stored_value_mapping",
            user_term=user_term,
            db_value=db_value,
            context=context,
        )

    async def recall_mapping(
        self,
        user_term: str,
        context: str,
    ) -> Optional[str]:
        """Recall a previously learned mapping.

        Args:
            user_term: What the user said
            context: Current context

        Returns:
            Database value if found, None otherwise
        """
        # Check in-memory cache first
        context_mappings = self._value_mappings.get(context, {})
        if user_term.lower() in context_mappings:
            return context_mappings[user_term.lower()]

        # Check persistent cache
        key = f"agent:mapping:{user_term.lower()}"
        mapping = await self.cache_manager.get(key)

        if mapping and mapping["confidence"] >= 0.7:
            log.info(
                "recalled_mapping",
                user_term=user_term,
                db_value=mapping["db_value"],
                confidence=mapping["confidence"],
            )
            return mapping["db_value"]

        return None

    async def store_successful_query(
        self,
        user_query: str,
        sql: str,
        mappings: Dict[str, str],
        row_count: Optional[int] = None,
    ) -> None:
        """Store a successful query pattern.

        Args:
            user_query: Original user query
            sql: Generated SQL that worked
            mappings: Value mappings used
            row_count: Number of rows returned
        """
        pattern = {
            "user_query": user_query,
            "sql": sql,
            "mappings": mappings,
            "row_count": row_count,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Store in cache
        key = f"agent:pattern:{hash(user_query)}"
        await self.cache_manager.set(key, pattern, self.ttl)

        # Update in-memory list
        self._successful_patterns.append(pattern)

        # Keep only recent patterns in memory
        if len(self._successful_patterns) > 100:
            self._successful_patterns = self._successful_patterns[-100:]

        log.info(
            "stored_successful_pattern",
            query_length=len(user_query),
            mappings_count=len(mappings),
        )

    async def recall_similar_query(
        self,
        user_query: str,
        schema: Dict[str, Any],
    ) -> Optional[str]:
        """Find similar successful queries.

        Args:
            user_query: Current user query
            schema: Current schema context

        Returns:
            SQL from similar successful query if found
        """
        # Simple similarity check - in production use embeddings
        query_words = set(user_query.lower().split())

        best_match = None
        best_score = 0.0

        for pattern in self._successful_patterns:
            pattern_words = set(pattern["user_query"].lower().split())

            # Calculate Jaccard similarity
            intersection = len(query_words & pattern_words)
            union = len(query_words | pattern_words)

            if union > 0:
                score = intersection / union

                if score > best_score and score > 0.6:
                    best_score = score
                    best_match = pattern

        if best_match:
            log.info(
                "found_similar_query",
                similarity=best_score,
                original_query=best_match["user_query"][:50],
            )
            return best_match["sql"]

        return None

    async def store_failed_query(
        self,
        user_query: str,
        error: str,
        attempted_sql: Optional[str] = None,
    ) -> None:
        """Store information about failed queries for learning.

        Args:
            user_query: Query that failed
            error: Error message
            attempted_sql: SQL that was attempted
        """
        failure = {
            "user_query": user_query,
            "error": error,
            "attempted_sql": attempted_sql,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Store in cache
        key = f"agent:failure:{hash(user_query)}"
        await self.cache_manager.set(key, failure, timedelta(days=7))

        # Update in-memory list
        self._failed_queries.append(failure)

        # Keep only recent failures
        if len(self._failed_queries) > 50:
            self._failed_queries = self._failed_queries[-50:]

        log.info("stored_failed_query", error_type=error[:50])

    async def get_known_mappings(self, context: str) -> Dict[str, str]:
        """Get all known mappings for a context.

        Args:
            context: Context to get mappings for

        Returns:
            Dict of user_term -> db_value mappings
        """
        return self._value_mappings.get(context, {})

    async def get_statistics(self) -> Dict[str, Any]:
        """Get memory statistics.

        Returns:
            Statistics about stored memories
        """
        return {
            "value_mappings": sum(len(m) for m in self._value_mappings.values()),
            "successful_patterns": len(self._successful_patterns),
            "failed_queries": len(self._failed_queries),
            "contexts": list(self._value_mappings.keys()),
        }

    def _load_memories(self) -> None:
        """Load memories from persistent storage on startup."""
        # This would load from Redis/database on startup
        # For now, start with empty memory
        log.info("memories_loaded", count=0)
