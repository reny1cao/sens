# Sens - Semantic Natural SQL

A natural language to SQL conversion tool with semantic understanding.

## Features

- Convert natural language questions to SQL queries
- Semantic understanding of database schema
- Safe, read-only query execution
- Rich, formatted output options
- Interactive mode for multiple queries
- Persistent conversation state with Redis session management
- Horizontal scalability with distributed session storage

## Installation

```bash
# Install using Poetry
poetry install

# Or using pip
pip install -r requirements.txt
```

## Configuration

Create a `.env` file with your database, LLM, and Redis settings:

```env
# Database
SENS_DB_URL=postgresql://user:pass@localhost:5432/dbname

# OpenRouter LLM
SENS_OPENROUTER_API_KEY=your_api_key
SENS_OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Redis Session Management (optional)
SENS_REDIS_URL=redis://localhost:6379
SENS_SESSION_TTL_SECONDS=86400  # 24 hours
```

If Redis is not available, Sens will operate in a degraded mode with in-memory session state.

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

```

## 📚 Documentation

- [Full Documentation](./docs/README.md) - Complete documentation index
- [Architecture Overview](./docs/schema_context.md) - System design
- [API Reference](http://localhost:8000/docs) - Interactive API docs
- [Deployment Guide](./DEPLOYMENT.md) - Production deployment
- [Test Coverage](./TEST_COVERAGE.md) - Testing status

## 🗺️ Roadmap

SENS is evolving towards an intelligent, proactive data platform:

### Current (v1.0)
- ✅ Natural language to SQL
- ✅ Multi-datasource support
- ✅ Web interface
- ✅ Session management

### Next (v2.0) - Agentic System
- 🚧 Intelligent value mapping
- 🚧 Self-correcting queries
- 🚧 Learning from interactions
- 📅 Proactive insights

See the full [Roadmap](./ROADMAP.md) for details.

## 🤝 Contributing

We welcome contributions! Please see our contributing guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

```bash
# Clone your fork
git clone https://github.com/yourusername/sens.git
cd sens

# Install development dependencies
poetry install --with dev

# Set up pre-commit hooks
pre-commit install

# Run tests before committing
poetry run pytest
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- OpenRouter for LLM infrastructure
- The FastAPI team for the excellent framework
- All contributors who have helped improve SENS

## 📞 Support

- 📖 [Documentation](./docs/README.md)
- 🐛 [Issue Tracker](https://github.com/yourusername/sens/issues)
- 💬 [Discussions](https://github.com/yourusername/sens/discussions)
- 📧 Email: support@sens-ai.dev

---

<p align="center">
  Made with ❤️ by the SENS team
</p>

# Run type checking
poetry run mypy src
```

## License

MIT License. See LICENSE file for details.
