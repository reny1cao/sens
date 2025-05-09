"""Models for chat state management and clarification handling."""

from datetime import UTC, datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from sens.llm.models import Intent


class ClarificationRequest(BaseModel):
    """Represents a request for clarification when intent is ambiguous or incomplete."""

    message: str = Field(
        ...,
        description="User-friendly message explaining what needs clarification",
    )
    reason: str = Field(
        ...,
        description="Technical reason for requesting clarification",
    )
    suggestions: List[str] = Field(
        default_factory=list,
        description="Optional list of suggested clarifications or examples",
    )
    context: Dict = Field(
        default_factory=dict,
        description="Additional context about what was understood so far",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "message": "Could you specify which year you're interested in?",
                "reason": "missing_temporal_filter",
                "suggestions": [
                    "Show orders from 2023",
                    "Show orders from last year",
                ],
                "context": {
                    "understood_tables": ["orders"],
                    "missing_info": ["time_period"],
                },
            }
        }
    }


class ConversationState(BaseModel):
    """Tracks the state of a multi-turn conversation."""

    conversation_id: str = Field(
        ...,
        description="Unique identifier for this conversation",
    )
    history: List[Dict] = Field(
        default_factory=list,
        description="List of interaction records in chronological order",
    )
    last_valid_intent: Optional[Intent] = Field(
        None,
        description="Most recent successfully validated intent",
    )
    pending_clarification: Optional[ClarificationRequest] = Field(
        None,
        description="Active clarification request if one exists",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When this conversation started",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When this conversation was last updated",
    )

    def add_interaction(
        self,
        user_input: str,
        response: Dict,
        intent: Optional[Intent] = None,
        clarification: Optional[ClarificationRequest] = None,
    ) -> None:
        """Add a new interaction to the conversation history.

        Args:
            user_input: The user's question or input
            response: The system's response
            intent: Optional validated intent from this interaction
            clarification: Optional clarification request from this interaction
        """
        interaction = {
            "timestamp": datetime.now(UTC).isoformat(),
            "user_input": user_input,
            "response": response,
        }

        if intent:
            self.last_valid_intent = intent
            interaction["intent"] = intent.model_dump()

        if clarification:
            self.pending_clarification = clarification
            interaction["clarification"] = clarification.model_dump()
        else:
            self.pending_clarification = None

        self.history.append(interaction)
        self.updated_at = datetime.now(UTC)

    def clear_clarification(self) -> None:
        """Clear any pending clarification request."""
        self.pending_clarification = None
        self.updated_at = datetime.now(UTC)

    def get_recent_context(self, limit: int = 5) -> List[Dict]:
        """Get the most recent interactions for context.

        Args:
            limit: Maximum number of recent interactions to return

        Returns:
            List of recent interactions, most recent first
        """
        return list(reversed(self.history[-limit:]))
