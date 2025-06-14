#!/usr/bin/env python3
"""Test agent without any hints - raw behavior."""

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


async def test_raw():
    """Test agent's raw behavior without hints."""
    from sens.agents.core import SENSAgent

    print("🧪 Testing Agent Raw Behavior (No Hints)")
    print("=" * 60)

    # Create agent with more iterations to see full behavior
    agent = SENSAgent(max_iterations=10)

    # Simple query - no hints
    query = "Show me Apple stock prices"
    print(f"Query: '{query}'")
    print("-" * 60)

    result = await agent.process_query(query, conversation_id="test_raw")

    print(f"\n📊 Final Result:")
    print(f"Success: {result.get('success', False)}")
    print(f"SQL: {result.get('sql', 'None')}")
    print(f"Mappings: {result.get('discovered_mappings', {})}")
    print(f"Iterations: {result.get('iterations', 0)}")

    # Print ALL reasoning steps
    print("\n🧠 Complete Reasoning Trace:")
    if result.get("reasoning_trace"):
        for i, thought in enumerate(result["reasoning_trace"]):
            print(f"\n{i+1}. {thought.get('content', 'No content')}")

    # Print ALL actions taken
    print("\n🔧 Complete Action Sequence:")
    if result.get("actions_taken"):
        for i, action in enumerate(result["actions_taken"]):
            action_type = action.get("type", "Unknown")
            params = action.get("parameters", {})
            print(f"\n{i+1}. ACTION: {action_type}")
            print(f"   PARAMETERS: {params}")

    # Show final data if any
    if result.get("data"):
        print(f"\n📈 Data returned: {len(result.get('data', []))} rows")
    else:
        print(f"\n❌ No data returned")

    # Show error if any
    if result.get("error"):
        print(f"\n⚠️ Error: {result.get('error')}")


if __name__ == "__main__":
    asyncio.run(test_raw())
