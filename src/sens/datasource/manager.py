"""Manager for handling multiple data sources."""

import asyncio
import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles
import duckdb
import structlog
from fastapi import UploadFile

from sens.caching.factory import create_cache_backend
from sens.caching.manager import CacheManager
from sens.schema.extractors import SchemaExtractor
from sens.schema.extractors.duckdb_extractor import DuckDBExtractor
from sens.schema.extractors.postgresql_extractor import PostgreSQLExtractor
from sens.schema.format_adapter import SchemaFormatAdapter
from sens.schema.unified_schema import DataSourceType as UnifiedDataSourceType
from sens.schema.unified_schema import UnifiedSchema
from sens.settings import get_settings

from .llm_query_suggestions import generate_llm_query_suggestions
from .models import DataSourceInfo, DataSourceType, SessionInfo, TableInfo
from .query_suggestions import generate_query_suggestions
from .storage import storage_manager

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
        self.unified_schema: Optional[UnifiedSchema] = None
        self._connection = None

    def get_connection(self):
        """Get database connection based on source type."""
        if self.type == DataSourceType.UPLOADED_FILE:
            if not self._connection:
                self._connection = duckdb.connect(
                    self.config.get("db_path", ":memory:")
                )
            return self._connection
        elif self.type == DataSourceType.DEFAULT_POSTGRES:
            # Return connection string for postgres
            return self.config.get("connection_string")
        else:
            raise NotImplementedError(f"Connection for {self.type} not implemented")

    def close(self):
        """Close any open connections."""
        if self._connection:
            self._connection.close()
            self._connection = None


