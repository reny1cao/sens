#!/usr/bin/env python3
"""Test minimal agent with only generate_sql and execute_sql tools."""

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


async def test_minimal_agent():
    """Test minimal agent with various queries."""
    from sens.agents.core import SENSAgent

    test_queries = [
        "Show me Apple stock prices",
        "What was the average closing price of Tesla in January 2024?",
        "Compare Apple and Microsoft stock prices",
        "Find the highest price for Amazon stock in 2024",
        "Show me all companies in the database",
    ]

    for i, query in enumerate(test_queries, 1):
        print(f"\n{'='*80}")
        print(f"🧪 Test {i}: Minimal Agent")
        print(f"Query: '{query}'")
        print("-" * 80)

        agent = SENSAgent(max_iterations=8)
        result = await agent.process_query(query, conversation_id=f"minimal_{i}")

        print(f"\n📊 Result:")
        print(f"Success: {result.get('success', False)}")
        print(f"Iterations: {result.get('iterations', 0)}")

        # Show reasoning trace
        if result.get("reasoning_trace"):
            print(f"\n🧠 Reasoning Steps:")
            for j, thought in enumerate(result["reasoning_trace"]):
                print(f"{j+1}. {thought.get('content', '')[:150]}...")

        # Show actions
        if result.get("actions_taken"):
            print(f"\n🔧 Actions:")
            for j, action in enumerate(result["actions_taken"]):
                print(f"{j+1}. {action.get('type', 'Unknown')}")

        if result.get("sql"):
            print(f"\n🔍 Generated SQL:")
            print(result.get("sql", "")[:300])
            if len(result.get("sql", "")) > 300:
                print("...")

        if result.get("success") and result.get("result"):
            data = result["result"].get("rows", [])
            print(f"\n📈 Data: {len(data)} rows returned")

        if result.get("error"):
            print(f"\n❌ Error: {result.get('error')}")

        print(f"\n{'-'*40}")


if __name__ == "__main__":
    asyncio.run(test_minimal_agent())
