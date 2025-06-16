"""Agent-based NL2SQL pipeline for CLI."""

import asyncio
import json
import time
from typing import Dict, Optional

import structlog

from sens.agents.core import SENSAgent
from sens.agents.event_emitter import EventEmittingAgent
from sens.agents.memory import AgentMemory
from sens.agents.reasoning import ReasoningEngine
from sens.agents.tools import AgentTools
from sens.chat.session import SessionManager
from sens.settings import get_settings

log = structlog.get_logger()


class AgentNL2SQLPipeline:
    """Agent-based pipeline for natural language to SQL conversion."""

    def __init__(
        self,
        session_id: Optional[str] = None,
        metrics_enabled: bool = False,
        debug_mode: bool = False,
        max_iterations: int = 10,
    ):
        """Initialize the agent pipeline.

        Args:
            session_id: Optional session ID for conversation continuity
            metrics_enabled: Whether to track and display metrics
            debug_mode: Whether to include debug information
            max_iterations: Maximum number of agent reasoning iterations
        """
        self.settings = get_settings()
        self.metrics_enabled = metrics_enabled
        self.debug_mode = debug_mode
        self.max_iterations = max_iterations

        # Initialize session
        self.session_manager = SessionManager()
        if session_id:
            self.session_id = session_id
        else:
            # Generate a new session ID
            import uuid

            self.session_id = str(uuid.uuid4())

        # Initialize agent components
        self.agent_tools = AgentTools()
        self.agent_memory = AgentMemory()
        self.reasoning_engine = ReasoningEngine()

        # Create event-emitting agent
        self.agent = EventEmittingAgent(
            tools=self.agent_tools,
            memory=self.agent_memory,
            reasoning_engine=self.reasoning_engine,
            max_iterations=max_iterations,
        )

        # Register event handler to store events
        self.events = []
        self.agent.add_event_handler(self._handle_agent_event)

        log.info(
            "agent_pipeline_initialized",
            session_id=self.session_id,
            max_iterations=max_iterations,
            debug_mode=debug_mode,
            metrics_enabled=metrics_enabled,
            agent_type="EventEmittingAgent",
        )

    def _handle_agent_event(self, event: Dict) -> None:
        """Handle events emitted by the agent."""
        self.events.append(event)

        # Print events in real-time if debug mode is enabled
        if self.debug_mode:
            event_type = event.get("type", "unknown")
            if event_type == "thought":
                print(f"\n🤔 Thinking: {event['data']['content']}")
            elif event_type == "action":
                action_type = event["data"]["action_type"]
                print(f"\n🔧 Action: {action_type}")
                if "reasoning" in event["data"]:
                    print(f"   Reason: {event['data']['reasoning']}")
            elif event_type == "observation":
                success = event["data"]["success"]
                status = "✅ Success" if success else "❌ Failed"
                print(f"\n👁️  Observation: {status}")
                if not success and "error" in event["data"]:
                    print(f"   Error: {event['data']['error']}")

    async def process_question(
        self,
        question: str,
        format_type: str = "json",
        show_preview: bool = True,
        max_rows: int = 5,
    ) -> Dict:
        """Process a natural language question using the agent.

        Args:
            question: Natural language question
            format_type: Output format (json, table, summary)
            show_preview: Whether to show data preview
            max_rows: Maximum rows to preview

        Returns:
            Dict containing results and metadata
        """
        start_time = time.time()
        log.info(
            "agent_processing_question",
            question=question,
            session_id=self.session_id,
            format_type=format_type,
        )

        try:
            # Process query with agent
            print("\n🤖 Agent is thinking about your query...")
            result = await self.agent.process_query(
                user_query=question,
                conversation_id=self.session_id,
            )

            # Calculate metrics
            total_duration_ms = (time.time() - start_time) * 1000

            # Format response
            response = {
                "status": "success" if result.get("success") else "error",
                "summary": self._generate_summary(result),
                "sql": result.get("sql"),
                "row_count": 0,
                "table_preview": [],
                "columns": [],
                "metadata": {
                    "session_id": self.session_id,
                    "iterations": result.get("iterations", 0),
                    "discovered_mappings": result.get("discovered_mappings", {}),
                    "agent_trace": self._format_agent_trace(result),
                },
            }

            # Add execution result if available
            if result.get("result") and result["result"].get("success"):
                exec_result = result["result"]
                response["row_count"] = exec_result.get("row_count", 0)
                response["columns"] = exec_result.get("columns", [])

                # Add preview if requested
                if show_preview and exec_result.get("data"):
                    response["table_preview"] = exec_result["data"][:max_rows]

            # Add metrics if enabled
            if self.metrics_enabled:
                response["metrics"] = {
                    "total_duration_ms": total_duration_ms,
                    "iterations": result.get("iterations", 0),
                    "actions_count": len(result.get("actions_taken", [])),
                    "success_rate": 1.0 if result.get("success") else 0.0,
                }

            # Add debug info if enabled
            if self.debug_mode:
                response["debug"] = {
                    "events": self.events,
                    "reasoning_trace": result.get("reasoning_trace", []),
                    "actions_taken": result.get("actions_taken", []),
                }

            # Store in session
            await self._store_in_session(question, response)

            return response

        except Exception as e:
            log.error(
                "agent_processing_failed", error=str(e), session_id=self.session_id
            )
            return {
                "status": "error",
                "error": str(e),
                "summary": f"Failed to process query: {str(e)}",
                "metadata": {
                    "session_id": self.session_id,
                    "error_type": type(e).__name__,
                },
            }

    def _generate_summary(self, result: Dict) -> str:
        """Generate a summary of the agent's result."""
        if not result.get("success"):
            error = result.get("error", "Unknown error")
            return f"Query failed: {error}"

        if result.get("result") and result["result"].get("row_count", 0) > 0:
            row_count = result["result"]["row_count"]
            return f"Found {row_count} matching record{'s' if row_count != 1 else ''}"
        elif result.get("sql"):
            return "Generated SQL query but no results found"
        else:
            return "Unable to generate SQL for this query"

    def _format_agent_trace(self, result: Dict) -> Dict:
        """Format the agent's reasoning trace for display."""
        trace = {
            "thoughts": [],
            "actions": [],
            "key_discoveries": {},
        }

        # Extract thoughts
        for thought in result.get("reasoning_trace", []):
            trace["thoughts"].append(
                {
                    "content": thought["content"],
                    "timestamp": thought["timestamp"],
                }
            )

        # Extract actions
        for action in result.get("actions_taken", []):
            trace["actions"].append(
                {
                    "type": action["type"],
                    "parameters": action.get("parameters", {}),
                }
            )

        # Extract key discoveries
        if result.get("discovered_mappings"):
            trace["key_discoveries"]["value_mappings"] = result["discovered_mappings"]

        return trace

    async def _store_in_session(self, question: str, response: Dict) -> None:
        """Store the interaction in the session."""
        try:
            # Get existing session state
            state = self.session_manager.get_session(self.session_id)
            if not state:
                state = {"interactions": []}

            # Add new interaction
            state["interactions"].append(
                {
                    "question": question,
                    "response": response,
                    "timestamp": time.time(),
                    "agent_mode": True,
                }
            )

            # Update session
            self.session_manager.update_session(self.session_id, state)

        except Exception as e:
            log.warning(
                "failed_to_store_in_session", error=str(e), session_id=self.session_id
            )

    def get_session_history(self) -> Dict:
        """Get the current session history."""
        state = self.session_manager.get_session(self.session_id)
        return state if state else {"interactions": []}
