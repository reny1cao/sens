#!/bin/bash

# Start all services for SENS development

set -e

echo "🚀 Starting SENS development environment..."

# Set Python path
export PYTHONPATH="$(pwd)/src:$PYTHONPATH"

# Start backend API
echo "Starting backend API..."
poetry run uvicorn sens.api.app_unified:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Wait for backend to start
echo "Waiting for backend to start..."
sleep 5

# Start the Next.js frontend
echo "Starting Next.js frontend on port 3000..."
cd /Users/renyitsao/workplace/sens/web
pnpm dev &
FRONTEND_PID=$!

echo ""
echo "=========================="
echo "SENS is running!"
echo "Backend API: http://localhost:8000"
echo "Frontend UI: http://localhost:3000"
echo "=========================="
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for Ctrl+C
trap "echo 'Stopping services...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT
wait
