# SENS Deployment Checklist

This checklist ensures smooth deployment of SENS with Cloudflare Tunnel and Vercel.

## Pre-Deployment Checklist

### Backend Requirements
- [ ] Python 3.11+ installed
- [ ] Poetry installed
- [ ] All dependencies installed: `poetry install`
- [ ] Environment variables configured in `.env`:
  - [ ] `SENS_DB_URL` (database connection)
  - [ ] `SENS_OPENROUTER_API_KEY` (LLM API key)
  - [ ] `SENS_REDIS_URL` (optional, for session persistence)
- [ ] Database migrations applied (if any)
- [ ] Tests passing: `poetry run pytest`

### Frontend Requirements
- [ ] Node.js 18+ installed
- [ ] pnpm or npm installed
- [ ] Dependencies installed: `cd web && pnpm install`
- [ ] Environment configured (`.env.local` for dev, Vercel env for prod)

### Infrastructure Requirements
- [ ] Cloudflared binary available (auto-downloaded by scripts)
- [ ] Vercel CLI installed (for production deployment): `npm i -g vercel`
- [ ] Ports 8000 and 3000 available (for local deployment)

## Local Development Deployment

1. **Quick Start (All-in-One)**
   ```bash
   ./scripts/setup_development_with_tunnel.sh
   ```
   This script handles everything automatically.

2. **Manual Deployment**
   - [ ] Start backend: `poetry run uvicorn sens.api.app:app --reload --host 0.0.0.0 --port 8000`
   - [ ] Verify backend health: `curl http://localhost:8000/health`
   - [ ] Start Cloudflare tunnel: `cloudflared tunnel --url http://localhost:8000`
   - [ ] Note tunnel URL from output
   - [ ] Update `web/.env.local` with tunnel URL
   - [ ] Start frontend: `cd web && pnpm run dev`
   - [ ] Verify frontend: `http://localhost:3000`

## Production Deployment

### Option A: Local Backend with Cloudflare Tunnel + Vercel Frontend

1. **Prepare Production Tunnel**
   - [ ] Login to Cloudflare: `cloudflared tunnel login`
   - [ ] Create named tunnel: `cloudflared tunnel create sens-prod`
   - [ ] Configure DNS routing (if using custom domain)
   - [ ] Create tunnel config file

2. **Deploy with Script**
   ```bash
   ./scripts/deploy_with_tunnel.sh --deploy-vercel
   ```

3. **Manual Steps**
   - [ ] Start backend in production mode
   - [ ] Start authenticated Cloudflare tunnel
   - [ ] Set `NEXT_PUBLIC_API_URL` in Vercel dashboard
   - [ ] Deploy frontend: `cd web && vercel --prod`

### Option B: Cloud Backend + Vercel Frontend

1. **Deploy Backend**
   - [ ] Choose platform (Railway, AWS, Heroku, etc.)
   - [ ] Configure environment variables
   - [ ] Deploy backend code
   - [ ] Note backend URL

2. **Deploy Frontend**
   - [ ] Set `NEXT_PUBLIC_API_URL` in Vercel to backend URL
   - [ ] Run: `cd web && vercel --prod`

## Post-Deployment Verification

### Backend Health Checks
- [ ] API health endpoint: `curl https://your-backend-url/health`
- [ ] API docs accessible: `https://your-backend-url/docs`
- [ ] Database connection working
- [ ] LLM integration working

### Frontend Checks
- [ ] Frontend loads without errors
- [ ] Can submit queries through UI
- [ ] Results display correctly
- [ ] Session management working
- [ ] File upload working (if applicable)

### Integration Tests
- [ ] Test simple query: "show me all tables"
- [ ] Test complex query with joins
- [ ] Test error handling (invalid query)
- [ ] Test session persistence
- [ ] Test concurrent users

## Monitoring Setup

### Cloudflare Tunnel Monitoring
- [ ] Monitor tunnel logs for disconnections
- [ ] Set up alerts for tunnel downtime
- [ ] Plan for tunnel URL rotation (if using free tier)

### Application Monitoring
- [ ] Backend logs accessible
- [ ] Frontend error tracking configured
- [ ] Performance metrics collection enabled
- [ ] Database query monitoring

## Troubleshooting Guide

### Common Issues

1. **Tunnel Connection Lost**
   - Check if backend is still running
   - Restart cloudflared process
   - Update frontend with new tunnel URL if changed

2. **Frontend Can't Connect to Backend**
   - Verify `NEXT_PUBLIC_API_URL` is correct
   - Check CORS configuration
   - Test backend directly with curl

3. **Session Issues**
   - Check Redis connection (if using)
   - Verify session headers are passed correctly
   - Check backend session storage

4. **Performance Issues**
   - Monitor backend CPU/memory usage
   - Check database query performance
   - Review Cloudflare tunnel metrics
   - Consider upgrading to authenticated tunnel

## Security Checklist

- [ ] Remove debug mode in production
- [ ] Secure all API keys and secrets
- [ ] Enable HTTPS only (handled by Cloudflare/Vercel)
- [ ] Review CORS settings for production
- [ ] Implement rate limiting if needed
- [ ] Regular security updates for dependencies

## Rollback Plan

1. **Frontend Rollback**
   - Vercel provides instant rollback in dashboard
   - Or redeploy previous commit: `vercel --prod`

2. **Backend Rollback**
   - Keep previous version running until new version is verified
   - Switch tunnel to point to old version if needed
   - Database rollback plan (if schema changed)

## Maintenance Tasks

### Daily
- [ ] Check tunnel health
- [ ] Monitor error logs
- [ ] Review performance metrics

### Weekly
- [ ] Update dependencies: `poetry update` and `pnpm update`
- [ ] Review and rotate logs
- [ ] Check for security advisories

### Monthly
- [ ] Full system backup
- [ ] Performance optimization review
- [ ] Security audit
- [ ] Update documentation

## Contact for Issues

- Backend issues: Check logs at `/logs` endpoint
- Frontend issues: Check browser console and Vercel logs
- Tunnel issues: Check cloudflared logs
- Database issues: Check connection and query logs