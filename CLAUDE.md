# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SENS (Semantic Natural SQL) is a natural language to SQL conversion tool with semantic understanding. It's built with Python using FastAPI for the API layer and includes a CLI interface.

**Important**: SENS is evolving towards an agentic architecture that intelligently maps user terms to database values. See [docs/agentic_query_architecture.md](docs/agentic_query_architecture.md) for the planned intelligent query system that will handle value mismatches, self-correct queries, and learn from user interactions.

## Common Development Commands

```bash
# Install dependencies
poetry install

# Run tests
poetry run pytest
poetry run pytest tests/path/to/test_file.py::TestClass::test_method  # Run single test

# Run linting and formatting
poetry run black .       # Format code
poetry run ruff .        # Lint code
poetry run mypy src      # Type checking

# Run the API server
poetry run uvicorn sens.api.app:app --reload

# CLI commands
poetry run sens nl2sql -q "How many users signed up last month?"
poetry run sens nl2sql -i  # Interactive mode
poetry run sens execute "SELECT * FROM users LIMIT 5"
poetry run sens debug --conversation-id 1234
poetry run sens metrics --detailed
poetry run sens status

# Schema management
poetry run sens extract-schema -o schema.json
poetry run sens build-index -s schema.json

# Financial data management
poetry run sens financial setup --create-schema  # Create financial database schema
poetry run sens financial load --symbols AAPL,GOOGL,MSFT --days 365  # Load stock data
poetry run sens financial load-economic --preset key_economic  # Load economic indicators
poetry run sens financial update  # Daily data update
poetry run sens financial status --detailed  # Show data status
poetry run sens financial prices AAPL --days 30  # Show recent prices
```

## High-Level Architecture

The codebase follows a domain-driven design with clear separation of concerns:

1. **Pipeline Architecture**: The `EnhancedNL2SQLPipeline` orchestrates the entire conversion flow from natural language to SQL execution.

2. **Retrieval System**: Implements RAG (Retrieval Augmented Generation) with two approaches:
   - Token-based search for exact schema matches
   - Embedding-based search using Sentence Transformers and FAISS for semantic similarity

3. **Schema Context Management**:
   - Schema graph for understanding relationships between tables
   - "Sticky columns" feature to identify semantically important columns
   - Singleton pattern for efficient schema instance management

4. **LLM Integration**: Uses OpenRouter API for intent extraction and SQL generation with structured prompts.

5. **Session Management**: Redis-backed sessions with automatic fallback to in-memory storage for horizontal scalability.

6. **Validation Hierarchy**: Multi-level SQL validation (syntax, schema, safety) before execution.

## Key Architectural Patterns

- **Async/Await**: Used throughout for concurrent operations
- **Dependency Injection**: Settings management through Pydantic settings
- **Structured Logging**: JSON-formatted logs using structlog
- **Error Hierarchy**: Custom exception classes for different error types
- **Metrics Collection**: Comprehensive tracking of pipeline performance

## Development Guidelines from Cursor Rules

1. **Start Simple**: Solve with fewest components possible
2. **Plan Before Coding**: Always outline steps before generating code
3. **One Module, One Responsibility**: Each file serves a single purpose
4. **Model Honesty**: All implementations must be production-viable
5. **Mandatory Test Coverage**: Every new module needs tests
6. **Poetry for Dependencies**: All dependencies managed through pyproject.toml
7. **Descriptive Naming**: Files named by what they do (e.g., `token_index.py`, not `utils.py`)

## Important Configuration

- Database: Configure `SENS_DB_URL` in `.env`
- LLM: Set `SENS_OPENROUTER_API_KEY` and `SENS_OPENROUTER_BASE_URL`
- Redis (optional): `SENS_REDIS_URL` for session management
- CLI settings: Environment variables with `SENS_CLI_` prefix control debug, metrics, and output formatting

## Current Known Limitations

1. **Value Mapping**: The system currently expects exact matches between user input and database values (e.g., "Technology" vs "technology", "Apple" vs "AAPL")
2. **No Self-Correction**: If a query returns no results, the system doesn't attempt to diagnose or fix the issue
3. **Static Value Understanding**: No ability to explore database values or learn from successful queries
4. **Limited Temporal Reasoning**: Relative dates like "last month" need explicit date ranges

These limitations are being addressed in the upcoming agentic architecture (see roadmap Phase 1).
