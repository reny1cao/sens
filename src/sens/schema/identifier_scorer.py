"""Identifies and scores columns that serve as primary identifiers for their tables."""

import re
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from .schema_extractor import ColumnInfo, DatabaseSchema, TableInfo


class ColumnScore(BaseModel):
    """Score and metadata for a column's suitability as an identifier."""

    score: float = Field(
        ..., description="Numeric score indicating suitability as an identifier"
    )
    reasons: List[str] = Field(
        default_factory=list, description="List of reasons contributing to the score"
    )


class IdentifierScorer:
    """Identifies and scores columns that serve as primary identifiers for their tables."""

    # Patterns that suggest a column is an identifier
    IDENTIFIER_PATTERNS = [
        r"(^|_)(name|title|label)($|_)",  # Matches name, title, label with word boundaries
        r"(^|_)display(_|$)",  # Matches display_name, display_label etc
        r"(^|_)description($|_)",  # Matches description fields
    ]

    # Keywords in descriptions that suggest identifier status
    IDENTIFIER_KEYWORDS = [
        "identifier",
        "display",
        "primary",
        "name",
        "title",
        "label",
        "description",
    ]

    # Patterns suggesting technical/system fields to down-rank
    SYSTEM_PATTERNS = [
        r"(^|_)(created|updated|modified)(_at|_date)($|_)",  # Timestamps
        r"(^|_)(version|deleted|active|enabled)($|_)",  # Status/system fields
        r"(^|_)(pk|fk)(_|$)",  # Technical keys
        r"^id$",  # Standalone 'id'
    ]

    def __init__(self):
        """Initialize the scorer with compiled regex patterns."""
        self.identifier_regex = [re.compile(p, re.I) for p in self.IDENTIFIER_PATTERNS]
        self.system_regex = [re.compile(p, re.I) for p in self.SYSTEM_PATTERNS]

    def score_column(self, column: ColumnInfo, table_info: TableInfo) -> ColumnScore:
        """Score a single column's suitability as an identifier.

        Args:
            column: The column to score
            table_info: The table containing this column, for context

        Returns:
            ColumnScore with numeric score and reasons
        """
        score = 0.0
        reasons: List[str] = []

        # Check name patterns
        pattern_matches = 0
        for pattern in self.identifier_regex:
            if pattern.search(column.name):
                pattern_matches += 1
                score += 3.0
                reasons.append(f"name_pattern_match:{pattern.pattern}")

        # Check description keywords if available
        if column.description:
            keyword_matches = 0
            desc_lower = column.description.lower()
            for keyword in self.IDENTIFIER_KEYWORDS:
                if keyword.lower() in desc_lower:
                    keyword_matches += 1
                    score += 2.0  # Add 2.0 points per keyword match
                    reasons.append(f"description_keyword:{keyword}")

        # Prefer string types as identifiers
        if any(
            type_name in column.data_type.value.lower()
            for type_name in ["char", "text", "varchar"]
        ):
            score += 2.0
            reasons.append("string_type")

        # Down-rank system fields
        for pattern in self.system_regex:
            if pattern.search(column.name):
                score -= 3.0
                reasons.append(f"system_field:{pattern.pattern}")

        # Check if column is a foreign key
        is_fk = any(
            column.name in fk.from_columns
            for fk in table_info.foreign_keys
        )
        if is_fk:
            score -= 2.0
            reasons.append("foreign_key")

        # Down-rank primary keys that aren't string-based
        # (numeric PKs are usually internal IDs)
        if column.is_primary_key and not any(
            type_name in column.data_type.value.lower()
            for type_name in ["char", "text", "varchar"]
        ):
            score -= 1.0
            reasons.append("numeric_primary_key")

        return ColumnScore(score=score, reasons=reasons)

    def identify_sticky_columns(
        self, schema: DatabaseSchema, top_n: int = 2
    ) -> Dict[str, List[str]]:
        """Identify sticky columns for each table in the schema.

        Args:
            schema: The database schema to analyze
            top_n: Maximum number of sticky columns to identify per table

        Returns:
            Dictionary mapping table names to their sticky column names
        """
        sticky_columns: Dict[str, List[str]] = {}

        for table_name, table_info in schema.tables.items():
            # Score each column in the table
            scores: Dict[str, ColumnScore] = {}
            for column in table_info.columns:
                scores[column.name] = self.score_column(column, table_info)

            # Select top N scoring columns
            sorted_columns = sorted(
                scores.items(), key=lambda x: x[1].score, reverse=True
            )

            # Only include columns with positive scores
            sticky_columns[table_name] = [
                col_name
                for col_name, score in sorted_columns[:top_n]
                if score.score > 0
            ]

        return sticky_columns
