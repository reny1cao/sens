# Agent Improvement Plan Based on Testing

## Current Agent Behavior Analysis

### What's Working ✅
1. **Database Exploration**: Agent successfully explores database structure
2. **Table Discovery**: Finds relevant tables (daily_prices, securities, etc.)
3. **Schema Understanding**: Discovers columns and their types
4. **Basic SQL Generation**: Can generate simple SELECT queries

### Key Issues Identified ❌

#### 1. **Inefficient Exploration Pattern**
- Agent starts with `information_schema` queries instead of using direct knowledge
- Multiple exploration steps for basic queries (3-5 steps for simple price lookups)
- Doesn't leverage the schema that's already loaded in memory

#### 2. **Value Mapping Failures**
- Cannot map "Apple" → "AAPL" without exploration
- No fuzzy matching for company names
- Case sensitivity issues (aapl vs AAPL)

#### 3. **Missing Temporal Reasoning**
- Struggles with "yesterday", "last week" date calculations
- Doesn't understand partitioned table structure (daily_prices_YYYY_MM)
- Queries wrong tables for date ranges

#### 4. **Limited Tools in Minimal Mode**
- SEARCH_VALUES: Disabled (returns error)
- FIND_SIMILAR_VALUES: Disabled (returns error)
- DIAGNOSE_EMPTY_RESULTS: Disabled (returns error)
- Only 3 tools active: EXPLORE_DATABASE, GENERATE_SQL, EXECUTE_SQL

## Recommended Improvements (Priority Order)

### Phase 1: Enable Core Tools (Immediate)

#### 1. **Enable SEARCH_VALUES Tool**
```python
# Current: Returns error "Value search disabled in minimal mode"
# Fix: Implement actual value search using the embedding index

async def search_values(self, table: str, column: str, search_term: str):
    """Search for values in a specific column."""
    # Use the existing embedding index to find similar values
    results = await self.retriever.search_column_values(
        table=table,
        column=column,
        search_term=search_term,
        limit=10
    )
    return results
```

**Impact**: Resolves company name → ticker mapping issues

#### 2. **Enable FIND_SIMILAR_VALUES Tool**
```python
# Implement fuzzy matching for user terms
async def find_similar_values(self, user_term: str, table: str, column: str):
    """Find database values similar to user term."""
    # Use Levenshtein distance for fuzzy matching
    # Use embeddings for semantic similarity
    # Return ranked list of matches with confidence scores
```

**Impact**: Handles typos, variations, partial matches

#### 3. **Optimize Initial Schema Loading**
```python
# Agent should start with pre-loaded schema context
def __init__(self):
    self.schema_context = SchemaGraph.get_instance()
    self.known_tables = self.schema_context.get_all_tables()
    self.sticky_columns = self.schema_context.get_sticky_columns()
```

**Impact**: Reduces unnecessary exploration queries

### Phase 2: Improve Reasoning (Week 1)

#### 1. **Better Action Selection Logic**
```python
# Current: Always explores database first
# Improved: Check if we already have the information

if self._has_sufficient_schema_info(state):
    # Skip exploration, go directly to SQL generation
    return AgentAction(ActionType.GENERATE_SQL, ...)
```

#### 2. **Temporal Query Handler**
```python
# Add date calculation utilities
def calculate_date_range(temporal_expression: str) -> tuple[date, date]:
    """Convert 'yesterday', 'last week' to actual dates."""
    # Handle relative dates
    # Map to correct partitioned tables
```

#### 3. **Smart Table Selection**
```python
# For partitioned tables, select the right partition
def select_partition(date_range: tuple[date, date]) -> list[str]:
    """Select daily_prices_YYYY_MM tables for date range."""
```

### Phase 3: Value Discovery System (Week 2)

#### 1. **Build Value Index on Startup**
```python
# Pre-index common values from important columns
async def build_value_index():
    """Index values from sticky columns."""
    for table in ['securities', 'daily_prices']:
        for column in ['symbol', 'company_name']:
            values = await get_distinct_values(table, column)
            index_values(values)
```

#### 2. **Implement Mapping Cache**
```python
# Cache discovered mappings
class ValueMappingCache:
    def __init__(self):
        self.mappings = {
            # Pre-populate common mappings
            "apple": "AAPL",
            "microsoft": "MSFT",
            "google": "GOOGL",
            # Case variations
            "aapl": "AAPL",
            "msft": "MSFT",
        }
```

### Phase 4: Self-Correction (Week 3)

#### 1. **Enable DIAGNOSE_EMPTY_RESULTS**
```python
async def diagnose_empty_results(self, sql: str, filters: dict):
    """Diagnose why a query returned no results."""
    # Check if filter values exist in database
    # Suggest alternative values
    # Recommend broader filters
```

#### 2. **Implement Retry Strategies**
```python
# When queries fail, try alternatives
if result.row_count == 0:
    # Try case-insensitive search
    # Try partial matches
    # Broaden date ranges
```

## Quick Wins (Can Implement Today)

1. **Case-Insensitive Matching**
   ```sql
   -- Instead of: WHERE symbol = 'aapl'
   -- Use: WHERE UPPER(symbol) = UPPER('aapl')
   ```

2. **Common Mappings Dictionary**
   ```python
   COMMON_MAPPINGS = {
       "apple": "AAPL",
       "microsoft": "MSFT",
       "google": "GOOGL",
       "amazon": "AMZN",
       "tesla": "TSLA",
   }
   ```

3. **Skip Schema Exploration**
   ```python
   # If schema is already loaded, use it directly
   if self.schema_graph.has_table("daily_prices"):
       # Generate SQL without exploration
   ```

4. **Better Exploration Queries**
   ```sql
   -- Instead of: SELECT * FROM table LIMIT 5
   -- Use: SELECT DISTINCT symbol FROM securities WHERE symbol LIKE 'A%' LIMIT 10
   ```

## Success Metrics

- **Reduction in Steps**: From 5+ to 2-3 for simple queries
- **Success Rate**: From ~60% to 90%+ for common queries
- **Response Time**: From 15-30s to under 5s
- **Value Mapping**: 95%+ success for company names
- **Self-Correction**: 80%+ recovery from initial failures

## Implementation Priority

1. **Today**: Enable SEARCH_VALUES with basic implementation
2. **Tomorrow**: Add case-insensitive matching and common mappings
3. **This Week**: Implement FIND_SIMILAR_VALUES and temporal reasoning
4. **Next Week**: Full value discovery system and self-correction

The agent has a solid foundation but is operating with most tools disabled. Enabling these tools will dramatically improve performance and user experience.
