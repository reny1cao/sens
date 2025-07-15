"""
Memory Management API - Web interface for agent memory system
Provides endpoints to inspect, manage, and control the agent's learning system.
"""

import asyncio
from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from sens.memory import AgentMemory, AgentMemoryTools, MemoryType
from sens.settings import get_settings

log = structlog.get_logger()

router = APIRouter(prefix="/api/memory", tags=["memory"])


class MemorySearchRequest(BaseModel):
    """Request model for memory search."""

    query: str = Field(description="Search query for memories")
    memory_types: Optional[List[str]] = Field(
        default=None, description="Filter by memory types"
    )
    limit: int = Field(
        default=20, ge=1, le=100, description="Maximum number of results"
    )


class MemorySearchResponse(BaseModel):
    """Response model for memory search."""

    success: bool
    memories: List[Dict[str, Any]]
    count: int
    error: Optional[str] = None


class MemoryStatsResponse(BaseModel):
    """Response model for memory statistics."""

    success: bool
    total_memories: int
    memories_by_type: Dict[str, int]
    total_relationships: int
    performance: Dict[str, Any]
    configuration: Dict[str, Any]
    error: Optional[str] = None


class LearningInsightsResponse(BaseModel):
    """Response model for learning insights."""

    success: bool
    learned_concepts: List[Dict[str, Any]]
    successful_patterns: List[Dict[str, Any]]
    value_mappings: List[Dict[str, Any]]
    error_fixes: List[Dict[str, Any]]
    total_learned_items: int
    error: Optional[str] = None


class ForgetMemoryRequest(BaseModel):
    """Request model for forgetting a memory."""

    reason: str = Field(description="Reason for forgetting this memory")


class ForgetMemoryResponse(BaseModel):
    """Response model for forgetting a memory."""

    success: bool
    message: str
    error: Optional[str] = None


# Global memory managers by session
_memory_managers: Dict[str, AgentMemoryTools] = {}
_global_memory_tools: Optional[AgentMemoryTools] = None


def get_shared_memory_manager() -> Optional[AgentMemoryTools]:
    """Get the shared global memory manager for use across the application."""
    global _global_memory_tools

    if _global_memory_tools is None:
        # Initialize the global memory manager if not already done
        get_memory_manager("global")

    return _global_memory_tools


def get_memory_manager(session_id: str = "global") -> AgentMemoryTools:
    """Get or create memory manager for session."""
    global _global_memory_tools

    settings = get_settings()
    memory_config = settings.memory

    # If session isolation is disabled, use global memory
    if not memory_config.session_isolation or session_id == "global":
        if _global_memory_tools is None:
            try:
                global_memory = AgentMemory(db_path=memory_config.db_path)
                _global_memory_tools = AgentMemoryTools(global_memory)
                log.info("global_memory_manager_created", db_path=memory_config.db_path)
            except Exception as e:
                log.error("global_memory_manager_creation_failed", error=str(e))
                raise HTTPException(
                    status_code=500, detail=f"Failed to initialize memory: {str(e)}"
                )
        return _global_memory_tools

    # Session-specific memory
    if session_id not in _memory_managers:
        try:
            session_db_path = f"memory_session_{session_id}.db"
            memory = AgentMemory(db_path=session_db_path)
            _memory_managers[session_id] = AgentMemoryTools(memory)
            log.info("session_memory_manager_created", session_id=session_id)
        except Exception as e:
            log.error(
                "session_memory_manager_creation_failed",
                session_id=session_id,
                error=str(e),
            )
            raise HTTPException(
                status_code=500, detail=f"Failed to initialize session memory: {str(e)}"
            )

    return _memory_managers[session_id]


@router.get("/stats", response_model=MemoryStatsResponse)
async def get_memory_stats(
    session_id: str = Query(default="global", description="Session ID for memory stats")
):
    """Get comprehensive memory system statistics."""
    try:
        memory_tools = get_memory_manager(session_id)
        stats_result = await memory_tools.get_memory_stats()

        if not stats_result.success:
            return MemoryStatsResponse(
                success=False,
                total_memories=0,
                memories_by_type={},
                total_relationships=0,
                performance={},
                configuration={},
                error=stats_result.error,
            )

        stats_data = stats_result.data
        settings = get_settings()

        return MemoryStatsResponse(
            success=True,
            total_memories=stats_data.get("total_memories", 0),
            memories_by_type=stats_data.get("memories_by_type", {}),
            total_relationships=stats_data.get("total_relationships", 0),
            performance=stats_data.get("performance", {}),
            configuration={
                "session_isolation": settings.memory.session_isolation,
                "cross_session_sharing": settings.memory.cross_session_sharing,
                "max_memories_per_type": settings.memory.max_memories_per_type,
                "auto_consolidation": settings.memory.auto_consolidation,
                "background_learning": settings.memory.background_learning,
            },
        )

    except Exception as e:
        log.error("get_memory_stats_failed", session_id=session_id, error=str(e))
        return MemoryStatsResponse(
            success=False,
            total_memories=0,
            memories_by_type={},
            total_relationships=0,
            performance={},
            configuration={},
            error=str(e),
        )


