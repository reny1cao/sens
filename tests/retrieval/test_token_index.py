"""Test suite for the TokenIndexBuilder implementation."""

import pytest

from sens.retrieval import CaseFormat, TokenIndex, TokenIndexBuilder


@pytest.fixture
def builder():
    """Fixture providing a TokenIndexBuilder instance."""
    return TokenIndexBuilder()


@pytest.fixture
def sample_tables():
    """Fixture providing a list of sample table names in different formats."""
    return [
        "user_profiles",
        "userSettings",
        "user-preferences",
        "orderHistory",
        "order_items",
        "customer-data",
        "productCatalog",
        "product_variants",
        "shipping_address",
        "paymentMethods",
    ]


def test_build_index(builder, sample_tables):
    """Test basic index building functionality."""
    builder.build_index(sample_tables)

    # Check if all tables were indexed
    indexed_tables = set()
    for table_set in builder.index.token_map.values():
        indexed_tables.update(table_set)

    assert indexed_tables == set(sample_tables)


def test_case_format_detection(builder):
    """Test case format detection for different naming styles."""
    assert builder._detect_case_format("user_profile") == CaseFormat.SNAKE
    assert builder._detect_case_format("userProfile") == CaseFormat.CAMEL
    assert builder._detect_case_format("user-profile") == CaseFormat.KEBAB


def test_tokenization(builder):
    """Test name tokenization for different formats."""
    # Snake case
    assert builder._tokenize("user_profile_data") == ["user", "profile", "data"]

    # Camel case
    assert builder._tokenize("userProfileData") == ["user", "profile", "data"]

    # Kebab case
    assert builder._tokenize("user-profile-data") == ["user", "profile", "data"]


def test_memory_constraints(builder):
    """Test memory limit enforcement."""
    # Generate many table names to exceed memory limit
    large_tables = [
        f"very_long_table_name_{i}_with_lots_of_tokens" for i in range(10000)
    ]

    builder.build_index(large_tables)
    assert builder.index._current_size_bytes <= TokenIndex.MAX_MEMORY_BYTES


def test_lookup_exact_match(builder, sample_tables):
    """Test exact matches in table lookup."""
    builder.build_index(sample_tables)

    matches = builder.guess_tables("user_profiles")
    assert matches[0] == "user_profiles"


def test_lookup_partial_match(builder, sample_tables):
    """Test partial matches in table lookup."""
    builder.build_index(sample_tables)

    # Should match all user-related tables
    matches = builder.guess_tables("user")
    assert len(matches) == 3
    assert all(t.lower().startswith("user") for t in matches)


def test_lookup_case_insensitive(builder, sample_tables):
    """Test case-insensitive matching."""
    builder.build_index(sample_tables)

    # Should match regardless of case
    matches_lower = set(builder.guess_tables("user"))
    matches_upper = set(builder.guess_tables("USER"))
    matches_mixed = set(builder.guess_tables("UsEr"))

    assert matches_lower == matches_upper == matches_mixed


def test_lookup_empty_query(builder, sample_tables):
    """Test behavior with empty query."""
    builder.build_index(sample_tables)
    assert builder.guess_tables("") == []


def test_lookup_no_matches(builder, sample_tables):
    """Test behavior when no matches found."""
    builder.build_index(sample_tables)
    assert builder.guess_tables("nonexistent") == []


def test_token_length_limit(builder):
    """Test handling of very long tokens."""
    very_long_token = "a" * (TokenIndex.MAX_TOKEN_LENGTH + 10)
    tokens = builder._tokenize(very_long_token)

    assert all(len(token) <= TokenIndex.MAX_TOKEN_LENGTH for token in tokens)


def test_structured_logging(builder, caplog):
    """Test structured logging output."""
    builder.build_index(["test_table"])

    # Verify log messages are valid JSON
    import json

    for record in caplog.records:
        try:
            log_entry = json.loads(record.message)
            assert isinstance(log_entry, dict)
            assert "event" in log_entry
            assert "timestamp" in log_entry
        except json.JSONDecodeError:
            pytest.fail("Log message is not valid JSON")
