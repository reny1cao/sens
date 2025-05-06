"""Main FastAPI application."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sens.settings import get_settings  # Updated to use new settings module

from .common.logging import RequestLoggingMiddleware, configure_logging
from .routers.column_search.router import router as column_search_router
from .routers.intent.router import router as intent_router
from .routers.retrieval import router as retrieval_router
from .routers.table_search.router import router as table_search_router

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
    # Validate schema file exists
    schema_path = settings.schema_path
    if not schema_path.exists():
        logger.error(f"Schema file not found at {schema_path}")
        raise FileNotFoundError(f"Schema file not found at {schema_path}")

    yield

    # Cleanup on shutdown if needed
    pass


# Set lifespan after configuration
app.router.lifespan_context = lifespan

# Add routers
app.include_router(intent_router, prefix="/intent", tags=["intent"])
app.include_router(table_search_router, prefix="/table-search", tags=["table-search"])
app.include_router(
    column_search_router, prefix="/column-search", tags=["column-search"]
)
app.include_router(retrieval_router, prefix="/retrieval", tags=["retrieval"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
