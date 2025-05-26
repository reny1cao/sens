"""Unified schema context management to ensure consistency across components.

This module provides a single source of truth for schema context building,
ensuring that SQL generation and validation use the same schema information.
"""

from typing import Dict, List, Optional, Set, Tuple

import structlog

from sens.llm.intent_validator import ValidIntent
from sens.retrieval.models import RetrievedContext
from sens.schema.context import LLMSchemaContext, ValidatorSchemaContext
from sens.schema.graph import SchemaGraph

log = structlog.get_logger(__name__)


class UnifiedSchemaContextBuilder:
    """Builds consistent schema contexts for all pipeline components."""

    def __init__(self):
        """Initialize the builder with a schema graph instance."""
        self.schema = SchemaGraph.get_instance()

    def build_from_retrieval(
        self,
        retrieved_context: RetrievedContext,
        intent: Optional[ValidIntent] = None,
        include_all_columns: bool = False,
    ) -> Tuple[LLMSchemaContext, ValidatorSchemaContext]:
        """Build both LLM and Validator contexts from retrieval results.

        Args:
            retrieved_context: The context from retrieval
            intent: Optional intent to expand context with related tables
            include_all_columns: If True, include all columns for retrieved tables

        Returns:
            Tuple of (LLMSchemaContext, ValidatorSchemaContext) that are consistent
        """
        # Start with tables from retrieval
        tables = {table.table_name for table in retrieved_context.tables}

        # Add intent tables if provided
        if intent:
            tables.update(intent.original_intent.tables)

        # Expand with related tables for joins
        expanded_tables = self._expand_with_related_tables(tables)

        # Build column sets
        tables_columns = {}
        columns_per_table = {}

        for table in expanded_tables:
            if include_all_columns:
                # Include all columns from schema
                all_columns = self.schema.get_table_columns(table)
                tables_columns[table] = all_columns
                columns_per_table[table] = set(all_columns)
            else:
                # Use only retrieved columns for this table
                table_columns = [
                    col.column_name
                    for col in retrieved_context.columns
                    if col.table_name == table
                ]
                if table_columns:
                    tables_columns[table] = table_columns
                    columns_per_table[table] = set(table_columns)
                else:
                    # For expanded tables, include key columns
                    key_columns = self._get_key_columns(table)
                    tables_columns[table] = key_columns
                    columns_per_table[table] = set(key_columns)

        # Build primary keys
        primary_keys = {
            table: self.schema.get_table_pks(table) for table in expanded_tables
        }

        # Build foreign keys
        foreign_keys = self._build_foreign_keys(expanded_tables)

        # Build column descriptions
        column_descriptions = {}
        for table, columns in tables_columns.items():
            table_descriptions = {}
            for column in columns:
                description = self.schema.get_column_comment(table, column)
                if description:
                    table_descriptions[column] = description
            if table_descriptions:
                column_descriptions[table] = table_descriptions

        # Create contexts
        llm_context = LLMSchemaContext(
            tables=expanded_tables,
            tables_columns=tables_columns,
            primary_keys=primary_keys,
            foreign_keys=foreign_keys,
            column_descriptions=column_descriptions,
        )

        validator_context = ValidatorSchemaContext(
            tables=expanded_tables,
            columns_per_table=columns_per_table,
        )

        log.info(
            "unified_context_built",
            table_count=len(expanded_tables),
            total_columns=sum(len(cols) for cols in columns_per_table.values()),
            include_all_columns=include_all_columns,
        )

        return llm_context, validator_context

    def _expand_with_related_tables(self, tables: Set[str]) -> Set[str]:
        """Expand table set with directly related tables for joins."""
        expanded = set(tables)

        for table in list(tables):  # Use list to avoid set mutation during iteration
            # Add referenced tables (foreign key targets)
            referenced = self.schema.get_referenced_tables(table)
            expanded.update(referenced)

            # Optionally add referencing tables (tables that reference this one)
            # This is more aggressive and might include too many tables
            # referencing = self.schema.get_referencing_tables(table)
            # expanded.update(referencing)

        return expanded

    def _get_key_columns(self, table: str) -> List[str]:
        """Get key columns (PKs and FKs) for a table."""
        columns = []

        # Add primary keys
        pks = self.schema.get_table_pks(table)
        columns.extend(pks)

        # Add foreign keys
        fk_cols = self.schema.get_table_fks(table)
        columns.extend(fk_cols)

        # Remove duplicates while preserving order
        seen = set()
        return [col for col in columns if not (col in seen or seen.add(col))]

    def _build_foreign_keys(self, tables: Set[str]) -> List[Dict[str, any]]:
        """Build foreign key relationships between tables."""
        fk_list = []

        for table in tables:
            for ref_table in tables:
                if table == ref_table:
                    continue

                fk_cols = self.schema.get_table_fks_involved(table, {ref_table})
                if fk_cols:
                    fk_list.append(
                        {
                            "from_table": table,
                            "from_columns": fk_cols,
                            "to_table": ref_table,
                            "to_columns": self.schema.get_table_pks(ref_table),
                        }
                    )

        return fk_list


# Configuration options
class SchemaContextStrategy:
    """Strategy options for schema context building."""

    # Conservative: Only use retrieved columns
    CONSERVATIVE = "conservative"

    # Balanced: Use retrieved columns + all columns for primary intent tables
    BALANCED = "balanced"

    # Aggressive: Use all columns for all retrieved tables
    AGGRESSIVE = "aggressive"


def get_strategy_config(strategy: str) -> dict:
    """Get configuration for a given strategy."""
    configs = {
        SchemaContextStrategy.CONSERVATIVE: {
            "include_all_columns": False,
            "expand_intent_tables": False,
        },
        SchemaContextStrategy.BALANCED: {
            "include_all_columns": False,
            "expand_intent_tables": True,
        },
        SchemaContextStrategy.AGGRESSIVE: {
            "include_all_columns": True,
            "expand_intent_tables": True,
        },
    }
    return configs.get(strategy, configs[SchemaContextStrategy.BALANCED])
