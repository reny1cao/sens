# Use the official Python 3.12 image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry==1.8.3

# Copy poetry files
COPY pyproject.toml poetry.lock ./

# Configure poetry and install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-root

# Copy source code
COPY src/ src/
COPY README.md ./
RUN poetry install --only-root

# Expose port
EXPOSE 8000

# Start command
CMD sh -c "uvicorn sens.api.app_unified:app --host 0.0.0.0 --port ${PORT:-8000}"
