#!/usr/bin/env python3
"""Test agent with Amazon query - detailed logs."""

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


async def test_amazon():
    """Test agent with Amazon query."""
    from sens.agents.core import SENSAgent

    print("🧪 Testing Amazon Stock Query")
    print("=" * 80)
    query = "Show me the highest and lowest prices for Amazon stock in 2024"
    print(f"Query: '{query}'")
    print("-" * 80)

    agent = SENSAgent(max_iterations=12)
    result = await agent.process_query(query, conversation_id="amazon_test")

    print(f"\n📊 Final Result:")
    print(f"Success: {result.get('success', False)}")
    print(f"Iterations: {result.get('iterations', 0)}")

    # Show ALL reasoning steps
    print("\n🧠 Complete Agent Steps:")
    print("=" * 80)

    if result.get("reasoning_trace"):
        for i, thought in enumerate(result["reasoning_trace"]):
            print(f"\n{i+1}. THOUGHT: {thought.get('content', 'No content')}")

    if result.get("actions_taken"):
        for i, action in enumerate(result["actions_taken"]):
            print(f"\n{i+1}. ACTION: {action.get('type', 'Unknown')}")
            params = action.get("parameters", {})
            if params:
                if "query" in params and isinstance(params["query"], str):
                    # Show SQL queries in full
                    print(f"   SQL: {params['query']}")
                else:
                    # Show other parameters
                    for k, v in params.items():
                        if k == "schema":
                            print(
                                f"   {k}: <schema with {len(v.get('tables', []))} tables>"
                            )
                        else:
                            print(f"   {k}: {v}")

    if result.get("sql"):
        print(f"\n🔍 Final Generated SQL:")
        print(result.get("sql", ""))

    if result.get("discovered_mappings"):
        print(f"\n🗺️ Discovered Mappings:")
        for k, v in result["discovered_mappings"].items():
            print(f"  '{k}' → '{v}'")

    if result.get("success") and result.get("result"):
        data = result["result"].get("rows", [])
        print(f"\n📈 Result: {data}")


if __name__ == "__main__":
    asyncio.run(test_amazon())
