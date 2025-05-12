from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class RetrievedColumn:
    """Represents a column identified during retrieval."""

    table_name: str
    column_name: str
    score: float
    source: str  # 'token', 'embedding', or 'sticky'
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_sticky: bool = False  # Flag for sticky columns

    def __post_init__(self):
        """Post-initialization hook to adjust score for sticky columns."""
        if self.is_sticky and "sticky_boost" not in self.metadata:
            # Apply a boost to sticky columns that weren't already boosted
            self.score += 2.0
            self.metadata["sticky_boost"] = True


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

    def format_for_llm(self) -> Dict[str, Any]:
        """Format the retrieved context in a structure suitable for LLM consumption."""
        return {
            "query": self.query,
            "tables": [
                {"name": table.table_name, "reason": table.reason, **table.metadata}
                for table in self.tables
            ],
            "columns": [
                {
                    "table": column.table_name,
                    "column": column.column_name,
                    "score": column.score,
                    "source": column.source,
                    **column.metadata,
                }
                for column in self.columns
            ],
        }

    def model_dump(self) -> Dict[str, Any]:
        """Convert the instance to a dictionary representation."""
        return {
            "query": self.query,
            "tables": [
                {
                    "table_name": table.table_name,
                    "reason": table.reason,
                    "metadata": table.metadata,
                }
                for table in self.tables
            ],
            "columns": [
                {
                    "table_name": column.table_name,
                    "column_name": column.column_name,
                    "score": column.score,
                    "source": column.source,
                    "metadata": column.metadata,
                }
                for column in self.columns
            ],
        }
