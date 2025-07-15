#!/usr/bin/env python3
"""
Demo script showing the Note-Taking Agent in action.

This demonstrates how the agent takes human-like notes about database discoveries,
similar to how a person would document their learning while exploring a database.
"""

import json
import os
import sys
from pathlib import Path

# Add the src directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sens.agents.note_taker import DatabaseNoteTaker


def demo_database_exploration():
    """Simulate a database exploration session with note-taking."""

    print("🔍 SENS Note-Taking Agent Demo")
    print("=" * 50)
    print("Simulating a database exploration session...")
    print()

    # Create a note taker (will save to demo_notes.json)
    note_taker = DatabaseNoteTaker("demo_notes.json")

    print("📝 Starting fresh exploration...")
    print()

    # Phase 1: Initial Discovery
    print("🔍 Phase 1: Discovering Tables")
    print("-" * 30)

    tables = ["customers", "orders", "products", "order_items", "categories"]
    note_taker.observe_table_discovery(tables, "Initial schema exploration")

    print(f"✅ Discovered {len(tables)} tables: {', '.join(tables)}")
    print(f"📊 Total notes so far: {len(note_taker.notes)}")
    print()

    # Phase 2: Examine Customer Table
    print("🔍 Phase 2: Analyzing Customer Table Structure")
    print("-" * 45)

    customer_columns = [
        {"column_name": "customer_id", "data_type": "integer"},
        {"column_name": "first_name", "data_type": "varchar"},
        {"column_name": "last_name", "data_type": "varchar"},
        {"column_name": "email", "data_type": "varchar"},
        {"column_name": "phone", "data_type": "varchar"},
        {"column_name": "created_at", "data_type": "timestamp"},
        {"column_name": "status", "data_type": "varchar"},
    ]

    note_taker.observe_column_discovery(
        "customers", customer_columns, "Customer table structure analysis"
    )

    print(f"✅ Analyzed customers table with {len(customer_columns)} columns")
    print(
        f"🔑 Key columns identified: {note_taker.table_knowledge['customers'].key_columns}"
    )
    print(f"📊 Total notes so far: {len(note_taker.notes)}")
    print()

    # Phase 3: Sample Customer Data
    print("🔍 Phase 3: Sampling Customer Data")
    print("-" * 35)

    customer_data = [
        {
            "customer_id": 1,
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "status": "ACTIVE",
        },
        {
            "customer_id": 2,
            "first_name": "Jane",
            "last_name": "Smith",
            "email": "jane@example.com",
            "status": "ACTIVE",
        },
        {
            "customer_id": 3,
            "first_name": "Bob",
            "last_name": "Johnson",
            "email": "bob@example.com",
            "status": "INACTIVE",
        },
        {
            "customer_id": 4,
            "first_name": "Alice",
            "last_name": "Brown",
            "email": "alice@example.com",
            "status": "ACTIVE",
        },
    ]

    note_taker.observe_data_sample("customers", customer_data, "Customer data sampling")

    print(f"✅ Sampled {len(customer_data)} customer records")
    patterns = note_taker.table_knowledge["customers"].common_patterns
    print(f"🔍 Data patterns identified: {len(patterns)}")
    for pattern in patterns[:3]:  # Show first 3 patterns
        print(f"   • {pattern}")
    print(f"📊 Total notes so far: {len(note_taker.notes)}")
    print()

    # Phase 4: Execute Queries
    print("🔍 Phase 4: Executing Queries")
    print("-" * 30)

    # Count customers
    note_taker.observe_query_execution(
        "SELECT COUNT(*) FROM customers", 1250, ["customers"], "Customer count query"
    )
    print("✅ Executed: SELECT COUNT(*) FROM customers → 1,250 results")

    # Get active customers
    note_taker.observe_query_execution(
        "SELECT * FROM customers WHERE status = 'ACTIVE'",
        980,
        ["customers"],
        "Active customers query",
    )
    print("✅ Executed: SELECT * FROM customers WHERE status = 'ACTIVE' → 980 results")

    print(f"📊 Total notes so far: {len(note_taker.notes)}")
    print()

    # Phase 5: Discover Relationships
    print("🔍 Phase 5: Discovering Relationships")
    print("-" * 37)

    note_taker.observe_relationship(
        "customers", "orders", "has_many", "Foreign key relationship discovered"
    )
    note_taker.observe_relationship(
        "orders", "order_items", "has_many", "Order items relationship"
    )
    note_taker.observe_relationship(
        "products", "order_items", "has_many", "Product items relationship"
    )

    print("✅ Discovered customer → orders relationship")
    print("✅ Discovered orders → order_items relationship")
    print("✅ Discovered products → order_items relationship")
    print(f"📊 Total notes so far: {len(note_taker.notes)}")
    print()

    # Phase 6: Show Knowledge Summary
    print("📊 Knowledge Summary")
    print("-" * 20)

    summary = note_taker.get_knowledge_summary()
    print(f"📝 Total notes: {summary['total_notes']}")
    print(f"🗂️  Tables discovered: {summary['tables_discovered']}")
    print(f"📋 Tables with details: {summary['tables_with_details']}")
    print(f"🔍 Recent queries: {summary['recent_queries']}")
    print()
    print("📊 Notes by category:")
    for category, count in summary["categories"].items():
        print(f"   • {category.replace('_', ' ').title()}: {count}")
    print()

    # Phase 7: Show Table Knowledge
    print("🏪 Customer Table Knowledge")
    print("-" * 30)

    customer_summary = note_taker.get_table_summary("customers")
    print(customer_summary)
    print()

    # Phase 8: Query Knowledge
    print("🔍 Query Knowledge System")
    print("-" * 27)

    # Search for customer-related notes
    relevant_notes = note_taker.get_relevant_notes("customer email status", limit=3)
    print(f"Found {len(relevant_notes)} relevant notes for 'customer email status':")
    for i, note in enumerate(relevant_notes, 1):
        print(f"{i}. {note.title}")
        print(f"   📝 {note.content[:100]}...")
        print(f"   🏷️  Tags: {', '.join(note.tags[:3])}")
        print()

    # Save notes
    note_taker.save_notes()
    print(f"💾 Notes saved to demo_notes.json")
    print()

    # Show some actual notes
    print("📋 Sample Notes (Human-like Documentation)")
    print("-" * 45)

    for i, note in enumerate(note_taker.notes[:3], 1):
        print(f"{i}. [{note.category.upper()}] {note.title}")
        print(f"   📅 {note.timestamp}")
        print(f"   📝 {note.content}")
        print(f"   🎯 Tables: {', '.join(note.tables_involved)}")
        print(f"   🔍 Source: {note.source}")
        print(f"   ⭐ Confidence: {note.confidence}")
        print()

    print("✨ Demo completed! The note-taking system has:")
    print("   • Observed database discoveries")
    print("   • Recorded table structures and patterns")
    print("   • Tracked query executions")
    print("   • Identified relationships")
    print("   • Organized knowledge for future reference")
    print()
    print("🎯 This knowledge can now be used by the agent to:")
    print("   • Answer questions about the database")
    print("   • Suggest relevant tables for queries")
    print("   • Provide context for SQL generation")
    print("   • Speed up future explorations")


