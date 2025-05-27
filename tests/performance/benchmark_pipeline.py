"""Performance benchmarks for the full NL2SQL pipeline.

Run with: poetry run pytest tests/performance/benchmark_pipeline.py -v --benchmark-only
"""

import asyncio
import time
from typing import Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sens.chat.orchestrator import ChatOrchestrator
from sens.chat.state import ConversationState
from sens.cli.enhanced_pipeline import EnhancedNL2SQLPipeline
from sens.execution.types import QueryResult
from sens.llm.models import GeneratedSQL, Intent, IntentType, ValidatedIntent
from sens.monitoring.performance_metrics import (
    get_performance_tracker,
    reset_performance_tracker,
)
from sens.retrieval.models import ColumnInfo, RetrievedContext, TableInfo


class MockComponents:
    """Mock components for pipeline benchmarking."""

    @staticmethod
    def create_mock_intent() -> Intent:
        """Create a mock intent."""
        return Intent(
            query_type=IntentType.ANALYTICAL,
            tables=["users", "orders"],
            operations=["SELECT", "JOIN", "GROUP BY"],
            filters=["date range", "status"],
            aggregations=["COUNT", "SUM"],
            confidence=0.95,
        )

    @staticmethod
    def create_mock_validated_intent() -> ValidatedIntent:
        """Create a mock validated intent."""
        return ValidatedIntent(
            query_type=IntentType.ANALYTICAL,
            tables=["users", "orders"],
            operations=["SELECT", "JOIN", "GROUP BY"],
            filters=["date range", "status"],
            aggregations=["COUNT", "SUM"],
            confidence=0.95,
            is_valid=True,
        )

    @staticmethod
    def create_mock_retrieved_context() -> RetrievedContext:
        """Create a mock retrieved context."""
        return RetrievedContext(
            tables=[
                TableInfo(
                    table_name="users",
                    description="User information",
                    sample_values={},
                ),
                TableInfo(
                    table_name="orders",
                    description="Order information",
                    sample_values={},
                ),
            ],
            columns=[
                ColumnInfo(
                    table_name="users",
                    column_name="id",
                    data_type="integer",
                    is_primary_key=True,
                ),
                ColumnInfo(
                    table_name="users",
                    column_name="name",
                    data_type="varchar",
                ),
                ColumnInfo(
                    table_name="orders",
                    column_name="id",
                    data_type="integer",
                    is_primary_key=True,
                ),
                ColumnInfo(
                    table_name="orders",
                    column_name="user_id",
                    data_type="integer",
                    is_foreign_key=True,
                ),
                ColumnInfo(
                    table_name="orders",
                    column_name="amount",
                    data_type="decimal",
                ),
            ],
            relationships=[],
        )

    @staticmethod
    def create_mock_sql() -> GeneratedSQL:
        """Create a mock generated SQL."""
        return GeneratedSQL(
            sql="""
            SELECT u.name, COUNT(o.id) as order_count, SUM(o.amount) as total_amount
            FROM users u
            JOIN orders o ON u.id = o.user_id
            WHERE o.created_at >= '2024-01-01'
            GROUP BY u.name
            ORDER BY total_amount DESC
            """,
            explanation="Aggregate order data by user",
            confidence=0.9,
            tables_used=["users", "orders"],
            columns_used=["users.name", "orders.id", "orders.amount", "orders.user_id"],
            model_used="gpt-4",
            generation_ms=150.0,
        )

    @staticmethod
    def create_mock_query_result() -> QueryResult:
        """Create a mock query execution result."""
        return QueryResult(
            columns=["name", "order_count", "total_amount"],
            rows=[
                ["Alice", 5, 1500.00],
                ["Bob", 3, 800.00],
                ["Charlie", 7, 2100.00],
            ],
            row_count=3,
            execution_time_ms=25.0,
        )


