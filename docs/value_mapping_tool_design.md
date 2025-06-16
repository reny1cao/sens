# Value Mapping Tool Design for SENS Agent

## Problem Statement
The agent struggles to map user terms to database values, particularly:
- Company names → Stock symbols ("Microsoft" → "MSFT")
- Temporal references → Date ranges ("last quarter" → specific dates)
- Industry terms → Database codes
- Natural language → Exact database values

## Proposed Tool: `discover_value_mapping`

### Core Concept
A smart value discovery tool that combines multiple strategies to find the correct database values for user terms.

```python
async def discover_value_mapping(
    user_term: str,
    target_column: str,
    target_table: str,
    context: Optional[str] = None,
    search_strategy: str = "auto"
) -> Dict[str, Any]:
    """
    Discover the correct database value for a user-provided term.

    Args:
        user_term: The term from the user query (e.g., "Microsoft", "last quarter")
        target_column: The database column to search (e.g., "symbol", "trade_date")
        target_table: The table containing the values (e.g., "securities", "daily_prices")
        context: Additional context from the user query
        search_strategy: One of "auto", "fuzzy", "semantic", "pattern", "temporal"

    Returns:
        {
            "found": True/False,
            "confidence": 0.0-1.0,
            "mapping": {
                "user_term": "Microsoft",
                "database_value": "MSFT",
                "column": "symbol",
                "table": "securities"
            },
            "alternatives": [...],  # Other possible matches
            "strategy_used": "fuzzy_match",
            "metadata": {...}
        }
    """
```

## Implementation Strategies

### 1. **Multi-Strategy Approach**
The tool should try multiple strategies in order of effectiveness:

```python
class ValueMappingStrategies:
    def __init__(self):
        self.strategies = [
            self.check_cache,           # 1. Check previous successful mappings
            self.exact_match,           # 2. Try exact match first
            self.case_insensitive,      # 3. Try case variations
            self.fuzzy_match,           # 4. Fuzzy string matching
            self.semantic_search,       # 5. Embedding-based search
            self.pattern_match,         # 6. Regex patterns
            self.abbreviation_match,    # 7. Common abbreviations
            self.temporal_parse,        # 8. For date/time terms
        ]
```

### 2. **Caching Layer**
Remember successful mappings for fast retrieval:

```python
class MappingCache:
    def __init__(self):
        self.cache = {}
        self.ttl = 86400  # 24 hours

    def get(self, user_term: str, context: str) -> Optional[str]:
        key = f"{user_term}:{context}"
        if key in self.cache:
            return self.cache[key]["value"]
        return None

    def set(self, user_term: str, context: str, db_value: str):
        key = f"{user_term}:{context}"
        self.cache[key] = {
            "value": db_value,
            "timestamp": time.time(),
            "usage_count": 1
        }
```

### 3. **Specialized Sub-Tools**

#### A. **Company Name to Symbol Mapper**
```python
async def map_company_to_symbol(company_name: str) -> Dict[str, Any]:
    """
    Specialized tool for company name to stock symbol mapping.

    Strategies:
    1. Query securities table for company_name ILIKE match
    2. Use pre-built common mappings (Apple→AAPL, Microsoft→MSFT)
    3. Try abbreviations and variations
    4. Fuzzy match against known company names
    """

    # First, try common mappings
    COMMON_MAPPINGS = {
        "apple": "AAPL",
        "microsoft": "MSFT",
        "amazon": "AMZN",
        "google": "GOOGL",
        "alphabet": "GOOGL",
        "meta": "META",
        "facebook": "META",
        # ... more mappings
    }

    # Then query database
    sql = """
    SELECT symbol, company_name,
           similarity(company_name, %s) as score
    FROM securities
    WHERE company_name ILIKE %s
       OR symbol ILIKE %s
    ORDER BY score DESC
    LIMIT 5
    """
```

