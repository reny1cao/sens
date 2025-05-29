"""API routes for data source management."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, File, UploadFile, Header, HTTPException, Depends
from fastapi.responses import JSONResponse

import structlog

from sens.datasource import DataSourceManager, DataSourceType
from sens.datasource.models import DataSourceResponse, TableInfo
from sens.settings import Settings, get_settings

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/datasource", tags=["datasource"])


# Global data source manager instance
_datasource_manager: Optional[DataSourceManager] = None


def get_datasource_manager() -> DataSourceManager:
    """Get or create the global data source manager."""
    global _datasource_manager
    if _datasource_manager is None:
        _datasource_manager = DataSourceManager()
    return _datasource_manager


@router.post("/upload", response_model=DataSourceResponse)
async def upload_files(
    files: List[UploadFile] = File(...),
    source_name: Optional[str] = None,
    session_id: Optional[str] = Header(None, alias="X-Session-Id"),
    datasource_manager: DataSourceManager = Depends(get_datasource_manager)
) -> DataSourceResponse:
    """Upload CSV/Excel files and create a new data source."""
    
    # Generate session ID if not provided
    if not session_id:
        session_id = str(uuid.uuid4())
    
    logger.info("uploading_files", 
                session_id=session_id, 
                file_count=len(files),
                files=[f.filename for f in files])
    
    try:
        # Validate files
        allowed_extensions = {'.csv', '.xlsx', '.xls'}
        for file in files:
            if not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
                raise HTTPException(
                    status_code=400,
                    detail=f"File {file.filename} has unsupported extension. Allowed: {allowed_extensions}"
                )
            
            # Check file size (100MB limit)
            if file.size and file.size > 100 * 1024 * 1024:
                raise HTTPException(
                    status_code=400,
                    detail=f"File {file.filename} exceeds 100MB size limit"
                )
        
        # Create data source from files
        source = await datasource_manager.create_file_source(
            session_id=session_id,
            files=files,
            source_name=source_name
        )
        
        # Get table information
        tables = await datasource_manager.get_table_info(source)
        
        # Calculate total rows
        total_rows = sum(table.row_count for table in tables)
        
        return DataSourceResponse(
            session_id=session_id,
            source_id=source.id,
            type=source.type,
            name=source.name,
            tables=tables,
            total_rows=total_rows,
            message=f"Successfully uploaded {len(files)} file(s) with {len(tables)} table(s)"
        )
        
    except Exception as e:
        logger.error("file_upload_failed", 
                    session_id=session_id, 
                    error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}", response_model=DataSourceResponse)
async def get_session_info(
    session_id: str,
    datasource_manager: DataSourceManager = Depends(get_datasource_manager)
) -> DataSourceResponse:
    """Get information about the data source for a session."""
    
    source = datasource_manager.get_session_source(session_id)
    if not source:
        raise HTTPException(status_code=404, detail="Session not found")
    
    tables = await datasource_manager.get_table_info(source)
    total_rows = sum(table.row_count for table in tables)
    
    return DataSourceResponse(
        session_id=session_id,
        source_id=source.id,
        type=source.type,
        name=source.name,
        tables=tables,
        total_rows=total_rows
    )


@router.get("/preview/{table_name}")
async def preview_table(
    table_name: str,
    session_id: str = Header(..., alias="X-Session-Id"),
    limit: int = 100,
    datasource_manager: DataSourceManager = Depends(get_datasource_manager)
):
    """Preview data from a specific table."""
    
    source = datasource_manager.get_session_source(session_id)
    if not source:
        raise HTTPException(status_code=404, detail="Session not found")
    
    try:
        if source.type == DataSourceType.UPLOADED_FILE:
            conn = source.get_connection()
            
            # Check if table exists
            tables = conn.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'main' AND table_name = ?
            """, [table_name]).fetchall()
            
            if not tables:
                raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")
            
            # Get preview data
            result = conn.execute(f'SELECT * FROM "{table_name}" LIMIT ?', [limit])
            
            columns = [desc[0] for desc in result.description]
            rows = result.fetchall()
            
            # Convert to list of dicts
            data = [dict(zip(columns, row)) for row in rows]
            
            return {
                "table_name": table_name,
                "columns": columns,
                "row_count": len(data),
                "data": data
            }
        else:
            raise HTTPException(status_code=400, detail="Preview only available for uploaded files")
            
    except Exception as e:
        logger.error("table_preview_failed", 
                    session_id=session_id,
                    table=table_name,
                    error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/session/{session_id}")
async def delete_session(
    session_id: str,
    datasource_manager: DataSourceManager = Depends(get_datasource_manager)
):
    """Delete a session and its associated data."""
    
    if session_id not in datasource_manager.sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    try:
        await datasource_manager._cleanup_session(session_id)
        return {"message": f"Session {session_id} deleted successfully"}
    except Exception as e:
        logger.error("session_deletion_failed", 
                    session_id=session_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sources")
async def list_sources(
    datasource_manager: DataSourceManager = Depends(get_datasource_manager)
):
    """List all available data sources."""
    
    sources = []
    for source_id, source in datasource_manager.sources.items():
        sources.append({
            "id": source.id,
            "name": source.name,
            "type": source.type.value,
            "created_at": source.created_at.isoformat(),
            "schema_extracted": source.schema_extracted
        })
    
    return {"sources": sources}