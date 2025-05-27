"""Enhanced performance metrics tracking with recall rate measurement.

This module provides comprehensive performance metrics including:
- Component latency tracking
- Cache hit rates
- Retrieval recall rates
- Query complexity metrics
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Dict, List, Optional, Set, Tuple

import structlog

log = structlog.get_logger()


@dataclass
class RetrievalMetrics:
    """Metrics for retrieval performance and recall rate."""

    query: str
    retrieved_tables: Set[str] = field(default_factory=set)
    retrieved_columns: Set[Tuple[str, str]] = field(
        default_factory=set
    )  # (table, column)
    relevant_tables: Set[str] = field(default_factory=set)
    relevant_columns: Set[Tuple[str, str]] = field(default_factory=set)

    # Performance metrics
    token_search_ms: Optional[float] = None
    embedding_search_ms: Optional[float] = None
    expansion_ms: Optional[float] = None
    total_retrieval_ms: Optional[float] = None

    # Cache metrics
    token_cache_hit: bool = False
    embedding_cache_hit: bool = False
    schema_cache_hit: bool = False

    def calculate_recall(self) -> Dict[str, float]:
        """Calculate recall rates for tables and columns."""
        table_recall = 0.0
        column_recall = 0.0

        if self.relevant_tables:
            table_recall = len(self.retrieved_tables & self.relevant_tables) / len(
                self.relevant_tables
            )

        if self.relevant_columns:
            column_recall = len(self.retrieved_columns & self.relevant_columns) / len(
                self.relevant_columns
            )

        return {
            "table_recall": table_recall,
            "column_recall": column_recall,
            "tables_retrieved": len(self.retrieved_tables),
            "tables_relevant": len(self.relevant_tables),
            "columns_retrieved": len(self.retrieved_columns),
            "columns_relevant": len(self.relevant_columns),
        }


@dataclass
class CacheMetrics:
    """Metrics for cache performance."""

    hits: int = 0
    misses: int = 0
    total_requests: int = 0

    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        if self.total_requests == 0:
            return 0.0
        return self.hits / self.total_requests

    def record_hit(self):
        """Record a cache hit."""
        self.hits += 1
        self.total_requests += 1

    def record_miss(self):
        """Record a cache miss."""
        self.misses += 1
        self.total_requests += 1


@dataclass
class QueryComplexityMetrics:
    """Metrics for query complexity analysis."""

    query_length: int
    token_count: int
    table_count: int
    join_count: int
    filter_count: int
    aggregation_count: int

    def complexity_score(self) -> float:
        """Calculate overall query complexity score."""
        # Simple weighted complexity score
        return (
            self.table_count * 1.0
            + self.join_count * 2.0
            + self.filter_count * 0.5
            + self.aggregation_count * 1.5
        )


class PerformanceTracker:
    """Centralized performance tracking system."""

    def __init__(self):
        """Initialize the performance tracker."""
        # Component latency tracking
        self.component_latencies: Dict[str, List[float]] = defaultdict(list)

        # Cache metrics by type
        self.cache_metrics: Dict[str, CacheMetrics] = {
            "embedding": CacheMetrics(),
            "token": CacheMetrics(),
            "llm": CacheMetrics(),
            "schema": CacheMetrics(),
        }

        # Retrieval metrics history
        self.retrieval_metrics: List[RetrievalMetrics] = []

        # Query complexity metrics
        self.complexity_metrics: List[QueryComplexityMetrics] = []

        # Time window for metrics (last N minutes)
        self.time_window_minutes = 60
        self.metrics_start_time = datetime.now(UTC)

    def track_component_latency(self, component: str, latency_ms: float):
        """Track latency for a specific component."""
        self.component_latencies[component].append(latency_ms)

        # Keep only recent metrics
        self._cleanup_old_metrics()

    def track_cache_hit(self, cache_type: str):
        """Track a cache hit."""
        if cache_type in self.cache_metrics:
            self.cache_metrics[cache_type].record_hit()
            log.debug(
                "cache_hit_recorded",
                cache_type=cache_type,
                hit_rate=self.cache_metrics[cache_type].hit_rate(),
            )

    def track_cache_miss(self, cache_type: str):
        """Track a cache miss."""
        if cache_type in self.cache_metrics:
            self.cache_metrics[cache_type].record_miss()
            log.debug(
                "cache_miss_recorded",
                cache_type=cache_type,
                hit_rate=self.cache_metrics[cache_type].hit_rate(),
            )

    def track_retrieval(self, metrics: RetrievalMetrics):
        """Track retrieval performance and recall."""
        self.retrieval_metrics.append(metrics)
        recall_stats = metrics.calculate_recall()

        log.info(
            "retrieval_metrics_tracked",
            query=metrics.query[:50],
            table_recall=recall_stats["table_recall"],
            column_recall=recall_stats["column_recall"],
            total_ms=metrics.total_retrieval_ms,
            cache_hits={
                "token": metrics.token_cache_hit,
                "embedding": metrics.embedding_cache_hit,
                "schema": metrics.schema_cache_hit,
            },
        )

    def track_query_complexity(self, metrics: QueryComplexityMetrics):
        """Track query complexity metrics."""
        self.complexity_metrics.append(metrics)
        log.debug(
            "query_complexity_tracked",
            complexity_score=metrics.complexity_score(),
            table_count=metrics.table_count,
            join_count=metrics.join_count,
        )

    def get_performance_summary(self) -> Dict:
        """Get comprehensive performance summary."""
        # Calculate percentiles for latencies
        latency_percentiles = {}
        for component, latencies in self.component_latencies.items():
            if latencies:
                sorted_latencies = sorted(latencies)
                n = len(sorted_latencies)
                latency_percentiles[component] = {
                    "p50": sorted_latencies[n // 2],
                    "p95": sorted_latencies[int(n * 0.95)],
                    "p99": sorted_latencies[int(n * 0.99)],
                    "avg": sum(latencies) / n,
                    "count": n,
                }

        # Calculate cache hit rates
        cache_hit_rates = {
            cache_type: metrics.hit_rate()
            for cache_type, metrics in self.cache_metrics.items()
        }

        # Calculate average recall rates
        recall_rates = self._calculate_average_recall()

        # Calculate complexity trends
        complexity_stats = self._calculate_complexity_stats()

        return {
            "latency_percentiles": latency_percentiles,
            "cache_hit_rates": cache_hit_rates,
            "recall_rates": recall_rates,
            "complexity_stats": complexity_stats,
            "time_window": {
                "start": self.metrics_start_time.isoformat(),
                "end": datetime.now(UTC).isoformat(),
                "duration_minutes": self.time_window_minutes,
            },
        }

    def _calculate_average_recall(self) -> Dict[str, float]:
        """Calculate average recall rates."""
        if not self.retrieval_metrics:
            return {"table_recall": 0.0, "column_recall": 0.0}

        table_recalls = []
        column_recalls = []

        for metrics in self.retrieval_metrics:
            recall = metrics.calculate_recall()
            if recall["tables_relevant"] > 0:
                table_recalls.append(recall["table_recall"])
            if recall["columns_relevant"] > 0:
                column_recalls.append(recall["column_recall"])

        return {
            "table_recall": (
                sum(table_recalls) / len(table_recalls) if table_recalls else 0.0
            ),
            "column_recall": (
                sum(column_recalls) / len(column_recalls) if column_recalls else 0.0
            ),
            "sample_count": len(self.retrieval_metrics),
        }

    def _calculate_complexity_stats(self) -> Dict:
        """Calculate query complexity statistics."""
        if not self.complexity_metrics:
            return {}

        scores = [m.complexity_score() for m in self.complexity_metrics]
        return {
            "avg_complexity": sum(scores) / len(scores),
            "max_complexity": max(scores),
            "min_complexity": min(scores),
            "query_count": len(scores),
        }

    def _cleanup_old_metrics(self):
        """Remove metrics older than the time window."""
        # This is a simplified version - in production you'd want
        # to timestamp each metric and remove old ones
        for component, latencies in self.component_latencies.items():
            if len(latencies) > 1000:  # Keep last 1000 measurements
                self.component_latencies[component] = latencies[-1000:]

        if len(self.retrieval_metrics) > 1000:
            self.retrieval_metrics = self.retrieval_metrics[-1000:]

        if len(self.complexity_metrics) > 1000:
            self.complexity_metrics = self.complexity_metrics[-1000:]


# Global performance tracker instance
_performance_tracker: Optional[PerformanceTracker] = None


def get_performance_tracker() -> PerformanceTracker:
    """Get the global performance tracker instance."""
    global _performance_tracker
    if _performance_tracker is None:
        _performance_tracker = PerformanceTracker()
    return _performance_tracker


def reset_performance_tracker():
    """Reset the performance tracker (mainly for testing)."""
    global _performance_tracker
    _performance_tracker = PerformanceTracker()
