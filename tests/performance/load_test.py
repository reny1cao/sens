"""Load testing for the SENS system.

This script simulates multiple concurrent users making requests to test
system performance under load.

Run with: python tests/performance/load_test.py
"""

import asyncio
import statistics
import time
from dataclasses import dataclass
from typing import List, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

from sens.chat.orchestrator import ChatOrchestrator
from sens.chat.state import ConversationState
from sens.monitoring.performance_metrics import (
    get_performance_tracker,
    reset_performance_tracker,
)


@dataclass
class LoadTestResult:
    """Results from a load test run."""

    total_requests: int
    successful_requests: int
    failed_requests: int
    total_duration: float
    response_times: List[float]
    requests_per_second: float

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests

    @property
    def avg_response_time(self) -> float:
        """Calculate average response time."""
        if not self.response_times:
            return 0.0
        return statistics.mean(self.response_times)

    @property
    def p95_response_time(self) -> float:
        """Calculate 95th percentile response time."""
        if not self.response_times:
            return 0.0
        sorted_times = sorted(self.response_times)
        index = int(len(sorted_times) * 0.95)
        return sorted_times[index] if index < len(sorted_times) else sorted_times[-1]

    @property
    def p99_response_time(self) -> float:
        """Calculate 99th percentile response time."""
        if not self.response_times:
            return 0.0
        sorted_times = sorted(self.response_times)
        index = int(len(sorted_times) * 0.99)
        return sorted_times[index] if index < len(sorted_times) else sorted_times[-1]


class LoadTester:
    """Load testing utilities for SENS."""

    def __init__(self):
        """Initialize load tester."""
        self.queries = [
            "Show me all active users",
            "What are the top selling products?",
            "Calculate monthly revenue trends",
            "Find orders pending shipment",
            "Get customer purchase history",
            "Show inventory levels by warehouse",
            "Analyze user engagement metrics",
            "List employees by department",
            "Calculate conversion rates",
            "Show recent transactions",
        ]

    async def simulate_user(
        self,
        user_id: int,
        orchestrator: ChatOrchestrator,
        num_requests: int,
        delay_between_requests: float = 0.1,
    ) -> Tuple[int, int, List[float]]:
        """Simulate a single user making multiple requests.

        Returns:
            Tuple of (successful_requests, failed_requests, response_times)
        """
        successful = 0
        failed = 0
        response_times = []

        state = ConversationState(conversation_id=f"user_{user_id}")

        for i in range(num_requests):
            query = self.queries[i % len(self.queries)]

            start_time = time.time()
            try:
                response, state = await orchestrator.step(state, query)
                if response.get("status") == "success":
                    successful += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"User {user_id} request {i} failed: {e}")
                failed += 1

            response_time = (time.time() - start_time) * 1000  # Convert to ms
            response_times.append(response_time)

            # Small delay between requests
            if i < num_requests - 1:
                await asyncio.sleep(delay_between_requests)

        return successful, failed, response_times

    async def run_load_test(
        self,
        num_users: int,
        requests_per_user: int,
        ramp_up_time: float = 0.0,
    ) -> LoadTestResult:
        """Run a load test with multiple concurrent users.

        Args:
            num_users: Number of concurrent users to simulate
            requests_per_user: Number of requests each user will make
            ramp_up_time: Time in seconds to ramp up all users

        Returns:
            LoadTestResult with test metrics
        """
        print("\nStarting load test:")
        print(f"  Users: {num_users}")
        print(f"  Requests per user: {requests_per_user}")
        print(f"  Total requests: {num_users * requests_per_user}")
        print(f"  Ramp-up time: {ramp_up_time}s")

        reset_performance_tracker()

        # Create orchestrators with mocked components
        orchestrators = []
        for _ in range(num_users):
            with (
                patch(
                    "sens.chat.orchestrator.OptimizedSchemaRetriever"
                ) as mock_retriever,
                patch(
                    "sens.chat.orchestrator.IntentExtractor"
                ) as mock_intent_extractor,
                patch(
                    "sens.chat.orchestrator.IntentValidator"
                ) as mock_intent_validator,
                patch("sens.chat.orchestrator.SQLGenerator") as mock_sql_generator,
                patch("sens.chat.orchestrator.SQLValidator") as mock_validator,
                patch("sens.chat.orchestrator.SQLExecutor") as mock_executor,
                patch(
                    "sens.chat.orchestrator.ResponseBuilder"
                ) as mock_response_builder,
            ):

                # Setup minimal mocks for load testing
                self._setup_mocks(
                    mock_retriever,
                    mock_intent_extractor,
                    mock_intent_validator,
                    mock_sql_generator,
                    mock_validator,
                    mock_executor,
                    mock_response_builder,
                )

                orchestrator = ChatOrchestrator(use_optimized_retriever=True)
                orchestrators.append(orchestrator)

        # Start load test
        start_time = time.time()

        # Create user tasks with ramp-up
        tasks = []
        for i in range(num_users):
            # Stagger user start times during ramp-up
            if ramp_up_time > 0 and i > 0:
                delay = (ramp_up_time / num_users) * i
                task = self._delayed_user_start(
                    delay,
                    i,
                    orchestrators[i],
                    requests_per_user,
                )
            else:
                task = self.simulate_user(i, orchestrators[i], requests_per_user)

            tasks.append(task)

        # Wait for all users to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        total_duration = time.time() - start_time

        # Aggregate results
        total_successful = 0
        total_failed = 0
        all_response_times = []

        for result in results:
            if isinstance(result, Exception):
                print(f"User task failed with exception: {result}")
                total_failed += requests_per_user
            else:
                successful, failed, response_times = result
                total_successful += successful
                total_failed += failed
                all_response_times.extend(response_times)

        total_requests = total_successful + total_failed
        rps = total_requests / total_duration if total_duration > 0 else 0

        return LoadTestResult(
            total_requests=total_requests,
            successful_requests=total_successful,
            failed_requests=total_failed,
            total_duration=total_duration,
            response_times=all_response_times,
            requests_per_second=rps,
        )

    async def _delayed_user_start(
        self,
        delay: float,
        user_id: int,
        orchestrator: ChatOrchestrator,
        num_requests: int,
    ) -> Tuple[int, int, List[float]]:
        """Start a user simulation after a delay."""
        await asyncio.sleep(delay)
        return await self.simulate_user(user_id, orchestrator, num_requests)

    def _setup_mocks(
        self,
        mock_retriever,
        mock_intent_extractor,
        mock_intent_validator,
        mock_sql_generator,
        mock_validator,
        mock_executor,
        mock_response_builder,
    ):
        """Setup mocks for load testing."""
        # Quick mock responses for load testing
        mock_retriever_instance = AsyncMock()
        mock_retriever_instance.get_relevant_context = AsyncMock(
            return_value=MagicMock(tables=[], columns=[])
        )
        mock_retriever.return_value = mock_retriever_instance

        mock_intent_extractor.return_value.extract = AsyncMock(return_value=MagicMock())

        mock_intent_validator.return_value.validate = MagicMock(
            return_value=MagicMock(is_valid=True)
        )

        mock_sql_generator.return_value.generate = AsyncMock(
            return_value=MagicMock(sql="SELECT 1", tables_used=[], columns_used=[])
        )

        mock_validator.return_value.validate = MagicMock(
            return_value=MagicMock(is_valid=True, errors=[])
        )

        # Create a proper mock for query result
        query_result = MagicMock()
        query_result.columns = ["col1"]
        query_result.rows = [[1]]
        query_result.row_count = 1
        query_result.execution_time_ms = 10.0

        mock_executor.return_value.execute = AsyncMock(return_value=query_result)

        mock_response_builder.return_value.build = MagicMock(
            return_value={"status": "success", "results": {}}
        )


