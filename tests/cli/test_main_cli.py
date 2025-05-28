"""Tests for the main CLI entry point."""

import argparse
import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from sens.cli.main import (
    create_parser,
    handle_chat,
    handle_execute,
    handle_nl2sql,
    handle_performance,
    handle_validate,
    main,
    setup_logging,
)


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    settings = MagicMock()
    settings.logging.level = "INFO"
    settings.logging.format = "json"
    settings.environment = "test"
    settings.schema_path = Path("/tmp/schema.json")
    return settings


@pytest.fixture
def mock_logger():
    """Mock logger for testing."""
    return MagicMock()


class TestSetupLogging:
    """Test logging setup."""

    def test_setup_logging_default(self, mock_settings):
        """Test default logging setup."""
        with patch("sens.cli.main.get_settings", return_value=mock_settings):
            with patch("sens.cli.main.configure_logging") as mock_configure:
                logger = setup_logging(verbose=False)

                mock_configure.assert_called_once()
                assert logger is not None

    def test_setup_logging_verbose(self, mock_settings):
        """Test verbose logging setup."""
        with patch("sens.cli.main.get_settings", return_value=mock_settings):
            with patch("sens.cli.main.configure_logging") as mock_configure:
                with patch("sens.cli.main.reload_settings") as mock_reload:
                    logger = setup_logging(verbose=True)

                    # Should update settings with DEBUG level
                    mock_reload.assert_called_once()
                    assert logger is not None


class TestHandleNL2SQL:
    """Test NL2SQL command handler."""

    def test_nl2sql_with_question(self, mock_logger):
        """Test NL2SQL with direct question."""
        args = argparse.Namespace(
            question="How many users do we have?",
            interactive=False,
            json=False,
            verbose=False,
            validate=True,
            explain=False,
        )

        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = {
            "success": True,
            "sql": "SELECT COUNT(*) FROM users",
            "confidence": 0.95,
            "tables_used": ["users"],
            "intent": {"type": "aggregate", "confidence": 0.95},
        }

        with patch("sens.cli.main.EnhancedNL2SQLPipeline", return_value=mock_pipeline):
            with patch("sens.cli.main.format_nl2sql_response") as mock_format:
                with patch("builtins.print") as mock_print:
                    handle_nl2sql(args, mock_logger)

                    mock_pipeline.run.assert_called_once_with(
                        "How many users do we have?", validate=True, explain=False
                    )
                    mock_format.assert_called_once()

    def test_nl2sql_interactive_mode(self, mock_logger):
        """Test NL2SQL in interactive mode."""
        args = argparse.Namespace(
            question=None,
            interactive=True,
            json=False,
            verbose=False,
            validate=True,
            explain=False,
        )

        # Mock interactive input
        mock_inputs = ["What is the total revenue?", "exit"]

        with patch("builtins.input", side_effect=mock_inputs):
            with patch("sens.cli.main.EnhancedNL2SQLPipeline") as mock_pipeline_class:
                mock_pipeline = MagicMock()
                mock_pipeline.run.return_value = {
                    "success": True,
                    "sql": "SELECT SUM(amount) FROM orders",
                    "confidence": 0.92,
                }
                mock_pipeline_class.return_value = mock_pipeline

                with patch("builtins.print"):
                    handle_nl2sql(args, mock_logger)

                    # Should process first question
                    mock_pipeline.run.assert_called_with(
                        "What is the total revenue?", validate=True, explain=False
                    )

    def test_nl2sql_json_output(self, mock_logger):
        """Test NL2SQL with JSON output."""
        args = argparse.Namespace(
            question="Show all products",
            interactive=False,
            json=True,
            verbose=False,
            validate=False,
            explain=False,
        )

        mock_pipeline = MagicMock()
        mock_response = {
            "success": True,
            "sql": "SELECT * FROM products",
            "confidence": 0.98,
            "tables_used": ["products"],
        }
        mock_pipeline.run.return_value = mock_response

        with patch("sens.cli.main.EnhancedNL2SQLPipeline", return_value=mock_pipeline):
            with patch("builtins.print") as mock_print:
                handle_nl2sql(args, mock_logger)

                # Should print JSON
                printed_output = mock_print.call_args[0][0]
                assert json.loads(printed_output) == mock_response

    def test_nl2sql_error_handling(self, mock_logger):
        """Test NL2SQL error handling."""
        args = argparse.Namespace(
            question="Invalid query",
            interactive=False,
            json=False,
            verbose=False,
            validate=True,
            explain=False,
        )

        mock_pipeline = MagicMock()
        mock_pipeline.run.side_effect = Exception("Pipeline error")

        with patch("sens.cli.main.EnhancedNL2SQLPipeline", return_value=mock_pipeline):
            with patch("sys.exit") as mock_exit:
                handle_nl2sql(args, mock_logger)

                mock_logger.error.assert_called_with(
                    "nl2sql_failed", error="Pipeline error"
                )
                mock_exit.assert_called_with(1)


