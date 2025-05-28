"""Tests for the actual main CLI module."""

import argparse
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
import structlog

from sens.cli.main import (
    handle_build_index,
    handle_execute,
    handle_extract_schema,
    handle_validate,
    main,
    setup_logging,
)


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    return MagicMock(spec=structlog.BoundLogger)


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = MagicMock()
    settings.logging.level = "INFO"
    settings.logging.format = "json"
    settings.environment = "test"
    return settings


class TestSetupLogging:
    """Test logging setup function."""

    def test_setup_logging_default(self, mock_settings):
        """Test default logging setup."""
        with patch("sens.cli.main.get_settings", return_value=mock_settings):
            with patch("sens.cli.main.configure_logging") as mock_configure:
                logger = setup_logging(verbose=False)

                mock_configure.assert_called_once()
                assert isinstance(logger, structlog.BoundLogger)

    def test_setup_logging_verbose(self, mock_settings):
        """Test verbose logging setup."""
        with patch("sens.cli.main.get_settings", return_value=mock_settings):
            with patch("sens.cli.main.reload_settings") as mock_reload:
                with patch("sens.cli.main.configure_logging"):
                    logger = setup_logging(verbose=True)

                    # Should update settings to DEBUG
                    mock_reload.assert_called_once()
                    updated_settings = mock_reload.call_args[0][0]
                    assert updated_settings["logging"]["level"] == "DEBUG"


class TestHandleExtractSchema:
    """Test schema extraction handler."""

    def test_extract_schema_success(self, mock_logger, tmp_path):
        """Test successful schema extraction."""
        output_file = tmp_path / "schema.json"
        args = argparse.Namespace(output=str(output_file), db_url=None, format="json")

        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = {
            "tables": [
                {"name": "users", "columns": [{"name": "id", "type": "integer"}]}
            ]
        }

        with patch("sens.cli.main.SchemaExtractor", return_value=mock_extractor):
            handle_extract_schema(args, mock_logger)

            # Check file was created
            assert output_file.exists()
            content = json.loads(output_file.read_text())
            assert "tables" in content

    def test_extract_schema_with_db_url(self, mock_logger, tmp_path):
        """Test schema extraction with custom DB URL."""
        output_file = tmp_path / "schema.json"
        args = argparse.Namespace(
            output=str(output_file),
            db_url="postgresql://test@localhost/testdb",
            format="json",
        )

        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = {"tables": []}

        with patch("sens.cli.main.SchemaExtractor") as mock_extractor_class:
            mock_extractor_class.return_value = mock_extractor

            handle_extract_schema(args, mock_logger)

            # Should use custom DB URL
            mock_extractor_class.assert_called_once_with(
                db_url="postgresql://test@localhost/testdb"
            )

    def test_extract_schema_error(self, mock_logger):
        """Test schema extraction error handling."""
        args = argparse.Namespace(output="schema.json", db_url=None, format="json")

        with patch("sens.cli.main.SchemaExtractor") as mock_extractor_class:
            mock_extractor_class.side_effect = Exception("Connection failed")

            with patch("sys.exit") as mock_exit:
                handle_extract_schema(args, mock_logger)

                mock_logger.error.assert_called_with(
                    "schema_extraction_failed", error="Connection failed"
                )
                mock_exit.assert_called_with(1)


class TestHandleBuildIndex:
    """Test index building handler."""

    def test_build_index_success(self, mock_logger, tmp_path):
        """Test successful index building."""
        schema_file = tmp_path / "schema.json"
        schema_file.write_text(
            json.dumps(
                {
                    "tables": [
                        {
                            "name": "users",
                            "columns": [
                                {"name": "id", "type": "integer"},
                                {"name": "email", "type": "varchar"},
                            ],
                        }
                    ]
                }
            )
        )

        args = argparse.Namespace(
            schema=str(schema_file),
            output_dir=str(tmp_path / "index"),
            model_name="all-MiniLM-L6-v2",
        )

        with patch("sens.cli.main.build_embedding_index") as mock_build:
            handle_build_index(args, mock_logger)

            mock_build.assert_called_once_with(
                str(schema_file), str(tmp_path / "index"), "all-MiniLM-L6-v2"
            )

            mock_logger.info.assert_any_call(
                "index_build_complete", output_dir=str(tmp_path / "index")
            )

    def test_build_index_file_not_found(self, mock_logger):
        """Test index building with missing schema file."""
        args = argparse.Namespace(
            schema="nonexistent.json", output_dir="index", model_name="all-MiniLM-L6-v2"
        )

        with patch("sys.exit") as mock_exit:
            handle_build_index(args, mock_logger)

            mock_logger.error.assert_called_with(
                "schema_file_not_found", path="nonexistent.json"
            )
            mock_exit.assert_called_with(1)


