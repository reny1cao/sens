"""Enhanced NL2SQL pipeline using ChatOrchestrator.

This module provides an enhanced version of the NL2SQL pipeline that uses
the ChatOrchestrator for better error handling, metrics tracking, and debugging.
"""

import logging
import uuid
from typing import Dict, Optional, Tuple

import structlog

from sens.chat.orchestrator import ChatOrchestrator
from sens.chat.session import SessionManager
from sens.chat.state import ConversationState
from sens.monitoring.metrics import PipelineMetrics

# Configure structured logging
log = structlog.get_logger()


class EnhancedNL2SQLPipeline:
    """Enhanced pipeline for converting natural language to SQL using ChatOrchestrator."""

    def __init__(
        self,
        session_id: Optional[str] = None,
        metrics_enabled: bool = False,
        debug_mode: bool = False,
    ):
        """Initialize the enhanced pipeline.

        Args:
            session_id: Optional ID for the conversation session. If not provided,
                      a new session will be created for this pipeline instance.
            metrics_enabled: Whether to collect and return metrics
            debug_mode: Whether to include debug information in output
        """
        self.metrics_enabled = metrics_enabled
        self.debug_mode = debug_mode
        self.session_id = session_id or str(uuid.uuid4())

        # Initialize session management
        self.session_manager = SessionManager()
        self.state = self.session_manager.get(self.session_id)
        if not self.state:
            self.state = ConversationState(conversation_id=self.session_id)

        # Initialize ChatOrchestrator (now stateless)
        self.orchestrator = ChatOrchestrator(session_manager=self.session_manager)

        log.info(
            "enhanced_pipeline_initialized",
            session_id=self.session_id,
            metrics_enabled=metrics_enabled,
            debug_mode=debug_mode,
            validation_enabled=True,
            redis_available=self.session_manager.redis_available,
        )

    async def process_question(
        self,
        question: str,
        format_type: str = "json",
        show_preview: bool = True,
        max_rows: int = 5,
    ) -> Dict:
        """Process a natural language question.

        Args:
            question: The natural language question to process
            format_type: Output format (json, table, or summary)
            show_preview: Whether to include result preview
            max_rows: Maximum number of preview rows

        Returns:
            Dict containing the response with optional metrics and debug info
        """
        try:
            # Process through ChatOrchestrator with explicit state
            response, updated_state = await self.orchestrator.step(
                state=self.state,
                user_input=question,
            )
            self.state = updated_state

            # Add metrics if enabled
            if self.metrics_enabled and "metadata" in response:
                response["metadata"]["metrics_enabled"] = True
                if "pipeline_metrics" not in response["metadata"]:
                    # Ensure we always have metrics when enabled
                    metrics = PipelineMetrics(conversation_id=self.session_id)
                    response["metadata"]["pipeline_metrics"] = metrics.model_dump()

            # Add debug info if enabled
            if self.debug_mode:
                debug_info = {
                    "session_id": self.session_id,
                    "interaction_count": len(self.state.history),
                    "last_intent": (
                        self.state.last_valid_intent.model_dump()
                        if self.state.last_valid_intent
                        else None
                    ),
                    "redis_available": self.session_manager.redis_available,
                }
                if "metadata" not in response:
                    response["metadata"] = {}
                response["metadata"]["debug"] = debug_info

            return response

        except Exception as e:
            log.error(
                "enhanced_pipeline_error",
                error=str(e),
                session_id=self.session_id,
            )
            error_response = {
                "status": "error",
                "message": str(e),
                "metadata": {},
            }

            # Add metrics to error response if enabled
            if self.metrics_enabled:
                metrics = PipelineMetrics(conversation_id=self.session_id)
                metrics.complete(success=False, error=str(e))
                error_response["metadata"]["pipeline_metrics"] = metrics.model_dump()

            # Add debug info to error response if enabled
            if self.debug_mode:
                error_response["metadata"]["debug"] = {
                    "error_type": e.__class__.__name__,
                    "session_id": self.session_id,
                    "redis_available": self.session_manager.redis_available,
                }

            return error_response
