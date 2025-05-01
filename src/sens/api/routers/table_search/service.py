"""Service implementation for table search operations."""

import logging
import sys
import time
from collections import Counter
from typing import Any, Dict, List, Optional

from fastapi import Depends

from sens.schema import SchemaExtractor
from sens.token_index import TokenIndexBuilder

from ...common.errors import ServiceError

logger = logging.getLogger(__name__)


class TableSearchService:
    """Service for table name search operations."""

    _instance: Optional["TableSearchService"] = None
    _is_initialized: bool = False
    _index: Optional[TokenIndexBuilder] = None
    _schema_extractor: Optional[SchemaExtractor] = None

    def __init__(self):
        """Initialize the service with required components."""
        # Skip initialization if an instance already exists
        if self._instance is not None:
            return

        if not self._is_initialized:
            logger.info("Creating new TableSearchService instance")
            TableSearchService._index = TokenIndexBuilder()
            TableSearchService._schema_extractor = SchemaExtractor()
            self._initialize_index()
            TableSearchService._is_initialized = True
            TableSearchService._instance = self

    def _initialize_index(self) -> None:
        """Initialize the token index with current schema."""
        try:
            logger.info("Initializing table search index")
            schema = self._schema_extractor.extract_and_save()
            table_names = list(schema.tables.keys())
            self._index.build_index(table_names)
            logger.info(f"Index initialized with {len(table_names)} tables")
        except Exception as e:
            logger.error(f"Failed to initialize index: {str(e)}")
            raise ServiceError(f"Index initialization failed: {str(e)}")

    def search_tables(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Search for tables matching the query.

        Args:
            query: The search query string
            limit: Maximum number of results to return

        Returns:
            Dictionary containing search results and metadata

        Raises:
            ServiceError: If search operation fails
        """
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
        """Get current index statistics.

        Returns:
            Dictionary containing index statistics
        """
        return {
            "table_count": len(self._index.index.table_formats),
            "memory_usage_bytes": self._index.index._current_size_bytes,
            "case_formats": {
                format.value: len(
                    [
                        t
                        for t, f in self._index.index.table_formats.items()
                        if f == format
                    ]
                )
                for format in self._index.index.table_formats.values()
            },
        }

    def get_detailed_index(self) -> Dict[str, Any]:
        """Get detailed information about the index structure.

        Returns:
            Dictionary containing detailed index information
        """
        try:
            token_map = self._index.index.token_map
            table_formats = self._index.index.table_formats

            # Calculate token details
            tokens = {}
            for token, tables in token_map.items():
                token_memory = sys.getsizeof(token) + sum(
                    sys.getsizeof(t) for t in tables
                )
                tokens[token] = {
                    "token": token,
                    "tables": list(tables),
                    "frequency": len(tables),
                    "memory_bytes": token_memory,
                }

            # Calculate table tokenization details
            tables = {}
            for table_name, case_format in table_formats.items():
                table_tokens = self._index._tokenize(table_name)
                table_memory = sys.getsizeof(table_name) + sum(
                    sys.getsizeof(t) for t in table_tokens
                )
                tables[table_name] = {
                    "table_name": table_name,
                    "tokens": table_tokens,
                    "case_format": case_format.value,
                    "memory_bytes": table_memory,
                }

            # Find most common tokens
            token_frequencies = Counter(
                {t: len(tables) for t, tables in token_map.items()}
            )
            most_common = [
                tokens[token] for token, _ in token_frequencies.most_common(10)
            ]

            # Calculate memory distribution
            memory_distribution = {
                "tokens": sum(t["memory_bytes"] for t in tokens.values()),
                "tables": sum(t["memory_bytes"] for t in tables.values()),
                "overhead": (sys.getsizeof(token_map) + sys.getsizeof(table_formats)),
            }

            return {
                "total_tables": len(table_formats),
                "total_tokens": len(token_map),
                "total_memory_bytes": self._index.index._current_size_bytes,
                "tokens": tokens,
                "tables": tables,
                "most_common_tokens": most_common,
                "memory_distribution": memory_distribution,
            }
        except Exception as e:
            logger.error(f"Failed to get detailed index: {str(e)}")
            raise ServiceError(f"Failed to get detailed index: {str(e)}")

    def refresh_index(self) -> Dict[str, Any]:
        """Refresh the search index with latest schema.

        Returns:
            Dictionary containing refresh operation results
        """
        try:
            start_time = time.time()
            self._initialize_index()
            execution_time = (time.time() - start_time) * 1000

            return {
                "status": "success",
                "execution_time_ms": execution_time,
                **self.get_index_stats(),
            }
        except Exception as e:
            logger.error(f"Index refresh failed: {str(e)}")
            raise ServiceError(f"Index refresh failed: {str(e)}")

    @classmethod
    def get_instance(cls) -> "TableSearchService":
        """Dependency injection method for FastAPI."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
