"""Data models for the token index implementation."""

import sys
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Set


class CaseFormat(Enum):
    """Enumeration of supported case formats."""

    SNAKE = "snake"  # example_name
    CAMEL = "camel"  # exampleName
    KEBAB = "kebab"  # example-name


@dataclass
class TokenIndex:
    """Main token index data structure maintaining O(1) lookup capability."""

    # Main index mapping tokens to table names
    token_map: Dict[str, Set[str]] = field(default_factory=dict)

    # Original table names with their case format
    table_formats: Dict[str, CaseFormat] = field(default_factory=dict)

    # Memory tracking
    _current_size_bytes: int = 0

    # Constants
    MAX_MEMORY_BYTES: int = 1_000_000  # 1MB limit
    MAX_TOKEN_LENGTH: int = 64  # Maximum length for individual tokens

    def __post_init__(self):
        """Initialize any computed fields after instance creation."""
        self._validate_memory_usage()

    def _validate_memory_usage(self) -> None:
        """Ensure memory usage is within limits."""
        if self._current_size_bytes > self.MAX_MEMORY_BYTES:
            raise ValueError(
                f"Memory usage ({self._current_size_bytes} bytes) "
                f"exceeds limit ({self.MAX_MEMORY_BYTES} bytes)"
            )

    def get_stats(self) -> Dict[str, any]:
        """Calculate basic statistics about the index."""
        case_format_counts = Counter(f.value for f in self.table_formats.values())
        return {
            "table_count": len(self.table_formats),
            "token_count": len(self.token_map),
            "memory_usage_bytes": self._current_size_bytes,
            "case_formats": dict(case_format_counts),
        }

    def get_detailed_structure(self, top_n_tokens: int = 10) -> Dict[str, any]:
        """Calculate detailed structure and statistics of the index."""
        # Calculate token details
        tokens_details = {}
        for token, tables in self.token_map.items():
            token_memory = sys.getsizeof(token) + sum(sys.getsizeof(t) for t in tables)
            tokens_details[token] = {
                "token": token,
                "tables": list(tables),
                "frequency": len(tables),
                "memory_bytes": token_memory,
            }

        # Calculate table tokenization details (requires a tokenizer)
        # Note: The original service had _tokenize, but models shouldn't know how to tokenize.
        # We can skip table tokenization details here or require the builder's tokenizer.
        # For now, let's omit table-specific token details from this model method.

        # Find most common tokens
        token_frequencies = Counter(
            {t: details["frequency"] for t, details in tokens_details.items()}
        )
        most_common = [
            tokens_details[token]
            for token, _ in token_frequencies.most_common(top_n_tokens)
        ]

        # Calculate memory distribution (approximation)
        token_memory = sum(t["memory_bytes"] for t in tokens_details.values())
        table_format_memory = sum(
            sys.getsizeof(t) + sys.getsizeof(f) for t, f in self.table_formats.items()
        )
        overhead = sys.getsizeof(self.token_map) + sys.getsizeof(self.table_formats)
        memory_distribution = {
            "tokens": token_memory,
            "table_formats": table_format_memory,  # Memory for table names & their formats
            "index_overhead": overhead,  # Memory for the dict structures themselves
            "total_approx": token_memory + table_format_memory + overhead,
        }

        # Compare with tracked memory (should be close)
        memory_distribution["tracked_total"] = self._current_size_bytes

        return {
            "total_tables": len(self.table_formats),
            "total_tokens": len(self.token_map),
            "total_memory_bytes": self._current_size_bytes,
            "tokens_details": tokens_details,  # Renamed from 'tokens' for clarity
            # "tables_details": tables_details, # Omitted for now
            "most_common_tokens": most_common,
            "memory_distribution": memory_distribution,
        }
