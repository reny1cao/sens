"""Integration tests for performance metrics collection."""

import time
from unittest.mock import MagicMock, patch

import pytest

from sens.monitoring.metrics_collector import RetrievalMetricsCollector
from sens.monitoring.performance_metrics import (
    get_performance_tracker,
    reset_performance_tracker,
)
from sens.schema.context import ValidatorSchemaContext
from sens.validation.sql_validator import SQLValidator


class TestPerformanceMetricsIntegration:
    """Test performance metrics integration across components."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Reset tracker before each test."""
        reset_performance_tracker()

    def test_retrieval_performance_tracking(self):
        """Test that retrieval operations are tracked."""
        collector = RetrievalMetricsCollector()
        tracker = get_performance_tracker()

        # Simulate retrieval with timing
        collector.start_retrieval("test query")

        # Simulate token search
        time.sleep(0.01)  # 10ms
        collector.record_search_latency("token", 10.0, cache_hit=False)

        # Simulate embedding search
        time.sleep(0.02)  # 20ms
        collector.record_search_latency("embedding", 20.0, cache_hit=True)

        # Record schema
        collector.record_retrieved_schema(
            tables={"users", "orders"}, columns={("users", "id"), ("users", "name")}
        )

        # Complete retrieval
        collector.complete_retrieval(35.0)

        # Check performance summary
        summary = tracker.get_performance_summary()

        # Verify latencies were tracked
        assert "token_search" in summary["latency_percentiles"]
        assert "embedding_search" in summary["latency_percentiles"]

        # Verify cache tracking
        assert summary["cache_hit_rates"]["token"] == 0.0  # No hit
        assert summary["cache_hit_rates"]["embedding"] == 1.0  # Hit

    def test_sql_validation_recall_tracking(self):
        """Test that SQL validation tracks recall metrics."""
        validator = SQLValidator()
        collector = RetrievalMetricsCollector()
        tracker = get_performance_tracker()

        # Setup schema
        schema = ValidatorSchemaContext(
            tables=["users", "orders"],
            columns_per_table={
                "users": ["id", "name", "email"],
                "orders": ["id", "user_id", "total"],
            },
        )

        # Start retrieval
        collector.start_retrieval("find user orders")
        collector.record_retrieved_schema(
            tables={"users", "orders", "products"},  # Extra table
            columns={
                ("users", "id"),
                ("users", "name"),
                ("orders", "id"),
                ("orders", "total"),
                ("products", "id"),  # Extra columns
            },
        )

        # Validate SQL - should track recall
        sql = """
        SELECT u.name, o.total
        FROM users u
        JOIN orders o ON u.id = o.user_id
        """

        result = validator.validate(
            sql=sql, full_schema=schema, retrieval_metrics_collector=collector
        )

        assert result.is_valid

        # Check recall was calculated
        summary = tracker.get_performance_summary()
        assert "recall_rates" in summary
        assert summary["recall_rates"]["sample_count"] == 1
        assert summary["recall_rates"]["table_recall"] == 1.0  # Both tables retrieved
        assert summary["recall_rates"]["column_recall"] < 1.0  # Extra columns retrieved

    def test_component_latency_aggregation(self):
        """Test aggregation of component latencies."""
        tracker = get_performance_tracker()

        # Track multiple operations
        components = [
            ("schema_retrieval", [50.0, 45.0, 55.0]),
            ("intent_extraction", [100.0, 110.0, 95.0]),
            ("sql_generation", [200.0, 180.0, 220.0]),
            ("sql_validation", [10.0, 12.0, 8.0]),
            ("sql_execution", [30.0, 35.0, 25.0]),
        ]

        for component, latencies in components:
            for latency in latencies:
                tracker.track_component_latency(component, latency)

        # Get summary
        summary = tracker.get_performance_summary()

        # Verify all components tracked
        for component, _ in components:
            assert component in summary["latency_percentiles"]
            stats = summary["latency_percentiles"][component]
            assert stats["count"] == 3
            assert stats["avg"] > 0
            assert stats["p50"] > 0
            assert stats["p95"] > 0
            assert stats["p99"] > 0

    def test_query_complexity_impact(self):
        """Test that query complexity is tracked."""
        from sens.monitoring.metrics_collector import QueryComplexityAnalyzer

        tracker = get_performance_tracker()

        # Simple query
        simple_metrics = QueryComplexityAnalyzer.analyze_sql(
            "SELECT * FROM users WHERE id = 1"
        )
        tracker.track_query_complexity(simple_metrics)

        # Complex query
        complex_sql = """
        SELECT u.name, COUNT(o.id), SUM(o.total)
        FROM users u
        JOIN orders o ON u.id = o.user_id
        JOIN products p ON o.product_id = p.id
        WHERE o.created_at > '2024-01-01'
        GROUP BY u.name
        HAVING COUNT(o.id) > 5
        """
        complex_metrics = QueryComplexityAnalyzer.analyze_sql(complex_sql)
        tracker.track_query_complexity(complex_metrics)

        # Check complexity tracking
        summary = tracker.get_performance_summary()
        assert "query_complexity" in summary

        complexity = summary["query_complexity"]
        assert complexity["total_queries"] == 2
        assert complexity["avg_complexity_score"] > 0
        assert complexity["max_complexity_score"] > complexity["min_complexity_score"]

    def test_end_to_end_metrics_flow(self):
        """Test complete metrics flow through pipeline."""
        tracker = get_performance_tracker()

        # Simulate full pipeline execution
        pipeline_steps = [
            ("schema_retrieval", 50.0),
            ("intent_extraction", 100.0),
            ("intent_validation", 5.0),
            ("sql_generation", 150.0),
            ("sql_validation", 10.0),
            ("sql_execution", 30.0),
            ("response_building", 20.0),
        ]

        # Track each step
        for step, latency in pipeline_steps:
            tracker.track_component_latency(step, latency)

        # Track cache hits/misses
        tracker.track_cache_hit("embedding")
        tracker.track_cache_miss("token")
        tracker.track_cache_hit("llm")

        # Track recall
        from sens.monitoring.performance_metrics import RetrievalMetrics

        retrieval_metrics = RetrievalMetrics(
            query="test",
            retrieved_tables={"users", "orders"},
            relevant_tables={"users"},
            retrieved_columns={("users", "id"), ("orders", "total")},
            relevant_columns={("users", "id")},
            total_retrieval_ms=50.0,
        )
        tracker.track_retrieval(retrieval_metrics)

        # Get comprehensive summary
        summary = tracker.get_performance_summary()

        # Verify all metrics present
        assert len(summary["latency_percentiles"]) == len(pipeline_steps)
        assert all(
            cache in summary["cache_hit_rates"]
            for cache in ["embedding", "token", "llm"]
        )
        assert summary["recall_rates"]["sample_count"] == 1

        # Calculate total pipeline latency
        total_latency = sum(latency for _, latency in pipeline_steps)
        assert total_latency == 365.0  # Sum of all steps
