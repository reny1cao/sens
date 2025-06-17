"""Event-emitting wrapper for SENSAgent to support real-time updates."""

import asyncio
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import structlog

from sens.agents.base import AgentAction, AgentObservation, AgentThought
from sens.agents.core import SENSAgent
from sens.agents.reflection import ReflectionEngine

log = structlog.get_logger()


class EventEmittingAgent(SENSAgent):
    """Agent that emits events for real-time monitoring."""

    def __init__(self, *args, **kwargs):
        """Initialize the event-emitting agent."""
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

        # Call handlers
        for handler in self.event_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                log.error("event_handler_error", error=str(e), event_type=event_type)

    async def reason(self, state) -> Dict[str, Any]:
        """Override to emit reasoning events."""
        # Emit that we're starting to think
        await self.emit_event(
            "reasoning_start", {"iteration": state.iteration, "query": state.user_query}
        )

        # Call parent method
        reasoning_result = await super().reason(state)

        # Emit the reasoning result
        await self.emit_event(
            "reasoning",
            {
                "iteration": state.iteration,
                "action_type": reasoning_result.get("action_type"),
                "reasoning": reasoning_result.get("reasoning"),
                "notes": reasoning_result.get("notes"),
            },
        )

        return reasoning_result

    async def act(self, state, reasoning_result) -> AgentObservation:
        """Override to emit action events."""
        # Emit the action about to be taken
        await self.emit_event(
            "action",
            {
                "iteration": state.iteration,
                "action_type": reasoning_result.get("action_type"),
                "parameters": reasoning_result.get("parameters"),
                "reasoning": reasoning_result.get("reasoning"),
            },
        )

        # Call parent method
        observation = await super().act(state, reasoning_result)

        return observation

    async def observe(self, state, action) -> AgentObservation:
        """Override to emit observation events."""
        # Emit that we're executing the action
        await self.emit_event(
            "action_start",
            {"iteration": state.iteration, "action_type": action.action_type.value},
        )

        # Call parent method
        observation = await super().observe(state, action)

        # Emit the observation
        await self.emit_event(
            "observation",
            {
                "iteration": state.iteration,
                "success": observation.success,
                "error": observation.error,
                "content_preview": self._preview_content(observation.content),
                "action_type": observation.metadata.get("action_type"),
            },
        )

        return observation

    def _preview_content(self, content: Any) -> Any:
        """Create a preview of observation content for events."""
        if isinstance(content, dict):
            preview = {}
            if "row_count" in content:
                preview["row_count"] = content["row_count"]
            if "columns" in content:
                preview["columns"] = content["columns"]
            if "data" in content and isinstance(content["data"], list):
                preview["sample_rows"] = len(content["data"][:3])
            if "error" in content:
                preview["error"] = content["error"]
            if "success" in content:
                preview["success"] = content["success"]
            return preview
        elif isinstance(content, str):
            return content[:200] + "..." if len(content) > 200 else content
        else:
            return str(content)[:200]

    async def process_query(
        self, user_query: str, conversation_id: str
    ) -> Dict[str, Any]:
        """Override to emit start/complete events."""
        await self.emit_event(
            "query_start",
            {
                "query": user_query,
                "conversation_id": conversation_id,
                "max_iterations": self.max_iterations,
            },
        )

        try:
            result = await super().process_query(user_query, conversation_id)

            await self.emit_event(
                "query_complete",
                {
                    "success": result.get("success", False),
                    "iterations": result.get("iterations", 0),
                    "sql": result.get("sql"),
                    "row_count": (
                        result.get("result", {}).get("row_count", 0)
                        if result.get("result")
                        else 0
                    ),
                },
            )

            return result

        except Exception as e:
            await self.emit_event("query_error", {"error": str(e), "query": user_query})
            raise
