"""
SENS Agent Memory System

Simple file-based memory system for learning and remembering patterns.
Integrates with LLM note-taking system for enhanced knowledge management.
"""

from .simple_memory import Memory, MemoryType, SimpleAgentMemory
from .simple_memory_tools import SimpleAgentMemoryTools

# Aliases for backward compatibility
AgentMemory = SimpleAgentMemory
AgentMemoryTools = SimpleAgentMemoryTools

__all__ = [
    "AgentMemory",
    "Memory",
    "MemoryType",
    "AgentMemoryTools",
    "SimpleAgentMemory",
    "SimpleAgentMemoryTools",
]
