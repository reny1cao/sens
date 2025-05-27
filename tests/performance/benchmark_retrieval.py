"""Performance benchmarks for the retrieval system.

Run with: poetry run pytest tests/performance/benchmark_retrieval.py -v --benchmark-only
"""

import asyncio
import random
import time
from typing import List

import pytest

from sens.caching.factory import get_cache_manager
from sens.monitoring.performance_metrics import (
    get_performance_tracker,
    reset_performance_tracker,
)
from sens.retrieval.embedding.search import EmbeddingSearch
from sens.retrieval.optimized_retriever import OptimizedSchemaRetriever
from sens.retrieval.orchestrator import RetrievalOrchestrator
from sens.retrieval.token.builder import TokenIndexBuilder
from sens.schema.graph import SchemaGraph


class BenchmarkSetup:
    """Setup utilities for benchmarks."""

    @staticmethod
    def get_sample_queries() -> List[str]:
        """Get a diverse set of sample queries for benchmarking."""
        return [
            "Show me all users who signed up last month",
            "What is the total revenue by product category?",
            "Find orders with status pending and amount over 1000",
            "List top 10 customers by purchase amount",
            "Get average order value by month for 2024",
            "Show products that are out of stock",
            "Find all employees in the engineering department",
            "Calculate the conversion rate by marketing channel",
            "Show me user activity logs from yesterday",
            "What are the most popular products this week?",
        ]

    @staticmethod
    def setup_retrieval_components():
        """Setup retrieval components for benchmarking."""
        schema_graph = SchemaGraph.get_instance()
        token_index = TokenIndexBuilder()
        embedding_index = EmbeddingSearch()
        cache_manager = get_cache_manager()

        return {
            "schema_graph": schema_graph,
            "token_index": token_index,
            "embedding_index": embedding_index,
            "cache_manager": cache_manager,
        }