def show_notes_file():
    """Show the contents of the saved notes file."""

    if not os.path.exists("demo_notes.json"):
        print("❌ No notes file found. Run the demo first.")
        return

    print("\n📄 Saved Notes File Structure")
    print("-" * 35)

    with open("demo_notes.json", "r") as f:
        data = json.load(f)

    print(f"📊 File contains:")
    print(f"   • {len(data.get('notes', []))} notes")
    print(f"   • {len(data.get('table_knowledge', {}))} table knowledge entries")
    print(f"   • {len(data.get('discovered_tables', []))} discovered tables")
    print(f"   • {len(data.get('common_queries', []))} common queries")
    print(f"   • Last saved: {data.get('last_saved', 'Unknown')}")
    print()

    # Show structure of a note
    if data.get("notes"):
        print("📝 Sample Note Structure:")
        sample_note = data["notes"][0]
        print(json.dumps(sample_note, indent=2))

    # Show structure of table knowledge
    if data.get("table_knowledge"):
        print("\n🏪 Sample Table Knowledge:")
        table_name = list(data["table_knowledge"].keys())[0]
        table_knowledge = data["table_knowledge"][table_name]
        print(f"Table: {table_name}")
        print(json.dumps(table_knowledge, indent=2))


if __name__ == "__main__":
    # Clean up any existing demo file
    if os.path.exists("demo_notes.json"):
        os.remove("demo_notes.json")

    # Run the demo
    demo_database_exploration()

    # Show the saved file structure
    show_notes_file()

    print("\n🎉 Demo completed successfully!")
    print("💡 The note-taking system provides a simple, human-like way to")
    print("   accumulate and organize database knowledge without complex graphs.")
