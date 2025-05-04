"""Main FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers.column_search.router import router as column_search_router
from .routers.retrieval import router as retrieval_router
from .routers.table_search.router import router as table_search_router

app = FastAPI(
    title="Sens API",
    description="API for Sens project",
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(table_search_router)
app.include_router(column_search_router)
app.include_router(retrieval_router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
