"""API initialization and configuration."""

from fastapi import FastAPI

from sens.api.embedding_routes import router as embedding_router
from sens.api.token_index_routes import router as token_index_router

app = FastAPI(
    title="Sens API",
    description="Schema-aware natural language search API",
    version="0.1.0",
)

app.include_router(token_index_router)
app.include_router(embedding_router)

__all__ = ["app"]
