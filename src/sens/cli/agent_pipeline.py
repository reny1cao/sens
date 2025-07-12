"""Agent-based NL2SQL pipeline with integrated memory system for CLI."""

import asyncio
import json
import time
from typing import Dict, Optional

import structlog

from sens.agents.reasoning import ReasoningEngine
from sens.agents.tool_registry import EvaluationContext, tool_registry
from sens.agents.tools import AgentTools
from sens.agents.unified import UnifiedSENSAgent
from sens.chat.session import SessionManager
from sens.memory import AgentMemory, AgentMemoryTools
from sens.settings import get_settings

log = structlog.get_logger()


class AgentNL2SQLPipeline:
    """Agent-based pipeline with integrated memory system for natural language to SQL conversion."""

    def __init__(
        self,
        session_id: Optional[str] = None,
        metrics_enabled: bool = False,
        debug_mode: bool = False,
        max_iterations: Optional[int] = None,
        event_callback=None,
        evaluation_context: Optional[EvaluationContext] = None,
        db_path: Optional[str] = None,
        memory_enabled: bool = True,
        memory_db_path: str = "agent_memory.db",
    ):
        """Initialize the agent pipeline.

        Args:
            session_id: Optional session ID for conversation continuity
            metrics_enabled: Whether to track and display metrics
            debug_mode: Whether to include debug information
            max_iterations: Maximum number of agent reasoning iterations
            event_callback: Optional callback function for streaming events
            evaluation_context: Context for tool selection (BIRD_CRITIC, BIRD_SQL_DEV, etc.)
            db_path: Database path (required for SQLite contexts)
            memory_enabled: Whether to enable the agent memory system
            memory_db_path: Path to the memory database file
        """
        self.settings = get_settings()
        self.metrics_enabled = metrics_enabled
        self.debug_mode = debug_mode
        self.max_iterations = (
            max_iterations or self.settings.agent_reasoning.max_iterations
        )
        self.event_callback = event_callback

        # Initialize session
        self.session_manager = SessionManager()
        if session_id:
            self.session_id = session_id
        else:
            # Generate a new session ID
            import uuid

            self.session_id = str(uuid.uuid4())

        # Initialize context-aware tools
        if evaluation_context:
            tool_config = tool_registry.get_tools_for_context(
                evaluation_context, db_path=db_path
            )
            self.agent_tools = tool_config["tools"]
            self.tool_instructions = tool_config["instructions"]
            self.evaluation_context = evaluation_context

            log.info(
                "context_aware_tools_initialized",
                context=evaluation_context,
                database_type=tool_config["database_type"],
                available_tools=tool_config["available_tools"],
            )
        else:
            # Default tools for backward compatibility
            self.agent_tools = AgentTools()
            self.tool_instructions = ""
            self.evaluation_context = None

        self.reasoning_engine = ReasoningEngine()

        # Initialize memory system first
        self.memory_enabled = memory_enabled
        if memory_enabled:
            self.memory = AgentMemory(db_path=memory_db_path)
            self.memory_tools = AgentMemoryTools(self.memory)

            # Add memory tools to agent tools
            self._integrate_memory_tools()

            self.memory_context = {
                "database": db_path,
                "evaluation_context": (
                    evaluation_context.value if evaluation_context else None
                ),
                "database_type": (
                    tool_config.get("database_type")
                    if evaluation_context
                    else "default"
                ),
            }
        else:
            self.memory = None
            self.memory_tools = None
            self.memory_context = {}

        # Create unified agent with memory and session management
        self.agent = UnifiedSENSAgent(
            tools=self.agent_tools,
            memory_tools=self.memory_tools,
            reasoning_engine=self.reasoning_engine,
            session_manager=self.session_manager,
            max_iterations=max_iterations,
            conversation_enabled=True,
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
            memory_enabled=memory_enabled,
            agent_type="UnifiedSENSAgent",
        )

    def _integrate_memory_tools(self) -> None:
        """Integrate memory tools into the agent's toolkit."""
        if not self.memory_tools:
            return

        # Add memory methods to agent tools
        self.agent_tools.remember_concept = self.memory_tools.remember_concept
        self.agent_tools.remember_pattern = self.memory_tools.remember_pattern
        self.agent_tools.remember_mapping = self.memory_tools.remember_mapping
        self.agent_tools.remember_error_fix = self.memory_tools.remember_error_fix
        self.agent_tools.recall_knowledge = self.memory_tools.recall_knowledge
        self.agent_tools.connect_memories = self.memory_tools.connect_memories
        self.agent_tools.reflect_on_memory = self.memory_tools.reflect_on_memory
        self.agent_tools.forget_memory = self.memory_tools.forget_memory
        self.agent_tools.consolidate_memories = self.memory_tools.consolidate_memories
        self.agent_tools.get_memory_stats = self.memory_tools.get_memory_stats

        log.info(
            "memory_tools_integrated",
            tool_count=len(self.memory_tools.get_tool_descriptions()),
        )

    def _handle_agent_event(self, event: Dict) -> None:
        """Handle events emitted by the agent."""
        self.events.append(event)

        # Note: Agent now controls its own memory through memory tools
        # No passive event recording needed

        # Call external event callback if provided
        if self.event_callback:
            try:
                # Log for debugging
                log.debug(
                    "calling_external_event_callback",
                    event_type=event.get("type"),
                    has_callback=bool(self.event_callback),
                )
                self.event_callback(event)
            except Exception as e:
                log.warning("event_callback_failed", error=str(e))

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
            # Get relevant knowledge from memory if enabled
            relevant_knowledge = ""
            if self.memory_enabled and self.memory_tools:
                memory_result = await self.memory_tools.recall_knowledge(
                    query=question, context=self.memory_context, limit=5
                )

                if memory_result.success and memory_result.data:
                    memories = memory_result.data.get("memories", [])
                    if memories:
                        knowledge_parts = []
                        for mem in memories:
                            knowledge_parts.append(
                                f"[{mem['type'].upper()}] {mem['name']}: {json.dumps(mem['content'], indent=2)}"
                            )
                        relevant_knowledge = "\n\n".join(knowledge_parts)

                        log.info(
                            "applying_memory_knowledge",
                            session_id=self.session_id,
                            memory_count=len(memories),
                            knowledge_length=len(relevant_knowledge),
                        )

            # Enhance question with context-specific instructions and memory
            enhanced_question = question
            if hasattr(self, "tool_instructions") and self.tool_instructions:
                if relevant_knowledge:
                    enhanced_question = f"""
{self.tool_instructions}

RELEVANT MEMORIES:
{relevant_knowledge}

USER QUESTION: {question}
"""
                else:
                    enhanced_question = f"""
{self.tool_instructions}

USER QUESTION: {question}
"""

            # Process query with agent
            print("\n🤖 Agent is thinking about your query...")
            result = await self.agent.process_query(
                user_query=enhanced_question,
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
                    "memory_applied": bool(relevant_knowledge),
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

            # Note: Agent manages its own memory through tools during processing

            return response

        except Exception as e:
            log.error(
                "agent_processing_failed", error=str(e), session_id=self.session_id
            )

            # Note: Agent manages its own memory through tools during processing

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

    async def get_memory_stats(self) -> Dict:
        """Get memory system statistics."""
        if not self.memory_enabled or not self.memory_tools:
            return {"memory_enabled": False}

        result = await self.memory_tools.get_memory_stats()
        return result.data if result.success else {"error": result.error}

    async def enable_memory(self) -> bool:
        """Enable memory system if it was disabled."""
        if not self.memory_enabled:
            try:
                self.memory = AgentMemory()
                self.memory_tools = AgentMemoryTools(self.memory)
                self._integrate_memory_tools()
                self.memory_enabled = True

                log.info("memory_system_enabled", session_id=self.session_id)
                return True
            except Exception as e:
                log.error("memory_enable_failed", error=str(e))
                return False
        return True

    async def disable_memory(self) -> bool:
        """Disable memory system."""
        if self.memory_enabled:
            try:
                if self.memory:
                    self.memory.close()
                self.memory = None
                self.memory_tools = None
                self.memory_enabled = False

                log.info("memory_system_disabled", session_id=self.session_id)
                return True
            except Exception as e:
                log.error("memory_disable_failed", error=str(e))
                return False
        return True

    def close(self) -> None:
        """Close the pipeline and clean up resources."""
        try:
            if self.memory:
                self.memory.close()
            log.info("agent_pipeline_closed", session_id=self.session_id)
        except Exception as e:
            log.error("pipeline_close_failed", error=str(e))

    def __del__(self):
        """Destructor to ensure cleanup."""
        try:
            self.close()
        except:
            pass
