# Sens Project

## OpenRouter Setup

1. Sign up for an OpenRouter account at https://openrouter.ai/
2. Create an API key from your account dashboard
3. Set the API key as an environment variable:
   ```bash
   export OPENROUTER_API_KEY=your-api-key-here
   ```

## Model Configuration

The project supports configurable models for different tasks through environment variables:

### Required Variables
- `OPENROUTER_API_KEY`: Your OpenRouter API key

### Optional Model Configuration
You can override the default models for specific tasks:

```bash
# Intent extraction
export OPENROUTER_MODEL_INTENT=openai/gpt-4o

# SQL generation
export OPENROUTER_MODEL_SQL=openai/gpt-4o
```

### Fallback Models
Optionally configure fallback models for each task:

```bash
# Intent extraction fallback
export OPENROUTER_FALLBACK_MODEL_INTENT=openai/gpt-3.5-turbo

# SQL generation fallback
export OPENROUTER_FALLBACK_MODEL_SQL=openai/gpt-3.5-turbo
```

## Usage Example

```python
from sens.llm.intent_extractor import IntentExtractor

# Initialize with default model
extractor = IntentExtractor()

# Or specify a custom model
extractor = IntentExtractor(model="openai/gpt-3.5-turbo")

# Extract intent from a question
intent = extractor.extract(
    "How many movies were released in 2023?",
    """
    TABLE movie(
        id INTEGER PRIMARY KEY,
        title TEXT,
        release_year INTEGER
    )
    """
)
```

## CLI Usage

The Sens project provides a command-line interface for various operations. After installation, you can use the `sens` command:

### Natural Language to SQL Conversion

Convert natural language questions to SQL queries:

```bash
# Single question mode
sens nl2sql -q "How many users registered in 2024?"

# Interactive mode
sens nl2sql -i

# With pretty-printed output
sens nl2sql -q "List all active users" -p

# Adjust number of relevant context items
sens nl2sql -q "Find recent orders" -k 10
```

### Schema Management

Extract database schema to JSON:

```bash
# Use default output path
sens extract-schema

# Specify custom output path
sens extract-schema -o path/to/schema.json
```

### Embedding Index Management

Build the embedding search index:

```bash
# Use default paths
sens build-index

# Specify custom paths
sens build-index -s path/to/schema.json -o path/to/index/dir
```

### SQL Validation

Validate SQL queries against schema, syntax, and safety rules:

```bash
# Validate a SQL query
sens validate -s "SELECT id, name FROM users WHERE id = 1;"

# Validate SQL from a file
sens validate -f query.sql

# Validate specific aspects
sens validate -s "SELECT * FROM users" --syntax  # Only syntax
sens validate -s "SELECT * FROM users" --schema  # Only schema
sens validate -s "SELECT * FROM users" --safety  # Only safety

# Allow specific SQL keywords
sens validate -s "DROP TABLE users" --allow DROP

# Allow unfiltered UPDATE/DELETE
sens validate -s "DELETE FROM users" --allow-unfiltered

# Output in JSON format
sens validate -s "SELECT * FROM users" --json

# Pretty print output
sens validate -s "SELECT * FROM users" --json -p
```

The validator checks for:
- Syntax correctness
- Schema alignment (tables and columns exist)
- Safety (no destructive operations)
- UPDATE/DELETE with WHERE clause

Exit codes:
- 0: Validation passed
- 1: Validation failed or error occurred

### Global Options

- `-v, --verbose`: Enable verbose logging
- `-h, --help`: Show help message for any command

For detailed help on any command:

```bash
sens <command> --help
```