@router.post("/search", response_model=MemorySearchResponse)
async def search_memories(
    request: MemorySearchRequest,
    session_id: str = Query(
        default="global", description="Session ID for memory search"
    ),
):
    """Search memories by content with optional type filtering."""
    try:
        memory_tools = get_memory_manager(session_id)

        # Convert string memory types to MemoryType enums
        memory_type_filters = None
        if request.memory_types:
            try:
                memory_type_filters = [
                    MemoryType(mt)
                    for mt in request.memory_types
                    if mt in [t.value for t in MemoryType]
                ]
            except ValueError as e:
                raise HTTPException(
                    status_code=400, detail=f"Invalid memory type: {str(e)}"
                )

        result = await memory_tools.recall_knowledge(
            query=request.query, memory_types=memory_type_filters, limit=request.limit
        )

        if result.success:
            memories = result.data.get("memories", [])
            return MemorySearchResponse(
                success=True, memories=memories, count=len(memories)
            )
        else:
            return MemorySearchResponse(
                success=False, memories=[], count=0, error=result.error
            )

    except Exception as e:
        log.error(
            "search_memories_failed",
            session_id=session_id,
            query=request.query,
            error=str(e),
        )
        return MemorySearchResponse(success=False, memories=[], count=0, error=str(e))


@router.get("/insights", response_model=LearningInsightsResponse)
async def get_learning_insights(
    session_id: str = Query(
        default="global", description="Session ID for learning insights"
    )
):
    """Get insights about what the system has learned - top concepts, patterns, and mappings."""
    try:
        memory_tools = get_memory_manager(session_id)

        # Get different types of memories in parallel
        async def get_memories_by_type(memory_type: str, limit: int = 10):
            result = await memory_tools.recall_knowledge(
                query="", memory_types=[memory_type], limit=limit
            )
            return result.data.get("memories", []) if result.success else []

        # Fetch all memory types in parallel
        concepts_task = get_memories_by_type("concept")
        patterns_task = get_memories_by_type("pattern")
        mappings_task = get_memories_by_type("mapping")
        error_fixes_task = get_memories_by_type("error_fix")

        concepts, patterns, mappings, error_fixes = await asyncio.gather(
            concepts_task,
            patterns_task,
            mappings_task,
            error_fixes_task,
            return_exceptions=True,
        )

        # Handle any exceptions
        if isinstance(concepts, Exception):
            concepts = []
        if isinstance(patterns, Exception):
            patterns = []
        if isinstance(mappings, Exception):
            mappings = []
        if isinstance(error_fixes, Exception):
            error_fixes = []

        total_items = len(concepts) + len(patterns) + len(mappings) + len(error_fixes)

        return LearningInsightsResponse(
            success=True,
            learned_concepts=concepts,
            successful_patterns=patterns,
            value_mappings=mappings,
            error_fixes=error_fixes,
            total_learned_items=total_items,
        )

    except Exception as e:
        log.error("get_learning_insights_failed", session_id=session_id, error=str(e))
        return LearningInsightsResponse(
            success=False,
            learned_concepts=[],
            successful_patterns=[],
            value_mappings=[],
            error_fixes=[],
            total_learned_items=0,
            error=str(e),
        )


@router.delete("/{memory_id}", response_model=ForgetMemoryResponse)
async def forget_memory(
    memory_id: str,
    request: ForgetMemoryRequest,
    session_id: str = Query(
        default="global", description="Session ID for memory management"
    ),
):
    """Remove a specific memory from the system."""
    try:
        memory_tools = get_memory_manager(session_id)
        result = await memory_tools.forget_memory(memory_id, reason=request.reason)

        return ForgetMemoryResponse(
            success=result.success,
            message=result.message or f"Memory {memory_id} forgotten",
        )

    except Exception as e:
        log.error(
            "forget_memory_failed",
            memory_id=memory_id,
            session_id=session_id,
            error=str(e),
        )
        return ForgetMemoryResponse(success=False, message="", error=str(e))


