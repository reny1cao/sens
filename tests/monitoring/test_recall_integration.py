"""Integration test for recall tracking in the pipeline."""

import pytest

from sens.monitoring.metrics_collector import RetrievalMetricsCollector
from sens.monitoring.recall_tracker import RecallTracker
from sens.schema.context import ValidatorSchemaContext
from sens.validation.sql_validator import SQLValidator


class TestRecallIntegration:
    """Test recall tracking integration with SQL validation."""

    def test_recall_tracking_in_validation(self):
        """Test that recall is tracked when SQL is validated."""
        # Create validator and metrics collector
        validator = SQLValidator()
        collector = RetrievalMetricsCollector()

        # Create schema context
        schema = ValidatorSchemaContext(
            tables=["users", "orders"],
            columns_per_table={
                "users": ["id", "name", "email", "status"],
                "orders": ["id", "user_id", "amount", "created_at"],
            },
        )

        # Start retrieval and record retrieved schema
        metrics = collector.start_retrieval("find active users")
        collector.record_retrieved_schema(
            tables={"users", "orders"},
            columns={
                ("users", "id"),
                ("users", "name"),
                ("users", "status"),
                ("orders", "id"),
                ("orders", "user_id"),
            },
        )

        # Validate SQL which should trigger recall tracking
        sql = "SELECT id, name FROM users WHERE status = 'active'"
        result = validator.validate(
            sql=sql, full_schema=schema, retrieval_metrics_collector=collector
        )

        # Check validation passed
        assert result.is_valid

        # Check recall was calculated
        assert metrics.relevant_tables == {"users"}
        assert metrics.relevant_columns == {
            ("users", "id"),
            ("users", "name"),
            ("users", "status"),
        }

        # Calculate recall
        recall_stats = metrics.calculate_recall()
        assert recall_stats["table_recall"] == 1.0  # users was retrieved
        assert (
            recall_stats["column_recall"] == 1.0
        )  # All 3 relevant columns were retrieved

    def test_recall_with_missing_columns(self):
        """Test recall calculation when some columns are missing."""
        validator = SQLValidator()
        collector = RetrievalMetricsCollector()

        schema = ValidatorSchemaContext(
            tables=["users", "posts"],
            columns_per_table={
                "users": ["id", "name", "email", "created_at"],
                "posts": ["id", "user_id", "title", "content", "created_at"],
            },
        )

        # Start retrieval with partial schema
        metrics = collector.start_retrieval("find user posts")
        collector.record_retrieved_schema(
            tables={"users", "posts"},
            columns={
                ("users", "id"),
                ("users", "name"),
                ("posts", "id"),
                ("posts", "title"),
            },
        )

        # SQL that uses more columns than retrieved
        sql = """
        SELECT u.id, u.name, p.title, p.created_at
        FROM users u
        JOIN posts p ON u.id = p.user_id
        WHERE u.created_at > '2024-01-01'
        """

        result = validator.validate(
            sql=sql, full_schema=schema, retrieval_metrics_collector=collector
        )

        assert result.is_valid

        # Check relevant schema was identified
        assert metrics.relevant_tables == {"users", "posts"}
        assert ("users", "created_at") in metrics.relevant_columns
        assert ("posts", "created_at") in metrics.relevant_columns
        assert ("posts", "user_id") in metrics.relevant_columns

        # Calculate recall - should be less than 1.0
        recall_stats = metrics.calculate_recall()
        assert recall_stats["table_recall"] == 1.0  # Both tables retrieved
        assert recall_stats["column_recall"] < 1.0  # Missing some columns
