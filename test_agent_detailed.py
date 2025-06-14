#!/usr/bin/env python3
"""Detailed agent test to observe full behavior with increased iterations."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


async def test_agent_detailed():
    """Test agent with detailed logging of each step."""
    from sens.agents.core import SENSAgent

    # Initialize agent with more iterations
    agent = SENSAgent(max_iterations=6)

    # Test query
    query = "Show me recent Apple stock prices"
    print("=" * 80)
    print(f"🚀 TESTING AGENT WITH QUERY: '{query}'")
    print("=" * 80)

    try:
        result = await agent.process_query(
            user_query=query, conversation_id="test_detailed"
        )

        print("\n" + "=" * 80)
        print("📊 FINAL RESULT")
        print("=" * 80)
        print(f"✅ Success: {result.get('success')}")
        print(f"📝 SQL Generated: {'Yes' if result.get('sql') else 'No'}")
        print(f"🔄 Iterations Used: {result.get('iterations')}")
        print(f"🗺️ Discovered Mappings: {result.get('discovered_mappings') or 'None'}")

        if result.get("sql"):
            print(f"\n📄 GENERATED SQL:")
            print("-" * 40)
            print(result["sql"])
            print("-" * 40)

        if result.get("result"):
            print(f"\n📊 QUERY RESULT:")
            print(f"Rows returned: {result['result'].get('row_count', 0)}")
            if result["result"].get("rows"):
                print("Sample data:")
                for i, row in enumerate(result["result"]["rows"][:3]):
                    print(f"  Row {i+1}: {row}")

        print("\n" + "=" * 80)
        print("🧠 REASONING TRACE (Step by Step)")
        print("=" * 80)

        if result.get("reasoning_trace"):
            for i, thought in enumerate(result["reasoning_trace"]):
                print(f"\n🔹 Step {i+1}:")
                print(f"   Thought: {thought.get('content', 'No content')}")
                print(f"   Time: {thought.get('timestamp', 'Unknown')}")

        print("\n" + "=" * 80)
        print("⚡ ACTIONS TAKEN")
        print("=" * 80)

        if result.get("actions_taken"):
            for i, action in enumerate(result["actions_taken"]):
                print(f"\n🔸 Action {i+1}: {action.get('type', 'Unknown')}")
                print(f"   Time: {action.get('timestamp', 'Unknown')}")
                params = action.get("parameters", {})
                if params:
                    print("   Parameters:")
                    for key, value in params.items():
                        if isinstance(value, dict) and len(str(value)) > 100:
                            print(f"     - {key}: <large dict with {len(value)} keys>")
                        elif isinstance(value, list) and len(str(value)) > 100:
                            print(f"     - {key}: <list with {len(value)} items>")
                        else:
                            print(f"     - {key}: {value}")

        # Analyze the flow
        print("\n" + "=" * 80)
        print("📈 AGENT BEHAVIOR ANALYSIS")
        print("=" * 80)

        action_types = [a.get("type") for a in result.get("actions_taken", [])]
        print(f"Action sequence: {' → '.join(action_types)}")

        if "SEARCH_SCHEMA" in action_types:
            schema_count = action_types.count("SEARCH_SCHEMA")
            print(f"- Schema searches: {schema_count}")

        if "GENERATE_SQL" in action_types:
            print(f"- SQL generation attempted: Yes")

        if "EXECUTE_SQL" in action_types:
            print(f"- SQL execution attempted: Yes")
        else:
            print(f"- SQL execution attempted: No (likely hit iteration limit)")

        if "SEARCH_VALUES" in action_types or "FIND_SIMILAR_VALUES" in action_types:
            print(f"- Value discovery used: Yes")
        else:
            print(f"- Value discovery used: No")

    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {str(e)}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    print("🔧 Starting detailed agent test...")
    asyncio.run(test_agent_detailed())
