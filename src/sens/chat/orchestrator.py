"""Chat orchestration module for managing the full NL→SQL→Result pipeline."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Dict, Optional, Tuple, Union

import structlog
from openai import OpenAI

from sens.caching.factory import get_cache_manager
from sens.chat.adapters import ChatEmbeddingAdapter, ChatTokenIndexAdapter
from sens.chat.exceptions import (
    ChatError,
    IntentExtractionError,
    ResponseBuildingError,
    SchemaRetrievalError,
    SQLExecutionError,
    SQLGenerationError,
    SQLValidationError,
    UnexpectedError,
)
from sens.chat.session import SessionManager
from sens.chat.state import ClarificationRequest, ConversationState
from sens.execution import SQLExecutor
from sens.llm.intent_extractor import IntentExtractor
from sens.llm.intent_validator import IntentValidator
from sens.llm.models import Intent
from sens.llm.sql_generator import SQLGenerator
from sens.monitoring.metrics import PipelineMetrics, track_step
from sens.postprocessing.response_builder import ResponseBuilder
from sens.retrieval.embedding.search import EmbeddingSearch
from sens.retrieval.optimized_retriever import OptimizedSchemaRetriever
from sens.retrieval.orchestrator import RetrievalOrchestrator
from sens.retrieval.token.builder import TokenIndexBuilder
from sens.schema.graph import SchemaGraph
from sens.schema.unified_context import (
    SchemaContextStrategy,
    UnifiedSchemaContextBuilder,
)
from sens.settings import get_settings
from sens.validation.context_converter import to_validator_schema
from sens.validation.sql_validator import SQLValidator

# Configure structured logging
log = structlog.get_logger()


class ChatOrchestrator:
    """Orchestrates the full pipeline from natural language to SQL results."""

    def __init__(
        self,
        session_manager: Optional[SessionManager] = None,
        use_optimized_retriever: bool = True,
    ):
        """Initialize the chat orchestrator.

        Args:
            session_manager: Optional SessionManager for backward compatibility with existing tests
                           and scripts that don't need explicit state management
            use_optimized_retriever: Whether to use the optimized schema retriever
        """
        self.session_manager = session_manager
        self.settings = get_settings()

        # Initialize all pipeline components
        self.schema_graph = SchemaGraph.get_instance()
        token_index = ChatTokenIndexAdapter()
        embedding_index = ChatEmbeddingAdapter()

        # Initialize retriever based on configuration
        if use_optimized_retriever:
            # Create cache manager for optimized retriever
            cache_manager = get_cache_manager()
            self.retrieval = OptimizedSchemaRetriever(
                token_index=token_index,
                embedding_index=embedding_index,
                schema_graph=self.schema_graph,
                cache_manager=cache_manager,
                enable_caching=True,
            )
            log.info("using_optimized_schema_retriever")
        else:
            self.retrieval = RetrievalOrchestrator(
                token_index=token_index,
                embedding_index=embedding_index,
                schema_graph=self.schema_graph,
            )
            log.info("using_standard_retrieval_orchestrator")

        self.intent_extractor = IntentExtractor()
        self.intent_validator = IntentValidator()
        self.sql_generator = SQLGenerator()
        self.sql_validator = SQLValidator()
        self.sql_executor = SQLExecutor()
        self.response_builder = ResponseBuilder()
        self.context_builder = UnifiedSchemaContextBuilder()
        log.info(
            "chat_orchestrator_initialized", optimized_retriever=use_optimized_retriever
        )

    async def step(
        self, state: ConversationState, user_input: str
    ) -> Tuple[Union[Dict, ClarificationRequest], ConversationState]:
        """Process one step of the conversation.

        Args:
            state: The current conversation state
            user_input: The user's question or input

        Returns:
            A tuple containing:
            - Either a response dictionary or a clarification request
            - The updated conversation state
        """
        metrics = PipelineMetrics(conversation_id=state.conversation_id)
        metrics.metadata["user_input"] = user_input
        retrieval_metrics_collector = None
        try:
            log.info(
                "retrieving_schema_context",
                conversation_id=state.conversation_id,
                user_input=user_input,
            )
            try:
                with track_step(metrics, "schema_retrieval") as step:
                    # Pass metrics to optimized retriever if available
                    if (
                        hasattr(self.retrieval, "get_relevant_context")
                        and "metrics"
                        in self.retrieval.get_relevant_context.__code__.co_varnames
                    ):
                        context = await self.retrieval.get_relevant_context(
                            question=user_input, metrics=metrics
                        )
                    else:
                        context = await self.retrieval.get_relevant_context(
                            question=user_input
                        )
                    step.metadata["table_count"] = len(context.tables)
                    step.metadata["column_count"] = len(context.columns)

                    # Get metrics collector if using optimized retriever
                    if hasattr(self.retrieval, "metrics_collector"):
                        retrieval_metrics_collector = self.retrieval.metrics_collector
            except Exception as e:
                if isinstance(e, ChatError):
                    raise
                if "UnexpectedError" in e.__class__.__name__:
                    metrics.complete(success=False, error=str(e))
                    error_response = {
                        "status": "error",
                        "message": f"An unexpected error occurred: {str(e)}",
                        "metadata": {
                            "pipeline_metrics": metrics.model_dump(),
                        },
                    }
                    state.add_interaction(
                        user_input=user_input,
                        response=error_response,
                    )
                    if self.session_manager:
                        self.session_manager.save(state.conversation_id, state)
                    return error_response, state
                error = SchemaRetrievalError(
                    f"Failed to retrieve schema context: {str(e)}",
                    details={"user_input": user_input},
                )
                metrics.complete(success=False, error=str(error))
                error_response = {
                    "status": "error",
                    "message": str(error),
                    "details": error.details,
                    "error_type": error.__class__.__name__,
                    "metadata": {
                        "pipeline_metrics": metrics.model_dump(),
                    },
                }
                state.add_interaction(
                    user_input=user_input,
                    response=error_response,
                )
                if self.session_manager:
                    self.session_manager.save(state.conversation_id, state)
                return error_response, state
            log.info("extracting_intent")
            try:
                with track_step(metrics, "intent_extraction") as step:
                    intent = await self.intent_extractor.extract(
                        question=user_input,
                        schema_snippet=context,  # Pass the RetrievedContext directly
                    )
                    step.metadata["query_type"] = intent.query_type
                    step.metadata["confidence"] = intent.confidence
                    step.metadata["table_count"] = len(intent.tables)
            except Exception as e:
                if not isinstance(e, ChatError):
                    raise IntentExtractionError(
                        f"Failed to extract intent: {str(e)}",
                        details={
                            "user_input": user_input,
                            "context": context.model_dump(),
                        },
                    )
                raise
            log.info("validating_intent")
            with track_step(metrics, "intent_validation") as step:
                validation_result = self.intent_validator.validate(intent)
                step.metadata["is_clarification"] = isinstance(
                    validation_result, ClarificationRequest
                )
            if isinstance(validation_result, ClarificationRequest):
                metrics.complete(success=True)
                clarification_response = {
                    "status": "clarification_needed",
                    "message": validation_result.message,
                    "reason": validation_result.reason,
                    "suggestions": validation_result.suggestions,
                    "context": validation_result.context,
                    "metadata": {
                        "pipeline_metrics": metrics.model_dump(),
                    },
                }
                state.add_interaction(
                    user_input=user_input,
                    response=clarification_response,
                    clarification=validation_result,
                )
                if self.session_manager:
                    self.session_manager.save(state.conversation_id, state)
                return clarification_response, state

            # Build unified schema context
            llm_context, validator_context = self.context_builder.build_from_retrieval(
                retrieved_context=context,
                intent=validation_result,
                include_all_columns=True,  # Use aggressive strategy to include all columns
            )

            # Only proceed with SQL generation if validation passed
            log.info("generating_sql")
            try:
                with track_step(metrics, "sql_generation") as step:
                    sql_result = await self.sql_generator.generate(
                        question=user_input,
                        intent=validation_result,
                        schema_context=llm_context,
                    )
                    step.metadata["tables_used"] = sql_result.tables_used
                    step.metadata["columns_used"] = sql_result.columns_used
                    step.metadata["model_used"] = sql_result.model_used
                    step.metadata["generation_ms"] = sql_result.generation_ms
            except Exception as e:
                if not isinstance(e, ChatError):
                    raise SQLGenerationError(
                        f"Failed to generate SQL: {str(e)}",
                        details={
                            "user_input": user_input,
                            "intent": intent.model_dump(),
                            "validation_result": validation_result.model_dump(),
                        },
                    )
                raise

            # Continue with execution and response building
            log.info("executing_sql", sql=sql_result.sql)
            with track_step(metrics, "sql_validation") as step:
                # Use the unified validator context
                sql_validation = self.sql_validator.validate(
                    sql_result.sql,
                    validator_context,
                    retrieval_metrics_collector=retrieval_metrics_collector,
                )
                step.metadata["is_valid"] = sql_validation.is_valid
                if not sql_validation.is_valid:
                    error_message = "; ".join(
                        f"[{error.level.name}] {error.message}"
                        for error in sql_validation.errors
                    )
                    raise SQLValidationError(
                        f"SQL validation failed: {error_message}",
                        details={
                            "sql": sql_result.sql,
                            "validation_errors": [
                                {
                                    "level": error.level.name,
                                    "message": error.message,
                                    "details": error.details,
                                }
                                for error in sql_validation.errors
                            ],
                        },
                    )
            log.info("executing_sql")
            try:
                with track_step(metrics, "sql_execution") as step:
                    query_result = self.sql_executor.execute(sql_result.sql)
                    step.metadata["row_count"] = query_result.row_count
                    step.metadata["column_count"] = len(query_result.columns)
                    if query_result.error:
                        raise SQLExecutionError(
                            f"Query execution failed: {query_result.error}",
                            details={"sql": sql_result.sql},
                        )
            except Exception as e:
                if not isinstance(e, ChatError):
                    raise SQLExecutionError(
                        f"Failed to execute SQL: {str(e)}",
                        details={"sql": sql_result.sql},
                    )
                raise
            log.info("building_response")
            with track_step(metrics, "response_building") as step:
                response = self.response_builder.build(
                    question=user_input,
                    intent=intent,
                    sql=sql_result.sql,
                    result=query_result,
                ).model_dump()
                step.metadata["response_type"] = response.get("type", "unknown")
            metrics.complete(success=True)
            response["metadata"] = {
                "pipeline_metrics": metrics.model_dump(),
            }
            state.add_interaction(
                user_input=user_input,
                response=response,
                intent=intent,
            )
            if self.session_manager:
                self.session_manager.save(state.conversation_id, state)
            return response, state
        except ChatError as e:
            metrics.complete(success=False, error=str(e))
            error_response = {
                "status": "error",
                "message": str(e),
                "details": e.details,
                "error_type": e.__class__.__name__,
                "metadata": {
                    "pipeline_metrics": metrics.model_dump(),
                },
            }
            state.add_interaction(
                user_input=user_input,
                response=error_response,
            )
            if self.session_manager:
                self.session_manager.save(state.conversation_id, state)
            return error_response, state
        except Exception as e:
            metrics.complete(success=False, error=str(e))
            error = UnexpectedError(str(e))
            error_response = {
                "status": "error",
                "message": str(error),
                "error_type": error.__class__.__name__,
                "metadata": {
                    "pipeline_metrics": metrics.model_dump(),
                },
            }
            state.add_interaction(
                user_input=user_input,
                response=error_response,
            )
            if self.session_manager:
                self.session_manager.save(state.conversation_id, state)
            return error_response, state

    def get_conversation_state(self) -> ConversationState:
        """Get the current conversation state."""
        return self.state
