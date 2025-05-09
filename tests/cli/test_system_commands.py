"""Tests for system-related CLI commands."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sens.cli.commands.system import (
    SystemStatus,
    handle_debug,
    handle_metrics,
    handle_status,
)


@pytest.fixture
def mock_settings():
    """Mock settings."""
    with patch("sens.cli.commands.system.get_settings") as mock:
        settings = MagicMock()
        settings.schema_path = Path("/tmp/schema.json")
        settings.index_dir = Path("/tmp/indices")
        settings.db_url = "postgresql://user:pass@localhost:5432/db"
        mock.return_value = settings
        yield settings


@pytest.fixture
def mock_schema_graph():
    """Mock schema graph."""
    with patch("sens.cli.commands.system.SchemaGraph") as mock:
        instance = MagicMock()
        instance.list_all_tables.return_value = ["users", "orders"]
        mock.get_instance.return_value = instance
        yield instance


@pytest.fixture
def mock_orchestrator():
    """Mock ChatOrchestrator."""
    with patch("sens.cli.commands.system.ChatOrchestrator") as mock:
        instance = MagicMock()
        mock.return_value = instance
        yield instance


class TestSystemStatus:
    """Test SystemStatus class."""

    def test_check_schema_exists(self, mock_settings, mock_schema_graph, tmp_path):
        """Test schema check when schema exists."""
        schema_file = tmp_path / "schema.json"
        schema_file.write_text("{}")
        mock_settings.schema_path = schema_file

        status = SystemStatus()
        result = status.check_schema()

        assert result["exists"] is True
        assert result["table_count"] == 2
        assert "users" in result["tables"]
        assert "orders" in result["tables"]

    def test_check_schema_not_exists(self, mock_settings):
        """Test schema check when schema doesn't exist."""
        mock_settings.schema_path = Path("/nonexistent/schema.json")

        status = SystemStatus()
        result = status.check_schema()

        assert result["exists"] is False
        assert "table_count" not in result

    def test_check_indices(self, mock_settings):
        """Test indices check."""
        with patch("sens.cli.commands.system.TokenIndexBuilder") as mock_token:
            with patch("sens.cli.commands.system.EmbeddingSearch") as mock_embedding:
                token_instance = MagicMock()
                token_instance.index = None
                mock_token.return_value = token_instance

                embedding_instance = MagicMock()
                embedding_instance.index = True
                mock_embedding.return_value = embedding_instance

                status = SystemStatus()
                result = status.check_indices()

                assert result["token_index"]["ready"] is False
                assert result["embedding_index"]["ready"] is True

    def test_check_database(self, mock_settings):
        """Test database check."""
        with patch("sens.cli.commands.system.SQLExecutor") as mock_executor:
            instance = MagicMock()
            instance.execute.return_value.error = None
            mock_executor.return_value = instance

            status = SystemStatus()
            result = status.check_database()

            assert result["connected"] is True
            assert "localhost" in result["url"]


class TestDebugCommand:
    """Test debug command handler."""

    def test_debug_conversation(self, mock_orchestrator, capsys):
        """Test debugging a conversation."""
        state = MagicMock()
        state.interactions = [
            MagicMock(
                user_input="How many users?",
                intent=MagicMock(query_type="SELECT", confidence=0.9, tables=["users"]),
                response={"status": "success", "summary": "Found 10 users"},
            )
        ]
        mock_orchestrator.return_value.state = state

        args = MagicMock(conversation_id="test-123", component=None)
        handle_debug(args)

        captured = capsys.readouterr()
        assert "Conversation test-123" in captured.out
        assert "How many users?" in captured.out
        assert "Found 10 users" in captured.out

    def test_debug_component(self, mock_settings, capsys):
        """Test debugging a specific component."""
        args = MagicMock(conversation_id=None, component="schema")
        handle_debug(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "exists" in output
        assert "path" in output


class TestMetricsCommand:
    """Test metrics command handler."""

    def test_conversation_metrics(self, mock_orchestrator, capsys):
        """Test showing metrics for a conversation."""
        state = MagicMock()
        state.interactions = [
            MagicMock(
                response={
                    "metadata": {
                        "pipeline_metrics": {
                            "success": True,
                            "total_duration_ms": 1000.0,
                            "steps": [{"name": "step1"}],
                        }
                    }
                }
            )
        ]
        mock_orchestrator.return_value.state = state

        args = MagicMock(conversation_id="test-123", detailed=True)
        handle_metrics(args)

        captured = capsys.readouterr()
        assert "Metrics for conversation test-123" in captured.out
        assert "1000.00ms" in captured.out
        assert "Successful: 1/1" in captured.out


class TestStatusCommand:
    """Test status command handler."""

    def test_status_json(self, mock_settings, capsys):
        """Test status command with JSON output."""
        args = MagicMock(json=True)
        handle_status(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert "schema" in output
        assert "indices" in output
        assert "database" in output
        assert "settings" in output

    def test_status_human_readable(self, mock_settings, capsys):
        """Test status command with human-readable output."""
        args = MagicMock(json=False)
        handle_status(args)

        captured = capsys.readouterr()
        assert "Sens System Status" in captured.out
        assert "Schema:" in captured.out
        assert "Database:" in captured.out
