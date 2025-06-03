#!/bin/bash

# SENS Deployment with Cloudflare Tunnel
# This script automates the deployment process for SENS with Cloudflare Tunnel

set -e

echo "=================================================="
echo "SENS Deployment with Cloudflare Tunnel"
echo "=================================================="

# Configuration
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TUNNEL_LOG="$PROJECT_ROOT/tunnel_deployment.log"
ENV_FILE="$PROJECT_ROOT/web/.env.local"
CLOUDFLARED_PATH="$PROJECT_ROOT/cloudflared"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Function to cleanup on exit
cleanup() {
    echo ""
    print_warning "Cleaning up..."
    
    # Kill processes if PIDs exist
    [ -f "$PROJECT_ROOT/backend.pid" ] && kill $(cat "$PROJECT_ROOT/backend.pid") 2>/dev/null
    [ -f "$PROJECT_ROOT/tunnel.pid" ] && kill $(cat "$PROJECT_ROOT/tunnel.pid") 2>/dev/null
    [ -f "$PROJECT_ROOT/web/frontend.pid" ] && kill $(cat "$PROJECT_ROOT/web/frontend.pid") 2>/dev/null
    
    # Remove PID files
    rm -f "$PROJECT_ROOT/backend.pid" "$PROJECT_ROOT/tunnel.pid" "$PROJECT_ROOT/web/frontend.pid"
    
    print_status "Cleanup completed"
}

# Set trap for cleanup on exit
trap cleanup EXIT

# Check prerequisites
echo "Checking prerequisites..."

# Check for Python/Poetry
if ! command -v poetry &> /dev/null; then
    print_error "Poetry not found. Please install Poetry first."
    exit 1
fi

# Check for Node.js
if ! command -v node &> /dev/null; then
    print_error "Node.js not found. Please install Node.js first."
    exit 1
fi

# Check for pnpm or npm
if command -v pnpm &> /dev/null; then
    PM="pnpm"
elif command -v npm &> /dev/null; then
    PM="npm"
else
    print_error "Neither pnpm nor npm found. Please install pnpm or npm."
    exit 1
fi

print_status "Prerequisites checked"

# Download cloudflared if not present
if [ ! -f "$CLOUDFLARED_PATH" ]; then
    print_warning "Cloudflared not found. Downloading..."
    wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O "$CLOUDFLARED_PATH"
    chmod +x "$CLOUDFLARED_PATH"
    print_status "Cloudflared downloaded"
fi

# Step 1: Start Backend
echo ""
echo "Starting Backend..."
cd "$PROJECT_ROOT"

# Check if backend is already running
if lsof -ti:8000 > /dev/null 2>&1; then
    print_warning "Port 8000 is already in use. Killing existing process..."
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
    sleep 2
fi

# Start backend
poetry run uvicorn sens.api.app:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
echo $BACKEND_PID > "$PROJECT_ROOT/backend.pid"

# Wait for backend to start
echo "Waiting for backend to start..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null; then
        print_status "Backend is running on http://localhost:8000"
        break
    fi
    sleep 1
done

# Verify backend is running
if ! curl -s http://localhost:8000/health > /dev/null; then
    print_error "Backend failed to start"
    exit 1
fi

# Step 2: Start Cloudflare Tunnel
echo ""
echo "Starting Cloudflare Tunnel..."

# Kill any existing cloudflared processes
pkill cloudflared 2>/dev/null || true
sleep 2

# Start tunnel
"$CLOUDFLARED_PATH" tunnel --url http://localhost:8000 > "$TUNNEL_LOG" 2>&1 &
TUNNEL_PID=$!
echo $TUNNEL_PID > "$PROJECT_ROOT/tunnel.pid"

# Wait for tunnel to establish
echo "Waiting for tunnel to establish..."
TUNNEL_URL=""
for i in {1..30}; do
    if [ -f "$TUNNEL_LOG" ]; then
        TUNNEL_URL=$(grep -o 'https://[^[:space:]]*\.trycloudflare\.com' "$TUNNEL_LOG" | head -1)
        if [ ! -z "$TUNNEL_URL" ]; then
            break
        fi
    fi
    sleep 1
done

if [ -z "$TUNNEL_URL" ]; then
    print_error "Failed to establish tunnel"
    cat "$TUNNEL_LOG"
    exit 1
fi

