#!/bin/bash

echo "Setting up Cloudflare Tunnel for remote access..."

# Install cloudflared
if ! command -v cloudflared &> /dev/null; then
    echo "Installing cloudflared..."
    wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
    sudo mv cloudflared-linux-amd64 /usr/local/bin/cloudflared
    sudo chmod +x /usr/local/bin/cloudflared
fi

# Create tunnel for frontend
echo "Creating tunnel for frontend (port 3000)..."
cloudflared tunnel --url http://localhost:3000 &
FRONTEND_TUNNEL_PID=$!

# Wait a bit for tunnel to establish
sleep 5

# Create tunnel for backend API
echo "Creating tunnel for backend API (port 8000)..."
cloudflared tunnel --url http://localhost:8000 &
BACKEND_TUNNEL_PID=$!

echo ""
echo "Cloudflare Tunnels are running!"
echo "Check the output above for your public URLs"
echo ""
echo "Press Ctrl+C to stop tunnels"

trap "kill $FRONTEND_TUNNEL_PID $BACKEND_TUNNEL_PID 2>/dev/null; exit" INT
wait