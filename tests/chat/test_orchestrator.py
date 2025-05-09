"""Tests for the ChatOrchestrator class."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai import OpenAI

from sens.chat.exceptions import (
    IntentExtractionError,
    ResponseBuildingError,
    SchemaRetrievalError,
    SQLExecutionError,
    SQLGenerationError,
    SQLValidationError,
)
from sens.chat.orchestrator import ChatOrchestrator
from sens.chat.state import ClarificationRequest, ConversationState
from sens.execution.types import QueryResult
from sens.llm.intent_validator import ValidIntent
from sens.llm.models import GeneratedSQL, Intent, QueryType, TokenUsage
from sens.postprocessing.response_builder import FinalResponse
from sens.retrieval.models import RetrievedContext


@pytest.fixture
def mock_components():
    """Create mock components for testing."""
    retrieval_mock = AsyncMock()
    retrieval_mock.get_relevant_context.return_value = RetrievedContext(
        query="test query",
        tables=[],
        columns=[],
    )

    intent_extractor_mock = AsyncMock()
    sql_generator_mock = AsyncMock()

    return {
        "token_index": MagicMock(),
        "embedding_search": MagicMock(),
        "schema_graph": MagicMock(),
        "retrieval": retrieval_mock,
        "intent_extractor": intent_extractor_mock,
        "intent_validator": MagicMock(),
        "sql_generator": sql_generator_mock,
        "sql_validator": MagicMock(),
        "sql_executor": MagicMock(),
        "response_builder": MagicMock(),
    }


@pytest.fixture
def orchestrator(mock_components, monkeypatch):
    """Create a ChatOrchestrator with mocked components."""
    # Mock SchemaGraph.get_instance
    monkeypatch.setattr(
        "sens.schema.graph.SchemaGraph.get_instance",
        lambda: mock_components["schema_graph"],
    )

    # Mock TokenIndexBuilder and EmbeddingSearch constructors
    monkeypatch.setattr(
        "sens.retrieval.token.builder.TokenIndexBuilder",
        lambda: mock_components["token_index"],
    )
    monkeypatch.setattr(
        "sens.retrieval.embedding.search.EmbeddingSearch",
        lambda: mock_components["embedding_search"],
    )

    # Create orchestrator with mocked dependencies
    orchestrator = ChatOrchestrator(conversation_id="test-123")

    # Replace the automatically created RetrievalOrchestrator with our mock
    orchestrator.retrieval = mock_components["retrieval"]

    # Replace other components with mocks
    orchestrator.intent_extractor = mock_components["intent_extractor"]
    orchestrator.intent_validator = mock_components["intent_validator"]
    orchestrator.sql_generator = mock_components["sql_generator"]
    orchestrator.sql_validator = mock_components["sql_validator"]
    orchestrator.sql_executor = mock_components["sql_executor"]
    orchestrator.response_builder = mock_components["response_builder"]

    return orchestrator


@pytest.mark.asyncio
async def test_successful_query_flow(orchestrator, mock_components):
    """Test successful end-to-end query processing."""
    # Setup mock returns
    intent = Intent(
        query_type=QueryType.LOOKUP,
        tables=["orders"],
        confidence=0.9,
    )
    valid_intent = ValidIntent(
        original_intent=intent,
        enhanced_metadata={
            "table_relationships": {"orders": {"referenced_tables": []}}
        },
    )
    sql_result = GeneratedSQL(
        sql="SELECT * FROM orders",
        tables_used=["orders"],
        columns_used={"orders": ["id", "date"]},
        token_usage=TokenUsage(prompt_tokens=100, completion_tokens=50),
        model_used="gpt-4",
        generation_ms=1000,
    )
    query_result = QueryResult(
        columns=["id", "date"],
        rows=[[1, "2024-01-01"]],
        row_count=1,
    )
    response = FinalResponse(
        summary="Found 1 order.",
        table_preview=[{"id": 1, "date": "2024-01-01"}],
        row_count=1,
        sql=sql_result.sql,
        execution_time_ms=100.0,
        generated_at=datetime.now(UTC).isoformat(),
        metadata={},
    )

    # Configure mocks with async return values
    mock_components["intent_extractor"].extract.return_value = intent
    mock_components["intent_validator"].validate.return_value = valid_intent
    mock_components["sql_generator"].generate.return_value = sql_result
    mock_components["sql_validator"].validate.return_value = MagicMock(
        is_valid=True, error=None
    )
    mock_components["sql_executor"].execute.return_value = query_result
    mock_components["response_builder"].build.return_value = response

    # Run test
    result = await orchestrator.step("Show me recent orders")

    # Verify success response
    assert result["status"] == "success"
    assert result["sql"] == "SELECT * FROM orders"
    assert result["summary"] == "Found 1 order."
    assert len(result["result"]["preview"]) == 1

    # Verify state was updated
    state = orchestrator.get_conversation_state()
    assert len(state.history) == 1
    assert state.last_valid_intent == intent

    # Verify async mocks were called correctly
    mock_components["retrieval"].get_relevant_context.assert_awaited_once()
    mock_components["intent_extractor"].extract.assert_awaited_once()
    mock_components["sql_generator"].generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_clarification_flow(orchestrator, mock_components):
    """Test flow when clarification is needed."""
    # Setup clarification request
    clarification = ClarificationRequest(
        message="Which year would you like to see orders from?",
        reason="missing_temporal_filter",
        suggestions=["Show orders from 2023", "Show orders from last year"],
        context={"understood_tables": ["orders"]},
    )

    # Configure mocks
    mock_components["intent_extractor"].extract.return_value = Intent(
        query_type=QueryType.LOOKUP,
        tables=["orders"],
        confidence=0.7,
    )
    mock_components["intent_validator"].validate.return_value = clarification

    # Run test
    result = await orchestrator.step("Show me old orders")

    # Verify clarification was returned
    assert isinstance(result, ClarificationRequest)
    assert result.message == clarification.message
    assert result.reason == clarification.reason

    # Verify state was updated
    state = orchestrator.get_conversation_state()
    assert len(state.history) == 1
    assert state.pending_clarification == clarification

    # Verify async mocks were called correctly
    mock_components["retrieval"].get_relevant_context.assert_awaited_once()
    mock_components["intent_extractor"].extract.assert_awaited_once()
    assert not mock_components["sql_generator"].generate.called


@pytest.mark.asyncio
async def test_sql_validation_error(orchestrator, mock_components):
    """Test handling of SQL validation errors."""
    # Setup mocks for validation error
    intent = Intent(
        query_type=QueryType.LOOKUP,
        tables=["orders"],
        confidence=0.9,
    )
    valid_intent = ValidIntent(
        original_intent=intent,
        enhanced_metadata={
            "table_relationships": {"orders": {"referenced_tables": []}}
        },
    )
    sql_result = GeneratedSQL(
        sql="INVALID SQL",
        tables_used=["orders"],
        columns_used={},
        model_used="gpt-4",
        generation_ms=1000,
    )

    # Configure mocks
    mock_components["intent_extractor"].extract.return_value = intent
    mock_components["intent_validator"].validate.return_value = valid_intent
    mock_components["sql_generator"].generate.return_value = sql_result
    mock_components["sql_validator"].validate.return_value = MagicMock(
        is_valid=False, error="Invalid SQL syntax"
    )

    # Run test
    result = await orchestrator.step("Show me orders")

    # Verify error response
    assert result["status"] == "error"
    assert "SQL validation failed" in result["message"]
    assert result["sql"] == "INVALID SQL"

    # Verify state was updated
    state = orchestrator.get_conversation_state()
    assert len(state.history) == 1
    assert state.history[0]["response"]["status"] == "error"

    # Verify async mocks were called correctly
    mock_components["retrieval"].get_relevant_context.assert_awaited_once()
    mock_components["intent_extractor"].extract.assert_awaited_once()
    mock_components["sql_generator"].generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_execution_error(orchestrator, mock_components):
    """Test handling of SQL execution errors."""
    # Setup mocks for execution error
    intent = Intent(
        query_type=QueryType.LOOKUP,
        tables=["orders"],
        confidence=0.9,
    )
    valid_intent = ValidIntent(
        original_intent=intent,
        enhanced_metadata={
            "table_relationships": {"orders": {"referenced_tables": []}}
        },
    )
    sql_result = GeneratedSQL(
        sql="SELECT * FROM orders",
        tables_used=["orders"],
        columns_used={"orders": ["id"]},
        model_used="gpt-4",
        generation_ms=1000,
    )
    query_result = QueryResult(
        columns=[],
        rows=[],
        row_count=0,
        error="Table 'orders' does not exist",
    )

    # Configure mocks
    mock_components["intent_extractor"].extract.return_value = intent
    mock_components["intent_validator"].validate.return_value = valid_intent
    mock_components["sql_generator"].generate.return_value = sql_result
    mock_components["sql_validator"].validate.return_value = MagicMock(
        is_valid=True, error=None
    )
    mock_components["sql_executor"].execute.return_value = query_result

    # Run test
    result = await orchestrator.step("Show me orders")

    # Verify error response
    assert result["status"] == "error"
    assert "Query execution failed" in result["message"]
    assert "Table 'orders' does not exist" in result["message"]

    # Verify state was updated
    state = orchestrator.get_conversation_state()
    assert len(state.history) == 1
    assert state.history[0]["response"]["status"] == "error"

    # Verify async mocks were called correctly
    mock_components["retrieval"].get_relevant_context.assert_awaited_once()
    mock_components["intent_extractor"].extract.assert_awaited_once()
    mock_components["sql_generator"].generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_conversation_state_management(monkeypatch, mock_components):
    """Test conversation state initialization and management."""
    # Mock SchemaGraph.get_instance and component constructors
    monkeypatch.setattr(
        "sens.schema.graph.SchemaGraph.get_instance",
        lambda: mock_components["schema_graph"],
    )
    monkeypatch.setattr(
        "sens.retrieval.token.builder.TokenIndexBuilder",
        lambda: mock_components["token_index"],
    )
    monkeypatch.setattr(
        "sens.retrieval.embedding.search.EmbeddingSearch",
        lambda: mock_components["embedding_search"],
    )

    # Test with new conversation
    orchestrator = ChatOrchestrator()
    state = orchestrator.get_conversation_state()
    assert state.conversation_id is not None
    assert len(state.history) == 0

    # Test with existing conversation ID
    orchestrator = ChatOrchestrator(conversation_id="test-123")
    state = orchestrator.get_conversation_state()
    assert state.conversation_id == "test-123"

    # Test with existing state
    existing_state = ConversationState(conversation_id="test-456")
    orchestrator = ChatOrchestrator(state=existing_state)
    state = orchestrator.get_conversation_state()
    assert state.conversation_id == "test-456"
    assert state is existing_state


@pytest.mark.asyncio
async def test_schema_retrieval_error(orchestrator, mock_components):
    """Test handling of schema retrieval errors."""
    # Configure mock to raise an error
    mock_components["retrieval"].get_relevant_context.side_effect = Exception(
        "Database connection failed"
    )

    # Run test
    result = await orchestrator.step("Show me orders")

    # Verify error response
    assert result["status"] == "error"
    assert result["error_type"] == "SchemaRetrievalError"
    assert "Failed to retrieve schema context" in result["message"]
    assert "Database connection failed" in result["message"]
    assert result["details"]["user_input"] == "Show me orders"

    # Verify state was updated
    state = orchestrator.get_conversation_state()
    assert len(state.history) == 1
    assert state.history[0]["response"]["status"] == "error"


@pytest.mark.asyncio
async def test_intent_extraction_error(orchestrator, mock_components):
    """Test handling of intent extraction errors."""
    # Configure mocks
    mock_components["intent_extractor"].extract.side_effect = Exception(
        "Failed to parse intent"
    )

    # Run test
    result = await orchestrator.step("Show me orders")

    # Verify error response
    assert result["status"] == "error"
    assert result["error_type"] == "IntentExtractionError"
    assert "Failed to extract intent" in result["message"]
    assert result["details"]["user_input"] == "Show me orders"

    # Verify state was updated
    state = orchestrator.get_conversation_state()
    assert len(state.history) == 1
    assert state.history[0]["response"]["status"] == "error"


@pytest.mark.asyncio
async def test_sql_generation_error(orchestrator, mock_components):
    """Test handling of SQL generation errors."""
    # Setup successful intent extraction
    intent = Intent(
        query_type=QueryType.LOOKUP,
        tables=["orders"],
        confidence=0.9,
    )
    valid_intent = ValidIntent(
        original_intent=intent,
        enhanced_metadata={
            "table_relationships": {"orders": {"referenced_tables": []}}
        },
    )

    # Configure mocks
    mock_components["intent_extractor"].extract.return_value = intent
    mock_components["intent_validator"].validate.return_value = valid_intent
    mock_components["sql_generator"].generate.side_effect = Exception(
        "Failed to generate SQL"
    )

    # Run test
    result = await orchestrator.step("Show me orders")

    # Verify error response
    assert result["status"] == "error"
    assert result["error_type"] == "SQLGenerationError"
    assert "Failed to generate SQL" in result["message"]
    assert "orders" in result["details"]["intent"]["tables"]

    # Verify state was updated
    state = orchestrator.get_conversation_state()
    assert len(state.history) == 1
    assert state.history[0]["response"]["status"] == "error"


@pytest.mark.asyncio
async def test_sql_validation_error_new_type(orchestrator, mock_components):
    """Test handling of SQL validation errors with new error type."""
    # Setup successful steps before validation
    intent = Intent(
        query_type=QueryType.LOOKUP,
        tables=["orders"],
        confidence=0.9,
    )
    valid_intent = ValidIntent(
        original_intent=intent,
        enhanced_metadata={
            "table_relationships": {"orders": {"referenced_tables": []}}
        },
    )
    sql_result = GeneratedSQL(
        sql="INVALID SQL",
        tables_used=["orders"],
        columns_used={},
        model_used="gpt-4",
        generation_ms=1000,
    )

    # Configure mocks
    mock_components["intent_extractor"].extract.return_value = intent
    mock_components["intent_validator"].validate.return_value = valid_intent
    mock_components["sql_generator"].generate.return_value = sql_result
    mock_components["sql_validator"].validate.return_value = MagicMock(
        is_valid=False,
        error="Invalid SQL syntax",
    )

    # Run test
    result = await orchestrator.step("Show me orders")

    # Verify error response
    assert result["status"] == "error"
    assert result["error_type"] == "SQLValidationError"
    assert "SQL validation failed" in result["message"]
    assert result["details"]["sql"] == "INVALID SQL"
    assert result["details"]["validation_error"] == "Invalid SQL syntax"

    # Verify state was updated
    state = orchestrator.get_conversation_state()
    assert len(state.history) == 1
    assert state.history[0]["response"]["status"] == "error"


@pytest.mark.asyncio
async def test_sql_execution_error(orchestrator, mock_components):
    """Test handling of SQL execution errors with new error type."""
    # Setup successful steps before execution
    intent = Intent(
        query_type=QueryType.LOOKUP,
        tables=["orders"],
        confidence=0.9,
    )
    valid_intent = ValidIntent(
        original_intent=intent,
        enhanced_metadata={
            "table_relationships": {"orders": {"referenced_tables": []}}
        },
    )
    sql_result = GeneratedSQL(
        sql="SELECT * FROM orders",
        tables_used=["orders"],
        columns_used={"orders": ["id"]},
        model_used="gpt-4",
        generation_ms=1000,
    )

    # Configure mocks
    mock_components["intent_extractor"].extract.return_value = intent
    mock_components["intent_validator"].validate.return_value = valid_intent
    mock_components["sql_generator"].generate.return_value = sql_result
    mock_components["sql_validator"].validate.return_value = MagicMock(
        is_valid=True,
        error=None,
    )
    mock_components["sql_executor"].execute.side_effect = Exception(
        "Database connection timeout"
    )

    # Run test
    result = await orchestrator.step("Show me orders")

    # Verify error response
    assert result["status"] == "error"
    assert result["error_type"] == "SQLExecutionError"
    assert "Query execution failed" in result["message"]
    assert result["details"]["sql"] == "SELECT * FROM orders"

    # Verify state was updated
    state = orchestrator.get_conversation_state()
    assert len(state.history) == 1
    assert state.history[0]["response"]["status"] == "error"


@pytest.mark.asyncio
async def test_response_building_error(orchestrator, mock_components):
    """Test handling of response building errors with new error type."""
    # Setup successful steps before response building
    intent = Intent(
        query_type=QueryType.LOOKUP,
        tables=["orders"],
        confidence=0.9,
    )
    valid_intent = ValidIntent(
        original_intent=intent,
        enhanced_metadata={
            "table_relationships": {"orders": {"referenced_tables": []}}
        },
    )
    sql_result = GeneratedSQL(
        sql="SELECT * FROM orders",
        tables_used=["orders"],
        columns_used={"orders": ["id"]},
        model_used="gpt-4",
        generation_ms=1000,
    )
    query_result = QueryResult(
        columns=["id"],
        rows=[[1]],
        row_count=1,
    )

    # Configure mocks
    mock_components["intent_extractor"].extract.return_value = intent
    mock_components["intent_validator"].validate.return_value = valid_intent
    mock_components["sql_generator"].generate.return_value = sql_result
    mock_components["sql_validator"].validate.return_value = MagicMock(
        is_valid=True,
        error=None,
    )
    mock_components["sql_executor"].execute.return_value = query_result
    mock_components["response_builder"].build.side_effect = Exception(
        "Failed to format response"
    )

    # Run test
    result = await orchestrator.step("Show me orders")

    # Verify error response
    assert result["status"] == "error"
    assert result["error_type"] == "ResponseBuildingError"
    assert "Failed to build response" in result["message"]
    assert result["details"]["sql"] == "SELECT * FROM orders"
    assert result["details"]["user_input"] == "Show me orders"

    # Verify state was updated
    state = orchestrator.get_conversation_state()
    assert len(state.history) == 1
    assert state.history[0]["response"]["status"] == "error"


@pytest.mark.asyncio
async def test_unexpected_error(orchestrator, mock_components):
    """Test handling of unexpected errors."""

    class UnexpectedError(Exception):
        pass

    mock_components["retrieval"].get_relevant_context.side_effect = UnexpectedError(
        "Something completely unexpected"
    )

    # Run test
    result = await orchestrator.step("Show me orders")

    # Verify error response
    assert result["status"] == "error"
    assert "error_type" not in result  # Unexpected errors don't get type classification
    assert "An unexpected error occurred" in result["message"]
    assert "Something completely unexpected" in result["message"]

    # Verify state was updated
    state = orchestrator.get_conversation_state()
    assert len(state.history) == 1
    assert state.history[0]["response"]["status"] == "error"


@pytest.mark.asyncio
async def test_successful_query_metrics(orchestrator, mock_components):
    """Test that performance metrics are captured for successful queries."""
    # Setup mock returns (reuse from test_successful_query_flow)
    intent = Intent(
        query_type=QueryType.LOOKUP,
        tables=["orders"],
        confidence=0.9,
    )
    valid_intent = ValidIntent(
        original_intent=intent,
        enhanced_metadata={
            "table_relationships": {"orders": {"referenced_tables": []}}
        },
    )
    sql_result = GeneratedSQL(
        sql="SELECT * FROM orders",
        tables_used=["orders"],
        columns_used={"orders": ["id", "date"]},
        token_usage=TokenUsage(prompt_tokens=100, completion_tokens=50),
        model_used="gpt-4",
        generation_ms=1000,
    )
    query_result = QueryResult(
        columns=["id", "date"],
        rows=[[1, "2024-01-01"]],
        row_count=1,
    )
    response = FinalResponse(
        summary="Found 1 order.",
        table_preview=[{"id": 1, "date": "2024-01-01"}],
        row_count=1,
        sql=sql_result.sql,
        execution_time_ms=100.0,
        generated_at=datetime.now(UTC).isoformat(),
        metadata={},
    )

    # Configure mocks
    mock_components["intent_extractor"].extract.return_value = intent
    mock_components["intent_validator"].validate.return_value = valid_intent
    mock_components["sql_generator"].generate.return_value = sql_result
    mock_components["sql_validator"].validate.return_value = MagicMock(
        is_valid=True, error=None
    )
    mock_components["sql_executor"].execute.return_value = query_result
    mock_components["response_builder"].build.return_value = response

    # Run test
    result = await orchestrator.step("Show me recent orders")

    # Verify metrics in response
    assert "pipeline_metrics" in result["metadata"]
    metrics = result["metadata"]["pipeline_metrics"]
    assert isinstance(metrics["total_duration_ms"], float)
    assert len(metrics["steps"]) == 7  # All pipeline steps should be tracked

    # Verify each step was tracked
    step_names = [step["name"] for step in metrics["steps"]]
    assert "schema_retrieval" in step_names
    assert "intent_extraction" in step_names
    assert "intent_validation" in step_names
    assert "sql_generation" in step_names
    assert "sql_validation" in step_names
    assert "sql_execution" in step_names
    assert "response_building" in step_names

    # Verify step details
    for step in metrics["steps"]:
        assert isinstance(step["duration_ms"], float)
        assert step["success"] is True


@pytest.mark.asyncio
async def test_error_metrics(orchestrator, mock_components):
    """Test that performance metrics are captured when errors occur."""
    # Configure mock to raise an error
    mock_components["sql_generator"].generate.side_effect = Exception(
        "Failed to generate SQL"
    )

    # Setup successful steps before error
    intent = Intent(
        query_type=QueryType.LOOKUP,
        tables=["orders"],
        confidence=0.9,
    )
    valid_intent = ValidIntent(
        original_intent=intent,
        enhanced_metadata={
            "table_relationships": {"orders": {"referenced_tables": []}}
        },
    )

    # Configure mocks for successful steps
    mock_components["intent_extractor"].extract.return_value = intent
    mock_components["intent_validator"].validate.return_value = valid_intent

    # Run test
    result = await orchestrator.step("Show me orders")

    # Verify error response
    assert result["status"] == "error"
    assert result["error_type"] == "SQLGenerationError"

    # Verify metrics in conversation state
    state = orchestrator.get_conversation_state()
    assert len(state.history) == 1
    interaction = state.history[0]

    # Verify steps up to error were tracked
    assert "schema_retrieval" in [
        step["name"]
        for step in interaction["response"]
        .get("metadata", {})
        .get("pipeline_metrics", {})
        .get("steps", [])
    ]
    assert "intent_extraction" in [
        step["name"]
        for step in interaction["response"]
        .get("metadata", {})
        .get("pipeline_metrics", {})
        .get("steps", [])
    ]
    assert "intent_validation" in [
        step["name"]
        for step in interaction["response"]
        .get("metadata", {})
        .get("pipeline_metrics", {})
        .get("steps", [])
    ]


@pytest.mark.asyncio
async def test_clarification_metrics(orchestrator, mock_components):
    """Test that performance metrics are captured when clarification is needed."""
    # Setup clarification request
    clarification = ClarificationRequest(
        message="Which year would you like to see orders from?",
        reason="missing_temporal_filter",
        suggestions=["Show orders from 2023", "Show orders from last year"],
        context={"understood_tables": ["orders"]},
    )

    # Configure mocks
    mock_components["intent_extractor"].extract.return_value = Intent(
        query_type=QueryType.LOOKUP,
        tables=["orders"],
        confidence=0.7,
    )
    mock_components["intent_validator"].validate.return_value = clarification

    # Run test
    result = await orchestrator.step("Show me old orders")

    # Verify clarification was returned
    assert isinstance(result, ClarificationRequest)
    assert result.message == clarification.message

    # Verify state was updated with metrics
    state = orchestrator.get_conversation_state()
    assert len(state.history) == 1
    interaction = state.history[0]

    # Verify steps up to clarification were tracked
    assert "schema_retrieval" in [
        step["name"]
        for step in interaction["response"]
        .get("metadata", {})
        .get("pipeline_metrics", {})
        .get("steps", [])
    ]
    assert "intent_extraction" in [
        step["name"]
        for step in interaction["response"]
        .get("metadata", {})
        .get("pipeline_metrics", {})
        .get("steps", [])
    ]
    assert "intent_validation" in [
        step["name"]
        for step in interaction["response"]
        .get("metadata", {})
        .get("pipeline_metrics", {})
        .get("steps", [])
    ]