@pytest.mark.benchmark
class TestPipelineBenchmarks:
    """Benchmark tests for the full pipeline."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each benchmark test."""
        reset_performance_tracker()
        self.sample_queries = [
            "Show me total sales by month",
            "Find top customers by revenue",
            "What products are low in stock?",
            "Calculate average order value by region",
            "Show employee performance metrics",
        ]

    @patch("sens.chat.orchestrator.OptimizedSchemaRetriever")
    @patch("sens.chat.orchestrator.IntentExtractor")
    @patch("sens.chat.orchestrator.IntentValidator")
    @patch("sens.chat.orchestrator.SQLGenerator")
    @patch("sens.chat.orchestrator.SQLValidator")
    @patch("sens.chat.orchestrator.SQLExecutor")
    @patch("sens.chat.orchestrator.ResponseBuilder")
    def test_chat_orchestrator_performance(
        self,
        mock_response_builder,
        mock_executor,
        mock_validator,
        mock_sql_generator,
        mock_intent_validator,
        mock_intent_extractor,
        mock_retriever,
        benchmark,
    ):
        """Benchmark ChatOrchestrator performance."""
        # Setup mocks
        mock_retriever_instance = AsyncMock()
        mock_retriever_instance.get_relevant_context = AsyncMock(
            return_value=MockComponents.create_mock_retrieved_context()
        )
        mock_retriever.return_value = mock_retriever_instance

        mock_intent_extractor.return_value.extract = AsyncMock(
            return_value=MockComponents.create_mock_intent()
        )

        mock_intent_validator.return_value.validate = MagicMock(
            return_value=MockComponents.create_mock_validated_intent()
        )

        mock_sql_generator.return_value.generate = AsyncMock(
            return_value=MockComponents.create_mock_sql()
        )

        mock_validator.return_value.validate = MagicMock(
            return_value=MagicMock(is_valid=True, errors=[])
        )

        mock_executor.return_value.execute = AsyncMock(
            return_value=MockComponents.create_mock_query_result()
        )

        mock_response_builder.return_value.build = MagicMock(
            return_value={
                "status": "success",
                "sql": "SELECT ...",
                "results": {"columns": [], "rows": []},
            }
        )

        # Create orchestrator
        orchestrator = ChatOrchestrator(use_optimized_retriever=True)

        async def process_queries():
            results = []
            for query in self.sample_queries:
                state = ConversationState(conversation_id="test")
                response, _ = await orchestrator.step(state, query)
                results.append(response)
            return results

        # Run benchmark
        results = benchmark(lambda: asyncio.run(process_queries()))

        # Verify results
        assert len(results) == len(self.sample_queries)
        for result in results:
            assert result["status"] == "success"

    @patch("sens.cli.enhanced_pipeline.ChatOrchestrator")
    def test_enhanced_pipeline_performance(self, mock_orchestrator_class, benchmark):
        """Benchmark EnhancedNL2SQLPipeline performance."""
        # Setup mock orchestrator
        mock_orchestrator = AsyncMock()
        mock_orchestrator.step = AsyncMock(
            return_value=(
                {
                    "status": "success",
                    "sql": "SELECT ...",
                    "results": {"columns": [], "rows": []},
                    "metadata": {"pipeline_metrics": {}},
                },
                ConversationState(conversation_id="test"),
            )
        )
        mock_orchestrator_class.return_value = mock_orchestrator

        # Create pipeline
        pipeline = EnhancedNL2SQLPipeline(metrics_enabled=True)

        async def process_batch():
            results = []
            for query in self.sample_queries:
                result = await pipeline.process_question(query)
                results.append(result)
            return results

        # Run benchmark
        results = benchmark(lambda: asyncio.run(process_batch()))

        # Verify results
        assert len(results) == len(self.sample_queries)
        for result in results:
            assert "status" in result
            assert "metadata" in result

    def test_concurrent_pipeline_requests(self, benchmark):
        """Benchmark concurrent pipeline request handling."""
        with (
            patch("sens.chat.orchestrator.OptimizedSchemaRetriever") as mock_retriever,
            patch("sens.chat.orchestrator.IntentExtractor") as mock_intent_extractor,
            patch("sens.chat.orchestrator.IntentValidator") as mock_intent_validator,
            patch("sens.chat.orchestrator.SQLGenerator") as mock_sql_generator,
            patch("sens.chat.orchestrator.SQLValidator") as mock_validator,
            patch("sens.chat.orchestrator.SQLExecutor") as mock_executor,
            patch("sens.chat.orchestrator.ResponseBuilder") as mock_response_builder,
        ):

            # Setup all mocks (same as above)
            mock_retriever_instance = AsyncMock()
            mock_retriever_instance.get_relevant_context = AsyncMock(
                return_value=MockComponents.create_mock_retrieved_context()
            )
            mock_retriever.return_value = mock_retriever_instance

            mock_intent_extractor.return_value.extract = AsyncMock(
                return_value=MockComponents.create_mock_intent()
            )

            mock_intent_validator.return_value.validate = MagicMock(
                return_value=MockComponents.create_mock_validated_intent()
            )

            mock_sql_generator.return_value.generate = AsyncMock(
                return_value=MockComponents.create_mock_sql()
            )

            mock_validator.return_value.validate = MagicMock(
                return_value=MagicMock(is_valid=True, errors=[])
            )

            mock_executor.return_value.execute = AsyncMock(
                return_value=MockComponents.create_mock_query_result()
            )

            mock_response_builder.return_value.build = MagicMock(
                return_value={
                    "status": "success",
                    "sql": "SELECT ...",
                    "results": {"columns": [], "rows": []},
                }
            )

            # Create multiple orchestrators to simulate concurrent users
            orchestrators = [
                ChatOrchestrator(use_optimized_retriever=True) for _ in range(5)
            ]

            async def process_concurrent():
                tasks = []
                for i, query in enumerate(self.sample_queries * 2):  # 10 total queries
                    orchestrator = orchestrators[i % len(orchestrators)]
                    state = ConversationState(conversation_id=f"test_{i}")
                    tasks.append(orchestrator.step(state, query))

                return await asyncio.gather(*tasks)

            # Run benchmark
            results = benchmark(lambda: asyncio.run(process_concurrent()))

            # Verify results
            assert len(results) == len(self.sample_queries) * 2
            for response, _ in results:
                assert response["status"] == "success"


