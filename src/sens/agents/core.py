"""Core SENS Agent implementation with ReAct loop."""

import asyncio
from typing import Any, Dict, List, Optional

# Import structlog if available, otherwise create a simple logger
try:
    import structlog
    log = structlog.get_logger()
    HAS_STRUCTLOG = True
except ImportError:
    import logging
    log = logging.getLogger(__name__)
    HAS_STRUCTLOG = False

from sens.agents.base import (
    ActionType,
    AgentAction,
    AgentObservation,
    AgentState,
    AgentThought,
    BaseAgent,
)
from sens.agents.memory import AgentMemory
from sens.agents.reasoning import ReasoningEngine
from sens.agents.reflection import ReflectionEngine
from sens.agents.tools import AgentTools
from sens.exceptions import AgentError

log = structlog.get_logger()


class SENSAgent(BaseAgent):
    """Main SENS agent that orchestrates the ReAct loop."""

    def __init__(
        self,
        tools: Optional[AgentTools] = None,
        memory: Optional[AgentMemory] = None,
        reasoning_engine: Optional[ReasoningEngine] = None,
        reflection_engine: Optional[ReflectionEngine] = None,
        max_iterations: int = 5,
    ):
        """Initialize the SENS agent.

        Args:
            tools: Agent tools for database operations
            memory: Agent memory for learning
            reasoning_engine: Engine for LLM-based reasoning
            reflection_engine: Engine for interpreting observations
            max_iterations: Maximum number of reasoning iterations
        """
        self.tools = tools or AgentTools()
        self.memory = memory or AgentMemory()
        self.reasoning_engine = reasoning_engine or ReasoningEngine()
        self.reflection_engine = reflection_engine or ReflectionEngine()
        self.max_iterations = max_iterations

        log.info("sens_agent_initialized", max_iterations=max_iterations)

    async def process_query(
        self, user_query: str, conversation_id: str
    ) -> Dict[str, Any]:
        """Process a user query using the ReAct loop.

        Args:
            user_query: Natural language query from user
            conversation_id: Unique conversation identifier

        Returns:
            Dict containing results, reasoning trace, and metadata
        """
        # Initialize agent state
        state = AgentState(
            user_query=user_query,
            conversation_id=conversation_id,
            max_iterations=self.max_iterations,
        )

        log.info(
            "agent_starting_query",
            query=user_query,
            conversation_id=conversation_id,
        )

        try:
            # Simple loop: reason and act
            while state.should_continue:
                state.iteration += 1

                log.info(
                    "🔄 agent_iteration_start",
                    iteration=f"{state.iteration}/{state.max_iterations}",
                    query=(
                        user_query[:100] + "..."
                        if len(user_query) > 100
                        else user_query
                    ),
                )

                # REASON: Analyze everything and decide what to do
                reasoning_result = await self.reason(state)

                # ACT: Execute the action
                await self.act(state, reasoning_result)

                # If we successfully executed SQL, we're done
                if state.success and state.current_sql:
                    # Store successful patterns
                    await self.memory.store_successful_query(
                        user_query=user_query,
                        sql=state.current_sql,
                        mappings=state.discovered_mappings,
                    )

            # Build final response
            return self._build_response(state)

        except Exception as e:
            log.error("agent_error", error=str(e), conversation_id=conversation_id)
            state.add_observation(
                content=None,
                success=False,
                error=str(e),
            )
            return self._build_error_response(state, e)

    async def reason(self, state: AgentState) -> Dict[str, Any]:
        """Analyze everything and decide what action to take."""
        log.info("🤔 agent_reasoning_start", iteration=state.iteration)

        # Build complete context
        context = self._build_full_context(state)

        # Log context summary
        log.debug(
            "agent_context_summary",
            iteration=state.iteration,
            discovered_tables=len(
                state.exploration_results.get("discovered_tables", [])
            ),
            has_sql=bool(state.current_sql),
            notes_length=len(state.agent_notes),
            previous_actions=len(state.actions),
        )

        # Ask LLM to reason and decide
        reasoning = await self.reasoning_engine.decide_action(
            user_query=state.user_query,
            full_context=context,
            iteration=state.iteration,
        )

        # Log reasoning result
        log.info(
            "💡 agent_reasoning_decision",
            iteration=state.iteration,
            action=reasoning.get("action_type"),
            reason=(
                reasoning.get("reasoning")[:200] + "..."
                if len(reasoning.get("reasoning", "")) > 200
                else reasoning.get("reasoning")
            ),
        )

        # Update notes if provided
        if reasoning.get("notes"):
            state.update_notes(reasoning["notes"])
            log.info(
                "📝 agent_notes_added",
                iteration=state.iteration,
                new_note=reasoning["notes"],
            )

        return reasoning

    def _build_full_context(self, state: AgentState) -> str:
        """Build complete context for reasoning."""
        context_parts = []

        # Add iteration info
        context_parts.append(
            f"=== ITERATION {state.iteration}/{state.max_iterations} ==="
        )

        # Add all previous actions and observations
        for i, (action, obs) in enumerate(zip(state.actions, state.observations)):
            context_parts.append(f"\n--- Action {i+1} ---")
            context_parts.append(f"Type: {action.action_type.value}")
            context_parts.append(f"Parameters: {action.parameters}")
            context_parts.append(f"Result: {'Success' if obs.success else 'Failed'}")
            if obs.content:
                context_parts.append(f"Content: {str(obs.content)[:500]}...")
            if obs.error:
                context_parts.append(f"Error: {obs.error}")

        # Add discovered information
        if state.exploration_results:
            context_parts.append("\n=== DISCOVERED INFORMATION ===")
            if state.exploration_results.get("discovered_tables"):
                tables = state.exploration_results["discovered_tables"]
                context_parts.append(f"Tables: {', '.join(tables)}")
            if state.exploration_results.get("table_schemas"):
                context_parts.append(
                    f"Explored schemas: {list(state.exploration_results['table_schemas'].keys())}"
                )

        # Add current SQL if any
        if state.current_sql:
            context_parts.append("\n=== CURRENT SQL ===")
            context_parts.append(state.current_sql)

        # Add notes
        if state.agent_notes:
            context_parts.append("\n=== AGENT NOTES ===")
            context_parts.append(state.agent_notes)

        return "\n".join(context_parts)

    async def act(
        self, state: AgentState, reasoning_result: Dict[str, Any]
    ) -> AgentObservation:
        """Execute the action decided by reasoning."""
        action_type = reasoning_result.get("action_type")
        parameters = reasoning_result.get("parameters", {})

        # Log action execution
        log.info(
            "🎯 agent_action_execute",
            iteration=state.iteration,
            action=action_type,
            has_params=bool(parameters),
        )

        # Create action record
        action = state.add_action(
            action_type=ActionType[action_type],
            parameters=parameters,
            reasoning=reasoning_result.get("reasoning", ""),
        )

        # Execute the action
        observation = await self.observe(state, action)

        # Log observation result
        if observation.success:
            log.info(
                "✓ agent_action_success",
                iteration=state.iteration,
                action=action_type,
                result_type=(
                    type(observation.content).__name__
                    if observation.content
                    else "None"
                ),
                result_size=self._get_result_size(observation.content),
            )
        else:
            log.warning(
                "✗ agent_action_failed",
                iteration=state.iteration,
                action=action_type,
                error=observation.error,
            )

        return observation

    def _get_result_size(self, content: Any) -> str:
        """Get a human-readable size description of the result."""
        if isinstance(content, dict):
            if "row_count" in content:
                return f"{content['row_count']} rows"
            elif "data" in content and isinstance(content["data"], list):
                return f"{len(content['data'])} items"
        elif isinstance(content, str):
            return f"{len(content)} chars"
        elif isinstance(content, list):
            return f"{len(content)} items"
        return "unknown"

    def _update_exploration_results(
        self, state: AgentState, exploration_data: Dict[str, Any]
    ) -> None:
        """Update exploration results from database exploration."""
        # Initialize exploration results structure if needed
        if not state.exploration_results:
            state.exploration_results = {
                "discovered_tables": [],
                "table_schemas": {},
                "sample_data": {},
                "relationships": {},
                "value_mappings": {},
            }

        # Extract table information from exploration query and results
        if exploration_data.get("columns") and exploration_data.get("data"):
            columns = exploration_data["columns"]
            data = exploration_data["data"]

            # Detect what kind of exploration this was
            if "table_name" in columns:
                # This was a table discovery query
                table_names = [row[0] for row in data if row]
                for table in table_names:
                    if table not in state.exploration_results["discovered_tables"]:
                        state.exploration_results["discovered_tables"].append(table)
                log.info("discovered_tables", tables=table_names)

            elif "column_name" in columns:
                # This was a column discovery query for a specific table
                column_names = [row[0] for row in data if row]
                # Try to infer table name from recent actions or queries
                table_name = self._infer_table_from_recent_actions(state)
                if table_name:
                    state.exploration_results["table_schemas"][
                        table_name
                    ] = column_names
                    log.info(
                        "discovered_table_schema",
                        table=table_name,
                        columns=column_names,
                    )

            else:
                # This was a data sampling query
                table_name = self._infer_table_from_recent_actions(state)
                if table_name and data:
                    # Store sample data and schema
                    state.exploration_results["table_schemas"][table_name] = columns
                    state.exploration_results["sample_data"][table_name] = data[
                        :5
                    ]  # Keep first 5 rows

                    # Look for potential value mappings (e.g., company names to symbols)
                    self._extract_value_mappings(state, table_name, columns, data)

                    log.info(
                        "discovered_sample_data",
                        table=table_name,
                        columns=columns,
                        rows=len(data),
                    )

    def _infer_table_from_recent_actions(self, state: AgentState) -> Optional[str]:
        """Try to infer which table the last exploration was about."""
        # Look at recent exploration queries to infer table name
        for action in reversed(state.actions[-3:]):  # Check last 3 actions
            if action.action_type == ActionType.EXPLORE_DATABASE:
                query = action.parameters.get("query", "").lower()

                # First check for WHERE table_name = 'xxx' pattern (for schema queries)
                import re

                table_match = re.search(
                    r"where\s+table_name\s*=\s*['\"]([^'\"]+)['\"]", query
                )
                if table_match:
                    return table_match.group(1)

                # Extract table name from FROM clause
                if "from " in query:
                    parts = query.split("from ")
                    if len(parts) > 1:
                        table_part = parts[1].split()[0].strip()
                        # Remove schema prefixes and quotes
                        table_name = (
                            table_part.replace("information_schema.", "")
                            .replace("'", "")
                            .replace('"', "")
                        )
                        if table_name not in ["tables", "columns"]:  # Skip meta tables
                            return table_name

        return None

    def _extract_value_mappings(
        self, state: AgentState, table_name: str, columns: List[str], data: List[List]
    ) -> None:
        """Extract potential value mappings from sample data."""
        try:
            if not data or not columns:
                return

            # Look for common mapping patterns in financial data
            symbol_idx = None
            company_name_idx = None

            for i, col in enumerate(columns):
                col_lower = col.lower()
                if col_lower in ["symbol", "ticker"]:
                    symbol_idx = i
                elif col_lower in ["company_name", "name", "company"]:
                    company_name_idx = i

            # Extract mappings if we found both symbol and company name columns
            if symbol_idx is not None and company_name_idx is not None:
                for row in data[:10]:  # Check first 10 rows
                    if len(row) > max(symbol_idx, company_name_idx):
                        symbol = row[symbol_idx]
                        company_name = row[company_name_idx]

                        if symbol and company_name:
                            # Create mapping from company name to symbol
                            state.exploration_results["value_mappings"][
                                str(company_name)
                            ] = str(symbol)

                            # Also create mapping for partial matches
                            if " " in str(company_name):
                                # Map first word of company name to symbol (e.g., "Apple" -> "AAPL")
                                first_word = str(company_name).split()[0]
                                state.exploration_results["value_mappings"][
                                    first_word
                                ] = str(symbol)

                # Update discovered_mappings in state for immediate use
                state.discovered_mappings.update(
                    state.exploration_results["value_mappings"]
                )

                log.info(
                    "extracted_value_mappings",
                    mappings=state.exploration_results["value_mappings"],
                )

        except Exception as e:
            log.warning("value_mapping_extraction_failed", error=str(e))

    async def observe(self, state: AgentState, action: AgentAction) -> AgentObservation:
        """Execute the action and observe the result."""
        try:
            # MINIMAL MODE: Only handle GENERATE_SQL and EXECUTE_SQL
            if action.action_type == ActionType.GENERATE_SQL:
                log.debug("🔨 generating_sql", iteration=state.iteration)

                # Check memory for similar queries first
                cached_sql = await self.memory.recall_similar_query(
                    state.user_query,
                    state.retrieved_schema,
                )

                if cached_sql:
                    result = cached_sql
                    log.info("💾 using_cached_sql", sql=cached_sql[:100] + "...")
                else:
                    result = await self.tools.generate_sql(
                        query=state.user_query,
                        exploration_results=state.exploration_results,
                        mappings=state.discovered_mappings,
                        agent_notes=state.agent_notes,
                    )
                    log.info(
                        "📝 sql_generated",
                        iteration=state.iteration,
                        sql_preview=(
                            result[:100] + "..." if len(result) > 100 else result
                        ),
                    )

                state.current_sql = result

            elif action.action_type == ActionType.EXECUTE_SQL:
                log.debug("🚀 executing_sql", iteration=state.iteration)
                # Execute SQL needs the current SQL from state
                if not state.current_sql:
                    result = {
                        "success": False,
                        "error": "No SQL query available to execute",
                    }
                else:
                    result = await self.tools.execute_sql(sql=state.current_sql)

                if result.get("success"):
                    log.info(
                        "📊 sql_execution_complete",
                        iteration=state.iteration,
                        rows=result.get("row_count", 0),
                        columns=len(result.get("columns", [])),
                        has_data=bool(result.get("rows")),
                        first_row=(
                            result.get("rows", [[]])[0] if result.get("rows") else None
                        ),
                    )

                    # SQL executed successfully - mark agent as successful and store result
                    state.success = True
                    state.final_result = result
                    log.info("✅ SQL executed successfully, agent marked as successful")

            elif action.action_type == ActionType.EXPLORE_DATABASE:
                query_preview = action.parameters.get("query", "")[:100]
                log.debug(
                    "🔍 exploring_database",
                    iteration=state.iteration,
                    query=query_preview,
                )

                result = await self.tools.explore_database(**action.parameters)

                # Update exploration results if successful
                if result.get("success") and result.get("data"):
                    self._update_exploration_results(state, result)
                    log.info(
                        "💎 exploration_discovered",
                        iteration=state.iteration,
                        rows_found=result.get("row_count", 0),
                        tables_discovered=len(
                            state.exploration_results.get("discovered_tables", [])
                        ),
                        schemas_mapped=len(
                            state.exploration_results.get("table_schemas", {})
                        ),
                    )

            # Conversational actions
            elif action.action_type == ActionType.CLARIFY_QUERY:
                log.debug("🤔 asking_for_clarification", iteration=state.iteration)
                clarification_text = action.parameters.get("clarification_message", "")
                options = action.parameters.get("options", [])

                result = {
                    "success": True,
                    "clarification_needed": True,
                    "message": clarification_text,
                    "options": options,
                    "action_type": "clarify_query",
                }

                # Mark agent as successful since we're providing value to user
                state.success = True
                state.final_result = result
                log.info("💬 Clarification requested from user")

            elif action.action_type == ActionType.PROVIDE_ANSWER:
                log.debug("📝 providing_direct_answer", iteration=state.iteration)
                answer_text = action.parameters.get("answer", "")

                result = {
                    "success": True,
                    "direct_answer": True,
                    "answer": answer_text,
                    "action_type": "provide_answer",
                }

                # Mark agent as successful
                state.success = True
                state.final_result = result
                state.natural_language_answer = answer_text
                log.info("✅ Direct answer provided without SQL")

            elif action.action_type == ActionType.SUGGEST_OPTIONS:
                log.debug("💡 suggesting_options", iteration=state.iteration)
                suggestions = action.parameters.get("suggestions", [])
                context = action.parameters.get("context", "")

                result = {
                    "success": True,
                    "suggestions": suggestions,
                    "context": context,
                    "action_type": "suggest_options",
                }

                # Mark agent as successful
                state.success = True
                state.final_result = result
                log.info("💡 Options suggested to user")

            # All other actions are disabled in minimal mode
            elif action.action_type == ActionType.SEARCH_SCHEMA:
                result = {
                    "error": "Schema search disabled in minimal mode",
                    "tables": [],
                    "columns": [],
                }
            elif action.action_type == ActionType.SEARCH_VALUES:
                result = [{"error": "Value search disabled in minimal mode"}]
            elif action.action_type == ActionType.FIND_SIMILAR_VALUES:
                result = {
                    "found": False,
                    "error": "Similar values search disabled in minimal mode",
                    "values": [],
                }
            elif action.action_type == ActionType.DIAGNOSE_EMPTY_RESULTS:
                result = {
                    "error": "Diagnosis disabled in minimal mode",
                    "issues": [],
                    "suggestions": [],
                }
            else:
                result = {
                    "error": f"Action {action.action_type.value} disabled in minimal mode"
                }

            # Create observation
            # Check if the result indicates success or failure
            success = True
            if isinstance(result, dict):
                # For execute_sql, check the success flag
                if "success" in result:
                    success = result["success"]
                # For other actions, check for errors
                elif "error" in result and result["error"]:
                    success = False

            observation = state.add_observation(
                content=result,
                success=success,
                action_type=action.action_type.value,
            )

            # Log the full observation for debugging
            log.info(
                "agent_observation_detail",
                iteration=state.iteration,
                action_type=action.action_type.value,
                success=success,
                content_type=type(result).__name__,
                content_preview=(
                    str(result)[:500] + "..." if len(str(result)) > 500 else str(result)
                ),
                full_content=(
                    result
                    if isinstance(result, dict) and len(str(result)) < 1000
                    else "Content too large - see content_preview"
                ),
            )

        except Exception as e:
            log.error("action_failed", action=action.action_type.value, error=str(e))
            observation = state.add_observation(
                content=None,
                success=False,
                error=str(e),
                action_type=action.action_type.value,
            )

        return observation

    async def reflect(self, state: AgentState, observation: AgentObservation) -> None:
        """Reflect on the observation and update state.

        This is the LEARN phase of ReAct where we:
        1. Create full context from the observation
        2. Let the reasoning engine reflect on it
        3. Update agent notes with discoveries
        """
        # Get the action that led to this observation
        last_action = state.get_last_action()
        if not last_action:
            return

        # Create reflection context with full observation
        reflection_context = self.reflection_engine.create_reflection_context(
            state=state, action=last_action, observation=observation
        )

        # Log the reflection context
        log.info(
            "agent_reflection_context",
            iteration=state.iteration,
            context_preview=(
                reflection_context[:500] + "..."
                if len(reflection_context) > 500
                else reflection_context
            ),
        )

        # Ask reasoning engine to reflect on this context
        reflection_prompt = f"""
Based on the following action and observation, what did we learn?
What should we note for future iterations?

{reflection_context}

Respond with:
LEARNINGS: <What we discovered from this observation>
NOTES_UPDATE: <Specific notes to add about what we found or didn't find>
NEXT_DIRECTION: <What we should explore next based on this>
"""

        try:
            # Use reasoning engine to reflect
            reflection_response = await self.reasoning_engine._call_llm(
                reflection_prompt
            )

            # Parse reflection response
            lines = reflection_response.strip().split("\n")
            learnings = ""
            notes_update = ""
            next_direction = ""

            for line in lines:
                if line.startswith("LEARNINGS:"):
                    learnings = line.replace("LEARNINGS:", "").strip()
                elif line.startswith("NOTES_UPDATE:"):
                    notes_update = line.replace("NOTES_UPDATE:", "").strip()
                elif line.startswith("NEXT_DIRECTION:"):
                    next_direction = line.replace("NEXT_DIRECTION:", "").strip()

            # Update notes if we have them
            if notes_update and notes_update.lower() != "none":
                state.update_notes(notes_update)
                log.info(
                    "reflection_notes_update",
                    iteration=state.iteration,
                    notes_update=notes_update,
                    full_notes=state.agent_notes,
                )

            # Add learnings as a thought
            if learnings:
                state.add_thought(f"Reflection: {learnings}", confidence=0.9)

            # Log the reflection results
            log.info(
                "agent_reflection_complete",
                iteration=state.iteration,
                learnings=learnings,
                notes_update=notes_update,
                next_direction=next_direction,
            )

        except Exception as e:
            log.error("reflection_failed", error=str(e))
            # Fall back to simple reflection
            state.add_thought(
                f"Observed: {observation.success}. Need to analyze results and plan next step.",
                confidence=0.7,
            )

        # Original reflection logic for specific cases
        if not observation.success:
            # Analyze the error
            if "does not exist" in str(observation.error):
                state.add_thought(
                    "The query failed because a table or column doesn't exist. "
                    "I should verify the schema."
                )
            elif "no results" in str(observation.error).lower():
                state.add_thought(
                    "The query returned no results. I should investigate why - "
                    "possibly incorrect values or filters."
                )
        else:
            # Handle successful observations
            action_type = observation.metadata.get("action_type")

            if action_type == ActionType.EXPLORE_DATABASE.value:
                # Update exploration results from database exploration
                if observation.content and observation.content.get("success"):
                    self._update_exploration_results(state, observation.content)
                    # Don't add generic thought - reflection engine handles this

            elif action_type == ActionType.SEARCH_SCHEMA.value:
                # Count how many times we've searched schema
                schema_searches = sum(
                    1
                    for a in state.actions
                    if a.action_type == ActionType.SEARCH_SCHEMA
                )
                if schema_searches >= 2:
                    state.add_thought(
                        "I've retrieved the schema successfully. The database has daily_prices tables "
                        "with columns like symbol, trade_date, open, close, high, low. "
                        "I should now generate SQL for the Apple stock prices query."
                    )
                    # Force schema as retrieved to move to next step
                    if observation.content:
                        state.retrieved_schema = observation.content

            elif action_type == ActionType.EXECUTE_SQL.value:
                if observation.content and observation.content.get("row_count", 0) == 0:
                    state.add_thought(
                        "Query executed successfully but returned no rows. "
                        "I need to diagnose why and find the correct values."
                    )
                elif (
                    observation.content and observation.content.get("row_count", 0) > 0
                ):
                    state.add_thought(
                        f"Query successful! Retrieved {observation.content['row_count']} rows."
                    )

            elif action_type == ActionType.SEARCH_VALUES.value:
                if observation.content:
                    state.add_thought(
                        f"Found database values: {observation.content}. "
                        "I should use these in the query."
                    )

    def _build_response(self, state: AgentState) -> Dict[str, Any]:
        """Build the final response from the agent state."""
        log.info(
            "agent_build_response",
            state_success=state.success,
            has_final_result=bool(state.final_result),
            final_result_type=(
                type(state.final_result).__name__ if state.final_result else None
            ),
            final_result_keys=(
                list(state.final_result.keys())
                if isinstance(state.final_result, dict)
                else None
            ),
            iterations=state.iteration,
        )

        response = {
            "success": state.success,
            "result": state.final_result,
            "actions_taken": [
                {
                    "type": action.action_type.value,
                    "parameters": action.parameters,
                    "reasoning": action.reasoning,
                    "timestamp": action.timestamp.isoformat(),
                }
                for action in state.actions
            ],
            "discovered_mappings": state.discovered_mappings,
            "iterations": state.iteration,
            "sql": state.current_sql,
        }

        log.info(
            "agent_final_response",
            success=response["success"],
            has_result=bool(response["result"]),
            result_type=(
                type(response["result"]).__name__ if response["result"] else None
            ),
            result_sample=(
                {
                    "row_count": response["result"].get("row_count"),
                    "columns": response["result"].get("columns"),
                    "has_rows": bool(response["result"].get("rows")),
                }
                if isinstance(response["result"], dict)
                else None
            ),
            sql_preview=(
                response["sql"][:100] + "..."
                if response["sql"] and len(response["sql"]) > 100
                else response["sql"]
            ),
            iterations=response["iterations"],
            action_count=len(response["actions_taken"]),
        )

        return response

    def _build_error_response(
        self, state: AgentState, error: Exception
    ) -> Dict[str, Any]:
        """Build an error response."""
        response = self._build_response(state)
        response["success"] = False
        response["error"] = str(error)
        return response
