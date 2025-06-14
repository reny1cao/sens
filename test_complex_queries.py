#!/usr/bin/env python3
"""Test agent with complex queries."""

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


async def test_complex_queries():
    """Test agent with various complex queries."""
    from sens.agents.core import SENSAgent

    # Complex queries to test
    queries = [
        # 1. Multi-company comparison with time range
        "Compare Apple and Microsoft stock prices for the last 6 months",
        # 2. Aggregation query
        "What was the average closing price of Tesla stock in 2024?",
        # 3. Finding extremes
        "Show me the highest and lowest prices for Amazon stock this year",
        # 4. Pattern finding
        "Which tech stocks have increased by more than 20% this year?",
        # 5. Volume analysis
        "Find the top 5 days with highest trading volume for Apple",
        # 6. Recent data query
        "What are the latest prices for all FAANG stocks?",
        # 7. Volatility query
        "Show me stocks with the highest price volatility in the last month",
    ]

    # Test each query
    for i, query in enumerate(queries, 1):
        print(f"\n{'='*80}")
        print(f"🧪 Test {i}: Complex Query")
        print(f"Query: '{query}'")
        print("-" * 80)

        agent = SENSAgent(max_iterations=15)  # More iterations for complex queries

        try:
            result = await agent.process_query(query, conversation_id=f"complex_{i}")

            print(f"\n📊 Result:")
            print(f"Success: {result.get('success', False)}")
            print(f"Iterations: {result.get('iterations', 0)}")

            if result.get("sql"):
                print(f"\n🔍 Generated SQL:")
                # Show first 200 chars of SQL
                sql = result.get("sql", "")
                if len(sql) > 200:
                    print(f"{sql[:200]}...")
                else:
                    print(sql)

            if result.get("discovered_mappings"):
                print(f"\n🗺️ Discovered Mappings:")
                for user_term, db_value in result["discovered_mappings"].items():
                    print(f"  '{user_term}' → '{db_value}'")

            # Show key reasoning steps
            if result.get("reasoning_trace"):
                print(f"\n🧠 Key Reasoning Steps:")
                key_thoughts = [
                    t
                    for t in result["reasoning_trace"]
                    if "discover" in t.get("content", "").lower()
                    or "found" in t.get("content", "").lower()
                    or "generate" in t.get("content", "").lower()
                ]
                for thought in key_thoughts[:3]:  # Show up to 3 key thoughts
                    print(f"  - {thought.get('content', '')[:100]}...")

            # Show data summary if successful
            if result.get("success") and result.get("result"):
                data = result["result"].get("rows", [])
                print(f"\n📈 Data Summary:")
                print(f"  Rows returned: {len(data)}")
                if data:
                    print(f"  Sample row: {data[0]}")

            # Show errors if any
            if result.get("error"):
                print(f"\n❌ Error: {result.get('error')}")

        except Exception as e:
            print(f"\n⚠️ Exception: {str(e)}")

        # Brief pause between tests
        await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(test_complex_queries())