class TestHandleExecute:
    """Test SQL execution command handler."""

    def test_execute_direct_sql(self, mock_logger):
        """Test executing SQL directly."""
        args = argparse.Namespace(
            sql="SELECT * FROM users LIMIT 5", file=None, json=False
        )

        mock_executor = MagicMock()
        mock_result = MagicMock()
        mock_result.error = None
        mock_result.columns = ["id", "name", "email"]
        mock_result.rows = [
            [1, "Alice", "alice@example.com"],
            [2, "Bob", "bob@example.com"],
        ]
        mock_result.row_count = 2
        mock_executor.execute.return_value = mock_result

        with patch("sens.cli.main.SQLExecutor", return_value=mock_executor):
            with patch("builtins.print") as mock_print:
                handle_execute(args, mock_logger)

                mock_executor.execute.assert_called_once_with(
                    "SELECT * FROM users LIMIT 5"
                )
                # Should print tabulated output
                assert any("Alice" in str(call) for call in mock_print.call_args_list)

    def test_execute_from_file(self, mock_logger, tmp_path):
        """Test executing SQL from file."""
        sql_file = tmp_path / "query.sql"
        sql_file.write_text("SELECT COUNT(*) FROM orders")

        args = argparse.Namespace(sql=None, file=str(sql_file), json=False)

        mock_executor = MagicMock()
        mock_result = MagicMock()
        mock_result.error = None
        mock_result.columns = ["count"]
        mock_result.rows = [[42]]
        mock_result.row_count = 1
        mock_executor.execute.return_value = mock_result

        with patch("sens.cli.main.SQLExecutor", return_value=mock_executor):
            with patch("builtins.print"):
                handle_execute(args, mock_logger)

                mock_executor.execute.assert_called_once_with(
                    "SELECT COUNT(*) FROM orders"
                )

    def test_execute_json_output(self, mock_logger):
        """Test executing SQL with JSON output."""
        args = argparse.Namespace(
            sql="SELECT id, name FROM products", file=None, json=True
        )

        mock_executor = MagicMock()
        mock_result = MagicMock()
        mock_result.error = None
        mock_result.columns = ["id", "name"]
        mock_result.rows = [[1, "Product A"], [2, "Product B"]]
        mock_result.row_count = 2
        mock_executor.execute.return_value = mock_result

        with patch("sens.cli.main.SQLExecutor", return_value=mock_executor):
            with patch("builtins.print") as mock_print:
                handle_execute(args, mock_logger)

                # Should print JSON
                printed_output = mock_print.call_args[0][0]
                parsed = json.loads(printed_output)
                assert parsed["columns"] == ["id", "name"]
                assert parsed["rows"] == [[1, "Product A"], [2, "Product B"]]
                assert parsed["row_count"] == 2

    def test_execute_error(self, mock_logger):
        """Test execution error handling."""
        args = argparse.Namespace(sql="INVALID SQL", file=None, json=False)

        mock_executor = MagicMock()
        mock_result = MagicMock()
        mock_result.error = "Syntax error near 'INVALID'"
        mock_executor.execute.return_value = mock_result

        with patch("sens.cli.main.SQLExecutor", return_value=mock_executor):
            with patch("builtins.print") as mock_print:
                with patch("sys.exit") as mock_exit:
                    handle_execute(args, mock_logger)

                    # Should print error and exit
                    assert any(
                        "Syntax error" in str(call)
                        for call in mock_print.call_args_list
                    )
                    mock_exit.assert_called_with(1)


