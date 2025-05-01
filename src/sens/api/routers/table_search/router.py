"""Router for table search endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from .models import (
    DetailedIndexResponse,
    IndexStatsResponse,
    RefreshResponse,
    TableSearchResponse,
)
from .service import TableSearchService

router = APIRouter(
    prefix="/table-search",
    tags=["table-search"],
    responses={404: {"description": "Not found"}},
)


def get_service() -> TableSearchService:
    """Dependency to get TableSearchService instance."""
    return TableSearchService.get_instance()


@router.get("/search", response_model=TableSearchResponse)
async def search_tables(
    query: str,
    limit: Optional[int] = 10,
    service: TableSearchService = Depends(get_service),
) -> TableSearchResponse:
    """Search for tables matching the query."""
    try:
        result = service.search_tables(query, limit)
        return TableSearchResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=IndexStatsResponse)
async def get_index_stats(
    service: TableSearchService = Depends(get_service),
) -> IndexStatsResponse:
    """Get current index statistics."""
    try:
        stats = service.get_index_stats()
        return IndexStatsResponse(**stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/structure", response_model=DetailedIndexResponse)
async def get_index_structure(
    service: TableSearchService = Depends(get_service),
) -> DetailedIndexResponse:
    """Get detailed information about the index structure."""
    try:
        result = service.get_detailed_index()
        return DetailedIndexResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_index(
    service: TableSearchService = Depends(get_service),
) -> RefreshResponse:
    """Refresh the search index with latest schema."""
    try:
        result = service.refresh_index()
        return RefreshResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
