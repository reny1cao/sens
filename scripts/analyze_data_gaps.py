#!/usr/bin/env python3
"""
Analyze data gaps and recommend loading strategy.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from psycopg2.extras import DictCursor
from sens.settings import get_settings
from collections import defaultdict


def analyze_gaps():
    """Analyze current data and identify gaps."""
    
    conn = psycopg2.connect(get_settings().database_url)
    
    print("="*70)
    print("SENS DATA GAP ANALYSIS")
    print("="*70)
    
    with conn.cursor(cursor_factory=DictCursor) as cur:
        # 1. Securities Analysis
        print("\n📊 SECURITIES ANALYSIS")
        print("-"*40)
        
        # Get securities with and without price data
        cur.execute("""
            SELECT 
                s.symbol,
                s.company_name,
                s.sector,
                CASE WHEN dp.symbol IS NOT NULL THEN 'Yes' ELSE 'No' END as has_prices,
                COUNT(dp.trade_date) as price_records
            FROM securities s
            LEFT JOIN daily_prices dp ON s.symbol = dp.symbol
            GROUP BY s.symbol, s.company_name, s.sector, dp.symbol
            ORDER BY has_prices DESC, s.symbol
        """)
        
        securities = cur.fetchall()
        with_prices = [s for s in securities if s['has_prices'] == 'Yes']
        without_prices = [s for s in securities if s['has_prices'] == 'No']
        
        print(f"Total securities: {len(securities)}")
        print(f"✅ With price data: {len(with_prices)}")
        print(f"❌ Without price data: {len(without_prices)}")
        
        if without_prices:
            print("\nSecurities missing price data:")
            for sec in without_prices:
                print(f"  - {sec['symbol']:6} {sec['company_name']}")
        
        # 2. Sector Coverage
        print("\n📊 SECTOR COVERAGE ANALYSIS")
        print("-"*40)
        
        cur.execute("""
            SELECT 
                COALESCE(s.sector, 'Unknown') as sector,
                COUNT(DISTINCT s.symbol) as total_symbols,
                COUNT(DISTINCT dp.symbol) as symbols_with_prices
            FROM securities s
            LEFT JOIN daily_prices dp ON s.symbol = dp.symbol
            GROUP BY s.sector
            ORDER BY COUNT(DISTINCT s.symbol) DESC
        """)
        
        sectors = cur.fetchall()
        print("Sector               Total  With Prices  Coverage")
        print("-"*50)
        for sector in sectors:
            coverage = (sector['symbols_with_prices'] / sector['total_symbols'] * 100) if sector['total_symbols'] > 0 else 0
            print(f"{sector['sector']:20} {sector['total_symbols']:5}  {sector['symbols_with_prices']:11}  {coverage:6.1f}%")
        
        # 3. Critical Missing Symbols
        print("\n📊 CRITICAL MISSING SYMBOLS")
        print("-"*40)
        
        critical_symbols = {
            "Market Indices": ["SPY", "QQQ", "DIA", "IWM", "VTI"],
            "Sector ETFs": ["XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLB"],
            "Volatility": ["VIX", "VXX", "UVXY"],
            "Bonds": ["TLT", "AGG", "HYG", "LQD"],
            "Commodities": ["GLD", "SLV", "USO", "UNG"],
        }
        
        # Check which critical symbols are missing
        cur.execute("SELECT symbol FROM securities")
        existing_symbols = set(row['symbol'] for row in cur.fetchall())
        
        missing_critical = defaultdict(list)
        for category, symbols in critical_symbols.items():
            for symbol in symbols:
                if symbol not in existing_symbols:
                    missing_critical[category].append(symbol)
        
        if missing_critical:
            print("Missing critical symbols for analysis:")
            for category, symbols in missing_critical.items():
                if symbols:
                    print(f"\n{category}:")
                    print(f"  Missing: {', '.join(symbols)}")
        else:
            print("✅ All critical symbols are loaded")
        
        # 4. Economic Indicators
        print("\n📊 ECONOMIC INDICATORS ANALYSIS")
        print("-"*40)
        
        cur.execute("""
            SELECT 
                indicator_code,
                COUNT(*) as data_points,
                MIN(date) as first_date,
                MAX(date) as last_date,
                MAX(date) - MIN(date) as date_range_days
            FROM economic_indicators
            GROUP BY indicator_code
            ORDER BY indicator_code
        """)
        
        indicators = cur.fetchall()
        
        essential_indicators = {
            "VIXCLS": "Volatility Index",
            "DGS10": "10-Year Treasury Rate",
            "DGS2": "2-Year Treasury Rate",
            "DFF": "Federal Funds Rate",
            "UNRATE": "Unemployment Rate",
            "GDP": "Gross Domestic Product",
            "CPIAUCSL": "Consumer Price Index",
            "DEXUSEU": "USD/EUR Exchange Rate",
            "INDPRO": "Industrial Production",
            "UMCSENT": "Consumer Sentiment",
        }
        
        loaded_indicators = {ind['indicator_code'] for ind in indicators}
        missing_indicators = set(essential_indicators.keys()) - loaded_indicators
        
        print(f"Loaded indicators: {len(indicators)}")
        print("\nCurrent indicators:")
        for ind in indicators:
            desc = essential_indicators.get(ind['indicator_code'], "")
            print(f"  {ind['indicator_code']:10} {ind['data_points']:4} points  {ind['first_date']} to {ind['last_date']}  {desc}")
        
        if missing_indicators:
            print("\n❌ Missing essential indicators:")
            for code in missing_indicators:
                print(f"  {code:10} - {essential_indicators[code]}")
        
        # 5. Data Quality Metrics
        print("\n📊 DATA QUALITY METRICS")
        print("-"*40)
        
        cur.execute("""
            SELECT 
                COUNT(DISTINCT symbol) as unique_symbols,
                COUNT(*) as total_price_records,
                MIN(trade_date) as earliest_date,
                MAX(trade_date) as latest_date,
                CURRENT_DATE - MAX(trade_date) as days_stale
            FROM daily_prices
        """)
        
        quality = cur.fetchone()
        print(f"Symbols with prices: {quality['unique_symbols']}")
        print(f"Total price records: {quality['total_price_records']:,}")
        print(f"Date range: {quality['earliest_date']} to {quality['latest_date']}")
        print(f"Data freshness: {quality['days_stale']} days old")
        
        # 6. Recommendations
        print("\n💡 RECOMMENDATIONS")
        print("="*70)
        
        if len(with_prices) < 30:
            print("⚠️  CRITICAL: Less than 30 symbols with price data")
            print("   Minimum recommended: 50-100 symbols for meaningful analysis")
            print("   Action: Run quick_start_loader.py for immediate coverage")
        
        if missing_critical:
            print("\n⚠️  Missing critical market indices and ETFs")
            print("   Action: Load Phase 1B and 1C from strategic plan")
        
        if len(loaded_indicators) < 10:
            print("\n⚠️  Limited economic indicators")
            print("   Action: Load Phase 1D economic indicators")
        
        sector_coverage = len([s for s in sectors if s['symbols_with_prices'] > 0])
        if sector_coverage < 8:
            print(f"\n⚠️  Only {sector_coverage} sectors have price data")
            print("   Action: Load sector leaders (Phase 2)")
        
        if quality['days_stale'] > 3:
            print("\n⚠️  Data is stale")
            print("   Action: Run daily update script")
        
        print("\n📋 LOADING PRIORITY:")
        print("1. Quick Start: ~35 essential symbols (4-6 hours)")
        print("   python scripts/quick_start_loader.py")
        print("\n2. Strategic Phase 1: Market coverage (1-2 days)")
        print("   python scripts/strategic_loader.py run --start 1A --end 1D")
        print("\n3. Full Coverage: All phases (5-7 days)")
        print("   python scripts/strategic_loader.py run")
    
    conn.close()


if __name__ == "__main__":
    analyze_gaps()