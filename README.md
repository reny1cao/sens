# Sens - Semantic Natural SQL

A natural language to SQL conversion tool with semantic understanding.

## Features

- Convert natural language questions to SQL queries
- Semantic understanding of database schema
- Safe, read-only query execution
- Rich, formatted output options
- Interactive mode for multiple queries

## Installation

```bash
# Install using Poetry
poetry install

# Or using pip
pip install -r requirements.txt
```

## Configuration

Create a `.env` file with your database and LLM settings:

```env
# Database
SENS_DB_URL=postgresql://user:pass@localhost:5432/dbname

# OpenRouter LLM
SENS_OPENROUTER_API_KEY=your_api_key
SENS_OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

## Usage

### Basic Usage

```bash
# Convert a question to SQL
sens nl2sql -q "How many users signed up last month?"

# Interactive mode
sens nl2sql -i

# Execute a SQL query
sens execute "SELECT * FROM users LIMIT 5"
```

For more details on system administration commands like `debug`, `metrics`, and `status`, as well as advanced CLI configuration options, please see the [Sens CLI Commands and Configuration](./docs/cli_commands.md) documentation.

### Output Formatting

The `nl2sql` command supports different output formats:

```bash
# JSON output (default)
sens nl2sql -q "List all users" --format json

# Table format with preview
sens nl2sql -q "List all users" --format table

# Summary only
sens nl2sql -q "List all users" --format summary

# Control preview rows
sens nl2sql -q "List all users" --max-rows 10

# Hide preview
sens nl2sql -q "List all users" --no-preview
```

### Schema Management

```bash
# Extract database schema
sens extract-schema -o schema.json

# Build search indices
sens build-index -s schema.json
```

## Development

```bash
# Run tests
poetry run pytest

# Run linting
poetry run flake8

# Run type checking
poetry run mypy src
```

## License

MIT License. See LICENSE file for details.
