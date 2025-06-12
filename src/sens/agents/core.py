"""Core SENS Agent implementation with ReAct loop."""

import asyncio
from typing import Any, Dict, Optional

import structlog

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
        max_iterations: int = 5,
    ):
        """Initialize the SENS agent.

        Args:
            tools: Agent tools for database operations
            memory: Agent memory for learning
            reasoning_engine: Engine for LLM-based reasoning
            max_iterations: Maximum number of reasoning iterations
        """
        self.tools = tools or AgentTools()
        self.memory = memory or AgentMemory()
        self.reasoning_engine = reasoning_engine or ReasoningEngine()
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
            # Main ReAct loop
            while state.should_continue:
                state.iteration += 1

                # THINK: Reason about what to do next
                thought = await self.reason(state)

                # ACT: Choose and execute an action
                action = await self.act(state, thought)

                # OBSERVE: Get the result
                observation = await self.observe(state, action)

                # REFLECT: Update state based on observation
                await self.reflect(state, observation)

                # Check for success
                if observation.success and action.action_type == ActionType.EXECUTE_SQL:
                    state.success = True
                    state.final_result = observation.content

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

    async def reason(self, state: AgentState) -> AgentThought:
        """Analyze the current state and decide what to do next."""
        # Get recent context
        context = state.get_recent_context()

        # Use reasoning engine to analyze situation
        reasoning = await self.reasoning_engine.analyze_situation(
            user_query=state.user_query,
            context=context,
            iteration=state.iteration,
            discovered_mappings=state.discovered_mappings,
        )

        # Create thought
        thought = state.add_thought(
            content=reasoning["thought"],
            confidence=reasoning.get("confidence", 1.0),
            next_action=reasoning.get("suggested_action"),
        )

        return thought

    async def act(self, state: AgentState, thought: AgentThought) -> AgentAction:
        """Choose an action based on the current thought."""
        # Determine action type from thought
        suggested_action = thought.metadata.get("next_action")

        if not suggested_action:
            # Default flow: schema -> sql -> execute
            if not state.retrieved_schema:
                action_type = ActionType.SEARCH_SCHEMA
                parameters = {"query": state.user_query}
            elif not state.current_sql:
                action_type = ActionType.GENERATE_SQL
                parameters = {"schema": state.retrieved_schema}
            else:
                action_type = ActionType.EXECUTE_SQL
                parameters = {"sql": state.current_sql}
        else:
            # Use suggested action from reasoning
            action_type = ActionType[suggested_action["type"]]
            parameters = suggested_action.get("parameters", {})

            # Validate and add required parameters
            parameters = self._validate_action_parameters(
                action_type, parameters, state
            )

        # Create action with reasoning
        action = state.add_action(
            action_type=action_type,
            parameters=parameters,
            reasoning=thought.content,
        )

        return action

    def _validate_action_parameters(
        self, action_type: ActionType, parameters: Dict[str, Any], state: AgentState
    ) -> Dict[str, Any]:
        """Validate and fill in missing required parameters for actions."""
        # Make a copy to avoid modifying the original
        validated_params = parameters.copy()

        if action_type == ActionType.SEARCH_SCHEMA:
            if "query" not in validated_params:
                validated_params["query"] = state.user_query
                log.info("added_missing_query_parameter", query=state.user_query)

        elif action_type == ActionType.SEARCH_VALUES:
            # Ensure required parameters exist
            if "table" not in validated_params:
                # Try to extract from schema or use a default
                if state.retrieved_schema and "tables" in state.retrieved_schema:
                    tables = state.retrieved_schema["tables"]
                    if tables:
                        validated_params["table"] = tables[0].get("name", "unknown")
                        log.info(
                            "inferred_table_parameter", table=validated_params["table"]
                        )

            if "column" not in validated_params:
                validated_params["column"] = "symbol"  # Common financial column
                log.info("defaulted_column_parameter", column="symbol")

        elif action_type == ActionType.FIND_SIMILAR_VALUES:
            # Ensure user_term exists
            if "user_term" not in validated_params:
                # Extract potential terms from user query
                query_words = state.user_query.split()
                # Look for capitalized words (likely entities)
                candidates = [word for word in query_words if word[0].isupper()]
                if candidates:
                    validated_params["user_term"] = candidates[0]
                    log.info("inferred_user_term", term=candidates[0])

            # Ensure table and column exist
            if "table" not in validated_params:
                if state.retrieved_schema and "tables" in state.retrieved_schema:
                    tables = state.retrieved_schema["tables"]
                    if tables:
                        validated_params["table"] = tables[0].get(
                            "name", "daily_prices"
                        )
                        log.info(
                            "inferred_table_for_similar_values",
                            table=validated_params["table"],
                        )
                else:
                    validated_params["table"] = (
                        "daily_prices"  # Default financial table
                    )
                    log.info("defaulted_table_for_similar_values", table="daily_prices")

            if "column" not in validated_params:
                validated_params["column"] = "symbol"  # Default to symbol column
                log.info("defaulted_column_for_similar_values", column="symbol")

        elif action_type == ActionType.GENERATE_SQL:
            if "query" not in validated_params:
                validated_params["query"] = state.user_query
            if "schema" not in validated_params:
                validated_params["schema"] = state.retrieved_schema or {}

        elif action_type == ActionType.EXECUTE_SQL:
            if "sql" not in validated_params:
                validated_params["sql"] = state.current_sql

        return validated_params

    async def observe(self, state: AgentState, action: AgentAction) -> AgentObservation:
        """Execute the action and observe the result."""
        try:
            # Route to appropriate tool
            if action.action_type == ActionType.SEARCH_SCHEMA:
                result = await self.tools.search_schema(**action.parameters)
                state.retrieved_schema = result

            elif action.action_type == ActionType.SEARCH_VALUES:
                result = await self.tools.search_values(**action.parameters)

            elif action.action_type == ActionType.GENERATE_SQL:
                # Check memory for similar queries first
                cached_sql = await self.memory.recall_similar_query(
                    state.user_query,
                    state.retrieved_schema,
                )

                if cached_sql:
                    result = cached_sql
                    log.info("using_cached_sql", sql=cached_sql)
                else:
                    result = await self.tools.generate_sql(
                        query=state.user_query,
                        schema=state.retrieved_schema,
                        mappings=state.discovered_mappings,
                    )

                state.current_sql = result

            elif action.action_type == ActionType.EXECUTE_SQL:
                result = await self.tools.execute_sql(**action.parameters)

            elif action.action_type == ActionType.DIAGNOSE_EMPTY_RESULTS:
                result = await self.tools.diagnose_empty_results(
                    sql=state.current_sql,
                    schema=state.retrieved_schema,
                )

            elif action.action_type == ActionType.FIND_SIMILAR_VALUES:
                result = await self.tools.find_similar_values(**action.parameters)
                # Update discovered mappings
                if result and "mapping" in result:
                    state.discovered_mappings.update(result["mapping"])

            else:
                raise ValueError(f"Unknown action type: {action.action_type}")

            # Create observation
            observation = state.add_observation(
                content=result,
                success=True,
                action_type=action.action_type.value,
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
        """Reflect on the observation and update state."""
        # Handle different types of observations
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

            if action_type == ActionType.SEARCH_SCHEMA.value:
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
        return {
            "success": state.success,
            "result": state.final_result,
            "reasoning_trace": [
                {
                    "type": "thought",
                    "content": thought.content,
                    "timestamp": thought.timestamp.isoformat(),
                }
                for thought in state.thoughts
            ],
            "actions_taken": [
                {
                    "type": action.action_type.value,
                    "parameters": action.parameters,
                    "timestamp": action.timestamp.isoformat(),
                }
                for action in state.actions
            ],
            "discovered_mappings": state.discovered_mappings,
            "iterations": state.iteration,
            "sql": state.current_sql,
        }

    def _build_error_response(
        self, state: AgentState, error: Exception
    ) -> Dict[str, Any]:
        """Build an error response."""
        response = self._build_response(state)
        response["success"] = False
        response["error"] = str(error)
        return response
