#!/bin/bash

# SENS Local Development Startup Script
# This script starts both the backend API and frontend UI for local development

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting SENS Development Environment${NC}"
echo "========================================"

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo -e "${RED}Error: Please run this script from the SENS root directory${NC}"
    exit 1
fi

# Check dependencies
echo -e "${BLUE}Checking dependencies...${NC}"

# Check if poetry is installed
if ! command -v poetry &> /dev/null; then
    echo -e "${RED}Error: Poetry is not installed. Please install it first:${NC}"
    echo "curl -sSL https://install.python-poetry.org | python3 -"
    exit 1
fi

# Check if pnpm is installed (for frontend)
if ! command -v pnpm &> /dev/null; then
    echo -e "${RED}Error: pnpm is not installed. Please install it first:${NC}"
    echo "npm install -g pnpm"
    exit 1
fi

# Install/update dependencies if needed
echo -e "${BLUE}Installing dependencies...${NC}"
poetry install --quiet
(cd web && pnpm install --silent)

# Check for .env file
if [ ! -f ".env" ]; then
    echo -e "${RED}Warning: .env file not found!${NC}"
    echo "Creating .env from example..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${GREEN}Created .env file. Please update it with your configuration.${NC}"
    else
        echo -e "${RED}No .env.example found. Please create a .env file.${NC}"
        exit 1
    fi
fi

# Kill any existing processes on our ports
echo -e "${BLUE}Cleaning up existing processes...${NC}"
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:3000 | xargs kill -9 2>/dev/null || true

# Function to cleanup on exit
cleanup() {
    echo -e "\n${BLUE}Stopping services...${NC}"
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    exit 0
}

trap cleanup INT TERM

# Start the FastAPI backend
echo -e "${BLUE}Starting Backend API on port 8000...${NC}"
poetry run uvicorn sens.api.app:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Wait for backend to start
echo -e "${BLUE}Waiting for backend to initialize...${NC}"
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Backend is ready!${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}Backend failed to start. Check logs above.${NC}"
        kill $BACKEND_PID 2>/dev/null
        exit 1
    fi
    sleep 1
done

# Start the Next.js frontend
echo -e "${BLUE}Starting Frontend UI on port 3000...${NC}"
cd web && pnpm dev &
FRONTEND_PID=$!
cd ..

# Wait a bit for frontend to start
sleep 3

echo ""
echo -e "${GREEN}========================================"
echo -e "✨ SENS is running!"
echo -e "========================================"
echo -e "${BLUE}Backend API:${NC} http://localhost:8000"
echo -e "${BLUE}API Docs:${NC}    http://localhost:8000/docs"
echo -e "${BLUE}Frontend UI:${NC} http://localhost:3000"
echo -e "========================================"
echo ""
echo -e "${BLUE}Logs will appear below. Press Ctrl+C to stop all services.${NC}"
echo ""

# Wait for processes
wait $BACKEND_PID $FRONTEND_PID
