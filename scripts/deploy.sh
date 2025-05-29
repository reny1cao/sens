#!/bin/bash

echo "==================================="
echo "SENS Full Deployment Script"
echo "==================================="

# Check if required tools are installed
command -v vercel >/dev/null 2>&1 || { echo "Vercel CLI not installed. Install with: npm i -g vercel"; exit 1; }
command -v railway >/dev/null 2>&1 || { echo "Railway CLI not installed. Install from: https://docs.railway.app/develop/cli"; exit 1; }

# Deploy Backend to Railway
echo ""
echo "1. Deploying Backend to Railway..."
echo "=================================="
railway login
railway link
railway up

# Get the Railway deployment URL
BACKEND_URL=$(railway status --json | jq -r '.url')
echo "Backend deployed at: $BACKEND_URL"

# Deploy Frontend to Vercel
echo ""
echo "2. Deploying Frontend to Vercel..."
echo "=================================="
cd web

# Set the backend URL as environment variable
vercel env add NEXT_PUBLIC_API_URL production <<< "$BACKEND_URL"

# Deploy
vercel --prod

echo ""
echo "==================================="
echo "Deployment Complete!"
echo "==================================="
echo ""
echo "Backend API: $BACKEND_URL"
echo "Frontend: Check Vercel output above"
echo ""
echo "Next steps:"
echo "1. Add custom domain in Vercel dashboard"
echo "2. Configure environment variables in Railway"
echo "3. Set up monitoring and alerts"