class DataSourceManager:
    """Manages multiple data sources and sessions."""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DataSourceManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if DataSourceManager._initialized:
            return

        logger.info("datasource_manager_init", instance_id=id(self))

        self.sources: Dict[str, DataSource] = {}
        self.sessions: Dict[str, SessionInfo] = {}
        self.settings = get_settings()
        self.temp_dir = Path("/tmp/sens")
        self.temp_dir.mkdir(exist_ok=True)
        self.session_ttl = timedelta(hours=24)

        # Initialize cache manager
        cache_backend = create_cache_backend()
        self.cache_manager = CacheManager(backend=cache_backend)

        # Initialize default PostgreSQL source
        self._init_default_source()

        # Schedule schema extraction for default database
        self._default_schema_extracted = False

        DataSourceManager._initialized = True

    def _init_default_source(self):
        """Initialize the default PostgreSQL data source."""
        default_source = DataSource(
            id="default",
            type=DataSourceType.DEFAULT_POSTGRES,
            config={
                "connection_string": self.settings.db_url,
                "host": self.settings.db_host,
                "port": self.settings.db_port,
                "database": self.settings.db_name,
                "user": self.settings.db_user,
            },
            name="Default Database",
        )
        self.sources["default"] = default_source

    async def ensure_default_schema_extracted(self):
        """Ensure the default database schema is extracted."""
        # Check if schema is already extracted AND SchemaGraph has the correct schema
        if self._default_schema_extracted:
            # Verify SchemaGraph has the financial database schema
            from sens.schema.graph import SchemaGraph

            schema_graph = SchemaGraph.get_instance()
            if len(schema_graph._all_tables) > 10:  # Financial DB has 57 tables
                return
            else:
                logger.info(
                    "schema_graph_has_demo_schema_reextracting",
                    current_table_count=len(schema_graph._all_tables),
                )

        default_source = self.sources.get("default")
        if not default_source:
            return

        try:
            # Import cache utilities
            from sens.schema.cache_utils import SchemaCache

            # Generate cache key with version
            db_config = {
                "host": self.settings.db_host,
                "port": self.settings.db_port,
                "database": self.settings.db_name,
                "user": self.settings.db_user,
            }
            cache_key = SchemaCache.get_cache_key("default", db_config)
            cached_schema = await self.cache_manager.get(cache_key)

            if cached_schema and SchemaCache.validate_cached_schema(cached_schema):
                # Check if schema needs refresh
                if not await SchemaCache.should_refresh_schema(
                    cached_schema, max_age_hours=24
                ):
                    default_source.unified_schema = cached_schema
                    default_source.schema_extracted = True
                    self._default_schema_extracted = True
                    logger.info(
                        "default_schema_loaded_from_cache",
                        table_count=len(cached_schema.tables),
                        extracted_at=cached_schema.extracted_at,
                    )
                    # Initialize indexes with cached schema
                    await self._initialize_indexes_with_schema(cached_schema)
                    return
                else:
                    logger.info("schema_cache_expired_will_refresh")

            # Extract schema
            logger.info("extracting_default_database_schema")
            await self._extract_schema(default_source)

            # Cache the schema for 24 hours
            if default_source.unified_schema:
                await self.cache_manager.set(
                    cache_key, default_source.unified_schema, ttl=timedelta(hours=24)
                )

                # Initialize indexes with the extracted schema
                await self._initialize_indexes_with_schema(
                    default_source.unified_schema
                )

            self._default_schema_extracted = True
            logger.info("default_schema_extracted_and_cached")

        except Exception as e:
            logger.error("default_schema_extraction_failed", error=str(e))
            # Don't fail initialization if schema extraction fails

    async def create_file_source(
        self,
        session_id: str,
        files: List[UploadFile],
        source_name: Optional[str] = None,
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
            async with aiofiles.open(file_path, "wb") as f:
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
                table_name = Path(path).stem.lower().replace(" ", "_")

                # Check if table already exists
                existing_tables = conn.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'main' AND table_name = ?
                """,
                    [table_name],
                ).fetchall()

                if existing_tables:
                    # Drop existing table first
                    conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
                    logger.info("dropped_existing_table", table=table_name)

                if path.endswith(".csv"):
                    conn.execute(
                        f"""
                        CREATE TABLE "{table_name}" AS
                        SELECT * FROM read_csv_auto('{path}')
                    """
                    )
                elif path.endswith((".xlsx", ".xls")):
                    # DuckDB requires spatial extension for Excel files
                    conn.execute("INSTALL spatial; LOAD spatial;")
                    conn.execute(
                        f"""
                        CREATE TABLE "{table_name}" AS
                        SELECT * FROM st_read('{path}')
                    """
                    )

                logger.info("table_created", table=table_name, source=path)

        finally:
            conn.close()

        # Create data source
        source = DataSource(
            id=source_id,
            type=DataSourceType.UPLOADED_FILE,
            config={
                "db_path": str(db_path),
                "file_paths": file_paths,
                "session_dir": str(session_dir),
            },
            name=source_name or f"Uploaded Files ({len(files)})",
        )

        self.sources[source_id] = source

        # Create session info
        now = datetime.utcnow()
        session_info = SessionInfo(
            session_id=session_id,
            source_id=source_id,
            created_at=now,
            last_accessed=now,
            expires_at=now + self.session_ttl,
        )
        self.sessions[session_id] = session_info

        # Extract schema asynchronously
        await self._extract_schema(source)

        return source

    async def _extract_schema(self, source: DataSource):
        """Extract schema for a data source using unified extractors."""
        try:
            extractor: Optional[SchemaExtractor] = None

            if source.type == DataSourceType.UPLOADED_FILE:
                # Use DuckDB extractor
                conn = source.get_connection()
                extractor = DuckDBExtractor(
                    connection=conn,
                    source_id=source.id,
                    database_name=source.name,
                    include_sample_data=True,
                    sample_rows=5,
                )

            elif source.type == DataSourceType.DEFAULT_POSTGRES:
                # Use PostgreSQL extractor
                extractor = PostgreSQLExtractor(
                    db_url=source.config["connection_string"],
                    source_id=source.id,
                    schema_name="public",
                    include_sample_data=True,
                    sample_rows=5,
                )

            if extractor:
                # Extract schema using unified extractor
                source.unified_schema = await extractor.extract_with_timing()
                source.schema_extracted = True

                logger.info(
                    "schema_extracted",
                    source_id=source.id,
                    source_type=source.type.value,
                    table_count=len(source.unified_schema.tables),
                    duration_ms=source.unified_schema.extraction_duration_ms,
                )
            else:
                raise ValueError(
                    f"No extractor available for source type: {source.type}"
                )

        except Exception as e:
            logger.error("schema_extraction_failed", source_id=source.id, error=str(e))
            raise

    def get_source(self, source_id: str) -> Optional[DataSource]:
        """Get a data source by ID."""
        source = self.sources.get(source_id)
        if source and source_id == "default":
            logger.info(
                "get_source_default",
                has_unified_schema=bool(source.unified_schema),
                schema_extracted=source.schema_extracted,
                table_count=(
                    len(source.unified_schema.tables) if source.unified_schema else 0
                ),
            )
        return source

    def get_session_source(self, session_id: str) -> Optional[DataSource]:
        """Get the data source for a session."""
        if not session_id or session_id not in self.sessions:
            # Don't return default source if session not found
            return None

        session_info = self.sessions[session_id]
        session_info.last_accessed = datetime.utcnow()

        return self.sources.get(session_info.source_id)

    async def get_table_info(self, source: DataSource) -> List[TableInfo]:
        """Get information about tables in a data source."""
        if not source.unified_schema:
            await self._extract_schema(source)

        # Convert from UnifiedSchema to legacy TableInfo format
        tables = []
        for table in source.unified_schema.tables:
            tables.append(
                TableInfo(
                    name=table.name,
                    columns=[
                        {"name": col.name, "type": col.data_type.value}
                        for col in table.columns
                    ],
                    row_count=table.row_count,
                    sample_data=table.sample_data,
                )
            )

        return tables

    async def get_query_suggestions(self, source: DataSource) -> List[str]:
        """Get query suggestions for a data source with caching."""
        if not source.unified_schema:
            logger.info("no_unified_schema_extracting", source_id=source.id)
            await self._extract_schema(source)

        # Generate cache key based on source ID and schema structure
        # We'll use table names and column counts as a simple schema fingerprint
        schema_fingerprint = {
            "source_id": source.id,
            "tables": [
                {
                    "name": table.name,
                    "column_count": len(table.columns),
                    "row_count": table.row_count,
                }
                for table in source.unified_schema.tables
            ],
        }

        cache_key = self.cache_manager.generate_key(
            "query_suggestions", source.id, schema_fingerprint=schema_fingerprint
        )

        # Try to get from cache first
        cached_suggestions = await self.cache_manager.get(cache_key)
        if cached_suggestions is not None:
            logger.info("query_suggestions_cache_hit", source_id=source.id)
            return cached_suggestions

        logger.info("query_suggestions_cache_miss", source_id=source.id)

        # Get sample data from first table if available
        sample_data = None
        if source.unified_schema.tables:
            first_table = source.unified_schema.tables[0]
            sample_data = first_table.sample_data

        try:
            # Try to use LLM-powered suggestions for better insights
            suggestions = await generate_llm_query_suggestions(
                source.unified_schema, sample_data, num_suggestions=10
            )
            logger.info("llm_suggestions_generated", count=len(suggestions))

            # Cache the suggestions for 1 hour
            await self.cache_manager.set(cache_key, suggestions, ttl=timedelta(hours=1))

            return suggestions
        except Exception as e:
            logger.warning("llm_suggestions_failed", error=str(e))
            # Fall back to pattern-based suggestions
            suggestions = generate_query_suggestions(source.unified_schema, sample_data)

            # Cache even the fallback suggestions
            await self.cache_manager.set(
                cache_key, suggestions, ttl=timedelta(minutes=30)
            )

            return suggestions

    async def refresh_query_suggestions(self, source: DataSource) -> List[str]:
        """Force refresh query suggestions for a data source."""
        # Clear cache for this source
        schema_fingerprint = {
            "source_id": source.id,
            "tables": (
                [
                    {
                        "name": table.name,
                        "column_count": len(table.columns),
                        "row_count": table.row_count,
                    }
                    for table in source.unified_schema.tables
                ]
                if source.unified_schema
                else []
            ),
        }

        cache_key = self.cache_manager.generate_key(
            "query_suggestions", source.id, schema_fingerprint=schema_fingerprint
        )

        # Clear the cache
        await self.cache_manager.delete(cache_key)
        logger.info("query_suggestions_cache_cleared", source_id=source.id)

        # Regenerate suggestions
        return await self.get_query_suggestions(source)

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
                    session_dir = Path(source.config.get("session_dir"))
                    if session_dir.exists():
                        shutil.rmtree(session_dir)

            # Remove session
            del self.sessions[session_id]

            logger.info("session_cleaned_up", session_id=session_id)

        except Exception as e:
            logger.error("session_cleanup_failed", session_id=session_id, error=str(e))

    async def _initialize_indexes_with_schema(self, schema: UnifiedSchema):
        """Initialize retrieval indexes with the provided schema.

        This ensures that token and embedding search can find the default database schema.
        """
        try:
            # Import here to avoid circular dependency
            import json
            import tempfile

            from sens.retrieval.embedding.search import EmbeddingSearch
            from sens.schema.format_adapter import SchemaFormatAdapter
            from sens.schema.graph import SchemaGraph

            logger.info(
                "initializing_indexes_with_schema", table_count=len(schema.tables)
            )

            # Convert UnifiedSchema to legacy format for SchemaGraph
            # We need to create a temporary schema file that matches the expected format
            schema_data = {
                "tables": {},
                "relationships": [],
                "metadata": {
                    "source_type": schema.source_type.value,
                    "source_id": schema.source_id,
                    "database_name": schema.database_name,
                    "schema_name": schema.schema_name,
                },
            }

            # Convert tables
            for table in schema.tables:
                table_data = {
                    "name": table.name,
                    "columns": [],
                    "primary_keys": table.primary_keys,
                    "row_count": table.row_count,
                    "description": table.description,
                }

                # Convert columns
                for col in table.columns:
                    col_data = {
                        "name": col.name,
                        "data_type": col.data_type.value,
                        "is_nullable": col.is_nullable,
                        "is_primary_key": col.is_primary_key,
                        "is_foreign_key": col.is_foreign_key,
                        "is_unique": col.is_unique,
                        "description": col.description,
                        "default_value": col.default_value,
                    }
                    table_data["columns"].append(col_data)

                schema_data["tables"][table.name] = table_data

            # Convert foreign keys
            for fk in schema.get_foreign_keys():
                fk_data = {
                    "from_table": fk.from_table,
                    "from_columns": fk.from_columns,
                    "to_table": fk.to_table,
                    "to_columns": fk.to_columns,
                    "constraint_name": fk.constraint_name,
                }
                schema_data["relationships"].append(fk_data)

            # Save to temporary file for SchemaGraph
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                json.dump(schema_data, f, indent=2)
                temp_schema_path = f.name

            try:
                # Re-initialize SchemaGraph with the default database schema
                SchemaGraph.reset_instance()
                schema_graph = SchemaGraph.get_instance(schema_path=temp_schema_path)
                logger.info(
                    "schema_graph_initialized_with_default_db",
                    table_count=len(schema_graph._all_tables),
                )

                # Reset the orchestrator so it picks up the new schema
                from sens.api.routers.nl2sql import reset_orchestrator

                reset_orchestrator()
                logger.info("orchestrator_reset_after_schema_update")

                # Build embedding index if needed
                if self.settings.index_dir.exists():
                    index_file = self.settings.index_dir / "columns.index"
                    if not index_file.exists():
                        try:
                            logger.info("building_embedding_index_for_default_db")
                            embedding_search = EmbeddingSearch(
                                index_dir=str(self.settings.index_dir)
                            )
                            embedding_search.build_index(temp_schema_path)
                            logger.info("embedding_index_built_successfully")
                        except Exception as e:
                            logger.warning(
                                "embedding_index_build_failed_continuing", error=str(e)
                            )
                            # Continue without embedding index - token search will still work

            finally:
                # Clean up temporary file
                import os

                if os.path.exists(temp_schema_path):
                    os.unlink(temp_schema_path)

        except Exception as e:
            logger.error("index_initialization_failed", error=str(e))
            # Don't fail if index initialization fails - queries might still work with fallback
