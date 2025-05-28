"""Extended tests for CLI formatters."""

import json
from datetime import datetime
from io import StringIO
from unittest.mock import patch

import pytest
from tabulate import tabulate

from sens.cli.formatters import (
    format_column_search_results,
    format_error,
    format_execution_result,
    format_intent_result,
    format_nl2sql_response,
    format_retrieval_context,
    format_sql_with_syntax_highlighting,
    format_success,
    format_table_search_results,
    format_validation_result,
    format_warning,
)
from sens.execution.types import ExecutionResult
from sens.retrieval.models import RetrievedColumn, RetrievedContext, RetrievedTable
from sens.validation.types import ValidationResult


class TestBasicFormatters:
    """Test basic formatting functions."""

    def test_format_success(self):
        """Test success message formatting."""
        result = format_success("Operation completed")
        assert "✓" in result
        assert "Operation completed" in result
        assert "\033[92m" in result  # Green color

    def test_format_error(self):
        """Test error message formatting."""
        result = format_error("Something went wrong")
        assert "✗" in result
        assert "Something went wrong" in result
        assert "\033[91m" in result  # Red color

    def test_format_warning(self):
        """Test warning message formatting."""
        result = format_warning("Be careful")
        assert "⚠" in result
        assert "Be careful" in result
        assert "\033[93m" in result  # Yellow color

    def test_format_sql_with_syntax_highlighting(self):
        """Test SQL syntax highlighting."""
        sql = "SELECT COUNT(*) FROM users WHERE active = true"
        result = format_sql_with_syntax_highlighting(sql)

        # Should contain ANSI color codes
        assert "\033[" in result
        # Should contain the SQL
        assert "SELECT" in result
        assert "COUNT" in result
        assert "users" in result

    def test_format_sql_with_complex_query(self):
        """Test SQL highlighting with complex query."""
        sql = """
        WITH monthly_sales AS (
            SELECT
                DATE_TRUNC('month', order_date) as month,
                SUM(amount) as total
            FROM orders
            WHERE status = 'completed'
            GROUP BY 1
        )
        SELECT * FROM monthly_sales
        ORDER BY month DESC
        """
        result = format_sql_with_syntax_highlighting(sql)

        # Should handle multi-line SQL
        assert "WITH" in result
        assert "DATE_TRUNC" in result
        assert "monthly_sales" in result


class TestNL2SQLResponseFormatter:
    """Test NL2SQL response formatting."""

    def test_format_successful_response(self):
        """Test formatting successful NL2SQL response."""
        response = {
            "success": True,
            "sql": "SELECT * FROM products WHERE price > 100",
            "confidence": 0.95,
            "tables_used": ["products"],
            "intent": {"type": "filter", "confidence": 0.95},
            "response_time": 0.234,
        }

        with patch("builtins.print") as mock_print:
            format_nl2sql_response(response)

            calls = [str(call) for call in mock_print.call_args_list]
            output = "\n".join(calls)

            # Should show SQL
            assert "SELECT * FROM products" in output
            # Should show confidence
            assert "95%" in output or "0.95" in output
            # Should show tables
            assert "products" in output
            # Should show response time
            assert "234ms" in output or "0.234" in output

    def test_format_failed_response(self):
        """Test formatting failed NL2SQL response."""
        response = {
            "success": False,
            "error": "Could not understand the query",
            "confidence": 0.2,
            "suggestions": ["Try rephrasing your question", "Be more specific"],
        }

        with patch("builtins.print") as mock_print:
            format_nl2sql_response(response)

            calls = [str(call) for call in mock_print.call_args_list]
            output = "\n".join(calls)

            # Should show error
            assert "Could not understand" in output
            # Should show suggestions
            assert "Try rephrasing" in output
            assert "Be more specific" in output

    def test_format_response_with_warnings(self):
        """Test formatting response with warnings."""
        response = {
            "success": True,
            "sql": "SELECT * FROM large_table",
            "confidence": 0.88,
            "warnings": [
                "Query may return large result set",
                "Consider adding LIMIT clause",
            ],
        }

        with patch("builtins.print") as mock_print:
            format_nl2sql_response(response)

            calls = [str(call) for call in mock_print.call_args_list]
            output = "\n".join(calls)

            # Should show warnings
            assert "Warning" in output
            assert "large result set" in output
            assert "LIMIT clause" in output

    def test_format_json_output(self):
        """Test JSON output formatting."""
        response = {
            "success": True,
            "sql": "SELECT COUNT(*) FROM users",
            "confidence": 0.99,
        }

        with patch("builtins.print") as mock_print:
            format_nl2sql_response(response, output_format="json")

            # Should print valid JSON
            printed = mock_print.call_args[0][0]
            parsed = json.loads(printed)
            assert parsed["sql"] == "SELECT COUNT(*) FROM users"


