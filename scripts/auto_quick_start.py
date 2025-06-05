#!/usr/bin/env python3
"""
Automated Quick Start Data Loader (no user prompts)
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from quick_start_loader import QUICK_START_SYMBOLS, ESSENTIAL_INDICATORS
from sens.datasource.financial import FinancialDataLoader
from strategic_loader import ProgressTracker


async def auto_quick_start():
    """Run quick start loading without prompts."""
    
    start_time = datetime.now()
    
    print("🚀 AUTOMATED QUICK START DATA LOADING")
    print("="*60)
    print(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("Target: Load ~30 essential symbols + 8 economic indicators")
    print("="*60)
    
    # Flatten symbols
    all_symbols = []
    for category, symbols in QUICK_START_SYMBOLS.items():
        all_symbols.extend(symbols)
    
    print(f"\nTotal symbols to load: {len(all_symbols)}")
    print(f"Economic indicators: {len(ESSENTIAL_INDICATORS)}")
    print("\n🔄 Starting automated loading process...")
    
    tracker = ProgressTracker()
    
    async with FinancialDataLoader() as loader:
        # First, complete existing securities without prices
        print("\n" + "="*60)
        print("STEP 0: Complete Securities Without Prices")
        print("="*60)
        
        missing_prices = ["CRM", "DIS", "HD", "JNJ", "NFLX", "PG", "V"]
        print(f"Loading {len(missing_prices)} securities that are missing prices...")
        
        try:
            response = await loader.load_daily_prices_batch(
                missing_prices, 
                use_csv=True,
                max_concurrent=1
            )
            
            if response.success:
                print(f"✓ Loaded {response.records_loaded} price records for existing securities")
                tracker.add_symbols(response.symbols_processed)
            else:
                print(f"✗ Failed to load some existing securities: {response.message}")
                
        except Exception as e:
            print(f"✗ Error loading existing securities: {str(e)}")
        
        # Wait before next batch
        print("⏸️  Waiting 60s before proceeding...")
        await asyncio.sleep(60)
        
        # Load new securities info
        print("\n" + "="*60)
        print("STEP 1: Loading New Company Information")
        print("="*60)
        
        loaded_securities = 0
        failed_securities = []
        
        for category, symbols in QUICK_START_SYMBOLS.items():
            print(f"\n📊 {category} ({len(symbols)} symbols)")
            
            for symbol in symbols:
                try:
                    print(f"   {symbol}...", end='', flush=True)
                    count = await loader.load_securities_info([symbol])
                    if count > 0:
                        print(" ✓ (new)")
                        loaded_securities += 1
                    else:
                        print(" ✓ (exists)")
                    
                    # Rate limiting
                    await asyncio.sleep(12)
                    
                except Exception as e:
                    print(f" ✗ Error: {str(e)}")
                    failed_securities.append(symbol)
        
        print(f"\n✅ Loaded {loaded_securities} new securities")
        if failed_securities:
            print(f"❌ Failed securities: {', '.join(failed_securities)}")
        
        # Load price data
        print("\n" + "="*60)
        print("STEP 2: Loading Price Data")
        print("="*60)
        
        batch_size = 5
        total_records = 0
        successful_symbols = []
        
        for category, symbols in QUICK_START_SYMBOLS.items():
            print(f"\n📊 {category}")
            
            for i in range(0, len(symbols), batch_size):
                batch = symbols[i:i+batch_size]
                print(f"   Batch {i//batch_size + 1}: {', '.join(batch)}")
                
                try:
                    response = await loader.load_daily_prices_batch(
                        batch, 
                        use_csv=True,
                        max_concurrent=1
                    )
                    
                    if response.success:
                        print(f"   ✓ Loaded {response.records_loaded} records")
                        total_records += response.records_loaded
                        successful_symbols.extend(response.symbols_processed)
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
        print(f"✅ Symbols with prices: {len(successful_symbols)}")
        
        # Load economic indicators
        print("\n" + "="*60)
        print("STEP 3: Loading Economic Indicators")
        print("="*60)
        
        try:
            from datetime import timedelta
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
        
        # Final status
        print("\n" + "="*60)
        print("LOADING SUMMARY")
        print("="*60)
        
        status = await loader.get_data_status()
        print(f"Securities in database: {status['securities']}")
        print(f"Total price records: {status['daily_prices']['total_records']:,}")
        print(f"Symbols with prices: {status['daily_prices']['symbols_with_data']}")
        print(f"Economic indicators: {status['economic_indicators']['unique_indicators']}")
        
        elapsed = (datetime.now() - start_time).total_seconds() / 60
        print(f"\n⏱️  Total time: {elapsed:.1f} minutes")
        
        # Save progress
        summary = tracker.get_summary()
        print(f"\n📊 Progress tracked:")
        print(f"   Symbols loaded: {summary['symbols_loaded']}")
        print(f"   Indicators loaded: {summary['indicators_loaded']}")


if __name__ == "__main__":
    try:
        print("Starting automated quick start data loading...")
        print("This will take 4-6 hours due to API rate limits.")
        print("You can safely interrupt with Ctrl+C if needed.\n")
        
        asyncio.run(auto_quick_start())
        
        print("\n✅ Quick start loading completed!")
        print("\nNext steps:")
        print("1. Run gap analysis: poetry run python scripts/analyze_data_gaps.py")
        print("2. Continue with strategic loading: poetry run python scripts/strategic_loader.py run")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Loading interrupted by user")
        print("Progress has been saved. You can resume later.")
    except Exception as e:
        print(f"\n\n❌ Error: {str(e)}")
        sys.exit(1)