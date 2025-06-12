"""Test script to demonstrate the SENS agent capabilities."""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.sens.agents.core import SENSAgent  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


async def test_agent():
    """Test the agent with various queries."""
    agent = SENSAgent(max_iterations=5)

    test_queries = [
        # This should trigger value discovery
        "Show me Apple stock prices from 2024",
        # This should trigger temporal reasoning
        "What were the stock prices last month?",
        # This should trigger schema exploration
        "Show me technology companies",
    ]

    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print("=" * 60)

        try:
            result = await agent.process_query(
                user_query=query,
                conversation_id=f"test-{hash(query)}",
            )

            print("\n--- Reasoning Trace ---")
            for item in result.get("reasoning_trace", []):
                print(f"{item['type'].upper()}: {item['content']}")

            print("\n--- Result ---")
            print(f"Success: {result['success']}")
            print(f"Iterations: {result['iterations']}")

            if result["success"] and result.get("result"):
                print(f"Rows returned: {result['result'].get('row_count', 0)}")

            if result.get("discovered_mappings"):
                print("\n--- Discovered Mappings ---")
                for k, v in result["discovered_mappings"].items():
                    print(f"  {k} → {v}")

            if result.get("sql"):
                print("\n--- Generated SQL ---")
                print(
                    result["sql"][:200] + "..."
                    if len(result["sql"]) > 200
                    else result["sql"]
                )

        except Exception as e:
            print(f"Error: {e}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_agent())
