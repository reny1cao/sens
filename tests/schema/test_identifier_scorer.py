"""Unit tests for the identifier scorer module."""

import pytest

from sens.schema import ColumnInfo, DatabaseSchema, IdentifierScorer, TableInfo
from sens.schema.schema_extractor import ForeignKeyColumnPair, ForeignKeyConstraint


def test_score_column_name_patterns():
    """Test scoring based on column name patterns."""
    scorer = IdentifierScorer()

    # Test cases with different name patterns
    test_cases = [
        ("title", 3.0, "Should match title pattern (+3)", "integer"),
        (
            "display_name",
            6.0,
            "Should match both display and name patterns (+6)",
            "integer",
        ),
        ("movie_title", 3.0, "Should match title pattern (+3)", "integer"),
        ("created_at", -3.0, "Should be down-ranked as system field (-3)", "timestamp"),
        ("id", -3.0, "Should be down-ranked as technical field (-3)", "integer"),
        ("description", 3.0, "Should match description pattern (+3)", "integer"),
        # Cases with string type bonus
        (
            "title",
            5.0,
            "Should match title pattern (+3) and string type (+2)",
            "varchar",
        ),
        (
            "description",
            5.0,
            "Should match description pattern (+3) and string type (+2)",
            "varchar",
        ),
    ]

    for name, expected_score, message, data_type in test_cases:
        column = ColumnInfo(
            name=name,
            data_type=data_type,
            is_nullable=True,
        )
        table = TableInfo(
            name="test_table",
            columns=[column],
            primary_keys=[],
            foreign_keys=[],
        )

        score = scorer.score_column(column, table)
        assert score.score == pytest.approx(expected_score), message


def test_score_column_description_keywords():
    """Test scoring based on description keywords."""
    scorer = IdentifierScorer()

    # Test cases with different data types and descriptions
    test_cases = [
        # Base scores without string type bonus
        (
            "The primary name for the entity",
            4.0,
            "integer",
        ),  # Matches 'primary' and 'name' (+2 each)
        (
            "Used as identifier for display",
            4.0,
            "integer",
        ),  # Matches 'identifier' and 'display' (+2 each)
        ("Technical metadata field", 0.0, "integer"),  # No keyword matches
        # With string type bonus (+2.0)
        (
            "The primary name for the entity",
            6.0,
            "varchar",
        ),  # 4.0 (keywords) + 2.0 (string)
        (
            "Used as identifier for display",
            6.0,
            "varchar",
        ),  # 4.0 (keywords) + 2.0 (string)
    ]

    for description, expected_score, data_type in test_cases:
        column = ColumnInfo(
            name="test_column",
            data_type=data_type,
            is_nullable=True,
            description=description,
        )
        table = TableInfo(
            name="test_table",
            columns=[column],
            primary_keys=[],
            foreign_keys=[],
        )

        score = scorer.score_column(column, table)
        assert score.score == pytest.approx(
            expected_score
        ), f"Failed for description '{description}' with type {data_type}"


def test_score_column_data_types():
    """Test scoring based on data types."""
    scorer = IdentifierScorer()

    test_cases = [
        ("varchar", 2.0, "String type should get bonus"),
        ("text", 2.0, "Text type should get bonus"),
        ("character varying", 2.0, "Character varying should get bonus"),
        ("integer", 0.0, "Integer should not get bonus"),
        ("timestamp", 0.0, "Timestamp should not get bonus"),
    ]

    for data_type, expected_bonus, message in test_cases:
        column = ColumnInfo(
            name="test_column",
            data_type=data_type,
            is_nullable=True,
        )
        table = TableInfo(
            name="test_table",
            columns=[column],
            primary_keys=[],
            foreign_keys=[],
        )

        score = scorer.score_column(column, table)
        assert score.score == pytest.approx(expected_bonus), message