@pytest.mark.benchmark
class TestRetrievalBenchmarks:
    """Benchmark tests for retrieval system."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each benchmark test."""
        reset_performance_tracker()
        self.components = BenchmarkSetup.setup_retrieval_components()
        self.queries = BenchmarkSetup.get_sample_queries()

    def test_standard_retriever_performance(self, benchmark):
        """Benchmark standard retrieval orchestrator."""
        retriever = RetrievalOrchestrator(
            token_index=self.components["token_index"],
            embedding_index=self.components["embedding_index"],
            schema_graph=self.components["schema_graph"],
        )

        async def retrieve_batch():
            tasks = []
            for query in self.queries:
                tasks.append(retriever.get_relevant_context(query))
            return await asyncio.gather(*tasks)

        # Run benchmark
        results = benchmark(lambda: asyncio.run(retrieve_batch()))

        # Verify results
        assert len(results) == len(self.queries)
        for result in results:
            assert result.tables is not None
            assert result.columns is not None

    def test_optimized_retriever_performance(self, benchmark):
        """Benchmark optimized schema retriever."""
        retriever = OptimizedSchemaRetriever(
            token_index=self.components["token_index"],
            embedding_index=self.components["embedding_index"],
            schema_graph=self.components["schema_graph"],
            cache_manager=self.components["cache_manager"],
            enable_caching=True,
        )

        async def retrieve_batch():
            tasks = []
            for query in self.queries:
                tasks.append(retriever.get_relevant_context(query))
            return await asyncio.gather(*tasks)

        # Run benchmark
        results = benchmark(lambda: asyncio.run(retrieve_batch()))

        # Verify results
        assert len(results) == len(self.queries)
        for result in results:
            assert result.tables is not None
            assert result.columns is not None

    def test_cache_effectiveness(self, benchmark):
        """Benchmark cache hit performance."""
        retriever = OptimizedSchemaRetriever(
            token_index=self.components["token_index"],
            embedding_index=self.components["embedding_index"],
            schema_graph=self.components["schema_graph"],
            cache_manager=self.components["cache_manager"],
            enable_caching=True,
        )

        # Warm up cache
        async def warmup():
            for query in self.queries[:5]:  # Cache first 5 queries
                await retriever.get_relevant_context(query)

        asyncio.run(warmup())

        # Benchmark with mix of cached and uncached queries
        async def retrieve_mixed():
            tasks = []
            # First 5 should hit cache, last 5 should miss
            for query in self.queries:
                tasks.append(retriever.get_relevant_context(query))
            return await asyncio.gather(*tasks)

        # Run benchmark
        benchmark(lambda: asyncio.run(retrieve_mixed()))

        # Get performance summary
        tracker = get_performance_tracker()
        summary = tracker.get_performance_summary()

        # Verify cache was used
        if "cache_hit_rates" in summary:
            assert any(rate > 0 for rate in summary["cache_hit_rates"].values())

    def test_concurrent_retrieval_scaling(self, benchmark):
        """Benchmark concurrent retrieval performance."""
        retriever = OptimizedSchemaRetriever(
            token_index=self.components["token_index"],
            embedding_index=self.components["embedding_index"],
            schema_graph=self.components["schema_graph"],
            cache_manager=self.components["cache_manager"],
            enable_caching=True,
        )

        # Generate more queries for concurrency test
        extended_queries = self.queries * 5  # 50 queries
        random.shuffle(extended_queries)

        async def retrieve_concurrent():
            tasks = []
            for query in extended_queries:
                tasks.append(retriever.get_relevant_context(query))
            return await asyncio.gather(*tasks)

        # Run benchmark
        results = benchmark(lambda: asyncio.run(retrieve_concurrent()))

        # Verify all queries completed
        assert len(results) == len(extended_queries)

    @pytest.mark.parametrize("batch_size", [1, 5, 10, 20])
    def test_batch_size_impact(self, benchmark, batch_size):
        """Benchmark impact of different batch sizes."""
        retriever = OptimizedSchemaRetriever(
            token_index=self.components["token_index"],
            embedding_index=self.components["embedding_index"],
            schema_graph=self.components["schema_graph"],
            cache_manager=self.components["cache_manager"],
            enable_caching=True,
        )

        async def retrieve_batch():
            tasks = []
            for query in self.queries[:batch_size]:
                tasks.append(retriever.get_relevant_context(query))
            return await asyncio.gather(*tasks)

        # Run benchmark
        results = benchmark(lambda: asyncio.run(retrieve_batch()))

        # Verify results
        assert len(results) == min(batch_size, len(self.queries))


def report_performance_summary():
    """Generate a performance summary report."""
    tracker = get_performance_tracker()
    summary = tracker.get_performance_summary()

    print("\n=== Performance Summary ===")

    # Latency percentiles
    if "latency_percentiles" in summary:
        print("\nComponent Latencies (ms):")
        for component, stats in summary["latency_percentiles"].items():
            print(f"  {component}:")
            print(f"    Count: {stats['count']}")
            print(f"    Average: {stats['avg']:.2f}")
            print(f"    P50: {stats['p50']:.2f}")
            print(f"    P95: {stats['p95']:.2f}")
            print(f"    P99: {stats['p99']:.2f}")

    # Cache hit rates
    if "cache_hit_rates" in summary:
        print("\nCache Hit Rates:")
        for cache_type, rate in summary["cache_hit_rates"].items():
            print(f"  {cache_type}: {rate:.2%}")

    # Recall rates
    if "recall_rates" in summary:
        print("\nRecall Rates:")
        print(f"  Table Recall: {summary['recall_rates']['table_recall']:.2%}")
        print(f"  Column Recall: {summary['recall_rates']['column_recall']:.2%}")
        print(f"  Sample Count: {summary['recall_rates']['sample_count']}")


if __name__ == "__main__":
    # Run benchmarks with pytest-benchmark
    pytest.main([__file__, "-v", "--benchmark-only", "--benchmark-compare"])
    report_performance_summary()
