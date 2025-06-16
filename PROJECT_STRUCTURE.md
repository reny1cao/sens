# SENS Project Structure

## Overview
SENS (Semantic Natural SQL) is a natural language to SQL conversion tool with an intelligent agent architecture.

## Directory Structure

```
sens/
├── src/sens/              # Main Python package
│   ├── agents/           # ReAct agent implementation
│   ├── api/              # FastAPI backend
│   ├── caching/          # Cache management (Redis/Memory)
│   ├── chat/             # Chat orchestration
│   ├── cli/              # Command-line interface
│   ├── datasource/       # Data source management
│   ├── execution/        # SQL execution engine
│   ├── llm/              # LLM integrations
│   ├── monitoring/       # Metrics and performance
│   ├── pipeline.py       # Main NL2SQL pipeline
│   ├── postprocessing/   # Response formatting
│   ├── retrieval/        # Schema retrieval (RAG)
│   ├── schema/           # Schema extraction & graph
│   ├── settings/         # Configuration
│   └── validation/       # SQL validation
│
├── web/                  # Next.js frontend
│   ├── app/             # App router pages
│   ├── components/      # React components
│   ├── contexts/        # React contexts
│   ├── hooks/           # Custom React hooks
│   ├── lib/             # Utilities
│   └── types/           # TypeScript types
│
├── tests/               # Test suite
│   ├── api/            # API tests
│   ├── chat/           # Chat tests
│   ├── cli/            # CLI tests
│   ├── integration/    # Integration tests
│   └── performance/    # Performance tests
│
├── scripts/             # Utility scripts
│   ├── deployment/     # Deployment scripts
│   ├── testing/        # Test scripts
│   └── *.py           # Data loading scripts
│
├── docs/               # Documentation
│   ├── architecture/   # Architecture docs
│   ├── deployment/     # Deployment guides
│   ├── development/    # Development guides
│   └── planning/       # Roadmaps and plans
│
└── var/indices/        # Embedding indices
```

## Key Components

### Backend (FastAPI)
- **Entry Point**: `src/sens/api/app.py`
- **Main Routes**:
  - `/api/nl2sql` - Standard NL2SQL conversion
  - `/api/nl2sql/agent` - Agent-based processing
  - `/api/schema` - Schema operations
  - `/api/datasource` - Data source management

### Frontend (Next.js)
- **Entry Point**: `web/app/page.tsx`
- **Key Components**:
  - `QueryInterfaceWithAgent` - Main query interface
  - `SchemaVisualizer` - Interactive schema visualization
  - `DataSourceSelector` - Multi-source data management

### CLI
- **Entry Point**: `src/sens/cli/main.py`
- **Commands**:
  - `sens nl2sql` - Convert natural language to SQL
  - `sens financial` - Financial data management
  - `sens schema` - Schema operations
  - `sens agent` - Agent operations

### Agent System
- **Core**: `src/sens/agents/core.py` - ReAct loop implementation
- **Tools**: `src/sens/agents/tools.py` - Agent capabilities
- **Memory**: `src/sens/agents/memory.py` - Learning system

## Configuration

### Environment Variables
- See `.env.example` for all configuration options
- Key prefixes:
  - `SENS_` - General settings
  - `SENS_DB_` - Database settings
  - `SENS_LLM_` - LLM settings
  - `SENS_CLI_` - CLI settings

### Deployment
- **Backend**: Railway (Docker)
- **Frontend**: Vercel (Next.js)
- **Database**: PostgreSQL (Railway)

## Development

### Setup
```bash
# Backend
poetry install
poetry run sens --help

# Frontend
cd web
pnpm install
pnpm run dev
```

### Testing
```bash
# Run all tests
poetry run pytest

# Run specific tests
poetry run pytest tests/api/
poetry run pytest -k "test_agent"
```

## Data Flow

1. **User Query** → Frontend (Next.js)
2. **API Request** → Backend (FastAPI)
3. **Intent Extraction** → LLM (OpenRouter)
4. **Schema Retrieval** → RAG (Embeddings + Token Search)
5. **SQL Generation** → LLM with Context
6. **Validation** → SQL Validator
7. **Execution** → PostgreSQL
8. **Response** → Natural Language Summary
9. **Display** → Frontend Components

## Agent Architecture

The agent uses a ReAct (Reasoning + Acting) loop:
1. **Reason** - Analyze the query and current state
2. **Act** - Choose and execute an action (tool)
3. **Observe** - Process the tool's output
4. **Reflect** - Update understanding and plan next steps

Currently operates in "minimal mode" with 3 active tools:
- `EXPLORE_DATABASE` - Execute exploration queries
- `GENERATE_SQL` - Generate SQL from discoveries
- `EXECUTE_SQL` - Execute the final SQL

## Key Features

- **Multi-Source Support**: PostgreSQL, DuckDB, CSV uploads
- **Intelligent Agents**: Self-correcting query generation
- **Schema Visualization**: Interactive ER diagrams
- **Session Management**: Stateful conversations
- **Performance Metrics**: Query timing and success tracking
- **Natural Language Summaries**: LLM-powered result explanations
