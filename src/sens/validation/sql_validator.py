"""
SQL Validator for ensuring query correctness, safety, and schema alignment.

This module provides validation for SQL queries to ensure they are:
1. Syntactically correct
2. Schema-aligned (using only existing tables/columns)
3. Safe (no destructive operations unless explicitly allowed)
"""

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Set, Tuple

import sqlparse
from sqlparse.sql import (
    Comment,
    Identifier,
    IdentifierList,
    Statement,
    Token,
    TokenList,
    Where,
)
from sqlparse.tokens import DDL, DML, Keyword, Name, Punctuation, Whitespace

# Configure logging
logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    """Levels of SQL validation."""

    SYNTAX = auto()
    SCHEMA = auto()
    SAFETY = auto()
    ALL = auto()


@dataclass
class SchemaContext:
    """Database schema representation for validation."""

    tables: Set[str]
    columns_per_table: Dict[str, Set[str]]
    foreign_keys: Dict[str, Dict[str, Tuple[str, str]]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict) -> "SchemaContext":
        """Create SchemaContext from a dictionary representation."""
        return cls(
            tables=set(data.get("tables", [])),
            columns_per_table={
                table: set(columns)
                for table, columns in data.get("columns_per_table", {}).items()
            },
            foreign_keys=data.get("foreign_keys", {}),
        )


@dataclass
class ValidationError:
    """Represents a single validation error."""

    level: ValidationLevel
    message: str
    details: Optional[str] = None


@dataclass
class ValidatedSQL:
    """Result of SQL validation."""

    sql: str
    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        """String representation of validation result."""
        status = "VALID" if self.is_valid else "INVALID"
        result = [f"SQL Validation Result: {status}"]
        if self.errors:
            result.append("\nErrors:")
            for error in self.errors:
                result.append(f"- [{error.level.name}] {error.message}")
                if error.details:
                    result.append(f"  Details: {error.details}")
        if self.warnings:
            result.append("\nWarnings:")
            for warning in self.warnings:
                result.append(f"- {warning}")
        return "\n".join(result)


