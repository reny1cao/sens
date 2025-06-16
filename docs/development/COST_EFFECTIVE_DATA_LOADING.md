# Cost-Effective Data Loading Guide for SENS

## 💰 Understanding API Costs

### Alpha Vantage (Stock Data)
- **Free Tier**: 25 API calls per day
- **Rate Limit**: 5 calls per minute
- **Cost**: $0 (but very limited)
- **Premium**: $49.99/month for 500 calls/day

### FRED (Economic Data)
- **Free Tier**: Unlimited API calls
- **Rate Limit**: 120 requests per minute
- **Cost**: $0 (completely free!)
- **Data**: 800,000+ economic time series

## 🎯 Cost-Effective Strategy

### Option 1: Minimal Cost ($0) - Recommended
Use the free tier strategically:

```bash
# Set up API keys locally
export SENS_ALPHA_VANTAGE_API_KEY="your-alpha-vantage-key"
export SENS_FRED_API_KEY="your-fred-key"

# Load data to Railway (uses ~20 API calls)
railway run python scripts/cost_effective_loader.py
```

This gives you:
- 5-6 major stocks with 1 year of data
- 15+ economic indicators with 2 years of data
- Enough data for meaningful demos

### Option 2: One-Time Load ($0)
Load sample data without any API calls:

```bash
# Use the existing sample data
railway run psql $DATABASE_URL < scripts/insert_sample_data.sql

# Or create more sample data
railway run python scripts/generate_sample_data.py
```

### Option 3: Scheduled Updates ($0)
Set up a daily cron job that respects limits:

```bash
# Add to Railway environment
railway variables --service sens --set "DAILY_SYMBOL_LIMIT=10"

# Run daily updater (uses exactly 20 calls)
railway run python scripts/daily_financial_update.py
```

## 📊 What You Get with Free Tier

### Day 1 (25 API calls):
- ✅ 12 companies with metadata (12 calls)
- ✅ 6 stocks with 1 year price data (12 calls)
- ✅ 15+ economic indicators (FREE)
- ⏱️ Total time: ~1 hour

### Day 2 (25 more calls):
- ✅ 6 more stocks with price data
- ✅ Update existing stock prices
- ✅ More economic indicators

### After 1 Week:
- 📈 20+ stocks with full price history
- 📊 50+ economic indicators
- 💾 ~500,000 data points

## 🚀 Quick Start Commands

### 1. Set Railway Environment Variables
```bash
# Add your API keys to Railway
railway variables --service sens --set "SENS_ALPHA_VANTAGE_API_KEY=your-key"
railway variables --service sens --set "SENS_FRED_API_KEY=your-key"

# Redeploy to pick up new variables
railway redeploy --service sens -y
```

### 2. Load Free Economic Data First
```bash
# This is completely FREE!
railway run python -c "
import asyncio
from sens.datasource.financial import FinancialDataLoader

async def load_fred():
    async with FinancialDataLoader() as loader:
        indicators = ['GDP', 'UNRATE', 'CPIAUCSL', 'FEDFUNDS', 'DGS10']
        for ind in indicators:
            data = await loader.load_economic_indicator(ind, days=730)
            print(f'Loaded {len(data)} points for {ind}')

asyncio.run(load_fred())
"
```

### 3. Load Critical Stocks Only
```bash
# Uses only 10 API calls
railway run python -c "
import asyncio
from sens.datasource.financial import FinancialDataLoader

async def load_minimal():
    async with FinancialDataLoader() as loader:
        # Load just SPY (S&P 500) and AAPL
        for symbol in ['SPY', 'AAPL']:
            await loader.load_company_info(symbol)
            prices = await loader.load_stock_prices(symbol, days=30)
            print(f'Loaded {symbol}: {len(prices)} days')
            await asyncio.sleep(15)  # Rate limit

asyncio.run(load_minimal())
"
```

## 💡 Money-Saving Tips

1. **Focus on ETFs**: Get broad market coverage with fewer symbols
   - SPY (S&P 500)
   - QQQ (NASDAQ)
   - DIA (Dow Jones)

2. **Use FRED for Everything Possible**:
   - Interest rates
   - Economic indicators
   - Exchange rates
   - Commodity prices

3. **Cache Aggressively**:
   - Historical data doesn't change
   - Only update recent prices daily

4. **Batch Updates**:
   - Run updates once per day
   - Update only the last few days of prices

## 📈 Example Queries After Loading

With minimal data, you can still run impressive queries:

```sql
-- Market overview
SELECT s.symbol, s.company_name,
       dp.close_price as latest_price,
       dp.close_price - LAG(dp.close_price, 30) OVER (PARTITION BY s.symbol ORDER BY dp.trade_date) as month_change
FROM securities s
JOIN daily_prices dp ON s.symbol = dp.symbol
WHERE dp.trade_date = (SELECT MAX(trade_date) FROM daily_prices WHERE symbol = s.symbol);

-- Economic dashboard
SELECT indicator_code, indicator_name,
       value as latest_value,
       date as latest_date
FROM economic_indicators
WHERE date = (SELECT MAX(date) FROM economic_indicators WHERE indicator_code = e.indicator_code);

-- Correlation analysis
SELECT 'SPY vs Interest Rates' as analysis,
       CORR(spy.close_price, rates.value) as correlation
FROM daily_prices spy
JOIN economic_indicators rates ON spy.trade_date = rates.date
WHERE spy.symbol = 'SPY' AND rates.indicator_code = 'DGS10';
```

## 🎯 Recommended Approach

1. **Start with cost_effective_loader.py** - Uses 20-25 API calls wisely
2. **Load all FREE FRED data** - Unlimited economic indicators
3. **Add sample data** - Fill gaps without API calls
4. **Set up daily updates** - Use remaining 5 calls/day for updates

This approach gives you a fully functional financial analysis system for $0!
