"""Chat orchestration module for managing the full NL→SQL→Result pipeline."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Dict, Optional, Union

import structlog
from openai import OpenAI

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
from sens.retrieval.orchestrator import RetrievalOrchestrator
from sens.retrieval.token.builder import TokenIndexBuilder
from sens.schema.graph import SchemaGraph
from sens.settings import get_settings
from sens.validation.context_converter import to_validator_schema
from sens.validation.sql_validator import SQLValidator

# Configure structured logging
log = structlog.get_logger()


class ChatOrchestrator:
    """Orchestrates the full pipeline from natural language to SQL results."""

    def __init__(
        self,
        conversation_id: Optional[str] = None,
        state: Optional[ConversationState] = None,
    ):
        """Initialize the chat orchestrator and session manager.

        Args:
            conversation_id: Optional ID for the conversation
            state: Optional existing conversation state
        """
        self.session_manager = SessionManager()
        self.state = state or (
            ConversationState(conversation_id=conversation_id)
            if conversation_id
            else ConversationState(conversation_id=str(uuid.uuid4()))
        )

        # Initialize all pipeline components
        self.schema_graph = SchemaGraph.get_instance()
        token_index = ChatTokenIndexAdapter()
        embedding_index = ChatEmbeddingAdapter()
        self.retrieval = RetrievalOrchestrator(
            token_index=token_index,
            embedding_index=embedding_index,
            schema_graph=self.schema_graph,
        )
        self.intent_extractor = IntentExtractor()
        self.intent_validator = IntentValidator()
        self.sql_generator = SQLGenerator()
        self.sql_validator = SQLValidator()
        self.sql_executor = SQLExecutor()
        self.response_builder = ResponseBuilder()
        log.info(
            "chat_orchestrator_initialized", conversation_id=self.state.conversation_id
        )

    async def step(self, user_input: str) -> Union[Dict, ClarificationRequest]:
        """Process one step of the conversation.

        Args:
            user_input: The user's question or input

        Returns:
            Either a response dictionary or a clarification request
        """
        metrics = PipelineMetrics(conversation_id=self.state.conversation_id)
        metrics.metadata["user_input"] = user_input
        try:
            log.info(
                "retrieving_schema_context",
                conversation_id=self.state.conversation_id,
                user_input=user_input,
            )
            try:
                with track_step(metrics, "schema_retrieval") as step:
                    context = await self.retrieval.get_relevant_context(
                        question=user_input
                    )
                    step.metadata["table_count"] = len(context.tables)
                    step.metadata["column_count"] = len(context.columns)
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
                    self.state.add_interaction(
                        user_input=user_input,
                        response=error_response,
                    )
                    self.session_manager.save(self.state.conversation_id, self.state)
                    return error_response
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
                self.state.add_interaction(
                    user_input=user_input,
                    response=error_response,
                )
                self.session_manager.save(self.state.conversation_id, self.state)
                return error_response
            log.info("extracting_intent")
            try:
                with track_step(metrics, "intent_extraction") as step:
                    intent = await self.intent_extractor.extract(
                        question=user_input,
                        schema_snippet=context.format_for_llm(),
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
                self.state.add_interaction(
                    user_input=user_input,
                    response=clarification_response,
                    clarification=validation_result,
                )
                self.session_manager.save(self.state.conversation_id, self.state)
                return validation_result
            log.info("generating_sql")
            try:
                with track_step(metrics, "sql_generation") as step:
                    sql_result = await self.sql_generator.generate(
                        question=user_input,
                        intent=validation_result,
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
            log.info("validating_sql", sql=sql_result.sql)
            with track_step(metrics, "sql_validation") as step:
                validator_schema = to_validator_schema(context)
                sql_validation = self.sql_validator.validate(
                    sql_result.sql, validator_schema
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
                        f"Query execution failed: {str(e)}",
                        details={"sql": sql_result.sql},
                    )
            log.info("building_response")
            try:
                with track_step(metrics, "response_building") as step:
                    response = self.response_builder.build(
                        question=user_input,
                        intent=intent,
                        result=query_result,
                        sql=sql_result.sql,
                        execution_time_ms=sql_result.generation_ms,
                    )
                    step.metadata["summary_length"] = len(response.summary)
            except Exception as build_error:
                if not isinstance(build_error, ChatError):
                    raise ResponseBuildingError(
                        f"Failed to build response: {str(build_error)}",
                        details={
                            "user_input": user_input,
                            "sql": sql_result.sql,
                            "result": (
                                query_result.model_dump()
                                if hasattr(query_result, "model_dump")
                                else str(query_result)
                            ),
                        },
                    )
                raise

            # Create final response with all metadata
            final_response = {
                "status": "success",
                "conversation_id": self.state.conversation_id,
                "summary": response.summary,
                "sql": sql_result.sql,
                "result": {
                    "preview": response.table_preview,
                    "row_count": response.row_count,
                    "columns": query_result.columns,
                },
                "metadata": {
                    "tables_used": sql_result.tables_used,
                    "columns_used": sql_result.columns_used,
                    "model_used": sql_result.model_used,
                    "generation_ms": sql_result.generation_ms,
                    "token_usage": (
                        sql_result.token_usage.model_dump()
                        if sql_result.token_usage
                        else None
                    ),
                    "intent_type": intent.query_type,
                    "tables": intent.tables,
                    "operations": intent.operations,
                    "confidence": intent.confidence,
                    "generated_at": response.generated_at,
                    "pipeline_metrics": metrics.model_dump(),
                },
            }

            # Update conversation state and save
            self.state.add_interaction(
                user_input=user_input,
                response=final_response,
                intent=intent,
            )
            metrics.complete(success=True)
            self.session_manager.save(self.state.conversation_id, self.state)
            return final_response

        except ChatError as e:
            # Handle known chat-related errors
            log.error(
                "chat_error",
                error_type=e.__class__.__name__,
                error_message=str(e),
                error_details=e.details,
                conversation_id=self.state.conversation_id,
            )
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
            self.state.add_interaction(
                user_input=user_input,
                response=error_response,
            )
            self.session_manager.save(self.state.conversation_id, self.state)
            return error_response

        except Exception as e:
            # Handle unexpected errors
            log.error(
                "unexpected_error",
                error=str(e),
                conversation_id=self.state.conversation_id,
            )
            metrics.complete(success=False, error=str(e))
            error_response = {
                "status": "error",
                "message": f"An unexpected error occurred: {str(e)}",
                "metadata": {
                    "pipeline_metrics": metrics.model_dump(),
                },
            }
            self.state.add_interaction(
                user_input=user_input,
                response=error_response,
            )
            self.session_manager.save(self.state.conversation_id, self.state)
            return error_response

    def get_conversation_state(self) -> ConversationState:
        """Get the current conversation state."""
        return self.state
