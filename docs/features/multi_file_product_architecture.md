# Multi-File Data Product Architecture

## Current State Analysis

### How It Works Now
1. **File Upload**: Multiple files are uploaded together
2. **Storage**: Each file is saved to disk in a session directory
3. **Loading**: Each file becomes a separate table in DuckDB
4. **Querying**: Users can query across tables using SQL joins

### Current Limitations
- No automatic relationship detection
- No validation of referential integrity
- No guidance on how tables relate
- Limited metadata about the "data product" as a whole
- No optimization for common query patterns

## Proposed Architecture: Multi-File as Data Product

### Core Concepts

#### 1. Data Product Definition
A "Data Product" is a collection of related files that together form a cohesive dataset. Examples:
- E-commerce: `customers.csv`, `orders.csv`, `products.csv`, `order_items.csv`
- HR System: `employees.csv`, `departments.csv`, `salaries.csv`, `positions.csv`
- Financial: `transactions.csv`, `accounts.csv`, `customers.csv`, `branches.csv`

#### 2. Relationship Detection

**Automatic Detection Strategies:**
```python
class RelationshipDetector:
    def detect_relationships(self, tables: List[TableInfo]) -> List[TableRelationship]:
        relationships = []
        
        # Strategy 1: Foreign Key Pattern (table_id in other tables)
        for table in tables:
            potential_pk = f"{table.name}_id"
            for other_table in tables:
                if other_table != table:
                    for column in other_table.columns:
                        if column.name.lower() == potential_pk.lower():
                            relationships.append(
                                TableRelationship(
                                    from_table=table.name,
                                    from_column="id",
                                    to_table=other_table.name,
                                    to_column=column.name,
                                    relationship_type="one_to_many"
                                )
                            )
        
        # Strategy 2: Common Column Names (likely join columns)
        for t1 in tables:
            for t2 in tables:
                if t1.name < t2.name:  # Avoid duplicates
                    common_columns = set(c.name for c in t1.columns) & set(c.name for c in t2.columns)
                    for col in common_columns:
                        if col.endswith('_id') or col in ['id', 'code', 'key']:
                            relationships.append(
                                TableRelationship(
                                    from_table=t1.name,
                                    from_column=col,
                                    to_table=t2.name,
                                    to_column=col,
                                    relationship_type="many_to_many"  # Conservative assumption
                                )
                            )
        
        # Strategy 3: Data Analysis (check actual values)
        # Check if values in one column are a subset of values in another
        
        return relationships
```

#### 3. Data Validation

**Referential Integrity Checks:**
```python
class DataProductValidator:
    async def validate_relationships(
        self, 
        connection: duckdb.DuckDBPyConnection,
        relationships: List[TableRelationship]
    ) -> List[ValidationIssue]:
        issues = []
        
        for rel in relationships:
            # Check if all foreign key values exist in parent table
            orphan_check = f"""
                SELECT COUNT(*) as orphan_count
                FROM "{rel.to_table}" t1
                LEFT JOIN "{rel.from_table}" t2 
                ON t1."{rel.to_column}" = t2."{rel.from_column}"
                WHERE t2."{rel.from_column}" IS NULL 
                AND t1."{rel.to_column}" IS NOT NULL
            """
            
            result = connection.execute(orphan_check).fetchone()
            if result[0] > 0:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        message=f"Found {result[0]} orphaned records in {rel.to_table}.{rel.to_column}",
                        suggestion=f"Consider adding missing records to {rel.from_table} or removing orphaned records"
                    )
                )
        
        return issues
```

#### 4. Enhanced Schema Model

```python
@dataclass
class DataProduct:
    """Represents a collection of related data files."""
    id: str
    name: str
    description: Optional[str]
    files: List[DataFile]
    tables: List[TableInfo]
    relationships: List[TableRelationship]
    metadata: DataProductMetadata
    validation_status: ValidationStatus
    created_at: datetime
    
@dataclass
class DataFile:
    """Individual file within a data product."""
    filename: str
    size_bytes: int
    row_count: int
    table_name: str
    file_type: str  # csv, xlsx, json, etc.
    
@dataclass
class DataProductMetadata:
    """Metadata about the data product."""
    domain: Optional[str]  # e.g., "e-commerce", "finance", "hr"
    tags: List[str]
    business_description: Optional[str]
    recommended_queries: List[str]
    common_metrics: List[MetricDefinition]
```

#### 5. Query Assistance

