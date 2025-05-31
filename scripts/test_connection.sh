#!/bin/bash

echo "Testing SENS Connection..."
echo "========================="

# Test local backend
echo "1. Testing local backend..."
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✓ Local backend is running"
else
    echo "✗ Local backend is not responding"
    exit 1
fi

# Get tunnel URL from frontend env
TUNNEL_URL=""
if [ -f "/home/rc65619/workplace/sens/web/.env.local" ]; then
    TUNNEL_URL=$(grep NEXT_PUBLIC_API_URL /home/rc65619/workplace/sens/web/.env.local | cut -d'=' -f2)
fi

if [ ! -z "$TUNNEL_URL" ] && [ "$TUNNEL_URL" != "http://localhost:8000" ]; then
    echo "2. Testing tunnel connection..."
    echo "   Tunnel URL: $TUNNEL_URL"
    
    if curl -s "$TUNNEL_URL/health" > /dev/null; then
        echo "✓ Tunnel is working"
        
        echo "3. Testing API endpoint through tunnel..."
        RESPONSE=$(curl -s -X POST "$TUNNEL_URL/api/nl2sql" \
            -H "Content-Type: application/json" \
            -d '{"question": "test"}' \
            | jq -r '.error // "success"' 2>/dev/null || echo "api_error")
        
        if [ "$RESPONSE" != "api_error" ]; then
            echo "✓ API endpoint is accessible through tunnel"
        else
            echo "✗ API endpoint failed through tunnel"
        fi
    else
        echo "✗ Tunnel is not responding"
    fi
else
    echo "2. No tunnel URL configured (using local development)"
fi

# Test frontend
echo "4. Testing frontend..."
if curl -s http://localhost:3000 > /dev/null; then
    echo "✓ Frontend is running"
else
    echo "✗ Frontend is not responding"
fi

echo ""
echo "Test completed!"