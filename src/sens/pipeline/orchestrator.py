"""
Pipeline adapter for ChatOrchestrator to implement standard Pipeline interface.
"""

import time
from typing import Any, Dict, Optional

import structlog

from ..chat.orchestrator import ChatOrchestrator
from ..chat.session import SessionManager
from ..chat.state import ConversationState
from ..interfaces import Pipeline, PipelineContext, PipelineResult
from ..interfaces.executor import ExecutionResult
from ..interfaces.generator import GenerationResult

logger = structlog.get_logger(__name__)


class OrchestratorPipeline(Pipeline):
    """
    Adapter that wraps ChatOrchestrator to implement Pipeline interface.

    This allows the existing ChatOrchestrator to be used through
    the standardized Pipeline interface.
    """

    def __init__(
        self,
        orchestrator: Optional[ChatOrchestrator] = None,
        session_manager: Optional[SessionManager] = None,
        **kwargs,
    ):
        self.orchestrator = orchestrator
        self.session_manager = session_manager or SessionManager()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the orchestrator if needed."""
        if not self._initialized:
            if not self.orchestrator:
                self.orchestrator = ChatOrchestrator(
                    session_manager=self.session_manager, use_optimized_retriever=True
                )
            self._initialized = True

    async def close(self) -> None:
        """Clean up resources."""
        # ChatOrchestrator doesn't have explicit cleanup
        pass

    def get_capabilities(self) -> Dict[str, Any]:
        """Get pipeline capabilities."""
        return {
            "supports_sessions": True,
            "supports_streaming": False,
            "supports_multi_datasource": False,
            "supports_agent_mode": False,
            "implementation": "ChatOrchestrator",
            "version": "1.0",
        }

    async def process(self, context: PipelineContext, **kwargs) -> PipelineResult:
        """Process query through ChatOrchestrator."""
        start_time = time.time()
        steps_timing = {}

        try:
            # Ensure initialized
            await self.initialize()

            # Get or create conversation state
            session_id = context.session_id or "default"
            state = self.session_manager.get(session_id)

            if state is None:
                state = ConversationState(
                    conversation_id=session_id, user_id="api_user"
                )

            # Process through orchestrator
            step_start = time.time()
            response, updated_state = await self.orchestrator.step(state, context.query)
            steps_timing["orchestrator_step"] = (time.time() - step_start) * 1000

            # Save updated state
            if self.session_manager:
                try:
                    self.session_manager.save(session_id, updated_state)
                except Exception as e:
                    logger.warning("Failed to save session state", error=str(e))

            # Convert response to PipelineResult
            return self._convert_response(response, context, steps_timing, start_time)

        except Exception as e:
            logger.error(
                "Pipeline processing failed", error=str(e), query=context.query
            )

            return PipelineResult(
                success=False,
                sql="",
                error=str(e),
                total_time_ms=(time.time() - start_time) * 1000,
                steps_timing=steps_timing,
            )

    def _convert_response(
        self,
        response: Dict[str, Any],
        context: PipelineContext,
        steps_timing: Dict[str, float],
        start_time: float,
    ) -> PipelineResult:
        """Convert ChatOrchestrator response to PipelineResult."""

        # Handle error responses
        if response.get("status") == "error":
            return PipelineResult(
                success=False,
                sql="",
                error=response.get("message", "Query failed"),
                total_time_ms=(time.time() - start_time) * 1000,
                steps_timing=steps_timing,
            )

        # Handle clarification needed
        if response.get("status") == "clarification_needed":
            return PipelineResult(
                success=False,
                sql="",
                error=response.get("message", "Clarification needed"),
                total_time_ms=(time.time() - start_time) * 1000,
                steps_timing=steps_timing,
                metadata={"suggestions": response.get("suggestions", [])},
            )

        # Extract SQL and results
        sql = response.get("sql", "")
        table_preview = response.get("table_preview", [])
        row_count = response.get("row_count", 0)
        metadata_info = response.get("metadata", {})
        columns = metadata_info.get("columns", [])

        # Convert table preview to execution result
        execution_result = None
        if table_preview and columns:
            # Convert list of lists to list of dicts
            rows = []
            for row in table_preview:
                if isinstance(row, list) and len(row) == len(columns):
                    rows.append(dict(zip(columns, row)))
                elif isinstance(row, dict):
                    rows.append(row)

            execution_result = ExecutionResult(
                success=True,
                rows=rows,
                columns=columns,
                row_count=row_count,
                execution_time_ms=metadata_info.get("execution_time_ms", 0),
            )

        # Create generation result if we have SQL
        generation_result = None
        if sql:
            generation_result = GenerationResult(
                sql=sql,
                confidence=metadata_info.get("confidence", 0.8),
                explanation=response.get("summary"),
            )

        # Build final result
        return PipelineResult(
            success=True,
            sql=sql,
            execution_result=execution_result,
            generation_result=generation_result,
            total_time_ms=(time.time() - start_time) * 1000,
            steps_timing=steps_timing,
            metadata={
                "summary": response.get("summary"),
                "pipeline_metrics": metadata_info.get("pipeline_metrics", {}),
                "session_id": context.session_id,
            },
        )
