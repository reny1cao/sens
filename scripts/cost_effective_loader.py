#!/usr/bin/env python3
"""
Cost-Effective Data Loader for SENS.
Optimized to minimize API calls while maximizing data value.

Alpha Vantage Free Tier: 25 API calls per day
FRED: Unlimited calls
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from strategic_loader import ProgressTracker  # noqa: E402

from sens.datasource.financial import FinancialDataLoader  # noqa: E402

# High-value symbols only - carefully selected for maximum coverage
COST_EFFECTIVE_SYMBOLS = {
    "Core Holdings": [
        "SPY",  # S&P 500 - represents overall market
        "AAPL",  # Tech giant - most valuable company
        "MSFT",  # Tech giant - enterprise software
        "GOOGL",  # Tech giant - search/cloud
        "AMZN",  # E-commerce/cloud leader
    ],
    "Sector Representatives": [
        "XLF",  # Financial sector ETF
        "XLK",  # Technology sector ETF
        "XLV",  # Healthcare sector ETF
        "XLE",  # Energy sector ETF
    ],
    "Market Indicators": [
        "VIX",  # Volatility index
        "TLT",  # Long-term treasuries
        "GLD",  # Gold prices
    ],
}

# FRED indicators - these are FREE!
ECONOMIC_INDICATORS = [
    # Core Economic Data
    "GDP",  # Gross Domestic Product
    "UNRATE",  # Unemployment Rate
    "CPIAUCSL",  # Consumer Price Index
    "FEDFUNDS",  # Federal Funds Rate
    # Market Indicators
    "DGS10",  # 10-Year Treasury Rate
    "DGS2",  # 2-Year Treasury Rate
    "VIXCLS",  # CBOE Volatility Index
    # Additional Economic Data
    "HOUST",  # Housing Starts
    "INDPRO",  # Industrial Production Index
    "PAYEMS",  # All Employees: Total Nonfarm
    "UMCSENT",  # University of Michigan Consumer Sentiment
    # Exchange Rates
    "DEXUSEU",  # US Dollar to Euro
    "DEXCHUS",  # US Dollar to Chinese Yuan
    "DEXJPUS",  # US Dollar to Japanese Yen
]


async def cost_effective_load():
    """Load data in a cost-effective manner."""
    print("💰 COST-EFFECTIVE DATA LOADER FOR SENS")
    print("=" * 60)
    print("Strategy: Minimize API costs while maximizing data value")
    print("Alpha Vantage: 25 calls/day limit (free tier)")
    print("FRED: Unlimited calls")
    print("=" * 60)

    # Calculate what we can do with 25 API calls
    all_symbols = []
    for category, symbols in COST_EFFECTIVE_SYMBOLS.items():
        all_symbols.extend(symbols)

    total_symbols = len(all_symbols)

    print("\n📊 Data Loading Plan:")
    print(f"- {total_symbols} key stocks (using {total_symbols * 2} API calls)")
    print(f"- {len(ECONOMIC_INDICATORS)} economic indicators (FREE via FRED)")
    print(f"- Total Alpha Vantage API calls: ~{total_symbols * 2}/25 daily limit")

    # Check if we have API keys
    av_key = os.getenv("SENS_ALPHA_VANTAGE_API_KEY")
    fred_key = os.getenv("SENS_FRED_API_KEY")

    if not av_key:
        print("\n❌ SENS_ALPHA_VANTAGE_API_KEY not found!")
        print("Please set: export SENS_ALPHA_VANTAGE_API_KEY='your-key'")
        return

    if not fred_key:
        print("\n⚠️  SENS_FRED_API_KEY not found!")
        print("FRED data is free but requires an API key.")
        print("Get one at: https://fred.stlouisfed.org/docs/api/api_key.html")

    # Initialize tracker
    tracker = ProgressTracker(
        total_symbols=total_symbols,
        total_indicators=len(ECONOMIC_INDICATORS) if fred_key else 0,
    )

    # Load data
    async with FinancialDataLoader() as loader:
        # Phase 1: Load company information (uses 1 API call per symbol)
        print("\n📈 Phase 1: Loading company information...")
        for i, symbol in enumerate(all_symbols):
            if i >= 12:  # Stop at 12 to save API calls for price data
                print(f"⚠️  Stopping at {i} symbols to preserve API calls")
                break

            print(f"  Loading {symbol}...")
            try:
                await loader.load_company_info(symbol)
                await asyncio.sleep(15)  # Rate limit: 5 calls per minute
                tracker.increment_symbols()
            except Exception as e:
                print(f"  ❌ Error loading {symbol}: {str(e)}")
                if "rate limit" in str(e).lower():
                    print("  ⏸️  Rate limit hit. Stopping company info loading.")
                    break

        # Phase 2: Load price data for most important symbols only
        print("\n📊 Phase 2: Loading price data (1 year history)...")
        critical_symbols = ["SPY", "AAPL", "MSFT", "GOOGL", "AMZN", "VIX"]

        for symbol in critical_symbols:
            if tracker.api_calls >= 20:  # Leave some buffer
                print("⚠️  Approaching API limit. Stopping price data loading.")
                break

            print(f"  Loading prices for {symbol}...")
            try:
                prices = await loader.load_stock_prices(
                    symbol=symbol,
                    days=365,  # 1 year of data
                    function="TIME_SERIES_DAILY",
                )
                print(f"    ✅ Loaded {len(prices)} days of price data")
                await asyncio.sleep(15)  # Rate limit
                tracker.api_calls += 1
            except Exception as e:
                print(f"  ❌ Error loading prices for {symbol}: {str(e)}")
                if "rate limit" in str(e).lower():
                    print("  ⏸️  Rate limit hit. Moving to FRED data...")
                    break

        # Phase 3: Load ALL economic indicators (FREE!)
        if fred_key:
            print("\n📊 Phase 3: Loading economic indicators (FREE via FRED)...")
            for indicator in ECONOMIC_INDICATORS:
                print(f"  Loading {indicator}...")
                try:
                    data = await loader.load_economic_indicator(
                        indicator_code=indicator, days=730  # 2 years of data
                    )
                    print(f"    ✅ Loaded {len(data)} data points")
                    tracker.increment_indicators()
                    await asyncio.sleep(1)  # Be nice to FRED API
                except Exception as e:
                    print(f"  ❌ Error loading {indicator}: {str(e)}")

        # Summary
        await tracker.display_summary()

        print("\n💡 COST-SAVING TIPS:")
        print("1. Run this script once per day (respects 25 API call limit)")
        print("2. Use 'insert_sample_data.sql' for additional test data")
        print("3. Focus queries on loaded symbols: SPY, AAPL, MSFT, GOOGL, AMZN")
        print("4. Economic indicators are updated regularly via FRED (free)")

        print("\n📝 NEXT STEPS:")
        print("1. Wait 24 hours before running again (API limit resets)")
        print("2. Or upgrade to Alpha Vantage premium for more data")
        print("3. Use the web UI to query the loaded data")

        # Save loading status
        status = {
            "loaded_at": datetime.now().isoformat(),
            "symbols_loaded": critical_symbols[: tracker.api_calls // 2],
            "indicators_loaded": len(ECONOMIC_INDICATORS) if fred_key else 0,
            "api_calls_used": tracker.api_calls,
            "daily_limit": 25,
        }

        with open("loading_status.json", "w") as f:
            json.dump(status, f, indent=2)

        print("\n✅ Loading status saved to loading_status.json")


if __name__ == "__main__":
    asyncio.run(cost_effective_load())
