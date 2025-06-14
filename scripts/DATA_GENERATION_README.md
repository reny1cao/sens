# SENS Test Data Generation Scripts

This directory contains scripts for generating test data for the SENS agent testing framework.

## Overview

The SENS agent needs comprehensive financial data to test its value discovery and mapping capabilities. These scripts populate the database with realistic test data including:

- **Securities**: Stocks with name variations (e.g., "Apple", "AAPL", "Apple Inc.")
- **Daily Prices**: Historical price data with technical indicators
- **Economic Indicators**: GDP, unemployment rate, federal funds rate, etc.
- **Financial Statements**: Quarterly earnings data
- **Portfolio Data**: Sample trades and holdings
- **Market Data**: Real-time bid/ask spreads

## Scripts

### 1. `load_agent_test_data.py` (Quick Start)
**Purpose**: Load essential test data quickly for agent testing
**Runtime**: ~1-2 minutes
**Data Generated**:
- 18 securities (tech, finance, healthcare, consumer)
- 90 days of price data
- 5 economic indicators

```bash
poetry run python scripts/load_agent_test_data.py
```

### 2. `generate_comprehensive_test_data.py` (Full Dataset)
**Purpose**: Generate comprehensive test data with edge cases
**Runtime**: ~5-10 minutes
**Data Generated**:
- 50+ securities across all sectors
- 2 years of historical prices
- 14 economic indicators
- Financial statements (8 quarters)
- Sample trades and portfolios
- Intraday market data

```bash
poetry run python scripts/generate_comprehensive_test_data.py
```

### 3. `generate_sample_data.py` (Legacy)
**Purpose**: Original sample data generator
**Note**: Use the newer scripts above for better test coverage

## Test Scenarios Supported

### Value Mapping Tests
- Company name variations: "Apple" → "AAPL"
- Sector variations: "technology" → "Technology"
- Abbreviations: "MS" → "MSFT" (Microsoft)
- Old names: "Facebook" → "META"

### Query Pattern Tests
```sql
-- Name variation handling
"Show me Apple stock" → Maps to AAPL

-- Sector queries
"Technology companies" → Finds all tech stocks

-- Similar companies
"Stocks like Tesla" → Finds similar growth stocks

-- Multi-table queries
"GDP vs stock market" → Joins economic and price data

-- Date handling
"Last month's performance" → Handles relative dates
```

## Database Schema

The scripts populate these tables:
- `securities`: Company information with sectors
- `daily_prices`: OHLCV data with technical indicators
- `economic_indicators`: Macro economic data
- `financial_statements`: Quarterly earnings
- `trades`: Transaction history
- `portfolio_holdings`: Current positions
- `market_data`: Real-time spreads

## Usage for Agent Testing

1. **First Time Setup**:
   ```bash
   # Create schema if needed
   poetry run python scripts/create_financial_schema.sql

   # Load test data (quick)
   poetry run python scripts/load_agent_test_data.py
   ```

2. **Run Agent Tests**:
   ```bash
   poetry run python test_agent_improvements.py
   ```

3. **Test Specific Scenarios**:
   ```python
   # The test data includes these edge cases:

   # Name variations
   queries = [
       "Show me Apple stock",      # Apple → AAPL
       "Microsoft performance",    # Microsoft → MSFT
       "Google vs Facebook",       # Google → GOOGL, Facebook → META
   ]

   # Sector queries
   queries = [
       "Technology stocks",        # Normalized sector search
       "Bank stocks",             # Finance sector
       "Healthcare companies",    # Healthcare sector
   ]

   # Value discovery
   queries = [
       "Stocks similar to Tesla", # Find similar volatile growth stocks
       "Companies like Apple",    # Find similar large cap tech
   ]
   ```

## Troubleshooting

### No Data Returned
- Check if data was loaded: `poetry run sens financial status`
- Verify database connection: `poetry run python scripts/test_railway_connection.py`

### Slow Performance
- Create indexes: The comprehensive script creates performance indexes
- Use the quick loader for faster iteration

### Data Inconsistencies
- Clear and reload: The scripts clear existing data before loading
- Check for partial loads in logs

## Development Tips

1. **Adding New Test Cases**:
   - Add to `ESSENTIAL_TEST_DATA` in `load_agent_test_data.py`
   - Include name variations in the `aliases` field

2. **Testing Specific Dates**:
   - Modify `days` parameter to generate different date ranges
   - Default is 90 days (quick) or 730 days (comprehensive)

3. **Custom Volatility**:
   - Adjust `VOLATILITY_PROFILES` for different price patterns
   - Useful for testing trend detection

## Next Steps

After loading test data:
1. Run agent tests: `python test_agent_improvements.py`
2. Check agent logs for value mapping discoveries
3. Verify SQL generation handles variations correctly
4. Test with natural language queries in the CLI
