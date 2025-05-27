"""Tests for performance metrics tracking."""

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from sens.monitoring.metrics_collector import (
    QueryComplexityAnalyzer,
    RetrievalMetricsCollector,
    track_latency,
)
from sens.monitoring.performance_metrics import (
    CacheMetrics,
    PerformanceTracker,
    QueryComplexityMetrics,
    RetrievalMetrics,
    get_performance_tracker,
    reset_performance_tracker,
)


class TestRetrievalMetrics:
    """Test retrieval metrics and recall calculation."""

    def test_recall_calculation_perfect(self):
        """Test recall calculation with perfect recall."""
        metrics = RetrievalMetrics(
            query="test query",
            retrieved_tables={"users", "posts", "comments"},
            retrieved_columns={("users", "id"), ("users", "name"), ("posts", "title")},
            relevant_tables={"users", "posts"},
            relevant_columns={("users", "id"), ("posts", "title")},
        )

        recall = metrics.calculate_recall()
        assert recall["table_recall"] == 1.0  # All relevant tables retrieved
        assert recall["column_recall"] == 1.0  # All relevant columns retrieved

    def test_recall_calculation_partial(self):
        """Test recall calculation with partial recall."""
        metrics = RetrievalMetrics(
            query="test query",
            retrieved_tables={"users", "posts"},
            retrieved_columns={("users", "id"), ("posts", "title")},
            relevant_tables={"users", "posts", "comments"},
            relevant_columns={
                ("users", "id"),
                ("users", "name"),
                ("posts", "title"),
                ("comments", "text"),
            },
        )

        recall = metrics.calculate_recall()
        assert recall["table_recall"] == 2 / 3  # 2 out of 3 relevant tables
        assert recall["column_recall"] == 0.5  # 2 out of 4 relevant columns

    def test_recall_calculation_empty(self):
        """Test recall calculation with no relevant items."""
        metrics = RetrievalMetrics(
            query="test query",
            retrieved_tables={"users"},
            retrieved_columns={("users", "id")},
            relevant_tables=set(),
            relevant_columns=set(),
        )

        recall = metrics.calculate_recall()
        assert recall["table_recall"] == 0.0
        assert recall["column_recall"] == 0.0


class TestCacheMetrics:
    """Test cache metrics tracking."""

    def test_cache_hit_rate(self):
        """Test cache hit rate calculation."""
        cache = CacheMetrics()

        # Initial state
        assert cache.hit_rate() == 0.0

        # Record some hits and misses
        cache.record_hit()
        cache.record_hit()
        cache.record_miss()

        assert cache.hits == 2
        assert cache.misses == 1
        assert cache.total_requests == 3
        assert cache.hit_rate() == 2 / 3


class TestPerformanceTracker:
    """Test performance tracker functionality."""

    def setup_method(self):
        """Reset tracker before each test."""
        reset_performance_tracker()
        self.tracker = get_performance_tracker()

    def test_component_latency_tracking(self):
        """Test tracking component latencies."""
        self.tracker.track_component_latency("sql_generation", 150.5)
        self.tracker.track_component_latency("sql_generation", 200.3)
        self.tracker.track_component_latency("validation", 50.2)

        summary = self.tracker.get_performance_summary()

        assert "sql_generation" in summary["latency_percentiles"]
        assert "validation" in summary["latency_percentiles"]

        sql_stats = summary["latency_percentiles"]["sql_generation"]
        assert sql_stats["count"] == 2
        assert sql_stats["avg"] == pytest.approx(175.4, rel=0.01)

    def test_cache_tracking(self):
        """Test cache hit/miss tracking."""
        self.tracker.track_cache_hit("embedding")
        self.tracker.track_cache_hit("embedding")
        self.tracker.track_cache_miss("embedding")

        self.tracker.track_cache_hit("llm")

        summary = self.tracker.get_performance_summary()
        cache_rates = summary["cache_hit_rates"]

        assert cache_rates["embedding"] == pytest.approx(2 / 3)
        assert cache_rates["llm"] == 1.0
        assert cache_rates["token"] == 0.0  # No requests

    def test_retrieval_tracking(self):
        """Test retrieval metrics tracking."""
        metrics1 = RetrievalMetrics(
            query="query1",
            retrieved_tables={"users", "posts"},
            relevant_tables={"users"},
            retrieved_columns={("users", "id"), ("posts", "title")},
            relevant_columns={("users", "id")},
            total_retrieval_ms=100.5,
        )

        metrics2 = RetrievalMetrics(
            query="query2",
            retrieved_tables={"orders"},
            relevant_tables={"orders", "users"},
            retrieved_columns={("orders", "id")},
            relevant_columns={("orders", "id"), ("users", "id")},
            total_retrieval_ms=150.3,
        )

        self.tracker.track_retrieval(metrics1)
        self.tracker.track_retrieval(metrics2)

        summary = self.tracker.get_performance_summary()
        recall_rates = summary["recall_rates"]

        # First query: 100% table recall, 100% column recall
        # Second query: 50% table recall, 50% column recall
        # Average: 75% for both
        assert recall_rates["table_recall"] == 0.75
        assert recall_rates["column_recall"] == 0.75
        assert recall_rates["sample_count"] == 2


