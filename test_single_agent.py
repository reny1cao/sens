#!/usr/bin/env python3
"""Test single agent query with detailed output."""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Set Railway database URL
os.environ["DATABASE_URL"] = (
    "postgresql://postgres:FFIxLIkNyNeIpdfunHHmhYJSDSudQrZY@turntable.proxy.rlwy.net:13232/railway"
)


async def test_single_query():
    """Test a single query to see what happens."""
    from sens.agents.core import SENSAgent

    print("🧪 Testing SENS Agent with Railway Database")
    print("=" * 60)

    # Create agent with increased iterations
    agent = SENSAgent(max_iterations=5)

    # Test query that requires value discovery
    query = "Show me Apple stock prices"
    print(f"\nQuery: '{query}'")
    print("-" * 60)

    try:
        result = await agent.process_query(query, conversation_id="test_single")

        print("\n📊 Agent Result:")
        print(f"Success: {result.get('success', False)}")
        print(f"SQL: {result.get('sql', 'None')}")
        print(f"Mappings: {result.get('discovered_mappings', {})}")
        print(f"Iterations: {result.get('iterations', 0)}")

        if result.get("data"):
            print(f"\nData rows returned: {len(result['data'])}")
            print("Sample data (first 3 rows):")
            for row in result["data"][:3]:
                print(f"  {row}")

        if result.get("error"):
            print(f"\nError: {result['error']}")

    except Exception as e:
        print(f"Error: {type(e).__name__}: {str(e)}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_single_query())