class TestHandleValidate:
    """Test SQL validation command handler."""

    def test_validate_valid_sql(self, mock_logger):
        """Test validating valid SQL."""
        args = argparse.Namespace(
            sql="SELECT * FROM users WHERE id = 1", file=None, level="full", json=False
        )

        mock_validator = MagicMock()
        mock_validator.validate.return_value = MagicMock(
            is_valid=True, errors=[], warnings=[], level="full"
        )

        with patch("sens.cli.main.SQLValidator", return_value=mock_validator):
            with patch("builtins.print") as mock_print:
                handle_validate(args, mock_logger)

                # Should print success message
                assert any("Valid" in str(call) for call in mock_print.call_args_list)

    def test_validate_invalid_sql(self, mock_logger):
        """Test validating invalid SQL."""
        args = argparse.Namespace(
            sql="DELETE FROM users", file=None, level="safety", json=False
        )

        mock_validator = MagicMock()
        mock_validator.validate.return_value = MagicMock(
            is_valid=False,
            errors=["DELETE operations are not allowed"],
            warnings=[],
            level="safety",
        )

        with patch("sens.cli.main.SQLValidator", return_value=mock_validator):
            with patch("builtins.print") as mock_print:
                with patch("sys.exit") as mock_exit:
                    handle_validate(args, mock_logger)

                    # Should print errors and exit
                    assert any(
                        "DELETE operations" in str(call)
                        for call in mock_print.call_args_list
                    )
                    mock_exit.assert_called_with(1)

    def test_validate_with_warnings(self, mock_logger):
        """Test validation with warnings."""
        args = argparse.Namespace(
            sql="SELECT * FROM large_table", file=None, level="performance", json=False
        )

        mock_validator = MagicMock()
        mock_validator.validate.return_value = MagicMock(
            is_valid=True,
            errors=[],
            warnings=["Query may return large result set"],
            level="performance",
        )

        with patch("sens.cli.main.SQLValidator", return_value=mock_validator):
            with patch("builtins.print") as mock_print:
                handle_validate(args, mock_logger)

                # Should print warnings
                assert any("Warning" in str(call) for call in mock_print.call_args_list)


