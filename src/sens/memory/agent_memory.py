"""
Agent Memory System using KuzuDB

Core memory management for the SENS agent. Provides graph-based knowledge storage
where the agent can remember patterns, concepts, and relationships.
"""

import json
import time
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import kuzu
import structlog
from pydantic import BaseModel, Field

log = structlog.get_logger()


class MemoryType(str, Enum):
    """Types of memories the agent can store"""

    CONCEPT = "concept"  # Business concepts (e.g., "annual_revenue")
    PATTERN = "pattern"  # SQL patterns that work
    MAPPING = (
        "mapping"  # Value mappings (e.g., "tech companies" -> "sector='Technology'")
    )
    RULE = "rule"  # Business rules and constraints
    CALCULATION = "calculation"  # How to calculate metrics
    ERROR_FIX = "error_fix"  # Solutions to common errors
    RELATIONSHIP = "relationship"  # How tables/concepts relate


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


class AgentMemory:
    """
    Agent-controlled knowledge graph using KuzuDB.

    The agent uses this to remember patterns, concepts, and relationships
    that improve its performance over time.
    """

    def __init__(self, db_path: str = "agent_memory.db"):
        """Initialize the agent memory system"""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.db = kuzu.Database(str(self.db_path))
        self.conn = kuzu.Connection(self.db)

        # Initialize schema
        self._init_schema()

        # Performance tracking
        self.stats = {
            "memories_stored": 0,
            "queries_executed": 0,
            "avg_query_time": 0.0,
        }

        log.info(
            "agent_memory_initialized",
            db_path=str(self.db_path),
            memory_count=self._count_memories(),
        )

    def _init_schema(self) -> None:
        """Initialize the KuzuDB schema for agent memory"""

        # Create Memory node table
        self.conn.execute(
            """
            CREATE NODE TABLE IF NOT EXISTS Memory (
                id STRING,
                memory_type STRING,
                name STRING,
                content STRING,
                metadata STRING,
                confidence DOUBLE,
                usage_count INT64,
                success_count INT64,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                last_used TIMESTAMP,
                PRIMARY KEY (id)
            )
        """
        )

        # Create relationship table for memory connections
        self.conn.execute(
            """
            CREATE REL TABLE IF NOT EXISTS Relates (
                FROM Memory TO Memory,
                relationship_type STRING,
                strength DOUBLE,
                metadata STRING,
                created_at TIMESTAMP
            )
        """
        )

        # Create indexes for performance
        try:
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_type ON Memory(memory_type)"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_name ON Memory(name)"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_confidence ON Memory(confidence)"
            )
        except Exception as e:
            # KuzuDB might not support this syntax yet
            log.debug("index_creation_skipped", error=str(e))

    def _count_memories(self) -> int:
        """Count total memories in the database"""
        try:
            result = self.conn.execute("MATCH (m:Memory) RETURN COUNT(m) as count")
            return result.get_next()[0] if result.has_next() else 0
        except Exception:
            return 0

    async def remember(
        self,
        memory_type: MemoryType,
        name: str,
        content: Dict[str, Any],
        context: Dict[str, Any] = None,
    ) -> str:
        """
        Store a new memory in the knowledge graph.

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

        # Store in KuzuDB
        try:
            self.conn.execute(
                """
                CREATE (m:Memory {
                    id: $id,
                    memory_type: $memory_type,
                    name: $name,
                    content: $content,
                    metadata: $metadata,
                    confidence: $confidence,
                    usage_count: $usage_count,
                    success_count: $success_count,
                    created_at: $created_at,
                    updated_at: $updated_at,
                    last_used: $last_used
                })
            """,
                {
                    "id": memory.id,
                    "memory_type": memory.memory_type.value,
                    "name": memory.name,
                    "content": json.dumps(memory.content),
                    "metadata": json.dumps(memory.metadata),
                    "confidence": memory.confidence,
                    "usage_count": memory.usage_count,
                    "success_count": memory.success_count,
                    "created_at": memory.created_at,
                    "updated_at": memory.updated_at,
                    "last_used": memory.last_used,
                },
            )

            # CRITICAL FIX: Commit the transaction to persist the memory
            self.conn.commit()

            self.stats["memories_stored"] += 1

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

        except Exception as e:
            log.error("memory_store_failed", memory_id=memory_id, error=str(e))
            raise

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

        # Build Cypher query
        cypher_parts = ["MATCH (m:Memory)"]
        params = {}

        conditions = []

        # Filter by memory types if specified
        if memory_types:
            type_values = [mt.value for mt in memory_types]
            conditions.append("m.memory_type IN $memory_types")
            params["memory_types"] = type_values

        # Simple text matching for now (could be enhanced with embeddings)
        if query:
            # Split query into words and search for each word
            query_words = query.lower().split()
            word_conditions = []
            for i, word in enumerate(query_words):
                word_param = f"word_{i}"
                word_conditions.append(
                    f"(m.name CONTAINS ${word_param} OR m.content CONTAINS ${word_param})"
                )
                params[word_param] = word

            if word_conditions:
                conditions.append(f"({' OR '.join(word_conditions)})")

        # Add context filtering
        if context:
            database = context.get("database")
            if database:
                conditions.append("m.metadata CONTAINS $database")
                params["database"] = database

        # Build WHERE clause
        if conditions:
            cypher_parts.append(f"WHERE {' AND '.join(conditions)}")

        # Order by confidence and usage
        cypher_parts.append(
            """
            RETURN m.id, m.memory_type, m.name, m.content, m.metadata,
                   m.confidence, m.usage_count, m.success_count,
                   m.created_at, m.updated_at, m.last_used
            ORDER BY m.confidence DESC, m.usage_count DESC
            LIMIT $limit
        """
        )

        params["limit"] = limit
        cypher = " ".join(cypher_parts)

        try:
            result = self.conn.execute(cypher, params)
            memories = []

            while result.has_next():
                row = result.get_next()
                memory = Memory(
                    id=row[0],
                    memory_type=MemoryType(row[1]),
                    name=row[2],
                    content=json.loads(row[3]),
                    metadata=json.loads(row[4]) if row[4] else {},
                    confidence=row[5],
                    usage_count=row[6],
                    success_count=row[7],
                    created_at=row[8],
                    updated_at=row[9],
                    last_used=row[10],
                )
                memories.append(memory)

            query_time = time.time() - start_time
            self.stats["queries_executed"] += 1
            self.stats["avg_query_time"] = (
                self.stats["avg_query_time"] * (self.stats["queries_executed"] - 1)
                + query_time
            ) / self.stats["queries_executed"]

            log.info(
                "memories_recalled",
                query=query[:50] + "..." if len(query) > 50 else query,
                count=len(memories),
                query_time_ms=query_time * 1000,
            )

            return memories

        except Exception as e:
            log.error("memory_recall_failed", query=query, error=str(e))
            return []

    async def connect(
        self,
        from_memory_id: str,
        to_memory_id: str,
        relationship_type: str,
        strength: float = 1.0,
        metadata: Dict[str, Any] = None,
    ) -> bool:
        """
        Create a relationship between two memories.

        Args:
            from_memory_id: Source memory ID
            to_memory_id: Target memory ID
            relationship_type: Type of relationship (e.g., "extends", "uses", "contradicts")
            strength: Strength of the relationship (0.0 to 1.0)
            metadata: Additional metadata about the relationship

        Returns:
            True if connection was created successfully
        """
        try:
            self.conn.execute(
                """
                MATCH (from:Memory {id: $from_id}), (to:Memory {id: $to_id})
                CREATE (from)-[r:Relates {
                    relationship_type: $rel_type,
                    strength: $strength,
                    metadata: $metadata,
                    created_at: $created_at
                }]->(to)
            """,
                {
                    "from_id": from_memory_id,
                    "to_id": to_memory_id,
                    "rel_type": relationship_type,
                    "strength": strength,
                    "metadata": json.dumps(metadata or {}),
                    "created_at": datetime.utcnow(),
                },
            )

            # Commit the transaction to persist the connection
            self.conn.commit()

            log.info(
                "memory_connection_created",
                from_id=from_memory_id,
                to_id=to_memory_id,
                relationship=relationship_type,
            )

            return True

        except Exception as e:
            log.error(
                "memory_connection_failed",
                from_id=from_memory_id,
                to_id=to_memory_id,
                error=str(e),
            )
            return False

    async def reflect(self, memory_id: str) -> Dict[str, Any]:
        """
        Analyze a memory's performance and relationships.

        Args:
            memory_id: Memory to analyze

        Returns:
            Analysis results including usage stats and relationships
        """
        try:
            # Get memory details
            result = self.conn.execute(
                """
                MATCH (m:Memory {id: $id})
                RETURN m.usage_count, m.success_count, m.confidence,
                       m.created_at, m.last_used
            """,
                {"id": memory_id},
            )

            if not result.has_next():
                return {"error": "Memory not found"}

            row = result.get_next()
            usage_count = row[0]
            success_count = row[1]
            confidence = row[2]
            created_at = row[3]
            last_used = row[4]

            # Get relationships
            rel_result = self.conn.execute(
                """
                MATCH (m:Memory {id: $id})-[r:Relates]-(other:Memory)
                RETURN r.relationship_type, r.strength, other.name, other.memory_type
            """,
                {"id": memory_id},
            )

            relationships = []
            while rel_result.has_next():
                rel_row = rel_result.get_next()
                relationships.append(
                    {
                        "type": rel_row[0],
                        "strength": rel_row[1],
                        "related_to": rel_row[2],
                        "related_type": rel_row[3],
                    }
                )

            analysis = {
                "memory_id": memory_id,
                "usage_count": usage_count,
                "success_count": success_count,
                "success_rate": success_count / max(usage_count, 1),
                "confidence": confidence,
                "created_at": created_at,
                "last_used": last_used,
                "relationships": relationships,
                "age_days": (datetime.utcnow() - created_at).days if created_at else 0,
                "recommendation": self._get_recommendation(
                    usage_count, success_count, confidence
                ),
            }

            log.info(
                "memory_reflection_complete",
                memory_id=memory_id,
                success_rate=analysis["success_rate"],
                relationship_count=len(relationships),
            )

            return analysis

        except Exception as e:
            log.error("memory_reflection_failed", memory_id=memory_id, error=str(e))
            return {"error": str(e)}

    def _get_recommendation(
        self, usage_count: int, success_count: int, confidence: float
    ) -> str:
        """Get recommendation for memory based on performance"""
        if usage_count == 0:
            return "unused"

        success_rate = success_count / usage_count

        if success_rate < 0.3:
            return "consider_forgetting"
        elif success_rate < 0.7:
            return "needs_improvement"
        elif success_rate > 0.9 and confidence > 0.8:
            return "highly_reliable"
        else:
            return "performing_well"

    async def forget(self, memory_id: str, reason: str) -> bool:
        """
        Remove a memory from the knowledge graph.

        Args:
            memory_id: Memory to remove
            reason: Reason for forgetting

        Returns:
            True if memory was removed successfully
        """
        try:
            # Remove the memory node (relationships will be cascade deleted)
            result = self.conn.execute(
                """
                MATCH (m:Memory {id: $id})
                DELETE m
            """,
                {"id": memory_id},
            )

            # Commit the transaction to persist the deletion
            self.conn.commit()

            log.info("memory_forgotten", memory_id=memory_id, reason=reason)

            return True

        except Exception as e:
            log.error("memory_forget_failed", memory_id=memory_id, error=str(e))
            return False

    async def consolidate(self, memory_ids: List[str]) -> Optional[str]:
        """
        Consolidate multiple similar memories into one stronger memory.

        Args:
            memory_ids: List of memories to consolidate

        Returns:
            ID of the consolidated memory, or None if failed
        """
        if len(memory_ids) < 2:
            return None

        try:
            # Get all memories to consolidate
            memories = []
            for memory_id in memory_ids:
                result = self.conn.execute(
                    """
                    MATCH (m:Memory {id: $id})
                    RETURN m.memory_type, m.name, m.content, m.metadata,
                           m.confidence, m.usage_count, m.success_count
                """,
                    {"id": memory_id},
                )

                if result.has_next():
                    row = result.get_next()
                    memories.append(
                        {
                            "id": memory_id,
                            "memory_type": row[0],
                            "name": row[1],
                            "content": json.loads(row[2]),
                            "metadata": json.loads(row[3]) if row[3] else {},
                            "confidence": row[4],
                            "usage_count": row[5],
                            "success_count": row[6],
                        }
                    )

            if not memories:
                return None

            # Create consolidated memory
            consolidated_content = self._merge_memory_content(memories)
            consolidated_metadata = self._merge_memory_metadata(memories)

            # Calculate combined statistics
            total_usage = sum(m["usage_count"] for m in memories)
            total_success = sum(m["success_count"] for m in memories)
            avg_confidence = sum(m["confidence"] for m in memories) / len(memories)

            # Create new consolidated memory
            consolidated_id = await self.remember(
                memory_type=MemoryType(memories[0]["memory_type"]),
                name=f"consolidated_{memories[0]['name']}",
                content=consolidated_content,
                context=consolidated_metadata,
            )

            # Update usage statistics
            self.conn.execute(
                """
                MATCH (m:Memory {id: $id})
                SET m.usage_count = $usage_count,
                    m.success_count = $success_count,
                    m.confidence = $confidence
            """,
                {
                    "id": consolidated_id,
                    "usage_count": total_usage,
                    "success_count": total_success,
                    "confidence": avg_confidence,
                },
            )

            # Commit the statistics update
            self.conn.commit()

            # Remove old memories
            for memory_id in memory_ids:
                await self.forget(memory_id, "consolidated")

            log.info(
                "memories_consolidated",
                original_count=len(memory_ids),
                consolidated_id=consolidated_id,
                total_usage=total_usage,
            )

            return consolidated_id

        except Exception as e:
            log.error(
                "memory_consolidation_failed", memory_ids=memory_ids, error=str(e)
            )
            return None

    def _merge_memory_content(self, memories: List[Dict]) -> Dict[str, Any]:
        """Merge content from multiple memories"""
        merged = {}

        for memory in memories:
            content = memory["content"]
            for key, value in content.items():
                if key not in merged:
                    merged[key] = value
                elif isinstance(value, list) and isinstance(merged[key], list):
                    merged[key].extend(value)
                elif isinstance(value, dict) and isinstance(merged[key], dict):
                    merged[key].update(value)

        return merged

    def _merge_memory_metadata(self, memories: List[Dict]) -> Dict[str, Any]:
        """Merge metadata from multiple memories"""
        merged = {"consolidated_from": [m["id"] for m in memories]}

        for memory in memories:
            metadata = memory["metadata"]
            for key, value in metadata.items():
                if key not in merged:
                    merged[key] = value

        return merged

    async def get_stats(self) -> Dict[str, Any]:
        """Get memory system statistics"""
        try:
            # Count memories by type
            result = self.conn.execute(
                """
                MATCH (m:Memory)
                RETURN m.memory_type, COUNT(m) as count
            """
            )

            memory_counts = {}
            total_memories = 0

            while result.has_next():
                row = result.get_next()
                memory_type = row[0]
                count = row[1]
                memory_counts[memory_type] = count
                total_memories += count

            # Count relationships
            rel_result = self.conn.execute(
                """
                MATCH ()-[r:Relates]-()
                RETURN COUNT(r) as count
            """
            )

            relationship_count = 0
            if rel_result.has_next():
                relationship_count = rel_result.get_next()[0]

            stats = {
                "total_memories": total_memories,
                "memories_by_type": memory_counts,
                "total_relationships": relationship_count,
                "performance": self.stats,
            }

            return stats

        except Exception as e:
            log.error("stats_retrieval_failed", error=str(e))
            return {"error": str(e)}

    def close(self) -> None:
        """Close the database connection"""
        try:
            self.conn.close()
            log.info("agent_memory_closed")
        except Exception as e:
            log.error("memory_close_failed", error=str(e))
