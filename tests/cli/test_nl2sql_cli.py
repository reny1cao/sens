"""Tests for the NL2SQL CLI module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sens.cli.nl2sql import (
    NL2SQLContext,
    NL2SQLHandler,
    get_multiline_input,
    handle_special_command,
    run_interactive_session,
)


@pytest.fixture
def mock_context():
    """Create a mock NL2SQL context."""
    ctx = MagicMock(spec=NL2SQLContext)
    ctx.pipeline = MagicMock()
    ctx.logger = MagicMock()
    ctx.settings = MagicMock()
    ctx.session_manager = MagicMock()
    ctx.current_session = MagicMock()
    ctx.history = []
    ctx.metrics = {}
    return ctx


@pytest.fixture
def nl2sql_handler(mock_context):
    """Create NL2SQL handler with mock context."""
    return NL2SQLHandler(mock_context)


class TestNL2SQLContext:
    """Test NL2SQL context initialization."""

    def test_context_initialization(self):
        """Test creating NL2SQL context."""
        with patch("sens.cli.nl2sql.EnhancedNL2SQLPipeline") as mock_pipeline:
            with patch("sens.cli.nl2sql.get_settings") as mock_settings:
                with patch("sens.cli.nl2sql.SessionManager") as mock_session:
                    context = NL2SQLContext()

                    assert context.pipeline is not None
                    assert context.logger is not None
                    assert context.settings is not None
                    assert context.session_manager is not None
                    assert context.history == []
                    assert context.metrics == {}

    def test_context_with_session(self):
        """Test context with existing session."""
        mock_session = MagicMock()
        mock_session.session_id = "test-123"

        with patch("sens.cli.nl2sql.EnhancedNL2SQLPipeline"):
            with patch("sens.cli.nl2sql.get_settings"):
                with patch("sens.cli.nl2sql.SessionManager") as mock_session_mgr:
                    mock_session_mgr.return_value.get_session.return_value = (
                        mock_session
                    )

                    context = NL2SQLContext(session_id="test-123")
                    assert context.current_session == mock_session


class TestGetMultilineInput:
    """Test multiline input handling."""

    def test_single_line_input(self):
        """Test single line input."""
        with patch("builtins.input", return_value="SELECT * FROM users"):
            result = get_multiline_input()
            assert result == "SELECT * FROM users"

    def test_multiline_input(self):
        """Test multiline input with \\\\."""
        inputs = ["SELECT * \\", "FROM users \\", "WHERE active = true"]

        with patch("builtins.input", side_effect=inputs):
            result = get_multiline_input()
            assert result == "SELECT * FROM users WHERE active = true"

    def test_empty_input(self):
        """Test empty input."""
        with patch("builtins.input", return_value=""):
            result = get_multiline_input()
            assert result == ""

    def test_input_with_special_chars(self):
        """Test input with special characters."""
        with patch("builtins.input", return_value="What's the avg(price) for items?"):
            result = get_multiline_input()
            assert result == "What's the avg(price) for items?"


class TestHandleSpecialCommand:
    """Test special command handling."""

    def test_help_command(self):
        """Test help command."""
        with patch("builtins.print") as mock_print:
            result = handle_special_command(".help")

            assert result is True
            # Should print help text
            assert any(
                "Available commands" in str(call) for call in mock_print.call_args_list
            )

    def test_history_command(self, mock_context):
        """Test history command."""
        mock_context.history = [
            {"query": "Test 1", "sql": "SELECT 1"},
            {"query": "Test 2", "sql": "SELECT 2"},
        ]

        with patch("builtins.print") as mock_print:
            result = handle_special_command(".history", mock_context)

            assert result is True
            # Should print history
            assert any("Test 1" in str(call) for call in mock_print.call_args_list)
            assert any("Test 2" in str(call) for call in mock_print.call_args_list)

    def test_clear_command(self):
        """Test clear command."""
        with patch("os.system") as mock_system:
            result = handle_special_command(".clear")

            assert result is True
            mock_system.assert_called_once()

    def test_metrics_command(self, mock_context):
        """Test metrics command."""
        mock_context.metrics = {
            "total_queries": 10,
            "success_rate": 0.9,
            "avg_response_time": 0.5,
        }

        with patch("builtins.print") as mock_print:
            result = handle_special_command(".metrics", mock_context)

            assert result is True
            # Should print metrics
            assert any(
                "total_queries" in str(call) for call in mock_print.call_args_list
            )

    def test_unknown_command(self):
        """Test unknown special command."""
        result = handle_special_command(".unknown")
        assert result is False

    def test_regular_input(self):
        """Test non-special command input."""
        result = handle_special_command("SELECT * FROM users")
        assert result is False


class TestNL2SQLHandler:
    """Test NL2SQL handler methods."""

    def test_process_query_success(self, nl2sql_handler, mock_context):
        """Test successful query processing."""
        mock_context.pipeline.run.return_value = {
            "success": True,
            "sql": "SELECT COUNT(*) FROM users",
            "confidence": 0.95,
            "tables_used": ["users"],
            "intent": {"type": "aggregate"},
        }

        result = nl2sql_handler.process_query("How many users?")

        assert result["success"] is True
        assert result["sql"] == "SELECT COUNT(*) FROM users"
        mock_context.pipeline.run.assert_called_once_with(
            "How many users?", validate=True, explain=False
        )

    def test_process_query_failure(self, nl2sql_handler, mock_context):
        """Test query processing failure."""
        mock_context.pipeline.run.return_value = {
            "success": False,
            "error": "Failed to understand query",
            "confidence": 0.2,
        }

        result = nl2sql_handler.process_query("Invalid query")

        assert result["success"] is False
        assert "error" in result

    def test_process_query_with_history(self, nl2sql_handler, mock_context):
        """Test query processing with history tracking."""
        mock_context.pipeline.run.return_value = {
            "success": True,
            "sql": "SELECT * FROM products",
            "confidence": 0.98,
        }

        result = nl2sql_handler.process_query("Show all products")

        assert len(mock_context.history) == 1
        assert mock_context.history[0]["query"] == "Show all products"
        assert mock_context.history[0]["sql"] == "SELECT * FROM products"

    def test_format_response_success(self, nl2sql_handler):
        """Test formatting successful response."""
        response = {
            "success": True,
            "sql": "SELECT * FROM users",
            "confidence": 0.95,
            "tables_used": ["users"],
        }

        with patch("builtins.print") as mock_print:
            nl2sql_handler.format_response(response)

            # Should print SQL and confidence
            assert any(
                "SELECT * FROM users" in str(call) for call in mock_print.call_args_list
            )
            assert any("0.95" in str(call) for call in mock_print.call_args_list)

    def test_format_response_error(self, nl2sql_handler):
        """Test formatting error response."""
        response = {"success": False, "error": "Failed to parse query"}

        with patch("builtins.print") as mock_print:
            nl2sql_handler.format_response(response)

            # Should print error
            assert any(
                "Failed to parse query" in str(call)
                for call in mock_print.call_args_list
            )

    def test_save_to_session(self, nl2sql_handler, mock_context):
        """Test saving query to session."""
        mock_context.current_session = MagicMock()

        query_data = {"query": "Test query", "sql": "SELECT 1", "confidence": 0.99}

        nl2sql_handler.save_to_session(query_data)

        mock_context.current_session.add_message.assert_called_once()
        call_args = mock_context.current_session.add_message.call_args[1]
        assert call_args["role"] == "user"
        assert "Test query" in call_args["content"]

    def test_update_metrics(self, nl2sql_handler, mock_context):
        """Test metrics update."""
        # Reset metrics
        mock_context.metrics = {
            "total_queries": 0,
            "successful_queries": 0,
            "total_response_time": 0,
        }

        # Update with successful query
        response = {"success": True, "response_time": 0.5}
        nl2sql_handler.update_metrics(response)

        assert mock_context.metrics["total_queries"] == 1
        assert mock_context.metrics["successful_queries"] == 1
        assert mock_context.metrics["total_response_time"] == 0.5

        # Update with failed query
        response = {"success": False, "response_time": 0.3}
        nl2sql_handler.update_metrics(response)

        assert mock_context.metrics["total_queries"] == 2
        assert mock_context.metrics["successful_queries"] == 1
        assert mock_context.metrics["total_response_time"] == 0.8


class TestRunInteractiveSession:
    """Test interactive session runner."""

    @pytest.mark.asyncio
    async def test_interactive_session_basic(self):
        """Test basic interactive session flow."""
        inputs = ["How many users?", "exit"]

        with patch("builtins.input", side_effect=inputs):
            with patch("sens.cli.nl2sql.NL2SQLContext") as mock_ctx_class:
                mock_context = MagicMock()
                mock_handler = MagicMock()
                mock_handler.process_query.return_value = {
                    "success": True,
                    "sql": "SELECT COUNT(*) FROM users",
                }

                with patch("sens.cli.nl2sql.NL2SQLHandler", return_value=mock_handler):
                    await run_interactive_session()

                    mock_handler.process_query.assert_called_once_with(
                        "How many users?"
                    )

    @pytest.mark.asyncio
    async def test_interactive_session_special_commands(self):
        """Test interactive session with special commands."""
        inputs = [".help", ".history", "exit"]

        with patch("builtins.input", side_effect=inputs):
            with patch(
                "sens.cli.nl2sql.handle_special_command", return_value=True
            ) as mock_special:
                with patch("sens.cli.nl2sql.NL2SQLContext"):
                    with patch("sens.cli.nl2sql.NL2SQLHandler"):
                        await run_interactive_session()

                        # Should handle special commands
                        assert mock_special.call_count >= 2

    @pytest.mark.asyncio
    async def test_interactive_session_error_handling(self):
        """Test interactive session error handling."""
        inputs = ["Test query", "exit"]

        with patch("builtins.input", side_effect=inputs):
            with patch("sens.cli.nl2sql.NL2SQLContext") as mock_ctx_class:
                mock_handler = MagicMock()
                mock_handler.process_query.side_effect = Exception("Processing error")

                with patch("sens.cli.nl2sql.NL2SQLHandler", return_value=mock_handler):
                    with patch("builtins.print") as mock_print:
                        await run_interactive_session()

                        # Should print error but continue
                        assert any(
                            "Error" in str(call) for call in mock_print.call_args_list
                        )

    @pytest.mark.asyncio
    async def test_interactive_session_keyboard_interrupt(self):
        """Test handling keyboard interrupt."""
        with patch("builtins.input", side_effect=KeyboardInterrupt):
            with patch("sens.cli.nl2sql.NL2SQLContext"):
                with patch("sens.cli.nl2sql.NL2SQLHandler"):
                    with patch("builtins.print") as mock_print:
                        await run_interactive_session()

                        # Should print goodbye message
                        assert any(
                            "Goodbye" in str(call) for call in mock_print.call_args_list
                        )


class TestIntegration:
    """Integration tests for NL2SQL CLI."""

    def test_full_query_flow(self):
        """Test full query processing flow."""
        with patch("sens.cli.nl2sql.EnhancedNL2SQLPipeline") as mock_pipeline_class:
            mock_pipeline = MagicMock()
            mock_pipeline.run.return_value = {
                "success": True,
                "sql": "SELECT AVG(price) FROM products WHERE category = 'electronics'",
                "confidence": 0.92,
                "tables_used": ["products"],
                "intent": {"type": "aggregate", "operation": "average"},
                "response_time": 0.45,
            }
            mock_pipeline_class.return_value = mock_pipeline

            context = NL2SQLContext()
            handler = NL2SQLHandler(context)

            with patch("builtins.print") as mock_print:
                result = handler.process_query(
                    "What is the average price of electronics?"
                )
                handler.format_response(result)

                # Verify full flow
                assert result["success"] is True
                assert len(context.history) == 1
                assert context.metrics["total_queries"] == 1
                assert context.metrics["successful_queries"] == 1

                # Check output
                assert any(
                    "SELECT AVG(price)" in str(call)
                    for call in mock_print.call_args_list
                )
