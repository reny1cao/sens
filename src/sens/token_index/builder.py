"""TokenIndexBuilder implementation for efficient table name lookups."""

import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import List, Set

from .models import CaseFormat, TokenIndex


class TokenIndexBuilder:
    """Builds and maintains a token-based index for efficient table name lookups."""

    def __init__(self):
        """Initialize the token index builder."""
        self.index = TokenIndex()
        self._logger = self._setup_logger()

    def build_index(self, table_names: List[str]) -> None:
        """Build the token index from a list of table names.

        Args:
            table_names: List of table names to index
        """
        self._logger.info(
            json.dumps(
                {
                    "event": "build_index_start",
                    "table_count": len(table_names),
                    "timestamp": self._get_timestamp(),
                }
            )
        )

        for table_name in table_names:
            self._add_table(table_name)

        self._logger.info(
            json.dumps(
                {
                    "event": "build_index_complete",
                    "final_memory": self.index._current_size_bytes,
                    "timestamp": self._get_timestamp(),
                }
            )
        )

    def guess_tables(self, partial_name: str) -> List[str]:
        """Find table names matching the partial name.

        Args:
            partial_name: Partial table name to match against

        Returns:
            List of matching table names, sorted by relevance
        """
        if not partial_name:
            return []

        # Convert query to lowercase for case-insensitive matching
        partial_name = partial_name.lower()
        tokens = self._tokenize(partial_name)
        candidates = self._find_candidates(tokens)
        return self._rank_candidates(candidates, partial_name)

    def _add_table(self, table_name: str) -> None:
        """Add a table name to the index.

        Args:
            table_name: Name of the table to add
        """
        case_format = self._detect_case_format(table_name)
        tokens = self._tokenize(table_name)

        # Calculate memory impact before adding
        new_memory = sum(sys.getsizeof(token) for token in tokens)
        new_memory += sys.getsizeof(table_name)

        if self.index._current_size_bytes + new_memory > TokenIndex.MAX_MEMORY_BYTES:
            self._logger.warning(
                json.dumps(
                    {
                        "event": "memory_limit_reached",
                        "table_name": table_name,
                        "current_memory": self.index._current_size_bytes,
                        "timestamp": self._get_timestamp(),
                    }
                )
            )
            return

        # Add tokens to index
        for token in tokens:
            if token not in self.index.token_map:
                self.index.token_map[token] = set()
            self.index.token_map[token].add(table_name)

        self.index.table_formats[table_name] = case_format
        self.index._current_size_bytes += new_memory

        self._log_index_update(table_name, tokens)

    def _tokenize(self, name: str) -> List[str]:
        """Tokenize a name into searchable parts.

        Args:
            name: String to tokenize

        Returns:
            List of normalized tokens
        """
        if not name:
            return []

        # First handle camelCase by inserting spaces before capitals
        # Insert space before capitals that are:
        # 1. Not at the start of the string
        # 2. Not preceded by another capital (handles acronyms like UUID)
        name = re.sub(r"(?<!^)(?<![\W_])(?=[A-Z])", " ", name)

        # Now split by common delimiters and whitespace
        tokens = re.split(r"[-_\s]+", name)

        # Convert to lowercase and filter empty tokens
        tokens = [token.lower() for token in tokens if token]

        # Filter tokens by length
        return [t for t in tokens if len(t) <= TokenIndex.MAX_TOKEN_LENGTH]

    def _detect_case_format(self, name: str) -> CaseFormat:
        """Detect the case format of a name.

        Args:
            name: String to analyze

        Returns:
            Detected CaseFormat
        """
        if "_" in name:
            return CaseFormat.SNAKE
        if "-" in name:
            return CaseFormat.KEBAB
        if re.search(r"[A-Z]", name):
            return CaseFormat.CAMEL
        return CaseFormat.SNAKE  # Default to snake_case

    def _find_candidates(self, tokens: List[str]) -> Set[str]:
        """Find candidate table names matching the tokens.

        Args:
            tokens: List of tokens to match

        Returns:
            Set of matching table names
        """
        if not tokens:
            return set()

        # Start with tables matching first token
        candidates = self.index.token_map.get(tokens[0].lower(), set())

        # Intersect with other token matches
        for token in tokens[1:]:
            token_matches = self.index.token_map.get(token.lower(), set())
            candidates &= token_matches
            if not candidates:
                break

        return candidates

    def _rank_candidates(self, candidates: Set[str], query: str) -> List[str]:
        """Rank candidate matches by relevance.

        Args:
            candidates: Set of candidate table names
            query: Original search query

        Returns:
            Sorted list of candidates
        """
        # Simple ranking based on:
        # 1. Exact prefix match
        # 2. Contains all query tokens
        # 3. Alphabetical order
        query_lower = query.lower()
        query_tokens = set(self._tokenize(query))

        def rank_key(table: str) -> tuple:
            table_lower = table.lower()
            table_tokens = set(self._tokenize(table))
            prefix_match = table_lower.startswith(query_lower)
            token_overlap = len(query_tokens & table_tokens)
            return (-prefix_match, -token_overlap, table)

        return sorted(candidates, key=rank_key)

    def _setup_logger(self) -> logging.Logger:
        """Setup structured JSON logging.

        Returns:
            Configured logger instance
        """
        logger = logging.getLogger("token_index")
        logger.setLevel(logging.INFO)

        # Add console handler if none exists
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(handler)

        return logger

    def _log_index_update(self, table_name: str, tokens: List[str]) -> None:
        """Log index updates in structured JSON format.

        Args:
            table_name: Name of table being added
            tokens: Tokens extracted from table name
        """
        log_entry = {
            "event": "index_update",
            "table_name": table_name,
            "tokens": tokens,
            "case_format": self.index.table_formats[table_name].value,
            "current_memory": self.index._current_size_bytes,
            "timestamp": self._get_timestamp(),
        }
        self._logger.info(json.dumps(log_entry))

    @staticmethod
    def _get_timestamp() -> str:
        """Get current timestamp in ISO format.

        Returns:
            ISO formatted timestamp string
        """
        return datetime.now(UTC).isoformat()