class SQLValidator:
    """
    Validates SQL queries for syntax, schema alignment, and safety.

    This validator ensures that SQL queries are:
    1. Syntactically correct using sqlparse
    2. Schema-aligned by checking tables and columns against a provided schema
    3. Safe by checking for forbidden operations
    """

    # Default set of dangerous keywords that should be blocked
    DEFAULT_FORBIDDEN_KEYWORDS = {
        "DROP",
        "TRUNCATE",
        "DELETE",
        "ALTER",
        "GRANT",
        "REVOKE",
        "RENAME",
        "REPLACE",
        "EXECUTE",
    }

    def __init__(
        self,
        whitelisted_keywords: Optional[Set[str]] = None,
        additional_forbidden_keywords: Optional[Set[str]] = None,
        require_where_for_updates: bool = True,
    ):
        """
        Initialize the SQL validator.

        Args:
            whitelisted_keywords: Set of normally forbidden keywords to allow
            additional_forbidden_keywords: Additional keywords to forbid
            require_where_for_updates: If True, requires WHERE clause for UPDATE/DELETE
        """
        self.whitelisted_keywords = {k.upper() for k in (whitelisted_keywords or set())}
        additional_forbidden = {
            k.upper() for k in (additional_forbidden_keywords or set())
        }
        self.forbidden_keywords = (
            self.DEFAULT_FORBIDDEN_KEYWORDS | additional_forbidden
        ) - self.whitelisted_keywords
        self.require_where_for_updates = require_where_for_updates

    def _check_syntax(self, sql: str) -> List[ValidationError]:
        """
        Check SQL syntax using sqlparse.

        Args:
            sql: SQL query string to validate

        Returns:
            List of ValidationError objects for any syntax errors found
        """
        errors = []
        try:
            # Parse the SQL statement
            statements = sqlparse.parse(sql.strip())

            if not statements:
                errors.append(
                    ValidationError(
                        level=ValidationLevel.SYNTAX,
                        message="No SQL statements found in input",
                    )
                )
                return errors

            # Check each statement
            for stmt in statements:
                # Skip comments
                tokens = [t for t in stmt.tokens if not isinstance(t, Comment)]
                if not tokens or all(t.is_whitespace for t in tokens):
                    errors.append(
                        ValidationError(
                            level=ValidationLevel.SYNTAX,
                            message=f"Empty statement found in SQL: {stmt}",
                        )
                    )
                    continue

                # Basic structure validation
                has_valid_keyword = False
                for token in stmt.flatten():
                    if isinstance(token, Comment):
                        continue
                    if token.ttype in (Keyword, DML, DDL):
                        has_valid_keyword = True
                        break

                if not has_valid_keyword:
                    errors.append(
                        ValidationError(
                            level=ValidationLevel.SYNTAX,
                            message=f"No valid SQL keyword found in statement: {stmt}",
                        )
                    )

        except Exception as e:
            errors.append(
                ValidationError(
                    level=ValidationLevel.SYNTAX,
                    message="SQL parsing failed",
                    details=str(e),
                )
            )

        return errors

    def _extract_table_column_references(
        self, stmt: Statement
    ) -> Tuple[Set[str], Dict[str, Set[str]]]:
        referenced_tables = set()
        referenced_columns = {}
        table_aliases = {}
        current_tables = []

        def clean_identifier(value: str) -> str:
            value = value.split("--", 1)[0].strip()
            return value.strip("`\"' ")

        def collect_columns(token, current_tables):
            # Recursively collect columns from TokenList, Identifier, or Name
            if isinstance(token, TokenList):
                for subtoken in token.tokens:
                    collect_columns(subtoken, current_tables)
            elif isinstance(token, Identifier):
                name = clean_identifier(
                    token.get_real_name() or token.get_name() or token.value
                )
                if "." in name:
                    tbl, col = name.split(".", 1)
                    tbl = tbl.lower()
                    col = col.lower()
                    if tbl in table_aliases:
                        tbl = table_aliases[tbl]
                    if tbl not in referenced_columns:
                        referenced_columns[tbl] = set()
                    referenced_columns[tbl].add(col)
                else:
                    if len(current_tables) == 1:
                        real_tbl = table_aliases.get(
                            current_tables[0], current_tables[0]
                        )
                        if real_tbl not in referenced_columns:
                            referenced_columns[real_tbl] = set()
                        referenced_columns[real_tbl].add(name.lower())
                    else:
                        for tbl in current_tables:
                            real_tbl = table_aliases.get(tbl, tbl)
                            if real_tbl not in referenced_columns:
                                referenced_columns[real_tbl] = set()
                            referenced_columns[real_tbl].add(name.lower())
            elif token.ttype in (Name,):
                name = clean_identifier(token.value)
                if len(current_tables) == 1:
                    real_tbl = table_aliases.get(current_tables[0], current_tables[0])
                    if real_tbl not in referenced_columns:
                        referenced_columns[real_tbl] = set()
                    referenced_columns[real_tbl].add(name.lower())
                else:
                    for tbl in current_tables:
                        real_tbl = table_aliases.get(tbl, tbl)
                        if real_tbl not in referenced_columns:
                            referenced_columns[real_tbl] = set()
                        referenced_columns[real_tbl].add(name.lower())

        tokens = list(stmt.tokens)
        # First pass: collect tables and aliases from FROM, JOIN, UPDATE, INTO, and DDL (DROP, ALTER, etc.)
        for idx, token in enumerate(tokens):
            if isinstance(token, Comment):
                continue
            # DDL statements (DROP TABLE ...)
            if token.ttype == DDL:
                # Look for the first Name or Identifier token after the DDL keyword
                j = idx + 1
                while j < len(tokens):
                    t = tokens[j]
                    if (
                        isinstance(t, Comment)
                        or t.is_whitespace
                        or (t.ttype == Keyword)
                    ):
                        j += 1
                        continue
                    if isinstance(t, Identifier):
                        real_name = clean_identifier(
                            t.get_real_name() or t.get_name() or t.value
                        )
                        referenced_tables.add(real_name.lower())
                        break
                    elif t.ttype in (Name, None):
                        name = clean_identifier(t.value)
                        referenced_tables.add(name.lower())
                        break
                    j += 1
            if token.ttype == Keyword and token.value.upper() in {
                "FROM",
                "JOIN",
                "UPDATE",
                "INTO",
            }:
                j = idx + 1
                while j < len(tokens) and (
                    tokens[j].is_whitespace or isinstance(tokens[j], Comment)
                ):
                    j += 1
                if j < len(tokens):
                    next_token = tokens[j]
                    if isinstance(next_token, Identifier):
                        real_name = clean_identifier(
                            next_token.get_real_name()
                            or next_token.get_name()
                            or next_token.value
                        )
                        alias = clean_identifier(next_token.get_alias() or real_name)
                        referenced_tables.add(real_name.lower())
                        table_aliases[alias.lower()] = real_name.lower()
                        current_tables.append(alias.lower())
                    elif next_token.ttype in (Name, None):
                        name = clean_identifier(next_token.value)
                        referenced_tables.add(name.lower())
                        table_aliases[name.lower()] = name.lower()
                        current_tables.append(name.lower())

        # Second pass: collect columns from SELECT, WHERE, etc.
        found_from = False
        for token in stmt.tokens:
            if isinstance(token, Comment):
                continue
            # SELECT columns: collect all IdentifierList/Identifier tokens before FROM
            if not found_from:
                if token.ttype is Keyword and token.value.upper() == "FROM":
                    found_from = True
                elif isinstance(token, (IdentifierList, Identifier)):
                    collect_columns(token, current_tables)
            # WHERE clause
            if isinstance(token, Where):
                for t in token.tokens:
                    if isinstance(t, Identifier) or t.ttype in (Name,):
                        collect_columns(t, current_tables)

        return referenced_tables, referenced_columns

    def _check_schema(self, sql: str, schema: SchemaContext) -> List[ValidationError]:
        """
        Validate SQL against schema context.

        Args:
            sql: SQL query string
            schema: SchemaContext object containing valid tables and columns

        Returns:
            List of ValidationError objects for any schema mismatches
        """
        errors = []
        statements = sqlparse.parse(sql)

        schema_tables_lower = {t.lower() for t in schema.tables}
        schema_columns_lower = {
            table.lower(): {col.lower() for col in columns}
            for table, columns in schema.columns_per_table.items()
        }

        for stmt in statements:
            referenced_tables, referenced_columns = (
                self._extract_table_column_references(stmt)
            )

            # Check tables
            for table in referenced_tables:
                if table not in schema_tables_lower:
                    errors.append(
                        ValidationError(
                            level=ValidationLevel.SCHEMA,
                            message=f"Referenced table '{table}' does not exist in schema",
                            details=f"Available tables: {', '.join(sorted(schema.tables))}",
                        )
                    )

            # Check columns
            for table, columns in referenced_columns.items():
                if table in schema_tables_lower:
                    valid_columns = schema_columns_lower[table]
                    for col in columns:
                        if col not in valid_columns:
                            errors.append(
                                ValidationError(
                                    level=ValidationLevel.SCHEMA,
                                    message=f"Column '{col}' does not exist in table '{table}'",
                                    details=f"Available columns: {', '.join(sorted(schema.columns_per_table[table]))}",
                                )
                            )
                else:
                    # If table doesn't exist, report column errors with a note about the invalid table
                    for col in columns:
                        errors.append(
                            ValidationError(
                                level=ValidationLevel.SCHEMA,
                                message=f"Cannot validate column '{col}' as table '{table}' does not exist",
                                details=f"Available tables: {', '.join(sorted(schema.tables))}",
                            )
                        )

        return errors

    def _check_safety(self, sql: str) -> List[ValidationError]:
        """
        Check SQL for safety violations.

        Args:
            sql: SQL query string

        Returns:
            List of ValidationError objects for any safety violations
        """
        errors = []
        statements = sqlparse.parse(sql)

        for stmt in statements:
            # Skip comments
            tokens = [t for t in stmt.tokens if not isinstance(t, Comment)]
            if not tokens or all(t.is_whitespace for t in tokens):
                continue

            # Get the statement type
            stmt_type = None
            for token in stmt.tokens:
                if isinstance(token, Comment):
                    continue
                if token.ttype in (Keyword, DML, DDL):
                    stmt_type = token.value.upper()
                    # For DDL statements, they are forbidden by default unless whitelisted
                    if (
                        token.ttype == DDL
                        and stmt_type not in self.whitelisted_keywords
                    ):
                        errors.append(
                            ValidationError(
                                level=ValidationLevel.SAFETY,
                                message=f"DDL statement '{stmt_type}' is not allowed",
                                details="DDL operations are forbidden by default",
                            )
                        )
                        # Skip checking for forbidden keywords since we've already flagged the DDL statement
                        break
                    break

            # Only check for forbidden keywords if we haven't already flagged a DDL statement
            if not any(error.message.startswith("DDL statement") for error in errors):
                # Check for forbidden keywords in the rest of the statement
                found_forbidden = set()
                for token in stmt.flatten():
                    if isinstance(token, Comment):
                        continue
                    if token.ttype in (Keyword, DML, DDL):
                        token_upper = token.value.upper()
                        # Don't count the statement type itself as a forbidden keyword for DML statements
                        if (
                            token_upper != stmt_type
                            and token_upper in self.forbidden_keywords
                        ):
                            found_forbidden.add(token_upper)

                for keyword in found_forbidden:
                    errors.append(
                        ValidationError(
                            level=ValidationLevel.SAFETY,
                            message=f"Forbidden keyword '{keyword}' found in SQL",
                            details="This operation is not allowed for safety reasons",
                        )
                    )

            # Special handling for UPDATE and DELETE if they require WHERE clauses
            if self.require_where_for_updates and stmt_type in ("UPDATE", "DELETE"):
                has_where = False
                has_condition = False

                # Look for WHERE clause and ensure it has conditions
                for token in stmt.tokens:
                    if isinstance(token, Comment):
                        continue
                    if isinstance(token, Where):
                        has_where = True
                        # Check if WHERE clause has actual conditions
                        where_tokens = [
                            t
                            for t in token.tokens
                            if not isinstance(t, Comment) and not t.is_whitespace
                        ]
                        has_condition = (
                            len(where_tokens) > 1
                        )  # More than just the WHERE keyword
                        break
                    elif isinstance(token, TokenList):
                        for t in token.tokens:
                            if isinstance(t, Comment):
                                continue
                            if isinstance(t, Where):
                                has_where = True
                                where_tokens = [
                                    wt
                                    for wt in t.tokens
                                    if not isinstance(wt, Comment)
                                    and not wt.is_whitespace
                                ]
                                has_condition = len(where_tokens) > 1
                                break
                            elif t.ttype == Keyword and t.value.upper() == "WHERE":
                                has_where = True
                                # Look ahead for conditions
                                idx = token.token_index(t)
                                next_tokens = [
                                    nt
                                    for nt in token.tokens[idx + 1 :]
                                    if not isinstance(nt, Comment)
                                    and not nt.is_whitespace
                                ]
                                has_condition = len(next_tokens) > 0
                                break
                    elif token.ttype == Keyword and token.value.upper() == "WHERE":
                        has_where = True
                        # Look ahead for conditions
                        idx = stmt.token_index(token)
                        next_tokens = [
                            nt
                            for nt in stmt.tokens[idx + 1 :]
                            if not isinstance(nt, Comment) and not nt.is_whitespace
                        ]
                        has_condition = len(next_tokens) > 0
                        break

                if not has_where or not has_condition:
                    errors.append(
                        ValidationError(
                            level=ValidationLevel.SAFETY,
                            message=f"{stmt_type} statement requires a non-empty WHERE clause",
                            details="Unfiltered UPDATE/DELETE operations are not allowed",
                        )
                    )

        return errors

    def validate(
        self,
        sql: str,
        schema: SchemaContext,
        levels: Optional[Set[ValidationLevel]] = None,
    ) -> ValidatedSQL:
        """
        Validate SQL query against all specified validation levels.

        Args:
            sql: SQL query string to validate
            schema: SchemaContext object containing valid tables and columns
            levels: Set of ValidationLevel to check (defaults to ALL)

        Returns:
            ValidatedSQL object containing validation results
        """
        if levels is None:
            levels = {ValidationLevel.ALL}

        if ValidationLevel.ALL in levels:
            levels = {
                ValidationLevel.SYNTAX,
                ValidationLevel.SCHEMA,
                ValidationLevel.SAFETY,
            }

        errors = []

        # Always do syntax check first as other checks depend on valid syntax
        syntax_errors = self._check_syntax(sql)
        if ValidationLevel.SYNTAX in levels:
            errors.extend(syntax_errors)

        # Only proceed with other checks if syntax is valid
        if not syntax_errors:
            # Always run both schema and safety checks for DDL
            if ValidationLevel.SCHEMA in levels:
                schema_errors = self._check_schema(sql, schema)
                errors.extend(schema_errors)
            if ValidationLevel.SAFETY in levels:
                safety_errors = self._check_safety(sql)
                errors.extend(safety_errors)

        is_valid = len(errors) == 0
        return ValidatedSQL(sql=sql, is_valid=is_valid, errors=errors)