class TestHandleValidate:
    """Test SQL validation handler."""

    def test_validate_sql_valid(self, mock_logger):
        """Test validating valid SQL."""
        args = argparse.Namespace(
            sql="SELECT * FROM users", file=None, level="full", json=False
        )

        mock_validator = MagicMock()
        mock_result = MagicMock()
        mock_result.is_valid = True
        mock_result.errors = []
        mock_result.warnings = []
        mock_validator.validate.return_value = mock_result

        with patch("sens.cli.main.SQLValidator", return_value=mock_validator):
            with patch("builtins.print") as mock_print:
                handle_validate(args, mock_logger)

                # Should print success
                assert any(
                    "SQL is valid" in str(call) for call in mock_print.call_args_list
                )

    def test_validate_sql_from_file(self, mock_logger, tmp_path):
        """Test validating SQL from file."""
        sql_file = tmp_path / "query.sql"
        sql_file.write_text("SELECT COUNT(*) FROM orders WHERE status = 'active'")

        args = argparse.Namespace(
            sql=None, file=str(sql_file), level="safety", json=False
        )

        mock_validator = MagicMock()
        mock_result = MagicMock()
        mock_result.is_valid = True
        mock_result.errors = []
        mock_result.warnings = ["Consider adding index on status column"]
        mock_validator.validate.return_value = mock_result

        with patch("sens.cli.main.SQLValidator", return_value=mock_validator):
            with patch("builtins.print") as mock_print:
                handle_validate(args, mock_logger)

                # Should validate the SQL from file
                mock_validator.validate.assert_called_with(
                    "SELECT COUNT(*) FROM orders WHERE status = 'active'",
                    level="safety",
                )

                # Should show warning
                assert any(
                    "Consider adding index" in str(call)
                    for call in mock_print.call_args_list
                )

    def test_validate_sql_invalid(self, mock_logger):
        """Test validating invalid SQL."""
        args = argparse.Namespace(
            sql="DELETE FROM users", file=None, level="safety", json=False
        )

        mock_validator = MagicMock()
        mock_result = MagicMock()
        mock_result.is_valid = False
        mock_result.errors = ["DELETE operations are not allowed"]
        mock_result.warnings = []
        mock_validator.validate.return_value = mock_result

        with patch("sens.cli.main.SQLValidator", return_value=mock_validator):
            with patch("builtins.print") as mock_print:
                with patch("sys.exit") as mock_exit:
                    handle_validate(args, mock_logger)

                    # Should print errors
                    assert any(
                        "DELETE operations" in str(call)
                        for call in mock_print.call_args_list
                    )
                    mock_exit.assert_called_with(1)

    def test_validate_json_output(self, mock_logger):
        """Test validation with JSON output."""
        args = argparse.Namespace(
            sql="SELECT * FROM users", file=None, level="full", json=True
        )

        mock_validator = MagicMock()
        mock_result = MagicMock()
        mock_result.is_valid = True
        mock_result.errors = []
        mock_result.warnings = []
        mock_result.level = "full"
        mock_validator.validate.return_value = mock_result

        with patch("sens.cli.main.SQLValidator", return_value=mock_validator):
            with patch("builtins.print") as mock_print:
                handle_validate(args, mock_logger)

                # Should print JSON
                output = mock_print.call_args[0][0]
                data = json.loads(output)
                assert data["is_valid"] is True
                assert data["level"] == "full"


class TestHandleExecute:
    """Test SQL execution handler."""

    def test_execute_sql_success(self, mock_logger):
        """Test successful SQL execution."""
        args = argparse.Namespace(
            sql="SELECT id, name FROM users LIMIT 3", file=None, json=False
        )

        mock_executor = MagicMock()
        mock_result = MagicMock()
        mock_result.error = None
        mock_result.columns = ["id", "name"]
        mock_result.rows = [[1, "Alice"], [2, "Bob"], [3, "Charlie"]]
        mock_result.row_count = 3
        mock_executor.execute.return_value = mock_result

        with patch("sens.cli.main.SQLExecutor", return_value=mock_executor):
            with patch("builtins.print") as mock_print:
                handle_execute(args, mock_logger)

                # Should print table
                output = str(mock_print.call_args_list)
                assert "Alice" in output
                assert "Bob" in output
                assert "Charlie" in output
                assert "3" in output  # row count

    def test_execute_error(self, mock_logger):
        """Test execution error handling."""
        args = argparse.Namespace(sql="INVALID SQL", file=None, json=False)

        mock_executor = MagicMock()
        mock_executor.execute.side_effect = Exception("Syntax error")

        with patch("sens.cli.main.SQLExecutor", return_value=mock_executor):
            with patch("sys.exit") as mock_exit:
                handle_execute(args, mock_logger)

                mock_logger.error.assert_called_with(
                    "execution_failed", error="Syntax error"
                )
                mock_exit.assert_called_with(1)


class TestMain:
    """Test main entry point."""

    def test_main_no_command(self):
        """Test main with no command."""
        with patch("sys.argv", ["sens"]):
            with patch("sens.cli.main.setup_logging") as mock_setup:
                mock_logger = MagicMock()
                mock_setup.return_value = mock_logger

                # Create a parser that returns None for command
                with patch("argparse.ArgumentParser") as mock_parser_class:
                    mock_parser = MagicMock()
                    mock_parser.parse_args.return_value = argparse.Namespace(
                        command=None, verbose=False
                    )
                    mock_parser_class.return_value = mock_parser

                    main()

                    # Should print help
                    mock_parser.print_help.assert_called_once()

    def test_main_validate_command(self):
        """Test main with validate command."""
        with patch("sys.argv", ["sens", "validate", "-s", "SELECT 1"]):
            with patch("sens.cli.main.setup_logging") as mock_setup:
                mock_logger = MagicMock()
                mock_setup.return_value = mock_logger

                with patch("sens.cli.main.handle_validate") as mock_handle:
                    main()

                    # Should call validate handler
                    mock_handle.assert_called_once()
                    args = mock_handle.call_args[0][0]
                    assert args.sql == "SELECT 1"

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
