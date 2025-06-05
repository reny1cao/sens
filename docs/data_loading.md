# Comprehensive Data Loading Guide

This guide consolidates all information about loading financial data into SENS.

## Table of Contents
1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Database Schema](#database-schema)
4. [Data Sources](#data-sources)
5. [Loading Scripts](#loading-scripts)
6. [Strategic Loading Plan](#strategic-loading-plan)
7. [API Rate Limits](#api-rate-limits)
8. [Troubleshooting](#troubleshooting)
9. [Automation](#automation)

## Overview

SENS requires financial data to function effectively. The data loading system populates:
- **Real market data** from APIs (securities, prices, economic indicators)
- **Sample data** for expensive or user-specific features (portfolios, options, intraday)

### What Gets Loaded

| Data Type | Source | Records | Time |
|-----------|--------|---------|------|
| Securities | Alpha Vantage | 100+ stocks & ETFs | ~15 min |
| Daily Prices | Alpha Vantage | 2+ years history | 4-6 hours |
| Economic Indicators | FRED | 28 indicators | ~2 min |
| Portfolio Holdings | Generated | Sample data | Instant |
| Options Contracts | Generated | 25 contracts | Instant |
| Market Data | Generated | Intraday samples | Instant |

## Quick Start

```bash
# 1. Configure API keys
export SENS_ALPHA_VANTAGE_API_KEY="your_key"
export SENS_FRED_API_KEY="your_key"

# 2. Load all data (6-8 hours)
poetry run python scripts/comprehensive_data_loader.py

# 3. Verify data loaded
poetry run python scripts/comprehensive_data_loader.py --verify

# 4. Check detailed status
poetry run sens financial status --detailed
```

## Database Schema

The financial database includes 8 main tables:

### Core Tables (API-Populated)
1. **securities** - Company and ETF information
2. **daily_prices** - Historical prices (partitioned by month 2023-2026)
3. **economic_indicators** - FRED economic data
4. **financial_statements** - Quarterly/annual reports (future)

### Sample Tables (Generated)
5. **portfolio_holdings** - User's current positions
6. **trades** - Historical transactions
7. **options_contracts** - Options with Greeks
8. **market_data** - Intraday bid/ask data

## Data Sources

### Alpha Vantage (Free Tier)
- **What**: Stock prices, company info
- **Limits**: 5 calls/minute, 100/day
- **Cost**: Free (with limitations)

### FRED (Federal Reserve)
- **What**: Economic indicators
- **Limits**: 120 calls/minute
- **Cost**: Free

### Why Sample Data?
- **Portfolio/Trades**: User-specific, no universal API
- **Options**: Premium APIs cost $100-500/month
- **Intraday**: Real-time feeds cost $50-200/month

## Loading Scripts

### 1. Comprehensive Data Loader (Recommended)

The main script that handles everything:

```bash
poetry run python scripts/comprehensive_data_loader.py [options]
```

**Options:**
- `--reset` - Start fresh, clearing progress
- `--resume` - Continue from last interruption
- `--verify` - Check current data status

**Features:**
- Loads 100+ securities (70 stocks + 27 ETFs)
- Handles ETFs without API calls
- Progress tracking with JSON state
- Proper error handling and retry logic
- Foreign key constraint compliance

### 2. Quick Loaders (Deprecated)

These older scripts are superseded by the comprehensive loader:
- `quick_start_loader.py` - 35 essential symbols
- `auto_quick_start.py` - Automated version
- `strategic_loader.py` - Phased approach

### 3. Utility Scripts

```bash
# Analyze what's missing
poetry run python scripts/analyze_data_gaps.py

# Daily updates
poetry run sens financial update

# Validate data quality
poetry run python scripts/validate_financial_data.py
```

## Strategic Loading Plan

### Phase 1: Essential Coverage (Day 1)
1. **ETFs First** (No API needed)
   - Market indices: SPY, QQQ, DIA, IWM
   - Sectors: XLK, XLF, XLV, XLE, etc.
   - Bonds: TLT, AGG, HYG
   - Commodities: GLD, SLV, USO

2. **Major Stocks** (API calls)
   - Tech: AAPL, MSFT, GOOGL, AMZN, NVDA
   - Finance: JPM, BAC, GS, V
   - Healthcare: JNJ, UNH, PFE
   - Consumer: WMT, PG, DIS

3. **Economic Indicators**
   - Core: GDP, UNRATE, CPIAUCSL
   - Rates: DFF, DGS10, DGS2
   - Market: VIXCLS, DEXUSEU

### Phase 2: Sector Leaders (Day 2+)
- Technology expansion
- Healthcare leaders
- Financial services
- Energy sector
- Industrial companies

## API Rate Limits

### Alpha Vantage Strategy
```python
# Free tier: 5 calls/minute
# Solution: 12-second delays between calls

for symbol in symbols:
    load_data(symbol)
    time.sleep(12)  # Rate limit compliance
```

### Batch Processing
```python
# Load prices in batches of 5
# 60-second wait between batches
batch_size = 5
for batch in chunks(symbols, batch_size):
    load_batch(batch)
    time.sleep(60)
```

## Troubleshooting

### Common Issues

1. **Foreign Key Constraint Errors**
   ```
   ERROR: Key (symbol)=(SPY) is not present in table "securities"
   ```
   **Solution**: ETFs are loaded first by comprehensive loader

2. **Rate Limit Errors**
   ```
   Error: API call frequency exceeded
   ```
   **Solution**: Script includes automatic delays

3. **Missing _ctypes Module**
   ```
   ModuleNotFoundError: No module named '_ctypes'
   ```
   **Solution**: Python installation issue, doesn't affect data loading

4. **Data Not Showing**
   - Run `--verify` to check what's loaded
   - Check progress file: `scripts/loading_progress/comprehensive_progress.json`
   - Ensure schema extracted: `poetry run python scripts/extract_schema.py`

### Recovery Steps

```bash
# If data seems missing
poetry run python scripts/comprehensive_data_loader.py --verify

# If interrupted
poetry run python scripts/comprehensive_data_loader.py --resume

# If corrupted
poetry run python scripts/comprehensive_data_loader.py --reset
```

## Automation

### Daily Updates

Create a cron job for daily updates:

```bash
# Edit crontab
crontab -e

# Add daily update at 6 PM
0 18 * * * cd /path/to/sens && poetry run sens financial update
```

### Update Script
```bash
#!/bin/bash
# scripts/daily_update.sh

cd /home/user/sens
source .env
poetry run sens financial update
poetry run python scripts/analyze_data_gaps.py
```

## Progress Tracking

Progress saved in `scripts/loading_progress/comprehensive_progress.json`:

```json
{
  "securities_loaded": ["AAPL", "MSFT", ...],
  "etfs_loaded": ["SPY", "QQQ", ...],
  "prices_loaded": ["AAPL", "MSFT", ...],
  "indicators_loaded": ["GDP", "UNRATE", ...],
  "portfolios_created": true,
  "options_created": true,
  "market_data_created": true,
  "last_updated": "2025-06-05T10:30:00",
  "total_price_records": 50000,
  "total_statement_records": 0
}
```

## Best Practices

1. **First Time Setup**
   - Use comprehensive loader
   - Run during off-hours (6-8 hour process)
   - Monitor progress file

2. **Daily Maintenance**
   - Run `sens financial update` daily
   - Check for gaps weekly
   - Validate data monthly

3. **Development**
   - Use `--verify` before testing
   - Keep sample data for offline development
   - Don't commit API keys

## Summary

The comprehensive data loader is your one-stop solution for populating SENS with financial data. It handles:
- ✅ All database tables
- ✅ ETF loading without APIs
- ✅ Progress tracking
- ✅ Rate limit compliance
- ✅ Error recovery
- ✅ Sample data generation

Run it once, wait 6-8 hours, and you'll have a fully functional financial analysis system!