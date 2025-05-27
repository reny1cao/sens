"""Pre-computed schema indexes for optimized retrieval.

This module provides pre-computed indexes for schema elements to avoid
repeated calculations during query processing.
"""

import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import structlog

from sens.schema.graph import SchemaGraph
from sens.settings import get_settings

log = structlog.get_logger()


@dataclass
class TableIndex:
    """Pre-computed index for a table."""

    table_name: str
    columns: List[str]
    primary_keys: List[str]
    sticky_columns: List[str]
    # Tables this table has FKs to
    referenced_tables: Set[str] = field(default_factory=set)
    # Tables that have FKs to this table
    referencing_tables: Set[str] = field(default_factory=set)
    # All neighbor tables (both directions)
    neighbor_tables: Set[str] = field(default_factory=set)
    # Foreign key columns in this table
    foreign_key_columns: Dict[str, Tuple[str, str]] = field(default_factory=dict)
    # Column descriptions
    column_descriptions: Dict[str, str] = field(default_factory=dict)


@dataclass
class RelationshipIndex:
    """Pre-computed index for table relationships."""

    # Map of (from_table, to_table) -> List of (from_col, to_col) pairs
    foreign_keys: Dict[Tuple[str, str], List[Tuple[str, str]]] = field(
        default_factory=dict
    )
    # Map of table -> set of all tables it can join with
    join_graph: Dict[str, Set[str]] = field(default_factory=dict)
    # Map of table -> minimum join distance to other tables
    join_distances: Dict[str, Dict[str, int]] = field(default_factory=dict)


