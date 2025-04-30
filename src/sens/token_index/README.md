# Token Index Builder

A high-performance, memory-efficient token-based index for fast table name lookups. This module is part of the Sens project and provides O(1) lookup capabilities while maintaining strict memory constraints.

## Features

- O(1) lookup complexity
- Memory efficient (<1MB for 1K tables)
- Support for multiple case formats (snake_case, camelCase, kebab-case)
- Structured JSON logging
- High performance (<2ms latency for lookups)

## Usage

```python
from sens.token_index import TokenIndexBuilder

# Initialize the builder
builder = TokenIndexBuilder()

# Build index from table names
table_names = ["user_profiles", "userSettings", "user-preferences"]
builder.build_index(table_names)

# Look up tables
matches = builder.guess_tables("user")  # Returns matching table names
```

## Memory Management

The index maintains strict memory usage under 1MB for 1000 tables through:
- Token length limits
- Efficient data structures
- Memory tracking
- Automatic pruning when limits are reached

## Performance

- Build time: O(n) where n is total characters in table names
- Lookup time: O(1) with <2ms latency guarantee
- Memory usage: O(n) with strict 1MB cap

## Logging

All operations are logged in structured JSON format:
```json
{
    "event": "index_update",
    "table_name": "user_profiles",
    "tokens": ["user", "profiles"],
    "case_format": "snake",
    "current_memory": 1234,
    "timestamp": "2024-03-20T10:30:00Z"
}
```

## Testing

The module includes comprehensive test suites:
- Unit tests (`tests/test_token_index.py`)
- Performance tests (`tests/test_token_index_performance.py`)

Run tests with:
```bash
pytest tests/test_token_index*.py
```
