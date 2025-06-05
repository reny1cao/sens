#!/usr/bin/env python3
"""
Minimal test data loading for SENS - loads just a few symbols to verify setup.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sens.datasource.financial import FinancialDataLoader

# Just 3 symbols for testing
TEST_SYMBOLS = ['AAPL', 'GOOGL', 'MSFT']
TEST_INDICATORS = ['GDP', 'UNRATE', 'FEDFUNDS']


async def load_test_data():
    """Load minimal test data."""
    print("Loading minimal test data...")
    print(f"Symbols: {', '.join(TEST_SYMBOLS)}")
    print(f"Indicators: {', '.join(TEST_INDICATORS)}")
    print("-" * 40)
    
    async with FinancialDataLoader() as loader:
        # Load company info
        print("Loading company information...")
        for symbol in TEST_SYMBOLS:
            try:
                print(f"  {symbol}...", end='', flush=True)
                await loader.load_securities_info([symbol])
                print(" ✓")
                await asyncio.sleep(12)  # Rate limit
            except Exception as e:
                print(f" ✗ {str(e)}")
        
        # Load prices
        print("\nLoading price data...")
        try:
            response = await loader.load_daily_prices_batch(TEST_SYMBOLS, use_csv=True)
            print(f"✓ Loaded {response.records_loaded} price records")
        except Exception as e:
            print(f"✗ Error: {str(e)}")
        
        # Load indicators
        print("\nLoading economic indicators...")
        try:
            from datetime import datetime, timedelta
            response = await loader.load_economic_indicators(
                TEST_INDICATORS,
                start_date=(datetime.now() - timedelta(days=365)).date(),
                end_date=datetime.now().date()
            )
            print(f"✓ Loaded {response.records_loaded} indicator records")
        except Exception as e:
            print(f"✗ Error: {str(e)}")
        
        # Show status
        print("\nData Status:")
        print("-" * 40)
        status = await loader.get_data_status()
        print(f"Securities: {status['securities']}")
        print(f"Price records: {status['daily_prices']['total_records']:,}")
        print(f"Economic indicators: {status['economic_indicators']['total_records']:,}")
    
    print("\nTest data loading complete!")


if __name__ == "__main__":
    asyncio.run(load_test_data())