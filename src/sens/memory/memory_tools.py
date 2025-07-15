"""
Agent Memory Tools

Tools that the agent can use to manage its own memory and knowledge.
These tools are designed to be used by the agent during query processing.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import structlog
from pydantic import BaseModel, Field

from .agent_memory import AgentMemory, Memory, MemoryType

log = structlog.get_logger()


class MemoryToolResult(BaseModel):
    """Result from a memory tool operation"""

    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    message: Optional[str] = None


class AgentMemoryTools:
    """
    Memory tools for the agent to use during query processing.

    These tools allow the agent to:
    - Remember useful patterns and concepts
    - Recall relevant knowledge
    - Reflect on memory effectiveness
    - Connect related memories
    - Forget outdated information
    """

    def __init__(self, memory: AgentMemory):
        self.memory = memory
        log.info("memory_tools_initialized")

    async def remember_concept(
        self,
        name: str,
        description: str,
        business_terms: List[str],
        database_mapping: Dict[str, Any],
        context: Dict[str, Any] = None,
    ) -> MemoryToolResult:
        """
        Remember a business concept and how it maps to database structures.

        Args:
            name: Name of the concept (e.g., "annual_revenue")
            description: Human-readable description
            business_terms: Alternative terms users might use
            database_mapping: How this concept maps to database tables/columns
            context: Additional context (database, domain, etc.)

        Returns:
            Result with memory ID if successful
        """
        try:
            content = {
                "description": description,
                "business_terms": business_terms,
                "database_mapping": database_mapping,
                "examples": context.get("examples", []),
            }

            memory_id = await self.memory.remember(
                memory_type=MemoryType.CONCEPT,
                name=name,
                content=content,
                context=context or {},
            )

            return MemoryToolResult(
                success=True,
                data={"memory_id": memory_id},
                message=f"Remembered concept '{name}' with ID {memory_id}",
            )

        except Exception as e:
            log.error("remember_concept_failed", name=name, error=str(e))
            return MemoryToolResult(
                success=False,
                error=str(e),
                message=f"Failed to remember concept '{name}'",
            )

    async def remember_pattern(
        self,
        name: str,
        trigger_phrase: str,
        sql_template: str,
        tables_used: List[str],
        success_context: Dict[str, Any],
        context: Dict[str, Any] = None,
    ) -> MemoryToolResult:
        """
        Remember a successful SQL pattern that worked for a specific query type.

        Args:
            name: Name of the pattern (e.g., "monthly_revenue_calculation")
            trigger_phrase: What user said that triggered this pattern
            sql_template: The SQL template that worked
            tables_used: Tables involved in this pattern
            success_context: Context where this pattern succeeded
            context: Additional context

        Returns:
            Result with memory ID if successful
        """
        try:
            content = {
                "trigger_phrase": trigger_phrase,
                "sql_template": sql_template,
                "tables_used": tables_used,
                "success_context": success_context,
                "parameters": context.get("parameters", {}),
                "notes": context.get("notes", ""),
            }

            memory_id = await self.memory.remember(
                memory_type=MemoryType.PATTERN,
                name=name,
                content=content,
                context=context or {},
            )

            return MemoryToolResult(
                success=True,
                data={"memory_id": memory_id},
                message=f"Remembered pattern '{name}' with ID {memory_id}",
            )

        except Exception as e:
            log.error("remember_pattern_failed", name=name, error=str(e))
            return MemoryToolResult(
                success=False,
                error=str(e),
                message=f"Failed to remember pattern '{name}'",
            )

    async def remember_mapping(
        self,
        name: str,
        user_term: str,
        database_value: str,
        mapping_type: str,
        context: Dict[str, Any] = None,
    ) -> MemoryToolResult:
        """
        Remember a mapping between user terms and database values.

        Args:
            name: Name of the mapping (e.g., "tech_companies_sector")
            user_term: What the user said (e.g., "tech companies")
            database_value: Database equivalent (e.g., "sector='Technology'")
            mapping_type: Type of mapping (e.g., "categorical", "exact_match")
            context: Additional context

        Returns:
            Result with memory ID if successful
        """
        try:
            content = {
                "user_term": user_term,
                "database_value": database_value,
                "mapping_type": mapping_type,
                "confidence": context.get("confidence", 1.0),
                "examples": context.get("examples", []),
            }

            memory_id = await self.memory.remember(
                memory_type=MemoryType.MAPPING,
                name=name,
                content=content,
                context=context or {},
            )

            return MemoryToolResult(
                success=True,
                data={"memory_id": memory_id},
                message=f"Remembered mapping '{name}' with ID {memory_id}",
            )

        except Exception as e:
            log.error("remember_mapping_failed", name=name, error=str(e))
            return MemoryToolResult(
                success=False,
                error=str(e),
                message=f"Failed to remember mapping '{name}'",
            )

    async def remember_error_fix(
        self,
        name: str,
        error_pattern: str,
        solution: str,
        root_cause: str,
        context: Dict[str, Any] = None,
    ) -> MemoryToolResult:
        """
        Remember how to fix a specific error pattern.

        Args:
            name: Name of the error fix (e.g., "missing_column_fix")
            error_pattern: Pattern that identifies the error
            solution: How to fix the error
            root_cause: Why the error occurred
            context: Additional context

        Returns:
            Result with memory ID if successful
        """
        try:
            content = {
                "error_pattern": error_pattern,
                "solution": solution,
                "root_cause": root_cause,
                "prevention": context.get("prevention", ""),
                "examples": context.get("examples", []),
            }

            memory_id = await self.memory.remember(
                memory_type=MemoryType.ERROR_FIX,
                name=name,
                content=content,
                context=context or {},
            )

            return MemoryToolResult(
                success=True,
                data={"memory_id": memory_id},
                message=f"Remembered error fix '{name}' with ID {memory_id}",
            )

        except Exception as e:
            log.error("remember_error_fix_failed", name=name, error=str(e))
            return MemoryToolResult(
                success=False,
                error=str(e),
                message=f"Failed to remember error fix '{name}'",
            )

    async def recall_knowledge(
        self,
        query: str,
        memory_types: List[str] = None,
        context: Dict[str, Any] = None,
        limit: int = 5,
    ) -> MemoryToolResult:
        """
        Recall relevant knowledge from memory.

        Args:
            query: What to search for
            memory_types: Types of memories to search (optional)
            context: Context to help with search
            limit: Maximum number of results

        Returns:
            Result with list of relevant memories
        """
        try:
            # Convert string types to MemoryType enums
            type_filters = None
            if memory_types:
                type_filters = [
                    MemoryType(mt)
                    for mt in memory_types
                    if mt in [t.value for t in MemoryType]
                ]

            memories = await self.memory.recall(
                query=query,
                memory_types=type_filters,
                context=context or {},
                limit=limit,
            )

            # Convert memories to serializable format
            memory_data = []
            for mem in memories:
                memory_data.append(
                    {
                        "id": mem.id,
                        "type": mem.memory_type.value,
                        "name": mem.name,
                        "content": mem.content,
                        "confidence": mem.confidence,
                        "success_rate": mem.success_rate,
                        "usage_count": mem.usage_count,
                        "created_at": mem.created_at.isoformat(),
                        "last_used": (
                            mem.last_used.isoformat() if mem.last_used else None
                        ),
                    }
                )

            return MemoryToolResult(
                success=True,
                data={"memories": memory_data, "count": len(memory_data)},
                message=f"Found {len(memory_data)} relevant memories",
            )

        except Exception as e:
            log.error("recall_knowledge_failed", query=query, error=str(e))
            return MemoryToolResult(
                success=False,
                error=str(e),
                message=f"Failed to recall knowledge for query '{query}'",
            )

    async def connect_memories(
        self,
        from_memory_id: str,
        to_memory_id: str,
        relationship_type: str,
        strength: float = 1.0,
        reason: str = "",
    ) -> MemoryToolResult:
        """
        Connect two memories with a relationship.

        Args:
            from_memory_id: Source memory ID
            to_memory_id: Target memory ID
            relationship_type: Type of relationship (e.g., "extends", "uses", "contradicts")
            strength: Strength of the relationship (0.0 to 1.0)
            reason: Reason for the connection

        Returns:
            Result indicating success/failure
        """
        try:
            success = await self.memory.connect(
                from_memory_id=from_memory_id,
                to_memory_id=to_memory_id,
                relationship_type=relationship_type,
                strength=strength,
                metadata={"reason": reason},
            )

            if success:
                return MemoryToolResult(
                    success=True,
                    message=f"Connected memories {from_memory_id} -> {to_memory_id} ({relationship_type})",
                )
            else:
                return MemoryToolResult(
                    success=False,
                    message=f"Failed to connect memories {from_memory_id} -> {to_memory_id}",
                )

        except Exception as e:
            log.error(
                "connect_memories_failed",
                from_id=from_memory_id,
                to_id=to_memory_id,
                error=str(e),
            )
            return MemoryToolResult(
                success=False,
                error=str(e),
                message=f"Failed to connect memories: {str(e)}",
            )

    async def reflect_on_memory(self, memory_id: str) -> MemoryToolResult:
        """
        Reflect on a specific memory's performance and relationships.

        Args:
            memory_id: Memory to analyze

        Returns:
            Result with analysis data
        """
        try:
            analysis = await self.memory.reflect(memory_id)

            if "error" in analysis:
                return MemoryToolResult(
                    success=False,
                    error=analysis["error"],
                    message=f"Failed to reflect on memory {memory_id}",
                )

            return MemoryToolResult(
                success=True,
                data=analysis,
                message=f"Reflection complete for memory {memory_id}",
            )

        except Exception as e:
            log.error("reflect_on_memory_failed", memory_id=memory_id, error=str(e))
            return MemoryToolResult(
                success=False,
                error=str(e),
                message=f"Failed to reflect on memory {memory_id}",
            )

    async def forget_memory(self, memory_id: str, reason: str) -> MemoryToolResult:
        """
        Forget a specific memory.

        Args:
            memory_id: Memory to forget
            reason: Reason for forgetting

        Returns:
            Result indicating success/failure
        """
        try:
            success = await self.memory.forget(memory_id, reason)

            if success:
                return MemoryToolResult(
                    success=True,
                    message=f"Forgot memory {memory_id} (reason: {reason})",
                )
            else:
                return MemoryToolResult(
                    success=False, message=f"Failed to forget memory {memory_id}"
                )

        except Exception as e:
            log.error("forget_memory_failed", memory_id=memory_id, error=str(e))
            return MemoryToolResult(
                success=False,
                error=str(e),
                message=f"Failed to forget memory {memory_id}",
            )

    async def consolidate_memories(self, memory_ids: List[str]) -> MemoryToolResult:
        """
        Consolidate multiple similar memories into one.

        Args:
            memory_ids: List of memory IDs to consolidate

        Returns:
            Result with consolidated memory ID if successful
        """
        try:
            consolidated_id = await self.memory.consolidate(memory_ids)

            if consolidated_id:
                return MemoryToolResult(
                    success=True,
                    data={"consolidated_id": consolidated_id},
                    message=f"Consolidated {len(memory_ids)} memories into {consolidated_id}",
                )
            else:
                return MemoryToolResult(
                    success=False, message=f"Failed to consolidate memories"
                )

        except Exception as e:
            log.error(
                "consolidate_memories_failed", memory_ids=memory_ids, error=str(e)
            )
            return MemoryToolResult(
                success=False,
                error=str(e),
                message=f"Failed to consolidate memories: {str(e)}",
            )

    async def get_memory_stats(self) -> MemoryToolResult:
        """
        Get statistics about the memory system.

        Returns:
            Result with memory statistics
        """
        try:
            stats = await self.memory.get_stats()

            if "error" in stats:
                return MemoryToolResult(
                    success=False,
                    error=stats["error"],
                    message="Failed to get memory stats",
                )

            return MemoryToolResult(
                success=True,
                data=stats,
                message="Memory statistics retrieved successfully",
            )

        except Exception as e:
            log.error("get_memory_stats_failed", error=str(e))
            return MemoryToolResult(
                success=False, error=str(e), message="Failed to get memory stats"
            )

    async def mark_memory_used(
        self, memory_id: str, success: bool = True
    ) -> MemoryToolResult:
        """
        Mark a memory as used and update its success rate.

        Args:
            memory_id: Memory that was used
            success: Whether the usage was successful

        Returns:
            Result indicating success/failure
        """
        try:
            # Update usage statistics in the database
            self.memory.conn.execute(
                """
                MATCH (m:Memory {id: $id})
                SET m.usage_count = m.usage_count + 1,
                    m.success_count = m.success_count + $success_increment,
                    m.last_used = $now,
                    m.updated_at = $now
            """,
                {
                    "id": memory_id,
                    "success_increment": 1 if success else 0,
                    "now": datetime.utcnow(),
                },
            )

            # Commit the usage update
            self.memory.conn.commit()

            return MemoryToolResult(
                success=True,
                message=f"Marked memory {memory_id} as used ({'success' if success else 'failure'})",
            )

        except Exception as e:
            log.error("mark_memory_used_failed", memory_id=memory_id, error=str(e))
            return MemoryToolResult(
                success=False,
                error=str(e),
                message=f"Failed to mark memory {memory_id} as used",
            )

    def get_tool_descriptions(self) -> List[Dict[str, Any]]:
        """
        Get descriptions of all available memory tools for the agent.

        Returns:
            List of tool descriptions
        """
        return [
            {
                "name": "remember_concept",
                "description": "Remember a business concept and how it maps to database structures",
                "parameters": {
                    "name": "Name of the concept",
                    "description": "Human-readable description",
                    "business_terms": "Alternative terms users might use",
                    "database_mapping": "How this concept maps to database tables/columns",
                    "context": "Additional context (optional)",
                },
            },
            {
                "name": "remember_pattern",
                "description": "Remember a successful SQL pattern for future use",
                "parameters": {
                    "name": "Name of the pattern",
                    "trigger_phrase": "What user said that triggered this pattern",
                    "sql_template": "The SQL template that worked",
                    "tables_used": "Tables involved in this pattern",
                    "success_context": "Context where this pattern succeeded",
                    "context": "Additional context (optional)",
                },
            },
            {
                "name": "remember_mapping",
                "description": "Remember a mapping between user terms and database values",
                "parameters": {
                    "name": "Name of the mapping",
                    "user_term": "What the user said",
                    "database_value": "Database equivalent",
                    "mapping_type": "Type of mapping",
                    "context": "Additional context (optional)",
                },
            },
            {
                "name": "remember_error_fix",
                "description": "Remember how to fix a specific error pattern",
                "parameters": {
                    "name": "Name of the error fix",
                    "error_pattern": "Pattern that identifies the error",
                    "solution": "How to fix the error",
                    "root_cause": "Why the error occurred",
                    "context": "Additional context (optional)",
                },
            },
            {
                "name": "recall_knowledge",
                "description": "Recall relevant knowledge from memory",
                "parameters": {
                    "query": "What to search for",
                    "memory_types": "Types of memories to search (optional)",
                    "context": "Context to help with search (optional)",
                    "limit": "Maximum number of results (optional)",
                },
            },
            {
                "name": "connect_memories",
                "description": "Connect two memories with a relationship",
                "parameters": {
                    "from_memory_id": "Source memory ID",
                    "to_memory_id": "Target memory ID",
                    "relationship_type": "Type of relationship",
                    "strength": "Strength of the relationship (0.0 to 1.0, optional)",
                    "reason": "Reason for the connection (optional)",
                },
            },
            {
                "name": "reflect_on_memory",
                "description": "Reflect on a specific memory's performance and relationships",
                "parameters": {"memory_id": "Memory to analyze"},
            },
            {
                "name": "forget_memory",
                "description": "Forget a specific memory",
                "parameters": {
                    "memory_id": "Memory to forget",
                    "reason": "Reason for forgetting",
                },
            },
            {
                "name": "consolidate_memories",
                "description": "Consolidate multiple similar memories into one",
                "parameters": {"memory_ids": "List of memory IDs to consolidate"},
            },
            {
                "name": "get_memory_stats",
                "description": "Get statistics about the memory system",
                "parameters": {},
            },
            {
                "name": "mark_memory_used",
                "description": "Mark a memory as used and update its success rate",
                "parameters": {
                    "memory_id": "Memory that was used",
                    "success": "Whether the usage was successful (optional)",
                },
            },
        ]
