#!/usr/bin/env python3
"""Test simpler AAPL query to check SQL generation."""

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


async def test_simple_aapl():
    """Test a simpler AAPL query to verify SQL generation works."""
    from sens.agents.core import SENSAgent

    # Simple query that should work
    query = "Show me AAPL closing prices for the last 10 days"

    print(f"🧪 Testing Simple AAPL Query:")
    print(f"'{query}'")
    print("=" * 80)

    agent = SENSAgent(max_iterations=8)
    result = await agent.process_query(query, conversation_id="simple_aapl")

    print(f"\n📊 Final Result:")
    print(f"Success: {result.get('success', False)}")
    print(f"Iterations: {result.get('iterations', 0)}")

    if result.get("sql"):
        print(f"\n🔍 Generated SQL:")
        print(result.get("sql"))

    if result.get("success") and result.get("result"):
        data = result["result"].get("rows", [])
        print(f"\n📈 Data: {len(data)} rows returned")
        if data:
            print("Sample rows:")
            for i, row in enumerate(data[:3]):
                print(f"  {i+1}: {row}")

    if result.get("error"):
        print(f"\n❌ Error: {result.get('error')}")

    # Show only last few reasoning steps
    print(f"\n🧠 Final Reasoning Steps:")
    if result.get("reasoning_trace"):
        for i, thought in enumerate(result["reasoning_trace"][-3:]):
            print(f"{i+1}. {thought.get('content', '')[:100]}...")


if __name__ == "__main__":
    asyncio.run(test_simple_aapl())
