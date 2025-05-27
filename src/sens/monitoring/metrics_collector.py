"""Metrics collection integration for SENS components.

This module provides decorators and utilities to automatically collect
performance metrics from various components.
"""

import asyncio
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional, Set, Tuple

import structlog

from sens.monitoring.performance_metrics import (
    QueryComplexityMetrics,
    RetrievalMetrics,
    get_performance_tracker,
)

log = structlog.get_logger()


def track_latency(component_name: str):
    """Decorator to track component latency.

    Args:
        component_name: Name of the component being tracked
    """

    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.perf_counter()
                try:
                    result = await func(*args, **kwargs)
                    return result
                finally:
                    latency_ms = (time.perf_counter() - start_time) * 1000
                    tracker = get_performance_tracker()
                    tracker.track_component_latency(component_name, latency_ms)
                    log.debug(
                        "component_latency_tracked",
                        component=component_name,
                        latency_ms=latency_ms,
                    )

            return async_wrapper
        else:

            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.perf_counter()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    latency_ms = (time.perf_counter() - start_time) * 1000
                    tracker = get_performance_tracker()
                    tracker.track_component_latency(component_name, latency_ms)
                    log.debug(
                        "component_latency_tracked",
                        component=component_name,
                        latency_ms=latency_ms,
                    )

            return sync_wrapper

    return decorator


class RetrievalMetricsCollector:
    """Collects retrieval metrics including recall rate."""

    def __init__(self):
        """Initialize the retrieval metrics collector."""
        self.current_metrics: Optional[RetrievalMetrics] = None
        self.tracker = get_performance_tracker()

    def start_retrieval(self, query: str) -> RetrievalMetrics:
        """Start tracking a new retrieval."""
        self.current_metrics = RetrievalMetrics(query=query)
        return self.current_metrics

    def record_search_latency(
        self, search_type: str, latency_ms: float, cache_hit: bool = False
    ):
        """Record search latency and cache status."""
        if not self.current_metrics:
            return

        if search_type == "token":
            self.current_metrics.token_search_ms = latency_ms
            self.current_metrics.token_cache_hit = cache_hit
            if cache_hit:
                self.tracker.track_cache_hit("token")
            else:
                self.tracker.track_cache_miss("token")
        elif search_type == "embedding":
            self.current_metrics.embedding_search_ms = latency_ms
            self.current_metrics.embedding_cache_hit = cache_hit
            if cache_hit:
                self.tracker.track_cache_hit("embedding")
            else:
                self.tracker.track_cache_miss("embedding")

    def record_retrieved_schema(self, tables: Set[str], columns: Set[Tuple[str, str]]):
        """Record what was retrieved."""
        if not self.current_metrics:
            return

        self.current_metrics.retrieved_tables = tables
        self.current_metrics.retrieved_columns = columns

    def record_relevant_schema(self, tables: Set[str], columns: Set[Tuple[str, str]]):
        """Record what was actually relevant (ground truth).

        This is typically determined after SQL generation/validation.
        """
        if not self.current_metrics:
            return

        self.current_metrics.relevant_tables = tables
        self.current_metrics.relevant_columns = columns

    def complete_retrieval(self, total_ms: float):
        """Complete retrieval tracking and submit metrics."""
        if not self.current_metrics:
            return

        self.current_metrics.total_retrieval_ms = total_ms
        self.tracker.track_retrieval(self.current_metrics)
        self.current_metrics = None


class QueryComplexityAnalyzer:
    """Analyzes query complexity for metrics."""

    @staticmethod
    def analyze_natural_language(query: str) -> Dict[str, int]:
        """Analyze complexity of natural language query."""
        # Simple heuristics for now
        words = query.lower().split()

        # Count potential complexity indicators
        join_indicators = ["join", "with", "and", "combine", "merge"]
        filter_indicators = ["where", "filter", "only", "exclude", "between"]
        aggregation_indicators = ["sum", "count", "average", "max", "min", "group"]

        join_count = sum(1 for word in words if word in join_indicators)
        filter_count = sum(1 for word in words if word in filter_indicators)
        aggregation_count = sum(1 for word in words if word in aggregation_indicators)

        return {
            "token_count": len(words),
            "join_count": join_count,
            "filter_count": filter_count,
            "aggregation_count": aggregation_count,
        }

    @staticmethod
    def analyze_sql(sql: str) -> QueryComplexityMetrics:
        """Analyze complexity of generated SQL."""
        sql_upper = sql.upper()

        # Count SQL elements
        table_count = sql_upper.count("FROM") + sql_upper.count("JOIN")
        join_count = sql_upper.count("JOIN")
        filter_count = (
            sql_upper.count("WHERE") + sql_upper.count("AND") + sql_upper.count("OR")
        )
        aggregation_count = (
            sql_upper.count("GROUP BY")
            + sql_upper.count("SUM(")
            + sql_upper.count("COUNT(")
            + sql_upper.count("AVG(")
            + sql_upper.count("MAX(")
            + sql_upper.count("MIN(")
        )

        return QueryComplexityMetrics(
            query_length=len(sql),
            token_count=len(sql.split()),
            table_count=table_count,
            join_count=join_count,
            filter_count=filter_count,
            aggregation_count=aggregation_count,
        )


def track_cache_operation(cache_type: str, hit: bool):
    """Track a cache operation."""
    tracker = get_performance_tracker()
    if hit:
        tracker.track_cache_hit(cache_type)
    else:
        tracker.track_cache_miss(cache_type)
