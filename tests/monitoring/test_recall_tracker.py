"""Tests for recall tracking from SQL."""

import pytest

from sens.monitoring.recall_tracker import RecallTracker


class TestRecallTracker:
    """Test recall tracking functionality."""

    def test_extract_simple_select(self):
        """Test extraction from simple SELECT query."""
        sql = "SELECT id, name FROM users WHERE status = 'active'"

        tables, columns = RecallTracker.extract_schema_from_sql(sql)

        assert tables == {"users"}
        assert ("users", "id") in columns
        assert ("users", "name") in columns
        assert ("users", "status") in columns

    def test_extract_join_query(self):
        """Test extraction from JOIN query."""
        sql = """
        SELECT u.id, u.name, p.title
        FROM users u
        JOIN posts p ON u.id = p.user_id
        WHERE p.created_at > '2024-01-01'
        """

        tables, columns = RecallTracker.extract_schema_from_sql(sql)

        assert "users" in tables
        assert "posts" in tables
        assert ("users", "id") in columns
        assert ("users", "name") in columns
        assert ("posts", "title") in columns
        assert ("posts", "user_id") in columns
        assert ("posts", "created_at") in columns

    def test_extract_complex_query(self):
        """Test extraction from complex query with aggregations."""
        sql = """
        SELECT
            u.department,
            COUNT(o.id) as order_count,
            SUM(o.amount) as total_amount
        FROM users u
        LEFT JOIN orders o ON u.id = o.user_id
        WHERE u.status = 'active'
            AND o.created_at >= '2024-01-01'
        GROUP BY u.department
        HAVING COUNT(o.id) > 10
        """

        tables, columns = RecallTracker.extract_schema_from_sql(sql)

        assert "users" in tables
        assert "orders" in tables

        # Should include columns used in SELECT, JOIN, WHERE, GROUP BY
        expected_columns = {
            ("users", "department"),
            ("users", "id"),
            ("users", "status"),
            ("orders", "id"),
            ("orders", "user_id"),
            ("orders", "amount"),
            ("orders", "created_at"),
        }

        for col in expected_columns:
            assert col in columns

    def test_extract_subquery(self):
        """Test extraction from query with subquery."""
        sql = """
        SELECT u.name, u.email
        FROM users u
        WHERE u.id IN (
            SELECT DISTINCT user_id
            FROM orders
            WHERE total > 1000
        )
        """

        tables, columns = RecallTracker.extract_schema_from_sql(sql)

        assert "users" in tables
        assert "orders" in tables

        assert ("users", "name") in columns
        assert ("users", "email") in columns
        assert ("users", "id") in columns
        assert ("orders", "user_id") in columns
        assert ("orders", "total") in columns

    def test_regex_fallback(self):
        """Test regex fallback for malformed SQL."""
        # Intentionally malformed SQL that might fail parsing
        sql = "SELECT * FROM users WHERE"

        # Should not raise exception
        tables, columns = RecallTracker.extract_schema_from_sql(sql)

        # At minimum should extract the table
        assert "users" in tables

    def test_track_sql_recall_integration(self):
        """Test full recall tracking integration."""
        from sens.monitoring.metrics_collector import RetrievalMetricsCollector

        collector = RetrievalMetricsCollector()
        metrics = collector.start_retrieval("find active users")

        # Simulate retrieval
        collector.record_retrieved_schema(
            tables={"users", "posts", "comments"},
            columns={
                ("users", "id"),
                ("users", "name"),
                ("users", "email"),
                ("posts", "title"),
                ("comments", "text"),
            },
        )

        # Track SQL recall
        sql = "SELECT id, name FROM users WHERE status = 'active'"
        RecallTracker.track_sql_recall("find active users", sql, collector)

        # Check recall calculation
        recall = metrics.calculate_recall()
        assert recall["table_recall"] == 1.0  # users table was relevant and retrieved
        assert recall["column_recall"] > 0  # Some columns were relevant
