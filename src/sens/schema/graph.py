import json
import logging
from pathlib import Path
from typing import ClassVar, Dict, List, Optional, Set, Tuple

from sens.settings import get_settings

# Use the Pydantic models for schema validation and structure
from .schema_extractor import (
    ColumnInfo,
    DatabaseSchema,
    ForeignKeyColumnPair,
    ForeignKeyConstraint,
    TableInfo,
)

logger = logging.getLogger(__name__)

# Get schema path from settings
settings = get_settings()
DEFAULT_SCHEMA_PATH = str(settings.schema_path)


class SchemaGraph:
    # ... (Keep singleton logic and __init__ declaration) ...
    _instance: ClassVar[Optional["SchemaGraph"]] = None
    _initialized: ClassVar[bool] = False

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance. Primarily used for testing."""
        cls._instance = None
        cls._initialized = False
        logger.info("SchemaGraph singleton instance reset.")

    @classmethod
    def get_instance(cls, schema_path: str = DEFAULT_SCHEMA_PATH) -> "SchemaGraph":
        """Gets the singleton instance, initializing it on first call."""
        if cls._instance is None:
            logger.info("Creating new SchemaGraph singleton instance.")
            cls._instance = cls(schema_path=schema_path)
        elif not cls._initialized:
            logger.warning(
                "SchemaGraph instance exists but not initialized. Re-initializing."
            )
            cls._instance.__init__(schema_path=cls._instance.schema_path)

        return cls._instance

    def __init__(self, schema_path: str = DEFAULT_SCHEMA_PATH):
        """
        Initializes the SchemaGraph instance. Should typically be called via get_instance().
        Loads and processes schema data if not already initialized.
        """
        if SchemaGraph._initialized:
            logger.debug("SchemaGraph already initialized, skipping re-initialization.")
            if self.schema_path != schema_path:
                logger.warning(
                    f"SchemaGraph singleton already initialized with {self.schema_path}. "
                    f"Ignoring request to re-initialize with {schema_path}."
                )
            return

        logger.info(f"Initializing SchemaGraph singleton from {schema_path}")
        self.schema_path = schema_path
        self._pk_map: Dict[str, List[str]] = {}
        # Maps table -> list of (fk_cols_list, ref_table, ref_cols_list) tuples originating from table
        self._fk_map: Dict[str, List[Tuple[List[str], str, List[str]]]] = {}
        # Maps ref_table -> list of (from_table, from_cols_list, ref_cols_list) tuples pointing to ref_table
        self._reverse_fk_map: Dict[str, List[Tuple[str, List[str], List[str]]]] = {}
        self._out_edges: Dict[str, Set[str]] = {}
        self._in_edges: Dict[str, Set[str]] = {}
        self._adjacency_list: Dict[str, Set[str]] = {}
        self._column_comments: Dict[Tuple[str, str], str] = {}
        self._all_tables: Set[str] = set()
        # Store the full constraint info if needed for more complex queries later
        self._constraints: Dict[str, ForeignKeyConstraint] = {}

        self._load_and_process_schema()
        SchemaGraph._initialized = True
        logger.info(
            f"SchemaGraph singleton initialized successfully with {len(self._all_tables)} tables."
        )

    def _load_and_process_schema(self):
        """Loads schema JSON using Pydantic models and builds internal maps."""
        schema_file = Path(self.schema_path)
        if not schema_file.is_file():
            logger.error(f"Schema metadata file not found: {self.schema_path}")
            SchemaGraph._initialized = False
            raise FileNotFoundError(f"Schema file not found: {self.schema_path}")

        try:
            with open(schema_file, "r") as f:
                schema_data = DatabaseSchema.model_validate_json(f.read())

            tables_data: Dict[str, TableInfo] = schema_data.tables
            relationships: List[ForeignKeyConstraint] = schema_data.relationships

            # Store the full schema data
            self._schema_data = schema_data

            # Build PK map, Column Comments map, initialize maps
            for table_name, table_info in tables_data.items():
                self._all_tables.add(table_name)
                self._pk_map[table_name] = table_info.primary_keys
                self._fk_map.setdefault(table_name, [])
                self._reverse_fk_map.setdefault(table_name, [])
                self._out_edges.setdefault(table_name, set())
                self._in_edges.setdefault(table_name, set())
                self._adjacency_list.setdefault(table_name, set())
                for col in table_info.columns:
                    if col.description:
                        self._column_comments[(table_name, col.name)] = col.description

            # Build FK maps and Edge Lists from validated ForeignKeyConstraint objects
            for constraint in relationships:
                from_table = constraint.from_table
                to_table = constraint.to_table
                # Extract lists of corresponding columns
                from_cols = [pair.from_column for pair in constraint.columns]
                to_cols = [pair.to_column for pair in constraint.columns]

                # Store full constraint info by name
                self._constraints[constraint.constraint_name] = constraint

                # Check if tables exist (should be true after Pydantic validation)
                if from_table in self._all_tables and to_table in self._all_tables:
                    # --- FK Maps (storing lists of columns) ---
                    self._fk_map[from_table].append((from_cols, to_table, to_cols))
                    self._reverse_fk_map[to_table].append(
                        (from_table, from_cols, to_cols)
                    )

                    # --- Edge Lists (table names only) ---
                    self._out_edges[from_table].add(to_table)
                    self._in_edges[to_table].add(from_table)
                    self._adjacency_list[from_table].add(to_table)
                    self._adjacency_list[to_table].add(from_table)

        except Exception as e:
            logger.exception(f"Failed processing schema file {self.schema_path}: {e}")
            SchemaGraph._initialized = False
            raise

    # --- Public Accessor Methods ---

    def get_table_pks(self, table_name: str) -> List[str]:
        """Get the primary key columns for a given table.

        Args:
            table_name: The name of the table to get primary keys for.

        Returns:
            A list of primary key column names.
        """
        return self._pk_map.get(table_name, [])

    def get_table_columns(self, table_name: str) -> List[str]:
        """Get all column names for a given table.

        Args:
            table_name: The name of the table to get columns for.

        Returns:
            A list of column names.
        """
        if hasattr(self, "_schema_data") and table_name in self._schema_data.tables:
            return [col.name for col in self._schema_data.tables[table_name].columns]
        return []

    def get_table_fks_involved(
        self, table_name: str, involved_tables: Set[str]
    ) -> List[str]:
        """Return a flat list of all source FK columns in 'table_name' that participate in any FK constraint referencing any table in 'involved_tables'."""
        if table_name not in self._fk_map:
            return []

        involved_fk_columns = set()
        # fk_col_list: List[str], referenced_table: str, _ : List[str]
        for fk_col_list, referenced_table, _ in self._fk_map[table_name]:
            if referenced_table in involved_tables:
                # Add all columns from this constraint to the set
                involved_fk_columns.update(fk_col_list)
        return list(involved_fk_columns)

    # --- Keep other methods: get_neighbor_tables, get_referencing_tables,
    # --- get_referenced_tables, get_column_comment, list_all_tables ---
    # They primarily use edge lists or direct maps unaffected by composite key column lists

    def get_neighbor_tables(self, table_names: Set[str]) -> Set[str]:
        """Get all tables that are directly connected to the given tables via foreign keys."""
        if not table_names:
            return set()
        valid_input_tables = table_names.intersection(self._all_tables)
        if not valid_input_tables:
            return set()
        neighbors = set(valid_input_tables)
        for table in valid_input_tables:
            neighbors.update(self._adjacency_list.get(table, set()))
        return neighbors

    def get_referencing_tables(self, table_name: str) -> Set[str]:
        """Returns tables that have FKs pointing *to* the given table."""
        return self._in_edges.get(table_name, set())

    def get_referenced_tables(self, table_name: str) -> Set[str]:
        """Returns tables that the given table points *to* via FKs."""
        return self._out_edges.get(table_name, set())

    def get_column_comment(self, table_name: str, column_name: str) -> Optional[str]:
        """Returns the comment/description for a specific column, if available."""
        return self._column_comments.get((table_name, column_name))

    def list_all_tables(self) -> List[str]:
        """Returns a sorted list of all table names loaded from the schema."""
        return sorted(list(self._all_tables))

    def get_constraint_info(
        self, constraint_name: str
    ) -> Optional[ForeignKeyConstraint]:
        """Returns the full ForeignKeyConstraint object for a given constraint name."""
        return self._constraints.get(constraint_name)

    def get_table_sticky_columns(self, table_name: str) -> List[str]:
        """Get the sticky (high-value identifier) columns for a given table.

        Args:
            table_name: The name of the table to get sticky columns for.

        Returns:
            A list of sticky column names.
        """
        if hasattr(self, "_schema_data") and table_name in self._schema_data.tables:
            return self._schema_data.tables[table_name].sticky_columns
        return []


# ... (Remove the old get_table_info placeholder if it existed) ...
