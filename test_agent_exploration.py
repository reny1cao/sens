#!/usr/bin/env python3
"""Test agent with database exploration capabilities."""

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


async def test_exploration():
    """Test agent's ability to explore and discover."""
    from sens.agents.core import SENSAgent

    print("🧪 Testing Agent Database Exploration")
    print("=" * 60)

    # Create agent with more iterations
    agent = SENSAgent(max_iterations=10)

    # Test 1: Direct exploration hint
    print("\n📊 Test 1: Agent with exploration hint")
    query = "Show me Apple stock prices. Check the securities table for company names if needed."
    print(f"Query: '{query}'")
    print("-" * 60)

    result = await agent.process_query(query, conversation_id="test_explore_1")

    print(f"\nSuccess: {result.get('success', False)}")
    print(f"SQL: {result.get('sql', 'None')}")
    print(f"Mappings: {result.get('discovered_mappings', {})}")
    print(f"Iterations: {result.get('iterations', 0)}")

    # Print reasoning trace
    if result.get("reasoning_trace"):
        print("\nReasoning Trace:")
        for i, thought in enumerate(result["reasoning_trace"]):
            print(f"{i+1}. {thought.get('content', 'No content')}")

    # Print actions taken
    if result.get("actions_taken"):
        print("\nActions Taken:")
        for i, action in enumerate(result["actions_taken"]):
            print(
                f"{i+1}. {action.get('type', 'Unknown')} - {action.get('parameters', {})}"
            )

    # Test 2: Let agent figure it out
    print("\n\n📊 Test 2: Agent without hints")
    query2 = "What's Microsoft stock price today?"
    print(f"Query: '{query2}'")
    print("-" * 60)

    result2 = await agent.process_query(query2, conversation_id="test_explore_2")

    print(f"\nSuccess: {result2.get('success', False)}")
    print(f"SQL: {result2.get('sql', 'None')}")
    print(f"Mappings: {result2.get('discovered_mappings', {})}")

    # Test 3: Check if agent learned
    print("\n\n📊 Test 3: Testing learned mappings")
    query3 = "Show me Apple and Microsoft stock comparison"
    print(f"Query: '{query3}'")
    print("-" * 60)

    result3 = await agent.process_query(query3, conversation_id="test_explore_3")

    print(f"\nSuccess: {result3.get('success', False)}")
    print(f"Mappings used: {result3.get('discovered_mappings', {})}")


if __name__ == "__main__":
    asyncio.run(test_exploration())
