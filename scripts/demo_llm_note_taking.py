#!/usr/bin/env python3

"""
Demo script showing the LLM-powered Note-Taking Agent in action.

This demonstrates how the agent uses LLMs to intelligently analyze database
interactions and generate human-like notes about discoveries.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the src directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sens.agents.note_taker import LLMDatabaseNoteTaker


async def demo_llm_note_taking():
    """Simulate database exploration with LLM-powered note-taking."""

    print("🤖 SENS LLM-Powered Note-Taking Agent Demo")
    print("=" * 60)
    print("Simulating intelligent database exploration with LLM analysis...")
    print()

    # Create a note taker (will save to demo_llm_notes.json)
    note_taker = LLMDatabaseNoteTaker("demo_llm_notes.json")

    # Simulate various database interactions
    interactions = [
        {
            "type": "exploration",
            "query": "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'",
            "results": {
                "data": [
                    {"table_name": "users"},
                    {"table_name": "orders"},
                    {"table_name": "products"},
                    {"table_name": "order_items"},
                    {"table_name": "categories"},
                ],
                "columns": ["table_name"],
            },
            "context": "Initial database schema discovery",
        },
        {
            "type": "exploration",
            "query": "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'users'",
            "results": {
                "data": [
                    {"column_name": "id", "data_type": "integer"},
                    {"column_name": "email", "data_type": "varchar"},
                    {"column_name": "first_name", "data_type": "varchar"},
                    {"column_name": "last_name", "data_type": "varchar"},
                    {"column_name": "created_at", "data_type": "timestamp"},
                    {"column_name": "last_login", "data_type": "timestamp"},
                ],
                "columns": ["column_name", "data_type"],
            },
            "context": "Examining user table structure",
        },
        {
            "type": "query_execution",
            "query": "SELECT COUNT(*) as total_users FROM users",
            "results": {"data": [{"total_users": 15420}], "columns": ["total_users"]},
            "context": "Getting user count for analysis",
        },
        {
            "type": "query_execution",
            "query": "SELECT * FROM users WHERE created_at > '2024-01-01' LIMIT 5",
            "results": {
                "data": [
                    {
                        "id": 1001,
                        "email": "john@example.com",
                        "first_name": "John",
                        "last_name": "Doe",
                        "created_at": "2024-02-15",
                        "last_login": "2024-07-10",
                    },
                    {
                        "id": 1002,
                        "email": "jane@company.org",
                        "first_name": "Jane",
                        "last_name": "Smith",
                        "created_at": "2024-03-20",
                        "last_login": "2024-07-11",
                    },
                    {
                        "id": 1003,
                        "email": "bob@startup.io",
                        "first_name": "Bob",
                        "last_name": "Wilson",
                        "created_at": "2024-04-05",
                        "last_login": "2024-07-09",
                    },
                ],
                "columns": [
                    "id",
                    "email",
                    "first_name",
                    "last_name",
                    "created_at",
                    "last_login",
                ],
            },
            "context": "Sampling recent user data",
        },
        {
            "type": "exploration",
            "query": "SELECT o.id, u.email, o.total_amount FROM orders o JOIN users u ON o.user_id = u.id LIMIT 3",
            "results": {
                "data": [
                    {"id": 5001, "email": "john@example.com", "total_amount": 89.99},
                    {"id": 5002, "email": "jane@company.org", "total_amount": 156.50},
                    {"id": 5003, "email": "bob@startup.io", "total_amount": 45.00},
                ],
                "columns": ["id", "email", "total_amount"],
            },
            "context": "Exploring relationship between users and orders",
        },
    ]

    print("🔍 Processing database interactions with LLM analysis...")
    print()

    # Process each interaction
    for i, interaction in enumerate(interactions, 1):
        print(f"📝 Interaction {i}: {interaction['type']}")
        print(
            f"   Query: {interaction['query'][:80]}{'...' if len(interaction['query']) > 80 else ''}"
        )

        # Let the LLM analyze the interaction
        await note_taker.observe_database_interaction(
            interaction_type=interaction["type"],
            query=interaction["query"],
            results=interaction["results"],
            context=interaction["context"],
        )

        print(f"   ✅ Analyzed and processed")
        print()

    # Show the accumulated knowledge
    print("📚 ACCUMULATED KNOWLEDGE")
    print("=" * 40)

    summary = note_taker.get_knowledge_summary()
    print(f"📊 Total notes: {summary['total_notes']}")
    print(f"🗂️  Tables discovered: {summary['tables_discovered']}")
    print(f"🎯 Average confidence: {summary['avg_confidence']:.2f}")
    print()

    if summary["categories"]:
        print("📋 Note categories:")
        for category, count in summary["categories"].items():
            print(f"   • {category}: {count} notes")
        print()

    # Show recent notes
    recent_notes = note_taker.get_recent_notes(3)
    if recent_notes:
        print("📝 Recent discoveries:")
        for note in recent_notes:
            print(f"   • {note.title} (confidence: {note.confidence:.2f})")
            print(
                f"     {note.content[:100]}{'...' if len(note.content) > 100 else ''}"
            )
            if note.insights:
                print(f"     💡 Insights: {', '.join(note.insights[:2])}")
            print()

    # Show table knowledge
    print("🗃️  TABLE KNOWLEDGE")
    print("=" * 30)
    for table_name in summary["tables"]:
        table_summary = note_taker.get_table_summary(table_name)
        print(f"📊 Table: {table_name}")
        if table_summary.get("description"):
            print(f"   Description: {table_summary['description']}")
        if table_summary.get("purpose"):
            print(f"   Purpose: {table_summary['purpose']}")
        if table_summary.get("data_patterns"):
            print(f"   Patterns: {', '.join(table_summary['data_patterns'][:2])}")
        print()

    # Generate LLM summary
    print("🤖 LLM ANALYSIS SUMMARY")
    print("=" * 35)
    try:
        llm_summary = await note_taker.get_knowledge_summary_with_llm()
        print(llm_summary)
    except Exception as e:
        print(f"Could not generate LLM summary: {e}")

    print()
    print("✨ Demo completed! Notes saved to demo_llm_notes.json")
    print("   The LLM has intelligently analyzed the database interactions")
    print("   and generated human-like insights about the data structure.")


if __name__ == "__main__":
    asyncio.run(demo_llm_note_taking())
