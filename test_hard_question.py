#!/usr/bin/env python3
"""Test the hard question that previously failed."""

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


async def test_hard_question():
    """Test the complex correlation question that previously failed."""
    from sens.agents.core import SENSAgent

    # The hard question that caused failure before
    query = "How has the average closing price of AAPL evolved monthly over the past two years, and how does it correlate with changes in trading volume?"

    print(f"🧪 Testing Hard Question:")
    print(f"'{query}'")
    print("=" * 100)

    agent = SENSAgent(max_iterations=10)  # Give it more iterations for complex query
    result = await agent.process_query(query, conversation_id="hard_test")

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
            print("First few rows:")
            for i, row in enumerate(data[:5]):
                print(f"  {i+1}: {row}")

    if result.get("error"):
        print(f"\n❌ Error: {result.get('error')}")

    # Show key reasoning steps
    print(f"\n🧠 Key Reasoning Steps:")
    if result.get("reasoning_trace"):
        for i, thought in enumerate(
            result["reasoning_trace"][-8:]
        ):  # Show last 8 steps
            print(f"{i+1:2d}. {thought.get('content', '')[:120]}...")

    # Show action progression
    print(f"\n🔧 Action Progression:")
    if result.get("actions_taken"):
        for i, action in enumerate(result["actions_taken"]):
            action_type = action.get("type", "Unknown")
            if action_type == "explore_database":
                params = action.get("parameters", {})
                query_snippet = params.get("query", "")[:50]
                print(f"{i+1:2d}. {action_type}: {query_snippet}...")
            else:
                print(f"{i+1:2d}. {action_type}")

    # Show discovered mappings
    if result.get("discovered_mappings"):
        print(f"\n🗺️  Discovered Mappings:")
        for k, v in result["discovered_mappings"].items():
            print(f"   '{k}' → '{v}'")


if __name__ == "__main__":
    asyncio.run(test_hard_question())
