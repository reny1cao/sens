"""Convert between different schema context representations."""

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

    return ValidatorSchemaContext(
        tables=tables,
        columns_per_table=columns_per_table,
        # Foreign keys are not available in RetrievedContext
        foreign_keys={},
    )
