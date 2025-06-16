#!/bin/bash

echo "==================================="
echo "Testing Railway Backend Connection"
echo "==================================="
echo ""

BACKEND_URL="https://sens-production.up.railway.app"

echo "1. Testing Health Endpoint..."
echo "   URL: $BACKEND_URL/health"
HEALTH_RESPONSE=$(curl -s "$BACKEND_URL/health")
echo "   Response: $HEALTH_RESPONSE"
echo ""

echo "2. Testing API Documentation..."
echo "   URL: $BACKEND_URL/docs"
DOCS_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BACKEND_URL/docs")
echo "   Status Code: $DOCS_STATUS"
echo ""

echo "3. Testing NL2SQL Endpoint..."
echo "   URL: $BACKEND_URL/api/nl2sql"
TEST_QUERY='{"query": "How many tables are in the database?"}'
echo "   Test Query: $TEST_QUERY"
NL2SQL_RESPONSE=$(curl -s -X POST "$BACKEND_URL/api/nl2sql" \
  -H "Content-Type: application/json" \
  -d "$TEST_QUERY" | jq -r '.error // .sql // "Unknown response"' 2>/dev/null || echo "Request failed")
echo "   Response: $NL2SQL_RESPONSE"
echo ""

echo "4. Testing CORS Headers..."
CORS_HEADERS=$(curl -s -I "$BACKEND_URL/health" | grep -i "access-control-allow-origin" || echo "No CORS headers found")
echo "   CORS Headers: $CORS_HEADERS"
echo ""

echo "==================================="
echo "Connection Test Complete!"
echo "==================================="
echo ""
echo "Summary:"
echo "- Backend URL: $BACKEND_URL"
echo "- Health Check: $([ "$HEALTH_RESPONSE" = '{"status":"healthy"}' ] && echo "✓ PASSED" || echo "✗ FAILED")"
echo "- API Docs: $([ "$DOCS_STATUS" = "200" ] && echo "✓ PASSED" || echo "✗ FAILED")"
echo "- CORS: $([ -n "$CORS_HEADERS" ] && echo "✓ Configured" || echo "✗ Not configured")"
echo ""
echo "To test with frontend:"
echo "1. Visit http://localhost:3001"
echo "2. Try a sample query"
echo "3. Check browser console for any errors"
