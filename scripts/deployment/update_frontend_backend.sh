#!/bin/bash

echo "==================================="
echo "Update Frontend Backend URL Script"
echo "==================================="
echo ""

# Instructions for getting Railway URL
echo "Step 1: Get your Railway backend URL"
echo "--------------------------------------"
echo "1. Go to https://railway.app/dashboard"
echo "2. Click on your 'sens-backend' project"
echo "3. Click on your backend service"
echo "4. Go to 'Settings' tab"
echo "5. Under 'Networking', click 'Generate Domain'"
echo "6. Copy the generated URL (e.g., https://sens-backend-production.up.railway.app)"
echo ""

# Get the backend URL from user
read -p "Enter your Railway backend URL: " BACKEND_URL

# Validate URL
if [[ ! "$BACKEND_URL" =~ ^https?:// ]]; then
    echo "Error: Invalid URL. Please include http:// or https://"
    exit 1
fi

echo ""
echo "Step 2: Updating frontend configuration"
echo "---------------------------------------"

# Update local development .env.local (optional)
if [ -f "web/.env.local" ]; then
    echo "Updating web/.env.local for local development..."
    sed -i.bak "s|NEXT_PUBLIC_API_URL=.*|NEXT_PUBLIC_API_URL=$BACKEND_URL|" web/.env.local
    echo "✓ Updated .env.local"
fi

# Create production env file
echo "Creating web/.env.production..."
cat > web/.env.production << EOF
# API Configuration
NEXT_PUBLIC_API_URL=$BACKEND_URL
NEXT_PUBLIC_APP_NAME=SENS

# Feature Flags
NEXT_PUBLIC_ENABLE_VISUALIZATIONS=true
NEXT_PUBLIC_ENABLE_EXPORT=true
NEXT_PUBLIC_ENABLE_SCHEMA_EXPLORER=true
EOF
echo "✓ Created .env.production"

echo ""
echo "Step 3: Deploy frontend to Vercel"
echo "---------------------------------"
echo "Option A: Via Vercel CLI"
echo "  cd web"
echo "  vercel --prod"
echo ""
echo "Option B: Via Vercel Dashboard"
echo "  1. Go to https://vercel.com/dashboard"
echo "  2. Import your GitHub repository"
echo "  3. Set environment variable:"
echo "     NEXT_PUBLIC_API_URL = $BACKEND_URL"
echo "  4. Deploy"
echo ""
echo "Option C: Update existing Vercel deployment"
echo "  1. Go to your project on Vercel"
echo "  2. Go to Settings → Environment Variables"
echo "  3. Add/Update:"
echo "     NEXT_PUBLIC_API_URL = $BACKEND_URL"
echo "  4. Redeploy"

echo ""
echo "==================================="
echo "Configuration Complete!"
echo "==================================="
echo "Backend URL: $BACKEND_URL"
echo ""
echo "Next steps:"
echo "1. Ensure your Railway backend is running"
echo "2. Deploy frontend to Vercel with the new environment variable"
echo "3. Your frontend will now connect to Railway backend!"
