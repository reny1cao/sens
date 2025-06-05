# Cloudflare Tunnel Deployment Pattern

This document describes the deployment pattern for SENS using Cloudflare Tunnel for backend exposure and Vercel for frontend hosting.

## Architecture Overview

```
[Vercel Frontend] --> [Cloudflare Tunnel] --> [Local/Cloud Backend]
```

- **Frontend**: Next.js app deployed on Vercel
- **Backend**: FastAPI running locally or on a cloud server
- **Tunnel**: Cloudflare Tunnel exposes backend API to the internet

## Key Components

### 1. Backend API (FastAPI)
- Runs on `http://localhost:8000`
- Exposed via Cloudflare Tunnel with a public URL
- No need for complex firewall rules or port forwarding

### 2. Cloudflare Tunnel
- Creates secure connection from backend to Cloudflare's edge
- Provides HTTPS URL: `https://*.trycloudflare.com`
- Free tier tunnels are ephemeral (URL changes on restart)
- Production should use authenticated tunnels for stable URLs

### 3. Frontend (Next.js)
- Deployed on Vercel
- Uses `NEXT_PUBLIC_API_URL` environment variable
- API route proxy at `/api/nl2sql` forwards to backend

## Deployment Steps

### Local Development with Tunnel

1. **Start Backend**
   ```bash
   poetry run uvicorn sens.api.app:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Create Cloudflare Tunnel**
   ```bash
   cloudflared tunnel --url http://localhost:8000
   ```
   Note the generated URL (e.g., `https://county-illustration-experiments-tears.trycloudflare.com`)

3. **Update Frontend Environment**
   ```bash
   echo "NEXT_PUBLIC_API_URL=https://your-tunnel-url.trycloudflare.com" > web/.env.local
   ```

4. **Start Frontend**
   ```bash
   cd web && pnpm run dev
   ```

### Production Deployment

1. **Backend Deployment Options**
   - **Option A**: Keep backend local with persistent Cloudflare Tunnel
   - **Option B**: Deploy to cloud (Railway, AWS, etc.) with Cloudflare Tunnel
   - **Option C**: Deploy to cloud with direct HTTPS endpoint

2. **Cloudflare Tunnel Setup (Production)**
   ```bash
   # Login to Cloudflare
   cloudflared tunnel login
   
   # Create named tunnel
   cloudflared tunnel create sens-backend
   
   # Create config file
   cat > ~/.cloudflared/config.yml << EOF
   tunnel: sens-backend
   credentials-file: /home/user/.cloudflared/TUNNEL_ID.json
   
   ingress:
     - hostname: api.yourdomain.com
       service: http://localhost:8000
     - service: http_status:404
   EOF
   
   # Route traffic
   cloudflared tunnel route dns sens-backend api.yourdomain.com
   
   # Run tunnel
   cloudflared tunnel run sens-backend
   ```

3. **Vercel Deployment**
   ```bash
   # Set production environment variable
   vercel env add NEXT_PUBLIC_API_URL production
   # Enter: https://api.yourdomain.com
   
   # Deploy
   cd web && vercel --prod
   ```

## Environment Variables

### Frontend (.env.local / Vercel Environment)
```env
# Development with tunnel
NEXT_PUBLIC_API_URL=https://your-tunnel.trycloudflare.com

# Production with custom domain
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
```

### Backend (.env)
```env
# Standard backend configuration
SENS_DB_URL=your_database_url
SENS_OPENROUTER_API_KEY=your_api_key
SENS_REDIS_URL=redis://localhost:6379  # Optional
```

## Important Considerations

### 1. Tunnel URL Stability
- Free tunnels generate new URLs on each restart
- Use authenticated tunnels for production
- Consider implementing a URL update mechanism

### 2. CORS Configuration
- Backend allows all origins by default (configured in FastAPI)
- Frontend proxy handles CORS for client requests
- Vercel.json includes CORS headers for API routes

### 3. Session Management
- Sessions use `X-Session-Id` header
- Backend stores sessions in Redis (with memory fallback)
- Frontend includes session ID in all requests

### 4. Error Handling
- Frontend shows "Failed to connect to backend" on connection errors
- Tunnel connection errors appear as DNS resolution failures
- Always verify tunnel URL is accessible before deployment

## Monitoring and Troubleshooting

### Check Tunnel Status
```bash
# View tunnel logs
tail -f tunnel.log

# Test tunnel connectivity
curl https://your-tunnel.trycloudflare.com/health
```

### Check Frontend API Connection
```bash
# Test API route
curl -X POST http://localhost:3000/api/nl2sql \
  -H "Content-Type: application/json" \
  -d '{"question": "test", "source_type": "duckdb"}'
```

### Common Issues

1. **"getaddrinfo ENOTFOUND" Error**
   - Tunnel URL is invalid or expired
   - Restart tunnel and update `.env.local`

2. **"Failed to connect to backend"**
   - Backend is not running
   - Tunnel is not connected
   - Wrong URL in environment variable

3. **CORS Errors**
   - Check Vercel.json headers configuration
   - Verify backend CORS middleware settings

## Automated Deployment Script

See `scripts/deploy_with_tunnel.sh` for automated deployment process.