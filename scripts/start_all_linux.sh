#!/bin/bash

echo "Starting SENS Full Stack..."
echo "=========================="

# Get the project root directory
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Kill any existing processes on our ports
echo "Cleaning up existing processes..."
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:3000 | xargs kill -9 2>/dev/null || true

# Setup Python environment
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

# Start the FastAPI backend
echo "Starting FastAPI backend on port 8000..."
cd "$PROJECT_ROOT"
poetry run uvicorn sens.api.app:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Wait for backend to start
echo "Waiting for backend to start..."
sleep 5

# Check if npm or pnpm is available for frontend
if command -v pnpm &> /dev/null; then
    PM="pnpm"
elif command -v npm &> /dev/null; then
    PM="npm"
else
    echo "Error: Neither pnpm nor npm found. Please install Node.js."
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

# Start the Next.js frontend
echo "Starting Next.js frontend on port 3000 using $PM..."
cd "$PROJECT_ROOT/web"
$PM install
$PM run dev &
FRONTEND_PID=$!

echo ""
echo "=========================="
echo "SENS is running!"
echo "Backend API: http://localhost:8000"
echo "Frontend UI: http://localhost:3000"
echo "API Docs: http://localhost:8000/docs"
echo "=========================="
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for Ctrl+C
trap "echo 'Stopping services...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT
wait