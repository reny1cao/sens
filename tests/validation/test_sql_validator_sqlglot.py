"""Tests for the SQLValidator with sqlglot implementation."""

import pytest

from sens.schema.context import ValidatorSchemaContext
from sens.validation.sql_validator import SQLValidator, ValidationLevel

# Test schema setup
TEST_SCHEMA = {
    "movie": [
        "id",
        "created_date",
        "modified_date",
        "available_globally",
        "locale",
        "original_title",
        "release_date",
        "runtime",
        "title",
    ],
    "view_summary": [
        "id",
        "created_date",
        "modified_date",
        "cumulative_weeks_in_top10",
        "duration",
        "end_date",
        "hours_viewed",
        "start_date",
        "view_rank",
        "views",
        "movie_id",
        "season_id",
    ],
    "season": [
        "id",
        "created_date",
        "modified_date",
        "original_title",
        "release_date",
        "runtime",
        "season_number",
        "title",
        "tv_show_id",
    ],
}


@pytest.fixture
def schema_context():
    """Create a test schema context."""
    return ValidatorSchemaContext(
        tables=set(TEST_SCHEMA.keys()), columns_per_table=TEST_SCHEMA
    )


@pytest.fixture
def validator():
    """Create a SQLValidator instance."""
    return SQLValidator()


def test_basic_select(validator, schema_context):
    """Test basic SELECT query validation."""
    sql = "SELECT title FROM movie"
    result = validator.validate(sql, schema_context)
    assert result.is_valid
    assert not result.errors


def test_aliased_tables(validator, schema_context):
    """Test validation with table aliases."""
    sql = """
    SELECT m.title, vs.views
    FROM movie m
    JOIN view_summary vs ON vs.movie_id = m.id
    """
    result = validator.validate(sql, schema_context)
    assert result.is_valid
    assert not result.errors


def test_aggregation_with_alias(validator, schema_context):
    """Test validation of aggregated columns with aliases."""
    sql = """
    SELECT
        m.title,
        SUM(vs.views) AS total_views
    FROM
        movie m
    JOIN
        view_summary vs ON vs.movie_id = m.id
    GROUP BY
        m.title
    ORDER BY
        total_views DESC
    LIMIT 10
    """
    result = validator.validate(sql, schema_context)
    assert result.is_valid
    assert not result.errors


def test_invalid_table(validator, schema_context):
    """Test validation with non-existent table."""
    sql = "SELECT * FROM nonexistent_table"
    result = validator.validate(sql, schema_context)
    assert not result.is_valid
    assert len(result.errors) == 1
    assert "Table 'nonexistent_table'" in result.errors[0].message


def test_invalid_column(validator, schema_context):
    """Test validation with non-existent column."""
    sql = "SELECT nonexistent_column FROM movie"
    result = validator.validate(sql, schema_context)
    assert not result.is_valid
    assert len(result.errors) == 1
    assert "Column 'nonexistent_column'" in result.errors[0].message


def test_invalid_column_in_alias(validator, schema_context):
    """Test validation with non-existent column in aliased table."""
    sql = """
    SELECT m.nonexistent_column
    FROM movie m
    """
    result = validator.validate(sql, schema_context)
    assert not result.is_valid
    assert len(result.errors) == 1
    assert "Column 'nonexistent_column'" in result.errors[0].message


def test_complex_query(validator, schema_context):
    """Test validation of a complex query with multiple joins and conditions."""
    sql = """
    SELECT
        m.title,
        s.season_number,
        SUM(vs.views) as total_views,
        AVG(vs.hours_viewed) as avg_hours
    FROM
        movie m
    JOIN
        view_summary vs ON vs.movie_id = m.id
    LEFT JOIN
        season s ON vs.season_id = s.id
    WHERE
        m.available_globally = true
        AND vs.end_date >= '2023-01-01'
    GROUP BY
        m.title, s.season_number
    HAVING
        SUM(vs.views) > 1000000
    ORDER BY
        total_views DESC, avg_hours DESC
    LIMIT 20
    """
    result = validator.validate(sql, schema_context)
    assert result.is_valid
    assert not result.errors


def test_unqualified_column_single_table(validator, schema_context):
    """Test validation of unqualified column with single table."""
    sql = "SELECT title, release_date FROM movie"
    result = validator.validate(sql, schema_context)
    assert result.is_valid
    assert not result.errors


def test_unqualified_column_multiple_tables(validator, schema_context):
    """Test validation of unqualified column with multiple tables."""
    sql = """
    SELECT id  # ambiguous - exists in both tables
    FROM movie m
    JOIN view_summary vs ON vs.movie_id = m.id
    """
    result = validator.validate(sql, schema_context)
    # The validator should either:
    # 1. Flag this as an error due to ambiguity (preferred)
    # 2. Accept it if the column exists in any referenced table
    # Check the actual behavior matches our expectations
    assert not result.is_valid  # We expect this to fail due to ambiguity
    assert any("ambiguous" in error.message.lower() for error in result.errors)


def test_derived_columns(validator, schema_context):
    """Test validation of derived columns and expressions."""
    sql = """
    SELECT
        m.title,
        vs.views + vs.hours_viewed as engagement_score,
        CASE
            WHEN vs.views > 1000000 THEN 'High'
            WHEN vs.views > 100000 THEN 'Medium'
            ELSE 'Low'
        END as popularity
    FROM
        movie m
    JOIN
        view_summary vs ON vs.movie_id = m.id
    """
    result = validator.validate(sql, schema_context)
    assert result.is_valid
    assert not result.errors


def test_subquery(validator, schema_context):
    """Test validation of subqueries."""
    sql = """
    SELECT
        m.title,
        (SELECT AVG(views) FROM view_summary WHERE movie_id = m.id) as avg_views
    FROM
        movie m
    WHERE
        m.release_date >= '2023-01-01'
    """
    result = validator.validate(sql, schema_context)
    assert result.is_valid
    assert not result.errors
