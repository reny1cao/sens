"""Tests for the SQL Validator module."""

import pytest

from sens.schema.context import ValidatorSchemaContext
from sens.validation.sql_validator import (
    SQLValidator,
    ValidatedSQL,
    ValidationError,
    ValidationLevel,
)


# Test fixtures
@pytest.fixture
def sample_schema():
    """Create a sample schema for testing."""
    return ValidatorSchemaContext(
        tables={"users", "orders"},
        columns_per_table={
            "users": {"id", "name", "email"},
            "orders": {"id", "user_id", "product_id", "quantity"},
        },
    )


@pytest.fixture
def full_schema():
    """Create a full schema for testing."""
    return ValidatorSchemaContext(
        tables={"users", "orders", "products"},
        columns_per_table={
            "users": {"id", "name", "email", "created_at"},
            "orders": {"id", "user_id", "total", "status", "created_at"},
            "products": {"id", "name", "price", "description"},
        },
    )


@pytest.fixture
def prompted_schema():
    """Create a subset schema that would be given to LLM."""
    return ValidatorSchemaContext(
        tables={"users", "orders"},
        columns_per_table={
            "users": {"id", "name"},  # email and created_at omitted
            "orders": {"id", "user_id", "total"},  # status and created_at omitted
        },
    )


@pytest.fixture
def validator():
    """Create a default SQLValidator instance."""
    return SQLValidator()


# Syntax validation tests
def test_syntax_validation_valid_sql(validator):
    """Test syntax validation with valid SQL."""
    sql = "SELECT id, name FROM users WHERE id = 1;"
    result = validator.validate(
        sql=sql,
        full_schema=ValidatorSchemaContext(set(), {}),
        prompted_schema=None,
        levels={ValidationLevel.SYNTAX},
    )
    assert result.is_valid
    assert not result.errors


def test_syntax_validation_invalid_sql(validator):
    """Test syntax validation with invalid SQL."""
    sql = "SELEC * FORM users"  # Intentional typos
    result = validator.validate(
        sql=sql,
        full_schema=ValidatorSchemaContext(set(), {}),
        prompted_schema=None,
        levels={ValidationLevel.SYNTAX},
    )
    assert not result.is_valid
    assert len(result.errors) > 0
    assert all(error.level == ValidationLevel.SYNTAX for error in result.errors)


def test_empty_sql(validator):
    """Test validation of empty SQL."""
    sql = ""
    result = validator.validate(
        sql=sql,
        full_schema=ValidatorSchemaContext(set(), {}),
        prompted_schema=None,
        levels={ValidationLevel.SYNTAX},
    )
    assert not result.is_valid
    assert len(result.errors) == 1
    assert result.errors[0].level == ValidationLevel.SYNTAX


# Schema validation tests
def test_schema_validation_valid(validator, sample_schema):
    """Test schema validation with valid table and column references."""
    sql = "SELECT id, name FROM users WHERE email = 'test@example.com';"
    result = validator.validate(
        sql=sql,
        full_schema=sample_schema,
        prompted_schema=None,
        levels={ValidationLevel.SCHEMA},
    )
    assert result.is_valid
    assert not result.errors


def test_schema_validation_invalid_table(validator, sample_schema):
    """Test schema validation with non-existent table."""
    sql = "SELECT id FROM non_existent_table;"
    result = validator.validate(
        sql=sql,
        full_schema=sample_schema,
        prompted_schema=None,
        levels={ValidationLevel.SCHEMA},
    )
    assert not result.is_valid
    assert len(result.errors) == 1
    assert "non_existent_table" in result.errors[0].message.lower()


def test_schema_validation_invalid_column(validator, sample_schema):
    """Test schema validation with non-existent column."""
    sql = "SELECT id, non_existent_column FROM users;"
    result = validator.validate(
        sql=sql,
        full_schema=sample_schema,
        prompted_schema=None,
        levels={ValidationLevel.SCHEMA},
    )
    assert not result.is_valid
    assert len(result.errors) == 1
    assert "non_existent_column" in result.errors[0].message.lower()


def test_schema_validation_qualified_names(validator, sample_schema):
    """Test schema validation with qualified column names."""
    sql = "SELECT users.id, users.name FROM users;"
    result = validator.validate(
        sql=sql,
        full_schema=sample_schema,
        prompted_schema=None,
        levels={ValidationLevel.SCHEMA},
    )
    assert result.is_valid
    assert not result.errors


