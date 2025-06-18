"""Main FastAPI application."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sens.settings import get_settings  # Updated to use new settings module

from .common.logging import RequestLoggingMiddleware, configure_logging
from .routers.agent_stream import router as agent_stream_router  # Clean SSE streaming
from .routers.column_search.router import router as column_search_router
from .routers.datasource import router as datasource_router
from .routers.intent.router import router as intent_router
from .routers.nl2sql import router as nl2sql_router  # Main implementation
from .routers.nl2sql_agent import router as nl2sql_agent_router  # Agent-based with SSE
from .routers.nl2sql_dev import router as nl2sql_dev_router  # Development/mock endpoint
from .routers.nl2sql_session import (
    router as nl2sql_session_router,  # Session-based for uploads
)
from .routers.nl2sql_simple_agent import (
    router as nl2sql_simple_agent_router,  # Simple agent with notes
)
from .routers.retrieval import router as retrieval_router
from .routers.schema import router as schema_router
from .routers.table_search.router import router as table_search_router

# Load environment variables from .env file
load_dotenv()

# Configure logging
configure_logging()
logger = logging.getLogger(__name__)

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
    """
    logger.info("Starting up Sens API...")

    # Initialize default database schema at startup
    try:
        from sens.datasource.manager import DataSourceManager
        from sens.schema.graph import SchemaGraph

        logger.info("Initializing default database schema...")

        # Extract schema from default PostgreSQL database
        datasource_manager = DataSourceManager()
        await datasource_manager.ensure_default_schema_extracted()

        # Verify schema is loaded correctly
        schema_graph = SchemaGraph.get_instance()
        table_count = len(schema_graph._all_tables)
        logger.info(f"Schema initialized with {table_count} tables")

        if table_count < 10:
            logger.warning(
                f"Schema only has {table_count} tables - might be using demo schema instead of real database"
            )
        else:
            # Pre-create the orchestrator with the correct schema loaded
            logger.info(
                "Pre-initializing ChatOrchestrator with financial database schema..."
            )
            from sens.api.routers.nl2sql import get_orchestrator

            _ = get_orchestrator()  # Pre-initialize orchestrator
            logger.info("ChatOrchestrator pre-initialized successfully")

        # Try to build embedding index
        try:
            from sens.retrieval.embedding.search import EmbeddingSearch

            index_dir = settings.index_dir
            index_file = index_dir / "columns.index"

            if not index_file.exists():
                logger.info("Embedding index not found, will build on first query")
                # Don't build at startup due to _ctypes issue
                # Will be built on demand with proper error handling
            else:
                logger.info(f"Embedding index found at {index_file}")

        except Exception as e:
            logger.warning(f"Embedding index check failed: {e}")

    except Exception as e:
        logger.error(f"Failed to initialize schema at startup: {e}")
        # Don't fail startup - schema can be loaded on demand

    # Keep original schema validation for backward compatibility
    schema_path = settings.schema_path
    if schema_path.exists():
        logger.info(f"Demo schema file found at {schema_path}")
    else:
        logger.warning(f"Demo schema file not found at {schema_path}")

    yield

    # Cleanup on shutdown
    logger.info("Shutting down Sens API...")
    # Add any cleanup tasks here


# Set lifespan after configuration
app.router.lifespan_context = lifespan

# Add routers
app.include_router(nl2sql_router, prefix="/api", tags=["nl2sql"])
app.include_router(nl2sql_dev_router, prefix="/api", tags=["nl2sql-dev"])
app.include_router(nl2sql_session_router, prefix="/api", tags=["nl2sql-session"])
app.include_router(nl2sql_agent_router, prefix="/api", tags=["nl2sql-agent"])
app.include_router(
    nl2sql_simple_agent_router, prefix="/api", tags=["nl2sql-simple-agent"]
)
app.include_router(agent_stream_router, prefix="/api", tags=["agent-stream"])
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