@router.post("/consolidate")
async def consolidate_memories(
    memory_ids: List[str],
    session_id: str = Query(
        default="global", description="Session ID for memory management"
    ),
):
    """Consolidate multiple similar memories into one stronger memory."""
    try:
        if len(memory_ids) < 2:
            raise HTTPException(
                status_code=400,
                detail="At least 2 memory IDs required for consolidation",
            )

        memory_tools = get_memory_manager(session_id)
        result = await memory_tools.consolidate_memories(memory_ids)

        if result.success:
            return {
                "success": True,
                "consolidated_memory_id": result.data,
                "message": f"Successfully consolidated {len(memory_ids)} memories",
            }
        else:
            return {
                "success": False,
                "error": result.error,
                "message": "Failed to consolidate memories",
            }

    except Exception as e:
        log.error(
            "consolidate_memories_failed",
            memory_ids=memory_ids,
            session_id=session_id,
            error=str(e),
        )
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to consolidate memories",
        }


@router.get("/health")
async def get_memory_health():
    """Get the health status of the memory system."""
    try:
        settings = get_settings()

        # Test global memory access
        try:
            global_memory_tools = get_memory_manager("global")
            global_stats = await global_memory_tools.get_memory_stats()
            global_healthy = global_stats.success
        except Exception:
            global_healthy = False

        return {
            "memory_enabled": settings.memory.enabled,
            "session_isolation": settings.memory.session_isolation,
            "global_memory_healthy": global_healthy,
            "configuration": {
                "db_path": settings.memory.db_path,
                "max_memories_per_type": settings.memory.max_memories_per_type,
                "auto_consolidation": settings.memory.auto_consolidation,
                "background_learning": settings.memory.background_learning,
                "cross_session_sharing": settings.memory.cross_session_sharing,
            },
            "active_sessions": len(_memory_managers),
            "status": "healthy" if global_healthy else "degraded",
        }

    except Exception as e:
        log.error("memory_health_check_failed", error=str(e))
        return {"memory_enabled": False, "status": "unhealthy", "error": str(e)}


@router.post("/clear")
async def clear_session_memory(
    session_id: str = Query(description="Session ID to clear memory for"),
    confirm: bool = Query(
        default=False, description="Confirmation flag - must be true"
    ),
):
    """Clear all memories for a specific session. Requires confirmation."""
    if not confirm:
        raise HTTPException(
            status_code=400, detail="Must set confirm=true to clear session memory"
        )

    if session_id == "global":
        raise HTTPException(
            status_code=400, detail="Cannot clear global memory via this endpoint"
        )

    try:
        # Remove from cache
        if session_id in _memory_managers:
            memory_tools = _memory_managers[session_id]
            # Close the memory connection
            if hasattr(memory_tools.memory, "close"):
                memory_tools.memory.close()
            del _memory_managers[session_id]

        # Remove the database file
        import os

        session_db_path = f"memory_session_{session_id}.db"
        if os.path.exists(session_db_path):
            os.remove(session_db_path)
            log.info(
                "session_memory_cleared", session_id=session_id, db_path=session_db_path
            )

        return {
            "success": True,
            "message": f"Session memory cleared for {session_id}",
            "session_id": session_id,
        }

    except Exception as e:
        log.error("clear_session_memory_failed", session_id=session_id, error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to clear session memory: {str(e)}"
        )


@router.get("/types")
async def get_memory_types():
    """Get all available memory types and their descriptions."""
    return {
        "memory_types": [
            {
                "type": memory_type.value,
                "description": _get_memory_type_description(memory_type),
            }
            for memory_type in MemoryType
        ]
    }


def _get_memory_type_description(memory_type: MemoryType) -> str:
    """Get human-readable description for memory types."""
    descriptions = {
        MemoryType.CONCEPT: "Business concepts and their database mappings",
        MemoryType.PATTERN: "Successful SQL patterns and query templates",
        MemoryType.MAPPING: "Value mappings between user terms and database values",
        MemoryType.RULE: "Business rules and constraints",
        MemoryType.CALCULATION: "How to calculate specific metrics",
        MemoryType.ERROR_FIX: "Solutions to common errors",
        MemoryType.RELATIONSHIP: "How tables and concepts relate to each other",
    }
    return descriptions.get(memory_type, "Unknown memory type")
