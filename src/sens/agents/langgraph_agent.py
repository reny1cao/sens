"""LangGraph-based agent implementation for SENS."""

import json
import time
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Dict, List, Optional, TypedDict

import structlog
from langchain_core.messages import BaseMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from sens.agents.reasoning import ReasoningEngine
from sens.agents.tools import AgentTools
from sens.execution.executor import SQLExecutor
from sens.execution.types import QueryResult
from sens.llm.sql_generator import SQLGenerator
from sens.settings import get_settings

log = structlog.get_logger()


class DateTimeJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime objects and other non-serializable types."""

    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        elif hasattr(obj, "__dict__"):
            # For objects with __dict__, convert to dict representation
            return {"type": obj.__class__.__name__, "data": str(obj)}
        # For any other non-serializable object, convert to string
        return str(obj)


def safe_json_dumps(obj, **kwargs):
    """Safely serialize objects to JSON, handling datetime and other non-serializable types."""
    try:
        return json.dumps(obj, cls=DateTimeJSONEncoder, **kwargs)
    except Exception as e:
        # If even the custom encoder fails, return a string representation
        return json.dumps({"error": f"Failed to serialize: {str(e)}", "data": str(obj)})


class AgentState(TypedDict):
    """State for the LangGraph agent following LangGraph patterns."""

    # Core state
    user_query: str
    """The original user query."""

    iteration: int
    """Current iteration count."""

    # Messages following LangGraph pattern
    messages: Annotated[List[BaseMessage], add_messages]
    """Conversation messages with automatic appending."""

    # Agent reasoning and memory
    agent_notes: List[str]
    """Running notes from the agent's discoveries."""

    chosen_action: Optional[str]
    """The action chosen by the reasoning engine."""

    action_parameters: Optional[Dict[str, Any]]
    """Parameters for the chosen action."""

    action_output: Optional[Any]
    """Output from the last action execution."""

    # SQL generation and execution
    generated_sql: Optional[str]
    """Generated SQL query."""

    sql_result: Optional[QueryResult]
    """Results from SQL execution."""

    # Final output
    final_answer: Optional[str]
    """Final answer to provide to the user."""

    # Metadata
    session_id: Optional[str]
    """Session identifier for conversation context."""

    start_time: float
    """Timestamp when processing started."""

    discovered_mappings: Dict[str, str]
    """Value mappings discovered during exploration."""


