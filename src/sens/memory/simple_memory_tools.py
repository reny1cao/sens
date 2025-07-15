"""
Simple Memory Tools for SENS Agent

Provides high-level memory operations that work with the simple file-based
memory system and integrate with the LLM note-taking system.
"""

from typing import Any, Dict, List, Optional

import structlog
from pydantic import BaseModel

from .simple_memory import MemoryType, SimpleAgentMemory

log = structlog.get_logger()


class MemoryResult(BaseModel):
    """Result from a memory operation"""

    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None
    execution_time_ms: Optional[float] = None


class SimpleAgentMemoryTools:
    """
    High-level memory operations for the SENS agent.

    Provides convenient methods for storing and retrieving different types
    of knowledge, working with the simple file-based memory system.
    """

    def __init__(self, memory: SimpleAgentMemory):
        """Initialize memory tools with a memory instance"""
        self.memory = memory
        log.info("simple_memory_tools_initialized")

    async def remember_concept(
        self,
        name: str,
        description: str,
        business_terms: List[str],
        database_mapping: Dict[str, Any],
        context: Dict[str, Any] = None,
    ) -> MemoryResult:
        """Remember a business concept or entity"""
        try:
            content = {
                "description": description,
                "business_terms": business_terms,
                "database_mapping": database_mapping,
            }

            memory_id = await self.memory.remember(
                memory_type=MemoryType.CONCEPT,
                name=name,
                content=content,
                context=context or {},
            )

            return MemoryResult(
                success=True, data={"memory_id": memory_id, "name": name}
            )

        except Exception as e:
            log.error("remember_concept_failed", error=str(e), name=name)
            return MemoryResult(success=False, data={}, error=str(e))

    async def remember_pattern(
        self,
        name: str,
        trigger_phrase: str,
        sql_template: str,
        tables_used: List[str],
        success_context: Dict[str, Any],
        context: Dict[str, Any] = None,
    ) -> MemoryResult:
        """Remember a successful SQL pattern"""
        try:
            content = {
                "trigger_phrase": trigger_phrase,
                "sql_template": sql_template,
                "tables_used": tables_used,
                "success_context": success_context,
            }

            memory_id = await self.memory.remember(
                memory_type=MemoryType.PATTERN,
                name=name,
                content=content,
                context=context or {},
            )

            return MemoryResult(
                success=True, data={"memory_id": memory_id, "name": name}
            )

        except Exception as e:
            log.error("remember_pattern_failed", error=str(e), name=name)
            return MemoryResult(success=False, data={}, error=str(e))

    async def remember_mapping(
        self,
        name: str,
        user_term: str,
        database_value: str,
        table_column: str,
        confidence: float = 0.9,
        context: Dict[str, Any] = None,
    ) -> MemoryResult:
        """Remember a value mapping"""
        try:
            content = {
                "user_term": user_term,
                "database_value": database_value,
                "table_column": table_column,
                "confidence": confidence,
            }

            memory_id = await self.memory.remember(
                memory_type=MemoryType.MAPPING,
                name=name,
                content=content,
                context=context or {},
            )

            return MemoryResult(
                success=True, data={"memory_id": memory_id, "name": name}
            )

        except Exception as e:
            log.error("remember_mapping_failed", error=str(e), name=name)
            return MemoryResult(success=False, data={}, error=str(e))

    async def remember_error_fix(
        self,
        name: str,
        error_pattern: str,
        solution: str,
        root_cause: str,
        context: Dict[str, Any] = None,
    ) -> MemoryResult:
        """Remember how to fix a specific error pattern"""
        try:
            content = {
                "error_pattern": error_pattern,
                "solution": solution,
                "root_cause": root_cause,
            }

            memory_id = await self.memory.remember(
                memory_type=MemoryType.ERROR_FIX,
                name=name,
                content=content,
                context=context or {},
            )

            return MemoryResult(
                success=True, data={"memory_id": memory_id, "name": name}
            )

        except Exception as e:
            log.error("remember_error_fix_failed", error=str(e), name=name)
            return MemoryResult(success=False, data={}, error=str(e))

    async def recall_knowledge(
        self,
        query: str,
        memory_types: List[str] = None,
        context: Dict[str, Any] = None,
        limit: int = 10,
    ) -> MemoryResult:
        """Recall relevant knowledge for a query"""
        try:
            # Convert string memory types to enum
            enum_types = None
            if memory_types:
                enum_types = [MemoryType(mt) for mt in memory_types]

            memories = await self.memory.recall(
                query=query,
                memory_types=enum_types,
                context=context,
                limit=limit,
            )

            # Convert memories to serializable format
            memory_data = []
            for memory in memories:
                memory_data.append(
                    {
                        "id": memory.id,
                        "type": memory.memory_type.value,
                        "name": memory.name,
                        "content": memory.content,
                        "confidence": memory.confidence,
                        "usage_count": memory.usage_count,
                        "success_rate": memory.success_rate,
                        "created_at": memory.created_at.isoformat(),
                        "last_used": (
                            memory.last_used.isoformat() if memory.last_used else None
                        ),
                    }
                )

            return MemoryResult(
                success=True, data={"memories": memory_data, "count": len(memory_data)}
            )

        except Exception as e:
            log.error("recall_knowledge_failed", error=str(e), query=query)
            return MemoryResult(success=False, data={}, error=str(e))

    async def get_memory_stats(self) -> MemoryResult:
        """Get memory system statistics"""
        try:
            stats = await self.memory.get_memory_stats()

            return MemoryResult(success=True, data=stats)

        except Exception as e:
            log.error("get_memory_stats_failed", error=str(e))
            return MemoryResult(success=False, data={}, error=str(e))

    async def clear_memories(self) -> MemoryResult:
        """Clear all memories"""
        try:
            await self.memory.clear_memories()

            return MemoryResult(success=True, data={"message": "All memories cleared"})

        except Exception as e:
            log.error("clear_memories_failed", error=str(e))
            return MemoryResult(success=False, data={}, error=str(e))

    async def consolidate_memories(self) -> MemoryResult:
        """Consolidate similar memories (placeholder for now)"""
        # This could be enhanced with LLM-based consolidation
        return MemoryResult(
            success=True, data={"message": "Memory consolidation not implemented yet"}
        )

    async def get_memory_insights(self, query: str) -> MemoryResult:
        """Get insights about memories related to a query"""
        try:
            # Get all relevant memories
            all_memories = await self.memory.recall(query=query, limit=50)

            if not all_memories:
                return MemoryResult(
                    success=True,
                    data={"insights": [], "summary": "No relevant memories found"},
                )

            # Generate insights
            insights = []

            # Group by type
            by_type = {}
            for memory in all_memories:
                memory_type = memory.memory_type.value
                if memory_type not in by_type:
                    by_type[memory_type] = []
                by_type[memory_type].append(memory)

            for memory_type, memories in by_type.items():
                insights.append(f"Found {len(memories)} {memory_type} memories")

                # Get highest confidence memory
                best_memory = max(memories, key=lambda m: m.confidence)
                insights.append(
                    f"Best {memory_type}: {best_memory.name} (confidence: {best_memory.confidence:.2f})"
                )

            summary = f"Found {len(all_memories)} relevant memories across {len(by_type)} types"

            return MemoryResult(
                success=True, data={"insights": insights, "summary": summary}
            )

        except Exception as e:
            log.error("get_memory_insights_failed", error=str(e))
            return MemoryResult(success=False, data={}, error=str(e))
