FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src ./src
COPY scripts ./scripts

# Create necessary directories
RUN mkdir -p /tmp/sens /app/indices

# Set environment variables
ENV PYTHONPATH=/app/src
ENV SENS_ENVIRONMENT=production

# Start command - use shell to expand Railway's PORT variable
CMD sh -c "uvicorn sens.api.app:app --host 0.0.0.0 --port ${PORT:-8000}"
