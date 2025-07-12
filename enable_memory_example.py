#!/usr/bin/env python3
"""
Example: Enable Memory in Current Agent Pipeline
Shows how to integrate memory-enhanced agent with minimal changes
"""

import asyncio
from pathlib import Path

from sens.agents.memory_enhanced_core import MemoryEnhancedAgent
from sens.agents.reasoning import ReasoningEngine
from sens.agents.tool_registry import EvaluationContext, tool_registry
from sens.memory import AgentMemory, AgentMemoryTools


async def run_memory_enhanced_example():
    """Example of running memory-enhanced agent on BIRD query"""

    print("🧠 Memory-Enhanced Agent Example")
    print("=" * 50)

    # Database setup
    db_path = "external/BIRD-SQL-DEV/dev_databases/california_schools/california_schools.sqlite"

    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        return

    # Initialize memory system
    memory = AgentMemory(db_path="example_memory.db")
    memory_tools = AgentMemoryTools(memory)

    print("✅ Memory system initialized")

    # Initialize tools for BIRD SQL Dev context
    tool_config = tool_registry.get_tools_for_context(
        EvaluationContext.BIRD_SQL_DEV, db_path=db_path
    )
    tools = tool_config["tools"]

    print("✅ Context-aware tools initialized")

    # Initialize reasoning engine
    reasoning_engine = ReasoningEngine()

    # Create memory-enhanced agent
    agent = MemoryEnhancedAgent(
        tools=tools,
        memory_tools=memory_tools,
        reasoning_engine=reasoning_engine,
        max_iterations=5,
    )

    print("✅ Memory-enhanced agent created")
    print()

    # Test queries that show memory learning
    test_queries = [
        "How many charter schools are there?",
        "What are the phone numbers of charter schools?",
        "List charter schools with their opening dates",
        "How many total schools are in the database?",
    ]

    for i, query in enumerate(test_queries, 1):
        print(f"🔍 Query {i}: {query}")
        print("-" * 40)

        # Get memory stats before
        stats_before = await memory_tools.get_memory_stats()
        memory_count_before = (
            stats_before.data.get("total_memories", 0) if stats_before.success else 0
        )

        # Process query
        start_time = asyncio.get_event_loop().time()
        result = await agent.process_query(query, f"session_{i}")
        end_time = asyncio.get_event_loop().time()

        # Get memory stats after
        stats_after = await memory_tools.get_memory_stats()
        memory_count_after = (
            stats_after.data.get("total_memories", 0) if stats_after.success else 0
        )

        # Results
        print(f"📊 Result: {result.get('status', 'unknown')}")
        print(
            f"🧠 Memory: {memory_count_before} → {memory_count_after} (+{memory_count_after - memory_count_before})"
        )
        print(f"⏱️  Time: {end_time - start_time:.2f}s")
        print(f"🔄 Iterations: {result.get('iterations', 'unknown')}")

        if result.get("success") and result.get("result"):
            print(f"📈 Rows: {result['result'].get('row_count', 0)}")

            # Show sample data
            if result["result"].get("data"):
                print("📋 Sample data:")
                for row in result["result"]["data"][:2]:
                    print(f"   {row}")

        print()

        # Small delay to see memory effects
        await asyncio.sleep(1)

    # Final memory analysis
    print("🧠 Final Memory Analysis")
    print("=" * 30)

    final_stats = await memory_tools.get_memory_stats()
    if final_stats.success:
        stats = final_stats.data
        print(f"📊 Total memories: {stats['total_memories']}")
        print(f"🔗 Total relationships: {stats['total_relationships']}")
        print(f"📈 Memory types:")
        for mem_type, count in stats["memories_by_type"].items():
            print(f"   - {mem_type}: {count}")

        print(f"⚡ Performance:")
        perf = stats["performance"]
        print(f"   - Avg query time: {perf['avg_query_time']:.2f}ms")
        print(f"   - Queries executed: {perf['queries_executed']}")

    # Show learned memories
    print("\n🧠 Learned Memories:")
    all_memories = await memory_tools.recall_knowledge("", limit=10)
    if all_memories.success:
        for memory in all_memories.data["memories"]:
            print(f"   🎯 {memory['type'].upper()}: {memory['name']}")
            print(
                f"      Used: {memory['usage_count']} times | Success: {memory['success_rate']:.1%}"
            )

    print("\n🎉 Memory-enhanced agent example complete!")
    print("The agent has learned patterns and will be faster on similar queries.")

    # Cleanup
    memory.close()


if __name__ == "__main__":
    asyncio.run(run_memory_enhanced_example())
