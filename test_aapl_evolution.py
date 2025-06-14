#!/usr/bin/env python3
"""Test agent with complex AAPL evolution query."""

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


async def test_aapl_evolution():
    """Test agent with AAPL price evolution query."""
    from sens.agents.core import SENSAgent

    print("🧪 Testing AAPL Price Evolution Query")
    print("=" * 80)
    query = "How has the average closing price of AAPL evolved monthly over the past two years, and how does it correlate with changes in trading volume?"
    print(f"Query: '{query}'")
    print("-" * 80)

    agent = SENSAgent(max_iterations=15)  # More iterations for complex query
    result = await agent.process_query(query, conversation_id="aapl_evolution")

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
        print("\n🔧 Actions Taken:")
        for i, action in enumerate(result["actions_taken"]):
            print(f"\n{i+1}. ACTION: {action.get('type', 'Unknown')}")
            params = action.get("parameters", {})
            if params:
                if (
                    "query" in params
                    and isinstance(params["query"], str)
                    and len(params["query"]) > 100
                ):
                    # Truncate long SQL queries
                    print(f"   Query/SQL: {params['query'][:200]}...")
                elif "query" in params:
                    print(f"   Query: {params['query']}")
                elif "sql" in params and len(params.get("sql", "")) > 100:
                    print(f"   SQL: {params['sql'][:200]}...")
                else:
                    # Show other parameters
                    for k, v in params.items():
                        if k == "schema":
                            print(
                                f"   {k}: <schema with {len(v.get('tables', []))} tables>"
                            )
                        else:
                            print(f"   {k}: {str(v)[:100]}")

    if result.get("sql"):
        print(f"\n🔍 Final Generated SQL:")
        print("-" * 80)
        print(result.get("sql", ""))

    if result.get("discovered_mappings"):
        print(f"\n🗺️ Discovered Mappings:")
        for k, v in result["discovered_mappings"].items():
            print(f"  '{k}' → '{v}'")

    if result.get("success") and result.get("result"):
        data = result["result"].get("rows", [])
        print(f"\n📈 Data Summary:")
        print(f"Rows returned: {len(data)}")
        if data and len(data) > 0:
            print("\nFirst 5 rows:")
            for row in data[:5]:
                print(f"  {row}")
            if len(data) > 5:
                print(f"  ... ({len(data) - 5} more rows)")

    if result.get("error"):
        print(f"\n❌ Error: {result.get('error')}")


if __name__ == "__main__":
    asyncio.run(test_aapl_evolution())
