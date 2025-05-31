# Schema Extraction & Multi-DataSource Architecture

## Overview

SENS supports multiple data sources with different schema extraction mechanisms. This document outlines the current architecture, issues, and roadmap for improvements.

## Current Architecture

### 1. Schema Extraction Paths

#### PostgreSQL Database
- **Script**: `/scripts/extract_schema.py`
- **Core Module**: `/src/sens/schema/schema_extractor.py`
- **Features**:
  - Full relationship extraction (including composite foreign keys)
  - Sticky column identification (high-value identifiers)
  - Data pattern analysis
  - LLM-friendly format generation
  - Outputs: `schema_metadata.json` and `schema_for_llm.txt`

#### Uploaded Files (CSV/Excel)
- **Module**: `/src/sens/datasource/manager.py`
- **Process**:
  - Creates temporary DuckDB database
  - Extracts basic schema from information_schema
  - Session-based with 24-hour TTL
  - No relationship detection
  - Simple column type mapping

### 2. Available Scripts

```bash
# Extract schema from PostgreSQL database
python scripts/extract_schema.py

# Build FAISS embedding index for semantic search
python scripts/build_embedding_index.py
```

### 3. Data Source Types

```python
class DataSourceType(Enum):
    DEFAULT_POSTGRES = "default_postgres"
    UPLOADED_FILE = "uploaded_file"
    CONNECTED_DB = "connected_db"  # Planned
```

## Current Issues

### 1. Schema Format Mismatch
- **Problem**: LLM components expect PostgreSQL-style schema format
- **Impact**: "Invalid schema context structure" errors for uploaded files
- **Root Cause**: Different schema extraction paths produce incompatible formats

### 2. Static Query Suggestions
- **Problem**: Frontend shows hardcoded examples like "How many users do we have?"
- **Impact**: Irrelevant suggestions for uploaded data
- **Solution**: `QuerySuggestionGenerator` exists but isn't integrated

### 3. Pipeline Integration Issues
- **Problem**: SessionAwarePipeline assumes SchemaGraph singleton
- **Impact**: Pipeline fails for uploaded files
- **Root Cause**: SchemaGraph designed for static PostgreSQL schema

## Solution Architecture

### Phase 1: Immediate Fixes

#### 1. Format Uploaded Schema for LLM
Create a converter that transforms DuckDB schema to LLM-friendly format:

```python
def format_uploaded_schema_for_llm(schema_dict: Dict) -> Dict:
    """Convert DuckDB schema to LLM-compatible format.
    
    - Extract column types and map to semantic types
    - Analyze sample data for pattern detection
    - Generate basic sticky columns (ID fields, unique identifiers)
    - Format for IntentExtractor compatibility
    """
```

#### 2. Dynamic Query Suggestions
Integrate the existing QuerySuggestionGenerator:

```python
# In DataSourceResponse, add:
query_suggestions: List[str] = Field(default_factory=list)

# Generate based on:
- Column types (numeric → aggregations)
- Column names (date → time-based queries)
- Data patterns (categories → grouping)
```

#### 3. Simplified Pipeline for Uploaded Files
- Make SchemaGraph truly optional
- Pass formatted schema directly to LLM components
- Maintain compatibility with existing pipeline

### Phase 2: Multi-DataSource Support

Based on `/docs/data_source_architecture.md`:

#### Configuration
```python
DATA_SOURCES = {
    'primary': os.getenv('SENS_DB_URL'),
    'analytics': os.getenv('SENS_ANALYTICS_DB_URL'),
    'uploaded': 'duckdb://session/{session_id}'
}
```

#### Features
- Named data sources
- Per-source schema extraction
- Source-aware query routing
- Cross-database query support (future)

### Phase 3: Advanced Features

#### Potential Linked Files
For uploaded files, consider:
- Detecting relationships between multiple CSVs
- Common column analysis
- Automatic JOIN suggestions
- Virtual foreign key detection

#### User Database Connections
- OAuth/connection pooling
- Schema caching
- Security isolation
- Rate limiting

## Implementation Priority

1. **Format Schema for LLM** (Current Focus)
   - Create schema converter
   - Test with IntentExtractor
   - Ensure pipeline compatibility

2. **Dynamic Query Suggestions**
   - Wire QuerySuggestionGenerator to API
   - Pass to frontend
   - Replace static examples

3. **Pipeline Fixes**
   - Refactor SchemaGraph usage
   - Support multiple schema formats
   - Maintain backward compatibility

## Schema Format Examples

### PostgreSQL Format (Expected by LLM)
```
Table users {
  # Primary identifiers:
  #   - email
  #   - username
  id: bigint (primary key) (not null)
  email: varchar (unique) (sticky)
  username: varchar (not null) (sticky)
  created_at: timestamp
}
```

### DuckDB Format (Current)
```json
{
  "tables": {
    "users": {
      "columns": [
        {"name": "id", "data_type": "BIGINT"},
        {"name": "email", "data_type": "VARCHAR"},
        {"name": "username", "data_type": "VARCHAR"},
        {"name": "created_at", "data_type": "TIMESTAMP"}
      ]
    }
  }
}
```

### Target Unified Format
```json
{
  "tables": ["users"],
  "columns": [
    {"table": "users", "column": "id", "type": "bigint", "is_primary": true},
    {"table": "users", "column": "email", "type": "varchar", "is_sticky": true},
    {"table": "users", "column": "username", "type": "varchar", "is_sticky": true}
  ],
  "relationships": [],
  "metadata": {
    "source_type": "uploaded_file",
    "extraction_method": "duckdb_information_schema"
  }
}
```

## Testing Strategy

1. **Unit Tests**
   - Schema format conversion
   - Query suggestion generation
   - Pipeline component isolation

2. **Integration Tests**
   - End-to-end file upload → query execution
   - Multiple file handling
   - Session management

3. **Performance Tests**
   - Large file handling
   - Concurrent sessions
   - Schema extraction speed

## Security Considerations

- Session isolation for uploaded files
- SQL injection prevention in DuckDB
- File size and type validation
- Rate limiting for uploads
- Data retention policies

## Future Enhancements

1. **Smart Schema Detection**
   - Infer relationships from column names
   - Detect time series data
   - Identify hierarchical structures

2. **Schema Evolution**
   - Track schema changes
   - Version management
   - Migration support

3. **Advanced Analytics**
   - Automatic metric detection
   - Suggested visualizations
   - Anomaly detection queries