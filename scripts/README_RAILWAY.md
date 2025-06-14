# Railway Database Scripts

These scripts help you work with SENS when deployed on Railway.

## Prerequisites

1. Install Railway CLI:
   ```bash
   curl -fsSL https://railway.app/install.sh | sh
   ```

2. Login to Railway:
   ```bash
   railway login
   ```

3. Link your project:
   ```bash
   railway link
   ```

## Scripts

### test_railway_connection.py

Tests connection to Railway PostgreSQL database and checks schema.

```bash
# Run with Railway environment variables
railway run python scripts/test_railway_connection.py

# Or export DATABASE_URL locally
export DATABASE_URL="your-railway-database-url"
python scripts/test_railway_connection.py
```

### railway_data_loader.py

Loads financial data into Railway database.

```bash
# Load minimal test data (default)
railway run python scripts/railway_data_loader.py

# Load quick start data
railway run -e LOAD_TYPE=quick python scripts/railway_data_loader.py

# Load full data
railway run -e LOAD_TYPE=full python scripts/railway_data_loader.py
```

### insert_sample_data.sql

SQL script with sample data for testing.

```bash
# Get DATABASE_URL from Railway
railway variables | grep DATABASE_URL

# Run with psql
psql $DATABASE_URL < scripts/insert_sample_data.sql

# Or with Railway
railway run psql $DATABASE_URL < scripts/insert_sample_data.sql
```

## Security Notes

- Never commit database credentials to the repository
- Always use environment variables for sensitive data
- Use `railway run` to automatically inject Railway environment variables
- For local development, export DATABASE_URL or individual SENS_DB_* variables

## Environment Variables

The scripts support both formats:

1. **DATABASE_URL** (preferred):
   ```bash
   export DATABASE_URL="postgresql://user:password@host:port/database"
   ```

2. **Individual variables**:
   ```bash
   export SENS_DB_HOST="host"
   export SENS_DB_PORT="5432"
   export SENS_DB_NAME="database"
   export SENS_DB_USER="user"
   export SENS_DB_PASSWORD="password"
   ```
