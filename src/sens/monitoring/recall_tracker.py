"""Recall tracking integration for SQL validation.

This module provides utilities to track which schema elements were
actually used in the generated SQL for recall rate calculation.
"""

import re
from typing import Dict, List, Set, Tuple

import structlog
from sqlglot import parse_one
from sqlglot.expressions import Column, Identifier, Table

from sens.monitoring.performance_metrics import get_performance_tracker

log = structlog.get_logger()


class RecallTracker:
    """Tracks relevant schema elements from validated SQL."""

    @staticmethod
    def extract_schema_from_sql(sql: str) -> Tuple[Set[str], Set[Tuple[str, str]]]:
        """Extract tables and columns used in SQL query.

        Args:
            sql: The SQL query string

        Returns:
            Tuple of (tables, columns) where columns are (table, column) tuples
        """
        tables = set()
        columns = set()
        alias_to_table = {}  # Map aliases to actual table names

        try:
            # Parse SQL using sqlglot
            parsed = parse_one(sql)

            # First pass: Extract tables and build alias mapping
            for table in parsed.find_all(Table):
                table_name = table.name
                if table_name:
                    tables.add(table_name)
                    # Check for alias
                    if hasattr(table, "alias") and table.alias:
                        alias_name = str(table.alias)
                        alias_to_table[alias_name] = table_name

            # Second pass: Extract columns with their tables
            for column in parsed.find_all(Column):
                col_name = column.name
                table_ref = None

                # Try to get table from column reference
                if column.table:
                    table_ref = str(column.table)
                elif hasattr(column, "parent") and hasattr(column.parent, "table"):
                    table_ref = str(column.parent.table)

                # Resolve alias to actual table name
                if table_ref:
                    actual_table = alias_to_table.get(table_ref, table_ref)
                    if actual_table in tables:
                        columns.add((actual_table, col_name))
                elif col_name:
                    # Try to determine table from context
                    # For columns without explicit table reference, check parent nodes
                    parent = column.parent
                    while parent:
                        if hasattr(parent, "this") and hasattr(parent.this, "name"):
                            # Check if this is a table reference
                            potential_table = str(parent.this.name)
                            if potential_table in tables:
                                columns.add((potential_table, col_name))
                                break
                        parent = getattr(parent, "parent", None)

                    # If still no table found and only one table in query, use it
                    if not parent and len(tables) == 1:
                        columns.add((next(iter(tables)), col_name))

            # Also look for identifiers (columns without table prefix)
            for identifier in parsed.find_all(Identifier):
                id_name = str(identifier)
                # Check if this identifier is likely a column name
                if (
                    id_name
                    and id_name not in tables
                    and not id_name.upper()
                    in {
                        "SELECT",
                        "FROM",
                        "WHERE",
                        "JOIN",
                        "ON",
                        "AND",
                        "OR",
                        "IN",
                        "DISTINCT",
                    }
                ):
                    # Try to find which table this column belongs to
                    # For subqueries, check the nearest FROM clause
                    parent = identifier.parent
                    while parent:
                        if hasattr(parent, "this") and hasattr(parent.this, "name"):
                            potential_table = str(parent.this.name)
                            if potential_table in tables:
                                columns.add((potential_table, id_name))
                                break
                        # Check if we're in a subquery context
                        if parent.__class__.__name__ == "Select":
                            # Find tables in this select's FROM clause
                            for sub_table in parent.find_all(Table):
                                if sub_table.name in tables:
                                    columns.add((sub_table.name, id_name))
                                    break
                            break
                        parent = getattr(parent, "parent", None)

            log.debug(
                "extracted_schema_from_sql",
                tables=list(tables),
                column_count=len(columns),
                alias_mapping=alias_to_table,
            )

        except Exception as e:
            log.warning(
                "failed_to_parse_sql_for_recall",
                error=str(e),
                sql=sql[:100],
            )
            # Fallback to regex extraction
            tables, columns = RecallTracker._regex_extract_schema(sql)

        return tables, columns

    @staticmethod
    def _regex_extract_schema(sql: str) -> Tuple[Set[str], Set[Tuple[str, str]]]:
        """Fallback regex-based schema extraction."""
        tables = set()
        columns = set()

        # Normalize SQL
        sql_normalized = sql.upper()

        # Extract tables from FROM and JOIN clauses
        from_pattern = r"FROM\s+(\w+)"
        join_pattern = r"JOIN\s+(\w+)"

        for match in re.finditer(from_pattern, sql_normalized):
            tables.add(match.group(1).lower())

        for match in re.finditer(join_pattern, sql_normalized):
            tables.add(match.group(1).lower())

        # Extract columns (simplified - won't catch all cases)
        # This is a basic implementation and might need enhancement
        select_pattern = r"SELECT\s+(.*?)\s+FROM"
        select_match = re.search(select_pattern, sql_normalized)

        if select_match and tables:
            select_clause = select_match.group(1)
            # For simplicity, assume columns belong to first table
            first_table = next(iter(tables))

            # Split by comma and extract column names
            for col_expr in select_clause.split(","):
                col_expr = col_expr.strip()
                # Extract column name (handle aliases)
                if " AS " in col_expr:
                    col_name = col_expr.split(" AS ")[0].strip()
                else:
                    col_name = col_expr.strip()

                # Remove table prefixes if present
                if "." in col_name:
                    parts = col_name.split(".")
                    table_name = parts[0].lower()
                    col_name = parts[1].lower()
                    if table_name in tables:
                        columns.add((table_name, col_name))
                else:
                    columns.add((first_table, col_name.lower()))

        return tables, columns

    @staticmethod
    def track_sql_recall(query: str, sql: str, retrieval_metrics_collector):
        """Track recall based on SQL usage.

        Args:
            query: Original natural language query
            sql: Generated and validated SQL
            retrieval_metrics_collector: The collector instance from retrieval
        """
        try:
            # Extract schema elements from SQL
            relevant_tables, relevant_columns = RecallTracker.extract_schema_from_sql(
                sql
            )

            # Update the retrieval metrics with ground truth
            if (
                retrieval_metrics_collector
                and retrieval_metrics_collector.current_metrics
            ):
                retrieval_metrics_collector.record_relevant_schema(
                    relevant_tables, relevant_columns
                )

                # Log recall stats
                recall_stats = (
                    retrieval_metrics_collector.current_metrics.calculate_recall()
                )
                log.info(
                    "recall_tracked",
                    query=query[:50],
                    table_recall=recall_stats["table_recall"],
                    column_recall=recall_stats["column_recall"],
                    tables_relevant=len(relevant_tables),
                    columns_relevant=len(relevant_columns),
                )

        except Exception as e:
            log.error(
                "failed_to_track_recall",
                error=str(e),
                query=query[:50],
            )
