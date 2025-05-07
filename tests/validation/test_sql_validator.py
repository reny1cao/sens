"""Tests for the SQL Validator module."""

import pytest

from sens.validation.sql_validator import (
    SchemaContext,
    SQLValidator,
    ValidatedSQL,
    ValidationError,
    ValidationLevel,
)


# Test fixtures
@pytest.fixture
def sample_schema():
    """Create a sample schema for testing."""
    return SchemaContext(
        tables={"users", "orders"},
        columns_per_table={
            "users": {"id", "name", "email"},
            "orders": {"id", "user_id", "product_id", "quantity"},
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
    result = validator.validate(sql, SchemaContext(set(), {}), {ValidationLevel.SYNTAX})
    assert result.is_valid
    assert not result.errors


def test_syntax_validation_invalid_sql(validator):
    """Test syntax validation with invalid SQL."""
    sql = "SELEC * FORM users"  # Intentional typos
    result = validator.validate(sql, SchemaContext(set(), {}), {ValidationLevel.SYNTAX})
    assert not result.is_valid
    assert len(result.errors) > 0
    assert all(error.level == ValidationLevel.SYNTAX for error in result.errors)


def test_empty_sql(validator):
    """Test validation of empty SQL."""
    sql = ""
    result = validator.validate(sql, SchemaContext(set(), {}), {ValidationLevel.SYNTAX})
    assert not result.is_valid
    assert len(result.errors) == 1
    assert result.errors[0].level == ValidationLevel.SYNTAX


# Schema validation tests
def test_schema_validation_valid(validator, sample_schema):
    """Test schema validation with valid table and column references."""
    sql = "SELECT id, name FROM users WHERE email = 'test@example.com';"
    result = validator.validate(sql, sample_schema, {ValidationLevel.SCHEMA})
    assert result.is_valid
    assert not result.errors


def test_schema_validation_invalid_table(validator, sample_schema):
    """Test schema validation with non-existent table."""
    sql = "SELECT id FROM non_existent_table;"
    result = validator.validate(sql, sample_schema, {ValidationLevel.SCHEMA})
    assert not result.is_valid
    assert len(result.errors) == 1
    assert "non_existent_table" in result.errors[0].message.lower()


def test_schema_validation_invalid_column(validator, sample_schema):
    """Test schema validation with non-existent column."""
    sql = "SELECT id, non_existent_column FROM users;"
    result = validator.validate(sql, sample_schema, {ValidationLevel.SCHEMA})
    assert not result.is_valid
    assert len(result.errors) == 1
    assert "non_existent_column" in result.errors[0].message.lower()


def test_schema_validation_qualified_names(validator, sample_schema):
    """Test schema validation with qualified column names."""
    sql = "SELECT users.id, users.name FROM users;"
    result = validator.validate(sql, sample_schema, {ValidationLevel.SCHEMA})
    assert result.is_valid
    assert not result.errors


# Safety validation tests
def test_safety_validation_forbidden_keywords(validator, sample_schema):
    """Test safety validation with forbidden keywords."""
    sql = "DROP TABLE users;"
    result = validator.validate(sql, sample_schema, {ValidationLevel.SAFETY})
    assert not result.is_valid
    assert len(result.errors) == 1
    assert result.errors[0].level == ValidationLevel.SAFETY
    assert "DROP" in result.errors[0].message


def test_safety_validation_whitelisted_keywords():
    """Test safety validation with whitelisted keywords."""
    validator = SQLValidator(whitelisted_keywords={"DELETE"})
    sql = "DELETE FROM users WHERE id = 1;"
    result = validator.validate(sql, SchemaContext(set(), {}), {ValidationLevel.SAFETY})
    assert result.is_valid
    assert not result.errors


def test_safety_validation_update_without_where(validator, sample_schema):
    """Test safety validation for UPDATE without WHERE clause."""
    sql = "UPDATE users SET name = 'test';"
    result = validator.validate(sql, sample_schema, {ValidationLevel.SAFETY})
    assert not result.is_valid
    assert len(result.errors) == 1
    assert "WHERE" in result.errors[0].message


def test_safety_validation_delete_without_where(validator, sample_schema):
    """Test safety validation for DELETE without WHERE clause."""
    sql = "DELETE FROM users;"
    result = validator.validate(sql, sample_schema, {ValidationLevel.SAFETY})
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
    """Test creating SchemaContext from dictionary."""
    schema_dict = {
        "tables": ["users", "orders"],
        "columns_per_table": {"users": ["id", "name"], "orders": ["id", "user_id"]},
        "foreign_keys": {"orders": {"user_id": ("users", "id")}},
    }
    schema = SchemaContext.from_dict(schema_dict)
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
