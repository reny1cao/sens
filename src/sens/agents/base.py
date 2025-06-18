"""Base classes and types for the SENS agent system."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import structlog

log = structlog.get_logger()


class ActionType(Enum):
    """Types of actions the agent can take."""

    # Schema exploration
    SEARCH_SCHEMA = "search_schema"
    EXPLORE_TABLE = "explore_table"
    FIND_RELATIONSHIPS = "find_relationships"

    # Value discovery
    SEARCH_VALUES = "search_values"
    FIND_SIMILAR_VALUES = "find_similar_values"
    GET_VALUE_DISTRIBUTION = "get_value_distribution"

    # Query operations
    GENERATE_SQL = "generate_sql"
    EXECUTE_SQL = "execute_sql"
    VALIDATE_SQL = "validate_sql"

    # Diagnostics
    DIAGNOSE_EMPTY_RESULTS = "diagnose_empty_results"
    ANALYZE_ERROR = "analyze_error"
    SUGGEST_FIXES = "suggest_fixes"

    # Database exploration
    EXPLORE_DATABASE = "explore_database"

    # Memory operations
    STORE_MAPPING = "store_mapping"
    RECALL_MAPPING = "recall_mapping"
    STORE_PATTERN = "store_pattern"


@dataclass
class AgentThought:
    """Represents the agent's reasoning at a point in time."""

    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        """String representation of thought."""
        return f"Thought: {self.content}"


@dataclass
class AgentAction:
    """Represents an action the agent decides to take."""

    action_type: ActionType
    parameters: Dict[str, Any]
    reasoning: str
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __str__(self) -> str:
        """String representation of action."""
        return f"Action: {self.action_type.value}\nInput: {self.parameters}"


@dataclass
class AgentObservation:
    """Represents the result of an action."""

    content: Any
    success: bool
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        """String representation of observation."""
        if self.success:
            return f"Observation: {self.content}"
        else:
            return f"Observation: Error - {self.error}"


@dataclass
class AgentState:
    """Maintains the current state of the agent's reasoning process."""

    user_query: str
    conversation_id: str
    iteration: int = 0
    max_iterations: int = 5

    # History of thoughts, actions, and observations
    thoughts: List[AgentThought] = field(default_factory=list)
    actions: List[AgentAction] = field(default_factory=list)
    observations: List[AgentObservation] = field(default_factory=list)

    # Agent's running notes about discoveries
    agent_notes: str = ""

    # Current context
    current_sql: Optional[str] = None
    retrieved_schema: Optional[Dict[str, Any]] = None
    discovered_mappings: Dict[str, str] = field(default_factory=dict)
    exploration_results: Dict[str, Any] = field(default_factory=dict)

    # Results
    final_result: Optional[Any] = None
    success: bool = False
    natural_language_answer: Optional[str] = None

    def add_thought(self, content: str, confidence: float = 1.0, **metadata):
        """Add a thought to the reasoning trace."""
        thought = AgentThought(content, confidence=confidence, metadata=metadata)
        self.thoughts.append(thought)
        return thought

    def add_action(
        self, action_type: ActionType, parameters: Dict[str, Any], reasoning: str
    ):
        """Record an action."""
        action = AgentAction(action_type, parameters, reasoning)
        self.actions.append(action)
        return action

    def add_observation(
        self, content: Any, success: bool, error: Optional[str] = None, **metadata
    ):
        """Record an observation."""
        observation = AgentObservation(content, success, error, metadata=metadata)
        self.observations.append(observation)
        return observation

    def get_recent_context(self, n: int = 3) -> str:
        """Get recent thoughts, actions, and observations for context."""
        context_parts = []

        # Interleave thoughts, actions, and observations by timestamp
        all_items = []
        for thought in self.thoughts[-n:]:
            all_items.append((thought.timestamp, str(thought)))
        for action in self.actions[-n:]:
            all_items.append((action.timestamp, str(action)))
        for observation in self.observations[-n:]:
            all_items.append((observation.timestamp, str(observation)))

        # Sort by timestamp
        all_items.sort(key=lambda x: x[0])

        # Build context string
        for _, item_str in all_items[-n * 3 :]:  # Get last n*3 items
            context_parts.append(item_str)

        return "\n".join(context_parts)

    def get_last_action(self) -> Optional[AgentAction]:
        """Get the most recent action."""
        return self.actions[-1] if self.actions else None

    def get_last_observation(self) -> Optional[AgentObservation]:
        """Get the most recent observation."""
        return self.observations[-1] if self.observations else None

    def update_notes(self, new_info: str) -> None:
        """Update agent's notes with new information."""
        if self.agent_notes:
            self.agent_notes += f"\n{new_info}"
        else:
            self.agent_notes = f"Agent Notes:\n{new_info}"

        # Log the update with more detail
        log.info(
            "agent_notes_updated",
            notes_length=len(self.agent_notes),
            new_info=new_info,
            notes_preview=(
                self.agent_notes[-300:]
                if len(self.agent_notes) > 300
                else self.agent_notes
            ),
        )

    @property
    def should_continue(self) -> bool:
        """Check if the agent should continue iterating."""
        return (
            not self.success
            and self.iteration < self.max_iterations
            and self.final_result is None
        )


class BaseAgent(ABC):
    """Abstract base class for agents."""

    @abstractmethod
    async def reason(self, state: AgentState) -> AgentThought:
        """Analyze the current state and decide what to do next."""
        pass

    @abstractmethod
    async def act(self, state: AgentState, thought: AgentThought) -> AgentAction:
        """Choose an action based on the current thought."""
        pass

    @abstractmethod
    async def observe(self, state: AgentState, action: AgentAction) -> AgentObservation:
        """Execute the action and observe the result."""
        pass

    @abstractmethod
    async def reflect(self, state: AgentState, observation: AgentObservation) -> None:
        """Reflect on the observation and update state."""
        pass
