#!/bin/bash

echo "Setting up SENS with Cloudflare Tunnel for Remote Access..."
echo "=========================================================="

# Get the project root directory
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Kill any existing processes on our ports
echo "Cleaning up existing processes..."
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:3000 | xargs kill -9 2>/dev/null || true
pkill cloudflared 2>/dev/null || true

# Setup Python environment
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
if command -v pyenv &> /dev/null; then
    eval "$(pyenv init -)"
fi

# Start the FastAPI backend
echo "Starting FastAPI backend on port 8000..."
cd "$PROJECT_ROOT"
poetry run uvicorn sens.api.app:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Wait for backend to start
echo "Waiting for backend to start..."
sleep 5

# Test backend health
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✓ Backend is healthy"
else
    echo "✗ Backend failed to start"
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

# Install cloudflared if not available
if ! command -v cloudflared &> /dev/null; then
    echo "Installing cloudflared..."
    wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
    sudo mv cloudflared-linux-amd64 /usr/local/bin/cloudflared
    sudo chmod +x /usr/local/bin/cloudflared
fi

# Start cloudflare tunnel for backend
echo "Creating tunnel for backend API (port 8000)..."
cloudflared tunnel --url http://localhost:8000 > tunnel.log 2>&1 &
TUNNEL_PID=$!

# Wait for tunnel to establish and get URL
echo "Waiting for tunnel to establish..."
sleep 10

# Extract tunnel URL from logs
TUNNEL_URL=""
for i in {1..30}; do
    if [ -f tunnel.log ]; then
        TUNNEL_URL=$(grep -o 'https://[^.]*\.trycloudflare\.com' tunnel.log | head -1)
        if [ ! -z "$TUNNEL_URL" ]; then
            break
        fi
    fi
    sleep 1
done

if [ -z "$TUNNEL_URL" ]; then
    echo "✗ Failed to get tunnel URL"
    cat tunnel.log
    kill $BACKEND_PID $TUNNEL_PID 2>/dev/null
    exit 1
fi

echo "✓ Tunnel established: $TUNNEL_URL"

# Update frontend environment variable
cd "$PROJECT_ROOT/web"
echo "NEXT_PUBLIC_API_URL=$TUNNEL_URL" > .env.local

# Test tunnel connection
if curl -s "$TUNNEL_URL/health" > /dev/null; then
    echo "✓ Tunnel is working"
else
    echo "✗ Tunnel connection failed"
    kill $BACKEND_PID $TUNNEL_PID 2>/dev/null
    exit 1
fi

# Check if npm or pnpm is available for frontend
if command -v pnpm &> /dev/null; then
    PM="pnpm"
elif command -v npm &> /dev/null; then
    PM="npm"
else
    echo "Error: Neither pnpm nor npm found. Please install Node.js."
    kill $BACKEND_PID $TUNNEL_PID 2>/dev/null
    exit 1
fi

# Start the Next.js frontend
echo "Starting Next.js frontend on port 3000 using $PM..."
$PM install > /dev/null 2>&1
$PM run dev &
FRONTEND_PID=$!

echo ""
echo "=========================================================="
echo "🚀 SENS is running with remote access!"
echo ""
echo "Backend API (local):  http://localhost:8000"
echo "Backend API (remote): $TUNNEL_URL"
echo "Frontend (local):     http://localhost:3000"
echo "API Docs:             $TUNNEL_URL/docs"
echo ""
echo "The frontend is configured to use: $TUNNEL_URL"
echo "=========================================================="
echo ""
echo "Press Ctrl+C to stop all services"

# Store PIDs for cleanup
echo $BACKEND_PID > backend.pid
echo $FRONTEND_PID > frontend.pid
echo $TUNNEL_PID > tunnel.pid

# Wait for Ctrl+C
trap "echo 'Stopping services...'; kill $BACKEND_PID $FRONTEND_PID $TUNNEL_PID 2>/dev/null; rm -f backend.pid frontend.pid tunnel.pid tunnel.log; exit" INT
wait