class TestExecutionResultFormatter:
    """Test execution result formatting."""

    def test_format_successful_execution(self):
        """Test formatting successful execution."""
        result = ExecutionResult(
            success=True,
            columns=["id", "name", "email"],
            rows=[
                [1, "Alice", "alice@example.com"],
                [2, "Bob", "bob@example.com"],
                [3, "Charlie", "charlie@example.com"],
            ],
            row_count=3,
            execution_time=0.045,
        )

        with patch("builtins.print") as mock_print:
            format_execution_result(result)

            calls = [str(call) for call in mock_print.call_args_list]
            output = "\n".join(calls)

            # Should show table
            assert "Alice" in output
            assert "Bob" in output
            assert "Charlie" in output
            # Should show row count
            assert "3 rows" in output
            # Should show execution time
            assert "45ms" in output or "0.045" in output

    def test_format_empty_result(self):
        """Test formatting empty result."""
        result = ExecutionResult(
            success=True,
            columns=["id", "name"],
            rows=[],
            row_count=0,
            execution_time=0.012,
        )

        with patch("builtins.print") as mock_print:
            format_execution_result(result)

            calls = [str(call) for call in mock_print.call_args_list]
            output = "\n".join(calls)

            # Should indicate no results
            assert "No results" in output or "0 rows" in output

    def test_format_execution_error(self):
        """Test formatting execution error."""
        result = ExecutionResult(
            success=False, error="Table 'users' doesn't exist", execution_time=0.001
        )

        with patch("builtins.print") as mock_print:
            format_execution_result(result)

            calls = [str(call) for call in mock_print.call_args_list]
            output = "\n".join(calls)

            # Should show error
            assert "Error" in output
            assert "Table 'users' doesn't exist" in output

    def test_format_large_result_truncated(self):
        """Test formatting large result with truncation."""
        # Create 100 rows
        rows = [[i, f"User{i}", f"user{i}@example.com"] for i in range(100)]

        result = ExecutionResult(
            success=True,
            columns=["id", "name", "email"],
            rows=rows,
            row_count=100,
            execution_time=0.123,
        )

        with patch("builtins.print") as mock_print:
            format_execution_result(result, max_rows=10)

            calls = [str(call) for call in mock_print.call_args_list]
            output = "\n".join(calls)

            # Should show truncation message
            assert "Showing first 10" in output or "truncated" in output
            # Should still show total count
            assert "100 rows" in output


class TestValidationResultFormatter:
    """Test validation result formatting."""

    def test_format_valid_result(self):
        """Test formatting valid SQL."""
        result = ValidationResult(
            is_valid=True,
            level="full",
            errors=[],
            warnings=[],
            metadata={"tables_referenced": ["users", "orders"]},
        )

        with patch("builtins.print") as mock_print:
            format_validation_result(result)

            calls = [str(call) for call in mock_print.call_args_list]
            output = "\n".join(calls)

            # Should show success
            assert "Valid" in output or "✓" in output
            # Should show level
            assert "full" in output

    def test_format_invalid_result(self):
        """Test formatting invalid SQL."""
        result = ValidationResult(
            is_valid=False,
            level="syntax",
            errors=["Syntax error near 'SELCT'", "Unknown function 'COUNTT'"],
            warnings=[],
        )

        with patch("builtins.print") as mock_print:
            format_validation_result(result)

            calls = [str(call) for call in mock_print.call_args_list]
            output = "\n".join(calls)

            # Should show errors
            assert "Invalid" in output or "✗" in output
            assert "Syntax error" in output
            assert "Unknown function" in output

    def test_format_result_with_warnings(self):
        """Test formatting result with warnings."""
        result = ValidationResult(
            is_valid=True,
            level="performance",
            errors=[],
            warnings=[
                "Missing index on users.email",
                "Query may perform full table scan",
            ],
        )

        with patch("builtins.print") as mock_print:
            format_validation_result(result)

            calls = [str(call) for call in mock_print.call_args_list]
            output = "\n".join(calls)

            # Should show warnings
            assert "Warning" in output or "⚠" in output
            assert "Missing index" in output
            assert "full table scan" in output


