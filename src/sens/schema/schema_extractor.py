"""
Schema extractor for the Netflix sample database.
Extracts and formats database schema information for LLM consumption.
"""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import psycopg2
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, Field

from sens.settings import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": %(message)s}',
)
logger = logging.getLogger(__name__)


# --- New Models for Composite Key Support ---
class ForeignKeyColumnPair(BaseModel):
    """Represents a single pair of columns in an FK relationship."""

    from_column: str
    to_column: str


class ForeignKeyConstraint(BaseModel):
    """Represents a complete FK constraint, potentially composite."""

    constraint_name: str
    from_table: str
    to_table: str
    columns: List[ForeignKeyColumnPair] = Field(default_factory=list)


# --- End New Models ---


class ColumnInfo(BaseModel):
    """Metadata for a database column."""

    name: str
    data_type: str
    is_nullable: bool
    default_value: Optional[str] = None
    is_primary: bool = False
    # Keep simple dict here for now, or could be enhanced later
    foreign_key: Optional[Dict[str, str]] = None
    description: Optional[str] = None


class TableInfo(BaseModel):
    """Metadata for a database table."""

    name: str
    columns: List[ColumnInfo]
    primary_keys: List[str] = Field(default_factory=list)
    # Updated to store full constraint info
    foreign_keys: List[ForeignKeyConstraint] = Field(default_factory=list)
    row_count: Optional[int] = None
    description: Optional[str] = None


class DatabaseSchema(BaseModel):
    """Complete database schema representation."""

    tables: Dict[str, TableInfo]
    # Updated to use the new structured constraint model
    relationships: List[ForeignKeyConstraint] = Field(default_factory=list)
    metadata: Dict[str, Any]


