#!/bin/bash

echo "Starting SENS Full Stack..."
echo "=========================="

# Kill any existing processes on our ports
echo "Cleaning up existing processes..."
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:3000 | xargs kill -9 2>/dev/null || true

# Start the FastAPI backend
echo "Starting FastAPI backend on port 8000..."
cd /Users/renyitsao/workplace/sens
poetry run uvicorn sens.api.app:app --reload --host 0.0.0.0 --port 8000 &
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