class TestSearchResultFormatters:
    """Test search result formatting."""

    def test_format_table_search_results(self):
        """Test formatting table search results."""
        results = {
            "query": "user orders",
            "results": [
                {
                    "table_name": "users",
                    "score": 0.95,
                    "matched_tokens": ["user", "users"],
                    "match_type": "exact",
                },
                {
                    "table_name": "user_orders",
                    "score": 0.90,
                    "matched_tokens": ["user", "orders"],
                    "match_type": "partial",
                },
                {
                    "table_name": "order_items",
                    "score": 0.70,
                    "matched_tokens": ["orders"],
                    "match_type": "partial",
                },
            ],
            "total_results": 3,
            "search_time_ms": 12.5,
        }

        with patch("builtins.print") as mock_print:
            format_table_search_results(results)

            calls = [str(call) for call in mock_print.call_args_list]
            output = "\n".join(calls)

            # Should show query
            assert "user orders" in output
            # Should show results
            assert "users" in output
            assert "user_orders" in output
            assert "order_items" in output
            # Should show scores
            assert "0.95" in output or "95%" in output
            # Should show search time
            assert "12.5ms" in output

    def test_format_column_search_results(self):
        """Test formatting column search results."""
        results = {
            "query": "email address",
            "results": [
                {
                    "table_name": "users",
                    "column_name": "email",
                    "score": 0.98,
                    "source": "embedding",
                },
                {
                    "table_name": "customers",
                    "column_name": "email_address",
                    "score": 0.92,
                    "source": "token",
                },
                {
                    "table_name": "contacts",
                    "column_name": "primary_email",
                    "score": 0.85,
                    "source": "embedding",
                },
            ],
            "total_results": 3,
            "search_time_ms": 23.7,
        }

        with patch("builtins.print") as mock_print:
            format_column_search_results(results)

            calls = [str(call) for call in mock_print.call_args_list]
            output = "\n".join(calls)

            # Should show columns with tables
            assert "users.email" in output
            assert "customers.email_address" in output
            assert "contacts.primary_email" in output
            # Should show source
            assert "embedding" in output
            assert "token" in output


class TestRetrievalContextFormatter:
    """Test retrieval context formatting."""

    def test_format_retrieval_context(self):
        """Test formatting retrieved context."""
        context = RetrievedContext(
            query="Show revenue by customer segment",
            tables=[
                RetrievedTable(
                    table_name="orders",
                    reason="direct_hit",
                    metadata={"importance": "high"},
                ),
                RetrievedTable(
                    table_name="customers",
                    reason="join_expansion",
                    metadata={"importance": "medium"},
                ),
            ],
            columns=[
                RetrievedColumn(
                    table_name="orders",
                    column_name="total_amount",
                    score=0.95,
                    source="embedding",
                ),
                RetrievedColumn(
                    table_name="customers",
                    column_name="segment",
                    score=0.92,
                    source="embedding",
                ),
                RetrievedColumn(
                    table_name="orders",
                    column_name="customer_id",
                    score=0.88,
                    source="sticky",
                ),
            ],
        )

        with patch("builtins.print") as mock_print:
            format_retrieval_context(context)

            calls = [str(call) for call in mock_print.call_args_list]
            output = "\n".join(calls)

            # Should show query
            assert "revenue by customer segment" in output
            # Should show tables
            assert "orders" in output
            assert "customers" in output
            # Should show columns
            assert "total_amount" in output
            assert "segment" in output
            assert "customer_id" in output
            # Should show scores
            assert "0.95" in output or "95%" in output

    def test_format_empty_context(self):
        """Test formatting empty context."""
        context = RetrievedContext(query="Unknown query", tables=[], columns=[])

        with patch("builtins.print") as mock_print:
            format_retrieval_context(context)

            calls = [str(call) for call in mock_print.call_args_list]
            output = "\n".join(calls)

            # Should indicate no results
            assert "No tables found" in output or "No relevant" in output


class TestIntentResultFormatter:
    """Test intent result formatting."""

    def test_format_intent_result(self):
        """Test formatting intent extraction result."""
        result = {
            "intent": "aggregate",
            "confidence": 0.92,
            "relevant_tables": ["sales", "products", "categories"],
            "operations": ["SUM", "GROUP BY", "JOIN"],
            "metadata": {"time_range": "last_month", "aggregation": "sum"},
        }

        with patch("builtins.print") as mock_print:
            format_intent_result(result)

            calls = [str(call) for call in mock_print.call_args_list]
            output = "\n".join(calls)

            # Should show intent
            assert "aggregate" in output
            # Should show confidence
            assert "92%" in output or "0.92" in output
            # Should show tables
            assert "sales" in output
            assert "products" in output
            # Should show operations
            assert "SUM" in output
            assert "GROUP BY" in output

    def test_format_low_confidence_intent(self):
        """Test formatting low confidence intent."""
        result = {
            "intent": "unknown",
            "confidence": 0.35,
            "relevant_tables": [],
            "operations": [],
            "suggestions": ["Please be more specific", "Try including table names"],
        }

        with patch("builtins.print") as mock_print:
            format_intent_result(result)

            calls = [str(call) for call in mock_print.call_args_list]
            output = "\n".join(calls)

            # Should show low confidence warning
            assert "Low confidence" in output or "35%" in output
            # Should show suggestions
            assert "more specific" in output
            assert "table names" in output
