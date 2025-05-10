"""SQL query validator for schema context.

This module provides validation for SQL queries against a schema context,
ensuring proper table and column references, and valid foreign key relationships.
"""

from dataclasses import dataclass
from typing import List, Set, Union

import sqlparse
from sqlparse.sql import Statement, Token, TokenList
from sqlparse.tokens import Name

from sens.schema.context import ValidatorSchemaContext
from sens.validation.types import ColumnReference, JoinCondition


class SQLValidator:
    """Validates SQL queries against schema context."""

    def __init__(self, schema_context: ValidatorSchemaContext):
        """Initialize SQL validator with schema context.

        Args:
            schema_context: Schema context containing tables, columns and relationships
        """
        self.schema_context = schema_context
        self._validate_schema_context()

    def _validate_schema_context(self):
        """Validate that schema context is internally consistent."""
        # Validate foreign keys reference existing tables and columns
        for from_table, fk_map in self.schema_context.foreign_keys.items():
            if from_table not in self.schema_context.tables:
                raise ValueError(
                    f"Foreign key references non-existent table: {from_table}"
                )

            for from_col, (to_table, to_col) in fk_map.items():
                if to_table not in self.schema_context.tables:
                    raise ValueError(
                        f"Foreign key references non-existent table: {to_table}"
                    )

                if from_col not in self.schema_context.columns_per_table[from_table]:
                    raise ValueError(
                        f"Foreign key column {from_col} not in table {from_table}"
                    )
                if to_col not in self.schema_context.columns_per_table[to_table]:
                    raise ValueError(
                        f"Foreign key column {to_col} not in table {to_table}"
                    )

    def validate_query(self, sql_query: str) -> List[str]:
        """Validate SQL query against schema context.

        Returns:
            List of validation error messages. Empty list if validation passes.
        """
        try:
            # Parse the SQL query
            parsed = sqlparse.parse(sql_query)[0]

            # Extract table and column references
            table_refs = set()
            column_refs = []
            self._extract_references(parsed, table_refs, column_refs)

            # Validate tables exist
            errors = []
            for table in table_refs:
                if table not in self.schema_context.tables:
                    errors.append(f"Table '{table}' not found in schema")

            # Early return if table errors found
            if errors:
                return errors

            # Validate columns exist in their tables
            for col_ref in column_refs:
                if col_ref.table:
                    # Fully qualified column
                    if col_ref.table not in self.schema_context.tables:
                        errors.append(f"Table '{col_ref.table}' not found in schema")
                        continue

                    if (
                        col_ref.column
                        not in self.schema_context.columns_per_table[col_ref.table]
                    ):
                        errors.append(
                            f"Column '{col_ref.column}' not found in table '{col_ref.table}'"
                        )
                else:
                    # Unqualified column - check all referenced tables
                    found = False
                    for table in table_refs:
                        if (
                            col_ref.column
                            in self.schema_context.columns_per_table[table]
                        ):
                            found = True
                            break
                    if not found:
                        errors.append(
                            f"Column '{col_ref.column}' not found in any referenced table"
                        )

            # Validate joins use valid foreign keys
            self._validate_joins(parsed, errors)

            return errors

        except Exception as e:
            return [f"SQL parsing error: {str(e)}"]

    def _extract_references(
        self,
        token: Union[sqlparse.sql.Token, sqlparse.sql.TokenList],
        table_refs: Set[str],
        column_refs: List[ColumnReference],
    ):
        """Extract table and column references from SQL tokens."""
        if isinstance(token, sqlparse.sql.TokenList):
            for t in token.tokens:
                self._extract_references(t, table_refs, column_refs)
        else:
            # Handle table references
            if (
                isinstance(token.parent, sqlparse.sql.Identifier)
                and token.parent.has_alias()
                and token.parent.get_real_name()
            ):
                table_refs.add(token.parent.get_real_name())
            elif token.ttype is sqlparse.tokens.Name and isinstance(
                token.parent, (sqlparse.sql.Identifier, sqlparse.sql.Function)
            ):
                parts = token.value.split(".")
                if len(parts) == 2:
                    table_refs.add(parts[0])
                    column_refs.append(ColumnReference(parts[0], parts[1]))
                elif len(parts) == 1:
                    column_refs.append(ColumnReference(None, parts[0]))

    def _validate_joins(self, parsed: sqlparse.sql.Statement, errors: List[str]):
        """Validate that JOINs use valid foreign key relationships."""
        join_conditions = self._extract_join_conditions(parsed)

        for join in join_conditions:
            left_table = join.left_table
            right_table = join.right_table
            left_col = join.left_column
            right_col = join.right_column

            # Check if this join matches any foreign key relationship
            valid_join = False

            # Check left to right
            if left_table in self.schema_context.foreign_keys:
                for from_col, (to_table, to_col) in self.schema_context.foreign_keys[
                    left_table
                ].items():
                    if (
                        to_table == right_table
                        and from_col == left_col
                        and to_col == right_col
                    ):
                        valid_join = True
                        break

            # Check right to left
            if not valid_join and right_table in self.schema_context.foreign_keys:
                for from_col, (to_table, to_col) in self.schema_context.foreign_keys[
                    right_table
                ].items():
                    if (
                        to_table == left_table
                        and from_col == right_col
                        and to_col == left_col
                    ):
                        valid_join = True
                        break

            if not valid_join:
                errors.append(
                    f"Invalid join between {left_table}.{left_col} and {right_table}.{right_col}"
                )

    def _extract_join_conditions(
        self, parsed: sqlparse.sql.Statement
    ) -> List[JoinCondition]:
        """Extract join conditions from parsed SQL."""
        joins = []
        # Implementation to extract join conditions from parsed SQL
        # This is a placeholder - actual implementation would traverse the parse tree
        return joins
