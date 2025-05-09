"""Enhanced NL2SQL pipeline using ChatOrchestrator.

This module provides an enhanced version of the NL2SQL pipeline that uses
the ChatOrchestrator for better error handling, metrics tracking, and debugging.
"""

import logging
from typing import Dict, Optional

import structlog

from sens.chat.orchestrator import ChatOrchestrator
from sens.chat.state import ConversationState
from sens.monitoring.metrics import PipelineMetrics

# Configure structured logging
log = structlog.get_logger()


class EnhancedNL2SQLPipeline:
    """Enhanced pipeline for converting natural language to SQL using ChatOrchestrator."""

    def __init__(
        self,
        conversation_id: Optional[str] = None,
        metrics_enabled: bool = False,
        debug_mode: bool = False,
    ):
        """Initialize the enhanced pipeline.

        Args:
            conversation_id: Optional ID for the conversation
            metrics_enabled: Whether to collect and return metrics
            debug_mode: Whether to include debug information in output
        """
        self.metrics_enabled = metrics_enabled
        self.debug_mode = debug_mode

        # Initialize ChatOrchestrator with optional conversation state
        state = (
            ConversationState(conversation_id=conversation_id)
            if conversation_id
            else None
        )
        self.orchestrator = ChatOrchestrator(
            conversation_id=conversation_id,
            state=state,
        )

        log.info(
            "enhanced_pipeline_initialized",
            conversation_id=conversation_id,
            metrics_enabled=metrics_enabled,
            debug_mode=debug_mode,
            validation_enabled=True,
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
            # Process through ChatOrchestrator
            response = await self.orchestrator.step(question)

            # Add metrics if enabled
            if self.metrics_enabled and "metadata" in response:
                response["metadata"]["metrics_enabled"] = True
                if "pipeline_metrics" not in response["metadata"]:
                    # Ensure we always have metrics when enabled
                    metrics = PipelineMetrics(
                        conversation_id=self.orchestrator.state.conversation_id
                    )
                    response["metadata"]["pipeline_metrics"] = metrics.model_dump()

            # Add debug info if enabled
            if self.debug_mode:
                debug_info = {
                    "conversation_id": self.orchestrator.state.conversation_id,
                    "interaction_count": len(self.orchestrator.state.interactions),
                    "last_intent": (
                        self.orchestrator.state.last_intent.model_dump()
                        if self.orchestrator.state.last_intent
                        else None
                    ),
                }
                if "metadata" not in response:
                    response["metadata"] = {}
                response["metadata"]["debug"] = debug_info

            return response

        except Exception as e:
            log.error(
                "enhanced_pipeline_error",
                error=str(e),
                conversation_id=self.orchestrator.state.conversation_id,
            )
            error_response = {
                "status": "error",
                "message": str(e),
                "metadata": {},
            }

            # Add metrics to error response if enabled
            if self.metrics_enabled:
                metrics = PipelineMetrics(
                    conversation_id=self.orchestrator.state.conversation_id
                )
                metrics.complete(success=False, error=str(e))
                error_response["metadata"]["pipeline_metrics"] = metrics.model_dump()

            # Add debug info to error response if enabled
            if self.debug_mode:
                error_response["metadata"]["debug"] = {
                    "error_type": e.__class__.__name__,
                    "conversation_id": self.orchestrator.state.conversation_id,
                }

            return error_response
