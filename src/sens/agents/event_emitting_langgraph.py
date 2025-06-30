"""Event-emitting wrapper for LangGraph agent to support real-time updates."""

import asyncio
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import structlog

from sens.agents.langgraph_agent import LangGraphSENSAgent

log = structlog.get_logger()


class EventEmittingLangGraphAgent(LangGraphSENSAgent):
    """LangGraph agent that emits events for real-time monitoring."""

    def __init__(self, *args, **kwargs):
        """Initialize the event-emitting LangGraph agent."""
        super().__init__(*args, **kwargs)
        self.event_handlers: List[Callable] = []
        self.event_queue: asyncio.Queue = asyncio.Queue()

    def add_event_handler(self, handler: Callable) -> None:
        """Add an event handler for agent events."""
        self.event_handlers.append(handler)

    async def emit_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Emit an event to all registered handlers."""
        event = {
            "type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data,
        }

        # Put event in queue for async processing
        await self.event_queue.put(event)

        # Call handlers immediately
        for handler in self.event_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                log.error("event_handler_error", error=str(e), event_type=event_type)

    async def _reasoning_node(self, state) -> Dict[str, Any]:
        """Override to emit reasoning events."""
        iteration = state.get("iteration", 0)

        # Emit that we're starting to think
        await self.emit_event(
            "reasoning_start",
            {"iteration": iteration, "query": state.get("user_query")},
        )

        # Call parent method
        result = await super()._reasoning_node(state)

        # Emit the reasoning result
        action = result.get("chosen_action", "unknown")
        await self.emit_event(
            "reasoning",
            {
                "iteration": iteration,
                "action": action,
                "content": f"🤔 Decided to: {action}",
            },
        )

        return result

    async def _explore_database_node(self, state) -> Dict[str, Any]:
        """Override to emit exploration events."""
        iteration = state.get("iteration", 0)
        query_param = state.get("action_parameters", {}).get("query", "")

        # Emit exploration start
        await self.emit_event(
            "exploration_start",
            {
                "iteration": iteration,
                "content": f"🔍 Exploring database: {query_param[:60]}...",
                "query": query_param,
            },
        )

        # Call parent method
        result = await super()._explore_database_node(state)

        # Emit exploration result
        success = result.get("action_output", {}).get("success", False)
        status = "✅ Success" if success else "❌ Failed"

        await self.emit_event(
            "exploration",
            {
                "iteration": iteration,
                "success": success,
                "status": status,
                "content": f"Database exploration: {status}",
            },
        )

        return result

    async def _generate_sql_node(self, state) -> Dict[str, Any]:
        """Override to emit SQL generation events."""
        iteration = state.get("iteration", 0)

        # Emit SQL generation start
        await self.emit_event(
            "sql_generation_start",
            {
                "iteration": iteration,
                "content": "⚡ Generating SQL query...",
            },
        )

        try:
            # Extract exploration results from previous actions
            exploration_results = self._extract_exploration_results_from_state(state)

            # Extract discovered mappings
            mappings = state.get("discovered_mappings", {})

            # Get agent notes
            agent_notes = "\n".join(state.get("agent_notes", []))

            # Use AgentTools to generate SQL with correct parameters
            generated_sql = await self.agent_tools.generate_sql(
                query=state["user_query"],
                exploration_results=exploration_results,
                mappings=mappings,
                agent_notes=agent_notes,
            )

            # Create success result
            result = {
                "success": True,
                "sql": generated_sql,
            }

            # Emit SQL if generated
            if generated_sql:
                await self.emit_event(
                    "sql_generated",
                    {
                        "iteration": iteration,
                        "sql": generated_sql,
                        "content": "SQL query generated successfully",
                    },
                )

            return {
                "action_output": result,
                "generated_sql": generated_sql,
            }

        except Exception as e:
            log.error(
                "generate_sql_node_error",
                iteration=iteration,
                error=str(e),
            )
            return {
                "action_output": {
                    "success": False,
                    "error": f"SQL generation failed: {str(e)}",
                }
            }

    def _extract_exploration_results_from_state(self, state) -> Dict[str, Any]:
        """Extract and aggregate exploration results from all previous database exploration actions."""
        exploration_results = {}

        # Look for exploration outputs in the state
        action_output = state.get("action_output", {})

        # If the last action was database exploration, use that directly
        if isinstance(action_output, dict) and action_output.get("success"):
            if "columns" in action_output and "data" in action_output:
                # This looks like database exploration results
                exploration_results["last_exploration"] = action_output

                # Try to categorize the data
                columns = action_output.get("columns", [])
                data = action_output.get("data", [])

                # Detect if this is table listing
                if len(columns) == 1 and "table" in columns[0].lower():
                    table_names = [row[0] for row in data if row]
                    exploration_results["discovered_tables"] = table_names

                # Detect if this is column information
                elif "column_name" in columns:
                    exploration_results["table_schemas"] = {"discovered_table": columns}

                # Detect if this is sample data from a specific table
                elif len(columns) > 1:
                    exploration_results["sample_data"] = {"last_sampled_table": data}

        # Add any insights from the exploration
        if isinstance(action_output, dict) and "insights" in action_output:
            exploration_results["insights"] = action_output["insights"]

        # Provide fallback structure if no exploration results
        if not exploration_results:
            exploration_results = {
                "discovered_tables": [],
                "table_schemas": {},
                "sample_data": {},
                "insights": "No database exploration completed yet.",
            }

        return exploration_results

    async def _execute_sql_node(self, state) -> Dict[str, Any]:
        """Override to emit SQL execution events."""
        iteration = state.get("iteration", 0)

        # Emit execution start
        await self.emit_event(
            "execution_start",
            {
                "iteration": iteration,
                "content": "🚀 Executing SQL query...",
            },
        )

        # Call parent method
        result = await super()._execute_sql_node(state)

        # Emit execution result
        success = result.get("action_output", {}).get("success", False)
        row_count = result.get("action_output", {}).get("row_count", 0)

        if success:
            await self.emit_event(
                "execution",
                {
                    "iteration": iteration,
                    "success": True,
                    "row_count": row_count,
                    "content": f"✅ Found {row_count} results",
                },
            )
        else:
            error = result.get("action_output", {}).get("error", "Unknown error")
            await self.emit_event(
                "execution",
                {
                    "iteration": iteration,
                    "success": False,
                    "error": error,
                    "content": f"❌ Error: {error}",
                },
            )

        return result

    async def _finalize_answer_node(self, state) -> Dict[str, Any]:
        """Override to emit finalization events."""
        iteration = state.get("iteration", 0)

        # Emit finalization start
        await self.emit_event(
            "finalization_start",
            {
                "iteration": iteration,
                "content": "📝 Finalizing response...",
            },
        )

        # Call parent method
        result = await super()._finalize_answer_node(state)

        # Emit final answer
        final_answer = result.get("final_answer", "")
        await self.emit_event(
            "answer_generated",
            {
                "iteration": iteration,
                "answer": final_answer,
                "content": "Final answer generated",
            },
        )

        return result

    async def run(
        self, user_query: str, session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Override to emit start/complete events."""
        await self.emit_event(
            "query_start",
            {
                "query": user_query,
                "session_id": session_id,
                "max_iterations": self.max_iterations,
                "content": "Starting LangGraph agent processing...",
            },
        )

        try:
            result = await super().run(user_query, session_id)

            await self.emit_event(
                "query_complete",
                {
                    "success": result.get("success", False),
                    "iterations": result.get("iterations", 0),
                    "sql": result.get("generated_sql"),
                    "has_results": bool(result.get("sql_result")),
                    "answer": result.get("final_answer"),
                    "content": "LangGraph agent processing complete",
                },
            )

            return result

        except Exception as e:
            await self.emit_event(
                "query_error",
                {"error": str(e), "query": user_query, "content": f"Error: {str(e)}"},
            )
            raise
