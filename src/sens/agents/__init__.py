"""SENS Agent System - Intelligent query processing with self-correction and learning."""

from .base import AgentAction, AgentObservation, AgentState, AgentThought
from .tools import AgentTools
from .unified import UnifiedSENSAgent

# Backwards compatibility alias
SENSAgent = UnifiedSENSAgent

__all__ = [
    "AgentState",
    "AgentAction",
    "AgentObservation",
    "AgentThought",
    "SENSAgent",
    "UnifiedSENSAgent",
    "AgentTools",
]
