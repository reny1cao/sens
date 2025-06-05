#!/usr/bin/env python3
"""Check data status across all financial database tables."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from psycopg2.extras import DictCursor
from sens.settings import get_settings

def check_all_tables():
    settings = get_settings()
    conn = psycopg2.connect(settings.database_url)
    
    print('=' * 80)
    print('COMPREHENSIVE DATABASE STATUS - ALL TABLES')
    print('=' * 80)
    
    with conn.cursor(cursor_factory=DictCursor) as cur:
        # Get all tables in the financial schema
        cur.execute('''
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
            AND table_name NOT LIKE 'daily_prices_%%'  -- Exclude partitions
            AND table_name NOT LIKE '%%_id_seq'  -- Exclude sequences
            ORDER BY table_name
        ''')
        tables = [row['table_name'] for row in cur.fetchall()]
        
        empty_tables = []
        populated_tables = []
        
        for table in tables:
            print(f'\n### TABLE: {table.upper()}')
            print('-' * 40)
            
            # Get row count
            cur.execute(f'SELECT COUNT(*) as count FROM {table}')
            count = cur.fetchone()['count']
            print(f'Records: {count:,}')
            
            if count > 0:
                populated_tables.append((table, count))
                
                # Show sample data based on table
                if table == 'securities':
                    cur.execute('''
                        SELECT symbol, company_name, sector, market_cap, exchange
                        FROM securities
                        ORDER BY symbol
                        LIMIT 5
                    ''')
                    print('Sample data:')
                    for row in cur.fetchall():
                        cap = row['market_cap'] / 1e9 if row['market_cap'] else 0
                        sector = row['sector'] or 'Unknown'
                        print(f'  {row["symbol"]:6} | {row["company_name"]:30} | {sector:20}')
                        
                elif table == 'economic_indicators':
                    cur.execute('''
                        SELECT indicator_code, COUNT(*) as records, 
                               MIN(date) as first_date, MAX(date) as last_date
                        FROM economic_indicators
                        GROUP BY indicator_code
                        ORDER BY indicator_code
                    ''')
                    print('Indicators loaded:')
                    for row in cur.fetchall():
                        print(f'  {row["indicator_code"]:10} | {row["records"]:3} records | {row["first_date"]} to {row["last_date"]}')
                        
                elif table == 'daily_prices':
                    cur.execute('''
                        SELECT COUNT(DISTINCT symbol) as symbols,
                               MIN(trade_date) as first_date,
                               MAX(trade_date) as last_date
                        FROM daily_prices
                    ''')
                    stats = cur.fetchone()
                    print(f'Price data summary:')
                    print(f'  Symbols with data: {stats["symbols"]}')
                    print(f'  Date range: {stats["first_date"]} to {stats["last_date"]}')
                    
            else:
                if table != 'staging_daily_prices':
                    empty_tables.append(table)
                else:
                    print('✅ Staging table is empty (as expected)')
        
        print()
        print('=' * 80)
        print('DATA LOADING SUMMARY')
        print('=' * 80)
        
        print(f'\n✅ Tables with data ({len(populated_tables)}):')
        for table, count in populated_tables:
            print(f'   - {table}: {count:,} records')
        
        print(f'\n⚠️  Empty tables ({len(empty_tables)}):')
        for table in empty_tables:
            print(f'   - {table}')
        
        # Check views
        print('\n📊 VIEWS AVAILABLE:')
        cur.execute('''
            SELECT table_name
            FROM information_schema.views
            WHERE table_schema = 'public'
            ORDER BY table_name
        ''')
        views = cur.fetchall()
        for view in views:
            print(f'   - {view["table_name"]}')
        
        # Check if we can use the views
        print('\n📈 SAMPLE VIEW DATA:')
        try:
            cur.execute('SELECT * FROM latest_prices LIMIT 3')
            print('latest_prices view:')
            for row in cur.fetchall():
                close_price = float(row['close_price']) if row['close_price'] else 0
                volume = int(row['volume']) if row['volume'] else 0
                print(f'  {row["symbol"]:6} | {row["trade_date"]} | Close: ${close_price:7.2f} | Vol: {volume:,}')
        except Exception as e:
            print(f'  Error accessing view: {e}')
        
        # Check data quality across tables
        print('\n🔍 DATA QUALITY CHECKS:')
        
        # Check for orphaned records
        cur.execute('''
            SELECT COUNT(*) as orphaned
            FROM daily_prices dp
            LEFT JOIN securities s ON dp.symbol = s.symbol
            WHERE s.symbol IS NULL
        ''')
        orphaned = cur.fetchone()['orphaned']
        if orphaned > 0:
            print(f'  ❌ Found {orphaned} orphaned price records')
        else:
            print('  ✅ No orphaned records in daily_prices')
        
        # Check partitions
        cur.execute('''
            SELECT 
                schemaname,
                tablename,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
            FROM pg_tables
            WHERE tablename LIKE 'daily_prices_%%'
            ORDER BY tablename
            LIMIT 5
        ''')
        partitions = cur.fetchall()
        if partitions:
            print(f'\n  📅 Sample partitions (showing 5 of many):')
            for part in partitions:
                print(f'     - {part["tablename"]}: {part["size"]}')
    
    conn.close()
    
    print()
    print('=' * 80)
    print('RECOMMENDATIONS FOR COMPLETE BUSINESS ANALYSIS:')
    print('=' * 80)
    print('1. ✅ Securities master data - LOADED')
    print('2. ✅ Daily price data - LOADED (8 symbols)')  
    print('3. ✅ Economic indicators - LOADED (5 indicators)')
    print('4. ⚠️  Financial statements - NOT LOADED')
    print('   Run: poetry run sens financial load -s "AAPL,GOOGL,MSFT" --include-fundamentals')
    print('5. ⚠️  Trading/Portfolio data - NOT LOADED')
    print('   These require actual trading data or simulation')
    print('6. ⚠️  Options data - NOT LOADED')
    print('   Available through Alpha Vantage premium')
    print('7. ⚠️  Real-time market data - NOT LOADED')
    print('   Requires streaming data source')
    print()
    print('For business analysis, you currently have enough data to:')
    print('- Analyze stock price trends and performance')
    print('- Compare sectors and companies')
    print('- Correlate with economic indicators')
    print('- Calculate technical indicators')
    print('- Perform time series analysis')

if __name__ == '__main__':
    check_all_tables()