def test_foreign_key_handling():
    """Test proper handling of foreign key columns."""
    scorer = IdentifierScorer()

    # Create a foreign key column
    fk_column = ColumnInfo(
        name="category_id",
        data_type="integer",
        is_nullable=True,
    )

    # Create foreign key constraint
    fk_constraint = ForeignKeyConstraint(
        constraint_name="fk_test",
        from_table="test_table",
        to_table="categories",
        columns=[ForeignKeyColumnPair(from_column="category_id", to_column="id")],
    )

    table = TableInfo(
        name="test_table",
        columns=[fk_column],
        primary_keys=[],
        foreign_keys=[fk_constraint],
    )

    score = scorer.score_column(fk_column, table)
    assert score.score < 0, "Foreign key should be down-ranked"
    assert "foreign_key" in score.reasons


def test_real_movie_schema():
    """Test with real examples from our movie/TV show schema."""
    scorer = IdentifierScorer()

    # Test movie table columns
    movie_columns = [
        ColumnInfo(
            name="title",
            data_type="character varying",
            is_nullable=False,
            description="The movie title",
        ),
        ColumnInfo(
            name="id",
            data_type="bigint",
            is_nullable=False,
            is_primary=True,
            description="Primary unique identifier",
        ),
        ColumnInfo(
            name="release_date",
            data_type="date",
            is_nullable=True,
            description="Date when this title was released",
        ),
    ]

    movie_table = TableInfo(
        name="movie",
        columns=movie_columns,
        primary_keys=["id"],
        foreign_keys=[],
    )

    # Score each column
    scores = {col.name: scorer.score_column(col, movie_table) for col in movie_columns}

    # Title should be the highest scoring
    assert (
        scores["title"].score > scores["id"].score
    ), "Title should score higher than ID"
    assert (
        scores["title"].score > scores["release_date"].score
    ), "Title should score higher than release_date"

    # Test full schema identification
    schema = DatabaseSchema(
        tables={"movie": movie_table},
        relationships=[],
        metadata={},
    )

    sticky_columns = scorer.identify_sticky_columns(schema)
    assert "movie" in sticky_columns
    assert (
        "title" in sticky_columns["movie"]
    ), "Movie title should be identified as sticky"
    assert (
        len(sticky_columns["movie"]) >= 1
    ), "Should identify at least one sticky column for movies"


def test_identify_sticky_columns():
    """Test the full sticky column identification process."""
    scorer = IdentifierScorer()

    # Create a test schema with multiple tables
    tables = {
        "products": TableInfo(
            name="products",
            columns=[
                ColumnInfo(
                    name="id",
                    data_type="integer",
                    is_nullable=False,
                    is_primary=True,
                ),
                ColumnInfo(
                    name="name",
                    data_type="varchar",
                    is_nullable=False,
                    description="Product name",
                ),
                ColumnInfo(
                    name="description",
                    data_type="text",
                    is_nullable=True,
                    description="Product description",
                ),
            ],
            primary_keys=["id"],
            foreign_keys=[],
        ),
        "categories": TableInfo(
            name="categories",
            columns=[
                ColumnInfo(
                    name="id",
                    data_type="integer",
                    is_nullable=False,
                    is_primary=True,
                ),
                ColumnInfo(
                    name="title",
                    data_type="varchar",
                    is_nullable=False,
                    description="Category title",
                ),
            ],
            primary_keys=["id"],
            foreign_keys=[],
        ),
    }

    schema = DatabaseSchema(
        tables=tables,
        relationships=[],
        metadata={},
    )

    sticky_columns = scorer.identify_sticky_columns(schema)

    # Verify results
    assert "products" in sticky_columns
    assert "categories" in sticky_columns
    assert "name" in sticky_columns["products"], "Product name should be sticky"
    assert "title" in sticky_columns["categories"], "Category title should be sticky"

    # Check ordering (name should come before description for products)
    if len(sticky_columns["products"]) > 1:
        assert sticky_columns["products"].index("name") < sticky_columns[
            "products"
        ].index("description"), "Name should be ranked higher than description"
