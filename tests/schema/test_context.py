"""Tests for schema context management."""

import pytest

from sens.schema.context import SchemaContext, TableContext


def test_schema_context_validation():
    """Test schema snippet validation."""
    # Valid cases
    assert SchemaContext.validate_snippet("TABLE users (id, name, email)")
    assert SchemaContext.validate_snippet(
        """
        TABLE users (id, name, email)
        TABLE posts (id, title, content)
    """
    )

    # Invalid cases
    assert not SchemaContext.validate_snippet("")
    assert not SchemaContext.validate_snippet("   ")
    assert not SchemaContext.validate_snippet("TABLE users")  # No columns
    assert not SchemaContext.validate_snippet("TABLE users ()")  # Empty columns
    assert not SchemaContext.validate_snippet(
        "users (id, name)"
    )  # Missing TABLE keyword


def test_table_context():
    """Test TableContext creation and formatting."""
    table = TableContext(
        name="users", columns=["id", "name", "email"], description="User accounts table"
    )
    context = SchemaContext([table])
    formatted = context.format_for_llm()

    assert "TABLE users (id, name, email)" in formatted
    assert "User accounts table" in formatted


def test_empty_tables():
    """Test SchemaContext with empty tables list."""
    with pytest.raises(
        ValueError, match="Schema context must contain at least one table"
    ):
        SchemaContext([])


def test_format_multiple_tables():
    """Test formatting multiple tables."""
    tables = [
        TableContext(name="users", columns=["id", "name"]),
        TableContext(name="posts", columns=["id", "title"], description="Blog posts"),
    ]
    context = SchemaContext(tables)
    formatted = context.format_for_llm()

    assert "TABLE users (id, name)" in formatted
    assert "TABLE posts (id, title)" in formatted
    assert "Blog posts" in formatted
