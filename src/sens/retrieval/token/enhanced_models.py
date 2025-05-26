"""Enhanced data models for the token index implementation."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

from .models import CaseFormat, TokenIndex


@dataclass
class SchemaItem:
    """Represents a schema item (table or column) with its metadata."""

    name: str
    item_type: str  # "table" or "column"
    parent_table: Optional[str] = None  # For columns, the table they belong to
    metadata: Dict = field(default_factory=dict)


@dataclass
class TokenMatch:
    """Represents a match from the token index with its score."""

    table_name: str
    column_name: Optional[str]
    score: float
    match_type: str  # "exact", "prefix", "partial"
    token_overlap: int  # Number of query tokens that matched


@dataclass
class EnhancedTokenIndex(TokenIndex):
    """Enhanced token index that supports both table and column indexing."""

    # Additional index for columns, mapping tokens to (table_name, column_name) pairs
    column_token_map: Dict[str, Set[Tuple[str, str]]] = field(default_factory=dict)

    # Metadata about columns
    column_metadata: Dict[Tuple[str, str], Dict] = field(default_factory=dict)

    def add_column(
        self, table_name: str, column_name: str, metadata: Optional[Dict] = None
    ) -> None:
        """Add a column to the index with its metadata.

        Args:
            table_name: Name of the table containing the column
            column_name: Name of the column
            metadata: Optional metadata about the column (e.g., data type, constraints)
        """
        if metadata is None:
            metadata = {}

        key = (table_name, column_name)
        self.column_metadata[key] = metadata

    def get_column_metadata(self, table_name: str, column_name: str) -> Optional[Dict]:
        """Get metadata for a specific column.

        Args:
            table_name: Name of the table containing the column
            column_name: Name of the column

        Returns:
            Dictionary of metadata if the column exists, None otherwise
        """
        return self.column_metadata.get((table_name, column_name))

    def get_stats(self) -> Dict[str, any]:
        """Calculate basic statistics about the enhanced index."""
        stats = super().get_stats()
        stats.update(
            {
                "column_token_count": len(self.column_token_map),
                "indexed_columns": len(self.column_metadata),
            }
        )
        return stats
