#!/usr/bin/env python3
"""
Rate-limit aware financial data loading script for SENS.

This script loads financial data while respecting API rate limits:
- Alpha Vantage: 5 calls/minute (free tier)
- FRED: 120 calls/minute (free tier)

Usage:
    python load_financial_data_rate_limited.py
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog
from sens.datasource.financial import FinancialDataLoader

logger = structlog.get_logger(__name__)

# Essential symbols for business analysis
ESSENTIAL_SYMBOLS = [
    # Tech Giants (most requested)
    'AAPL', 'GOOGL', 'MSFT', 'AMZN', 'META', 'NVDA', 'TSLA',
    
    # Other Major Tech
    'NFLX', 'CRM', 'ORCL', 'ADBE', 'PYPL',
    
    # Financials
    'JPM', 'BAC', 'WFC', 'GS', 'MS', 'V', 'MA',
    
    # Healthcare
    'JNJ', 'UNH', 'PFE', 'ABBV', 'MRK',
    
    # Consumer
    'WMT', 'HD', 'PG', 'KO', 'PEP', 'DIS', 'MCD', 'NKE',
    
    # Energy & Industrials
    'XOM', 'CVX', 'BA', 'CAT', 'MMM',
    
    # Sector ETFs for benchmarking
    'SPY', 'QQQ', 'DIA', 'IWM', 'XLK', 'XLF', 'XLV', 'XLE', 'XLI', 'XLY'
]

# Key economic indicators
ECONOMIC_INDICATORS = [
    'GDP',      # Gross Domestic Product
    'UNRATE',   # Unemployment Rate
    'FEDFUNDS', # Federal Funds Rate
    'CPIAUCSL', # Consumer Price Index
    'PAYEMS',   # Nonfarm Payrolls
    'VIXCLS',   # VIX (Volatility Index)
    'DGS10',    # 10-Year Treasury Rate
    'DGS2',     # 2-Year Treasury Rate
    'DEXUSEU',  # USD/EUR Exchange Rate
    'INDPRO',   # Industrial Production Index
    'UMCSENT',  # Consumer Sentiment
    'HOUST',    # Housing Starts
]


async def load_with_rate_limit_management():
    """Load financial data with proper rate limit management."""
    
    print("=" * 60)
    print("SENS Financial Data Loading (Rate-Limited)")
    print("=" * 60)
    print(f"Symbols to load: {len(ESSENTIAL_SYMBOLS)}")
    print(f"Economic indicators: {len(ECONOMIC_INDICATORS)}")
    print()
    
    async with FinancialDataLoader() as loader:
        # Phase 1: Load securities information (1 call per symbol)
        print("Phase 1: Loading company information...")
        print("Rate limit: 5 calls/minute = 12 seconds between calls")
        print("-" * 40)
        
        loaded_securities = 0
        for i, symbol in enumerate(ESSENTIAL_SYMBOLS):
            try:
                print(f"[{i+1}/{len(ESSENTIAL_SYMBOLS)}] Loading {symbol}...", end='', flush=True)
                count = await loader.load_securities_info([symbol])
                if count > 0:
                    print(" ✓")
                    loaded_securities += 1
                else:
                    print(" ✗ (skipped)")
                
                # Rate limiting: 12 seconds between calls (5 calls/minute)
                if i < len(ESSENTIAL_SYMBOLS) - 1:
                    print(f"    Waiting 12s for rate limit...", end='', flush=True)
                    await asyncio.sleep(12)
                    print(" done")
                    
            except Exception as e:
                print(f" ✗ Error: {str(e)}")
                continue
        
        print(f"\nPhase 1 Complete: {loaded_securities}/{len(ESSENTIAL_SYMBOLS)} securities loaded")
        print()
        
        # Phase 2: Load daily prices using CSV mode (more efficient)
        print("Phase 2: Loading daily price data...")
        print("Using CSV mode for bulk loading (1 call per symbol)")
        print("-" * 40)
        
        # Split into smaller batches to avoid timeouts
        batch_size = 5
        total_price_records = 0
        
        for i in range(0, len(ESSENTIAL_SYMBOLS), batch_size):
            batch = ESSENTIAL_SYMBOLS[i:i+batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(ESSENTIAL_SYMBOLS) + batch_size - 1) // batch_size
            
            print(f"\nBatch {batch_num}/{total_batches}: {', '.join(batch)}")
            
            try:
                response = await loader.load_daily_prices_batch(
                    batch, 
                    use_csv=True,
                    max_concurrent=1  # Process one at a time to respect rate limits
                )
                
                if response.success:
                    print(f"✓ Loaded {response.records_loaded} records")
                    total_price_records += response.records_loaded
                else:
                    print(f"✗ Batch failed: {response.message}")
                    for error in response.errors:
                        print(f"  - {error}")
                
                # Wait between batches
                if i + batch_size < len(ESSENTIAL_SYMBOLS):
                    wait_time = 60  # Wait 1 minute between batches
                    print(f"Waiting {wait_time}s between batches for rate limit...")
                    await asyncio.sleep(wait_time)
                    
            except Exception as e:
                print(f"✗ Batch error: {str(e)}")
                continue
        
        print(f"\nPhase 2 Complete: {total_price_records} price records loaded")
        print()
        
        # Phase 3: Load economic indicators (FRED has higher rate limit)
        print("Phase 3: Loading economic indicators...")
        print("Rate limit: 120 calls/minute (0.5s between calls)")
        print("-" * 40)
        
        try:
            # FRED allows more calls, so we can load all at once
            response = await loader.load_economic_indicators(
                ECONOMIC_INDICATORS,
                start_date=datetime.now().date() - timedelta(days=730),  # 2 years
                end_date=datetime.now().date()
            )
            
            if response.success:
                print(f"✓ Loaded {response.records_loaded} economic indicator records")
            else:
                print(f"✗ Failed: {response.message}")
                for error in response.errors:
                    print(f"  - {error}")
                    
        except Exception as e:
            print(f"✗ Error loading economic indicators: {str(e)}")
        
        print()
        
        # Phase 4: Show data status
        print("Phase 4: Data Status")
        print("-" * 40)
        
        try:
            status = await loader.get_data_status()
            print(f"Securities in database: {status['securities']}")
            print(f"Price records: {status['daily_prices']['total_records']:,}")
            print(f"Symbols with prices: {status['daily_prices']['symbols_with_data']}")
            print(f"Economic indicators: {status['economic_indicators']['total_records']:,}")
            print(f"Unique indicators: {status['economic_indicators']['unique_indicators']}")
        except Exception as e:
            print(f"✗ Error getting status: {str(e)}")
    
    print()
    print("=" * 60)
    print("Data loading complete!")
    print()
    print("Next steps:")
    print("1. Run 'poetry run sens financial status --detailed' to see full status")
    print("2. Use 'poetry run sens financial update' for daily updates")
    print("3. Try queries like:")
    print("   - 'Show me Apple stock performance last month'")
    print("   - 'Compare tech giants market cap'")
    print("   - 'What is the current unemployment rate?'")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(load_with_rate_limit_management())
    except KeyboardInterrupt:
        print("\n\nLoading interrupted by user.")
    except Exception as e:
        print(f"\n\nError: {str(e)}")
        sys.exit(1)