# Safety validation tests
def test_safety_validation_forbidden_keywords(validator, sample_schema):
    """Test safety validation with forbidden keywords."""
    sql = "DROP TABLE users;"
    result = validator.validate(
        sql=sql,
        full_schema=sample_schema,
        prompted_schema=None,
        levels={ValidationLevel.SAFETY},
    )
    assert not result.is_valid
    assert len(result.errors) == 1
    assert result.errors[0].level == ValidationLevel.SAFETY
    assert "DROP" in result.errors[0].message


def test_safety_validation_whitelisted_keywords():
    """Test safety validation with whitelisted keywords."""
    validator = SQLValidator(whitelisted_keywords={"DELETE"})
    sql = "DELETE FROM users WHERE id = 1;"
    result = validator.validate(
        sql=sql,
        full_schema=ValidatorSchemaContext(set(), {}),
        prompted_schema=None,
        levels={ValidationLevel.SAFETY},
    )
    assert result.is_valid
    assert not result.errors


def test_safety_validation_update_without_where(validator, sample_schema):
    """Test safety validation for UPDATE without WHERE clause."""
    sql = "UPDATE users SET name = 'test';"
    result = validator.validate(
        sql=sql,
        full_schema=sample_schema,
        prompted_schema=None,
        levels={ValidationLevel.SAFETY},
    )
    assert not result.is_valid
    assert len(result.errors) == 1
    assert "WHERE" in result.errors[0].message


def test_safety_validation_delete_without_where(validator, sample_schema):
    """Test safety validation for DELETE without WHERE clause."""
    sql = "DELETE FROM users;"
    result = validator.validate(
        sql=sql,
        full_schema=sample_schema,
        prompted_schema=None,
        levels={ValidationLevel.SAFETY},
    )
    assert not result.is_valid
    assert len(result.errors) == 1
    assert "WHERE" in result.errors[0].message


# Combined validation tests
def test_all_validations_pass(validator, sample_schema):
    """Test that all validation levels pass for valid SQL."""
    sql = "SELECT id, name FROM users WHERE id = 1;"
    result = validator.validate(sql, sample_schema)  # Default: ALL levels
    assert result.is_valid
    assert not result.errors


def test_all_validations_fail(validator, sample_schema):
    """Test multiple validation failures."""
    sql = "DROP TABLE non_existent_table;"
    result = validator.validate(sql, sample_schema)
    assert not result.is_valid
    assert len(result.errors) >= 2  # Should fail both schema and safety checks


# SchemaContext tests
def test_schema_context_from_dict():
    """Test creating ValidatorSchemaContext from dictionary."""
    schema_dict = {
        "tables": ["users", "orders"],
        "columns_per_table": {"users": ["id", "name"], "orders": ["id", "user_id"]},
        "foreign_keys": {"orders": {"user_id": ("users", "id")}},
    }
    schema = ValidatorSchemaContext(
        tables=set(schema_dict["tables"]),
        columns_per_table={
            table: set(columns)
            for table, columns in schema_dict["columns_per_table"].items()
        },
        foreign_keys=schema_dict["foreign_keys"],
    )
    assert "users" in schema.tables
    assert "id" in schema.columns_per_table["users"]
    assert "orders" in schema.foreign_keys
    assert schema.foreign_keys["orders"]["user_id"] == ("users", "id")


# Edge cases
def test_multiple_statements(validator, sample_schema):
    """Test validation of multiple SQL statements."""
    sql = """
    SELECT id FROM users;
    SELECT id FROM orders;
    """
    result = validator.validate(sql, sample_schema)
    assert result.is_valid
    assert not result.errors


def test_case_insensitive_validation(validator, sample_schema):
    """Test case-insensitive validation."""
    sql = "SELECT ID, NAME from USERS where ID = 1;"
    result = validator.validate(sql, sample_schema)
    assert result.is_valid
    assert not result.errors


def test_validation_with_comments(validator, sample_schema):
    """Test validation of SQL with comments."""
    sql = """
    -- This is a comment
    SELECT id, name
    FROM users  -- Another comment
    WHERE id = 1;
    """
    result = validator.validate(sql, sample_schema)
    assert result.is_valid
    assert not result.errors


