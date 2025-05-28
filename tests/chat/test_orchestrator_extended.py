import uuid
from datetime import datetime
from typing import Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sens.chat.exceptions import (
    IntentExtractionError,
    ResponseBuildingError,
    SchemaRetrievalError,
    SQLExecutionError,
    SQLGenerationError,
    SQLValidationError,
)
from sens.chat.orchestrator import ChatOrchestrator
from sens.chat.state import ConversationState
from sens.execution.types import QueryResult
from sens.llm.intent_validator import ClarificationRequest, ValidIntent
from sens.llm.models import GeneratedSQL, Intent
from sens.postprocessing.response_builder import FinalResponse
from sens.retrieval.models import RetrievedColumn, RetrievedContext, RetrievedTable
from sens.schema.context import ValidatorSchemaContext
from sens.validation.sql_validator import ValidatedSQL, ValidationError, ValidationLevel


class TestChatOrchestrator:
    """Test suite for ChatOrchestrator."""

    @pytest.fixture
    def mock_session_manager(self):
        """Create a mock session manager."""
        mock = MagicMock()
        mock.save = MagicMock()
        return mock

    @pytest.fixture
    def mock_retrieval(self):
        """Create a mock retrieval component."""
        mock = MagicMock()
        mock.get_relevant_context = AsyncMock()
        return mock

    @pytest.fixture
    def mock_intent_extractor(self):
        """Create a mock intent extractor."""
        mock = MagicMock()
        mock.extract = AsyncMock()
        return mock

    @pytest.fixture
    def mock_intent_validator(self):
        """Create a mock intent validator."""
        mock = MagicMock()
        mock.validate = MagicMock()
        return mock

    @pytest.fixture
    def mock_sql_generator(self):
        """Create a mock SQL generator."""
        mock = MagicMock()
        mock.generate = AsyncMock()
        return mock

    @pytest.fixture
    def mock_sql_validator(self):
        """Create a mock SQL validator."""
        mock = MagicMock()
        mock.validate = MagicMock()
        return mock

    @pytest.fixture
    def mock_sql_executor(self):
        """Create a mock SQL executor."""
        mock = MagicMock()
        mock.execute = MagicMock()
        return mock

    @pytest.fixture
    def mock_response_builder(self):
        """Create a mock response builder."""
        mock = MagicMock()
        mock.build = MagicMock()
        return mock

    @pytest.fixture
    def mock_context_builder(self):
        """Create a mock context builder."""
        mock = MagicMock()
        mock.build_from_retrieval = MagicMock()
        return mock

    @pytest.fixture
    def orchestrator(
        self,
        mock_session_manager,
        mock_retrieval,
        mock_intent_extractor,
        mock_intent_validator,
        mock_sql_generator,
        mock_sql_validator,
        mock_sql_executor,
        mock_response_builder,
        mock_context_builder,
    ):
        """Create a ChatOrchestrator instance with mocked dependencies."""
        with patch("sens.chat.orchestrator.SchemaGraph.get_instance"):
            with patch("sens.chat.orchestrator.ChatTokenIndexAdapter"):
                with patch("sens.chat.orchestrator.ChatEmbeddingAdapter"):
                    with patch("sens.chat.orchestrator.IntentExtractor"):
                        with patch("sens.chat.orchestrator.IntentValidator"):
                            with patch("sens.chat.orchestrator.SQLGenerator"):
                                with patch("sens.chat.orchestrator.SQLValidator"):
                                    with patch("sens.chat.orchestrator.SQLExecutor"):
                                        with patch(
                                            "sens.chat.orchestrator.ResponseBuilder"
                                        ):
                                            with patch(
                                                "sens.chat.orchestrator.UnifiedSchemaContextBuilder"
                                            ):
                                                orchestrator = ChatOrchestrator(
                                                    session_manager=mock_session_manager,
                                                    use_optimized_retriever=False,
                                                )
                                                orchestrator.retrieval = mock_retrieval
                                                orchestrator.intent_extractor = (
                                                    mock_intent_extractor
                                                )
                                                orchestrator.intent_validator = (
                                                    mock_intent_validator
                                                )
                                                orchestrator.sql_generator = (
                                                    mock_sql_generator
                                                )
                                                orchestrator.sql_validator = (
                                                    mock_sql_validator
                                                )
                                                orchestrator.sql_executor = (
                                                    mock_sql_executor
                                                )
                                                orchestrator.response_builder = (
                                                    mock_response_builder
                                                )
                                                orchestrator.context_builder = (
                                                    mock_context_builder
                                                )
                                                return orchestrator

    @pytest.fixture
    def sample_state(self):
        """Create a sample conversation state."""
        return ConversationState(
            conversation_id=str(uuid.uuid4()),
            started_at=datetime.now(),
        )

    @pytest.fixture
    def sample_context(self):
        """Create a sample retrieved context."""
        return RetrievedContext(
            query="Find users created last month",
            tables=[
                RetrievedTable(
                    table_name="users",
                    reason="direct_hit",
                    metadata={"score": 0.9},
                ),
            ],
            columns=[
                RetrievedColumn(
                    table_name="users",
                    column_name="user_id",
                    score=0.9,
                    source="token",
                ),
                RetrievedColumn(
                    table_name="users",
                    column_name="created_at",
                    score=0.8,
                    source="token",
                ),
            ],
        )

    @pytest.fixture
    def sample_intent(self):
        """Create a sample intent."""
        return Intent(
            query_type="lookup",
            confidence=0.9,
            tables=["users"],
            operations=[],
            conditions=["created_at > '2023-12-01'"],
        )

    @pytest.fixture
    def sample_validation_result(self, sample_intent):
        """Create a sample validation result."""
        return ValidIntent(
            original_intent=sample_intent,
            enhanced_metadata={},
        )

    @pytest.mark.asyncio
    async def test_successful_pipeline(
        self,
        orchestrator,
        sample_state,
        sample_context,
        sample_intent,
        sample_validation_result,
    ):
        """Test successful end-to-end pipeline execution."""
        # Setup mocks
        orchestrator.retrieval.get_relevant_context.return_value = sample_context
        orchestrator.intent_extractor.extract.return_value = sample_intent
        orchestrator.intent_validator.validate.return_value = sample_validation_result

        # Mock SQL generation
        sql_result = GeneratedSQL(
            sql="SELECT * FROM users WHERE created_at > '2023-12-01'",
            tables_used=["users"],
            columns_used={"users": ["user_id", "created_at"]},
            model_used="gpt-4",
            generation_ms=150,
        )
        orchestrator.sql_generator.generate.return_value = sql_result

        # Mock SQL validation
        sql_validation = ValidatedSQL(
            sql=sql_result.sql,
            is_valid=True,
            errors=[],
            warnings=[],
        )
        orchestrator.sql_validator.validate.return_value = sql_validation

        # Mock SQL execution
        query_result = QueryResult(
            rows=[[1, "2023-12-15"]],
            columns=["user_id", "created_at"],
            row_count=1,
            error=None,
        )
        orchestrator.sql_executor.execute.return_value = query_result

        # Mock response building
        response_data = FinalResponse(
            summary="Found 1 user created last month",
            table_preview=query_result.rows,
            row_count=query_result.row_count,
            sql=sql_result.sql,
            execution_time_ms=10.5,
            generated_at=datetime.now().isoformat(),
            metadata={},
        )
        orchestrator.response_builder.build.return_value = response_data

        # Mock context building
        llm_context = "Table: users\nColumns: user_id, created_at"
        validator_context = ValidatorSchemaContext(
            tables={"users"},
            columns_per_table={"users": {"user_id", "created_at"}},
            foreign_keys={},
        )
        orchestrator.context_builder.build_from_retrieval.return_value = (
            llm_context,
            validator_context,
        )

        # Execute
        response, updated_state = await orchestrator.step(
            sample_state, "Find users created last month"
        )

        # Verify
        assert "summary" in response
        assert response["summary"] == "Found 1 user created last month"
        assert "metadata" in response
        assert "pipeline_metrics" in response["metadata"]
        assert len(updated_state.history) == 1
        assert orchestrator.session_manager.save.called

    @pytest.mark.asyncio
    async def test_clarification_request(
        self,
        orchestrator,
        sample_state,
        sample_context,
        sample_intent,
    ):
        """Test handling of clarification requests."""
        # Setup mocks
        orchestrator.retrieval.get_relevant_context.return_value = sample_context
        orchestrator.intent_extractor.extract.return_value = sample_intent

        # Mock validation returning clarification request
        clarification = ClarificationRequest(
            message="Which time period are you interested in?",
            reason="ambiguous_time_filter",
            missing_fields=["time_filter"],
            ambiguous_fields=["created_at"],
        )
        orchestrator.intent_validator.validate.return_value = clarification

        # Execute
        response, updated_state = await orchestrator.step(sample_state, "Find users")

        # Verify
        assert response["status"] == "clarification_needed"
        assert response["message"] == "Which time period are you interested in?"
        assert response.get("suggestions", []) == []
        assert len(updated_state.history) == 1
        assert updated_state.pending_clarification is not None

    @pytest.mark.asyncio
    async def test_schema_retrieval_error(
        self,
        orchestrator,
        sample_state,
    ):
        """Test handling of schema retrieval errors."""
        # Setup mock to raise error
        orchestrator.retrieval.get_relevant_context.side_effect = Exception(
            "Connection timeout"
        )

        # Execute
        response, updated_state = await orchestrator.step(sample_state, "Find users")

        # Verify
        assert response["status"] == "error"
        assert "Failed to retrieve schema context" in response["message"]
        assert response["error_type"] == "SchemaRetrievalError"
        assert len(updated_state.history) == 1

    @pytest.mark.asyncio
    async def test_intent_extraction_error(
        self,
        orchestrator,
        sample_state,
        sample_context,
    ):
        """Test handling of intent extraction errors."""
        # Setup mocks
        orchestrator.retrieval.get_relevant_context.return_value = sample_context
        orchestrator.intent_extractor.extract.side_effect = Exception("LLM API error")

        # Execute
        response, updated_state = await orchestrator.step(sample_state, "Find users")

        # Verify
        assert response["status"] == "error"
        assert "Failed to extract intent" in response["message"]
        assert response["error_type"] == "IntentExtractionError"

    @pytest.mark.asyncio
    async def test_sql_generation_error(
        self,
        orchestrator,
        sample_state,
        sample_context,
        sample_intent,
        sample_validation_result,
    ):
        """Test handling of SQL generation errors."""
        # Setup mocks
        orchestrator.retrieval.get_relevant_context.return_value = sample_context
        orchestrator.intent_extractor.extract.return_value = sample_intent
        orchestrator.intent_validator.validate.return_value = sample_validation_result
        orchestrator.sql_generator.generate.side_effect = Exception("Model overloaded")

        # Mock context building
        orchestrator.context_builder.build_from_retrieval.return_value = (
            "context",
            ValidatorSchemaContext(tables=set(), columns_per_table={}, foreign_keys={}),
        )

        # Execute
        response, updated_state = await orchestrator.step(sample_state, "Find users")

        # Verify
        assert response["status"] == "error"
        assert "Failed to generate SQL" in response["message"]
        assert response["error_type"] == "SQLGenerationError"

    @pytest.mark.asyncio
    async def test_sql_validation_failure(
        self,
        orchestrator,
        sample_state,
        sample_context,
        sample_intent,
        sample_validation_result,
    ):
        """Test handling of SQL validation failures."""
        # Setup mocks
        orchestrator.retrieval.get_relevant_context.return_value = sample_context
        orchestrator.intent_extractor.extract.return_value = sample_intent
        orchestrator.intent_validator.validate.return_value = sample_validation_result

        # Mock SQL generation
        sql_result = GeneratedSQL(
            sql="SELECT * FROM nonexistent_table",
            tables_used=["nonexistent_table"],
            columns_used={},
            model_used="gpt-4",
            generation_ms=100,
        )
        orchestrator.sql_generator.generate.return_value = sql_result

        # Mock SQL validation failure
        sql_validation = ValidatedSQL(
            sql=sql_result.sql,
            is_valid=False,
            errors=[
                ValidationError(
                    level=ValidationLevel.SCHEMA,
                    message="Table 'nonexistent_table' does not exist",
                    details="table: nonexistent_table",
                )
            ],
            warnings=[],
        )
        orchestrator.sql_validator.validate.return_value = sql_validation

        # Mock context building
        orchestrator.context_builder.build_from_retrieval.return_value = (
            "context",
            ValidatorSchemaContext(tables=set(), columns_per_table={}, foreign_keys={}),
        )

        # Execute
        response, updated_state = await orchestrator.step(sample_state, "Find users")

        # Verify
        assert response["status"] == "error"
        assert "SQL validation failed" in response["message"]
        assert response["error_type"] == "SQLValidationError"
        assert "validation_errors" in response["details"]

    @pytest.mark.asyncio
    async def test_sql_execution_error(
        self,
        orchestrator,
        sample_state,
        sample_context,
        sample_intent,
        sample_validation_result,
    ):
        """Test handling of SQL execution errors."""
        # Setup successful pipeline until execution
        orchestrator.retrieval.get_relevant_context.return_value = sample_context
        orchestrator.intent_extractor.extract.return_value = sample_intent
        orchestrator.intent_validator.validate.return_value = sample_validation_result

        sql_result = GeneratedSQL(
            sql="SELECT * FROM users",
            tables_used=["users"],
            columns_used={"users": ["*"]},
            model_used="gpt-4",
            generation_ms=100,
        )
        orchestrator.sql_generator.generate.return_value = sql_result

        sql_validation = ValidatedSQL(
            sql=sql_result.sql, is_valid=True, errors=[], warnings=[]
        )
        orchestrator.sql_validator.validate.return_value = sql_validation

        # Mock execution failure
        query_result = QueryResult(
            rows=[],
            columns=[],
            row_count=0,
            error="Database connection lost",
        )
        orchestrator.sql_executor.execute.return_value = query_result

        # Mock context building
        orchestrator.context_builder.build_from_retrieval.return_value = (
            "context",
            ValidatorSchemaContext(tables=set(), columns_per_table={}, foreign_keys={}),
        )

        # Execute
        response, updated_state = await orchestrator.step(sample_state, "Find users")

        # Verify
        assert response["status"] == "error"
        assert "Query execution failed" in response["message"]
        assert response["error_type"] == "SQLExecutionError"

    @pytest.mark.asyncio
    async def test_pipeline_metrics_tracking(
        self,
        orchestrator,
        sample_state,
        sample_context,
        sample_intent,
        sample_validation_result,
    ):
        """Test that pipeline metrics are properly tracked."""
        # Setup successful pipeline
        orchestrator.retrieval.get_relevant_context.return_value = sample_context
        orchestrator.intent_extractor.extract.return_value = sample_intent
        orchestrator.intent_validator.validate.return_value = sample_validation_result

        sql_result = GeneratedSQL(
            sql="SELECT * FROM users",
            tables_used=["users"],
            columns_used={"users": ["*"]},
            model_used="gpt-4",
            generation_ms=150,
        )
        orchestrator.sql_generator.generate.return_value = sql_result

        sql_validation = ValidatedSQL(
            sql=sql_result.sql, is_valid=True, errors=[], warnings=[]
        )
        orchestrator.sql_validator.validate.return_value = sql_validation

        query_result = QueryResult(
            rows=[[1]],
            columns=["id"],
            row_count=1,
            error=None,
        )
        orchestrator.sql_executor.execute.return_value = query_result

        response_data = FinalResponse(
            summary="Results",
            table_preview=query_result.rows,
            row_count=1,
            sql=sql_result.sql,
            execution_time_ms=10.5,
            generated_at=datetime.now().isoformat(),
            metadata={},
        )
        orchestrator.response_builder.build.return_value = response_data

        orchestrator.context_builder.build_from_retrieval.return_value = (
            "context",
            ValidatorSchemaContext(tables=set(), columns_per_table={}, foreign_keys={}),
        )

        # Execute
        response, _ = await orchestrator.step(sample_state, "Find users")

        # Verify metrics are included
        assert "metadata" in response
        assert "pipeline_metrics" in response["metadata"]
        metrics = response["metadata"]["pipeline_metrics"]
        assert metrics["success"] is True
        assert "steps" in metrics
        assert any(step["name"] == "schema_retrieval" for step in metrics["steps"])
        assert any(step["name"] == "intent_extraction" for step in metrics["steps"])
        assert any(step["name"] == "sql_generation" for step in metrics["steps"])

    @pytest.mark.asyncio
    async def test_optimized_retriever_with_metrics(
        self,
        sample_state,
        mock_session_manager,
    ):
        """Test that optimized retriever receives metrics when available."""
        # Create orchestrator with optimized retriever
        with patch("sens.chat.orchestrator.get_cache_manager"):
            with patch("sens.chat.orchestrator.SchemaGraph.get_instance"):
                with patch("sens.chat.orchestrator.ChatTokenIndexAdapter"):
                    with patch("sens.chat.orchestrator.ChatEmbeddingAdapter"):
                        with patch("sens.chat.orchestrator.IntentExtractor"):
                            with patch("sens.chat.orchestrator.IntentValidator"):
                                with patch("sens.chat.orchestrator.SQLGenerator"):
                                    with patch("sens.chat.orchestrator.SQLValidator"):
                                        with patch(
                                            "sens.chat.orchestrator.SQLExecutor"
                                        ):
                                            with patch(
                                                "sens.chat.orchestrator.ResponseBuilder"
                                            ):
                                                with patch(
                                                    "sens.chat.orchestrator.UnifiedSchemaContextBuilder"
                                                ):
                                                    with patch(
                                                        "sens.chat.orchestrator.OptimizedSchemaRetriever"
                                                    ):
                                                        orchestrator = ChatOrchestrator(
                                                            session_manager=mock_session_manager,
                                                            use_optimized_retriever=True,
                                                        )

        # Mock the optimized retriever
        mock_retriever = MagicMock()
        mock_retriever.get_relevant_context = AsyncMock()
        mock_retriever.get_relevant_context.__code__.co_varnames = [
            "question",
            "metrics",
        ]
        mock_retriever.metrics_collector = MagicMock()
        orchestrator.retrieval = mock_retriever

        # Mock other components to fail early (we're only testing retrieval)
        orchestrator.intent_extractor.extract = AsyncMock(
            side_effect=Exception("Test ended after retrieval")
        )

        # Execute
        response, _ = await orchestrator.step(sample_state, "Find users")

        # Verify metrics were passed to retriever
        mock_retriever.get_relevant_context.assert_called_once()
        call_args = mock_retriever.get_relevant_context.call_args
        assert "metrics" in call_args.kwargs

    @pytest.mark.asyncio
    async def test_unexpected_error_handling(
        self,
        orchestrator,
        sample_state,
    ):
        """Test handling of unexpected errors."""
        # Setup mock to raise unexpected error
        orchestrator.retrieval.get_relevant_context.side_effect = ValueError(
            "Unexpected value error"
        )

        # Execute
        response, updated_state = await orchestrator.step(sample_state, "Find users")

        # Verify
        assert response["status"] == "error"
        assert response["error_type"] == "SchemaRetrievalError"
        assert len(updated_state.history) == 1

    @pytest.mark.asyncio
    async def test_session_persistence(
        self,
        orchestrator,
        sample_state,
        sample_context,
        sample_intent,
    ):
        """Test that session state is properly saved."""
        # Setup for clarification response
        orchestrator.retrieval.get_relevant_context.return_value = sample_context
        orchestrator.intent_extractor.extract.return_value = sample_intent

        clarification = ClarificationRequest(
            message="Please clarify",
            reason="ambiguous",
        )
        orchestrator.intent_validator.validate.return_value = clarification

        # Execute
        _, updated_state = await orchestrator.step(sample_state, "Find data")

        # Verify session was saved
        orchestrator.session_manager.save.assert_called_once_with(
            sample_state.conversation_id, updated_state
        )

    def test_initialization_with_settings(self):
        """Test orchestrator initialization with settings."""
        with patch("sens.chat.orchestrator.get_settings") as mock_settings:
            with patch("sens.chat.orchestrator.SchemaGraph.get_instance"):
                with patch("sens.chat.orchestrator.get_cache_manager"):
                    with patch("sens.chat.orchestrator.ChatTokenIndexAdapter"):
                        with patch("sens.chat.orchestrator.ChatEmbeddingAdapter"):
                            with patch("sens.chat.orchestrator.IntentExtractor"):
                                with patch("sens.chat.orchestrator.IntentValidator"):
                                    with patch("sens.chat.orchestrator.SQLGenerator"):
                                        with patch(
                                            "sens.chat.orchestrator.SQLValidator"
                                        ):
                                            with patch(
                                                "sens.chat.orchestrator.SQLExecutor"
                                            ):
                                                with patch(
                                                    "sens.chat.orchestrator.ResponseBuilder"
                                                ):
                                                    with patch(
                                                        "sens.chat.orchestrator.UnifiedSchemaContextBuilder"
                                                    ):
                                                        with patch(
                                                            "sens.chat.orchestrator.OptimizedSchemaRetriever"
                                                        ):
                                                            orchestrator = ChatOrchestrator(
                                                                use_optimized_retriever=True
                                                            )
                                                            assert (
                                                                orchestrator.settings
                                                                is not None
                                                            )
                                                            mock_settings.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_builder_integration(
        self,
        orchestrator,
        sample_state,
        sample_context,
        sample_intent,
        sample_validation_result,
    ):
        """Test integration with context builder."""
        # Setup mocks
        orchestrator.retrieval.get_relevant_context.return_value = sample_context
        orchestrator.intent_extractor.extract.return_value = sample_intent
        orchestrator.intent_validator.validate.return_value = sample_validation_result

        # Spy on context builder
        llm_context = "LLM formatted context"
        validator_context = ValidatorSchemaContext(
            tables=set(), columns_per_table={}, foreign_keys={}
        )
        orchestrator.context_builder.build_from_retrieval.return_value = (
            llm_context,
            validator_context,
        )

        # Setup rest of pipeline to fail (we're testing context builder call)
        orchestrator.sql_generator.generate.side_effect = Exception("End test")

        # Execute
        await orchestrator.step(sample_state, "Find users")

        # Verify context builder was called correctly
        orchestrator.context_builder.build_from_retrieval.assert_called_once_with(
            retrieved_context=sample_context,
            intent=sample_validation_result,
            include_all_columns=True,
        )
