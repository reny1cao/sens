"""Main FastAPI application."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sens.config import settings  # Updated to use new unified settings

from .common.logging import RequestLoggingMiddleware, configure_logging
from .routers.column_search.router import router as column_search_router
from .routers.intent.router import router as intent_router
from .routers.retrieval import router as retrieval_router
from .routers.table_search.router import router as table_search_router

# Configure logging
configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI application.

    Handles startup and shutdown tasks:
    - Validates required environment variables
    - Ensures schema file exists
    - Initializes singletons
    - Validates embedding index
    """
    # Startup
    try:
        logger.info("Starting application...")

        # Validate schema file
        if not settings.schema_path.exists():
            raise RuntimeError(f"Schema file not found at {settings.schema_path}")
        logger.info(f"Found schema file at {settings.schema_path}")

        # Ensure index directory exists
        settings.index_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Using index directory: {settings.index_dir}")

        # Initialize singletons and validate dependencies
        from sens.api.routers.table_search.service import TableSearchService
        from sens.retrieval.embedding import EmbeddingSearch

        # Initialize TableSearchService
        logger.info("Initializing TableSearchService...")
        table_service = TableSearchService.get_instance()
        if not table_service._index:
            raise RuntimeError("Failed to initialize TokenIndexBuilder")

        # Initialize EmbeddingSearch
        logger.info("Initializing EmbeddingSearch...")
        embedding_search = EmbeddingSearch(index_dir=str(settings.index_dir))
        try:
            embedding_search.load_index()
        except FileNotFoundError:
            logger.warning(
                f"Embedding index not found at {settings.index_dir}. "
                "Search functionality will be limited."
            )

        logger.info("Application startup complete.")
        yield

    except Exception as e:
        logger.error(f"Application startup failed: {e}")
        raise

    # Shutdown
    logger.info("Shutting down application...")


# Create FastAPI application
app = FastAPI(
    title="Sens API",
    description="API for Sens project",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=settings.cors_methods,
    allow_headers=settings.cors_headers,
)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Include routers
app.include_router(table_search_router)
app.include_router(column_search_router)
app.include_router(retrieval_router)
app.include_router(intent_router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
