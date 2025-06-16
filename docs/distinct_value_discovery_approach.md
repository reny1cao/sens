# SELECT DISTINCT Approach for Value Discovery

## The Insight
Instead of building complex mapping tools, we can enhance the agent's exploration capabilities to discover actual column values using SELECT DISTINCT queries. This is simpler, more direct, and always returns real database values.

## How It Would Work

### 1. **Enhanced Exploration Pattern**
Current agent pattern:
1. Explore tables → 2. Explore columns → 3. Generate SQL

New pattern:
1. Explore tables → 2. Explore columns → 3. **Explore values** → 4. Generate SQL with correct values

### 2. **Value Discovery Queries**

When the agent needs to find values for a WHERE clause:

```sql
-- For company names/symbols
SELECT DISTINCT symbol, company_name
FROM securities
WHERE company_name ILIKE '%Microsoft%'
   OR symbol ILIKE '%MSFT%'
LIMIT 10;

-- For all symbols (when unsure)
SELECT DISTINCT symbol
FROM securities
ORDER BY symbol
LIMIT 20;

-- For date ranges
SELECT MIN(trade_date) as earliest,
       MAX(trade_date) as latest
FROM daily_prices;

-- For sectors
SELECT DISTINCT sector
FROM securities
WHERE sector IS NOT NULL;
```

### 3. **Agent Integration Example**

```python
# In agent's reasoning
thought: "User mentioned 'Microsoft'. I need to find the correct symbol value."

# New action type: EXPLORE_VALUES
action: {
    "type": "EXPLORE_DATABASE",
    "parameters": {
        "query": "SELECT DISTINCT symbol, company_name FROM securities WHERE company_name ILIKE '%Microsoft%' LIMIT 5"
    }
}

# Result
observation: {
    "columns": ["symbol", "company_name"],
    "data": [
        ["MSFT", "Microsoft Corporation"]
    ]
}

# Agent learns
thought: "Found that Microsoft Corporation has symbol 'MSFT'. I'll use this in my query."
```

## Advantages Over Complex Mapping Tool

1. **Simplicity**: No new tools needed, just smarter use of EXPLORE_DATABASE
2. **Accuracy**: Always returns actual database values
3. **Self-updating**: Automatically handles new data
4. **Transparent**: Agent can see and reason about the values
5. **No maintenance**: No mapping tables to update

## Implementation Strategy

### Phase 1: Teach Pattern Recognition
Enhance the agent's reasoning to recognize when it needs values:
- "Show me X stock" → Need to find symbol for X
- "In sector Y" → Need to find valid sector values
- "Company Z" → Need to map to database identifier

### Phase 2: Smart Value Queries
Train the agent on efficient value discovery queries:
```python
VALUE_DISCOVERY_PATTERNS = {
    "symbol_search": """
        SELECT DISTINCT symbol, company_name
        FROM securities
        WHERE company_name ILIKE %s OR symbol ILIKE %s
        LIMIT 10
    """,

    "list_all_values": """
        SELECT DISTINCT {column}
        FROM {table}
        WHERE {column} IS NOT NULL
        ORDER BY {column}
        LIMIT 20
    """,

    "date_range": """
        SELECT MIN({date_column}) as earliest,
               MAX({date_column}) as latest
        FROM {table}
    """,

    "value_frequency": """
        SELECT {column}, COUNT(*) as frequency
        FROM {table}
        GROUP BY {column}
        ORDER BY frequency DESC
        LIMIT 10
    """
}
```

### Phase 3: Reasoning Enhancement
Teach the agent when and how to use these queries:

```python
# Reasoning patterns to add
reasoning_patterns = [
    {
        "trigger": "user mentions company name",
        "action": "explore distinct symbols and company names",
        "query_template": "symbol_search"
    },
    {
        "trigger": "need values for WHERE clause",
        "action": "explore distinct values in target column",
        "query_template": "list_all_values"
    },
    {
        "trigger": "temporal query",
        "action": "find date range in table",
        "query_template": "date_range"
    }
]
```

## Example Scenarios

### Scenario 1: Company Name to Symbol
```
User: "Show me Apple stock prices"
Agent thinks: "Need to find symbol for Apple"
Agent explores: SELECT DISTINCT symbol, company_name FROM securities WHERE company_name ILIKE '%Apple%'
Agent discovers: [["AAPL", "Apple Inc."]]
Agent uses: WHERE symbol = 'AAPL'
```

### Scenario 2: Valid Sectors
```
User: "Average volume by sector"
Agent thinks: "Need to know what sectors exist"
Agent explores: SELECT DISTINCT sector FROM securities ORDER BY sector
Agent discovers: ["Consumer", "Energy", "ETF", "Finance", "Healthcare", "Technology"]
Agent generates: GROUP BY sector (knowing all values are valid)
```

### Scenario 3: Date Ranges
```
User: "Data from last quarter"
Agent thinks: "Need to know data availability"
Agent explores: SELECT MIN(trade_date), MAX(trade_date) FROM daily_prices
Agent discovers: ["2023-01-01", "2024-12-31"]
Agent reasons: "Last quarter of available data is Q4 2024"
```

## Comparison: Distinct vs Mapping Tool

| Aspect | SELECT DISTINCT | Mapping Tool |
|--------|----------------|--------------|
| Complexity | Low - uses existing tools | High - new tool needed |
| Accuracy | 100% - real values | Depends on mapping quality |
| Maintenance | None | Requires updates |
| Performance | Fast with indexes | Fast with caching |
| Learning Curve | Small - familiar SQL | Large - new concepts |
| Flexibility | High | Medium |

## Minimal Implementation

To implement this, we only need to:

1. **Update Agent's Reasoning** to recognize when value discovery is needed
2. **Add Examples** of value discovery queries to the agent's knowledge
3. **No New Tools** - just smarter use of EXPLORE_DATABASE

## Temporal Handling

For temporal expressions, combine with simple date parsing:
```python
# Agent could learn patterns like:
"last month" → explore MAX(trade_date), then subtract 1 month
"Q4 2024" → use DATE '2024-10-01' AND DATE '2024-12-31'
"yesterday" → CURRENT_DATE - 1
```

## Conclusion

Using SELECT DISTINCT for value discovery is a elegantly simple solution that:
- Leverages existing agent capabilities
- Provides accurate, real-time value mapping
- Requires minimal implementation effort
- Scales naturally with the database

This approach transforms the agent from guessing values to discovering them, making it much more reliable and easier to maintain.
