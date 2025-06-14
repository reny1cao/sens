#!/usr/bin/env python3
"""Test agent with simpler AAPL monthly query."""

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


async def test_aapl_monthly():
    """Test agent with simpler monthly AAPL query."""
    from sens.agents.core import SENSAgent

    print("🧪 Testing Simpler AAPL Monthly Query")
    print("=" * 80)

    # Simpler query focusing just on monthly averages
    query = "Show me the average closing price of AAPL by month for 2024"
    print(f"Query: '{query}'")
    print("-" * 80)

    agent = SENSAgent(max_iterations=10)
    result = await agent.process_query(query, conversation_id="aapl_monthly")

    print(f"\n📊 Final Result:")
    print(f"Success: {result.get('success', False)}")
    print(f"Iterations: {result.get('iterations', 0)}")

    if result.get("sql"):
        print(f"\n🔍 Generated SQL:")
        print(result.get("sql", ""))

    if result.get("success") and result.get("result"):
        data = result["result"].get("rows", [])
        print(f"\n📈 Data: {len(data)} rows")
        if data:
            print("\nMonthly averages:")
            for row in data:
                print(f"  {row}")

    if result.get("error"):
        print(f"\n❌ Error: {result.get('error')}")


if __name__ == "__main__":
    asyncio.run(test_aapl_monthly())
