#!/usr/bin/env python3

"""
Demo script showing the integrated LLM-powered note-taking system.

This demonstrates how the note-taking system works with the unified agent
to maintain organized database knowledge without KuzuDB.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the src directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sens.agents.note_taker import DatabaseNote, LLMDatabaseNoteTaker
from sens.agents.tools import AgentTools
from sens.memory import SimpleAgentMemory, SimpleAgentMemoryTools


async def demo_integrated_note_taking():
    """Demonstrate the integrated note-taking system."""

    print("🤖 SENS Integrated Note-Taking System Demo")
    print("=" * 60)
    print("Demonstrating LLM-powered note-taking with simple file-based memory...")
    print()

    # Initialize the simple memory system
    print("1. Initializing simple memory system...")
    memory = SimpleAgentMemory(db_path="demo_memory.json")
    memory_tools = SimpleAgentMemoryTools(memory)

    # Initialize the note-taking system
    print("2. Initializing LLM-powered note-taking system...")
    note_taker = LLMDatabaseNoteTaker("demo_notes.json")

    # Initialize agent tools with note-taking
    print("3. Initializing agent tools with note-taking integration...")
    tools = AgentTools()

    print("✅ All systems initialized successfully!")
    print()

    # Demonstrate note creation
    print("4. Creating sample database knowledge notes...")

    # Sample database discovery notes
    schema_note = DatabaseNote(
        timestamp="2024-01-01T12:00:00",
        category="schema_discovery",
        title="Financial Database Schema Discovered",
        content="Found financial database with key tables: accounts, transactions, loans, districts. The accounts table appears to be the central entity with relationships to other tables.",
        tables_involved=["accounts", "transactions", "loans", "districts"],
        confidence=0.95,
        source="exploration",
        tags=["schema", "financial", "database"],
        insights=[
            "Accounts table is central to the schema",
            "Strong relationships between accounts and transactions",
            "District-based geographical organization",
        ],
    )

    data_pattern_note = DatabaseNote(
        timestamp="2024-01-01T12:01:00",
        category="data_insight",
        title="Account Distribution Pattern",
        content="Observed that accounts are distributed across 77 districts with varying concentrations. Higher account density in urban districts.",
        tables_involved=["accounts", "districts"],
        confidence=0.88,
        source="query_execution",
        tags=["data_pattern", "distribution", "geography"],
        insights=[
            "77 districts total in the dataset",
            "Urban districts have higher account density",
            "Geographic distribution affects financial patterns",
        ],
    )

    query_pattern_note = DatabaseNote(
        timestamp="2024-01-01T12:02:00",
        category="query_pattern",
        title="Common Financial Query Pattern",
        content="Successful pattern for counting financial entities: SELECT COUNT(*) FROM table_name. Works consistently across accounts, loans, and transactions tables.",
        tables_involved=["accounts", "loans", "transactions"],
        confidence=0.92,
        source="query_execution",
        tags=["sql_pattern", "counting", "financial"],
        insights=[
            "COUNT(*) is reliable for all financial tables",
            "No NULL handling needed for primary counts",
            "Consistent table structure across financial entities",
        ],
    )

    # Add notes to the system
    note_taker.add_note(schema_note)
    note_taker.add_note(data_pattern_note)
    note_taker.add_note(query_pattern_note)

    print(f"✅ Created {len(note_taker.notes)} database knowledge notes")
    print()

    # Demonstrate memory storage
    print("5. Storing patterns in simple memory system...")

    # Store a concept in memory
    concept_result = await memory_tools.remember_concept(
        name="financial_database_schema",
        description="Core financial database with accounts, transactions, loans, and districts",
        business_terms=[
            "accounts",
            "transactions",
            "loans",
            "districts",
            "financial_data",
        ],
        database_mapping={
            "primary_tables": ["accounts", "transactions", "loans", "districts"],
            "relationships": [
                "accounts->transactions",
                "accounts->loans",
                "districts->accounts",
            ],
            "key_metrics": ["account_count", "transaction_volume", "loan_amounts"],
        },
        context={"database_type": "financial", "domain": "banking"},
    )

    # Store a successful pattern
    pattern_result = await memory_tools.remember_pattern(
        name="financial_count_pattern",
        trigger_phrase="how many",
        sql_template="SELECT COUNT(*) FROM {table_name}",
        tables_used=["accounts", "loans", "transactions"],
        success_context={
            "works_for": ["accounts", "loans", "transactions", "districts"],
            "reliability": "high",
            "response_time": "fast",
        },
        context={"database_type": "financial", "pattern_type": "counting"},
    )

    print(f"✅ Memory storage results:")
    print(f"   - Concept storage: {'✅' if concept_result.success else '❌'}")
    print(f"   - Pattern storage: {'✅' if pattern_result.success else '❌'}")
    print()

    # Demonstrate knowledge retrieval
    print("6. Demonstrating knowledge retrieval...")

    # Search notes
    print("   Searching notes for 'accounts'...")
    account_notes = note_taker.search_notes("accounts")
    print(f"   Found {len(account_notes)} notes about accounts")

    # Get knowledge context
    print("   Getting knowledge context for 'financial database'...")
    context = tools.get_knowledge_context("financial database")
    print(f"   Context length: {len(context)} characters")

    # Recall from memory
    print("   Recalling from memory...")
    recall_result = await memory_tools.recall_knowledge(
        query="financial database structure", limit=3
    )
    print(f"   Recalled {len(recall_result.data.get('memories', []))} memories")
    print()

    # Demonstrate integration
    print("7. Demonstrating system integration...")

    # Show how the systems work together
    print("   Note-taking system stats:")
    summary = note_taker.get_knowledge_summary()
    print(f"   - Total notes: {summary['total_notes']}")
    print(f"   - Categories: {list(summary['categories'].keys())}")
    print(f"   - Tables covered: {len(note_taker.table_knowledge)} tables")

    print("   Memory system stats:")
    memory_stats = await memory_tools.get_memory_stats()
    if memory_stats.success:
        stats = memory_stats.data
        print(f"   - Total memories: {stats['total_memories']}")
        print(f"   - Memory types: {list(stats['memories_by_type'].keys())}")
        print(f"   - Average confidence: {stats['avg_confidence']:.2f}")

    print()
    print("🎉 Demo completed successfully!")
    print()
    print("Key Benefits:")
    print("✅ No KuzuDB dependency - simple file-based storage")
    print("✅ LLM-powered intelligent note categorization")
    print("✅ Seamless integration with agent tools")
    print("✅ Persistent knowledge across sessions")
    print("✅ Fast retrieval and search capabilities")
    print()

    # Cleanup
    print("Cleaning up demo files...")
    try:
        os.unlink("demo_memory.json")
        os.unlink("demo_notes.json")
        print("✅ Demo files cleaned up")
    except FileNotFoundError:
        pass


if __name__ == "__main__":
    asyncio.run(demo_integrated_note_taking())