class TestHandleChat:
    """Test chat command handler."""

    def test_chat_start(self, mock_logger):
        """Test starting chat session."""
        args = argparse.Namespace(session_id=None, list=False, clear=False)

        mock_session_manager = MagicMock()
        mock_session = MagicMock()
        mock_session.session_id = "test-session-123"
        mock_session_manager.get_or_create_session.return_value = mock_session

        mock_orchestrator = MagicMock()
        mock_orchestrator.run_interactive_session = MagicMock()

        with patch("sens.cli.main.SessionManager", return_value=mock_session_manager):
            with patch(
                "sens.cli.main.ChatOrchestrator", return_value=mock_orchestrator
            ):
                handle_chat(args, mock_logger)

                mock_orchestrator.run_interactive_session.assert_called_once()

    def test_chat_list_sessions(self, mock_logger):
        """Test listing chat sessions."""
        args = argparse.Namespace(session_id=None, list=True, clear=False)

        mock_session_manager = MagicMock()
        mock_sessions = [
            {"session_id": "123", "created_at": "2024-01-01", "message_count": 5},
            {"session_id": "456", "created_at": "2024-01-02", "message_count": 3},
        ]
        mock_session_manager.list_sessions.return_value = mock_sessions

        with patch("sens.cli.main.SessionManager", return_value=mock_session_manager):
            with patch("builtins.print") as mock_print:
                handle_chat(args, mock_logger)

                # Should print session list
                assert any("123" in str(call) for call in mock_print.call_args_list)
                assert any("456" in str(call) for call in mock_print.call_args_list)

    def test_chat_clear_sessions(self, mock_logger):
        """Test clearing chat sessions."""
        args = argparse.Namespace(session_id=None, list=False, clear=True)

        mock_session_manager = MagicMock()

        with patch("sens.cli.main.SessionManager", return_value=mock_session_manager):
            with patch("builtins.input", return_value="y"):
                with patch("builtins.print"):
                    handle_chat(args, mock_logger)

                    mock_session_manager.clear_all_sessions.assert_called_once()


class TestMainFunction:
    """Test main entry point."""

    def test_main_no_args(self):
        """Test main with no arguments."""
        with patch("sys.argv", ["sens"]):
            with patch("sens.cli.main.create_parser") as mock_create:
                mock_parser = MagicMock()
                mock_parser.parse_args.return_value = argparse.Namespace(
                    command=None, verbose=False
                )
                mock_create.return_value = mock_parser

                with patch("builtins.print") as mock_print:
                    main()

                    # Should show help
                    mock_parser.print_help.assert_called_once()

    def test_main_nl2sql_command(self):
        """Test main with nl2sql command."""
        with patch("sys.argv", ["sens", "nl2sql", "-q", "Test query"]):
            with patch("sens.cli.main.setup_logging") as mock_setup:
                mock_logger = MagicMock()
                mock_setup.return_value = mock_logger

                with patch("sens.cli.main.handle_nl2sql") as mock_handle:
                    main()

                    mock_handle.assert_called_once()
                    args = mock_handle.call_args[0][0]
                    assert args.question == "Test query"

    def test_main_unknown_command(self):
        """Test main with unknown command."""
        with patch("sys.argv", ["sens", "unknown"]):
            with patch("sens.cli.main.setup_logging") as mock_setup:
                mock_logger = MagicMock()
                mock_setup.return_value = mock_logger

                with patch("sys.exit") as mock_exit:
                    main()

                    mock_logger.error.assert_called_with(
                        "unknown_command", command="unknown"
                    )
                    mock_exit.assert_called_with(1)

    def test_main_config_command(self):
        """Test main with config command."""
        with patch("sys.argv", ["sens", "config", "get", "api_key"]):
            with patch("sens.cli.main.setup_logging") as mock_setup:
                mock_logger = MagicMock()
                mock_setup.return_value = mock_logger

                with patch("sens.cli.main.handle_config_command") as mock_handle:
                    main()

                    mock_handle.assert_called_once()
                    args = mock_handle.call_args[0][0]
                    assert args.config_command == "get"
                    assert args.key == "api_key"

    def test_create_parser(self):
        """Test parser creation."""
        parser = create_parser()

        # Test nl2sql command
        args = parser.parse_args(["nl2sql", "-q", "Test"])
        assert args.command == "nl2sql"
        assert args.question == "Test"

        # Test execute command
        args = parser.parse_args(["execute", "-s", "SELECT 1"])
        assert args.command == "execute"
        assert args.sql == "SELECT 1"

        # Test validate command
        args = parser.parse_args(["validate", "-s", "SELECT 1", "--level", "syntax"])
        assert args.command == "validate"
        assert args.sql == "SELECT 1"
        assert args.level == "syntax"

        # Test chat command
        args = parser.parse_args(["chat", "--list"])
        assert args.command == "chat"
        assert args.list is True
