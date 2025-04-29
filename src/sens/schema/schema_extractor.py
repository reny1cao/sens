"""
Schema extractor for the Netflix sample database.
Extracts and formats database schema information for LLM consumption.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import psycopg2
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": %(message)s}',
)
logger = logging.getLogger(__name__)


class ColumnInfo(BaseModel):
    """Metadata for a database column."""

    name: str
    data_type: str
    is_nullable: bool
    default_value: Optional[str] = None
    is_primary: bool = False
    foreign_key: Optional[Dict[str, str]] = None
    description: Optional[str] = None


class TableInfo(BaseModel):
    """Metadata for a database table."""

    name: str
    columns: List[ColumnInfo]
    primary_keys: List[str] = Field(default_factory=list)
    foreign_keys: List[Dict[str, str]] = Field(default_factory=list)
    row_count: Optional[int] = None
    description: Optional[str] = None


class DatabaseSchema(BaseModel):
    """Complete database schema representation."""

    tables: Dict[str, TableInfo]
    relationships: List[Dict[str, str]] = Field(default_factory=list)
    metadata: Dict[str, Any]


class SchemaExtractor:
    """Extracts and manages database schema information."""

    def __init__(self, db_url: str = "postgresql://localhost/netflixdb"):
        """Initialize the schema extractor.

        Args:
            db_url: Database connection URL
        """
        self.db_url = db_url
        self.logger = logging.getLogger(__name__)

    def _get_connection(self):
        """Create a database connection."""
        return psycopg2.connect(self.db_url)

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
    ) -> List[Dict[str, str]]:
        """Extract foreign key relationships."""
        relationships = []

        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT
                        tc.table_name as table_name,
                        kcu.column_name as column_name,
                        ccu.table_name AS foreign_table_name,
                        ccu.column_name AS foreign_column_name
                    FROM information_schema.table_constraints AS tc
                    JOIN information_schema.key_column_usage AS kcu
                        ON tc.constraint_name = kcu.constraint_name
                    JOIN information_schema.constraint_column_usage AS ccu
                        ON ccu.constraint_name = tc.constraint_name
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                """
                )

                for row in cur.fetchall():
                    relationships.append(
                        {
                            "from_table": row["table_name"],
                            "from_column": row["column_name"],
                            "to_table": row["foreign_table_name"],
                            "to_column": row["foreign_column_name"],
                        }
                    )

                    # Update table foreign key information
                    if row["table_name"] in tables:
                        tables[row["table_name"]].foreign_keys.append(
                            {
                                "column": row["column_name"],
                                "references_table": row["foreign_table_name"],
                                "references_column": row["foreign_column_name"],
                            }
                        )

        return relationships

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
            # Add table header with description
            output.append(f"\nTable {table_name} {{")
            if table_info.description:
                output.append(f"  # {table_info.description}")

            # Add columns
            for col in table_info.columns:
                parts = [
                    f"  {col.name}: {col.data_type}",
                    "(primary key)" if col.is_primary else "",
                    "(not null)" if not col.is_nullable else "",
                ]
                output.append(" ".join(part for part in parts if part))
                if col.description:
                    output.append(f"    # {col.description}")

            # Add relationships
            for fk in table_info.foreign_keys:
                output.append(f"  → {fk['references_table']} via {fk['column']}")

            output.append("}")

        return "\n".join(output)

    def extract_and_save(self, config_dir: str = "config") -> DatabaseSchema:
        """Extract schema and save to files."""
        try:
            # Ensure config directory exists
            Path(config_dir).mkdir(parents=True, exist_ok=True)

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
                    "extracted_at": datetime.utcnow().isoformat(),
                    "database": self.db_url.split("/")[-1],
                },
            )

            # Save full schema
            schema_path = Path(config_dir) / "schema_metadata.json"
            self.logger.info(f"Saving full schema to {schema_path}")
            with open(schema_path, "w") as f:
                json.dump(schema.model_dump(), f, indent=2)

            # Save LLM-friendly version
            llm_path = Path(config_dir) / "schema_for_llm.txt"
            self.logger.info(f"Saving LLM format to {llm_path}")
            with open(llm_path, "w") as f:
                f.write(self.format_for_llm(schema))

            return schema

        except Exception as e:
            self.logger.error(f"Schema extraction failed: {str(e)}")
            raise


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