class SchemaExtractor:
    """Extracts and manages database schema information."""

    def __init__(
        self,
        db_url: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        dbname: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ):
        """Initialize with database connection parameters.

        Args:
            db_url: Optional database URL in format postgresql://user:pass@host:port/dbname
            host: Optional database host
            port: Optional database port
            dbname: Optional database name
            user: Optional database user
            password: Optional database password

        If db_url is provided, it takes precedence over individual parameters.
        If neither is provided, falls back to settings.
        """
        settings = get_settings()

        if db_url:
            # Parse db_url into components
            try:
                from urllib.parse import urlparse

                parsed = urlparse(db_url)
                if not parsed.scheme == "postgresql":
                    raise ValueError("Only PostgreSQL URLs are supported")

                # Extract components from URL
                self.db_config = {
                    "host": parsed.hostname,
                    "port": parsed.port or 5432,
                    "dbname": parsed.path.lstrip("/"),
                    "user": parsed.username,
                    "password": parsed.password,
                }
            except Exception as e:
                raise ValueError(f"Invalid database URL: {e}")
        else:
            # Use provided values or fall back to settings
            self.db_config = {
                "host": host or settings.db_host,
                "port": port or settings.db_port,
                "dbname": dbname or settings.db_name,
                "user": user or settings.db_user,
                "password": password or settings.db_password,
            }

        self.logger = logging.getLogger(__name__)

    def _get_connection(self):
        """Create a database connection."""
        try:
            return psycopg2.connect(
                host=self.db_config["host"],
                port=self.db_config["port"],
                dbname=self.db_config["dbname"],
                user=self.db_config["user"],
                password=self.db_config["password"],
            )
        except psycopg2.OperationalError as e:
            raise ValueError(f"Invalid database URL: {str(e)}")
        except Exception as e:
            raise ValueError(f"Database connection failed: {str(e)}")

    def extract_basic_schema(self) -> Dict[str, TableInfo]:
        """Extract basic table and column information."""
        tables = {}

        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get all tables
                cur.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_type = 'BASE TABLE'
                """
                )
                table_names = [row["table_name"] for row in cur.fetchall()]

                for table_name in table_names:
                    # Get columns
                    cur.execute(
                        """
                        SELECT
                            column_name,
                            data_type,
                            is_nullable = 'YES' as is_nullable,
                            column_default,
                            col_description(
                                (SELECT oid FROM pg_class WHERE relname = %s),
                                ordinal_position
                            ) as description
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                        AND table_name = %s
                        ORDER BY ordinal_position
                    """,
                        (table_name, table_name),
                    )

                    columns = []
                    for row in cur.fetchall():
                        columns.append(
                            ColumnInfo(
                                name=row["column_name"],
                                data_type=row["data_type"],
                                is_nullable=row["is_nullable"],
                                default_value=row["column_default"],
                                description=row["description"],
                            )
                        )

                    # Get primary keys
                    cur.execute(
                        """
                        SELECT a.attname
                        FROM pg_index i
                        JOIN pg_attribute a ON a.attrelid = i.indrelid
                        AND a.attnum = ANY(i.indkey)
                        WHERE i.indrelid = %s::regclass
                        AND i.indisprimary
                    """,
                        (table_name,),
                    )
                    primary_keys = [row["attname"] for row in cur.fetchall()]

                    # Mark primary key columns
                    for col in columns:
                        if col.name in primary_keys:
                            col.is_primary = True

                    # Get table description
                    cur.execute(
                        """
                        SELECT obj_description(%s::regclass, 'pg_class') as description
                    """,
                        (table_name,),
                    )
                    description = cur.fetchone()["description"]

                    tables[table_name] = TableInfo(
                        name=table_name,
                        columns=columns,
                        primary_keys=primary_keys,
                        description=description,
                    )

        return tables

    def extract_relationships(
        self, tables: Dict[str, TableInfo]
    ) -> List[ForeignKeyConstraint]:
        """Extract foreign key relationships, handling composite keys."""
        relationships_by_constraint: Dict[str, ForeignKeyConstraint] = {}
        final_relationships_list: List[ForeignKeyConstraint] = []

        sql = """
            SELECT
                tc.constraint_name,
                tc.table_name AS from_table,
                kcu.column_name AS from_column,
                ccu.table_name AS to_table,
                ccu.column_name AS to_column,
                kcu.ordinal_position -- Important for composite keys
            FROM
                information_schema.table_constraints AS tc
            JOIN
                information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
            JOIN
                information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
            WHERE
                tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_schema = 'public'  -- Adjust schema if needed
            ORDER BY
                tc.constraint_name,
                kcu.ordinal_position;
            """

        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(sql)

                    for row in cur.fetchall():
                        constraint_name = row["constraint_name"]
                        from_table = row["from_table"]
                        to_table = row["to_table"]

                        # If it's the first time seeing this constraint, create the base object
                        if constraint_name not in relationships_by_constraint:
                            relationships_by_constraint[constraint_name] = (
                                ForeignKeyConstraint(
                                    constraint_name=constraint_name,
                                    from_table=from_table,
                                    to_table=to_table,
                                    columns=[],  # Initialize empty list for column pairs
                                )
                            )

                        # Add the current column pair to the constraint's list
                        column_pair = ForeignKeyColumnPair(
                            from_column=row["from_column"], to_column=row["to_column"]
                        )
                        relationships_by_constraint[constraint_name].columns.append(
                            column_pair
                        )

            # Convert dict to list for the final result
            final_relationships_list = list(relationships_by_constraint.values())

            # --- Update TableInfo.foreign_keys ---
            # Clear existing potentially incorrect FKs added by previous logic if any
            for table in tables.values():
                table.foreign_keys = []

            # Add the correctly structured FK constraint info to each table
            for constraint in final_relationships_list:
                if constraint.from_table in tables:
                    tables[constraint.from_table].foreign_keys.append(constraint)
            # --- End Update TableInfo.foreign_keys ---

            self.logger.info(
                f"Extracted {len(final_relationships_list)} foreign key constraints."
            )
            return final_relationships_list

        except Exception as e:
            self.logger.error(f"Failed to extract relationships: {e}", exc_info=True)
            # Depending on desired behavior, might return empty list or re-raise
            raise  # Re-raise for now

    def analyze_data_patterns(self, tables: Dict[str, TableInfo]):
        """Analyze basic data patterns and statistics."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                for table_name, table_info in tables.items():
                    # Get row count
                    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
                    table_info.row_count = cur.fetchone()[0]

    def format_for_llm(
        self, schema: DatabaseSchema, tables: Optional[Set[str]] = None
    ) -> str:
        """Format schema for LLM consumption."""
        output = ["Database Schema:"]

        # Filter tables if specified
        table_items = schema.tables.items()
        if tables:
            table_items = [(k, v) for k, v in table_items if k in tables]

        for table_name, table_info in table_items:
            output.append(f"\nTable {table_name} {{")
            if table_info.description:
                output.append(f"  # {table_info.description}")

            for col in table_info.columns:
                parts = [
                    f"  {col.name}: {col.data_type}",
                    "(primary key)" if col.is_primary else "",
                    "(not null)" if not col.is_nullable else "",
                ]
                output.append(" ".join(part for part in parts if part))
                if col.description:
                    output.append(f"    # {col.description}")

            # Display relationships - simple version for now
            for fk in table_info.foreign_keys:
                # Just show the referenced table and the first FK column for brevity
                # Could be enhanced to show all columns `(col1, col2) -> tableB (ref1, ref2)`
                from_cols_str = ", ".join([c.from_column for c in fk.columns])
                output.append(f"  → {fk.to_table} via {from_cols_str}")

            output.append("}")

        return "\n".join(output)

    def extract_and_save(self, config_dir: Optional[str] = None) -> DatabaseSchema:
        """Extract schema and save to files."""
        try:
            settings = get_settings()
            schema_path = (
                Path(config_dir) / "schema_metadata.json"
                if config_dir
                else settings.schema_path
            )
            schema_path.parent.mkdir(parents=True, exist_ok=True)

            # Extract basic schema
            self.logger.info("Extracting basic schema information...")
            tables = self.extract_basic_schema()

            # Extract relationships
            self.logger.info("Extracting relationships...")
            relationships = self.extract_relationships(tables)

            # Analyze patterns
            self.logger.info("Analyzing data patterns...")
            self.analyze_data_patterns(tables)

            # Create schema
            schema = DatabaseSchema(
                tables=tables,
                relationships=relationships,
                metadata={
                    "extracted_at": datetime.now(UTC).isoformat(),
                    "database": self.db_config["dbname"],
                },
            )

            # Save full schema
            self.logger.info(f"Saving full schema to {schema_path}")
            with open(schema_path, "w") as f:
                json.dump(
                    schema.model_dump(mode="json", exclude_unset=True), f, indent=2
                )

            # Save LLM-friendly version
            llm_path = schema_path.parent.parent / "prompts" / "schema_for_llm.txt"
            self.logger.info(f"Saving LLM format to {llm_path}")
            with open(llm_path, "w") as f:
                f.write(self.format_for_llm(schema))

            return schema

        except Exception as e:
            self.logger.error(f"Schema extraction failed: {str(e)}")
            raise

    def extract_schema(self, schema_path: str) -> Dict:
        """Extract schema metadata from the given JSON file.

        Args:
            schema_path: Path to the schema metadata JSON file.

        Returns:
            Dictionary containing the extracted schema metadata.
        """
        with open(schema_path, "r") as f:
            return json.load(f)


def main():
    """Main entry point for schema extraction."""
    try:
        extractor = SchemaExtractor()
        extractor.extract_and_save()
        print("Schema extracted successfully")
    except Exception as e:
        logging.error(f"Failed to extract schema: {str(e)}")
        raise


if __name__ == "__main__":
    main()