def test_computed_columns_and_aliases(validator, full_schema):
    """Test validation of computed columns and their aliases in GROUP BY and ORDER BY."""
    sql = """
    SELECT
        EXTRACT(MONTH FROM u.created_at) AS month,
        SUM(o.total) AS total_amount
    FROM
        users u
    JOIN orders o ON u.id = o.user_id
    GROUP BY
        month
    ORDER BY
        total_amount DESC
    LIMIT 1;
    """
    result = validator.validate(sql, full_schema)
    assert result.is_valid, f"Validation failed with errors: {result.errors}"
    assert not result.errors

    # Test with multiple computed columns and complex expressions
    sql = """
    SELECT
        EXTRACT(MONTH FROM u.created_at) AS month,
        EXTRACT(YEAR FROM u.created_at) AS year,
        SUM(o.total) AS total_amount,
        COUNT(*) AS order_count,
        SUM(o.total) / COUNT(*) AS avg_amount
    FROM
        users u
    JOIN orders o ON u.id = o.user_id
    GROUP BY
        month, year
    ORDER BY
        total_amount DESC,
        avg_amount ASC;
    """
    result = validator.validate(sql, full_schema)
    assert result.is_valid, f"Validation failed with errors: {result.errors}"
    assert not result.errors


def test_context_bypass_detection(validator, full_schema, prompted_schema):
    """Test detection of columns used but not in prompted schema.

    This test verifies that the validator correctly detects when a query uses columns
    that weren't included in the prompted schema. Each unique column usage is counted
    once, regardless of where it appears in the query (SELECT, WHERE, JOIN, etc).

    The bypass score is calculated as:
    (number of unique unprompted columns used) / (total number of unique columns used)
    """
    sql = """
    SELECT u.email, u.name, o.status, o.total
    FROM users u
    JOIN orders o ON u.id = o.user_id
    WHERE u.created_at > '2024-01-01'
    """

    result = validator.validate(
        sql=sql,
        full_schema=full_schema,
        prompted_schema=prompted_schema,
        query_id="test-query-1",
    )

    assert result.is_valid  # Query is valid against full schema
    assert result.context_bypass_info is not None
    assert result.context_bypass_info.is_bypass

    # Verify missing columns are detected
    # Each column should only be counted once, even if used multiple times
    expected_missing = {
        ("users", "email"),
        ("users", "created_at"),
        ("orders", "status"),
    }
    assert set(result.context_bypass_info.used_but_missing_columns) == expected_missing

    # Total unique columns used (7): email, name, status, total, id, user_id, created_at
    # Missing unique columns (3): email, created_at, status
    # Score = 3/7 ≈ 0.429
    assert result.context_bypass_info.bypass_score == pytest.approx(3 / 7)


def test_no_context_bypass(validator, full_schema, prompted_schema):
    """Test when all used columns are in prompted schema."""
    sql = """
    SELECT u.name, o.total
    FROM users u
    JOIN orders o ON u.id = o.user_id
    """

    result = validator.validate(
        sql=sql,
        full_schema=full_schema,
        prompted_schema=prompted_schema,
        query_id="test-query-2",
    )

    assert result.is_valid
    assert result.context_bypass_info is not None
    assert not result.context_bypass_info.is_bypass
    assert len(result.context_bypass_info.used_but_missing_columns) == 0
    assert result.context_bypass_info.bypass_score == 0.0


def test_invalid_table_reference(validator, full_schema, prompted_schema):
    """Test when query references a table not in full schema."""
    sql = """
    SELECT u.name, p.category
    FROM users u
    JOIN products p ON p.user_id = u.id
    """

    result = validator.validate(
        sql=sql,
        full_schema=full_schema,
        prompted_schema=prompted_schema,
        query_id="test-query-3",
    )

    assert not result.is_valid
    assert any(
        e.level == ValidationLevel.SCHEMA and "category" in e.message
        for e in result.errors
    )


def test_computed_columns_not_counted(validator, full_schema, prompted_schema):
    """Test that computed columns don't count in bypass detection."""
    sql = """
    SELECT
        u.name,
        COUNT(*) as order_count,
        SUM(o.total) as total_spent
    FROM users u
    JOIN orders o ON u.id = o.user_id
    GROUP BY u.name
    """

    result = validator.validate(
        sql=sql,
        full_schema=full_schema,
        prompted_schema=prompted_schema,
        query_id="test-query-4",
    )

    assert result.is_valid
    assert result.context_bypass_info is not None
    assert not result.context_bypass_info.is_bypass
    assert len(result.context_bypass_info.used_but_missing_columns) == 0


def test_schema_version_logging(validator, full_schema, prompted_schema):
    """Test that schema version is included in bypass info."""
    # Add metadata to full schema
    full_schema.metadata = {"version": "v1.2.3"}

    sql = "SELECT email FROM users"

    result = validator.validate(
        sql=sql,
        full_schema=full_schema,
        prompted_schema=prompted_schema,
        query_id="test-query-5",
    )

    assert result.is_valid
    assert result.context_bypass_info is not None
    assert result.context_bypass_info.is_bypass
    assert result.context_bypass_info.full_schema_version == "v1.2.3"
