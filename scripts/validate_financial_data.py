#!/usr/bin/env python3
"""
Financial data quality validation script for SENS.

This script performs comprehensive checks on loaded financial data to ensure:
1. No duplicates
2. Data completeness
3. Reasonable values
4. Proper handling of corporate actions
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import DictCursor

sys.path.insert(0, str(Path(__file__).parent.parent))

from sens.settings import get_settings
import structlog

logger = structlog.get_logger(__name__)


def validate_financial_data():
    """Run comprehensive data quality checks."""
    
    settings = get_settings()
    conn = psycopg2.connect(settings.database_url)
    
    print("=" * 60)
    print("SENS Financial Data Quality Validation")
    print("=" * 60)
    print()
    
    all_checks_passed = True
    
    with conn.cursor(cursor_factory=DictCursor) as cur:
        # 1. Duplicate Check
        print("1. DUPLICATE RECORDS CHECK")
        cur.execute("""
            SELECT symbol, trade_date, COUNT(*) as count
            FROM daily_prices
            GROUP BY symbol, trade_date
            HAVING COUNT(*) > 1
        """)
        duplicates = cur.fetchall()
        
        if duplicates:
            print(f"   ❌ FAILED: Found {len(duplicates)} duplicate records")
            for dup in duplicates[:5]:
                print(f"      - {dup['symbol']} on {dup['trade_date']}: {dup['count']} records")
            all_checks_passed = False
        else:
            print("   ✅ PASSED: No duplicate records found")
        
        # 2. Primary Key Integrity
        print("\n2. PRIMARY KEY INTEGRITY CHECK")
        cur.execute("""
            SELECT COUNT(*) as total,
                   COUNT(DISTINCT (symbol, trade_date)) as unique_pairs
            FROM daily_prices
        """)
        pk_check = cur.fetchone()
        
        if pk_check['total'] != pk_check['unique_pairs']:
            print(f"   ❌ FAILED: Primary key violations detected")
            all_checks_passed = False
        else:
            print("   ✅ PASSED: All (symbol, trade_date) pairs are unique")
        
        # 3. Data Completeness
        print("\n3. DATA COMPLETENESS CHECK")
        cur.execute("""
            SELECT 
                COUNT(*) as total_records,
                SUM(CASE WHEN close_price IS NULL THEN 1 ELSE 0 END) as null_close,
                SUM(CASE WHEN open_price IS NULL THEN 1 ELSE 0 END) as null_open,
                SUM(CASE WHEN high_price IS NULL THEN 1 ELSE 0 END) as null_high,
                SUM(CASE WHEN low_price IS NULL THEN 1 ELSE 0 END) as null_low,
                SUM(CASE WHEN volume IS NULL THEN 1 ELSE 0 END) as null_volume
            FROM daily_prices
        """)
        completeness = cur.fetchone()
        
        if any([completeness['null_close'] > 0, completeness['null_open'] > 0,
                completeness['null_high'] > 0, completeness['null_low'] > 0]):
            print(f"   ❌ FAILED: Found NULL values in price data")
            print(f"      - NULL close prices: {completeness['null_close']}")
            print(f"      - NULL open prices: {completeness['null_open']}")
            all_checks_passed = False
        else:
            print("   ✅ PASSED: All price fields are populated")
        
        # 4. Price Consistency Check
        print("\n4. PRICE CONSISTENCY CHECK")
        cur.execute("""
            SELECT symbol, trade_date, open_price, high_price, low_price, close_price
            FROM daily_prices
            WHERE (high_price < low_price) 
               OR (high_price < open_price)
               OR (high_price < close_price)
               OR (low_price > open_price)
               OR (low_price > close_price)
            LIMIT 10
        """)
        inconsistent = cur.fetchall()
        
        if inconsistent:
            print(f"   ❌ FAILED: Found {len(inconsistent)} price inconsistencies")
            for inc in inconsistent[:3]:
                print(f"      - {inc['symbol']} on {inc['trade_date']}: H={inc['high_price']}, L={inc['low_price']}")
            all_checks_passed = False
        else:
            print("   ✅ PASSED: High/Low prices are consistent")
        
        # 5. Volume Validation
        print("\n5. VOLUME VALIDATION CHECK")
        cur.execute("""
            SELECT symbol, COUNT(*) as zero_vol_days
            FROM daily_prices
            WHERE volume = 0 OR volume IS NULL
            GROUP BY symbol
            HAVING COUNT(*) > 10
        """)
        zero_volumes = cur.fetchall()
        
        if zero_volumes:
            print("   ⚠️  WARNING: Some symbols have many zero-volume days")
            for zv in zero_volumes:
                print(f"      - {zv['symbol']}: {zv['zero_vol_days']} days")
        else:
            print("   ✅ PASSED: Volume data looks reasonable")
        
        # 6. Date Range Validation
        print("\n6. DATE RANGE VALIDATION")
        cur.execute("""
            SELECT symbol, 
                   MIN(trade_date) as first_date,
                   MAX(trade_date) as last_date,
                   COUNT(DISTINCT trade_date) as trading_days
            FROM daily_prices
            GROUP BY symbol
            ORDER BY symbol
        """)
        date_ranges = cur.fetchall()
        
        print("   Symbol  First Date   Last Date    Trading Days")
        for dr in date_ranges:
            # Check if data is reasonably recent
            days_old = (datetime.now().date() - dr['last_date']).days
            status = "✅" if days_old <= 5 else "⚠️"
            print(f"   {status} {dr['symbol']:6}  {dr['first_date']}  {dr['last_date']}  {dr['trading_days']:4}")
        
        # 7. Adjusted Close Validation
        print("\n7. ADJUSTED CLOSE VALIDATION")
        cur.execute("""
            SELECT symbol,
                   COUNT(*) as total_days,
                   SUM(CASE WHEN adj_close != close_price THEN 1 ELSE 0 END) as adjusted_days
            FROM daily_prices
            WHERE adj_close IS NOT NULL AND close_price IS NOT NULL
            GROUP BY symbol
            HAVING SUM(CASE WHEN adj_close != close_price THEN 1 ELSE 0 END) > 0
        """)
        adjustments = cur.fetchall()
        
        if adjustments:
            print("   Symbols with price adjustments (splits/dividends):")
            for adj in adjustments:
                pct = (adj['adjusted_days'] / adj['total_days'] * 100)
                print(f"      - {adj['symbol']}: {adj['adjusted_days']} days ({pct:.1f}%)")
        else:
            print("   ✅ No adjusted prices found (may indicate no splits/dividends)")
        
        # 8. Data Source Consistency
        print("\n8. DATA SOURCE CONSISTENCY")
        cur.execute("""
            SELECT data_source, COUNT(*) as records
            FROM daily_prices
            GROUP BY data_source
        """)
        sources = cur.fetchall()
        
        print("   Data sources:")
        for src in sources:
            print(f"      - {src['data_source']}: {src['records']:,} records")
        
        # 9. Foreign Key Integrity
        print("\n9. FOREIGN KEY INTEGRITY")
        cur.execute("""
            SELECT COUNT(DISTINCT dp.symbol) as orphaned_symbols
            FROM daily_prices dp
            LEFT JOIN securities s ON dp.symbol = s.symbol
            WHERE s.symbol IS NULL
        """)
        orphans = cur.fetchone()
        
        if orphans['orphaned_symbols'] > 0:
            print(f"   ❌ FAILED: {orphans['orphaned_symbols']} symbols in daily_prices not in securities table")
            all_checks_passed = False
        else:
            print("   ✅ PASSED: All price data linked to valid securities")
    
    conn.close()
    
    # Summary
    print("\n" + "=" * 60)
    if all_checks_passed:
        print("✅ ALL DATA QUALITY CHECKS PASSED")
        print("\nThe data loading process is working correctly with:")
        print("- Proper duplicate prevention (ON CONFLICT)")
        print("- Complete data loading")
        print("- Consistent price relationships")
        print("- Valid foreign key relationships")
    else:
        print("❌ SOME DATA QUALITY CHECKS FAILED")
        print("\nPlease review the failed checks above.")
    
    print("\nRecommendations:")
    print("1. Run daily updates to keep data fresh")
    print("2. Monitor for corporate actions (splits, dividends)")
    print("3. Consider loading financial statements for fundamental analysis")
    print("=" * 60)


if __name__ == "__main__":
    validate_financial_data()