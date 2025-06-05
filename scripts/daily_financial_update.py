#!/usr/bin/env python3
"""
Daily financial data update script for SENS.

This script is designed to be run daily (e.g., via cron) to update:
1. Latest price data for active symbols
2. New economic indicator values

Respects API rate limits and only updates what's needed.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog
from sens.datasource.financial import FinancialDataLoader

logger = structlog.get_logger(__name__)


async def daily_update():
    """Perform daily financial data update."""
    
    start_time = datetime.now()
    print(f"SENS Daily Financial Update - {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    async with FinancialDataLoader() as loader:
        # Get current data status
        print("Checking current data status...")
        status = await loader.get_data_status()
        
        print(f"Securities in database: {status['securities']}")
        print(f"Latest price data: {status['daily_prices']['latest_date']}")
        print(f"Latest economic data: {status['economic_indicators']['latest_date']}")
        print()
        
        # Update market data for active symbols
        print("Updating daily price data...")
        print("-" * 40)
        
        try:
            response = await loader.update_market_data_daily()
            
            if response.success:
                print(f"✓ Updated {response.records_loaded} price records")
                print(f"✓ Symbols updated: {len(response.symbols_processed)}")
            else:
                print(f"✗ Price update failed: {response.message}")
                for error in response.errors[:5]:  # Show first 5 errors
                    print(f"  - {error}")
                if len(response.errors) > 5:
                    print(f"  ... and {len(response.errors) - 5} more errors")
        except Exception as e:
            print(f"✗ Error updating prices: {str(e)}")
        
        print()
        
        # Update key economic indicators
        print("Updating economic indicators...")
        print("-" * 40)
        
        key_indicators = [
            'FEDFUNDS',  # Fed funds rate (updates daily)
            'DGS10',     # 10-year treasury (daily)
            'DGS2',      # 2-year treasury (daily)
            'VIXCLS',    # VIX volatility (daily)
            'DEXUSEU',   # USD/EUR exchange (daily)
        ]
        
        try:
            # Only get last 7 days of data
            start_date = (datetime.now() - timedelta(days=7)).date()
            end_date = datetime.now().date()
            
            response = await loader.load_economic_indicators(
                key_indicators,
                start_date=start_date,
                end_date=end_date
            )
            
            if response.success:
                print(f"✓ Updated {response.records_loaded} indicator records")
            else:
                print(f"✗ Indicator update failed: {response.message}")
                for error in response.errors:
                    print(f"  - {error}")
        except Exception as e:
            print(f"✗ Error updating indicators: {str(e)}")
        
        print()
        
        # Show updated status
        print("Updated Data Status:")
        print("-" * 40)
        
        try:
            new_status = await loader.get_data_status()
            print(f"Total price records: {new_status['daily_prices']['total_records']:,}")
            print(f"Latest price date: {new_status['daily_prices']['latest_date']}")
            print(f"Total indicator records: {new_status['economic_indicators']['total_records']:,}")
            print(f"Latest indicator date: {new_status['economic_indicators']['latest_date']}")
        except Exception as e:
            print(f"✗ Error getting status: {str(e)}")
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print()
    print("=" * 60)
    print(f"Daily update completed in {duration:.1f} seconds")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(daily_update())
    except KeyboardInterrupt:
        print("\n\nUpdate interrupted by user.")
    except Exception as e:
        logger.error("daily_update_failed", error=str(e))
        print(f"\n\nDaily update failed: {str(e)}")
        sys.exit(1)