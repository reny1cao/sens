# Frontend Deployment Guide

## Backend URL Configuration

Your Railway backend is available at: `https://sens-production.up.railway.app`

Note: Railway handles port mapping internally, so you don't need to specify port 8080 in the URL.

## Frontend Configuration

### 1. Environment Files Created

- **Production**: `web/.env.production` - Points to Railway backend
- **Development**: `web/.env.local` - Points to localhost (with Railway URL commented out)

### 2. Deploy to Vercel

#### Option A: Using Vercel CLI

```bash
cd web
vercel --prod
```

When prompted for environment variables, they will be automatically loaded from `.env.production`.

#### Option B: Using Vercel Dashboard

1. Go to [vercel.com](https://vercel.com)
2. Import your repository (if not already done)
3. In Settings → Environment Variables, add:
   - **Key**: `NEXT_PUBLIC_API_URL`
   - **Value**: `https://sens-production.up.railway.app`
4. Deploy or redeploy

#### Option C: Direct GitHub Integration

If you've already connected your repo to Vercel:
1. Push the changes to GitHub
2. Vercel will automatically deploy with the new `.env.production` file

### 3. Configure Backend CORS (Railway Dashboard)

The backend currently allows all origins (`*`). For production security, you should restrict this:

1. Go to your Railway project dashboard
2. Click on your backend service
3. Go to Variables tab
4. Add or update:
   ```
   SENS_CORS_ORIGINS=https://your-app.vercel.app,https://your-custom-domain.com,http://localhost:3000
   ```
   Replace with your actual frontend URLs.

### 4. Verify the Connection

After deployment:
1. Visit your frontend URL
2. Open browser console (F12)
3. Try making a query
4. Check Network tab to ensure requests go to `https://sens-production.up.railway.app`

## Troubleshooting

### CORS Errors
If you see CORS errors:
- Ensure `SENS_CORS_ORIGINS` in Railway includes your frontend URL
- The backend logs will show the origin that's being blocked

### Connection Refused
If frontend can't connect:
- Verify Railway backend is running (check Railway dashboard)
- Ensure the URL is correct (no port number needed)
- Check if the health endpoint works: `https://sens-production.up.railway.app/health`

### Environment Variables Not Loading
- In Vercel, go to Settings → Environment Variables
- Ensure `NEXT_PUBLIC_API_URL` is set correctly
- Redeploy after changing environment variables

## Local Development

To test with Railway backend locally:
```bash
cd web
# Edit .env.local and uncomment the Railway URL
NEXT_PUBLIC_API_URL=https://sens-production.up.railway.app npm run dev
```
