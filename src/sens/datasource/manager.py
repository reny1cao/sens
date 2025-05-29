"""Manager for handling multiple data sources."""

import asyncio
import shutil
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import aiofiles
import duckdb
from fastapi import UploadFile
import structlog

from sens.settings import get_settings
from sens.schema.schema_extractor import SchemaExtractor
from .models import DataSourceType, DataSourceInfo, SessionInfo, TableInfo

logger = structlog.get_logger(__name__)


class DataSource:
    """Represents a single data source."""
    
    def __init__(self, id: str, type: DataSourceType, config: dict, name: str = ""):
        self.id = id
        self.type = type
        self.config = config
        self.name = name or f"{type.value}_{id[:8]}"
        self.schema_extracted = False
        self.created_at = datetime.utcnow()
        self.schema_context = None
        self._connection = None
    
    def get_connection(self):
        """Get database connection based on source type."""
        if self.type == DataSourceType.UPLOADED_FILE:
            if not self._connection:
                self._connection = duckdb.connect(self.config.get('db_path', ':memory:'))
            return self._connection
        elif self.type == DataSourceType.DEFAULT_POSTGRES:
            # Return connection string for postgres
            return self.config.get('connection_string')
        else:
            raise NotImplementedError(f"Connection for {self.type} not implemented")
    
    def close(self):
        """Close any open connections."""
        if self._connection:
            self._connection.close()
            self._connection = None


