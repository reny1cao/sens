"""Performance tests for the TokenIndexBuilder implementation."""

import time
from typing import List

import pytest

from sens.token_index import TokenIndexBuilder


@pytest.fixture
def large_table_set() -> List[str]:
    """Generate a large set of table names (1000 tables)."""
    formats = [
        "user_{}_data",
        "customer{}Profile",
        "order-{}-history",
        "product_{}_variant",
        "payment{}Method",
        "shipping_{}_address",
        "inventory{}Status",
        "category_{}_mapping",
        "analytics{}Metric",
        "settings_{}_config",
    ]

    tables = []
    for i in range(100):  # 100 variations of each format = 1000 tables
        for fmt in formats:
            if "{}" in fmt:
                tables.append(fmt.format(i))
            else:
                tables.append(f"{fmt}_{i}")

    return tables


def test_build_performance(large_table_set):
    """Test index building performance."""
    builder = TokenIndexBuilder()

    start_time = time.time()
    builder.build_index(large_table_set)
    build_time = time.time() - start_time

    # Building index should be reasonably fast
    assert build_time < 5.0, f"Index build took {build_time:.2f} seconds"


def test_lookup_latency(large_table_set):
    """Test lookup latency requirements (<2ms)."""
    builder = TokenIndexBuilder()
    builder.build_index(large_table_set)

    queries = ["user", "customer", "order", "product", "payment", "nonexistent"]

    for query in queries:
        start_time = time.time()
        builder.guess_tables(query)
        query_time = time.time() - start_time

        # Each lookup should complete within 2ms
        assert query_time < 0.002, f"Query '{query}' took {query_time*1000:.2f}ms"


def test_memory_usage(large_table_set):
    """Test memory usage requirements (<1MB for 1K tables)."""
    builder = TokenIndexBuilder()
    builder.build_index(large_table_set)

    # Memory should be under 1MB
    assert builder.index._current_size_bytes < 1_000_000, (
        f"Memory usage {builder.index._current_size_bytes/1024/1024:.2f}MB "
        "exceeds 1MB limit"
    )