**Intelligent Query Suggestions Based on Relationships:**
```python
class MultiTableQueryGenerator:
    def generate_join_queries(self, data_product: DataProduct) -> List[str]:
        suggestions = []
        
        # Generate JOIN templates
        for rel in data_product.relationships:
            if rel.relationship_type == "one_to_many":
                suggestions.append(
                    f"-- Join {rel.from_table} with {rel.to_table}\n"
                    f"SELECT t1.*, t2.*\n"
                    f"FROM {rel.from_table} t1\n"
                    f"JOIN {rel.to_table} t2 ON t1.{rel.from_column} = t2.{rel.to_column}"
                )
        
        # Generate aggregation queries
        for table in data_product.tables:
            numeric_columns = [c for c in table.columns if c.data_type in numeric_types]
            if numeric_columns and data_product.relationships:
                # Find related dimension tables
                for rel in data_product.relationships:
                    if rel.to_table == table.name:
                        suggestions.append(
                            f"-- Aggregate {table.name} by {rel.from_table}\n"
                            f"SELECT t1.name, SUM(t2.{numeric_columns[0].name}) as total\n"
                            f"FROM {rel.from_table} t1\n"
                            f"JOIN {table.name} t2 ON t1.{rel.from_column} = t2.{rel.to_column}\n"
                            f"GROUP BY t1.name"
                        )
        
        return suggestions
```

#### 6. UI/UX Enhancements

**Data Product Upload Flow:**
1. **Upload Multiple Files**: Drag and drop multiple related files
2. **Relationship Detection**: System analyzes and suggests relationships
3. **Validation**: Show data quality issues and suggestions
4. **Confirmation**: User confirms or adjusts detected relationships
5. **Ready to Query**: Enhanced suggestions based on the full data model

**Visual Schema Explorer:**
```typescript
interface SchemaGraphProps {
  dataProduct: DataProduct;
  onTableClick: (table: string) => void;
  onRelationshipClick: (rel: TableRelationship) => void;
}

export function SchemaGraph({ dataProduct }: SchemaGraphProps) {
  // Render interactive graph showing:
  // - Tables as nodes
  // - Relationships as edges
  // - Row counts and key columns
  // - Click to explore or query
}
```

## Implementation Plan

### Phase 1: Core Infrastructure (Week 1)
1. Extend `DataSource` model to support `DataProduct` concept
2. Implement `RelationshipDetector` for automatic relationship discovery
3. Add `DataProductValidator` for data integrity checks
4. Update `UnifiedSchema` to include relationship information

### Phase 2: Enhanced Processing (Week 2)
1. Modify `create_file_source` to detect relationships
2. Add validation step after loading files
3. Store relationship metadata in schema
4. Update `SchemaExtractor` to extract relationships

### Phase 3: Query Enhancement (Week 3)
1. Update `LLMQuerySuggestionGenerator` to use relationships
2. Add join query templates to suggestions
3. Implement `MultiTableQueryGenerator`
4. Enhance SQL generation to prefer detected relationships

### Phase 4: UI/UX Improvements (Week 4)
1. Add relationship visualization component
2. Show validation warnings in upload flow
3. Enhanced query suggestions for multi-table queries
4. Add "common queries" based on detected data model

## Example Use Cases

### E-commerce Dataset
Files: `customers.csv`, `orders.csv`, `products.csv`, `order_items.csv`

**Automatic Detection Results:**
- `orders.customer_id` → `customers.id` (many-to-one)
- `order_items.order_id` → `orders.id` (many-to-one)
- `order_items.product_id` → `products.id` (many-to-one)

**Generated Suggestions:**
- "What is the total revenue by customer?"
- "Which products are frequently bought together?"
- "Show customer lifetime value"
- "What are the top-selling products by category?"

### HR Dataset
Files: `employees.csv`, `departments.csv`, `salaries.csv`

**Automatic Detection Results:**
- `employees.department_id` → `departments.id` (many-to-one)
- `salaries.employee_id` → `employees.id` (many-to-one)

**Generated Suggestions:**
- "What is the average salary by department?"
- "Show salary progression for each employee"
- "Which department has the highest payroll?"
- "List employees with above-average salaries in their department"

## Benefits

1. **Better User Experience**: Users don't need to manually specify relationships
2. **Data Quality**: Automatic validation catches common issues
3. **Smarter Queries**: LLM has full context about relationships
4. **Reduced Errors**: Fewer incorrect joins and orphaned records
5. **Business Context**: Queries are more relevant to the actual data model

## Technical Considerations

1. **Performance**: Relationship detection should be fast (use sampling for large files)
2. **Storage**: Cache detected relationships to avoid re-computation
3. **Flexibility**: Allow users to override automatic detection
4. **Scalability**: Handle datasets with many tables (10+)
5. **Security**: Ensure relationship detection doesn't expose sensitive patterns

## Future Enhancements

1. **Schema Evolution**: Track changes when files are re-uploaded
2. **Data Lineage**: Show how data flows between tables
3. **Impact Analysis**: Warn if removing a file breaks relationships
4. **Template Library**: Pre-built queries for common data models
5. **ML-Based Detection**: Use machine learning to improve relationship detection