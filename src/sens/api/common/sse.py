"""Server-Sent Events utilities for real-time agent updates."""

import asyncio
import json
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional


class SSEMessage:
    """Represents a Server-Sent Event message."""

    def __init__(
        self,
        data: Any,
        event: Optional[str] = None,
        id: Optional[str] = None,
        retry: Optional[int] = None,
    ):
        self.data = data
        self.event = event
        self.id = id
        self.retry = retry

    def format(self) -> str:
        """Format the message for SSE protocol."""
        lines = []

        if self.id:
            lines.append(f"id: {self.id}")

        if self.event:
            lines.append(f"event: {self.event}")

        if self.retry:
            lines.append(f"retry: {self.retry}")

        # Format data as JSON
        if isinstance(self.data, str):
            lines.append(f"data: {self.data}")
        else:
            lines.append(f"data: {json.dumps(self.data)}")

        # SSE requires double newline at the end
        return "\n".join(lines) + "\n\n"


class AgentEventType:
    """Agent event types for SSE."""

    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"
    COMPLETE = "complete"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


def create_agent_event(
    event_type: str,
    iteration: int,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
    event_id: Optional[str] = None,
) -> SSEMessage:
    """Create a standardized agent event."""
    data = {
        "type": event_type,
        "timestamp": datetime.utcnow().isoformat(),
        "iteration": iteration,
        "content": content,
        "metadata": metadata or {},
    }

    return SSEMessage(data=data, event=event_type, id=event_id)


async def heartbeat_generator(interval: int = 30) -> AsyncGenerator[SSEMessage, None]:
    """Generate heartbeat messages to keep connection alive."""
    while True:
        await asyncio.sleep(interval)
        yield SSEMessage(
            data={"type": "heartbeat", "timestamp": datetime.utcnow().isoformat()},
            event=AgentEventType.HEARTBEAT,
        )
