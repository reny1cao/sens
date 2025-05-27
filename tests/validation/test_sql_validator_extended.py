"""Extended tests for SQL Validator to improve coverage."""

from unittest.mock import MagicMock, patch

import pytest

from sens.monitoring.metrics_collector import RetrievalMetricsCollector
from sens.schema.context import ValidatorSchemaContext
from sens.validation.sql_validator import (
    SQLValidator,
    ValidatedSQL,
    ValidationError,
    ValidationLevel,
)


class TestSQLValidatorExtended:
    """Extended test suite for SQL Validator."""

    @pytest.fixture
    def complex_schema(self):
        """Create a complex schema for testing."""
        schema = ValidatorSchemaContext(
            tables={"users", "orders", "products", "categories", "order_items"},
            columns_per_table={
                "users": {"id", "name", "email", "created_at", "status"},
                "orders": {
                    "id",
                    "user_id",
                    "total",
                    "status",
                    "created_at",
                    "updated_at",
                },
                "products": {
                    "id",
                    "name",
                    "price",
                    "category_id",
                    "description",
                    "sku",
                },
                "categories": {"id", "name", "parent_id"},
                "order_items": {"id", "order_id", "product_id", "quantity", "price"},
            },
            foreign_keys={
                "orders": {"user_id": ("users", "id")},
                "products": {"category_id": ("categories", "id")},
                "order_items": {
                    "order_id": ("orders", "id"),
                    "product_id": ("products", "id"),
                },
                "categories": {"parent_id": ("categories", "id")},
            },
        )
        schema.metadata = {"version": "v2.0.0", "environment": "test"}
        return schema

    @pytest.fixture
    def validator(self):
        """Create a standard validator."""
        return SQLValidator()

    def test_sql_parsing_exception(self, validator, complex_schema):
        """Test handling of SQL parsing exceptions."""
        sql = "SELECT * FROM users WHERE id = 'unclosed string"

        with patch("sqlparse.parse", side_effect=Exception("Parsing failed")):
            result = validator.validate(
                sql, complex_schema, levels={ValidationLevel.SYNTAX}
            )
            assert not result.is_valid
            assert any(
                e.level == ValidationLevel.SYNTAX and "SQL parsing failed" in e.message
                for e in result.errors
            )

    def test_complex_join_with_aliases(self, validator, complex_schema):
        """Test complex joins with multiple aliases."""
        sql = """
        SELECT
            u.name as user_name,
            o.total as order_total,
            p.name as product_name,
            c.name as category_name,
            oi.quantity
        FROM users u
        INNER JOIN orders o ON u.id = o.user_id
        INNER JOIN order_items oi ON o.id = oi.order_id
        INNER JOIN products p ON oi.product_id = p.id
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE u.status = 'active'
        AND o.created_at >= '2024-01-01'
        ORDER BY o.total DESC
        LIMIT 10
        """
        result = validator.validate(sql, complex_schema)
        assert result.is_valid

    def test_subquery_validation(self, validator, complex_schema):
        """Test validation of subqueries."""
        sql = """
        SELECT u.name,
               (SELECT COUNT(*) FROM orders o WHERE o.user_id = u.id) as order_count
        FROM users u
        WHERE u.id IN (
            SELECT DISTINCT user_id
            FROM orders
            WHERE total > 100
        )
        """
        result = validator.validate(sql, complex_schema)
        assert result.is_valid

    def test_window_functions_fixed(self, validator, complex_schema):
        """Test validation of window functions."""
        sql = """
        SELECT
            id,
            total,
            ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC) as rn,
            SUM(total) OVER (PARTITION BY user_id) as user_total,
            LAG(total, 1) OVER (PARTITION BY user_id ORDER BY created_at) as prev_total
        FROM orders
        """
        result = validator.validate(sql, complex_schema)
        assert result.is_valid

    def test_union_queries(self, validator, complex_schema):
        """Test validation of UNION queries."""
        sql = """
        SELECT 'user' as type, id, name FROM users
        UNION ALL
        SELECT 'product' as type, id, name FROM products
        UNION
        SELECT 'category' as type, id, name FROM categories
        """
        result = validator.validate(sql, complex_schema)
        assert result.is_valid

    def test_case_statements_fixed(self, validator, complex_schema):
        """Test validation of CASE statements."""
        sql = """
        SELECT
            id,
            user_id,
            CASE
                WHEN total > 1000 THEN 'high'
                WHEN total > 500 THEN 'medium'
                ELSE 'low'
            END as order_size,
            CASE status
                WHEN 'pending' THEN 0
                WHEN 'processing' THEN 1
                WHEN 'completed' THEN 2
                ELSE -1
            END as status_code
        FROM orders
        """
        result = validator.validate(sql, complex_schema)
        assert result.is_valid

    def test_select_star_expansion(self, validator, complex_schema):
        """Test that SELECT * is handled correctly."""
        sql = "SELECT * FROM users"
        result = validator.validate(sql, complex_schema)
        assert result.is_valid

    def test_string_value_validation(self, validator, complex_schema):
        """Test that string values in queries don't trigger false positives."""
        sql = """
        SELECT * FROM users
        WHERE name = 'DROP TABLE users'
        AND email LIKE '%CREATE%'
        AND status != 'ALTER'
        """
        result = validator.validate(sql, complex_schema)
        assert result.is_valid

    def test_computed_columns_complex(self, validator, complex_schema):
        """Test complex computed columns and aliases."""
        sql = """
        SELECT
            EXTRACT(YEAR FROM created_at) as year,
            EXTRACT(MONTH FROM created_at) as month,
            COUNT(DISTINCT user_id) as unique_users,
            SUM(total) as revenue,
            AVG(total) as avg_order_value,
            SUM(total) / COUNT(DISTINCT user_id) as revenue_per_user,
            CONCAT(EXTRACT(YEAR FROM created_at), '-', EXTRACT(MONTH FROM created_at)) as period
        FROM orders
        GROUP BY year, month, period
        HAVING revenue > 10000
        ORDER BY year DESC, month DESC
        """
        result = validator.validate(sql, complex_schema)
        assert result.is_valid

    def test_json_operations(self, validator):
        """Test validation of JSON operations."""
        schema = ValidatorSchemaContext(
            tables={"users"},
            columns_per_table={"users": {"id", "name", "metadata"}},
        )

        sql = """
        SELECT
            id,
            name,
            metadata->>'email' as email,
            metadata->'preferences'->>'theme' as theme
        FROM users
        WHERE metadata->>'status' = 'active'
        """
        result = validator.validate(sql, schema)
        assert result.is_valid

    def test_exists_clause_fixed(self, validator, complex_schema):
        """Test EXISTS clause validation."""
        sql = """
        SELECT u.id, u.name, u.email
        FROM users u
        WHERE EXISTS (
            SELECT 1
            FROM orders o
            WHERE o.user_id = u.id
            AND o.total > 100
        )
        AND NOT EXISTS (
            SELECT 1
            FROM orders o2
            WHERE o2.user_id = u.id
            AND o2.status = 'cancelled'
        )
        """
        result = validator.validate(sql, complex_schema)
        assert result.is_valid

    def test_lateral_join(self, validator, complex_schema):
        """Test LATERAL join validation."""
        sql = """
        SELECT u.name, recent_orders.total
        FROM users u
        CROSS JOIN LATERAL (
            SELECT total
            FROM orders o
            WHERE o.user_id = u.id
            ORDER BY o.created_at DESC
            LIMIT 3
        ) AS recent_orders
        """
        result = validator.validate(sql, complex_schema)
        assert result.is_valid

    def test_context_bypass_detection_comprehensive(self, validator, complex_schema):
        """Test comprehensive context bypass detection."""
        prompted_schema = ValidatorSchemaContext(
            tables={"users", "orders"},
            columns_per_table={
                "users": {"id", "name"},  # Missing email, created_at, status
                "orders": {"id", "user_id"},  # Missing total, status, etc.
            },
        )

        sql = """
        SELECT u.email, u.status, o.total, o.status as order_status
        FROM users u
        JOIN orders o ON u.id = o.user_id
        WHERE u.created_at > '2024-01-01'
        """

        result = validator.validate(
            sql=sql,
            full_schema=complex_schema,
            prompted_schema=prompted_schema,
            query_id="test-123",
        )

        assert result.is_valid  # Valid against full schema
        assert result.context_bypass_info is not None
        assert result.context_bypass_info.is_bypass
        assert len(result.context_bypass_info.used_but_missing_columns) > 0
        assert result.context_bypass_info.bypass_score > 0

    def test_invalid_column_detection(self, validator, complex_schema):
        """Test detection of invalid columns."""
        sql = """
        SELECT
            u.name,
            u.invalid_column
        FROM users u
        """

        result = validator.validate(sql, complex_schema)
        assert not result.is_valid
        assert any(
            e.level == ValidationLevel.SCHEMA and "invalid_column" in e.message
            for e in result.errors
        )

    def test_computed_columns_in_group_by(self, validator, complex_schema):
        """Test that computed column aliases can be used in GROUP BY."""
        sql = """
        SELECT
            EXTRACT(YEAR FROM created_at) as year,
            EXTRACT(MONTH FROM created_at) as month,
            SUM(total) as revenue
        FROM orders
        GROUP BY year, month
        ORDER BY year DESC, month DESC
        """
        result = validator.validate(sql, complex_schema)
        assert result.is_valid

    def test_update_without_where_check(self):
        """Test UPDATE without WHERE clause is caught."""
        schema = ValidatorSchemaContext(
            tables={"users"},
            columns_per_table={"users": {"id", "name", "status"}},
        )

        validator = SQLValidator()
        sql = "UPDATE users SET status = 'inactive'"
        result = validator.validate(sql, schema, levels={ValidationLevel.SAFETY})
        assert not result.is_valid
        assert any("WHERE" in e.message for e in result.errors)

    def test_multiple_validation_levels(self, validator, complex_schema):
        """Test multiple validation levels work together."""
        sql = "DROP TABLE non_existent_table"

        result = validator.validate(sql, complex_schema)

        assert not result.is_valid
        # Should have schema error for non-existent table
        schema_errors = [e for e in result.errors if e.level == ValidationLevel.SCHEMA]
        assert len(schema_errors) > 0
        assert any("non_existent_table" in e.message for e in schema_errors)

        # Should have safety error for DROP
        safety_errors = [e for e in result.errors if e.level == ValidationLevel.SAFETY]
        assert len(safety_errors) > 0
        assert any("DROP" in e.message for e in safety_errors)

    def test_validation_with_null_checks(self, validator, complex_schema):
        """Test validation with NULL checks and COALESCE."""
        sql = """
        SELECT
            name,
            COALESCE(email, 'no-email@example.com') as email,
            CASE
                WHEN created_at IS NULL THEN 'unknown'
                WHEN created_at > CURRENT_DATE - INTERVAL '30 days' THEN 'new'
                ELSE 'old'
            END as user_age
        FROM users
        WHERE email IS NOT NULL
        OR (email IS NULL AND status = 'pending')
        """

        result = validator.validate(sql, complex_schema)
        assert result.is_valid

    def test_aggregate_functions_without_group_by(self, validator, complex_schema):
        """Test aggregate functions without GROUP BY."""
        sql = """
        SELECT
            COUNT(*) as total_users,
            COUNT(DISTINCT status) as status_count,
            MAX(created_at) as latest_signup
        FROM users
        """

        result = validator.validate(sql, complex_schema)
        assert result.is_valid

    def test_having_without_group_by(self, validator, complex_schema):
        """Test HAVING clause without GROUP BY."""
        sql = """
        SELECT COUNT(*) as cnt
        FROM users
        HAVING COUNT(*) > 10
        """

        result = validator.validate(sql, complex_schema)
        # This should validate successfully
        assert isinstance(result, ValidatedSQL)

    def test_distinct_on(self, validator, complex_schema):
        """Test DISTINCT ON clause (PostgreSQL specific)."""
        sql = """
        SELECT DISTINCT ON (user_id)
            user_id,
            total,
            created_at
        FROM orders
        ORDER BY user_id, created_at DESC
        """

        result = validator.validate(sql, complex_schema)
        assert result.is_valid

    def test_validation_result_string_representation(self, validator, complex_schema):
        """Test the __str__ method of ValidatedSQL."""
        sql = "SELECT * FROM non_existent_table"

        result = validator.validate(sql, complex_schema)

        # Test string representation
        result_str = str(result)
        assert "SQL Validation Result: INVALID" in result_str
        assert "SCHEMA" in result_str
        assert "non_existent_table" in result_str

    def test_context_bypass_with_full_version(self, validator):
        """Test context bypass info includes schema version."""
        full_schema = ValidatorSchemaContext(
            tables={"users"},
            columns_per_table={"users": {"id", "name", "email"}},
        )
        full_schema.metadata = {"version": "v1.2.3", "last_updated": "2024-01-01"}

        prompted_schema = ValidatorSchemaContext(
            tables={"users"},
            columns_per_table={"users": {"id", "name"}},  # Missing email
        )

        sql = "SELECT id, name, email FROM users"

        result = validator.validate(
            sql=sql,
            full_schema=full_schema,
            prompted_schema=prompted_schema,
            query_id="test-456",
        )

        assert result.is_valid
        assert result.context_bypass_info is not None
        assert result.context_bypass_info.is_bypass
        assert result.context_bypass_info.full_schema_version == "v1.2.3"
        assert (
            result.context_bypass_info.bypass_score == 1 / 3
        )  # 1 missing out of 3 total

    def test_empty_schema_validation(self, validator):
        """Test validation with empty schema."""
        empty_schema = ValidatorSchemaContext(tables=set(), columns_per_table={})

        sql = "SELECT * FROM users"

        result = validator.validate(sql, empty_schema, levels={ValidationLevel.SCHEMA})

        assert not result.is_valid
        assert any(e.level == ValidationLevel.SCHEMA for e in result.errors)

    def test_validation_with_warnings(self, validator, complex_schema):
        """Test that warnings can be added to validation results."""
        sql = "SELECT * FROM users LIMIT 10000"

        result = validator.validate(sql, complex_schema)

        # Manually add a warning to test the string representation
        result.warnings.append("Large LIMIT value may impact performance")

        result_str = str(result)
        assert "Warnings:" in result_str
        assert "Large LIMIT value" in result_str