def print_load_test_results(result: LoadTestResult):
    """Print load test results in a formatted way."""
    print("\n" + "=" * 60)
    print("LOAD TEST RESULTS")
    print("=" * 60)

    print("\nSummary:")
    print(f"  Total Requests: {result.total_requests}")
    print(f"  Successful: {result.successful_requests}")
    print(f"  Failed: {result.failed_requests}")
    print(f"  Success Rate: {result.success_rate:.1%}")
    print(f"  Total Duration: {result.total_duration:.2f}s")
    print(f"  Requests/Second: {result.requests_per_second:.2f}")

    if result.response_times:
        print("\nResponse Times (ms):")
        print(f"  Average: {result.avg_response_time:.2f}")
        print(f"  Min: {min(result.response_times):.2f}")
        print(f"  Max: {max(result.response_times):.2f}")
        print(f"  P95: {result.p95_response_time:.2f}")
        print(f"  P99: {result.p99_response_time:.2f}")

    # Performance assessment
    print("\nPerformance Assessment:")
    if result.success_rate >= 0.99:
        print("  ✅ Excellent reliability (>99% success rate)")
    elif result.success_rate >= 0.95:
        print("  ⚠️  Good reliability (>95% success rate)")
    else:
        print("  ❌ Poor reliability (<95% success rate)")

    if result.avg_response_time <= 100:
        print("  ✅ Excellent response time (<100ms average)")
    elif result.avg_response_time <= 500:
        print("  ⚠️  Good response time (<500ms average)")
    else:
        print("  ❌ Slow response time (>500ms average)")

    if result.requests_per_second >= 100:
        print("  ✅ High throughput (>100 req/s)")
    elif result.requests_per_second >= 50:
        print("  ⚠️  Moderate throughput (>50 req/s)")
    else:
        print("  ❌ Low throughput (<50 req/s)")


async def main():
    """Run load tests with different configurations."""
    tester = LoadTester()

    # Test 1: Light load
    print("\n🔵 Running light load test...")
    light_result = await tester.run_load_test(
        num_users=5,
        requests_per_user=10,
        ramp_up_time=0,
    )
    print_load_test_results(light_result)

    # Test 2: Medium load with ramp-up
    print("\n🟡 Running medium load test...")
    medium_result = await tester.run_load_test(
        num_users=20,
        requests_per_user=10,
        ramp_up_time=5.0,
    )
    print_load_test_results(medium_result)

    # Test 3: Heavy load
    print("\n🔴 Running heavy load test...")
    heavy_result = await tester.run_load_test(
        num_users=50,
        requests_per_user=5,
        ramp_up_time=10.0,
    )
    print_load_test_results(heavy_result)

    # Final performance metrics
    print("\n" + "=" * 60)
    print("COMPONENT PERFORMANCE METRICS")
    print("=" * 60)

    tracker = get_performance_tracker()
    summary = tracker.get_performance_summary()

    if "latency_percentiles" in summary:
        for component, stats in summary["latency_percentiles"].items():
            print(f"\n{component}:")
            print(f"  Requests: {stats['count']}")
            print(f"  Avg Latency: {stats['avg']:.2f}ms")
            print(f"  P95 Latency: {stats['p95']:.2f}ms")


if __name__ == "__main__":
    asyncio.run(main())
