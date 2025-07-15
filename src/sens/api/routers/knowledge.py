"""
Knowledge System API Router
Provides endpoints for accessing the LLM-powered database knowledge system.
"""

from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from sens.agents.note_taker import DatabaseNote, LLMDatabaseNoteTaker, TableKnowledge

log = structlog.get_logger()

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

# Global note taker instance
_note_taker: Optional[LLMDatabaseNoteTaker] = None


def get_note_taker() -> LLMDatabaseNoteTaker:
    """Get or create the global note taker instance."""
    global _note_taker
    if _note_taker is None:
        _note_taker = LLMDatabaseNoteTaker()
    return _note_taker


class KnowledgeStatsResponse(BaseModel):
    """Response model for knowledge statistics."""

    total_notes: int
    categories: Dict[str, int]
    confidence_distribution: Dict[str, int]
    recent_discoveries: int
    tables_covered: int


class KnowledgeDataResponse(BaseModel):
    """Response model for knowledge data."""

    notes: List[Dict[str, Any]]
    table_knowledge: Dict[str, Dict[str, Any]]
    stats: KnowledgeStatsResponse


class KnowledgeActionRequest(BaseModel):
    """Request model for knowledge actions."""

    action: str = Field(
        ..., description="Action to perform: 'clear_notes', 'export_notes'"
    )
    data: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional data for the action"
    )


@router.get("/data", response_model=KnowledgeDataResponse)
async def get_knowledge_data(
    category: str = Query(default="all", description="Filter by category"),
    search: str = Query(default="", description="Search term"),
    limit: int = Query(default=100, description="Maximum number of notes to return"),
):
    """Get knowledge data from the LLM note-taking system."""
    try:
        note_taker = get_note_taker()

        # Get all notes
        all_notes = note_taker.notes

        # Filter by category
        if category != "all":
            all_notes = [note for note in all_notes if note.category == category]

        # Filter by search term
        if search:
            search_lower = search.lower()
            all_notes = [
                note
                for note in all_notes
                if (
                    search_lower in note.title.lower()
                    or search_lower in note.content.lower()
                    or any(search_lower in tag.lower() for tag in note.tags)
                )
            ]

        # Limit results
        notes = all_notes[:limit]

        # Convert notes to dict format
        notes_data = []
        for note in notes:
            notes_data.append(
                {
                    "timestamp": note.timestamp,
                    "category": note.category,
                    "title": note.title,
                    "content": note.content,
                    "tables_involved": note.tables_involved,
                    "confidence": note.confidence,
                    "source": note.source,
                    "tags": note.tags,
                    "insights": note.insights,
                }
            )

        # Convert table knowledge to dict format
        table_knowledge_data = {}
        for table_name, knowledge in note_taker.table_knowledge.items():
            table_knowledge_data[table_name] = {
                "table_name": knowledge.table_name,
                "columns": knowledge.columns,
                "relationships": knowledge.relationships,
                "data_patterns": knowledge.data_patterns,
                "insights": knowledge.insights,
                "last_updated": knowledge.last_updated,
            }

        # Calculate statistics
        category_counts = {}
        confidence_distribution = {"high": 0, "medium": 0, "low": 0}

        for note in note_taker.notes:
            # Count categories
            category_counts[note.category] = category_counts.get(note.category, 0) + 1

            # Count confidence levels
            if note.confidence >= 0.8:
                confidence_distribution["high"] += 1
            elif note.confidence >= 0.6:
                confidence_distribution["medium"] += 1
            else:
                confidence_distribution["low"] += 1

        # Count recent discoveries (last 24 hours)
        from datetime import datetime, timedelta

        recent_cutoff = datetime.now() - timedelta(hours=24)
        recent_discoveries = sum(
            1
            for note in note_taker.notes
            if datetime.fromisoformat(note.timestamp.replace("Z", "+00:00"))
            > recent_cutoff
        )

        stats = KnowledgeStatsResponse(
            total_notes=len(note_taker.notes),
            categories=category_counts,
            confidence_distribution=confidence_distribution,
            recent_discoveries=recent_discoveries,
            tables_covered=len(note_taker.table_knowledge),
        )

        return KnowledgeDataResponse(
            notes=notes_data, table_knowledge=table_knowledge_data, stats=stats
        )

    except Exception as e:
        log.error("knowledge_data_error", error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch knowledge data: {str(e)}"
        )


