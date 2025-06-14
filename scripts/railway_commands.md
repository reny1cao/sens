# Railway Data Loading Commands

## Quick Reference

### 1. Load Minimal Test Data (3 symbols, ~5 minutes)
```bash
railway run python scripts/railway_data_loader.py
# OR
railway run -e LOAD_TYPE=minimal python scripts/railway_data_loader.py
```

### 2. Load Quick Start Data (35 symbols, 4-6 hours)
```bash
railway run -e LOAD_TYPE=quick python scripts/railway_data_loader.py
```

### 3. Load Full Data (100+ symbols, 8-12 hours)
```bash
railway run -e LOAD_TYPE=full python scripts/railway_data_loader.py
```

### 4. Check Data Status
```bash
railway run poetry run sens financial status --detailed
```

### 5. Direct Database Connection (for debugging)
```bash
# Get connection string
railway variables | grep DATABASE_URL

# Connect with psql
railway run psql $DATABASE_URL -c "SELECT COUNT(*) FROM securities;"
```

## Local Development with Railway DB

### Option A: Using DATABASE_URL
```bash
# Get Railway database URL
railway variables | grep DATABASE_URL

# Export it locally
export DATABASE_URL="postgresql://..."

# Run scripts
python scripts/railway_data_loader.py
```

### Option B: Using Individual Variables
```bash
# Get all database variables
railway variables

# Export them
export SENS_DB_HOST="monorail.proxy.rlwy.net"
export SENS_DB_PORT="12345"
export SENS_DB_NAME="railway"
export SENS_DB_USER="postgres"
export SENS_DB_PASSWORD="your-password"

# Run scripts
poetry run python scripts/load_minimal_test_data.py
```

## Monitoring Progress

### Check logs in Railway dashboard
```bash
railway logs --tail 100
```

### Or use the web dashboard
1. Go to Railway dashboard
2. Click on your service
3. View "Logs" tab

## Troubleshooting

### Connection Issues
- Ensure your local IP is allowed (Railway dashboard → Settings → Networking)
- Check if DATABASE_URL is properly set
- Try using railway proxy for secure connection

### Rate Limit Issues
- Alpha Vantage: 5 calls/minute
- Use LOAD_TYPE=minimal first to test
- Consider running during off-peak hours