class DataSourceManager:
    """Manages multiple data sources and sessions."""
    
    def __init__(self):
        self.sources: Dict[str, DataSource] = {}
        self.sessions: Dict[str, SessionInfo] = {}
        self.settings = get_settings()
        self.temp_dir = Path("/tmp/sens")
        self.temp_dir.mkdir(exist_ok=True)
        self.session_ttl = timedelta(hours=24)
        
        # Initialize default PostgreSQL source
        self._init_default_source()
    
    def _init_default_source(self):
        """Initialize the default PostgreSQL data source."""
        default_source = DataSource(
            id="default",
            type=DataSourceType.DEFAULT_POSTGRES,
            config={
                'connection_string': self.settings.db_url,
                'host': self.settings.db_host,
                'port': self.settings.db_port,
                'database': self.settings.db_name,
                'user': self.settings.db_user,
            },
            name="Default Database"
        )
        self.sources["default"] = default_source
    
    async def create_file_source(
        self,
        session_id: str,
        files: List[UploadFile],
        source_name: Optional[str] = None
    ) -> DataSource:
        """Create a DuckDB data source from uploaded files."""
        if not session_id:
            session_id = str(uuid.uuid4())
        
        source_id = f"upload_{session_id}"
        
        # Create session directory
        session_dir = self.temp_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # Save uploaded files
        file_paths = []
        for file in files:
            file_path = session_dir / file.filename
            async with aiofiles.open(file_path, 'wb') as f:
                content = await file.read()
                await f.write(content)
            file_paths.append(str(file_path))
            logger.info("file_uploaded", path=str(file_path), size=file.size)
        
        # Create DuckDB database
        db_path = session_dir / "data.duckdb"
        conn = duckdb.connect(str(db_path))
        
        try:
            # Load files into DuckDB
            for path in file_paths:
                table_name = Path(path).stem.lower().replace(' ', '_')
                
                if path.endswith('.csv'):
                    conn.execute(f"""
                        CREATE TABLE "{table_name}" AS 
                        SELECT * FROM read_csv_auto('{path}')
                    """)
                elif path.endswith(('.xlsx', '.xls')):
                    # DuckDB requires spatial extension for Excel files
                    conn.execute("INSTALL spatial; LOAD spatial;")
                    conn.execute(f"""
                        CREATE TABLE "{table_name}" AS 
                        SELECT * FROM st_read('{path}')
                    """)
                
                logger.info("table_created", table=table_name, source=path)
        
        finally:
            conn.close()
        
        # Create data source
        source = DataSource(
            id=source_id,
            type=DataSourceType.UPLOADED_FILE,
            config={
                'db_path': str(db_path),
                'file_paths': file_paths,
                'session_dir': str(session_dir)
            },
            name=source_name or f"Uploaded Files ({len(files)})"
        )
        
        self.sources[source_id] = source
        
        # Create session info
        now = datetime.utcnow()
        session_info = SessionInfo(
            session_id=session_id,
            source_id=source_id,
            created_at=now,
            last_accessed=now,
            expires_at=now + self.session_ttl
        )
        self.sessions[session_id] = session_info
        
        # Extract schema asynchronously
        await self._extract_schema(source)
        
        return source
    
    async def _extract_schema(self, source: DataSource):
        """Extract schema for a data source."""
        try:
            if source.type == DataSourceType.UPLOADED_FILE:
                # Use DuckDB's information schema
                conn = source.get_connection()
                
                # Get basic schema info
                tables = conn.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'main'
                """).fetchall()
                
                schema_dict = {"tables": {}}
                
                for (table_name,) in tables:
                    columns = conn.execute(f"""
                        SELECT column_name, data_type 
                        FROM information_schema.columns 
                        WHERE table_name = '{table_name}'
                    """).fetchall()
                    
                    schema_dict["tables"][table_name] = {
                        "columns": [
                            {"name": col[0], "data_type": col[1]} 
                            for col in columns
                        ]
                    }
                
                source.schema_context = schema_dict
                source.schema_extracted = True
                
            elif source.type == DataSourceType.DEFAULT_POSTGRES:
                # Use existing schema extractor
                extractor = SchemaExtractor(
                    db_url=source.config['connection_string']
                )
                schema_dict = await asyncio.to_thread(extractor.extract_schema)
                source.schema_context = schema_dict
                source.schema_extracted = True
                
        except Exception as e:
            logger.error("schema_extraction_failed", source_id=source.id, error=str(e))
            raise
    
    def get_source(self, source_id: str) -> Optional[DataSource]:
        """Get a data source by ID."""
        return self.sources.get(source_id)
    
    def get_session_source(self, session_id: str) -> Optional[DataSource]:
        """Get the data source for a session."""
        if not session_id or session_id not in self.sessions:
            return self.sources.get("default")
        
        session_info = self.sessions[session_id]
        session_info.last_accessed = datetime.utcnow()
        
        return self.sources.get(session_info.source_id)
    
    async def get_table_info(self, source: DataSource) -> List[TableInfo]:
        """Get information about tables in a data source."""
        tables = []
        
        if source.type == DataSourceType.UPLOADED_FILE:
            conn = source.get_connection()
            
            # Get all tables
            table_names = conn.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'main'
            """).fetchall()
            
            for (table_name,) in table_names:
                # Get columns
                columns = conn.execute(f"""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = '{table_name}'
                    ORDER BY ordinal_position
                """).fetchall()
                
                # Get row count
                row_count = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
                
                # Get sample data (first 5 rows)
                sample_data = conn.execute(f'SELECT * FROM "{table_name}" LIMIT 5').fetchdf().to_dict('records')
                
                tables.append(TableInfo(
                    name=table_name,
                    columns=[{"name": col[0], "type": col[1]} for col in columns],
                    row_count=row_count,
                    sample_data=sample_data
                ))
        
        return tables
    
    async def cleanup_expired_sessions(self):
        """Clean up expired sessions and their data."""
        now = datetime.utcnow()
        expired_sessions = []
        
        for session_id, session_info in self.sessions.items():
            if now > session_info.expires_at:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            await self._cleanup_session(session_id)
    
    async def _cleanup_session(self, session_id: str):
        """Clean up a specific session."""
        try:
            session_info = self.sessions.get(session_id)
            if not session_info:
                return
            
            # Close and remove data source
            source = self.sources.get(session_info.source_id)
            if source:
                source.close()
                del self.sources[session_info.source_id]
                
                # Remove files if uploaded
                if source.type == DataSourceType.UPLOADED_FILE:
                    session_dir = Path(source.config.get('session_dir'))
                    if session_dir.exists():
                        shutil.rmtree(session_dir)
            
            # Remove session
            del self.sessions[session_id]
            
            logger.info("session_cleaned_up", session_id=session_id)
            
        except Exception as e:
            logger.error("session_cleanup_failed", session_id=session_id, error=str(e))