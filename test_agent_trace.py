#!/usr/bin/env python3
"""Trace agent execution step by step."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


async def test_with_trace():
    from sens.agents.core import SENSAgent

    # Initialize agent with more iterations
    agent = SENSAgent(max_iterations=5)

    query = "Show me recent Apple stock prices"
    print(f"Testing: {query}\n")

    result = await agent.process_query(user_query=query, conversation_id="test_trace")

    print("EXECUTION TRACE:")
    print("-" * 50)

    for i, (thought, action) in enumerate(
        zip(result.get("reasoning_trace", []), result.get("actions_taken", []))
    ):
        print(f"\nStep {i+1}:")
        print(f"Thought: {thought.get('content', '')[:100]}...")
        print(f"Action: {action.get('type')}")
        params = action.get("parameters", {})
        if "schema" in params:
            params = {k: v for k, v in params.items() if k != "schema"}
            params["schema"] = "<schema data>"
        print(f"Params: {params}")

    print("\n" + "-" * 50)
    print(f"Success: {result.get('success')}")
    print(f"Iterations: {result.get('iterations')}")
    print(f"SQL Generated: {'Yes' if result.get('sql') else 'No'}")

    if result.get("sql"):
        print("\nSQL Preview:")
        print(result["sql"][:200] + "...")


if __name__ == "__main__":
    asyncio.run(test_with_trace())
