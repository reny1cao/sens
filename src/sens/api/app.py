"""Main FastAPI application."""

from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sens.settings import get_settings  # Updated to use new settings module

from .common.logging import RequestLoggingMiddleware, configure_logging
from .routers.agent_stream import router as agent_stream_router  # Clean SSE streaming
from .routers.column_search.router import router as column_search_router
from .routers.datasource import router as datasource_router
from .routers.intent.router import router as intent_router

# Unified NL2SQL router (replaces all legacy nl2sql routers)
from .routers.nl2sql_unified import router as nl2sql_unified_router
from .routers.retrieval import router as retrieval_router
from .routers.schema import router as schema_router
from .routers.table_search.router import router as table_search_router

# Load environment variables from .env file
load_dotenv()

# Configure logging
configure_logging()
logger = structlog.get_logger(__name__)

# Get settings once at module level
settings = get_settings()

# Initialize FastAPI app
app = FastAPI(
    title="Sens API",
    description="API for semantic database querying",
    version="0.1.0",
)

# Configure middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=settings.cors_methods,
    allow_headers=settings.cors_headers,
)
app.add_middleware(RequestLoggingMiddleware)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI application.

    Handles startup and shutdown tasks:
    - Validates required environment variables
    - Ensures schema file exists
    - Initializes singletons
    - Validates embedding index
    - Registers components in the registry
    """
    logger.info("api_startup_started")

    # Register default components
    try:
        from sens.registry.register_components import register_default_components

        logger.info("component_registration_started")
        register_default_components()
        logger.info("component_registration_completed")
    except Exception as e:
        logger.error("component_registration_failed", error=str(e), exc_info=True)

    # Check startup mode
    fast_startup = settings.fast_startup if hasattr(settings, "fast_startup") else False

    if fast_startup:
        logger.info("fast_startup_enabled")

        # Optional: Schedule background schema loading
        if settings.preload_schema_background:
            import asyncio

            from sens.datasource.manager import DataSourceManager

            async def background_schema_load():
                try:
                    logger.info("background_schema_extraction_started")
                    datasource_manager = DataSourceManager()
                    await datasource_manager.ensure_default_schema_extracted()
                    logger.info("background_schema_extraction_completed")
                except Exception as e:
                    logger.error("background_schema_extraction_failed", error=str(e))

            # Start background task
            asyncio.create_task(background_schema_load())
    else:
        # Original startup behavior
        # Initialize default database schema at startup
        try:
            from sens.datasource.manager import DataSourceManager
            from sens.schema.graph import SchemaGraph

            logger.info("schema_initialization_started")

            # Extract schema from default PostgreSQL database
            datasource_manager = DataSourceManager()
            await datasource_manager.ensure_default_schema_extracted()

            # Verify schema is loaded correctly
            schema_graph = SchemaGraph.get_instance()
            table_count = len(schema_graph._all_tables)
            logger.info("schema_initialized", table_count=table_count)

            if table_count < 10:
                logger.warning(
                    "schema_table_count_low",
                    table_count=table_count,
                    message="might be using demo schema instead of real database",
                )
            else:
                # Schema loaded successfully
                logger.info("schema_loaded_successfully", table_count=table_count)

            # Try to build embedding index
            try:
                from sens.retrieval.embedding.search import EmbeddingSearch

                index_dir = settings.index_dir
                index_file = index_dir / "columns.index"

                if not index_file.exists():
                    logger.info("embedding_index_not_found")
                    # Don't build at startup due to _ctypes issue
                    # Will be built on demand with proper error handling
                else:
                    logger.info("embedding_index_found", path=str(index_file))

            except Exception as e:
                logger.warning("embedding_index_check_failed", error=str(e))

        except Exception as e:
            logger.error("schema_initialization_failed", error=str(e))
            # Don't fail startup - schema can be loaded on demand

    # Keep original schema validation for backward compatibility
    schema_path = settings.schema_path
    if schema_path.exists():
        logger.info("demo_schema_found", path=str(schema_path))
    else:
        logger.warning("demo_schema_not_found", path=str(schema_path))

    yield

    # Cleanup on shutdown
    logger.info("api_shutdown_started")
    # Add any cleanup tasks here


# Set lifespan after configuration
app.router.lifespan_context = lifespan

# Add routers
app.include_router(
    nl2sql_unified_router, prefix="/api", tags=["nl2sql"]
)  # Unified NL2SQL router
app.include_router(
    agent_stream_router, prefix="/api", tags=["agent-stream"]
)  # Clean SSE streaming
app.include_router(intent_router, prefix="/intent", tags=["intent"])
app.include_router(table_search_router, prefix="/table-search", tags=["table-search"])
app.include_router(
    column_search_router, prefix="/column-search", tags=["column-search"]
)
app.include_router(retrieval_router, prefix="/retrieval", tags=["retrieval"])
app.include_router(datasource_router, prefix="/api", tags=["datasource"])
app.include_router(schema_router, prefix="/api", tags=["schema"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
