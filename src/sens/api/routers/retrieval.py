import logging
from typing import List, Optional, Tuple

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from ...api.routers.table_search.service import TableSearchService
from ...retrieval.embedding.search import EmbeddingSearch
from ...retrieval.models import RetrievedColumn, RetrievedContext

# Import the orchestrator and context model
from ...retrieval.orchestrator import RetrievalOrchestrator

# Direct imports of REAL dependencies - no fallbacks or dummy implementations
from ...retrieval.token import TokenIndex
from ...schema.graph import SchemaGraph

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/retrieve",
    tags=["Retrieval"],
)

# --- Dependency Adapters ---
# These classes adapt the interfaces of the existing search services
# to match the interface expected by RetrievalOrchestrator.


class TokenIndexAdapter:
    """Adapts TableSearchService's table-name search for the Orchestrator."""

    def __init__(self, table_search_service: TableSearchService):
        """Initialize the token index adapter with a table search service.

        Args:
            table_search_service: The service providing access to the token index.
        """
        # Ensure the underlying index builder is available via the service
        if not table_search_service._index:
            logger.error("TokenIndexBuilder not available via TableSearchService.")
            raise RuntimeError(
                "Token index is not available within TableSearchService."
            )
        self._index_builder = table_search_service._index

    def search(self, query: str, k: int) -> List[RetrievedColumn]:
        """Performs table name search and maps results to RetrievedColumn."""
        # Current token search (`guess_tables`) only returns table names.
        # Map these table names to placeholder columns with a default score.
        try:
            table_names: List[str] = self._index_builder.guess_tables(query)
            # Assign a default score for these table-level matches
            results = [
                RetrievedColumn(
                    table_name=name,
                    column_name="<TABLE_MATCH>",  # Indicate this is a table match
                    score=1.0,  # High score for direct table name match? Needs tuning.
                    source="token",
                    metadata={"match_type": "table_name"},
                )
                for name in table_names
            ]
            # Note: `guess_tables` doesn't use `k`. Limit applied later by orchestrator.
            logger.debug(
                f"TokenAdapter found {len(results)} potential table hits for '{query}'."
            )
            return results
        except Exception as e:
            logger.error(
                f"TokenIndexAdapter search failed for query '{query}': {e}",
                exc_info=True,
            )
            return []  # Return empty list on error


class EmbeddingIndexAdapter:
    """Adapts EmbeddingSearch's column search results for the Orchestrator."""

    def __init__(self, embedding_search: EmbeddingSearch):
        """Initialize the embedding index adapter with an embedding search instance.

        Args:
            embedding_search: The embedding search instance to use.
        """
        self._embedding_search = embedding_search

    def search(self, query: str, k: int) -> List[RetrievedColumn]:
        """Performs embedding search and maps results to RetrievedColumn."""
        try:
            # Pass k directly to the embedding search
            results_raw: List[Tuple[str, str, float]] = self._embedding_search.search(
                query, k=k
            )
            results = [
                RetrievedColumn(
                    table_name=table,
                    column_name=column,
                    score=float(score),  # Ensure score is float
                    source="embedding",
                    # metadata field defaults to {}
                )
                for table, column, score in results_raw
            ]
            logger.debug(
                f"EmbeddingAdapter found {len(results)} column hits for '{query}' with k={k}."
            )
            return results
        except FileNotFoundError:
            logger.error("Embedding index file not found during search.", exc_info=True)
            # Allow orchestrator to proceed with potentially only token results
            return []
        except Exception as e:
            logger.error(
                f"EmbeddingIndexAdapter search failed for query '{query}': {e}",
                exc_info=True,
            )
            return []  # Return empty list on error


# --- Dependency Management ---
# Simple module-level caching for dependency instances.
_token_service_instance: Optional[TableSearchService] = None
_embedding_search_instance: Optional[EmbeddingSearch] = None
# SchemaGraph manages its own singleton instance.