class LangGraphSENSAgent:
    """
    LangGraph-based SENS agent that wraps existing components.

    This agent follows the patterns from the LangGraph tutorial, using:
    - TypedDict for state management
    - Graph nodes for each major action
    - Conditional edges for routing
    - Integration with existing SENS components
    """

    def __init__(
        self,
        reasoning_engine: Optional[ReasoningEngine] = None,
        agent_tools: Optional[AgentTools] = None,
        sql_generator: Optional[SQLGenerator] = None,
        sql_executor: Optional[SQLExecutor] = None,
        max_iterations: int = 10,
    ):
        """Initialize the LangGraph agent with existing SENS components."""
        self.reasoning_engine = reasoning_engine or ReasoningEngine()
        self.agent_tools = agent_tools or AgentTools()
        self.sql_generator = sql_generator or SQLGenerator()
        self.sql_executor = sql_executor or SQLExecutor()
        self.max_iterations = max_iterations

        # Build the graph
        self.graph = self._build_graph()

        log.info(
            "langgraph_agent_initialized",
            max_iterations=max_iterations,
            has_reasoning_engine=bool(reasoning_engine),
            has_tools=bool(agent_tools),
            has_sql_generator=bool(sql_generator),
            has_executor=bool(sql_executor),
        )

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow following tutorial patterns."""
        workflow = StateGraph(AgentState)

        # Add nodes - each wraps existing SENS functionality
        workflow.add_node("reasoning", self._reasoning_node)
        workflow.add_node("explore_database", self._explore_database_node)
        workflow.add_node("generate_sql", self._generate_sql_node)
        workflow.add_node("execute_sql", self._execute_sql_node)
        workflow.add_node("finalize_answer", self._finalize_answer_node)

        # Set entry point
        workflow.set_entry_point("reasoning")

        # Add conditional edges for routing
        workflow.add_conditional_edges(
            "reasoning",
            self._route_action,
            {
                "explore_database": "explore_database",
                "generate_sql": "generate_sql",
                "execute_sql": "execute_sql",
                "finalize_answer": "finalize_answer",
                END: END,
            },
        )

        # After actions, go back to reasoning (except finalize)
        workflow.add_edge("explore_database", "reasoning")
        workflow.add_edge("generate_sql", "reasoning")
        workflow.add_edge("execute_sql", "reasoning")
        workflow.add_edge("finalize_answer", END)

        return workflow.compile()

    async def _reasoning_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Reasoning node that wraps the existing ReasoningEngine.

        This follows the LangGraph pattern of nodes returning state updates.
        """
        log.info("reasoning_node_start", iteration=state["iteration"])

        # Build context from current state
        full_context = self._build_context_from_state(state)

        # Use existing ReasoningEngine
        decision = await self.reasoning_engine.decide_action(
            user_query=state["user_query"],
            full_context=full_context,
            iteration=state["iteration"],
        )

        # Extract action and parameters
        action_type = decision.get("action_type")
        parameters = decision.get("parameters", {})
        reasoning = decision.get("reasoning", "")
        notes = decision.get("notes", "")

        # Update agent notes if new notes provided
        current_notes = state.get("agent_notes", [])
        if notes and notes.lower() != "none":
            current_notes = current_notes + [notes]

        log.info(
            "reasoning_node_complete",
            iteration=state["iteration"],
            action=action_type,
            reasoning_preview=(
                reasoning[:100] + "..." if len(reasoning) > 100 else reasoning
            ),
        )

        return {
            "chosen_action": action_type,
            "action_parameters": parameters,
            "agent_notes": current_notes,
            "iteration": state["iteration"] + 1,
        }

    async def _explore_database_node(self, state: AgentState) -> Dict[str, Any]:
        """Database exploration node wrapping AgentTools.explore_database."""
        log.info("explore_database_node_start", iteration=state["iteration"])

        parameters = state.get("action_parameters", {})
        query = parameters.get("query")

        if not query:
            error_msg = "No query provided for database exploration"
            log.error("explore_database_missing_query", iteration=state["iteration"])
            return {"action_output": {"success": False, "error": error_msg}}

        # Use existing AgentTools
        result = await self.agent_tools.explore_database(query=query)

        log.info(
            "explore_database_node_complete",
            iteration=state["iteration"],
            success=result.get("success", False),
            query=query,
        )

        return {"action_output": result}

    async def _generate_sql_node(self, state: AgentState) -> Dict[str, Any]:
        """SQL generation node wrapping the existing SQLGenerator."""
        log.info("generate_sql_node_start", iteration=state["iteration"])

        try:
            # Build context for SQL generation
            schema_context = self._extract_schema_context_from_state(state)

            # Use AgentTools to generate SQL (which uses the context appropriately)
            result = await self.agent_tools.generate_sql(
                query=state["user_query"],
                schema_context=schema_context,
                agent_notes="\n".join(state.get("agent_notes", [])),
            )

            generated_sql = None
            if result.get("success") and result.get("sql"):
                generated_sql = result["sql"]

            log.info(
                "generate_sql_node_complete",
                iteration=state["iteration"],
                success=result.get("success", False),
                has_sql=bool(generated_sql),
            )

            return {
                "action_output": result,
                "generated_sql": generated_sql,
            }

        except Exception as e:
            log.error(
                "generate_sql_node_error",
                iteration=state["iteration"],
                error=str(e),
            )
            return {
                "action_output": {
                    "success": False,
                    "error": f"SQL generation failed: {str(e)}",
                }
            }

    async def _execute_sql_node(self, state: AgentState) -> Dict[str, Any]:
        """SQL execution node wrapping the existing SQLExecutor."""
        log.info("execute_sql_node_start", iteration=state["iteration"])

        sql = state.get("generated_sql")
        if not sql:
            error_msg = "No SQL query available for execution"
            log.error("execute_sql_missing_query", iteration=state["iteration"])
            return {"action_output": {"success": False, "error": error_msg}}

        try:
            # Use existing SQLExecutor
            result = self.sql_executor.execute(sql)

            # Convert QueryResult to dict for state
            result_dict = {
                "success": result.error is None,
                "columns": result.columns,
                "rows": result.rows,
                "row_count": result.row_count,
                "error": result.error,
            }

            log.info(
                "execute_sql_node_complete",
                iteration=state["iteration"],
                success=result_dict["success"],
                row_count=result_dict["row_count"],
            )

            return {
                "action_output": result_dict,
                "sql_result": result,
            }

        except Exception as e:
            log.error(
                "execute_sql_node_error",
                iteration=state["iteration"],
                error=str(e),
            )
            return {
                "action_output": {
                    "success": False,
                    "error": f"SQL execution failed: {str(e)}",
                }
            }

    async def _finalize_answer_node(self, state: AgentState) -> Dict[str, Any]:
        """Finalization node that generates the final answer."""
        log.info("finalize_answer_node_start", iteration=state["iteration"])

        # Build final answer based on state
        sql_result = state.get("sql_result")
        action_output = state.get("action_output", {})

        if sql_result and sql_result.error is None and sql_result.row_count > 0:
            # Successful query with results
            final_answer = f"I found {sql_result.row_count} results for your query. The data shows the requested information."
        elif sql_result and sql_result.error is None and sql_result.row_count == 0:
            # Successful query but no results
            final_answer = (
                "Your query was successful, but no data matches the specified criteria."
            )
        elif action_output.get("success") is False:
            # Error occurred
            error = action_output.get("error", "Unknown error occurred")
            final_answer = (
                f"I encountered an issue while processing your request: {error}"
            )
        else:
            # Default case
            final_answer = (
                "I've processed your request. Please check the results above."
            )

        log.info(
            "finalize_answer_node_complete",
            iteration=state["iteration"],
            answer_preview=(
                final_answer[:100] + "..." if len(final_answer) > 100 else final_answer
            ),
        )

        return {"final_answer": final_answer}

    def _route_action(self, state: AgentState) -> str:
        """
        Conditional edge function that routes based on chosen action.

        This follows the LangGraph pattern for conditional routing.
        """
        action = state.get("chosen_action")
        iteration = state.get("iteration", 0)

        # Safety check for max iterations
        if iteration >= self.max_iterations:
            log.warning("max_iterations_reached", iteration=iteration)
            return "finalize_answer"

        # Route based on action
        if action == "EXPLORE_DATABASE":
            return "explore_database"
        elif action == "GENERATE_SQL":
            return "generate_sql"
        elif action == "EXECUTE_SQL":
            return "execute_sql"
        elif action in ["PROVIDE_ANSWER", "CLARIFY_QUERY"]:
            return "finalize_answer"
        else:
            log.warning("unknown_action", action=action, iteration=iteration)
            return "finalize_answer"

    def _build_context_from_state(self, state: AgentState) -> str:
        """Build context string from current state for ReasoningEngine."""
        context_parts = []

        # Add iteration info
        context_parts.append(f"Iteration: {state.get('iteration', 0)}")

        # Add agent notes
        notes = state.get("agent_notes", [])
        if notes:
            context_parts.append("Agent Notes:")
            for i, note in enumerate(notes, 1):
                context_parts.append(f"  {i}. {note}")

        # Add last action output
        action_output = state.get("action_output")
        if action_output:
            context_parts.append(
                f"Last Action Output: {safe_json_dumps(action_output, indent=2)}"
            )

        # Add SQL if generated
        generated_sql = state.get("generated_sql")
        if generated_sql:
            context_parts.append(f"Generated SQL: {generated_sql}")

        # Add SQL results if available
        sql_result = state.get("sql_result")
        if sql_result:
            context_parts.append(f"SQL Results: {sql_result.row_count} rows returned")

        return "\n\n".join(context_parts)

    def _extract_schema_context_from_state(self, state: AgentState) -> str:
        """Extract schema information from exploration results in state."""
        action_output = state.get("action_output", {})

        # Try to extract schema info from exploration results
        if isinstance(action_output, dict) and "result" in action_output:
            return str(action_output["result"])
        elif isinstance(action_output, dict):
            return str(action_output)
        else:
            return "Schema context not yet available. Need to explore database first."

    async def run(
        self,
        user_query: str,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run the agent on a user query.

        Args:
            user_query: The user's natural language query
            session_id: Optional session identifier

        Returns:
            Dictionary with the final result and metadata
        """
        start_time = time.time()

        # Initialize state following LangGraph patterns
        initial_state = AgentState(
            user_query=user_query,
            iteration=0,
            messages=[],  # Will be populated by LangGraph message handling
            agent_notes=[],
            chosen_action=None,
            action_parameters=None,
            action_output=None,
            generated_sql=None,
            sql_result=None,
            final_answer=None,
            session_id=session_id,
            start_time=start_time,
            discovered_mappings={},
        )

        log.info(
            "langgraph_agent_start",
            user_query=user_query,
            session_id=session_id,
        )

        try:
            # Run the graph - this follows LangGraph patterns
            final_state = await self.graph.ainvoke(initial_state)

            # Calculate total time
            total_time_ms = (time.time() - start_time) * 1000

            # Build response
            response = {
                "success": True,
                "final_answer": final_state.get("final_answer"),
                "generated_sql": final_state.get("generated_sql"),
                "sql_result": final_state.get("sql_result"),
                "agent_notes": final_state.get("agent_notes", []),
                "iterations": final_state.get("iteration", 0),
                "total_time_ms": total_time_ms,
                "session_id": session_id,
            }

            log.info(
                "langgraph_agent_complete",
                success=True,
                iterations=final_state.get("iteration", 0),
                total_time_ms=total_time_ms,
                has_sql=bool(final_state.get("generated_sql")),
                has_results=bool(final_state.get("sql_result")),
            )

            return response

        except Exception as e:
            total_time_ms = (time.time() - start_time) * 1000

            log.error(
                "langgraph_agent_error",
                error=str(e),
                user_query=user_query,
                total_time_ms=total_time_ms,
            )

            return {
                "success": False,
                "error": str(e),
                "final_answer": f"I encountered an error processing your request: {str(e)}",
                "total_time_ms": total_time_ms,
                "session_id": session_id,
            }
