"""
Unified SENS Agent: Consolidated implementation with streaming, memory, and all features.
Replaces EventEmittingAgent, SENSAgent, and other redundant implementations.
"""

import asyncio
import hashlib
import time
from datetime import datetime
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Union

import structlog
from cachetools import TTLCache

from sens.agents.answer_generator import AnswerGenerator
from sens.agents.base import (
    ActionType,
    AgentAction,
    AgentObservation,
    AgentState,
    BaseAgent,
)
from sens.agents.reasoning import ReasoningEngine
from sens.agents.reflection import ReflectionEngine
from sens.agents.tools import AgentTools
from sens.chat.session import SessionManager
from sens.chat.state import ConversationState
from sens.memory import AgentMemoryTools, MemoryType
from sens.settings import get_settings

log = structlog.get_logger()


class AgentEvent:
    """Structured event for streaming"""

    def __init__(
        self,
        event_type: str,
        data: Dict[str, Any],
        timestamp: Optional[datetime] = None,
    ):
        self.type = event_type
        self.data = data
        self.timestamp = timestamp or datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }


class UnifiedSENSAgent:
    """
    Unified agent implementation with all features:
    - Streaming support for web UI
    - Memory integration with caching
    - Conversation context management
    - ReAct loop implementation
    - All action types support
    - Performance optimizations
    """

    def __init__(
        self,
        tools: Optional[AgentTools] = None,
        memory_tools: Optional[AgentMemoryTools] = None,
        reasoning_engine: Optional[ReasoningEngine] = None,
        reflection_engine: Optional[ReflectionEngine] = None,
        answer_generator: Optional[AnswerGenerator] = None,
        session_manager: Optional[SessionManager] = None,
        max_iterations: Optional[int] = None,
        # Feature flags
        streaming_enabled: bool = True,
        memory_enabled: bool = True,
        reflection_enabled: bool = True,
        conversation_enabled: bool = True,
        minimal_mode: bool = False,  # For performance-critical scenarios
    ):
        """Initialize unified agent with configurable features."""

        # Get settings for default max_iterations
        settings = get_settings()

        # Core components
        self.tools = tools or AgentTools()
        self.reasoning_engine = reasoning_engine or ReasoningEngine()
        self.reflection_engine = reflection_engine or ReflectionEngine()
        self.answer_generator = answer_generator or AnswerGenerator()

        # Session management for conversation context
        self.session_manager = session_manager if conversation_enabled else None
        self.conversation_enabled = conversation_enabled and session_manager is not None

        # Memory system
        self.memory_tools = memory_tools if memory_enabled else None
        self.memory_enabled = memory_enabled and memory_tools is not None

        # Feature flags
        self.streaming_enabled = streaming_enabled
        self.reflection_enabled = reflection_enabled
        self.minimal_mode = minimal_mode
        self.max_iterations = max_iterations or settings.agent_reasoning.max_iterations

        # Streaming support (matching original EventEmittingAgent)
        self.event_handlers: List[Callable] = []
        self.event_queue: asyncio.Queue = asyncio.Queue() if streaming_enabled else None

        # Memory caching layers (always enabled for performance)
        self.schema_cache = TTLCache(maxsize=50, ttl=1800)  # 30min
        self.sql_cache = TTLCache(maxsize=100, ttl=600)  # 10min
        self.pattern_cache = TTLCache(maxsize=100, ttl=600)  # 10min

        # Performance metrics
        self.metrics = {
            "cache_hits": 0,
            "cache_misses": 0,
            "memory_recalls": 0,
            "iterations_saved": 0,
        }

        log.info(
            "unified_agent_initialized",
            max_iterations=max_iterations,
            streaming=streaming_enabled,
            memory=memory_enabled,
            conversation=conversation_enabled,
            reflection=reflection_enabled,
            minimal_mode=minimal_mode,
        )

    # === Event Streaming Support ===

    def add_event_handler(self, handler: Callable) -> None:
        """Add an event handler for streaming."""
        if self.streaming_enabled:
            self.event_handlers.append(handler)

    async def emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Emit event to all handlers (matching original EventEmittingAgent)."""
        if not self.streaming_enabled:
            return

        event = {
            "type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data,
        }

        # Put event in queue for async processing (like original)
        if self.event_queue:
            await self.event_queue.put(event)

        # Call handlers (like original)
        for handler in self.event_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                log.error("event_handler_error", error=str(e), event_type=event_type)

    # === Main Processing Methods ===

    # Required BaseAgent methods (not used directly, but needed for interface)
    async def reason(self, state: AgentState) -> Dict[str, Any]:
        """Reason about the current state."""
        return await self._reason_with_memory(state)

    async def act(
        self, state: AgentState, reasoning_result: Dict[str, Any]
    ) -> AgentObservation:
        """Execute action based on reasoning."""
        return await self._act_with_events(state, reasoning_result)

    async def observe(self, state: AgentState, action: AgentAction) -> AgentObservation:
        """Observe the result of an action."""
        return await self._execute_optimized(state, action)

    async def reflect(self, state: AgentState, observation: AgentObservation) -> None:
        """Reflect on the observation (optional)."""
        if self.reflection_enabled and self.reflection_engine:
            # Simple reflection - can be enhanced
            pass

    async def process_query(
        self, user_query: str, conversation_id: str
    ) -> Dict[str, Any]:
        """Process query with all features enabled, including conversation context."""

        # Emit start event
        await self.emit_event(
            "query_start",
            {
                "query": user_query,
                "conversation_id": conversation_id,
                "max_iterations": self.max_iterations,
            },
        )

        # Load or create conversation state
        conversation_state = None
        if self.conversation_enabled and self.session_manager:
            conversation_state = self.session_manager.get(conversation_id)
            if conversation_state is None:
                conversation_state = ConversationState(conversation_id=conversation_id)
                log.info("created_new_conversation", conversation_id=conversation_id)
            else:
                log.info(
                    "loaded_conversation_history",
                    conversation_id=conversation_id,
                    history_count=len(conversation_state.history),
                )

        # Initialize agent state with conversation context
        state = AgentState(
            user_query=user_query,
            conversation_id=conversation_id,
            max_iterations=self.max_iterations,
        )

        # Add conversation context to agent notes if available
        if conversation_state and conversation_state.history:
            conversation_context = self._build_conversation_context(conversation_state)
            state.update_notes(f"Conversation History:\n{conversation_context}")

        try:
            # Phase 1: Memory-enhanced initialization (non-blocking)
            if self.memory_enabled:
                await self._initialize_with_memory(state)

            # Phase 2: ReAct loop
            while state.should_continue:
                state.iteration += 1

                # Emit iteration start
                await self.emit_event(
                    "iteration_start",
                    {
                        "iteration": state.iteration,
                        "max_iterations": state.max_iterations,
                    },
                )

                # REASON
                reasoning_result = await self._reason_with_memory(state)

                # ACT
                observation = await self._act_with_events(state, reasoning_result)

                # Check for completion
                if state.success and (state.current_sql or state.final_result):
                    break

            # Phase 3: Generate response
            result = await self._build_final_response(state)

            # Phase 4: Save conversation state
            if (
                self.conversation_enabled
                and self.session_manager
                and conversation_state
            ):
                await self._save_conversation_state(
                    conversation_state, user_query, result, state
                )

            # Emit completion
            await self.emit_event(
                "query_complete",
                {
                    "success": result["success"],
                    "iterations": result["iterations"],
                    "sql": result.get("sql"),
                    "answer": result.get("answer"),
                },
            )

            return result

        except Exception as e:
            log.error("agent_error", error=str(e))
            await self.emit_event("query_error", {"error": str(e)})
            return self._build_error_response(state, e)

    async def process_query_stream(
        self, user_query: str, conversation_id: str
    ) -> AsyncIterator[Dict[str, Any]]:
        """Process query with streaming output."""

        # Set up event collection
        events = []

        def collect_event(event):
            events.append(event)

        # Add temporary handler
        self.add_event_handler(collect_event)

        try:
            # Process query (events will be collected)
            result = await self.process_query(user_query, conversation_id)

            # Yield all collected events
            for event in events:
                yield event

            # Yield final result
            yield {
                "type": "final_result",
                "timestamp": datetime.utcnow().isoformat(),
                "data": result,
            }

        finally:
            # Remove temporary handler
            if collect_event in self.event_handlers:
                self.event_handlers.remove(collect_event)

    # === Memory Integration ===

    async def _initialize_with_memory(self, state: AgentState) -> None:
        """Enhanced memory initialization with intelligent recall and application."""

        if not self.memory_enabled or not self.memory_tools:
            return

        try:
            # Get memory configuration
            settings = get_settings()
            memory_config = settings.memory
            timeout_seconds = memory_config.memory_recall_timeout_ms / 1000.0

            # Enhanced parallel memory recalls with more specific searches
            memory_tasks = [
                self._recall_schema_memory(state),
                self._recall_pattern_memory(state),
                self._recall_similar_queries(state),
                self._recall_value_mappings(state),
                self._recall_error_solutions(state),
            ]

            results = await asyncio.wait_for(
                asyncio.gather(*memory_tasks, return_exceptions=True),
                timeout=timeout_seconds,
            )

            # Apply memory insights to state with confidence filtering
            insights_applied = self._apply_enhanced_memory_insights(
                state, results, memory_config
            )

            if insights_applied > 0:
                self.metrics["memory_recalls"] += 1
                log.info(
                    "memory_insights_applied",
                    count=insights_applied,
                    user_query=state.user_query[:50],
                )

        except asyncio.TimeoutError:
            log.warning(
                "memory_initialization_timeout",
                timeout_ms=memory_config.memory_recall_timeout_ms,
            )
        except Exception as e:
            log.warning("enhanced_memory_initialization_error", error=str(e))

    async def _recall_schema_memory(self, state: AgentState) -> Optional[Dict]:
        """Recall database schema from memory."""

        # Check cache first
        cache_key = f"schema_{state.conversation_id}"
        if cache_key in self.schema_cache:
            self.metrics["cache_hits"] += 1
            return self.schema_cache[cache_key]

        # Memory recall with timeout
        try:
            result = await asyncio.wait_for(
                self.memory_tools.recall_knowledge(
                    query=f"database schema {state.user_query}",
                    memory_types=["concept"],
                    context={"type": "database_schema"},
                    limit=3,
                ),
                timeout=0.05,  # 50ms timeout
            )

            if result.success:
                self.schema_cache[cache_key] = result
                self.metrics["memory_recalls"] += 1

            return result

        except asyncio.TimeoutError:
            return None

    async def _recall_pattern_memory(self, state: AgentState) -> Optional[Dict]:
        """Recall SQL pattern memories for similar queries."""

        if not self.memory_enabled or not self.memory_tools:
            return None

        try:
            result = await self.memory_tools.recall_knowledge(
                query=state.user_query,
                memory_types=["pattern"],
                context={"query_type": "sql_pattern"},
                limit=5,
            )

            if result.success and result.data.get("memories"):
                log.debug(
                    "pattern_memories_recalled", count=len(result.data["memories"])
                )
                return result.data

        except Exception as e:
            log.warning("pattern_memory_recall_failed", error=str(e))

        return None

    async def _recall_similar_queries(self, state: AgentState) -> Optional[Dict]:
        """Recall memories from similar queries."""

        if not self.memory_enabled or not self.memory_tools:
            return None

        try:
            # Search for any memories related to similar queries
            result = await self.memory_tools.recall_knowledge(
                query=state.user_query,
                memory_types=["concept", "pattern", "mapping"],
                context={"query_type": "similar_query"},
                limit=8,
            )

            if result.success and result.data.get("memories"):
                log.debug(
                    "similar_query_memories_recalled",
                    count=len(result.data["memories"]),
                )
                return result.data

        except Exception as e:
            log.warning("similar_query_recall_failed", error=str(e))

        return None

    async def _recall_value_mappings(self, state: AgentState) -> Optional[Dict]:
        """Recall value mapping memories for query terms."""

        if not self.memory_enabled or not self.memory_tools:
            return None

        try:
            result = await self.memory_tools.recall_knowledge(
                query=state.user_query,
                memory_types=["mapping"],
                context={"query_type": "value_mapping"},
                limit=10,
            )

            if result.success and result.data.get("memories"):
                log.debug("value_mappings_recalled", count=len(result.data["memories"]))
                return result.data

        except Exception as e:
            log.warning("value_mapping_recall_failed", error=str(e))

        return None

    async def _recall_error_solutions(self, state: AgentState) -> Optional[Dict]:
        """Recall error solutions and fixes."""

        if not self.memory_enabled or not self.memory_tools:
            return None

        try:
            result = await self.memory_tools.recall_knowledge(
                query=f"error solution fix {state.user_query}",
                memory_types=["error_fix"],
                context={"query_type": "error_solution"},
                limit=5,
            )

            if result.success and result.data.get("memories"):
                log.debug(
                    "error_solutions_recalled", count=len(result.data["memories"])
                )
                return result.data

        except Exception as e:
            log.warning("error_solution_recall_failed", error=str(e))

        return None

    def _apply_enhanced_memory_insights(
        self, state: AgentState, memory_results: List, memory_config
    ) -> int:
        """Apply enhanced memory insights to state with confidence filtering."""

        insights_applied = 0
        insights = []

        try:
            # Process schema memories (result[0])
            if (
                len(memory_results) > 0
                and memory_results[0]
                and not isinstance(memory_results[0], Exception)
                and hasattr(memory_results[0], "get")
            ):

                schema_memories = memory_results[0].get("memories", [])
                for memory in schema_memories:
                    if (
                        memory.get("confidence", 0)
                        >= memory_config.min_confidence_threshold
                    ):
                        db_info = memory.get("content", {}).get("database_mapping", {})
                        if db_info:
                            insights.append(
                                f"Known database: {db_info.get('database_path', 'unknown')}"
                            )
                            # Cache schema information
                            if "schema_data" in db_info:
                                state.exploration_results = (
                                    state.exploration_results or {}
                                )
                                state.exploration_results["cached_schema"] = db_info[
                                    "schema_data"
                                ]
                                insights_applied += 1

            # Process pattern memories (result[1])
            if (
                len(memory_results) > 1
                and memory_results[1]
                and not isinstance(memory_results[1], Exception)
                and hasattr(memory_results[1], "get")
            ):

                pattern_memories = memory_results[1].get("memories", [])
                high_confidence_patterns = [
                    m
                    for m in pattern_memories
                    if m.get("confidence", 0) >= memory_config.min_confidence_threshold
                    and m.get("success_rate", 0)
                    >= memory_config.min_confidence_threshold
                ]

                if high_confidence_patterns:
                    best_pattern = max(
                        high_confidence_patterns,
                        key=lambda x: x.get("success_rate", 0) * x.get("confidence", 0),
                    )

                    pattern_content = best_pattern.get("content", {})
                    insights.append(
                        f"Similar successful pattern: {pattern_content.get('trigger_phrase', 'unknown')}"
                    )

                    # Pre-populate SQL if very high confidence
                    if (
                        best_pattern.get("confidence", 0) > 0.9
                        and best_pattern.get("success_rate", 0) > 0.9
                        and pattern_content.get("sql_template")
                    ):
                        state.current_sql = pattern_content["sql_template"]
                        insights.append(
                            "Pre-populated SQL from high-confidence pattern"
                        )
                        insights_applied += 1

            # Process value mappings (result[3])
            if (
                len(memory_results) > 3
                and memory_results[3]
                and not isinstance(memory_results[3], Exception)
                and hasattr(memory_results[3], "get")
            ):

                mapping_memories = memory_results[3].get("memories", [])
                for memory in mapping_memories:
                    if (
                        memory.get("confidence", 0)
                        >= memory_config.min_confidence_threshold
                    ):
                        content = memory.get("content", {})
                        user_term = content.get("user_term", "")
                        db_value = content.get("database_value", "")

                        if (
                            user_term
                            and db_value
                            and user_term.lower() in state.user_query.lower()
                        ):
                            state.discovered_mappings[user_term] = db_value
                            insights.append(
                                f"Applied value mapping: {user_term} → {db_value}"
                            )
                            insights_applied += 1

            # Store insights in state
            if insights:
                state.memory_insights = insights
                state.update_notes("Memory insights: " + "; ".join(insights))

        except Exception as e:
            log.warning("memory_insights_application_failed", error=str(e))

        return insights_applied

    async def _reason_with_memory(self, state: AgentState) -> Dict[str, Any]:
        """Enhanced reasoning with memory insights."""

        # Emit reasoning start
        await self.emit_event(
            "reasoning_start", {"iteration": state.iteration, "query": state.user_query}
        )

        # Build context with memory
        context = self._build_enhanced_context(state)

        # Get reasoning decision
        reasoning = await self.reasoning_engine.decide_action(
            user_query=state.user_query, full_context=context, iteration=state.iteration
        )

        # Emit reasoning result
        await self.emit_event(
            "reasoning",
            {
                "iteration": state.iteration,
                "action_type": reasoning.get("action_type"),
                "reasoning": reasoning.get("reasoning"),
                "notes": reasoning.get("notes"),
            },
        )

        # Update notes
        if reasoning.get("notes"):
            state.update_notes(reasoning["notes"])

        return reasoning

    async def _act_with_events(
        self, state: AgentState, reasoning_result: Dict[str, Any]
    ) -> AgentObservation:
        """Execute action with event emission."""

        action_type = reasoning_result.get("action_type")
        parameters = reasoning_result.get("parameters", {})

        # Emit action event
        await self.emit_event(
            "action",
            {
                "iteration": state.iteration,
                "action_type": action_type,
                "parameters": parameters,
                "reasoning": reasoning_result.get("reasoning"),
            },
        )

        # Create action
        action = state.add_action(
            action_type=ActionType[action_type],
            parameters=parameters,
            reasoning=reasoning_result.get("reasoning", ""),
        )

        # Execute with memory optimization
        observation = await self._execute_optimized(state, action)

        # Emit observation
        await self.emit_event(
            "observation",
            {
                "iteration": state.iteration,
                "success": observation.success,
                "error": observation.error,
                "content_preview": self._preview_content(observation.content),
            },
        )

        return observation

    async def _execute_optimized(
        self, state: AgentState, action: AgentAction
    ) -> AgentObservation:
        """Execute action with memory shortcuts and caching."""

        try:
            # Check for memory shortcuts
            if (
                self.memory_enabled
                and action.action_type == ActionType.EXPLORE_DATABASE
            ):
                shortcut = await self._check_schema_shortcut(state, action.parameters)
                if shortcut:
                    self.metrics["iterations_saved"] += 1
                    return state.add_observation(
                        content=shortcut,
                        success=True,
                        action_type=action.action_type.value,
                    )

            # Check SQL cache
            elif action.action_type == ActionType.GENERATE_SQL:
                cached_sql = self._check_sql_cache(state.user_query)
                if cached_sql:
                    state.current_sql = cached_sql
                    return state.add_observation(
                        content=cached_sql,
                        success=True,
                        action_type=action.action_type.value,
                    )

            # Execute action normally
            result = await self._execute_action(action, state)

            # Learn from successful execution (await to ensure completion)
            if result.get("success") and self.memory_enabled:
                try:
                    await self._learn_from_action(state, action, result)
                except Exception as e:
                    log.warning(
                        "memory_learning_failed",
                        action_type=action.action_type.value,
                        error=str(e),
                    )

            # Create observation
            observation = state.add_observation(
                content=result,
                success=result.get("success", True),
                error=result.get("error"),
                action_type=action.action_type.value,
            )

            return observation

        except Exception as e:
            log.error(
                "action_execution_failed", action=action.action_type.value, error=str(e)
            )
            return state.add_observation(
                content=None,
                success=False,
                error=str(e),
                action_type=action.action_type.value,
            )

    async def _execute_action(
        self, action: AgentAction, state: AgentState
    ) -> Dict[str, Any]:
        """Execute the actual action based on type."""

        # Map action types to tool methods
        if action.action_type == ActionType.EXPLORE_DATABASE:
            return await self.tools.explore_database(**action.parameters)

        elif action.action_type == ActionType.GENERATE_SQL:
            sql = await self.tools.generate_sql(
                query=state.user_query,
                exploration_results=state.exploration_results,
                mappings=state.discovered_mappings,
                agent_notes=state.agent_notes,
            )
            state.current_sql = sql
            return {"success": True, "sql": sql}

        elif action.action_type == ActionType.EXECUTE_SQL:
            if not state.current_sql:
                # Auto-generate if needed
                sql = await self.tools.generate_sql(
                    query=state.user_query,
                    exploration_results=state.exploration_results,
                    mappings=state.discovered_mappings,
                    agent_notes=state.agent_notes,
                )
                state.current_sql = sql

            result = await self.tools.execute_sql(sql=state.current_sql)
            if result.get("success"):
                state.success = True
                state.final_result = result
            return result

        # Database management actions
        elif action.action_type == ActionType.DISCOVER_DATABASES:
            return await self.tools.discover_databases(**action.parameters)

        elif action.action_type == ActionType.SWITCH_DATABASE:
            return await self.tools.switch_database(**action.parameters)

        elif action.action_type == ActionType.GET_CURRENT_DATABASE:
            return await self.tools.get_current_database()

        # Conversational actions
        elif action.action_type == ActionType.CLARIFY_QUERY:
            result = {
                "success": True,
                "clarification_needed": True,
                "message": action.parameters.get("clarification_message", ""),
                "options": action.parameters.get("options", []),
            }
            state.success = True
            state.final_result = result
            return result

        elif action.action_type == ActionType.PROVIDE_ANSWER:
            result = {
                "success": True,
                "direct_answer": True,
                "answer": action.parameters.get("answer", ""),
            }
            state.success = True
            state.final_result = result
            return result

        elif action.action_type == ActionType.RESPOND_TO_USER:
            # Unified response action that handles answer, clarification, or suggestions
            response_type = action.parameters.get("response_type", "answer")
            message = action.parameters.get("message", "")

            # Debug logging for RESPOND_TO_USER
            log.info(
                "respond_to_user_action",
                response_type=response_type,
                message_length=len(message),
                message_preview=(
                    message[:100] + "..." if len(message) > 100 else message
                ),
                full_parameters=action.parameters,
            )

            if response_type == "answer":
                result = {
                    "success": True,
                    "direct_answer": True,
                    "answer": message,
                    "message": message,  # Include both for compatibility
                }
            elif response_type == "clarification":
                result = {
                    "success": True,
                    "clarification_needed": True,
                    "message": message,
                    "options": action.parameters.get("options", []),
                }
            elif response_type == "suggestions":
                result = {
                    "success": True,
                    "suggestions_provided": True,
                    "message": message,
                    "suggestions": action.parameters.get("suggestions", []),
                }
            else:
                # Default to answer if unknown response_type
                result = {
                    "success": True,
                    "direct_answer": True,
                    "answer": message
                    or f"Response type '{response_type}' not supported",
                    "message": message
                    or f"Response type '{response_type}' not supported",
                }

            # Ensure we have a non-empty message
            if not message:
                log.warning(
                    "respond_to_user_empty_message",
                    action_parameters=action.parameters,
                    response_type=response_type,
                )
                result["answer"] = (
                    "I apologize, but I didn't provide a proper response message."
                )
                result["message"] = (
                    "I apologize, but I didn't provide a proper response message."
                )

            state.success = True
            state.final_result = result

            log.info(
                "respond_to_user_result",
                result_keys=list(result.keys()),
                has_answer=bool(result.get("answer")),
                has_message=bool(result.get("message")),
            )

            return result

        # Add other action types as needed...
        else:
            return {"error": f"Action {action.action_type.value} not implemented"}

    async def _build_final_response(self, state: AgentState) -> Dict[str, Any]:
        """Build final response with answer generation."""

        response = {
            "success": state.success,
            "result": state.final_result,
            "iterations": state.iteration,
            "sql": state.current_sql,
            "discovered_mappings": state.discovered_mappings,
            "actions_taken": [
                {
                    "type": action.action_type.value,
                    "parameters": action.parameters,
                    "reasoning": action.reasoning,
                    "timestamp": action.timestamp.isoformat(),
                }
                for action in state.actions
            ],
        }

        # Handle answer generation based on result type
        if state.success and state.final_result:
            # Check for direct conversational responses first (RESPOND_TO_USER results)
            if state.final_result.get("direct_answer"):
                # Agent provided a direct answer via RESPOND_TO_USER action
                response["answer"] = state.final_result.get(
                    "answer", state.final_result.get("message", "")
                )
                await self.emit_event(
                    "answer_provided",
                    {"iteration": state.iteration, "content": response["answer"]},
                )

            # Check for clarification requests
            elif state.final_result.get("clarification_needed"):
                # Frontend handles clarification - no answer generation needed
                response["answer"] = None
                response["clarification"] = {
                    "message": state.final_result.get("message", ""),
                    "options": state.final_result.get("options", []),
                }

            # Check for suggestions
            elif state.final_result.get("suggestions_provided"):
                # Frontend handles suggestions - no answer generation needed
                response["answer"] = None
                response["suggestions"] = {
                    "message": state.final_result.get("message", ""),
                    "suggestions": state.final_result.get("suggestions", []),
                }

            # Generate natural language answer for SQL results
            elif (
                state.final_result.get("columns")
                or state.final_result.get("rows")
                or state.final_result.get("row_count") is not None
                or state.current_sql
            ):
                # This is a SQL execution result - generate natural language answer
                await self.emit_event(
                    "generating_answer",
                    {
                        "iteration": state.iteration,
                        "content": "Generating natural language response...",
                    },
                )

                answer = await self.answer_generator.generate_answer(
                    user_query=state.user_query,
                    query_results=state.final_result,
                    sql_query=state.current_sql,
                    discovered_mappings=state.discovered_mappings,
                )

                response["answer"] = answer

                await self.emit_event(
                    "answer_generated",
                    {"iteration": state.iteration, "content": answer},
                )

            # Fallback: Generate answer if we have SQL but no clear result structure
            elif state.current_sql and state.success:
                await self.emit_event(
                    "generating_answer",
                    {
                        "iteration": state.iteration,
                        "content": "Generating response for SQL query...",
                    },
                )

                # Create a fallback result structure for answer generation
                fallback_result = state.final_result or {}
                answer = await self.answer_generator.generate_answer(
                    user_query=state.user_query,
                    query_results=fallback_result,
                    sql_query=state.current_sql,
                    discovered_mappings=state.discovered_mappings,
                )

                response["answer"] = answer

                await self.emit_event(
                    "answer_generated",
                    {"iteration": state.iteration, "content": answer},
                )

            # Final fallback: no answer
            else:
                response["answer"] = None

        return response

    # === Helper Methods ===

    def _preview_content(self, content: Any) -> Any:
        """Create preview of content for events."""
        if isinstance(content, dict):
            preview = {}
            for key in ["row_count", "columns", "success", "error"]:
                if key in content:
                    preview[key] = content[key]
            if "data" in content and isinstance(content["data"], list):
                preview["sample_rows"] = len(content["data"][:3])
            return preview
        elif isinstance(content, str):
            return content[:200] + "..." if len(content) > 200 else content
        else:
            return str(content)[:200]

    def _build_error_response(
        self, state: AgentState, error: Exception
    ) -> Dict[str, Any]:
        """Build error response."""
        return {
            "success": False,
            "error": str(error),
            "iterations": state.iteration,
            "actions_taken": [
                {
                    "type": action.action_type.value,
                    "parameters": action.parameters,
                    "reasoning": action.reasoning,
                }
                for action in state.actions
            ],
        }

    async def _learn_from_action(
        self, state: AgentState, action: AgentAction, result: Dict[str, Any]
    ) -> None:
        """Enhanced background learning from successful actions."""

        # Debug logging to trace the learning process
        log.info(
            "_learn_from_action_called",
            action_type=action.action_type.value,
            result_success=result.get("success", False),
            memory_enabled=self.memory_enabled,
            memory_tools_available=self.memory_tools is not None,
        )

        if not self.memory_enabled or not self.memory_tools:
            log.warning(
                "learning_skipped_no_memory",
                memory_enabled=self.memory_enabled,
                memory_tools=self.memory_tools is not None,
            )
            return

        try:
            # Get settings for learning behavior
            settings = get_settings()
            memory_config = settings.memory

            log.info(
                "memory_config_check",
                background_learning=memory_config.background_learning,
                action_type=action.action_type.value,
            )

            if not memory_config.background_learning:
                log.warning("learning_skipped_disabled", background_learning=False)
                return

            if action.action_type == ActionType.EXPLORE_DATABASE:
                log.info(
                    "learning_explore_database_check",
                    has_success=result.get("success", False),
                    has_data=result.get("data") is not None,
                    data_preview=str(result.get("data", ""))[:100],
                )

                # Learn database schema information
                if result.get("success") and result.get("data"):
                    schema_data = result["data"]

                    # Create meaningful concept name based on data
                    db_context = action.parameters.get("database_path", "unknown_db")
                    concept_name = (
                        f"schema_{db_context.split('/')[-1].replace('.db', '')}"
                    )

                    log.info(
                        "attempting_schema_learning",
                        concept_name=concept_name,
                        schema_data_type=type(schema_data).__name__,
                    )

                    learning_result = await self.memory_tools.remember_concept(
                        name=concept_name,
                        description=f"Database schema and structure for {db_context}",
                        business_terms=["tables", "columns", "schema", "database"],
                        database_mapping={
                            "database_path": db_context,
                            "schema_data": schema_data,
                            "exploration_query": action.parameters.get("query", ""),
                            "discovered_at": datetime.utcnow().isoformat(),
                        },
                        context={
                            "action_type": "explore_database",
                            "user_query": state.user_query,
                            "iteration": state.iteration,
                        },
                    )
                    log.info(
                        "schema_learning_result",
                        concept_name=concept_name,
                        success=learning_result.success,
                        error=learning_result.error,
                        memory_id=(
                            learning_result.data.get("memory_id")
                            if learning_result.data
                            else None
                        ),
                    )

            elif action.action_type == ActionType.EXECUTE_SQL and result.get("success"):
                log.info(
                    "learning_execute_sql_check",
                    has_success=result.get("success", False),
                    row_count=result.get("row_count", 0),
                    has_current_sql=state.current_sql is not None,
                    sql_preview=state.current_sql[:50] if state.current_sql else None,
                )

                # Learn successful SQL patterns with more context
                row_count = result.get("row_count", 0)

                if row_count > 0 and state.current_sql:
                    # Extract meaningful information for pattern learning
                    tables_used = self._extract_tables_from_sql(state.current_sql)
                    query_type = self._classify_sql_query(state.current_sql)

                    pattern_name = f"{query_type}_{hashlib.md5(state.user_query.encode()).hexdigest()[:8]}"

                    log.info(
                        "attempting_pattern_learning",
                        pattern_name=pattern_name,
                        query_type=query_type,
                        row_count=row_count,
                        tables_used=tables_used,
                    )

                    learning_result = await self.memory_tools.remember_pattern(
                        name=pattern_name,
                        trigger_phrase=state.user_query,
                        sql_template=state.current_sql,
                        tables_used=tables_used,
                        success_context={
                            "row_count": row_count,
                            "execution_successful": True,
                            "query_type": query_type,
                            "iteration_count": state.iteration,
                            "discovered_mappings": state.discovered_mappings,
                        },
                        context={
                            "action_type": "execute_sql",
                            "database_context": action.parameters.get("database_path"),
                            "learned_at": datetime.utcnow().isoformat(),
                        },
                    )
                    log.info(
                        "pattern_learning_result",
                        pattern_name=pattern_name,
                        success=learning_result.success,
                        error=learning_result.error,
                        memory_id=(
                            learning_result.data.get("memory_id")
                            if learning_result.data
                            else None
                        ),
                    )

            elif action.action_type == ActionType.GENERATE_SQL and result.get(
                "success"
            ):
                # Learn about successful SQL generation process
                if state.current_sql and hasattr(state, "exploration_results"):
                    generation_context = {
                        "user_query": state.user_query,
                        "generated_sql": state.current_sql,
                        "exploration_context": state.exploration_results,
                        "reasoning_steps": [act.reasoning for act in state.actions],
                        "iteration": state.iteration,
                    }

                    concept_name = f"sql_generation_{hashlib.md5(state.user_query.encode()).hexdigest()[:8]}"

                    await self.memory_tools.remember_concept(
                        name=concept_name,
                        description="Successful SQL generation process",
                        business_terms=["sql", "generation", "query", "process"],
                        database_mapping=generation_context,
                        context={
                            "action_type": "generate_sql",
                            "learned_at": datetime.utcnow().isoformat(),
                        },
                    )
                    log.info("learned_sql_generation", concept_name=concept_name)

            # Learn from discovered value mappings
            if (
                state.discovered_mappings
                and action.action_type == ActionType.EXECUTE_SQL
            ):
                for user_term, db_value in state.discovered_mappings.items():
                    mapping_name = (
                        f"mapping_{hashlib.md5(user_term.encode()).hexdigest()[:8]}"
                    )

                    await self.memory_tools.remember_mapping(
                        name=mapping_name,
                        user_term=user_term,
                        database_value=db_value,
                        mapping_type="value_mapping",
                        context={
                            "discovered_in_query": state.user_query,
                            "learned_at": datetime.utcnow().isoformat(),
                            "confidence": 0.9,  # High confidence since it led to successful execution
                        },
                    )
                    log.info(
                        "learned_value_mapping", user_term=user_term, db_value=db_value
                    )

        except Exception as e:
            log.warning(
                "enhanced_background_learning_failed",
                action_type=action.action_type.value,
                error=str(e),
            )

    def _classify_sql_query(self, sql: str) -> str:
        """Classify SQL query type for pattern learning."""
        sql_lower = sql.lower().strip()

        if sql_lower.startswith("select"):
            if "group by" in sql_lower:
                return "aggregation"
            elif "order by" in sql_lower:
                return "sorted_selection"
            elif "join" in sql_lower:
                return "join_query"
            elif "where" in sql_lower:
                return "filtered_selection"
            else:
                return "simple_selection"
        elif sql_lower.startswith("insert"):
            return "insert"
        elif sql_lower.startswith("update"):
            return "update"
        elif sql_lower.startswith("delete"):
            return "delete"
        else:
            return "other"

    def _extract_tables_from_sql(self, sql: str) -> List[str]:
        """Extract table names from SQL."""
        tables = []
        sql_lower = sql.lower()

        # Simple extraction from FROM clauses
        if "from" in sql_lower:
            parts = sql_lower.split("from")
            for part in parts[1:]:
                table = part.split()[0].strip("(),")
                if table and not table.startswith("("):
                    tables.append(table)

        return list(set(tables))

    def _build_enhanced_context(self, state: AgentState) -> str:
        """Build context with memory insights."""

        context_parts = [f"=== ITERATION {state.iteration}/{state.max_iterations} ==="]

        # === CONVERSATION HISTORY FIRST (Most Important Context) ===
        # Extract conversation history from agent notes if present
        conversation_context = ""
        if state.agent_notes and "Conversation History:" in state.agent_notes:
            # Extract just the conversation part
            lines = state.agent_notes.split("\n")
            conv_started = False
            conv_lines = []
            for line in lines:
                if line.strip() == "Conversation History:":
                    conv_started = True
                    continue
                elif conv_started:
                    if line.startswith("Previous Query") or line.startswith("  "):
                        conv_lines.append(line)
                    else:
                        break

            if conv_lines:
                conversation_context = "\n".join(conv_lines)

        if conversation_context:
            context_parts.append(f"\n=== CONVERSATION HISTORY ===")
            context_parts.append("Previous context from this conversation:")
            context_parts.append(conversation_context)

        # Add memory insights if available
        if hasattr(state, "memory_insights") and state.memory_insights:
            context_parts.append("\n=== MEMORY INSIGHTS ===")
            for insight in state.memory_insights:
                context_parts.append(f"- {insight}")

        # Add action history chronologically
        context_parts.append(f"\n=== ACTION HISTORY ===")
        for i, (action, obs) in enumerate(zip(state.actions, state.observations)):
            context_parts.append(f"\nStep {i+1}: {action.action_type.value}")
            if action.parameters:
                context_parts.append(f"Parameters: {action.parameters}")
            context_parts.append(f"Reasoning: {action.reasoning}")
            context_parts.append(f"Result: {'Success' if obs.success else 'Failed'}")

            if obs.content:
                # Include meaningful content based on action type
                if action.action_type.value == "discover_databases":
                    if isinstance(obs.content, dict) and "databases" in obs.content:
                        db_list = obs.content.get("databases", [])
                        context_parts.append(
                            f"Found {len(db_list)} databases: {', '.join(db_list[:10])}"
                        )
                        if len(db_list) > 10:
                            context_parts.append(f"...and {len(db_list) - 10} more")
                    else:
                        context_parts.append(f"Content: {str(obs.content)[:500]}...")
                elif action.action_type.value == "explore_database":
                    if isinstance(obs.content, dict):
                        if "row_count" in obs.content:
                            context_parts.append(
                                f"Found {obs.content['row_count']} results"
                            )
                        if "columns" in obs.content:
                            context_parts.append(
                                f"Columns: {obs.content.get('columns', [])}"
                            )
                        if "data" in obs.content and obs.content["data"]:
                            sample_data = obs.content["data"][:3]
                            context_parts.append(f"Sample data: {sample_data}")
                    else:
                        context_parts.append(f"Content: {str(obs.content)[:500]}...")
                elif action.action_type.value == "generate_sql":
                    if isinstance(obs.content, dict) and "sql" in obs.content:
                        context_parts.append(f"Generated SQL: {obs.content['sql']}")
                    else:
                        context_parts.append(f"Content: {str(obs.content)[:500]}...")
                else:
                    context_parts.append(f"Content: {str(obs.content)[:500]}...")

            if obs.error:
                context_parts.append(f"Error: {obs.error}")

        # Add current state information
        context_parts.append(f"\n=== CURRENT STATE ===")

        # Database exploration status
        if state.exploration_results:
            if state.exploration_results.get("discovered_tables"):
                context_parts.append(
                    f"Known tables: {', '.join(state.exploration_results['discovered_tables'])}"
                )

        # SQL status
        if state.current_sql:
            context_parts.append(f"Generated SQL available:")
            context_parts.append(state.current_sql)
        else:
            context_parts.append("No SQL generated yet")

        # Final result status
        if state.final_result:
            context_parts.append(
                f"Final result obtained: {type(state.final_result).__name__}"
            )
        elif state.success:
            context_parts.append("Task marked as successful")
        else:
            context_parts.append("Task not yet complete")

        # Add remaining agent notes (excluding conversation history since we moved it up)
        if state.agent_notes:
            # Filter out conversation history since we already included it prominently
            filtered_notes = []
            lines = state.agent_notes.split("\n")
            skip_conv = False
            for line in lines:
                if line.strip() == "Conversation History:":
                    skip_conv = True
                    continue
                elif skip_conv:
                    if line.startswith("Previous Query") or line.startswith("  "):
                        continue
                    else:
                        skip_conv = False

                if not skip_conv and line.strip():
                    filtered_notes.append(line)

            if filtered_notes:
                context_parts.append(f"\n=== ADDITIONAL NOTES ===")
                context_parts.append("\n".join(filtered_notes))

        return "\n".join(context_parts)

    def _apply_memory_insights(self, state: AgentState, memory_results: List) -> None:
        """Apply memory recall results to state."""

        insights = []

        # Process schema memories
        if memory_results[0] and hasattr(memory_results[0], "data"):
            for memory in memory_results[0].data.get("memories", []):
                db_info = memory.get("content", {}).get("database_mapping", {})
                if db_info:
                    insights.append(
                        f"Known database: {db_info.get('database_path', 'unknown')}"
                    )
                    # Cache schema
                    if "tables" in db_info:
                        state.exploration_results = state.exploration_results or {}
                        state.exploration_results["discovered_tables"] = db_info[
                            "tables"
                        ]

        # Process pattern memories
        if memory_results[1] and hasattr(memory_results[1], "data"):
            for memory in memory_results[1].data.get("memories", []):
                pattern = memory.get("content", {})
                if pattern:
                    insights.append(
                        f"Similar query pattern: {pattern.get('trigger_phrase', 'unknown')}"
                    )

        # Store insights
        if insights:
            state.memory_insights = insights
            state.update_notes("Memory insights: " + "; ".join(insights))

    async def _check_schema_shortcut(
        self, state: AgentState, params: Dict
    ) -> Optional[Dict]:
        """Check if we can shortcut database exploration."""

        db_path = params.get("database_path")
        if not db_path:
            return None

        # Check cache
        if db_path in self.schema_cache:
            self.metrics["cache_hits"] += 1
            return self.schema_cache[db_path]

        return None

    def _check_sql_cache(self, query: str) -> Optional[str]:
        """Check SQL cache for similar queries."""

        cache_key = hashlib.md5(query.encode()).hexdigest()
        if cache_key in self.sql_cache:
            self.metrics["cache_hits"] += 1
            return self.sql_cache[cache_key]

        return None

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get agent performance metrics."""
        total_requests = self.metrics["cache_hits"] + self.metrics["cache_misses"]
        cache_hit_rate = self.metrics["cache_hits"] / max(total_requests, 1) * 100

        return {
            "cache_hit_rate_percent": round(cache_hit_rate, 1),
            "total_requests": total_requests,
            "memory_recalls": self.metrics["memory_recalls"],
            "iterations_saved": self.metrics["iterations_saved"],
        }

    # === Conversation Context Management ===

    def _build_conversation_context(self, conversation_state: ConversationState) -> str:
        """Build conversation context from history for agent reasoning."""
        if not conversation_state.history:
            return ""

        context_parts = []
        # Get recent interactions (last 3 to avoid overwhelming context)
        recent_history = conversation_state.get_recent_context(limit=3)

        for i, interaction in enumerate(reversed(recent_history), 1):
            user_input = interaction.get("user_input", "")
            response = interaction.get("response", {})

            context_parts.append(f"Previous Query {i}: {user_input}")

            # Extract key information from response
            if isinstance(response, dict):
                if response.get("sql"):
                    context_parts.append(f"  SQL: {response['sql']}")
                if response.get("answer"):
                    context_parts.append(f"  Answer: {response['answer'][:200]}...")
                elif response.get("message"):
                    context_parts.append(f"  Result: {response['message'][:200]}...")

        return "\n".join(context_parts)

    async def _save_conversation_state(
        self,
        conversation_state: ConversationState,
        user_query: str,
        result: Dict[str, Any],
        agent_state: AgentState,
    ) -> None:
        """Save the conversation state with the new interaction."""
        try:
            # Build response for conversation history
            response_data = {
                "success": result["success"],
                "sql": result.get("sql"),
                "answer": result.get("answer"),
                "iterations": result["iterations"],
                "agent_actions": [
                    {
                        "type": action.action_type.value,
                        "reasoning": action.reasoning,
                    }
                    for action in agent_state.actions
                ],
            }

            # Add interaction to conversation history
            conversation_state.add_interaction(
                user_input=user_query,
                response=response_data,
            )

            # Save to session manager
            self.session_manager.save(
                conversation_state.conversation_id, conversation_state
            )

            log.info(
                "conversation_state_saved",
                conversation_id=conversation_state.conversation_id,
                total_interactions=len(conversation_state.history),
            )

        except Exception as e:
            log.warning(
                "failed_to_save_conversation_state",
                error=str(e),
                conversation_id=conversation_state.conversation_id,
            )
