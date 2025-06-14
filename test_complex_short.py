#!/usr/bin/env python3
"""Test agent with a few complex queries."""

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


async def test_complex():
    """Test agent with complex queries."""
    from sens.agents.core import SENSAgent

    # Test 1: Time-based comparison
    print("\n" + "=" * 80)
    print("🧪 Test 1: Multi-company comparison with time range")
    query = "Compare Apple and Microsoft stock prices for December 2024"
    print(f"Query: '{query}'")
    print("-" * 80)

    agent = SENSAgent(max_iterations=12)
    result = await agent.process_query(query, conversation_id="complex_1")

    print(f"\nSuccess: {result.get('success', False)}")
    print(f"Iterations: {result.get('iterations', 0)}")

    if result.get("sql"):
        sql = result.get("sql", "")
        print(f"\n🔍 Generated SQL (first 300 chars):")
        print(sql[:300] + "..." if len(sql) > 300 else sql)

    if result.get("discovered_mappings"):
        print(f"\n🗺️ Discovered Mappings:")
        for k, v in result["discovered_mappings"].items():
            print(f"  '{k}' → '{v}'")

    if result.get("success") and result.get("result"):
        data = result["result"].get("rows", [])
        print(f"\n📈 Data: {len(data)} rows returned")
        if data:
            print("Sample rows:")
            for row in data[:3]:
                print(f"  {row}")

    # Test 2: Aggregation query
    print("\n" + "=" * 80)
    print("🧪 Test 2: Aggregation query")
    query = "What was the average closing price of Tesla stock in January 2024?"
    print(f"Query: '{query}'")
    print("-" * 80)

    agent2 = SENSAgent(max_iterations=12)
    result2 = await agent2.process_query(query, conversation_id="complex_2")

    print(f"\nSuccess: {result2.get('success', False)}")
    print(f"Iterations: {result2.get('iterations', 0)}")

    if result2.get("sql"):
        sql = result2.get("sql", "")
        print(f"\n🔍 Generated SQL:")
        print(sql)

    if result2.get("discovered_mappings"):
        print(f"\n🗺️ Discovered Mappings:")
        for k, v in result2["discovered_mappings"].items():
            print(f"  '{k}' → '{v}'")

    if result2.get("success") and result2.get("result"):
        data = result2["result"].get("rows", [])
        print(f"\n📈 Result: {data}")

    # Test 3: Finding extremes
    print("\n" + "=" * 80)
    print("🧪 Test 3: Finding extremes")
    query = "Show me the highest and lowest prices for Amazon stock in 2024"
    print(f"Query: '{query}'")
    print("-" * 80)

    agent3 = SENSAgent(max_iterations=12)
    result3 = await agent3.process_query(query, conversation_id="complex_3")

    print(f"\nSuccess: {result3.get('success', False)}")
    print(f"Iterations: {result3.get('iterations', 0)}")

    if result3.get("sql"):
        print(f"\n🔍 Generated SQL:")
        print(result3.get("sql", ""))

    if result3.get("success") and result3.get("result"):
        data = result3["result"].get("rows", [])
        print(f"\n📈 Result: {data}")


if __name__ == "__main__":
    asyncio.run(test_complex())
