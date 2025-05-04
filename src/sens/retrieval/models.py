from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class RetrievedColumn:
    """Represents a column identified during retrieval."""

    table_name: str
    column_name: str
    score: float
    source: str  # 'token' or 'embedding'
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievedTable:
    """Represents a table identified during retrieval or through expansion."""

    table_name: str
    # Reason for inclusion: 'direct_hit', 'join_expansion', etc.
    reason: str
    # Can store aggregated scores or other table-level info
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievedContext:
    """Holds the final ranked and deduplicated schema context after retrieval."""

    query: str
    tables: List[RetrievedTable] = field(default_factory=list)
    columns: List[RetrievedColumn] = field(default_factory=list)
    # Optional: Add overall confidence or other top-level metadata if needed