print_status "Tunnel established: $TUNNEL_URL"

# Test tunnel
if curl -s "$TUNNEL_URL/health" > /dev/null; then
    print_status "Tunnel is accessible"
else
    print_error "Tunnel is not accessible"
    exit 1
fi

# Step 3: Update Frontend Configuration
echo ""
echo "Configuring Frontend..."

# Update .env.local
echo "NEXT_PUBLIC_API_URL=$TUNNEL_URL" > "$ENV_FILE"
print_status "Updated $ENV_FILE with tunnel URL"

# Step 4: Deploy to Vercel (if requested)
if [ "$1" == "--deploy-vercel" ]; then
    echo ""
    echo "Deploying to Vercel..."
    
    cd "$PROJECT_ROOT/web"
    
    # Check if vercel CLI is installed
    if ! command -v vercel &> /dev/null; then
        print_error "Vercel CLI not installed. Install with: npm i -g vercel"
        exit 1
    fi
    
    # Set environment variable in Vercel
    print_warning "Setting NEXT_PUBLIC_API_URL in Vercel..."
    vercel env add NEXT_PUBLIC_API_URL production --force <<< "$TUNNEL_URL"
    
    # Deploy to Vercel
    print_warning "Deploying to Vercel..."
    vercel --prod
    
    print_status "Deployed to Vercel"
else
    # Start local frontend
    echo ""
    echo "Starting Frontend (Local)..."
    
    cd "$PROJECT_ROOT/web"
    
    # Kill existing frontend process
    if lsof -ti:3000 > /dev/null 2>&1; then
        print_warning "Port 3000 is already in use. Killing existing process..."
        lsof -ti:3000 | xargs kill -9 2>/dev/null || true
        sleep 2
    fi
    
    # Install dependencies
    $PM install > /dev/null 2>&1
    
    # Start frontend
    $PM run dev &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > "$PROJECT_ROOT/web/frontend.pid"
    
    # Wait for frontend
    echo "Waiting for frontend to start..."
    for i in {1..30}; do
        if curl -s http://localhost:3000 > /dev/null 2>&1; then
            print_status "Frontend is running on http://localhost:3000"
            break
        fi
        sleep 1
    done
fi

# Step 5: Display Summary
echo ""
echo "=================================================="
echo -e "${GREEN}Deployment Successful!${NC}"
echo "=================================================="
echo ""
echo "Backend API (Local): http://localhost:8000"
echo "Backend API (Tunnel): $TUNNEL_URL"
echo "API Documentation: $TUNNEL_URL/docs"

if [ "$1" != "--deploy-vercel" ]; then
    echo "Frontend (Local): http://localhost:3000"
fi

echo ""
echo "Tunnel URL: $TUNNEL_URL"
echo "This URL is configured in the frontend environment."
echo ""

# Step 6: Monitor tunnel health
if [ "$1" != "--deploy-vercel" ]; then
    echo "Monitoring tunnel health..."
    echo "Press Ctrl+C to stop all services"
    
    # Monitor tunnel connection
    while true; do
        if ! curl -s "$TUNNEL_URL/health" > /dev/null 2>&1; then
            print_warning "Tunnel connection lost. Attempting to reconnect..."
            
            # Kill old tunnel
            kill $TUNNEL_PID 2>/dev/null || true
            
            # Start new tunnel
            "$CLOUDFLARED_PATH" tunnel --url http://localhost:8000 > "$TUNNEL_LOG" 2>&1 &
            TUNNEL_PID=$!
            echo $TUNNEL_PID > "$PROJECT_ROOT/tunnel.pid"
            
            # Wait for new URL
            sleep 10
            NEW_TUNNEL_URL=$(grep -o 'https://[^[:space:]]*\.trycloudflare\.com' "$TUNNEL_LOG" | tail -1)
            
            if [ ! -z "$NEW_TUNNEL_URL" ] && [ "$NEW_TUNNEL_URL" != "$TUNNEL_URL" ]; then
                TUNNEL_URL=$NEW_TUNNEL_URL
                echo "NEXT_PUBLIC_API_URL=$TUNNEL_URL" > "$ENV_FILE"
                print_warning "Tunnel URL changed to: $TUNNEL_URL"
                print_warning "Frontend needs to be restarted to use new URL"
            fi
        fi
        sleep 30
    done
fi