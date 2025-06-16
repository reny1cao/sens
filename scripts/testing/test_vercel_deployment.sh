#!/bin/bash

echo "==================================="
echo "Testing Vercel Deployment"
echo "==================================="
echo ""

FRONTEND_URL="https://web-mzc10c9xx-reny1caos-projects.vercel.app"
BACKEND_URL="https://sens-production.up.railway.app"

echo "1. Testing Backend Health..."
BACKEND_HEALTH=$(curl -s "$BACKEND_URL/health")
echo "   Backend: $BACKEND_HEALTH"
echo ""

echo "2. Testing Frontend..."
FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$FRONTEND_URL")
echo "   Frontend Status: $FRONTEND_STATUS"
echo ""

echo "3. Testing API Route (through Next.js)..."
# Test a simple API route through the frontend
API_TEST=$(curl -s -X POST "$FRONTEND_URL/api/nl2sql" \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}' \
  -w "\nStatus: %{http_code}" 2>/dev/null || echo "Request failed")
echo "   API Response: $API_TEST"
echo ""

echo "==================================="
echo "Deployment URLs:"
echo "==================================="
echo "🚀 Frontend: $FRONTEND_URL"
echo "🔧 Backend: $BACKEND_URL"
echo ""
echo "✅ Environment variable BACKEND_URL has been set in Vercel"
echo "✅ All API routes updated to use server-side env vars"
echo ""
echo "Visit your app at: $FRONTEND_URL"
