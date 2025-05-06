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


class LLMClientMock(MagicMock):
    """Enhanced mock for OpenAI client with helper methods for test configuration."""

    def __init__(self, *args, **kwargs):
        """Initialize the mock with test-specific state tracking."""
        super().__init__(*args, **kwargs)
        self._test_side_effect = None
        self._test_return_value = None

    def set_chat_create_side_effect(self, side_effect):
        """Set test-specific side effect for chat.completions.create."""
        self._test_side_effect = side_effect
        self._test_return_value = None

    def set_chat_create_return_value(self, return_value):
        """Set test-specific return value for chat.completions.create."""
        self._test_return_value = return_value
        self._test_side_effect = None

    def _handle_chat_create(self, **kwargs):
        """Internal handler for chat.completions.create calls."""
        if self._test_side_effect:
            return self._test_side_effect(**kwargs)
        return self._test_return_value


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

        def reset(self):
            """Reset the capture state."""
            self.last_prompt = None
            self.last_messages = None
            self.attempts = []

    return PromptCapture()


@pytest.fixture(autouse=True)
def mock_openai(prompt_capture):
    """
    Module-level fixture to mock OpenAI client.
    autouse=True ensures this is automatically used for all tests.
    """
    with patch("sens.llm.intent_extractor.OpenAI") as mock:
        # Create enhanced mock instance
        mock_instance = LLMClientMock()
        mock.return_value = mock_instance

        def capture_and_delegate(**kwargs):
            """Capture prompt and delegate to test-specific behavior."""
            prompt_capture.capture_prompt(**kwargs)
            return mock_instance._handle_chat_create(**kwargs)

        # Install the capturing wrapper
        mock_instance.chat.completions.create = MagicMock(
            side_effect=capture_and_delegate
        )

        yield mock_instance

        # Reset state after each test
        prompt_capture.reset()
        mock_instance._test_side_effect = None
        mock_instance._test_return_value = None


