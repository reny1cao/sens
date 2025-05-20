"""Enhanced TokenIndexBuilder implementation for efficient schema lookups."""

import json
import logging
import re
from datetime import UTC, datetime
from typing import Dict, List, Optional, Set, Tuple, Union

import structlog

from .builder import TokenIndexBuilder
from .enhanced_models import EnhancedTokenIndex, SchemaItem, TokenMatch
from .models import CaseFormat

log = structlog.get_logger(__name__)


class EnhancedTokenIndexBuilder(TokenIndexBuilder):
    """Builds and maintains a token-based index for efficient schema lookups."""

    def __init__(self):
        """Initialize the enhanced token index builder."""
        super().__init__()
        self.index = EnhancedTokenIndex()  # Override with enhanced index

    def build_index(self, schema_items: List[SchemaItem]) -> None:
        """Build the token index from a list of schema items.

        Args:
            schema_items: List of SchemaItem objects to index
        """
        log.info(
            "enhanced_index_build_start",
            item_count=len(schema_items),
            timestamp=self._get_timestamp(),
        )

        # Reset the index
        self.index = EnhancedTokenIndex()

        # Process tables first to maintain parent references
        tables = [item for item in schema_items if item.item_type == "table"]
        for item in tables:
            self._add_table(item.name)

        # Then process columns
        columns = [item for item in schema_items if item.item_type == "column"]
        for item in columns:
            if item.parent_table:
                self._add_column(item.parent_table, item.name, item.metadata)

        log.info(
            "enhanced_index_build_complete",
            table_count=len(self.index.table_formats),
            column_count=len(self.index.column_metadata),
            timestamp=self._get_timestamp(),
        )

    def _add_column(
        self, table_name: str, column_name: str, metadata: Optional[Dict] = None
    ) -> None:
        """Add a column to the index.

        Args:
            table_name: Name of the parent table
            column_name: Name of the column to add
            metadata: Optional metadata about the column
        """
        tokens = self._tokenize(column_name)

        # Add to enhanced index's column_token_map
        for token in tokens:
            if token not in self.index.column_token_map:
                self.index.column_token_map[token] = set()
            self.index.column_token_map[token].add((table_name, column_name))

        # Store metadata
        self.index.add_column(table_name, column_name, metadata)

        log.debug(
            "column_indexed",
            table=table_name,
            column=column_name,
            tokens=tokens,
            timestamp=self._get_timestamp(),
        )

    def search(self, query: str, k: int = 5) -> List[TokenMatch]:
        """Search for schema items matching the query.

        This method searches both table names and column names, combining and ranking
        the results based on match quality.

        Args:
            query: The search query
            k: Maximum number of results to return

        Returns:
            List of TokenMatch objects, sorted by relevance
        """
        if not query:
            return []

        query = query.lower()
        query_tokens = self._tokenize(query)

        # Get table matches
        table_candidates = self._find_candidates(query_tokens)
        table_matches = self._score_table_matches(table_candidates, query, query_tokens)

        # Get column matches
        column_candidates = self._find_column_candidates(query_tokens)
        column_matches = self._score_column_matches(
            column_candidates, query, query_tokens
        )

        # Combine and rank all matches
        all_matches = table_matches + column_matches
        ranked_matches = sorted(
            all_matches,
            key=lambda x: (x.score, x.token_overlap, x.match_type != "exact"),
            reverse=True,
        )

        return ranked_matches[:k]

    def _find_column_candidates(self, tokens: List[str]) -> Set[Tuple[str, str]]:
        """Find candidate columns matching the tokens.

        Args:
            tokens: List of tokens to match

        Returns:
            Set of (table_name, column_name) tuples
        """
        if not tokens:
            return set()

        # Start with columns matching first token
        candidates = self.index.column_token_map.get(tokens[0].lower(), set())

        # Intersect with other token matches
        for token in tokens[1:]:
            token_matches = self.index.column_token_map.get(token.lower(), set())
            candidates &= token_matches
            if not candidates:
                break

        return candidates

    def _score_table_matches(
        self, candidates: Set[str], query: str, query_tokens: List[str]
    ) -> List[TokenMatch]:
        """Score and convert table candidates to TokenMatch objects.

        Args:
            candidates: Set of candidate table names
            query: Original search query
            query_tokens: Tokenized query

        Returns:
            List of TokenMatch objects for table matches
        """
        matches = []
        query_lower = query.lower()

        for table in candidates:
            table_lower = table.lower()
            table_tokens = set(self._tokenize(table))

            # Calculate match characteristics
            is_exact = table_lower == query_lower
            is_prefix = table_lower.startswith(query_lower)
            token_overlap = len(query_tokens & table_tokens)

            # Calculate score based on match type and token overlap
            if is_exact:
                score = 1.0
                match_type = "exact"
            elif is_prefix:
                score = 0.8
                match_type = "prefix"
            else:
                score = 0.5 + (0.3 * (token_overlap / len(query_tokens)))
                match_type = "partial"

            matches.append(
                TokenMatch(
                    table_name=table,
                    column_name=None,  # Table-level match
                    score=score,
                    match_type=match_type,
                    token_overlap=token_overlap,
                )
            )

        return matches

    def _score_column_matches(
        self, candidates: Set[Tuple[str, str]], query: str, query_tokens: List[str]
    ) -> List[TokenMatch]:
        """Score and convert column candidates to TokenMatch objects.

        Args:
            candidates: Set of (table_name, column_name) tuples
            query: Original search query
            query_tokens: Tokenized query

        Returns:
            List of TokenMatch objects for column matches
        """
        matches = []
        query_lower = query.lower()

        for table_name, column_name in candidates:
            column_lower = column_name.lower()
            column_tokens = set(self._tokenize(column_name))

            # Calculate match characteristics
            is_exact = column_lower == query_lower
            is_prefix = column_lower.startswith(query_lower)
            token_overlap = len(query_tokens & column_tokens)

            # Calculate score based on match type and token overlap
            if is_exact:
                score = 0.95  # Slightly lower than table exact match
                match_type = "exact"
            elif is_prefix:
                score = 0.75
                match_type = "prefix"
            else:
                score = 0.4 + (0.3 * (token_overlap / len(query_tokens)))
                match_type = "partial"

            matches.append(
                TokenMatch(
                    table_name=table_name,
                    column_name=column_name,
                    score=score,
                    match_type=match_type,
                    token_overlap=token_overlap,
                )
            )

        return matches