async def get_orchestrator() -> RetrievalOrchestrator:
    """Provide a fully initialized RetrievalOrchestrator instance with real dependencies and adapters.

    This FastAPI dependency function initializes dependencies lazily and caches them per process.
    It ensures all required components (token index, embedding search, schema graph) are properly
    initialized before creating the orchestrator.

    Returns:
        A fully initialized RetrievalOrchestrator instance.

    Raises:
        HTTPException: If any required dependency fails to initialize.
    """
    global _token_service_instance, _embedding_search_instance

    try:
        # --- Get/Instantiate Real Dependencies ---

        # SchemaGraph (Singleton via get_instance)
        # Assumes SchemaGraph can find 'config/schema_metadata.json' or is configured
        schema_g = SchemaGraph.get_instance()

        # TokenIndex (via TableSearchService Singleton)
        if _token_service_instance is None:
            logger.info("Initializing TableSearchService singleton for token index.")
            _token_service_instance = TableSearchService.get_instance()
            # Verify successful initialization of the underlying index
            if not _token_service_instance._index:
                logger.error(
                    "TokenIndexBuilder failed to initialize within TableSearchService."
                )
                raise RuntimeError("Token index failed to load.")
        token_service = _token_service_instance

        # EmbeddingSearch (Lazy Init - ensure index loaded)
        if _embedding_search_instance is None:
            logger.info("Initializing EmbeddingSearch instance.")
            # TODO: Configuration for model_name, index_dir should come from settings/env
            _embedding_search_instance = EmbeddingSearch()
            try:
                # Explicitly load index on first init if search doesn't always trigger load
                _embedding_search_instance.load_index()
            except FileNotFoundError as fnf:
                logger.error(
                    f"Embedding index file not found on init: {fnf}. Search will fail."
                )
                # Raise here to prevent API from starting in bad state? Or let search fail?
                # Let's raise for now, as it's likely unusable.
                raise RuntimeError(
                    f"Embedding index data not found at {_embedding_search_instance.index_dir}"
                )
        embedding_search = _embedding_search_instance

        # --- Create Adapters ---
        token_adapter = TokenIndexAdapter(token_service)
        embedding_adapter = EmbeddingIndexAdapter(embedding_search)

        # --- Instantiate Orchestrator ---
        orchestrator = RetrievalOrchestrator(
            token_index=token_adapter,  # Use the adapter
            embedding_index=embedding_adapter,  # Use the adapter
            schema_graph=schema_g,  # Use the real graph
        )
        logger.debug("RetrievalOrchestrator instance created successfully.")
        return orchestrator

    except FileNotFoundError as e:
        # Catch missing schema or embedding index files specifically
        logger.error(
            f"Dependency initialization failed: Required data file not found - {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=503,
            detail=f"Service Unavailable: Required data file missing ({e})",
        )
    except RuntimeError as e:
        # Catch specific runtime errors like failed index loading
        logger.error(f"Dependency initialization failed: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"Service Unavailable: {e}")
    except Exception as e:
        # Catch-all for other unexpected initialization errors
        logger.error(
            f"Failed to create RetrievalOrchestrator dependency: {e}", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error: Could not initialize core components.",
        )


# --- API Endpoint ---


@router.post("/context", response_model=RetrievedContext)
async def get_relevant_schema_context(
    question: str = Body(
        ...,
        embed=True,
        description="The natural language question to retrieve context for.",
    ),
    k: int = Body(
        5,
        embed=True,
        description="The target number of relevant columns to return based on score.",
    ),
    orchestrator: RetrievalOrchestrator = Depends(get_orchestrator),
):
    """Retrieve relevant schema context for a natural language question.

    This endpoint combines results from token-based table search and embedding-based column search
    to return a ranked and deduplicated list of relevant tables and columns.
    """
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    logger.info(f"API received context retrieval request: question='{question}', k={k}")

    try:
        # The injected orchestrator now uses real dependencies via adapters
        context = orchestrator.get_relevant_context(question=question, k=k)
        logger.info(f"Successfully retrieved context for question '{question}'.")
        return context
    except Exception as e:
        # Log the unexpected error at the API boundary if orchestrator doesn't handle it
        logger.error(
            f"API error during context retrieval for question '{question}': {e}",
            exc_info=True,
        )
        # Avoid leaking internal details in the error message
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred during context retrieval.",
        )


# Note: Ensure the paths in the import statements at the top match your actual file locations.
# Ensure the instantiation logic within get_orchestrator matches how your dependencies are created.

# Note: To make this runnable, this router needs to be included in a main FastAPI application instance.
# Example (in e.g., src/sens/api/main.py):
# from fastapi import FastAPI
# from . import retrieval
#
# app = FastAPI()
# app.include_router(retrieval.router)