@router.post("/action")
async def perform_knowledge_action(request: KnowledgeActionRequest):
    """Perform actions on the knowledge system."""
    try:
        note_taker = get_note_taker()

        if request.action == "clear_notes":
            # Clear all notes
            note_taker.notes = []
            note_taker.table_knowledge = {}
            note_taker.save_notes()
            return {"success": True, "message": "All notes cleared successfully"}

        elif request.action == "export_notes":
            # Export notes to a file (return the data)
            export_data = {
                "notes": [
                    {
                        "timestamp": note.timestamp,
                        "category": note.category,
                        "title": note.title,
                        "content": note.content,
                        "tables_involved": note.tables_involved,
                        "confidence": note.confidence,
                        "source": note.source,
                        "tags": note.tags,
                        "insights": note.insights,
                    }
                    for note in note_taker.notes
                ],
                "table_knowledge": {
                    table_name: {
                        "table_name": knowledge.table_name,
                        "columns": knowledge.columns,
                        "relationships": knowledge.relationships,
                        "data_patterns": knowledge.data_patterns,
                        "insights": knowledge.insights,
                        "last_updated": knowledge.last_updated,
                    }
                    for table_name, knowledge in note_taker.table_knowledge.items()
                },
                "export_timestamp": datetime.now().isoformat(),
            }
            return {
                "success": True,
                "data": export_data,
                "message": "Notes exported successfully",
            }

        else:
            raise HTTPException(
                status_code=400, detail=f"Unknown action: {request.action}"
            )

    except HTTPException:
        raise
    except Exception as e:
        log.error("knowledge_action_error", error=str(e), action=request.action)
        raise HTTPException(
            status_code=500, detail=f"Failed to perform action: {str(e)}"
        )


@router.get("/stats", response_model=KnowledgeStatsResponse)
async def get_knowledge_stats():
    """Get knowledge system statistics."""
    try:
        note_taker = get_note_taker()

        # Calculate statistics
        category_counts = {}
        confidence_distribution = {"high": 0, "medium": 0, "low": 0}

        for note in note_taker.notes:
            # Count categories
            category_counts[note.category] = category_counts.get(note.category, 0) + 1

            # Count confidence levels
            if note.confidence >= 0.8:
                confidence_distribution["high"] += 1
            elif note.confidence >= 0.6:
                confidence_distribution["medium"] += 1
            else:
                confidence_distribution["low"] += 1

        # Count recent discoveries (last 24 hours)
        from datetime import datetime, timedelta

        recent_cutoff = datetime.now() - timedelta(hours=24)
        recent_discoveries = sum(
            1
            for note in note_taker.notes
            if datetime.fromisoformat(note.timestamp.replace("Z", "+00:00"))
            > recent_cutoff
        )

        return KnowledgeStatsResponse(
            total_notes=len(note_taker.notes),
            categories=category_counts,
            confidence_distribution=confidence_distribution,
            recent_discoveries=recent_discoveries,
            tables_covered=len(note_taker.table_knowledge),
        )

    except Exception as e:
        log.error("knowledge_stats_error", error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch knowledge stats: {str(e)}"
        )


@router.get("/health")
async def knowledge_health():
    """Health check for the knowledge system."""
    try:
        note_taker = get_note_taker()
        return {
            "status": "healthy",
            "notes_count": len(note_taker.notes),
            "tables_count": len(note_taker.table_knowledge),
            "note_taker_initialized": note_taker is not None,
        }
    except Exception as e:
        log.error("knowledge_health_error", error=str(e))
        return {"status": "unhealthy", "error": str(e)}
