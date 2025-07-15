"""
Simple File-Based Memory System for SENS Agent

Replaces KuzuDB with a simple JSON-based memory system that integrates
with the LLM note-taking system for database knowledge management.
"""

import json
import time
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
from pydantic import BaseModel, Field

log = structlog.get_logger()


class MemoryType(str, Enum):
    """Types of memories the agent can store"""

    CONCEPT = "concept"
    PATTERN = "pattern"
    MAPPING = "mapping"
    RULE = "rule"
    CALCULATION = "calculation"
    ERROR_FIX = "error_fix"
    RELATIONSHIP = "relationship"


class Memory(BaseModel):
    """A single memory stored by the agent"""

    id: str
    memory_type: MemoryType
    name: str
    content: Dict[str, Any]
    metadata: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    usage_count: int = Field(default=0, ge=0)
    success_count: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_used: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        """Calculate success rate for this memory"""
        if self.usage_count == 0:
            return 1.0
        return self.success_count / self.usage_count

    def mark_used(self, success: bool = True) -> None:
        """Mark this memory as used"""
        self.usage_count += 1
        if success:
            self.success_count += 1
        self.last_used = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def update_confidence(self, new_confidence: float) -> None:
        """Update confidence based on new evidence"""
        self.confidence = max(0.0, min(1.0, new_confidence))
        self.updated_at = datetime.utcnow()


class SimpleAgentMemory:
    """
    Simple file-based memory system for the SENS agent.

    Stores memories in JSON files and provides basic search capabilities.
    Integrates with the LLM note-taking system for enhanced knowledge management.
    """

    def __init__(self, db_path: str = "agent_memory.json"):
        """Initialize the simple memory system"""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing memories
        self.memories: List[Memory] = []
        self._load_memories()

        # Performance tracking
        self.stats = {
            "memories_stored": len(self.memories),
            "queries_executed": 0,
            "avg_query_time": 0.0,
        }

        log.info(
            "simple_memory_initialized",
            db_path=str(self.db_path),
            memory_count=len(self.memories),
        )

    def _load_memories(self) -> None:
        """Load memories from JSON file"""
        if self.db_path.exists():
            try:
                with open(self.db_path, "r") as f:
                    data = json.load(f)
                    for memory_data in data.get("memories", []):
                        # Convert datetime strings back to datetime objects
                        memory_data["created_at"] = datetime.fromisoformat(
                            memory_data["created_at"]
                        )
                        memory_data["updated_at"] = datetime.fromisoformat(
                            memory_data["updated_at"]
                        )
                        if memory_data.get("last_used"):
                            memory_data["last_used"] = datetime.fromisoformat(
                                memory_data["last_used"]
                            )

                        memory = Memory(**memory_data)
                        self.memories.append(memory)

                log.info("memories_loaded", count=len(self.memories))
            except Exception as e:
                log.error("memory_load_failed", error=str(e))
                self.memories = []

    def _save_memories(self) -> None:
        """Save memories to JSON file"""
        try:
            data = {
                "memories": [],
                "metadata": {
                    "last_updated": datetime.utcnow().isoformat(),
                    "total_memories": len(self.memories),
                },
            }

            for memory in self.memories:
                memory_dict = memory.model_dump()
                # Convert datetime objects to ISO strings
                memory_dict["created_at"] = memory.created_at.isoformat()
                memory_dict["updated_at"] = memory.updated_at.isoformat()
                if memory.last_used:
                    memory_dict["last_used"] = memory.last_used.isoformat()
                else:
                    memory_dict["last_used"] = None

                data["memories"].append(memory_dict)

            with open(self.db_path, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            log.error("memory_save_failed", error=str(e))

    async def remember(
        self,
        memory_type: MemoryType,
        name: str,
        content: Dict[str, Any],
        context: Dict[str, Any] = None,
    ) -> str:
        """
        Store a new memory.

        Args:
            memory_type: Type of memory to store
            name: Name/identifier for the memory
            content: The actual content to remember
            context: Additional context about this memory

        Returns:
            Memory ID that was created
        """
        start_time = time.time()

        memory_id = f"{memory_type.value}_{uuid.uuid4().hex[:8]}"
        now = datetime.utcnow()

        # Create memory object
        memory = Memory(
            id=memory_id,
            memory_type=memory_type,
            name=name,
            content=content,
            metadata=context or {},
            created_at=now,
            updated_at=now,
        )

        # Store in memory list
        self.memories.append(memory)
        self._save_memories()

        self.stats["memories_stored"] = len(self.memories)

        query_time = time.time() - start_time
        self.stats["queries_executed"] += 1
        self.stats["avg_query_time"] = (
            self.stats["avg_query_time"] * (self.stats["queries_executed"] - 1)
            + query_time
        ) / self.stats["queries_executed"]

        log.info(
            "memory_stored",
            memory_id=memory_id,
            memory_type=memory_type.value,
            name=name,
            query_time_ms=query_time * 1000,
        )

        return memory_id

    async def recall(
        self,
        query: str,
        memory_types: List[MemoryType] = None,
        context: Dict[str, Any] = None,
        limit: int = 10,
    ) -> List[Memory]:
        """
        Recall memories matching the query.

        Args:
            query: Natural language query or pattern to match
            memory_types: Filter by specific memory types
            context: Context to help with retrieval
            limit: Maximum number of memories to return

        Returns:
            List of matching memories, ranked by relevance
        """
        start_time = time.time()

        # Filter memories
        filtered_memories = []
        query_lower = query.lower()

        for memory in self.memories:
            # Filter by memory type if specified
            if memory_types and memory.memory_type not in memory_types:
                continue

            # Simple text matching
            if query_lower:
                name_match = query_lower in memory.name.lower()
                content_match = any(
                    query_lower in str(v).lower() for v in memory.content.values()
                )
                metadata_match = any(
                    query_lower in str(v).lower() for v in memory.metadata.values()
                )

                if not (name_match or content_match or metadata_match):
                    continue

            # Context filtering
            if context:
                database = context.get("database")
                if database and database not in str(memory.metadata):
                    continue

            filtered_memories.append(memory)

        # Sort by confidence and usage
        filtered_memories.sort(
            key=lambda m: (m.confidence, m.usage_count, m.updated_at), reverse=True
        )

        # Apply limit
        result_memories = filtered_memories[:limit]

        query_time = time.time() - start_time
        self.stats["queries_executed"] += 1
        self.stats["avg_query_time"] = (
            self.stats["avg_query_time"] * (self.stats["queries_executed"] - 1)
            + query_time
        ) / self.stats["queries_executed"]

        log.info(
            "memories_recalled",
            query=query[:50] + "..." if len(query) > 50 else query,
            count=len(result_memories),
            query_time_ms=query_time * 1000,
        )

        return result_memories

    async def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory statistics"""
        return {
            "total_memories": len(self.memories),
            "memories_by_type": {
                memory_type.value: len(
                    [m for m in self.memories if m.memory_type == memory_type]
                )
                for memory_type in MemoryType
            },
            "avg_confidence": (
                sum(m.confidence for m in self.memories) / len(self.memories)
                if self.memories
                else 0
            ),
            "total_usage": sum(m.usage_count for m in self.memories),
            "performance_stats": self.stats,
        }

    async def clear_memories(self) -> None:
        """Clear all memories"""
        self.memories = []
        self._save_memories()
        self.stats["memories_stored"] = 0
        log.info("memories_cleared")

    def close(self) -> None:
        """Close the memory system"""
        self._save_memories()
        log.info("simple_memory_closed")
