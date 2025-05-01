"""Data models for the token index implementation."""

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
