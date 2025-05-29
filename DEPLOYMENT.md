# SENS Production Deployment Guide

This guide covers deploying SENS to production using:
- **Frontend**: Vercel (free tier)
- **Backend**: Railway (PostgreSQL + Redis included)
- **File Storage**: Cloudflare R2 or AWS S3

## Prerequisites

1. Install deployment tools:
   ```bash
   # Vercel CLI
   npm install -g vercel
   
   # Railway CLI
   curl -fsSL https://railway.app/install.sh | sh
   ```

2. Create accounts:
   - [Vercel](https://vercel.com) - for frontend
   - [Railway](https://railway.app) - for backend + database
   - [Cloudflare](https://dash.cloudflare.com) - for R2 storage (optional)

## Step 1: Deploy Backend to Railway

1. **Login to Railway**:
   ```bash
   railway login
   ```

2. **Create new project**:
   ```bash
   cd /path/to/sens
   railway init
   ```

3. **Add PostgreSQL and Redis**:
   - Go to your Railway project dashboard
   - Click "New" → "Database" → "Add PostgreSQL"
   - Click "New" → "Database" → "Add Redis"

4. **Configure environment variables**:
   - Copy `.env.production.example` content
   - In Railway dashboard, go to your service → Variables
   - Add all variables (Railway auto-populates database URLs)

5. **Deploy backend**:
   ```bash
   railway up
   ```

6. **Get your backend URL**:
   ```bash
   railway domain
   ```
   Example: `https://sens-backend.up.railway.app`

## Step 2: Set up File Storage (Cloudflare R2)

1. **Create R2 bucket**:
   - Go to Cloudflare dashboard → R2
   - Create bucket named `sens-uploads`
   - Enable public access if needed

2. **Create API token**:
   - Go to R2 → Manage API tokens
   - Create token with read/write permissions
   - Save the access key and secret

3. **Update Railway environment**:
   ```
   SENS_STORAGE_TYPE=r2
   SENS_STORAGE_BUCKET=sens-uploads
   SENS_STORAGE_ENDPOINT=https://YOUR_ACCOUNT_ID.r2.cloudflarestorage.com
   SENS_STORAGE_ACCESS_KEY=your_access_key
   SENS_STORAGE_SECRET_KEY=your_secret_key
   ```

## Step 3: Deploy Frontend to Vercel

1. **Login to Vercel**:
   ```bash
   vercel login
   ```

2. **Deploy frontend**:
   ```bash
   cd web
   vercel
   ```

3. **Configure environment**:
   ```bash
   # Add backend URL
   vercel env add NEXT_PUBLIC_API_URL production
   # Enter: https://your-backend.up.railway.app
   ```

4. **Deploy to production**:
   ```bash
   vercel --prod
   ```

## Step 4: Configure Custom Domains

### Backend (Railway):
1. Go to Railway dashboard → Settings → Domains
2. Add custom domain: `api.yourdomain.com`
3. Update DNS records as instructed

### Frontend (Vercel):
1. Go to Vercel dashboard → Settings → Domains
2. Add custom domain: `app.yourdomain.com`
3. Update DNS records as instructed

## Step 5: Post-Deployment

1. **Update CORS settings** in Railway:
   ```
   SENS_CORS_ORIGINS=https://app.yourdomain.com
   ```

2. **Test the deployment**:
   - Visit `https://app.yourdomain.com`
   - Upload a test CSV file
   - Run a query

3. **Set up monitoring**:
   - Railway: Built-in metrics dashboard
   - Vercel: Analytics dashboard
   - Add error tracking (Sentry recommended)

## Environment Variables Reference

### Backend (Railway)
```env
# Core
SENS_ENVIRONMENT=production

# Database (auto-populated by Railway)
SENS_DB_HOST=${{PGHOST}}
SENS_DB_PORT=${{PGPORT}}
SENS_DB_NAME=${{PGDATABASE}}
SENS_DB_USER=${{PGUSER}}
SENS_DB_PASSWORD=${{PGPASSWORD}}

# Redis (auto-populated by Railway)
SENS_REDIS_URL=${{REDIS_URL}}

# OpenRouter
SENS_OPENROUTER_API_KEY=sk-or-v1-xxxxx

# Storage
SENS_STORAGE_TYPE=r2
SENS_STORAGE_BUCKET=sens-uploads
SENS_STORAGE_ENDPOINT=https://xxx.r2.cloudflarestorage.com
SENS_STORAGE_ACCESS_KEY=xxx
SENS_STORAGE_SECRET_KEY=xxx

# Security
SENS_CORS_ORIGINS=https://app.yourdomain.com
```

### Frontend (Vercel)
```env
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
```

## Deployment Script

Use the automated deployment script:
```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

## Troubleshooting

### CORS Issues
- Ensure `SENS_CORS_ORIGINS` matches your frontend URL exactly
- Include protocol (https://)

### File Upload Issues
- Check storage credentials
- Verify bucket permissions
- Check file size limits

### Database Connection Issues
- Railway auto-injects database credentials
- Use the template variables (e.g., ${{PGHOST}})

## Cost Estimates

- **Vercel**: Free tier (100GB bandwidth/month)
- **Railway**: ~$5-10/month (usage-based)
- **Cloudflare R2**: Free tier (10GB storage, 1M requests/month)

Total: ~$5-10/month for a production deployment

## Scaling Considerations

1. **Database**: Railway PostgreSQL can be scaled vertically
2. **Backend**: Increase Railway replicas for high traffic
3. **Storage**: R2 scales automatically
4. **Frontend**: Vercel handles scaling automatically

## Security Checklist

- [ ] Set strong database password
- [ ] Configure CORS properly
- [ ] Use HTTPS everywhere
- [ ] Set up rate limiting
- [ ] Enable audit logging
- [ ] Regular security updates
- [ ] Backup database regularly