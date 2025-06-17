"""Enhanced reflection system for agent learning."""

from typing import Any, Dict, Optional

import structlog

from sens.agents.base import ActionType, AgentAction, AgentObservation, AgentState

log = structlog.get_logger()


class ReflectionEngine:
    """Engine for creating reflection context from observations."""

    def __init__(self):
        """Initialize the reflection engine."""
        pass

    def create_reflection_context(
        self, state: AgentState, action: AgentAction, observation: AgentObservation
    ) -> str:
        """Create a detailed context for the agent to reflect on.

        This provides the full observation content for the model to analyze,
        rather than trying to extract specific pieces.
        """
        context_parts = []

        # Add the action that was taken
        context_parts.append("=== ACTION TAKEN ===")
        context_parts.append(f"Type: {action.action_type.value}")
        context_parts.append(f"Parameters: {action.parameters}")
        context_parts.append(f"Reasoning: {action.reasoning}")

        # Add the observation result
        context_parts.append("\n=== OBSERVATION RESULT ===")
        context_parts.append(f"Success: {observation.success}")

        if observation.error:
            context_parts.append(f"Error: {observation.error}")

        # Add the full content for reflection
        if observation.content:
            context_parts.append("\n=== OBSERVATION CONTENT ===")
            if isinstance(observation.content, dict):
                # Format dict content nicely
                for key, value in observation.content.items():
                    if key == "data" and isinstance(value, list) and len(value) > 10:
                        context_parts.append(
                            f"{key}: [List with {len(value)} items, showing first 5...]"
                        )
                        for i, item in enumerate(value[:5]):
                            context_parts.append(f"  [{i}]: {item}")
                    elif key == "columns" and isinstance(value, list):
                        context_parts.append(f"{key}: {value}")
                    else:
                        value_str = str(value)
                        if len(value_str) > 200:
                            context_parts.append(f"{key}: {value_str[:200]}...")
                        else:
                            context_parts.append(f"{key}: {value_str}")
            else:
                context_parts.append(str(observation.content))

        # Add current agent notes for context
        context_parts.append("\n=== CURRENT AGENT NOTES ===")
        context_parts.append(
            state.agent_notes if state.agent_notes else "No notes yet."
        )

        # Add discovered tables summary
        if state.exploration_results.get("discovered_tables"):
            context_parts.append("\n=== DISCOVERED TABLES ===")
            tables = state.exploration_results["discovered_tables"]
            context_parts.append(
                f"Found {len(tables)} tables: {', '.join(tables[:10])}"
            )
            if "economic_indicators" in tables:
                context_parts.append(
                    "NOTE: 'economic_indicators' table found - could contain Federal Funds Rate!"
                )
            if "market_data" in tables:
                context_parts.append(
                    "NOTE: 'market_data' table found - could contain market indicators!"
                )

        # Add pattern detection
        patterns = self._detect_patterns(state)
        if patterns:
            context_parts.append("\n=== PATTERNS DETECTED ===")
            context_parts.append(patterns)

        return "\n".join(context_parts)

    def _detect_patterns(self, state: AgentState) -> Optional[str]:
        """Detect problematic patterns in agent behavior."""
        if len(state.actions) < 3:
            return None

        # Pattern 1: Exploring same query repeatedly
        recent_queries = []
        for action in state.actions[-5:]:
            if action.action_type == ActionType.EXPLORE_DATABASE:
                query = action.parameters.get("query", "").lower()
                recent_queries.append(query)

        # Check for exact duplicates
        if len(recent_queries) >= 3:
            for i in range(len(recent_queries) - 2):
                if recent_queries[i] == recent_queries[i + 1] == recent_queries[i + 2]:
                    return f"Repeated same exploration query 3 times: '{recent_queries[i][:100]}...'"

        # Pattern 2: No progress after many iterations
        if state.iteration > 5 and not state.current_sql:
            return f"No SQL generated after {state.iteration} iterations"

        # Pattern 3: Multiple failed executions
        failed_executions = sum(
            1
            for obs in state.observations[-3:]
            if hasattr(obs, "metadata")
            and obs.metadata.get("action_type") == "EXECUTE_SQL"
            and not obs.success
        )

        if failed_executions >= 2:
            return "Multiple SQL execution failures in recent attempts"

        return None
