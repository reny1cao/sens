#!/usr/bin/env python3
"""
Quick Start Data Loader for SENS
Loads essential data for immediate business analysis capability.
Target: 30-50 symbols in 4-6 hours
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sens.datasource.financial import FinancialDataLoader
from strategic_loader import ProgressTracker

# Essential symbols for immediate analysis
QUICK_START_SYMBOLS = {
    "Market Indices": ["SPY", "QQQ", "DIA", "IWM"],
    "Mega Cap Tech": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA"],
    "Sector Leaders": ["JPM", "XOM", "UNH", "WMT", "JNJ", "V"],
    "Sector ETFs": ["XLK", "XLF", "XLV", "XLE", "XLI", "XLY"],
    "Volatility": ["VXX", "UVXY"],
    "Bonds": ["TLT", "AGG", "HYG"],
    "Commodities": ["GLD", "SLV", "USO"]
}

ESSENTIAL_INDICATORS = [
    "VIXCLS",    # Volatility Index
    "DGS10",     # 10-Year Treasury
    "DGS2",      # 2-Year Treasury  
    "DFF",       # Federal Funds Rate
    "DEXUSEU",   # USD/EUR Exchange Rate
    "UNRATE",    # Unemployment Rate
    "CPIAUCSL",  # Consumer Price Index
    "GDP",       # Gross Domestic Product
]


async def quick_start_load():
    """Load essential data for immediate analysis."""
    
    print("🚀 SENS QUICK START DATA LOADER")
    print("="*60)
    print("Target: Load ~35 essential symbols + 8 economic indicators")
    print("Estimated time: 4-6 hours (with rate limits)")
    print("="*60)
    
    # Flatten symbols
    all_symbols = []
    for category, symbols in QUICK_START_SYMBOLS.items():
        all_symbols.extend(symbols)
    
    print(f"\nTotal symbols to load: {len(all_symbols)}")
    print(f"Economic indicators: {len(ESSENTIAL_INDICATORS)}")
    
    response = input("\nProceed with quick start loading? (y/n): ")
    if response.lower() != 'y':
        print("❌ Loading cancelled")
        return
    
    tracker = ProgressTracker()
    
    async with FinancialDataLoader() as loader:
        # Step 1: Load securities info
        print("\n" + "="*60)
        print("STEP 1: Loading Company Information")
        print("="*60)
        
        loaded_securities = 0
        for i, (category, symbols) in enumerate(QUICK_START_SYMBOLS.items()):
            print(f"\n📊 {category} ({len(symbols)} symbols)")
            
            for j, symbol in enumerate(symbols):
                try:
                    print(f"   [{j+1}/{len(symbols)}] {symbol}...", end='', flush=True)
                    count = await loader.load_securities_info([symbol])
                    if count > 0:
                        print(" ✓")
                        loaded_securities += 1
                    else:
                        print(" (already exists)")
                    
                    # Rate limiting
                    await asyncio.sleep(12)
                    
                except Exception as e:
                    print(f" ✗ Error: {str(e)}")
        
        print(f"\n✅ Loaded {loaded_securities} new securities")
        
        # Step 2: Load price data in batches
        print("\n" + "="*60)
        print("STEP 2: Loading Price Data")
        print("="*60)
        
        batch_size = 5
        total_records = 0
        
        for category, symbols in QUICK_START_SYMBOLS.items():
            print(f"\n📊 {category}")
            
            # Process in batches
            for i in range(0, len(symbols), batch_size):
                batch = symbols[i:i+batch_size]
                print(f"   Batch: {', '.join(batch)}")
                
                try:
                    response = await loader.load_daily_prices_batch(
                        batch, 
                        use_csv=True,
                        max_concurrent=1
                    )
                    
                    if response.success:
                        print(f"   ✓ Loaded {response.records_loaded} records")
                        total_records += response.records_loaded
                        tracker.add_symbols(response.symbols_processed)
                    else:
                        print(f"   ✗ Failed: {response.message}")
                    
                    # Wait between batches
                    if i + batch_size < len(symbols):
                        print("   ⏸️  Waiting 60s for rate limit...")
                        await asyncio.sleep(60)
                        
                except Exception as e:
                    print(f"   ✗ Batch error: {str(e)}")
        
        print(f"\n✅ Total price records loaded: {total_records:,}")
        
        # Step 3: Load economic indicators
        print("\n" + "="*60)
        print("STEP 3: Loading Economic Indicators")
        print("="*60)
        
        try:
            from datetime import datetime, timedelta
            start_date = (datetime.now() - timedelta(days=730)).date()
            
            response = await loader.load_economic_indicators(
                ESSENTIAL_INDICATORS,
                start_date=start_date,
                end_date=datetime.now().date()
            )
            
            if response.success:
                print(f"✅ Loaded {response.records_loaded} economic indicator records")
                tracker.add_indicators(response.symbols_processed)
            else:
                print(f"❌ Failed: {response.message}")
                
        except Exception as e:
            print(f"❌ Error loading indicators: {str(e)}")
        
        # Step 4: Show final status
        print("\n" + "="*60)
        print("QUICK START LOADING COMPLETE")
        print("="*60)
        
        status = await loader.get_data_status()
        print(f"Securities in database: {status['securities']}")
        print(f"Total price records: {status['daily_prices']['total_records']:,}")
        print(f"Symbols with prices: {status['daily_prices']['symbols_with_data']}")
        print(f"Economic indicators: {status['economic_indicators']['unique_indicators']}")
        
        print("\n✅ You now have enough data for:")
        print("   - Market trend analysis")
        print("   - Sector performance comparison")
        print("   - Risk analysis (with VIX)")
        print("   - Bond-equity correlation")
        print("   - Economic impact analysis")
        
        print("\n📝 Next steps:")
        print("   1. Run strategic loader for complete coverage:")
        print("      python scripts/strategic_loader.py run")
        print("   2. Set up daily updates:")
        print("      ./scripts/setup_daily_cron.sh")
        print("   3. Start querying:")
        print("      poetry run sens nl2sql -q \"Compare tech sector performance\"")


if __name__ == "__main__":
    try:
        asyncio.run(quick_start_load())
    except KeyboardInterrupt:
        print("\n\n❌ Loading interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {str(e)}")
        sys.exit(1)