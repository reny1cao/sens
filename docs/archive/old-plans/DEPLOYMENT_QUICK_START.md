# SENS Deployment Quick Start

## Local Development with Cloudflare Tunnel

For quick testing and sharing your local development:

1. **Start both services locally:**
   ```bash
   # Linux/WSL
   ./scripts/start_all_linux.sh
   
   # macOS
   ./scripts/start_all.sh
   ```

2. **Create public tunnels:**
   ```bash
   ./scripts/setup_cloudflare_tunnel.sh
   ```
   
   This will give you public URLs like:
   - Frontend: `https://random-name.trycloudflare.com`
   - Backend: `https://another-random-name.trycloudflare.com`

3. **Update frontend to use tunnel backend:**
   ```bash
   # In web/.env.local
   NEXT_PUBLIC_API_URL=https://your-backend-tunnel.trycloudflare.com
   ```

## Production Deployment

### Option 1: Automated Deployment
```bash
./scripts/deploy.sh
```

This will:
- Deploy backend to Railway
- Deploy frontend to Vercel
- Configure environment variables

### Option 2: Manual Deployment

**Backend (Railway):**
```bash
railway login
railway init
railway up
```

**Frontend (Vercel):**
```bash
cd web
vercel --prod
```

## Quick Test

1. Visit your frontend URL
2. Upload a CSV file
3. Try queries like:
   - "How many rows are there?"
   - "Show me the first 5 records"
   - "What's the average of [numeric column]?"

## Current Status

✅ Backend running at: http://localhost:8000
✅ Frontend running at: http://localhost:3000
✅ API Documentation: http://localhost:8000/docs

## Environment Variables

See `.env.example` for required variables:
- `SENS_OPENROUTER_API_KEY` - Required for LLM
- `SENS_DB_*` - Database configuration
- `NEXT_PUBLIC_API_URL` - Backend URL for frontend