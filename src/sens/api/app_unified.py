"""
Unified FastAPI application - cleaner architecture with consolidated endpoints.
"""

from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sens.settings import get_settings

from .common.logging import RequestLoggingMiddleware, configure_logging
from .routers.agent_stream_unified import (
    router as unified_agent_router,  # Unified streaming
)
from .routers.column_search.router import router as column_search_router
from .routers.datasource import router as datasource_router

# Core functionality routers
from .routers.nl2sql_unified import router as nl2sql_router
from .routers.retrieval import router as retrieval_router
from .routers.schema import router as schema_router

# Search routers
from .routers.table_search.router import router as table_search_router

# Load environment variables
load_dotenv()

# Configure logging
configure_logging()
logger = structlog.get_logger(__name__)

# Get settings
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for application startup/shutdown.
    Simplified to focus on essential initialization.
    """
    logger.info("api_startup_started")

    # Register components
    try:
        from sens.registry.register_components import register_default_components

        logger.info("component_registration_started")
        register_default_components()
        logger.info("component_registration_completed")
    except Exception as e:
        logger.error("component_registration_failed", error=str(e))

    # Schema initialization (based on startup mode)
    if getattr(settings, "fast_startup", False):
        logger.info("fast_startup_enabled", message="Schema will be loaded on demand")
    else:
        # Initialize schema at startup
        try:
            from sens.datasource.manager import DataSourceManager

            logger.info("schema_initialization_started")
            datasource_manager = DataSourceManager()
            await datasource_manager.ensure_default_schema_extracted()
            logger.info("schema_initialization_completed")
        except Exception as e:
            logger.warning("schema_initialization_failed", error=str(e))

    yield

    # Cleanup
    logger.info("api_shutdown_completed")


# Create FastAPI app
app = FastAPI(
    title="SENS API (Unified)",
    description="Unified API for semantic database querying with consolidated endpoints",
    version="2.0.0",
    lifespan=lifespan,
)

# Configure middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=settings.cors_methods,
    allow_headers=settings.cors_headers,
)
app.add_middleware(RequestLoggingMiddleware)

# === Core Routers (Consolidated) ===

# Unified agent streaming (replaces agent_stream.py and agent_stream_enhanced.py)
app.include_router(unified_agent_router, prefix="/api", tags=["agent"])

# Core NL2SQL functionality
app.include_router(nl2sql_router, prefix="/api", tags=["nl2sql"])

# Memory management API
from .routers.memory_management import router as memory_router

app.include_router(memory_router, tags=["memory"])

# Knowledge system API
from .routers.knowledge import router as knowledge_router

app.include_router(knowledge_router, tags=["knowledge"])

# Schema and datasource management
app.include_router(datasource_router, prefix="/api", tags=["datasource"])
app.include_router(schema_router, prefix="/api", tags=["schema"])

# Search functionality
app.include_router(table_search_router, prefix="/table-search", tags=["search"])
app.include_router(column_search_router, prefix="/column-search", tags=["search"])
app.include_router(retrieval_router, prefix="/retrieval", tags=["search"])

# === Optional Routers ===

# Evaluation endpoints (if available)
try:
    from .routers.unified_evaluation import router as evaluation_router

    app.include_router(evaluation_router, prefix="/api", tags=["evaluation"])
    logger.info("evaluation_router_loaded")
except ImportError:
    logger.info("evaluation_router_not_available")

# BIRD-SQL-DEV evaluation (if available)
try:
    from .routers.bird_sql_dev_evaluation import router as bird_router

    app.include_router(bird_router, prefix="/api", tags=["evaluation"])
    logger.info("bird_sql_dev_router_loaded")
except ImportError:
    logger.info("bird_sql_dev_router_not_available")


# === Health Check ===


@app.get("/health")
async def health_check():
    """Health check endpoint with basic status information."""

    status = {"status": "healthy", "version": "2.0.0"}

    # Check schema status
    try:
        from sens.schema.graph import SchemaGraph

        schema = SchemaGraph.get_instance()
        status["schema_tables"] = len(schema._all_tables)
    except:
        status["schema_tables"] = 0

    # Check memory status
    try:
        from sens.memory import AgentMemory

        # Just check if we can create an instance
        status["memory_available"] = True
    except:
        status["memory_available"] = False

    return status


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "SENS API (Unified)",
        "version": "2.0.0",
        "description": "Semantic Natural SQL with unified agent architecture",
        "endpoints": {
            "agent_stream": "/api/nl2sql/agent/stream",
            "nl2sql": "/api/nl2sql/query",
            "health": "/health",
            "schema": "/api/schema",
            "search": {
                "tables": "/table-search",
                "columns": "/column-search",
                "retrieval": "/retrieval",
            },
        },
    }