class PrecomputedSchemaIndex:
    """Manager for pre-computed schema indexes.

    This class pre-computes and caches various schema relationships and
    metadata to optimize runtime schema retrieval.
    """

    def __init__(self, schema_graph: Optional[SchemaGraph] = None):
        """Initialize the pre-computed index.

        Args:
            schema_graph: Optional SchemaGraph instance. If not provided,
                        will use the singleton instance.
        """
        self.schema_graph = schema_graph or SchemaGraph.get_instance()
        self.settings = get_settings()

        # Index storage
        self.table_indexes: Dict[str, TableIndex] = {}
        self.relationship_index = RelationshipIndex()

        # Cache directory
        self.cache_dir = Path.home() / ".sens" / "schema_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Build or load indexes
        self._initialize_indexes()

    def _initialize_indexes(self):
        """Initialize indexes by loading from cache or building from scratch."""
        cache_file = self.cache_dir / "precomputed_index.pkl"

        # Check if cache exists and is newer than schema file
        schema_path = Path(self.settings.schema_path)
        if cache_file.exists() and schema_path.exists():
            cache_mtime = cache_file.stat().st_mtime
            schema_mtime = schema_path.stat().st_mtime

            if cache_mtime > schema_mtime:
                try:
                    self._load_from_cache(cache_file)
                    log.info("loaded_precomputed_indexes_from_cache")
                    return
                except Exception as e:
                    log.warning("failed_to_load_cache", error=str(e))

        # Build indexes from scratch
        log.info("building_precomputed_indexes")
        self._build_indexes()
        self._save_to_cache(cache_file)

    def _build_indexes(self):
        """Build all pre-computed indexes from the schema graph."""
        # Build table indexes
        for table_name in self.schema_graph.list_all_tables():
            self._build_table_index(table_name)

        # Build relationship indexes
        self._build_relationship_indexes()

        # Compute join distances
        self._compute_join_distances()

        log.info(
            "precomputed_indexes_built",
            table_count=len(self.table_indexes),
            relationship_count=len(self.relationship_index.foreign_keys),
        )

    def _build_table_index(self, table_name: str):
        """Build pre-computed index for a single table."""
        # Get all table information
        columns = self.schema_graph.get_table_columns(table_name)
        primary_keys = self.schema_graph.get_table_pks(table_name)
        sticky_columns = self.schema_graph.get_table_sticky_columns(table_name)

        # Get relationships
        referenced_tables = self.schema_graph.get_referenced_tables(table_name)
        referencing_tables = self.schema_graph.get_referencing_tables(table_name)
        neighbor_tables = self.schema_graph.get_neighbor_tables({table_name})

        # Get foreign key columns
        foreign_key_columns = {}
        if hasattr(self.schema_graph, "_fk_map"):
            for fk_cols, ref_table, ref_cols in self.schema_graph._fk_map.get(
                table_name, []
            ):
                for fk_col, ref_col in zip(fk_cols, ref_cols):
                    foreign_key_columns[fk_col] = (ref_table, ref_col)

        # Get column descriptions
        column_descriptions = {}
        for col in columns:
            desc = self.schema_graph.get_column_comment(table_name, col)
            if desc:
                column_descriptions[col] = desc

        # Create table index
        self.table_indexes[table_name] = TableIndex(
            table_name=table_name,
            columns=columns,
            primary_keys=primary_keys,
            sticky_columns=sticky_columns,
            referenced_tables=referenced_tables,
            referencing_tables=referencing_tables,
            neighbor_tables=neighbor_tables,
            foreign_key_columns=foreign_key_columns,
            column_descriptions=column_descriptions,
        )

    def _build_relationship_indexes(self):
        """Build pre-computed relationship indexes."""
        # Process all foreign keys
        for table_name, table_index in self.table_indexes.items():
            # Initialize join graph entry
            if table_name not in self.relationship_index.join_graph:
                self.relationship_index.join_graph[table_name] = set()

            # Process foreign keys from this table
            for fk_col, (ref_table, ref_col) in table_index.foreign_key_columns.items():
                # Add to foreign keys index
                key = (table_name, ref_table)
                if key not in self.relationship_index.foreign_keys:
                    self.relationship_index.foreign_keys[key] = []
                self.relationship_index.foreign_keys[key].append((fk_col, ref_col))

                # Update join graph
                self.relationship_index.join_graph[table_name].add(ref_table)
                if ref_table not in self.relationship_index.join_graph:
                    self.relationship_index.join_graph[ref_table] = set()
                self.relationship_index.join_graph[ref_table].add(table_name)

    def _compute_join_distances(self):
        """Pre-compute minimum join distances between all table pairs using BFS."""
        all_tables = list(self.table_indexes.keys())

        for start_table in all_tables:
            distances = {start_table: 0}
            queue = [start_table]
            visited = {start_table}

            while queue:
                current = queue.pop(0)
                current_distance = distances[current]

                # Get neighbors
                neighbors = self.relationship_index.join_graph.get(current, set())

                for neighbor in neighbors:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        distances[neighbor] = current_distance + 1
                        queue.append(neighbor)

            self.relationship_index.join_distances[start_table] = distances

    def _save_to_cache(self, cache_file: Path):
        """Save indexes to cache file."""
        try:
            cache_data = {
                "table_indexes": self.table_indexes,
                "relationship_index": self.relationship_index,
            }
            with open(cache_file, "wb") as f:
                pickle.dump(cache_data, f)
            log.info("saved_precomputed_indexes_to_cache", path=str(cache_file))
        except Exception as e:
            log.warning("failed_to_save_cache", error=str(e))

    def _load_from_cache(self, cache_file: Path):
        """Load indexes from cache file."""
        with open(cache_file, "rb") as f:
            cache_data = pickle.load(f)
        self.table_indexes = cache_data["table_indexes"]
        self.relationship_index = cache_data["relationship_index"]

    # Query methods for optimized retrieval

    def get_table_index(self, table_name: str) -> Optional[TableIndex]:
        """Get pre-computed index for a table."""
        return self.table_indexes.get(table_name)

    def get_tables_within_distance(
        self, source_tables: Set[str], max_distance: int = 1
    ) -> Set[str]:
        """Get all tables within a certain join distance from source tables.

        Args:
            source_tables: Set of starting tables
            max_distance: Maximum join distance (default 1 = direct neighbors)

        Returns:
            Set of table names within the specified distance
        """
        result = set()

        for source in source_tables:
            if source not in self.relationship_index.join_distances:
                continue

            distances = self.relationship_index.join_distances[source]
            for table, distance in distances.items():
                if distance <= max_distance:
                    result.add(table)

        return result

    def get_join_path(self, from_table: str, to_table: str) -> Optional[List[str]]:
        """Get the shortest join path between two tables.

        Args:
            from_table: Starting table
            to_table: Target table

        Returns:
            List of tables forming the shortest path, or None if no path exists
        """
        if from_table not in self.table_indexes or to_table not in self.table_indexes:
            return None

        if from_table == to_table:
            return [from_table]

        # BFS to find shortest path
        queue = [(from_table, [from_table])]
        visited = {from_table}

        while queue:
            current, path = queue.pop(0)
            neighbors = self.relationship_index.join_graph.get(current, set())

            for neighbor in neighbors:
                if neighbor == to_table:
                    return path + [neighbor]

                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return None

    def get_common_join_tables(self, tables: Set[str]) -> Set[str]:
        """Get tables that can join with all specified tables.

        Args:
            tables: Set of tables to find common joins for

        Returns:
            Set of tables that can join with all input tables
        """
        if not tables:
            return set()

        # Start with neighbors of first table
        first_table = next(iter(tables))
        candidates = self.table_indexes[first_table].neighbor_tables.copy()

        # Intersect with neighbors of remaining tables
        for table in tables:
            if table != first_table:
                table_neighbors = self.table_indexes[table].neighbor_tables
                candidates &= table_neighbors

        return candidates

    def get_expanded_schema_fast(
        self, initial_tables: Set[str], max_expansion: int = 1
    ) -> Tuple[Set[str], Dict[str, List[str]]]:
        """Fast schema expansion using pre-computed indexes.

        Args:
            initial_tables: Set of initial table names
            max_expansion: Maximum expansion distance (hops)

        Returns:
            Tuple of (expanded_tables, sticky_columns_by_table)
        """
        expanded_tables = self.get_tables_within_distance(initial_tables, max_expansion)

        # Collect sticky columns for all expanded tables
        sticky_columns_by_table = {}
        for table in expanded_tables:
            table_index = self.table_indexes.get(table)
            if table_index and table_index.sticky_columns:
                sticky_columns_by_table[table] = table_index.sticky_columns

        return expanded_tables, sticky_columns_by_table