#### B. **Temporal Expression Parser**
```python
async def parse_temporal_expression(expression: str, reference_date: date = None) -> Dict[str, Any]:
    """
    Parse temporal expressions into date ranges.

    Examples:
    - "last quarter" → {"start": "2024-07-01", "end": "2024-09-30"}
    - "past month" → {"start": "2024-11-01", "end": "2024-11-30"}
    - "Q4 2024" → {"start": "2024-10-01", "end": "2024-12-31"}
    - "December 2024" → {"start": "2024-12-01", "end": "2024-12-31"}
    """

    if not reference_date:
        reference_date = date.today()

    patterns = {
        r"last quarter": lambda: get_previous_quarter(reference_date),
        r"Q(\d) (\d{4})": lambda m: get_quarter_dates(int(m[1]), int(m[2])),
        r"past (\d+) days?": lambda m: get_past_days(int(m[1]), reference_date),
        r"(\w+) (\d{4})": lambda m: parse_month_year(m[1], int(m[2])),
    }
```

#### C. **Column Value Explorer**
```python
async def explore_column_values(
    table: str,
    column: str,
    search_term: str,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Explore actual values in a column to find matches.

    Returns ranked list of possible values with confidence scores.
    """

    # Use PostgreSQL's similarity functions
    sql = """
    SELECT DISTINCT
        {column} as value,
        similarity({column}, %s) as text_similarity,
        levenshtein({column}, %s) as edit_distance,
        COUNT(*) as frequency
    FROM {table}
    WHERE {column} IS NOT NULL
    GROUP BY {column}
    HAVING similarity({column}, %s) > 0.3
        OR {column} ILIKE %s
    ORDER BY text_similarity DESC, frequency DESC
    LIMIT %s
    """
```

### 4. **Integration with Agent**

The agent would use this tool when:
1. Generating SQL and needs to map user terms to values
2. A query returns no results (diagnostic mode)
3. User mentions company names, dates, or other natural language terms

Example usage in agent:
```python
# In the agent's act() method
if "company name detected" in thought:
    mapping_result = await self.tools.discover_value_mapping(
        user_term="Microsoft",
        target_column="symbol",
        target_table="securities",
        context=state.user_query
    )

    if mapping_result["found"]:
        state.discovered_mappings[mapping_result["mapping"]["user_term"]] = \
            mapping_result["mapping"]["database_value"]
```

### 5. **Learning Component**

The tool should learn from:
- Successful queries (which mappings worked)
- User corrections
- Frequency of use
- Context patterns

```python
class MappingLearner:
    def record_success(self, user_term: str, db_value: str, context: str):
        """Record successful mapping for future use"""

    def record_failure(self, user_term: str, attempted_value: str, context: str):
        """Record failed mapping to avoid in future"""

    def get_confidence(self, user_term: str, db_value: str) -> float:
        """Get confidence score based on historical success"""
```

## Benefits

1. **Flexible**: Handles multiple types of mappings
2. **Learning**: Gets better over time
3. **Transparent**: Returns confidence scores and alternatives
4. **Efficient**: Uses caching and indexing
5. **Extensible**: Easy to add new mapping strategies

## Example Scenarios

### Scenario 1: Company Name
```
User: "Show me Apple stock prices"
Agent: discover_value_mapping("Apple", "symbol", "securities")
Result: {"found": true, "mapping": {"user_term": "Apple", "database_value": "AAPL"}}
```

### Scenario 2: Temporal Expression
```
User: "Sales in the last quarter"
Agent: discover_value_mapping("last quarter", "trade_date", "daily_prices", search_strategy="temporal")
Result: {"found": true, "mapping": {"user_term": "last quarter", "database_value": {"start": "2024-07-01", "end": "2024-09-30"}}}
```

### Scenario 3: Fuzzy Match
```
User: "Microsoft corporation data"
Agent: discover_value_mapping("Microsoft corporation", "company_name", "securities")
Result: {"found": true, "mapping": {"user_term": "Microsoft corporation", "database_value": "Microsoft Corporation"}, "alternatives": [{"value": "MSFT", "column": "symbol", "confidence": 0.95}]}
```

## Implementation Priority

1. **Phase 1**: Basic exact and fuzzy matching
2. **Phase 2**: Temporal parsing and company mappings
3. **Phase 3**: Caching and learning
4. **Phase 4**: Semantic search and advanced strategies
