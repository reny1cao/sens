# Self-Discovering Value Discovery Implementation Plan

## Core Philosophy
The agent should naturally learn to use SELECT DISTINCT through experience and reasoning, not hardcoded rules. When queries fail or return no results, the agent should reason: "Let me see what values actually exist in this column."

## Implementation Strategy

### 1. **Enhanced Reasoning Context**
Give the agent more context about query failures so it can reason about solutions:

```python
# In reflect() method - when SQL execution returns 0 rows
if observation.content and observation.content.get("row_count", 0) == 0:
    state.add_thought(
        "The query returned no results. This could mean: "
        "1) The values I used don't exist in the database, "
        "2) The date range is outside available data, "
        "3) The column names or table references are incorrect. "
        "I should explore what values actually exist in the relevant columns."
    )
```

### 2. **Expand Agent's SQL Knowledge**
Add examples of value discovery queries to the agent's knowledge base:

```python
# In agent's training/knowledge
SQL_EXPLORATION_EXAMPLES = [
    {
        "scenario": "Need to find company symbols",
        "query": "SELECT DISTINCT symbol, company_name FROM securities ORDER BY symbol LIMIT 20",
        "purpose": "Discover what company symbols exist in the database"
    },
    {
        "scenario": "Search for specific company",
        "query": "SELECT DISTINCT symbol, company_name FROM securities WHERE company_name ILIKE '%search_term%'",
        "purpose": "Find exact symbol for a company name"
    },
    {
        "scenario": "Check what sectors exist",
        "query": "SELECT DISTINCT sector FROM securities WHERE sector IS NOT NULL",
        "purpose": "Discover valid sector values"
    },
    {
        "scenario": "Find date range",
        "query": "SELECT MIN(trade_date), MAX(trade_date) FROM daily_prices",
        "purpose": "Understand available date range"
    },
    {
        "scenario": "Debug failed WHERE clause",
        "query": "SELECT DISTINCT column_name FROM table_name ORDER BY column_name LIMIT 20",
        "purpose": "See what values exist in a column after query failure"
    }
]
```

### 3. **Enhanced LLM Prompts**
Update the reasoning engine prompts to include value discovery concepts:

```python
# In ReasoningEngine - add to system prompt
ENHANCED_REASONING_PROMPT = """
You are an AI agent that converts natural language to SQL. When working with databases:

1. If a query returns no results, consider that the values you used might not exist
2. Use SELECT DISTINCT to explore what values actually exist in columns
3. Before writing WHERE clauses with specific values, verify those values exist
4. When users mention company names, explore the securities table to find correct symbols
5. When queries fail, think about what information you need to discover

Example reasoning patterns:
- "User said 'Apple' but I should check what symbol represents Apple"
- "This returned 0 rows, let me see what values exist in this column"
- "Before filtering by sector, let me see what sectors are available"

Available exploration patterns:
- SELECT DISTINCT column FROM table (see all values)
- SELECT DISTINCT col1, col2 FROM table WHERE col1 ILIKE '%term%' (search for values)
- SELECT MIN(date_col), MAX(date_col) FROM table (find date ranges)
"""
```

### 4. **Learning from Failures**
Enhance the reflection mechanism to analyze failures and suggest discoveries:

```python
async def reflect(self, state: AgentState, observation: AgentObservation) -> None:
    """Enhanced reflection that learns from failures."""
    await super().reflect(state, observation)

    # Analyze execution failures
    if (observation.success and
        observation.content and
        observation.content.get("row_count", 0) == 0):

        # Extract the WHERE clause from current SQL to understand what failed
        failed_sql = state.current_sql
        if failed_sql and "WHERE" in failed_sql:
            self._analyze_where_clause_failure(state, failed_sql)

    # Analyze generation failures
    elif not observation.success and "does not exist" in str(observation.error):
        state.add_thought(
            "The error suggests a column or table doesn't exist. "
            "I should explore the schema more carefully to understand "
            "the correct table and column names."
        )

def _analyze_where_clause_failure(self, state: AgentState, failed_sql: str):
    """Analyze why a WHERE clause might have failed."""
    import re

    # Extract WHERE conditions
    where_patterns = [
        r"WHERE\s+(\w+)\s*=\s*['\"]([^'\"]+)['\"]",  # WHERE col = 'value'
        r"WHERE\s+(\w+)\s+ILIKE\s+['\"]([^'\"]+)['\"]",  # WHERE col ILIKE 'pattern'
    ]

    suggestions = []
    for pattern in where_patterns:
        matches = re.findall(pattern, failed_sql, re.IGNORECASE)
        for column, value in matches:
            suggestions.append(
                f"Check what values exist in column '{column}' since '{value}' returned no results. "
                f"Try: SELECT DISTINCT {column} FROM [table] WHERE {column} ILIKE '%{value[:3]}%'"
            )

    if suggestions:
        thought = "Query returned no results. Possible issues: " + " ".join(suggestions)
        state.add_thought(thought)
```

