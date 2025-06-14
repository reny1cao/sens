#!/usr/bin/env python3
"""Test single query with minimal agent."""

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
    """Test a single query with detailed logging."""
    from sens.agents.core import SENSAgent

    query = "Show me Apple stock prices"

    print(f"🧪 Testing: '{query}'")
    print("=" * 80)

    agent = SENSAgent(max_iterations=6)
    result = await agent.process_query(query, conversation_id="single_test")

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

    # Show detailed reasoning
    print(f"\n🧠 Detailed Reasoning:")
    if result.get("reasoning_trace"):
        for i, thought in enumerate(result["reasoning_trace"]):
            print(f"{i+1:2d}. {thought.get('content', '')}")

    # Show action sequence
    print(f"\n🔧 Action Sequence:")
    if result.get("actions_taken"):
        for i, action in enumerate(result["actions_taken"]):
            action_type = action.get("type", "Unknown")
            params = action.get("parameters", {})
            if action_type == "explore_database" and "query" in params:
                print(f"{i+1:2d}. {action_type}: {params['query'][:60]}...")
            else:
                print(f"{i+1:2d}. {action_type}")


if __name__ == "__main__":
    asyncio.run(test_single_query())
