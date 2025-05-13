"""Schema retriever for natural language queries.

This module provides functionality to retrieve relevant schema information
based on natural language queries, including tables, columns, and their relationships.
"""

from typing import Dict, List, Set, Tuple

from sens.schema import DatabaseSchema, IdentifierScorer
from sens.schema.context import LLMSchemaContext
from sens.schema.graph import SchemaGraph


class SchemaRetriever:
    """Retrieves relevant schema information based on natural language query."""

    def __init__(self, schema_graph: SchemaGraph):
        """Initialize retriever with schema graph."""
        self.schema_graph = schema_graph
        self.identifier_scorer = IdentifierScorer()
        self._init_indices()

    def _init_indices(self):
        """Initialize search indices for tables and columns."""
        self.table_index = self._build_table_index()
        self.column_index = self._build_column_index()

    def retrieve_schema_context(self, query: str, top_k: int = 5) -> LLMSchemaContext:
        """Retrieve relevant schema context for the query.

        Args:
            query: Natural language query
            top_k: Number of top tables/columns to retrieve

        Returns:
            LLMSchemaContext with relevant schema information and sticky columns
        """
        # Get relevant tables and their scores
        table_scores = self.table_index.search(query, top_k)
        relevant_tables = {table for table, _ in table_scores}

        # Get relevant columns and their scores
        column_scores = self.column_index.search(query, top_k * 2)  # Get more columns

        # Build tables_columns mapping
        tables_columns: Dict[str, List[str]] = {}
        for table in relevant_tables:
            # Get all columns for the table
            all_columns = self.schema_graph.get_table_columns(table)

            # Add primary keys
            primary_keys = self.schema_graph.get_primary_keys(table)

            # Initialize with primary keys to ensure they're always included
            tables_columns[table] = list(primary_keys)

            # Add other columns that are either relevant or part of relationships
            for col in all_columns:
                if col not in tables_columns[table]:  # Avoid duplicates
                    # Check if column is in relevant columns or part of a relationship
                    col_key = f"{table}.{col}"
                    if any(cs[0] == col_key for cs in column_scores):
                        tables_columns[table].append(col)
                    # Add columns involved in relationships with other relevant tables
                    elif self._is_relationship_column(table, col, relevant_tables):
                        tables_columns[table].append(col)

        # Get primary keys for all tables
        primary_keys = {
            table: list(self.schema_graph.get_primary_keys(table))
            for table in tables_columns.keys()
        }

        # Get foreign keys between relevant tables
        foreign_keys = []
        for table in relevant_tables:
            fks = self.schema_graph.get_foreign_keys(table)
            for fk in fks:
                if fk["to_table"] in relevant_tables:
                    foreign_keys.append(fk)
                    # Ensure foreign key columns are in tables_columns
                    if isinstance(fk["from_columns"], list):
                        tables_columns[fk["from_table"]].extend(
                            col
                            for col in fk["from_columns"]
                            if col not in tables_columns[fk["from_table"]]
                        )
                    else:
                        if fk["from_columns"] not in tables_columns[fk["from_table"]]:
                            tables_columns[fk["from_table"]].append(fk["from_columns"])

                    if isinstance(fk["to_columns"], list):
                        tables_columns[fk["to_table"]].extend(
                            col
                            for col in fk["to_columns"]
                            if col not in tables_columns[fk["to_table"]]
                        )
                    else:
                        if fk["to_columns"] not in tables_columns[fk["to_table"]]:
                            tables_columns[fk["to_table"]].append(fk["to_columns"])

        # Get column descriptions
        column_descriptions = {}
        for table, columns in tables_columns.items():
            column_descriptions[table] = {
                col: self.schema_graph.get_column_description(table, col)
                for col in columns
            }

        # Build schema for sticky column identification
        schema = DatabaseSchema(
            tables={
                table: self.schema_graph.get_table_info(table)
                for table in tables_columns.keys()
            },
            relationships=foreign_keys,
            metadata={},
        )

        # Identify sticky columns
        sticky_columns = self.identifier_scorer.identify_sticky_columns(schema)

        return LLMSchemaContext(
            tables_columns=tables_columns,
            primary_keys=primary_keys,
            foreign_keys=foreign_keys,
            column_descriptions=column_descriptions,
            sticky_columns=sticky_columns,
            tables=set(tables_columns.keys()),
            metadata=schema.metadata,
        )

    def _is_relationship_column(
        self, table: str, column: str, relevant_tables: Set[str]
    ) -> bool:
        """Check if a column is involved in relationships with other relevant tables."""
        # Check if column is part of a foreign key relationship
        fks = self.schema_graph.get_foreign_keys(table)
        for fk in fks:
            if fk["to_table"] in relevant_tables:
                if isinstance(fk["from_columns"], list):
                    if column in fk["from_columns"]:
                        return True
                elif column == fk["from_columns"]:
                    return True
        return False