### 5. **Example-Based Learning**
Add successful discovery examples to the agent's memory/context:

```python
# Examples the agent can learn from
DISCOVERY_SUCCESS_EXAMPLES = [
    {
        "user_query": "Show me Apple stock prices",
        "failed_approach": "WHERE symbol = 'Apple'",  # Returns 0 rows
        "discovery_query": "SELECT DISTINCT symbol, company_name FROM securities WHERE company_name ILIKE '%Apple%'",
        "discovery_result": [["AAPL", "Apple Inc."]],
        "successful_approach": "WHERE symbol = 'AAPL'",
        "lesson": "Company names in user queries need to be mapped to stock symbols"
    },
    {
        "user_query": "Show technology sector performance",
        "failed_approach": "WHERE sector = 'technology'",  # Wrong case
        "discovery_query": "SELECT DISTINCT sector FROM securities",
        "discovery_result": [["Technology"], ["Finance"], ["Healthcare"]],
        "successful_approach": "WHERE sector = 'Technology'",
        "lesson": "Check exact capitalization and values in database"
    }
]
```

### 6. **Natural Discovery Triggers**
Instead of hardcoded rules, let the agent naturally reason about when to discover:

```python
# Enhanced thought patterns that emerge from reasoning
NATURAL_DISCOVERY_TRIGGERS = [
    # When user mentions specific entities
    "User mentioned 'Microsoft' - this is likely a company name that needs to be mapped to a symbol",

    # When queries fail
    "This query returned 0 rows. The values I used might not exist in the database",

    # When unsure about values
    "I'm not sure what values exist in this column. Let me explore them first",

    # When starting complex queries
    "Before building this query, I should understand what data is available"
]
```

## Implementation Steps

### Phase 1: Enhanced Reflection (Week 1)
- Improve failure analysis in `reflect()` method
- Add better context when queries return 0 rows
- Help agent understand WHY queries might fail

### Phase 2: Enhanced Reasoning (Week 2)
- Update LLM prompts to include discovery concepts
- Add exploration examples to agent knowledge
- Improve reasoning about when exploration is needed

### Phase 3: Memory & Learning (Week 3)
- Add successful discovery patterns to agent memory
- Cache discovered mappings for reuse
- Learn from successful exploration patterns

### Phase 4: Testing & Refinement (Week 4)
- Test with the same queries that previously failed
- Measure improvement in success rate
- Refine reasoning patterns based on results

## Success Metrics

1. **Improved Success Rate**: Queries like "Show me Microsoft stock" should succeed
2. **Natural Discovery**: Agent should naturally think to explore values when needed
3. **Learning**: Agent should remember discovered mappings
4. **No Hardcoding**: All discovery should emerge from reasoning, not rules

## Example Agent Behavior (After Implementation)

```
User: "Show me Apple stock prices"

Iteration 1:
Thought: "User mentioned 'Apple'. This is likely a company name. I should check what the actual symbol is in the database before generating SQL."
Action: explore_database("SELECT DISTINCT symbol, company_name FROM securities WHERE company_name ILIKE '%Apple%'")
Observation: Found [["AAPL", "Apple Inc."]]

Iteration 2:
Thought: "Perfect! Apple Inc. has symbol 'AAPL'. Now I can generate the correct SQL."
Action: generate_sql(using symbol = 'AAPL')
Result: SUCCESS!
```

This approach makes the agent truly intelligent about value discovery rather than following programmed rules.
