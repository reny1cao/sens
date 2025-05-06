"""Tests for intent extraction functionality."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from openai import OpenAI

from sens.llm.intent_extractor import IntentExtractor
from sens.llm.models import Intent, QueryType
from sens.settings import get_settings

# Constants for testing
TEST_API_KEY = "test-key"
TEST_MODEL = "openai/gpt-3.5-turbo"
TEST_FALLBACK_MODEL = "openai/gpt-3.5-turbo:free"

# Get settings for model names
settings = get_settings()


@pytest.fixture
def prompt_capture():
    """Fixture to capture and validate prompts sent to OpenAI."""

    class PromptCapture:
        def __init__(self):
            self.last_prompt = None
            self.last_messages = None
            self.attempts = []

        def capture_prompt(self, **kwargs):
            """Capture the messages and model sent to OpenAI."""
            self.last_messages = kwargs.get("messages", [])
            self.last_prompt = (
                self.last_messages[0]["content"] if self.last_messages else None
            )
            self.attempts.append(
                {"model": kwargs.get("model"), "messages": self.last_messages}
            )

        def assert_prompt_contains(self, *expected_contents):
            """Assert that the prompt contains all expected contents."""
            assert self.last_prompt is not None, "No prompt was captured"
            for content in expected_contents:
                assert content in self.last_prompt, f"Expected '{content}' in prompt"

        def assert_schema_substitution(self, schema):
            """Assert that the schema was properly substituted."""
            assert schema.strip() in self.last_prompt, "Schema not properly substituted"

        def assert_question_substitution(self, question):
            """Assert that the question was properly substituted."""
            assert question in self.last_prompt, "Question not properly substituted"

        def assert_model_sequence(self, expected_models):
            """Assert that models were tried in the expected sequence."""
            actual_models = [attempt["model"] for attempt in self.attempts]
            assert (
                actual_models == expected_models
            ), f"Expected model sequence {expected_models}, got {actual_models}"

    return PromptCapture()


@pytest.fixture(autouse=True)
def mock_openai(prompt_capture):
    """
    Module-level fixture to mock OpenAI client.
    autouse=True ensures this is automatically used for all tests.
    """
    with patch("sens.llm.intent_extractor.OpenAI") as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance

        # Capture prompts before returning mock response
        def capture_create(**kwargs):
            prompt_capture.capture_prompt(**kwargs)
            return mock_instance.chat.completions.create.return_value

        mock_instance.chat.completions.create.side_effect = capture_create
        mock.mock_instance = mock_instance
        yield mock_instance


@pytest.fixture
def clean_env(monkeypatch):
    """
    Fixture to provide a clean environment for each test.
    Removes any existing OPENROUTER_API_KEY and restores it after the test.
    """
    # Store original environment
    # original_env = dict(os.environ)  # Removed unused variable

    # Clean environment variables that might affect tests
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    yield

    # Restore original environment (handled automatically by monkeypatch)


@pytest.fixture
def extractor(monkeypatch):
    """Create an IntentExtractor with test config."""
    monkeypatch.setenv("OPENROUTER_API_KEY", TEST_API_KEY)
    return IntentExtractor()


@pytest.fixture
def schema():
    """Sample database schema for testing."""
    return """
    TABLE movie(
        id INTEGER PRIMARY KEY,
        title TEXT,
        release_year INTEGER,
        director_id INTEGER REFERENCES person(id)
    )
    TABLE person(
        id INTEGER PRIMARY KEY,
        name TEXT,
        birth_year INTEGER
    )
    """


def test_aggregation_intent(extractor, schema, mock_openai, prompt_capture):
    """Test extraction of aggregation intent."""
    # Mock the OpenAI response
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content='{"query_type": "aggregation", "tables": ["movie"], "operations": ["COUNT"], "confidence": 0.9}'
            )
        )
    ]
    mock_openai.chat.completions.create.return_value = mock_response

    question = "How many movies were released in 2023?"
    intent = extractor.extract(question, schema)

    # Assert prompt structure and substitutions
    prompt_capture.assert_schema_substitution(schema)
    prompt_capture.assert_question_substitution(question)
    prompt_capture.assert_prompt_contains(
        '"query_type"', '"tables"', '"operations"', '"confidence"'
    )

    # Assert intent parsing
    assert intent.query_type == QueryType.AGGREGATION
    assert "movie" in intent.tables
    assert "COUNT" in [op.upper() for op in intent.operations]
    assert intent.confidence == 0.9


def test_lookup_intent(extractor, schema, mock_openai, prompt_capture):
    """Test extraction of lookup intent."""
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content='{"query_type": "lookup", "tables": ["movie"], "operations": [], "confidence": 0.85}'
            )
        )
    ]
    mock_openai.chat.completions.create.return_value = mock_response

    question = "What is the title of the movie with ID 123?"
    intent = extractor.extract(question, schema)

    # Assert prompt structure and substitutions
    prompt_capture.assert_schema_substitution(schema)
    prompt_capture.assert_question_substitution(question)
    prompt_capture.assert_prompt_contains(
        '"query_type"', '"tables"', '"operations"', '"confidence"'
    )

    # Assert intent parsing
    assert intent.query_type == QueryType.LOOKUP
    assert "movie" in intent.tables
    assert intent.confidence == 0.85


def test_relationship_intent(extractor, schema, mock_openai, prompt_capture):
    """Test extraction of relationship intent."""
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content='{"query_type": "relationship", "tables": ["movie", "person"], "operations": [], "confidence": 0.95}'
            )
        )
    ]
    mock_openai.chat.completions.create.return_value = mock_response

    question = "Who directed the movie 'Inception'?"
    intent = extractor.extract(question, schema)

    # Assert prompt structure and substitutions
    prompt_capture.assert_schema_substitution(schema)
    prompt_capture.assert_question_substitution(question)
    prompt_capture.assert_prompt_contains(
        '"query_type"', '"tables"', '"operations"', '"confidence"'
    )

    # Assert intent parsing
    assert intent.query_type == QueryType.RELATIONSHIP
    assert "movie" in intent.tables
    assert "person" in intent.tables
    assert intent.confidence == 0.95


def test_invalid_json_response(extractor, schema, mock_openai, prompt_capture):
    """Test handling of invalid JSON response."""
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content="This is not valid JSON"))
    ]
    mock_openai.chat.completions.create.return_value = mock_response

    question = "Invalid question"
    with pytest.raises(ValueError):
        extractor.extract(question, schema)

    # Even for invalid responses, the prompt should be properly formed
    prompt_capture.assert_schema_substitution(schema)
    prompt_capture.assert_question_substitution(question)
    prompt_capture.assert_prompt_contains(
        '"query_type"', '"tables"', '"operations"', '"confidence"'
    )


def test_missing_api_key(clean_env):
    """Test initialization without API key."""
    with pytest.raises(ValueError):
        IntentExtractor()


def test_model_override(monkeypatch):
    """Test model override in constructor."""
    monkeypatch.setenv("OPENROUTER_API_KEY", TEST_API_KEY)
    extractor = IntentExtractor(model=TEST_MODEL)
    assert extractor.model == TEST_MODEL


def test_default_model(monkeypatch):
    """Test default model from config."""
    monkeypatch.setenv("OPENROUTER_API_KEY", TEST_API_KEY)
    extractor = IntentExtractor()
    assert extractor.model == settings.intent_extractor.primary_model


def test_model_fallback_success(extractor, schema, mock_openai, prompt_capture):
    """Test successful fallback to secondary model."""

    def mock_completion(**kwargs):
        if kwargs["model"] == settings.intent_extractor.primary_model:
            raise Exception("Primary model failed")
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"query_type": "lookup", "tables": ["movie"], "operations": [], "confidence": 0.8}'
                )
            )
        ]
        return mock_response

    mock_openai.chat.completions.create.side_effect = mock_completion

    # Extract intent - should succeed with fallback model
    intent = extractor.extract("What movies are in the database?", schema)

    # Verify both models were attempted in correct order
    prompt_capture.assert_model_sequence(
        [
            settings.intent_extractor.primary_model,
            settings.intent_extractor.fallback_model,
        ]
    )

    assert intent.query_type == QueryType.LOOKUP
    assert "movie" in intent.tables


def test_model_fallback_all_fail(extractor, schema, mock_openai, prompt_capture):
    """Test handling when all models fail."""

    def mock_completion(**kwargs):
        raise Exception(f"Model {kwargs['model']} failed")

    mock_openai.chat.completions.create.side_effect = mock_completion

    with pytest.raises(Exception):
        extractor.extract("What movies are in the database?", schema)

    # Verify both models were attempted
    prompt_capture.assert_model_sequence(
        [
            settings.intent_extractor.primary_model,
            settings.intent_extractor.fallback_model,
        ]
    )


def test_custom_prompt_path(monkeypatch, tmp_path):
    """Test loading custom prompt from path."""
    monkeypatch.setenv("OPENROUTER_API_KEY", TEST_API_KEY)

    # Create test prompt file
    prompt_path = tmp_path / "test_prompt.txt"
    prompt_path.write_text("Test prompt template")

    extractor = IntentExtractor(prompt_path=prompt_path)
    assert extractor.template == "Test prompt template"


def test_invalid_prompt_path():
    """Test error on invalid prompt path."""
    with pytest.raises(FileNotFoundError) as exc_info:
        IntentExtractor(prompt_path=Path("/nonexistent/prompt.txt"))
    assert "Custom prompt not found" in str(exc_info.value)


def test_model_override_sequence(monkeypatch):
    """Test model override affects the fallback sequence."""
    monkeypatch.setenv("OPENROUTER_API_KEY", TEST_API_KEY)
    custom_models = ["custom-model-1", "custom-model-2"]
    extractor = IntentExtractor(models=custom_models)
    assert extractor.models == custom_models


def test_default_model_sequence(monkeypatch):
    """Test default model sequence from config."""
    monkeypatch.setenv("OPENROUTER_API_KEY", TEST_API_KEY)
    extractor = IntentExtractor()
    expected_models = settings.get_models_for("intent_extractor")
    assert extractor.models == expected_models
