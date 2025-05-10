"""Convert between different schema context representations."""

from typing import Dict, Set, Tuple

from sens.retrieval.models import RetrievedContext
from sens.schema.context import ValidatorSchemaContext


def to_validator_schema(context: RetrievedContext) -> ValidatorSchemaContext:
    """Convert RetrievedContext to ValidatorSchemaContext.

    Args:
        context: The retrieved context from the retrieval system

    Returns:
        A ValidatorSchemaContext suitable for SQL validation
    """
    # Extract unique table names
    tables = {table.table_name for table in context.tables}

    # Build columns per table mapping
    columns_per_table = {}
    for column in context.columns:
        if column.table_name not in columns_per_table:
            columns_per_table[column.table_name] = set()
        columns_per_table[column.table_name].add(column.column_name)

    # Ensure all tables have an entry in columns_per_table, even if empty
    for table in tables:
        if table not in columns_per_table:
            columns_per_table[table] = set()

    # Build foreign key mapping from metadata
    foreign_keys: Dict[str, Dict[str, Tuple[str, str]]] = {}

    for column in context.columns:
        # Only process columns marked as foreign keys
        if column.metadata.get("type") == "FK":
            referenced_table = column.metadata.get("references_table")
            if referenced_table and referenced_table in tables:
                # Initialize the FK dict for this table if needed
                if column.table_name not in foreign_keys:
                    foreign_keys[column.table_name] = {}

                # Add the FK relationship
                # For now, assume the referenced column is 'id' if not specified
                referenced_column = column.metadata.get("references_column", "id")
                foreign_keys[column.table_name][column.column_name] = (
                    referenced_table,
                    referenced_column,
                )

    return ValidatorSchemaContext(
        tables=tables,
        columns_per_table=columns_per_table,
        foreign_keys=foreign_keys,
    )