def generate_performance_report():
    """Generate a detailed performance report."""
    tracker = get_performance_tracker()
    summary = tracker.get_performance_summary()

    print("\n=== Pipeline Performance Report ===")

    # Component latencies
    if "latency_percentiles" in summary:
        print("\nComponent Performance (ms):")
        components = [
            "schema_retrieval",
            "intent_extraction",
            "intent_validation",
            "sql_generation",
            "sql_validation",
            "sql_execution",
            "response_building",
        ]

        for component in components:
            if component in summary["latency_percentiles"]:
                stats = summary["latency_percentiles"][component]
                print(f"\n  {component}:")
                print(f"    Requests: {stats['count']}")
                print(f"    Average: {stats['avg']:.2f} ms")
                print(f"    P50: {stats['p50']:.2f} ms")
                print(f"    P95: {stats['p95']:.2f} ms")
                print(f"    P99: {stats['p99']:.2f} ms")

    # Overall pipeline metrics
    print("\n\nOverall Pipeline Metrics:")
    total_latency = sum(
        stats["avg"] * stats["count"]
        for stats in summary.get("latency_percentiles", {}).values()
    )
    total_requests = sum(
        stats["count"] for stats in summary.get("latency_percentiles", {}).values()
    )

    if total_requests > 0:
        print(f"  Average End-to-End Latency: {total_latency / total_requests:.2f} ms")
        print(f"  Total Requests Processed: {total_requests}")

    # Cache effectiveness
    if "cache_hit_rates" in summary:
        print("\n\nCache Effectiveness:")
        for cache_type, rate in summary["cache_hit_rates"].items():
            print(f"  {cache_type}: {rate:.1%} hit rate")

    # Recommendations
    print("\n\nPerformance Recommendations:")
    if summary.get("latency_percentiles", {}):
        # Find slowest components
        slowest = sorted(
            summary["latency_percentiles"].items(),
            key=lambda x: x[1]["avg"],
            reverse=True,
        )[:3]

        print("\n  Top 3 Slowest Components:")
        for component, stats in slowest:
            print(f"    - {component}: {stats['avg']:.2f} ms average")

        # Cache recommendations
        if summary.get("cache_hit_rates", {}):
            low_hit_rates = [
                (cache, rate)
                for cache, rate in summary["cache_hit_rates"].items()
                if rate < 0.5
            ]
            if low_hit_rates:
                print("\n  Caches with Low Hit Rates:")
                for cache, rate in low_hit_rates:
                    print(
                        f"    - {cache}: {rate:.1%} (consider warming or adjusting TTL)"
                    )


if __name__ == "__main__":
    # Run benchmarks
    pytest.main([__file__, "-v", "--benchmark-only"])
    generate_performance_report()
