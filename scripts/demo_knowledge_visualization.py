#!/usr/bin/env python3

"""
Demo script for the Knowledge Visualization System.

This script demonstrates how the LLM-powered note-taking system works
and shows how the visualization components display the knowledge.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add the src directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sens.agents.note_taker import DatabaseNote, LLMDatabaseNoteTaker


async def demo_knowledge_visualization():
    """Demonstrate the knowledge visualization system."""

    print("🎨 SENS Knowledge Visualization System Demo")
    print("=" * 60)
    print("This demo shows how the LLM-powered note-taking system")
    print("generates knowledge that can be visualized in the web interface.")
    print()

    # Create a note taker
    note_taker = LLMDatabaseNoteTaker("demo_visualization_notes.json")

    print("📝 Creating sample knowledge notes...")
    print()

    # Create some sample notes that would be generated during database exploration
    sample_notes = [
        DatabaseNote(
            timestamp="2024-01-15T10:30:00Z",
            category="schema_discovery",
            title="Financial Database Schema Identified",
            content="Discovered a comprehensive financial database with loan, account, and transaction tables. The schema follows a relational pattern with clear foreign key relationships.",
            tables_involved=["loan", "account", "trans", "client"],
            confidence=0.95,
            source="exploration",
            tags=["schema", "financial", "relationships"],
            insights=[
                "Well-normalized database structure",
                "Clear entity relationships",
                "Suitable for financial analysis",
            ],
        ),
        DatabaseNote(
            timestamp="2024-01-15T11:15:00Z",
            category="data_insight",
            title="Loan Distribution Analysis",
            content="Analysis reveals 682 loans in the database with varying amounts and statuses. Most loans appear to be concentrated in specific regions with distinct patterns.",
            tables_involved=["loan", "district"],
            confidence=0.88,
            source="query_execution",
            tags=["loans", "distribution", "regional", "patterns"],
            insights=[
                "Regional loan concentration identified",
                "Status distribution shows clear patterns",
                "Amount ranges vary by geographic location",
            ],
        ),
        DatabaseNote(
            timestamp="2024-01-15T12:00:00Z",
            category="relationship",
            title="Account-Transaction Relationship Mapping",
            content="Strong relationship identified between account and transaction tables. Each transaction is linked to exactly one account, following standard banking practices with referential integrity.",
            tables_involved=["account", "trans"],
            confidence=0.92,
            source="exploration",
            tags=["relationship", "banking", "transactions", "integrity"],
            insights=[
                "One-to-many relationship confirmed",
                "Referential integrity maintained",
                "Standard banking data model",
            ],
        ),
        DatabaseNote(
            timestamp="2024-01-15T14:30:00Z",
            category="query_pattern",
            title="Common Query Patterns Identified",
            content="Detected recurring query patterns involving joins between account, loan, and district tables. Users frequently analyze loan data by geographic region.",
            tables_involved=["account", "loan", "district"],
            confidence=0.85,
            source="query_analysis",
            tags=["patterns", "joins", "geographic", "analysis"],
            insights=[
                "Geographic analysis is common use case",
                "Multi-table joins are frequent",
                "Performance optimization opportunities exist",
            ],
        ),
        DatabaseNote(
            timestamp="2024-01-15T15:45:00Z",
            category="performance",
            title="Database Performance Characteristics",
            content="Database shows good performance for most queries. Large transaction table (>1M rows) may benefit from indexing on date and account_id columns.",
            tables_involved=["trans"],
            confidence=0.78,
            source="performance_analysis",
            tags=["performance", "indexing", "optimization"],
            insights=[
                "Transaction table is performance bottleneck",
                "Date-based queries are common",
                "Index recommendations available",
            ],
        ),
    ]

    # Add notes to the system
    for note in sample_notes:
        note_taker.add_note(note)
        print(f"✅ Created note: {note.title}")
        print(f"   Category: {note.category}")
        print(f"   Confidence: {note.confidence:.0%}")
        print(f"   Tables: {', '.join(note.tables_involved)}")
        print()

    # Save the notes
    note_taker.save_notes()

    print("📊 Knowledge Summary:")
    print("-" * 30)
    summary = note_taker.get_knowledge_summary()
    print(f"Total Notes: {summary['total_notes']}")
    print(f"Categories: {list(summary['categories'].keys())}")
    print(f"Tables Covered: {len(note_taker.table_knowledge)}")
    print()

    print("🎯 Key Insights Generated:")
    print("-" * 30)
    all_insights = []
    for note in sample_notes:
        all_insights.extend(note.insights)

    for i, insight in enumerate(all_insights[:5], 1):
        print(f"{i}. {insight}")
    print()

    print("🌐 Visualization Features:")
    print("-" * 30)
    print("The web interface provides:")
    print("• Interactive knowledge note browser")
    print("• Real-time monitoring of note creation")
    print("• Category-based filtering and search")
    print("• Confidence level visualization")
    print("• Table relationship mapping")
    print("• Insight trend analysis")
    print()

    print("🚀 Access the visualization at:")
    print("   http://localhost:3000/knowledge")
    print("   http://localhost:3000/knowledge/dashboard")
    print()

    print("📈 Real-time Features:")
    print("• Live event stream showing note creation")
    print("• Confidence scoring in real-time")
    print("• Table discovery monitoring")
    print("• LLM analysis progress tracking")
    print()

    # Show sample API response format
    print("🔌 API Response Format:")
    print("-" * 30)
    api_response = {
        "notes": [note.__dict__ for note in sample_notes[:2]],
        "table_knowledge": dict(note_taker.table_knowledge),
        "stats": summary,
    }
    print(json.dumps(api_response, indent=2, default=str)[:500] + "...")
    print()

    print("✨ Demo completed successfully!")
    print("The knowledge visualization system is ready to use.")
    print()
    print("🎨 Features demonstrated:")
    print("• LLM-powered note creation")
    print("• Structured knowledge storage")
    print("• Multi-category organization")
    print("• Confidence-based insights")
    print("• Real-time visualization support")

    # Clean up
    import os

    if os.path.exists("demo_visualization_notes.json"):
        os.remove("demo_visualization_notes.json")
        print("\n🧹 Cleaned up demo files")


if __name__ == "__main__":
    asyncio.run(demo_knowledge_visualization())
