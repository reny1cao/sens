#!/usr/bin/env python3
"""Test agent with helpful hints about the database structure."""

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


async def test_with_hints():
    """Test agent with database structure hints."""
    from sens.agents.core import SENSAgent

    print("🧪 Testing Agent with Database Hints")
    print("=" * 60)

    # Create agent
    agent = SENSAgent(max_iterations=8)

    # Test with a clear hint about where to look
    query = """Show me Apple stock prices.
    Hint: Company names are in the securities table, and price data is in the daily_prices table (not the partitioned tables)."""

    print(f"Query: '{query}'")
    print("-" * 60)

    result = await agent.process_query(query, conversation_id="test_hint")

    print(f"\nSuccess: {result.get('success', False)}")
    print(f"SQL: {result.get('sql', 'None')}")
    print(f"Mappings: {result.get('discovered_mappings', {})}")
    print(f"Iterations: {result.get('iterations', 0)}")

    # Show key actions
    if result.get("actions_taken"):
        print("\nKey Actions:")
        for action in result.get("actions_taken", []):
            action_type = action.get("type", "Unknown")
            if action_type in ["explore_database", "generate_sql", "execute_sql"]:
                params = action.get("parameters", {})
                if "query" in params:
                    print(f"  - {action_type}: {params['query'][:100]}...")
                else:
                    print(f"  - {action_type}")

    # If successful, show some data
    if result.get("data"):
        print(f"\nData returned: {len(result.get('data', []))} rows")
        if result["data"]:
            print("Sample (first 3 rows):")
            for row in result["data"][:3]:
                print(f"  {row}")


if __name__ == "__main__":
    asyncio.run(test_with_hints())