def create_mock_response(content):
    """Helper to create a mock OpenAI response with given content."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content=content))]
    return mock_response


@pytest.fixture
def clean_env(monkeypatch):
    """
    Fixture to provide a clean environment for each test.
    Removes any existing API keys and restores them after the test.
    """
    # Clean environment variables that might affect tests
    monkeypatch.delenv("SENS_OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    yield


@pytest.fixture
def extractor(monkeypatch):
    """Create an IntentExtractor with test config."""
    monkeypatch.setenv("SENS_OPENROUTER_API_KEY", TEST_API_KEY)
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
    mock_openai.set_chat_create_return_value(
        create_mock_response(
            '{"query_type": "aggregation", "tables": ["movie"], "operations": ["COUNT"], "confidence": 0.9}'
        )
    )

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
    mock_openai.set_chat_create_return_value(
        create_mock_response(
            '{"query_type": "lookup", "tables": ["movie"], "operations": [], "confidence": 0.85}'
        )
    )

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
    mock_openai.set_chat_create_return_value(
        create_mock_response(
            '{"query_type": "relationship", "tables": ["movie", "person"], "operations": [], "confidence": 0.95}'
        )
    )

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
    mock_openai.set_chat_create_return_value(
        create_mock_response("This is not valid JSON")
    )

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
    monkeypatch.setenv("SENS_OPENROUTER_API_KEY", TEST_API_KEY)
    extractor = IntentExtractor(model=TEST_MODEL)
    assert extractor.model == TEST_MODEL


def test_default_model(monkeypatch):
    """Test default model from config."""
    monkeypatch.setenv("SENS_OPENROUTER_API_KEY", TEST_API_KEY)
    extractor = IntentExtractor()
    assert extractor.model == settings.intent_extractor.primary_model


def test_model_fallback_success(extractor, schema, mock_openai, prompt_capture):
    """Test successful fallback to secondary model."""

    def mock_completion(**kwargs):
        if kwargs["model"] == settings.intent_extractor.primary_model:
            raise Exception("Primary model failed")
        return create_mock_response(
            '{"query_type": "lookup", "tables": ["movie"], "operations": [], "confidence": 0.8}'
        )

    mock_openai.set_chat_create_side_effect(mock_completion)

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

    mock_openai.set_chat_create_side_effect(mock_completion)

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
    monkeypatch.setenv("SENS_OPENROUTER_API_KEY", TEST_API_KEY)

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
    monkeypatch.setenv("SENS_OPENROUTER_API_KEY", TEST_API_KEY)
    custom_models = ["custom-model-1", "custom-model-2"]
    extractor = IntentExtractor(models=custom_models)
    assert extractor.models == custom_models


def test_default_model_sequence(monkeypatch):
    """Test default model sequence from config."""
    monkeypatch.setenv("SENS_OPENROUTER_API_KEY", TEST_API_KEY)
    extractor = IntentExtractor()
    expected_models = settings.get_models_for("intent_extractor")
    assert extractor.models == expected_models


def test_custom_prompt_loading_nonexistent(tmp_path):
    """Test loading a nonexistent custom prompt file."""
    nonexistent_path = tmp_path / "nonexistent.txt"
    with pytest.raises(FileNotFoundError) as exc_info:
        IntentExtractor(prompt_path=nonexistent_path)
    assert "Custom prompt not found" in str(exc_info.value)


def test_json_response_with_markdown(extractor, schema, mock_openai):
    """Test handling of JSON response wrapped in markdown code blocks."""
    mock_openai.set_chat_create_return_value(
        create_mock_response(
            '```json\n{"query_type": "lookup", "tables": ["movie"], "operations": [], "confidence": 0.85}\n```'
        )
    )

    question = "What movies are in the database?"
    intent = extractor.extract(question, schema)
    assert intent.query_type == QueryType.LOOKUP
    assert "movie" in intent.tables


def test_json_response_without_markdown(extractor, schema, mock_openai):
    """Test handling of plain JSON response."""
    mock_openai.set_chat_create_return_value(
        create_mock_response(
            '{"query_type": "lookup", "tables": ["movie"], "operations": [], "confidence": 0.85}'
        )
    )

    question = "What movies are in the database?"
    intent = extractor.extract(question, schema)
    assert intent.query_type == QueryType.LOOKUP
    assert "movie" in intent.tables


def test_model_sequence_all_fail(extractor, schema, mock_openai, prompt_capture):
    """Test handling when all models in sequence fail."""

    def mock_completion(**kwargs):
        raise Exception(f"Model {kwargs['model']} failed with invalid JSON")

    mock_openai.set_chat_create_side_effect(mock_completion)

    with pytest.raises(ValueError) as exc_info:
        extractor.extract("What movies are there?", schema)

    assert "Failed to extract intent" in str(exc_info.value)
    assert len(prompt_capture.attempts) == len(extractor.models)


def test_empty_model_sequence():
    """Test initialization with empty model sequence."""
    with pytest.raises(ValueError) as exc_info:
        IntentExtractor(models=[])
    assert "At least one model must be specified" in str(exc_info.value)


def test_invalid_schema_format(extractor):
    """Test handling of invalid schema format."""
    invalid_schemas = [
        "NOT A SCHEMA",
        "TABLE",
        "TABLE ()",
        "TABLE name",
    ]

    for schema in invalid_schemas:
        with pytest.raises(ValueError) as exc_info:
            extractor.extract("What data is available?", schema)
        assert "Invalid schema format" in str(exc_info.value)


def test_whitespace_handling(extractor, mock_openai):
    """Test handling of whitespace in inputs."""
    mock_openai.set_chat_create_return_value(
        create_mock_response(
            '{"query_type": "lookup", "tables": ["movie"], "operations": [], "confidence": 0.85}'
        )
    )

    schema = """
        TABLE movie(
            id INTEGER PRIMARY KEY
        )
    """

    # Test various whitespace combinations
    questions = [
        "  What movies?  ",  # Leading/trailing spaces
        "\nWhat movies?\n",  # Newlines
        "\t\tWhat movies?\t\t",  # Tabs
    ]

    for question in questions:
        intent = extractor.extract(question, schema)
        assert intent.query_type == QueryType.LOOKUP
        assert "movie" in intent.tables
