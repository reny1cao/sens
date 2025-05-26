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

    def get_tables_dict(self) -> Dict[str, RetrievedTable]:
        """Get tables as a dictionary keyed by table name."""
        return {table.table_name: table for table in self.tables}

    def get_columns_by_table(self) -> Dict[str, List[RetrievedColumn]]:
        """Get columns grouped by table name."""
        result = {}
        for col in self.columns:
            if col.table_name not in result:
                result[col.table_name] = []
            result[col.table_name].append(col)
        return result

    def format_for_llm(self) -> str:
        """Format the retrieved context as a string suitable for LLM consumption."""
        # Group columns by table
        table_columns = self.get_columns_by_table()

        # Format each table
        parts = []
        for table in self.tables:
            columns = table_columns.get(table.table_name, [])
            column_names = sorted([col.column_name for col in columns])
            columns_str = ", ".join(column_names)

            table_def = f"TABLE {table.table_name} ({columns_str})"
            if table.metadata.get("description"):
                table_def += f"\n-- {table.metadata['description']}"
            parts.append(table_def)

        return "\n\n".join(parts)

    def format_for_llm_dict(self) -> Dict[str, Any]:
        """Format the retrieved context in a dictionary structure suitable for LLM consumption."""
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
