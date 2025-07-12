"""
Memory Management API Router
Provides endpoints for managing agent memory across sessions
"""

import json
from typing import Dict, List, Optional

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from sens.memory import AgentMemory, AgentMemoryTools, MemoryType

log = structlog.get_logger()

router = APIRouter(prefix="/memory", tags=["memory"])


class MemorySearchRequest(BaseModel):
    query: str
    session_id: str
    memory_types: Optional[List[str]] = None
    context: Optional[Dict] = None
    limit: int = 10


class MemoryCreateRequest(BaseModel):
    session_id: str
    memory_type: str
    name: str
    content: Dict
    context: Optional[Dict] = None


class MemoryConnectionRequest(BaseModel):
    session_id: str
    from_memory_id: str
    to_memory_id: str
    relationship_type: str
    strength: float = 1.0
    reason: Optional[str] = None


# Global memory managers by session
_memory_managers: Dict[str, AgentMemoryTools] = {}


def get_memory_manager(session_id: str) -> AgentMemoryTools:
    """Get or create memory manager for session"""
    if session_id not in _memory_managers:
        memory = AgentMemory(db_path=f"session_memory_{session_id}.db")
        _memory_managers[session_id] = AgentMemoryTools(memory)
        log.info("memory_manager_created", session_id=session_id)
    return _memory_managers[session_id]


@router.get("/stats")
async def get_memory_stats(session_id: str = Query(...)):
    """Get memory statistics for a session"""
    try:
        memory_tools = get_memory_manager(session_id)
        result = await memory_tools.get_memory_stats()

        if result.success:
            return {"status": "success", "data": result.data, "session_id": session_id}
        else:
            raise HTTPException(status_code=500, detail=result.error)

    except Exception as e:
        log.error("memory_stats_failed", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search_memories(request: MemorySearchRequest):
    """Search memories by content"""
    try:
        memory_tools = get_memory_manager(request.session_id)

        result = await memory_tools.recall_knowledge(
            query=request.query,
            memory_types=request.memory_types,
            context=request.context or {},
            limit=request.limit,
        )

        if result.success:
            return {
                "status": "success",
                "data": result.data,
                "session_id": request.session_id,
            }
        else:
            raise HTTPException(status_code=500, detail=result.error)

    except Exception as e:
        log.error("memory_search_failed", session_id=request.session_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create")
async def create_memory(request: MemoryCreateRequest):
    """Create a new memory"""
    try:
        memory_tools = get_memory_manager(request.session_id)

        # Route to appropriate memory creation method
        if request.memory_type == "concept":
            result = await memory_tools.remember_concept(
                name=request.name,
                description=request.content.get("description", ""),
                business_terms=request.content.get("business_terms", []),
                database_mapping=request.content.get("database_mapping", {}),
                context=request.context or {},
            )
        elif request.memory_type == "pattern":
            result = await memory_tools.remember_pattern(
                name=request.name,
                trigger_phrase=request.content.get("trigger_phrase", ""),
                sql_template=request.content.get("sql_template", ""),
                tables_used=request.content.get("tables_used", []),
                success_context=request.content.get("success_context", {}),
                context=request.context or {},
            )
        elif request.memory_type == "mapping":
            result = await memory_tools.remember_mapping(
                name=request.name,
                user_term=request.content.get("user_term", ""),
                database_value=request.content.get("database_value", ""),
                mapping_type=request.content.get("mapping_type", ""),
                context=request.context or {},
            )
        else:
            raise HTTPException(
                status_code=400, detail=f"Unknown memory type: {request.memory_type}"
            )

        if result.success:
            return {
                "status": "success",
                "data": result.data,
                "message": result.message,
                "session_id": request.session_id,
            }
        else:
            raise HTTPException(status_code=500, detail=result.error)

    except Exception as e:
        log.error("memory_create_failed", session_id=request.session_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/connect")
async def connect_memories(request: MemoryConnectionRequest):
    """Connect two memories with a relationship"""
    try:
        memory_tools = get_memory_manager(request.session_id)

        result = await memory_tools.connect_memories(
            from_memory_id=request.from_memory_id,
            to_memory_id=request.to_memory_id,
            relationship_type=request.relationship_type,
            strength=request.strength,
            reason=request.reason or "",
        )

        if result.success:
            return {
                "status": "success",
                "message": result.message,
                "session_id": request.session_id,
            }
        else:
            raise HTTPException(status_code=500, detail=result.error)

    except Exception as e:
        log.error("memory_connect_failed", session_id=request.session_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reflect/{memory_id}")
async def reflect_on_memory(memory_id: str, session_id: str = Query(...)):
    """Analyze a memory's performance and relationships"""
    try:
        memory_tools = get_memory_manager(session_id)

        result = await memory_tools.reflect_on_memory(memory_id)

        if result.success:
            return {"status": "success", "data": result.data, "session_id": session_id}
        else:
            raise HTTPException(status_code=500, detail=result.error)

    except Exception as e:
        log.error(
            "memory_reflect_failed",
            session_id=session_id,
            memory_id=memory_id,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{memory_id}")
async def forget_memory(
    memory_id: str, session_id: str = Query(...), reason: str = Query("User requested")
):
    """Remove a specific memory"""
    try:
        memory_tools = get_memory_manager(session_id)

        result = await memory_tools.forget_memory(memory_id, reason)

        if result.success:
            return {
                "status": "success",
                "message": result.message,
                "session_id": session_id,
            }
        else:
            raise HTTPException(status_code=500, detail=result.error)

    except Exception as e:
        log.error(
            "memory_forget_failed",
            session_id=session_id,
            memory_id=memory_id,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/consolidate")
async def consolidate_memories(session_id: str, memory_ids: List[str]):
    """Consolidate multiple similar memories"""
    try:
        memory_tools = get_memory_manager(session_id)

        result = await memory_tools.consolidate_memories(memory_ids)

        if result.success:
            return {
                "status": "success",
                "data": result.data,
                "message": result.message,
                "session_id": session_id,
            }
        else:
            raise HTTPException(status_code=500, detail=result.error)

    except Exception as e:
        log.error("memory_consolidate_failed", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export")
async def export_memory(session_id: str = Query(...)):
    """Export all memories for a session"""
    try:
        memory_tools = get_memory_manager(session_id)

        # Get all memories
        result = await memory_tools.recall_knowledge("", limit=1000)

        if result.success:
            return {
                "status": "success",
                "data": {
                    "memories": result.data["memories"],
                    "export_timestamp": "2025-01-01T00:00:00Z",
                    "session_id": session_id,
                },
                "session_id": session_id,
            }
        else:
            raise HTTPException(status_code=500, detail=result.error)

    except Exception as e:
        log.error("memory_export_failed", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/session/{session_id}")
async def cleanup_session_memory(session_id: str):
    """Clean up memory for a session"""
    try:
        if session_id in _memory_managers:
            memory_tools = _memory_managers[session_id]
            memory_tools.memory.close()
            del _memory_managers[session_id]
            log.info("memory_session_cleaned", session_id=session_id)

        return {
            "status": "success",
            "message": f"Session {session_id} memory cleaned up",
            "session_id": session_id,
        }

    except Exception as e:
        log.error("memory_cleanup_failed", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
