"""Service implementation for table search operations."""

import logging
import sys
import time
from collections import Counter
from typing import Any, Dict, List, Optional

from fastapi import Depends

from sens.retrieval.token import TokenIndexBuilder

from ...common.errors import ServiceError

# SchemaExtractor no longer needed here for initialization
# from sens.schema import SchemaExtractor


logger = logging.getLogger(__name__)

# Define the schema path constant (consider moving to central config)
SCHEMA_METADATA_PATH = "config/schema_metadata.json"


class TableSearchService:
    """Service for table name search operations.

    Loads the token index from the pre-extracted schema file on initialization.
    """

    _instance: Optional["TableSearchService"] = None
    _is_initialized: bool = False
    _index: Optional[TokenIndexBuilder] = None
    # _schema_extractor: Optional[SchemaExtractor] = None # Removed

    def __init__(self):
        """Initialize the service, loading the token index from schema file."""
        # Skip initialization if an instance already exists
        if self._instance is not None:
            return

        if not self._is_initialized:
            logger.info(
                "Creating new TableSearchService instance and loading token index..."
            )
            try:
                TableSearchService._index = TokenIndexBuilder()
                # Load index directly from the authoritative schema file
                TableSearchService._index.load_from_schema(SCHEMA_METADATA_PATH)
                TableSearchService._is_initialized = True
                TableSearchService._instance = self
                logger.info("TableSearchService initialized successfully.")
            except FileNotFoundError:
                logger.error(
                    f"Schema file not found at {SCHEMA_METADATA_PATH}. Token index could not be built."
                )
                # Allow service to start, but log error. Search will likely fail.
                TableSearchService._is_initialized = (
                    True  # Mark as initialized to prevent re-try loop
                )
                TableSearchService._instance = self
            except Exception as e:
                logger.exception(
                    f"Failed to initialize TableSearchService during index load: {e}"
                )
                # Depending on desired behavior, could re-raise or allow service to start partially.
                # For now, let it start but log the error.
                TableSearchService._is_initialized = True
                TableSearchService._instance = self

    # _initialize_index method is removed as its logic is now in __init__
    # and TokenIndexBuilder.load_from_schema

    def search_tables(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Search for tables matching the query."""
        # Ensure index was loaded
        if (
            not self._index or not self._index.index.table_formats
        ):  # Check if index has tables
            logger.warning("Search attempted but token index is not loaded or empty.")
            raise ServiceError(
                "Token index is not available. Please ensure schema is extracted and service restarted."
            )

        # ... (rest of search_tables remains the same)
        try:
            start_time = time.time()

            # Perform search
            matches = self._index.guess_tables(query)

            # Calculate execution time
            execution_time = (time.time() - start_time) * 1000

            return {
                "query": query,
                "matches": matches[:limit],
                "total_matches": len(matches),
                "execution_time_ms": execution_time,
            }
        except Exception as e:
            logger.error(f"Table search failed: {str(e)}")
            raise ServiceError(f"Search operation failed: {str(e)}")

    def get_index_stats(self) -> Dict[str, Any]:
        """Get current index statistics."""
        if not self._index:  # Check if builder exists
            raise ServiceError("Token index service component not initialized.")
        # Delegate calculation to the TokenIndex model
        return self._index.index.get_stats()

    def get_detailed_index(self) -> Dict[str, Any]:
        """Get detailed information about the index structure."""
        if not self._index:
            raise ServiceError("Token index service component not initialized.")
        try:
            # Delegate calculation to the TokenIndex model
            return self._index.index.get_detailed_structure()
        except Exception as e:
            logger.error(f"Failed to get detailed index: {str(e)}")
            raise ServiceError(f"Failed to get detailed index: {str(e)}")

    def refresh_index(self) -> Dict[str, Any]:
        """Refresh the token index by reloading from the schema file."""
        logger.info("Refreshing token index from schema file...")
        if not self._index:
            raise ServiceError(
                "Token index service component not initialized, cannot refresh."
            )
        try:
            start_time = time.time()
            # Reload the index from the schema file
            self._index.load_from_schema(SCHEMA_METADATA_PATH)
            execution_time = (time.time() - start_time) * 1000
            logger.info(
                f"Token index refreshed successfully in {execution_time:.2f} ms."
            )

            return {
                "status": "success",
                "execution_time_ms": execution_time,
                **self.get_index_stats(),
            }
        except Exception as e:
            logger.exception(f"Index refresh failed: {e}")
            raise ServiceError(f"Index refresh failed: {e}")

    @classmethod
    def get_instance(cls) -> "TableSearchService":
        """Dependency injection method for FastAPI."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
