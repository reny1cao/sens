"""Automatic relationship detection for multi-file data products."""

import re
from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict
import structlog

from sens.schema.unified_schema import TableInfo, ColumnInfo, DataType, ForeignKeyInfo

logger = structlog.get_logger(__name__)


class RelationshipDetector:
    """Detects relationships between tables in a multi-file dataset."""
    
    def __init__(self):
        # Common patterns for primary/foreign keys
        self.pk_patterns = [
            re.compile(r'^id$', re.IGNORECASE),
            re.compile(r'^(.+)_id$', re.IGNORECASE),
            re.compile(r'^(.+)_code$', re.IGNORECASE),
            re.compile(r'^(.+)_key$', re.IGNORECASE),
        ]
        
        # Patterns that indicate a foreign key
        self.fk_patterns = [
            re.compile(r'^(.+)_id$', re.IGNORECASE),
            re.compile(r'^fk_(.+)$', re.IGNORECASE),
            re.compile(r'^(.+)_fk$', re.IGNORECASE),
        ]
        
        # Common dimension table names
        self.dimension_tables = {
            'customer', 'user', 'product', 'category', 'department',
            'employee', 'location', 'store', 'branch', 'region',
            'vendor', 'supplier', 'account', 'project'
        }
        
        # Common fact table names
        self.fact_tables = {
            'order', 'sale', 'transaction', 'payment', 'invoice',
            'shipment', 'inventory', 'event', 'activity', 'log'
        }
    
    def detect_relationships(
        self, 
        tables: List[TableInfo],
        sample_data: Optional[Dict[str, List[Dict]]] = None
    ) -> List[ForeignKeyInfo]:
        """
        Detect relationships between tables using multiple strategies.
        
        Args:
            tables: List of table information
            sample_data: Optional sample data for each table for value-based detection
            
        Returns:
            List of detected foreign key relationships
        """
        relationships = []
        
        # Strategy 1: Name-based detection
        name_based = self._detect_by_naming_convention(tables)
        relationships.extend(name_based)
        
        # Strategy 2: Common column detection
        common_col = self._detect_by_common_columns(tables)
        relationships.extend(common_col)
        
        # Strategy 3: Data type matching
        type_based = self._detect_by_data_types(tables)
        relationships.extend(type_based)
        
        # Strategy 4: Value-based detection (if sample data provided)
        if sample_data:
            value_based = self._detect_by_values(tables, sample_data)
            relationships.extend(value_based)
        
        # Remove duplicates and conflicts
        relationships = self._deduplicate_relationships(relationships)
        
        # Score and rank relationships
        relationships = self._score_relationships(relationships, tables)
        
        logger.info("relationships_detected", 
                   count=len(relationships),
                   tables=len(tables))
        
        return relationships
    
    def _detect_by_naming_convention(self, tables: List[TableInfo]) -> List[ForeignKeyInfo]:
        """Detect relationships based on naming conventions."""
        relationships = []
        table_map = {t.name.lower(): t for t in tables}
        
        for table in tables:
            for column in table.columns:
                col_lower = column.name.lower()
                
                # Check if column matches foreign key pattern
                for pattern in self.fk_patterns:
                    match = pattern.match(col_lower)
                    if match:
                        # Extract potential table name
                        potential_table = match.group(1)
                        
                        # Check if this table exists
                        if potential_table in table_map:
                            # Look for primary key in referenced table
                            ref_table = table_map[potential_table]
                            pk_column = self._find_primary_key(ref_table)
                            
                            if pk_column:
                                relationships.append(
                                    ForeignKeyInfo(
                                        constraint_name=f"fk_{table.name}_{column.name}",
                                        column_name=column.name,
                                        referenced_table=ref_table.name,
                                        referenced_column=pk_column.name
                                    )
                                )
                        
                        # Also check plural forms
                        plural_forms = [
                            potential_table + 's',
                            potential_table + 'es',
                            potential_table[:-1] if potential_table.endswith('y') else potential_table + 'ies'
                        ]
                        
                        for plural in plural_forms:
                            if plural in table_map:
                                ref_table = table_map[plural]
                                pk_column = self._find_primary_key(ref_table)
                                
                                if pk_column:
                                    relationships.append(
                                        ForeignKeyInfo(
                                            constraint_name=f"fk_{table.name}_{column.name}",
                                            column_name=column.name,
                                            referenced_table=ref_table.name,
                                            referenced_column=pk_column.name
                                        )
                                    )
                                    break
        
        return relationships
    
    def _detect_by_common_columns(self, tables: List[TableInfo]) -> List[ForeignKeyInfo]:
        """Detect relationships based on common column names."""
        relationships = []
        
        # Build column index
        column_index = defaultdict(list)
        for table in tables:
            for column in table.columns:
                col_lower = column.name.lower()
                column_index[col_lower].append((table, column))
        
        # Find columns that appear in multiple tables
        for col_name, occurrences in column_index.items():
            if len(occurrences) > 1 and (col_name.endswith('_id') or col_name == 'id'):
                # Determine which table is the primary
                primary_table = None
                
                # Check if one table is clearly a dimension table
                for table, column in occurrences:
                    table_name_lower = table.name.lower()
                    if any(dim in table_name_lower for dim in self.dimension_tables):
                        if column.is_primary_key or col_name == 'id':
                            primary_table = table
                            break
                
                if primary_table:
                    # Create relationships from other tables to this primary table
                    for table, column in occurrences:
                        if table != primary_table:
                            relationships.append(
                                ForeignKeyInfo(
                                    constraint_name=f"fk_{table.name}_{column.name}",
                                    column_name=column.name,
                                    referenced_table=primary_table.name,
                                    referenced_column=col_name
                                )
                            )
        
        return relationships
    
    def _detect_by_data_types(self, tables: List[TableInfo]) -> List[ForeignKeyInfo]:
        """Detect relationships based on compatible data types."""
        relationships = []
        
        # Index all potential primary keys
        potential_pks = []
        for table in tables:
            pk = self._find_primary_key(table)
            if pk:
                potential_pks.append((table, pk))
        
        # Look for matching foreign keys
        for table in tables:
            for column in table.columns:
                if column.is_primary_key:
                    continue
                    
                # Check if this could be a foreign key
                if column.name.lower().endswith('_id') or '_id_' in column.name.lower():
                    # Find compatible primary keys
                    for pk_table, pk_column in potential_pks:
                        if pk_table == table:
                            continue
                            
                        # Check data type compatibility
                        if self._are_types_compatible(column.data_type, pk_column.data_type):
                            # Additional heuristic: table name similarity
                            if self._table_name_matches(column.name, pk_table.name):
                                relationships.append(
                                    ForeignKeyInfo(
                                        constraint_name=f"fk_{table.name}_{column.name}",
                                        column_name=column.name,
                                        referenced_table=pk_table.name,
                                        referenced_column=pk_column.name
                                    )
                                )
        
        return relationships
    
    def _detect_by_values(
        self, 
        tables: List[TableInfo],
        sample_data: Dict[str, List[Dict]]
    ) -> List[ForeignKeyInfo]:
        """Detect relationships by analyzing actual data values."""
        relationships = []
        
        # Build value sets for potential primary keys
        pk_values = {}
        for table in tables:
            if table.name not in sample_data:
                continue
                
            pk = self._find_primary_key(table)
            if pk:
                values = set()
                for row in sample_data[table.name]:
                    if pk.name in row and row[pk.name] is not None:
                        values.add(row[pk.name])
                
                if values:
                    pk_values[(table.name, pk.name)] = values
        
        # Check if foreign key candidates have values that are subsets
        for table in tables:
            if table.name not in sample_data:
                continue
                
            for column in table.columns:
                if column.is_primary_key or not column.name.lower().endswith('_id'):
                    continue
                
                # Get values for this column
                values = set()
                for row in sample_data[table.name]:
                    if column.name in row and row[column.name] is not None:
                        values.add(row[column.name])
                
                if not values:
                    continue
                
                # Check against all primary keys
                for (pk_table, pk_col), pk_vals in pk_values.items():
                    if pk_table == table.name:
                        continue
                    
                    # Check if this column's values are a subset of the PK values
                    if values.issubset(pk_vals):
                        coverage = len(values) / len(pk_vals) if pk_vals else 0
                        
                        # High coverage suggests a real relationship
                        if coverage > 0.1:  # At least 10% of PK values are referenced
                            relationships.append(
                                ForeignKeyInfo(
                                    constraint_name=f"fk_{table.name}_{column.name}",
                                    column_name=column.name,
                                    referenced_table=pk_table,
                                    referenced_column=pk_col
                                )
                            )
        
        return relationships
    
    def _find_primary_key(self, table: TableInfo) -> Optional[ColumnInfo]:
        """Find the primary key column in a table."""
        # First check for explicitly marked primary key
        for column in table.columns:
            if column.is_primary_key:
                return column
        
        # Then check common patterns
        for column in table.columns:
            col_lower = column.name.lower()
            if col_lower == 'id' or col_lower == f"{table.name.lower()}_id":
                return column
        
        # Check for auto-increment integer columns
        for column in table.columns:
            if column.data_type in (DataType.INTEGER, DataType.BIGINT) and column.name.lower().endswith('_id'):
                return column
        
        return None
    
    def _are_types_compatible(self, type1: DataType, type2: DataType) -> bool:
        """Check if two data types are compatible for foreign key relationship."""
        # Exact match
        if type1 == type2:
            return True
        
        # Compatible numeric types
        numeric_types = {DataType.INTEGER, DataType.BIGINT, DataType.SMALLINT}
        if type1 in numeric_types and type2 in numeric_types:
            return True
        
        # Compatible string types
        string_types = {DataType.VARCHAR, DataType.CHAR, DataType.TEXT}
        if type1 in string_types and type2 in string_types:
            return True
        
        return False
    
    def _table_name_matches(self, column_name: str, table_name: str) -> bool:
        """Check if a column name suggests it references a table."""
        col_lower = column_name.lower()
        table_lower = table_name.lower()
        
        # Direct match: customer_id -> customer
        if col_lower == f"{table_lower}_id":
            return True
        
        # Singular/plural: customers_id -> customer
        if col_lower == f"{table_lower}s_id" or col_lower == f"{table_lower[:-1]}_id":
            return True
        
        # Partial match: cust_id -> customer
        if len(table_lower) > 4:
            prefix = table_lower[:4]
            if col_lower.startswith(prefix) and col_lower.endswith('_id'):
                return True
        
        return False
    
    def _deduplicate_relationships(self, relationships: List[ForeignKeyInfo]) -> List[ForeignKeyInfo]:
        """Remove duplicate and conflicting relationships."""
        # Use a dict to track unique relationships
        unique = {}
        
        for rel in relationships:
            key = (rel.column_name, rel.referenced_table, rel.referenced_column)
            
            if key not in unique:
                unique[key] = rel
            else:
                # Keep the one with better naming convention match
                existing = unique[key]
                if rel.constraint_name.startswith('fk_') and not existing.constraint_name.startswith('fk_'):
                    unique[key] = rel
        
        return list(unique.values())
    
    def _score_relationships(
        self, 
        relationships: List[ForeignKeyInfo],
        tables: List[TableInfo]
    ) -> List[ForeignKeyInfo]:
        """Score relationships by confidence and return sorted list."""
        # For now, return as-is
        # TODO: Implement scoring based on:
        # - Naming convention match strength
        # - Data type compatibility
        # - Value coverage
        # - Table type (fact vs dimension)
        
        return relationships


def detect_relationships(
    tables: List[TableInfo],
    sample_data: Optional[Dict[str, List[Dict]]] = None
) -> List[ForeignKeyInfo]:
    """Convenience function to detect relationships between tables."""
    detector = RelationshipDetector()
    return detector.detect_relationships(tables, sample_data)