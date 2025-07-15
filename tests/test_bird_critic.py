"""Test script for BIRD-CRITIC evaluation functionality."""

from pathlib import Path

import pytest

from sens.evaluation.bird_critic import BirdCriticEvaluator, BirdCriticTask
from sens.evaluation.bird_db_setup import BirdDatabaseSetup
from sens.settings import get_settings


def test_bird_critic_task_creation():
    """Test basic BirdCriticTask creation."""
    task = BirdCriticTask(
        instance_id="test_1",
        db_id="financial",
        query="How many accounts are there?",
        issue_sql="SELECT COUNT() FROM account",
        sol_sql="SELECT COUNT(*) FROM account",
    )

    assert task.instance_id == "test_1"
    assert task.db_id == "financial"
    assert task.query == "How many accounts are there?"
    assert task.issue_sql == "SELECT COUNT() FROM account"
    assert task.sol_sql == "SELECT COUNT(*) FROM account"


def test_database_setup_initialization():
    """Test BirdDatabaseSetup initialization."""
    settings = get_settings()

    # Test with default dumps directory (should fail if not cloned)
    try:
        setup = BirdDatabaseSetup(settings)
        # If we get here, the external directory exists
        dumps = setup.list_available_dumps()
        assert isinstance(dumps, list)
    except FileNotFoundError:
        # This is expected if the BIRD-CRITIC repo hasn't been cloned
        pytest.skip("BIRD-CRITIC repository not cloned")


def test_evaluator_initialization():
    """Test BirdCriticEvaluator initialization."""
    settings = get_settings()

    # Test without schema file (should still work but with empty schema mapping)
    evaluator = BirdCriticEvaluator(settings)
    assert evaluator.settings == settings
    assert isinstance(evaluator.schema_by_db, dict)
    assert isinstance(evaluator.tasks, list)


def test_schema_file_loading():
    """Test loading schema mapping from JSONL file."""
    settings = get_settings()
    schema_file = "external/BIRD-CRITIC-1/baseline/data/post_schema.jsonl"

    if not Path(schema_file).exists():
        pytest.skip("Schema file not found - run setup first")

    evaluator = BirdCriticEvaluator(settings, schema_file_path=schema_file)

    # Should have loaded some schemas
    assert len(evaluator.schema_by_db) > 0

    # Check that schema entries are strings (DDL statements)
    for db_id, schema in evaluator.schema_by_db.items():
        assert isinstance(schema, str)
        assert "CREATE TABLE" in schema or schema == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