class TestMetricsCollector:
    """Test metrics collection utilities."""

    def test_retrieval_metrics_collector(self):
        """Test retrieval metrics collection flow."""
        collector = RetrievalMetricsCollector()

        # Start retrieval
        metrics = collector.start_retrieval("find all users")
        assert metrics.query == "find all users"

        # Record search latencies
        collector.record_search_latency("token", 50.5, cache_hit=False)
        collector.record_search_latency("embedding", 100.2, cache_hit=True)

        assert metrics.token_search_ms == 50.5
        assert metrics.embedding_search_ms == 100.2
        assert metrics.token_cache_hit is False
        assert metrics.embedding_cache_hit is True

        # Record retrieved schema
        collector.record_retrieved_schema(
            tables={"users", "posts"}, columns={("users", "id"), ("users", "name")}
        )

        # Record relevant schema
        collector.record_relevant_schema(tables={"users"}, columns={("users", "id")})

        # Complete retrieval
        collector.complete_retrieval(200.0)

        # Verify metrics were tracked
        assert metrics.total_retrieval_ms == 200.0
        recall = metrics.calculate_recall()
        assert recall["table_recall"] == 1.0  # Retrieved all relevant tables
        assert recall["column_recall"] == 1.0  # Retrieved all relevant columns

    def test_query_complexity_analyzer(self):
        """Test query complexity analysis."""
        # Natural language analysis
        nl_complexity = QueryComplexityAnalyzer.analyze_natural_language(
            "Show me the total sum of orders grouped by user where status is active"
        )
        assert nl_complexity["token_count"] == 14
        assert nl_complexity["aggregation_count"] >= 1  # "sum" and "group"
        assert nl_complexity["filter_count"] >= 1  # "where"

        # SQL analysis
        sql = """
        SELECT user_id, SUM(amount) as total
        FROM orders o
        JOIN users u ON o.user_id = u.id
        WHERE o.status = 'active'
        GROUP BY user_id
        """

        sql_metrics = QueryComplexityAnalyzer.analyze_sql(sql)
        assert sql_metrics.table_count >= 2  # orders and users
        assert sql_metrics.join_count >= 1
        assert sql_metrics.filter_count >= 1
        assert sql_metrics.aggregation_count >= 2  # SUM and GROUP BY
        assert sql_metrics.complexity_score() > 0


class TestLatencyDecorator:
    """Test latency tracking decorator."""

    @pytest.mark.asyncio
    async def test_async_latency_tracking(self):
        """Test latency tracking for async functions."""
        reset_performance_tracker()

        @track_latency("test_component")
        async def slow_async_function():
            await asyncio.sleep(0.1)
            return "result"

        result = await slow_async_function()
        assert result == "result"

        # Check that latency was tracked
        tracker = get_performance_tracker()
        summary = tracker.get_performance_summary()

        assert "test_component" in summary["latency_percentiles"]
        stats = summary["latency_percentiles"]["test_component"]
        assert stats["count"] == 1
        assert stats["avg"] >= 100  # At least 100ms

    def test_sync_latency_tracking(self):
        """Test latency tracking for sync functions."""
        reset_performance_tracker()

        @track_latency("test_sync")
        def slow_sync_function():
            time.sleep(0.05)
            return "result"

        result = slow_sync_function()
        assert result == "result"

        # Check that latency was tracked
        tracker = get_performance_tracker()
        summary = tracker.get_performance_summary()

        assert "test_sync" in summary["latency_percentiles"]
        stats = summary["latency_percentiles"]["test_sync"]
        assert stats["count"] == 1
        assert stats["avg"] >= 50  # At least 50ms
