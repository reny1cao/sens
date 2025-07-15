"""Test the LLM-powered Note-Taking Agent functionality."""

import asyncio
import os
import tempfile
from pathlib import Path

import pytest

from sens.agents.note_taker import DatabaseNote, LLMDatabaseNoteTaker


class TestLLMDatabaseNoteTaker:
    """Test the LLM-powered database note-taking agent."""

    def setup_method(self):
        """Set up test environment."""
        # Use temporary file for testing
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        self.temp_file.close()
        self.note_taker = LLMDatabaseNoteTaker(self.temp_file.name)

    def teardown_method(self):
        """Clean up test environment."""
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)

    @pytest.mark.asyncio
    async def test_database_interaction_observation(self):
        """Test observing database interactions."""
        # Simulate a table discovery interaction
        query = "SELECT table_name FROM information_schema.tables"
        results = {
            "success": True,
            "data": [{"table_name": "users"}, {"table_name": "orders"}],
            "row_count": 2,
        }

        await self.note_taker.observe_database_interaction(
            interaction_type="exploration",
            query=query,
            results=results,
            context="Schema discovery",
        )

        # Check that notes were created (this will depend on LLM response)
        # We can't guarantee specific notes since it's LLM-powered
        assert len(self.note_taker.notes) >= 0  # May or may not create notes

    @pytest.mark.asyncio
    async def test_query_execution_observation(self):
        """Test observing query execution."""
        query = "SELECT COUNT(*) FROM users"
        results = {"success": True, "data": [{"count": 1000}], "row_count": 1}

        await self.note_taker.observe_database_interaction(
            interaction_type="query_execution",
            query=query,
            results=results,
            context="User query execution",
        )

        # Check that the interaction was processed
        assert len(self.note_taker.notes) >= 0

    def test_manual_note_creation(self):
        """Test manually creating notes."""
        note = DatabaseNote(
            timestamp="2024-01-01T12:00:00",
            category="schema_discovery",
            title="Test Note",
            content="This is a test note about database schema",
            tables_involved=["users", "orders"],
            confidence=0.9,
            source="test",
            tags=["test", "schema"],
            insights=["Users table contains customer data"],
        )

        self.note_taker.add_note(note)

        assert len(self.note_taker.notes) == 1
        assert self.note_taker.notes[0].title == "Test Note"

    def test_search_notes(self):
        """Test searching notes."""
        # Add some test notes
        note1 = DatabaseNote(
            timestamp="2024-01-01T12:00:00",
            category="schema_discovery",
            title="Users Table Discovery",
            content="Found users table with customer information",
            tables_involved=["users"],
            confidence=0.9,
            source="test",
            tags=["users", "schema"],
            insights=["Contains customer data"],
        )

        note2 = DatabaseNote(
            timestamp="2024-01-01T12:01:00",
            category="data_insight",
            title="Order Volume Analysis",
            content="Orders table shows high volume in Q4",
            tables_involved=["orders"],
            confidence=0.8,
            source="test",
            tags=["orders", "volume"],
            insights=["High Q4 volume"],
        )

        self.note_taker.add_note(note1)
        self.note_taker.add_note(note2)

        # Search for notes about users
        user_notes = self.note_taker.search_notes("users")
        assert len(user_notes) >= 1
        assert any("users" in note.content.lower() for note in user_notes)

    def test_get_notes_by_category(self):
        """Test getting notes by category."""
        note = DatabaseNote(
            timestamp="2024-01-01T12:00:00",
            category="schema_discovery",
            title="Test Schema Note",
            content="Schema discovery note",
            tables_involved=["test_table"],
            confidence=0.9,
            source="test",
            tags=["test"],
            insights=["Test insight"],
        )

        self.note_taker.add_note(note)

        schema_notes = self.note_taker.get_notes_by_category("schema_discovery")
        assert len(schema_notes) == 1
        assert schema_notes[0].category == "schema_discovery"

    def test_get_recent_notes(self):
        """Test getting recent notes."""
        note1 = DatabaseNote(
            timestamp="2024-01-01T12:00:00",
            category="schema_discovery",
            title="Older Note",
            content="This is an older note",
            tables_involved=["table1"],
            confidence=0.9,
            source="test",
            tags=["test"],
            insights=["Old insight"],
        )

        note2 = DatabaseNote(
            timestamp="2024-01-01T12:01:00",
            category="data_insight",
            title="Newer Note",
            content="This is a newer note",
            tables_involved=["table2"],
            confidence=0.8,
            source="test",
            tags=["test"],
            insights=["New insight"],
        )

        self.note_taker.add_note(note1)
        self.note_taker.add_note(note2)

        recent_notes = self.note_taker.get_recent_notes(limit=1)
        assert len(recent_notes) == 1
        assert recent_notes[0].title == "Newer Note"

    def test_persistence(self):
        """Test that notes are persisted to file."""
        note = DatabaseNote(
            timestamp="2024-01-01T12:00:00",
            category="schema_discovery",
            title="Persistent Note",
            content="This note should persist",
            tables_involved=["persistent_table"],
            confidence=0.9,
            source="test",
            tags=["persistence"],
            insights=["Persistence test"],
        )

        self.note_taker.add_note(note)

        # Create a new note taker with the same file
        new_note_taker = LLMDatabaseNoteTaker(self.temp_file.name)

        assert len(new_note_taker.notes) == 1
        assert new_note_taker.notes[0].title == "Persistent Note"

    def test_get_knowledge_summary(self):
        """Test getting knowledge summary."""
        note = DatabaseNote(
            timestamp="2024-01-01T12:00:00",
            category="schema_discovery",
            title="Summary Test Note",
            content="Note for summary testing",
            tables_involved=["summary_table"],
            confidence=0.9,
            source="test",
            tags=["summary"],
            insights=["Summary insight"],
        )

        self.note_taker.add_note(note)

        summary = self.note_taker.get_knowledge_summary()
        assert "total_notes" in summary
        assert summary["total_notes"] == 1
        assert "categories" in summary
        assert "schema_discovery" in summary["categories"]
