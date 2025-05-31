FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN pip install poetry

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Configure poetry to not create virtual env
RUN poetry config virtualenvs.create false

# Install dependencies
RUN poetry install --no-interaction --no-ansi --no-dev

# Copy application code
COPY src ./src
COPY scripts ./scripts

# Create directories for file uploads and indices
RUN mkdir -p /tmp/sens /app/indices

# Set environment variables
ENV PYTHONPATH=/app/src
ENV SENS_ENVIRONMENT=production

# Expose port (Railway will override with $PORT)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Start command (Railway will inject $PORT)
CMD uvicorn sens.api.app:app --host 0.0.0.0 --port ${PORT:-8000}