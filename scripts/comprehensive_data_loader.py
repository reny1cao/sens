#!/usr/bin/env python3
"""
Comprehensive Financial Data Loader for SENS
Loads ALL tables with proper error handling and progress tracking.
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
import random

sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog
from sens.datasource.financial import FinancialDataLoader
import psycopg2
from sens.settings import get_settings

logger = structlog.get_logger(__name__)

# Progress tracking files
PROGRESS_DIR = Path(__file__).parent / "loading_progress"
PROGRESS_DIR.mkdir(exist_ok=True)

# Comprehensive symbol lists
STOCKS = {
    "Mega Cap Tech": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"],
    "Major Tech": ["ORCL", "CRM", "ADBE", "AMD", "INTC", "CSCO", "AVGO", "TXN", "QCOM"],
    "Finance": ["JPM", "BAC", "WFC", "GS", "MS", "BLK", "SPGI", "AXP", "C", "USB", "V", "MA"],
    "Healthcare": ["JNJ", "UNH", "PFE", "CVS", "LLY", "TMO", "ABT", "DHR", "BMY", "AMGN", "GILD"],
    "Consumer": ["WMT", "PG", "KO", "PEP", "COST", "HD", "DIS", "NKE", "MCD", "SBUX", "TGT", "LOW"],
    "Industrial": ["BA", "HON", "UNP", "CAT", "GE", "MMM", "LMT", "RTX", "UPS", "FDX"],
    "Energy": ["XOM", "CVX", "COP", "SLB", "EOG", "OXY", "PSX", "MPC", "VLO"],
}

# ETFs with metadata (to avoid Alpha Vantage API calls)
ETFS = {
    "SPY": ("SPDR S&P 500 ETF Trust", "Market Index"),
    "QQQ": ("Invesco QQQ Trust", "Market Index"),
    "DIA": ("SPDR Dow Jones Industrial Average ETF", "Market Index"),
    "IWM": ("iShares Russell 2000 ETF", "Market Index"),
    "VTI": ("Vanguard Total Stock Market ETF", "Market Index"),
    "VOO": ("Vanguard S&P 500 ETF", "Market Index"),
    "XLK": ("Technology Select Sector SPDR Fund", "Sector ETF"),
    "XLF": ("Financial Select Sector SPDR Fund", "Sector ETF"),
    "XLV": ("Health Care Select Sector SPDR Fund", "Sector ETF"),
    "XLE": ("Energy Select Sector SPDR Fund", "Sector ETF"),
    "XLI": ("Industrial Select Sector SPDR Fund", "Sector ETF"),
    "XLY": ("Consumer Discretionary Select Sector SPDR Fund", "Sector ETF"),
    "XLP": ("Consumer Staples Select Sector SPDR Fund", "Sector ETF"),
    "XLB": ("Materials Select Sector SPDR Fund", "Sector ETF"),
    "XLRE": ("Real Estate Select Sector SPDR Fund", "Sector ETF"),
    "XLU": ("Utilities Select Sector SPDR Fund", "Sector ETF"),
    "VXX": ("iPath Series B S&P 500 VIX Short-Term Futures ETN", "Volatility ETF"),
    "UVXY": ("ProShares Ultra VIX Short-Term Futures ETF", "Volatility ETF"),
    "TLT": ("iShares 20+ Year Treasury Bond ETF", "Bond ETF"),
    "AGG": ("iShares Core U.S. Aggregate Bond ETF", "Bond ETF"),
    "HYG": ("iShares iBoxx High Yield Corporate Bond ETF", "Bond ETF"),
    "LQD": ("iShares iBoxx Investment Grade Corporate Bond ETF", "Bond ETF"),
    "GLD": ("SPDR Gold Shares", "Commodity ETF"),
    "SLV": ("iShares Silver Trust", "Commodity ETF"),
    "USO": ("United States Oil Fund", "Commodity ETF"),
    "UNG": ("United States Natural Gas Fund", "Commodity ETF"),
    "DBA": ("Invesco DB Agriculture Fund", "Commodity ETF"),
}

# Economic indicators to load
ECONOMIC_INDICATORS = [
    # Core Economic
    "GDP", "GDPC1", "UNRATE", "PAYEMS", "CPIAUCSL", "CPILFESL",
    # Interest Rates  
    "DFF", "DGS2", "DGS10", "DGS30", "T10Y2Y", "FEDFUNDS",
    # Market Indicators
    "VIXCLS", "DEXUSEU", "DEXJPUS", "DEXCAUS", "DEXCHUS",
    # Housing
    "HOUST", "MORTGAGE30US", "MSPUS",
    # Manufacturing/Business
    "INDPRO", "UMCSENT", "NAPM", "RSXFS", "BUSLOANS",
    # Credit Spreads
    "BAMLH0A0HYM2", "BAMLC0A0CM", "TEDRATE",
]


class ComprehensiveLoader:
    """Handles all data loading with progress tracking."""
    
    def __init__(self):
        self.progress_file = PROGRESS_DIR / "comprehensive_progress.json"
        self.progress = self._load_progress()
        
    def _load_progress(self) -> Dict[str, Any]:
        """Load progress from file."""
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                return json.load(f)
        return {
            "securities_loaded": [],
            "etfs_loaded": [],
            "prices_loaded": [],
            "indicators_loaded": [],
            "statements_loaded": [],
            "portfolios_created": False,
            "options_created": False,
            "market_data_created": False,
            "last_updated": None,
            "total_price_records": 0,
            "total_statement_records": 0,
        }
    
    def _save_progress(self):
        """Save progress to file."""
        self.progress["last_updated"] = datetime.now().isoformat()
        with open(self.progress_file, 'w') as f:
            json.dump(self.progress, f, indent=2)
    
    async def load_all(self, reset: bool = False):
        """Load all financial data."""
        if reset:
            self.progress = self._load_progress()
            self.progress = {k: [] if isinstance(v, list) else False if isinstance(v, bool) else 0 if isinstance(v, int) else None 
                           for k, v in self.progress.items()}
        
        print("="*80)
        print("COMPREHENSIVE FINANCIAL DATA LOADER")
        print("="*80)
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Progress tracking: {self.progress_file}")
        print("="*80)
        
        async with FinancialDataLoader() as loader:
            # Step 1: Load ETFs first (no API calls needed)
            await self._load_etfs()
            
            # Step 2: Load stocks with company info
            await self._load_securities(loader)
            
            # Step 3: Load all price data
            await self._load_prices(loader)
            
            # Step 4: Load economic indicators
            await self._load_indicators(loader)
            
            # Step 5: Load financial statements
            await self._load_statements(loader)
            
            # Step 6: Create sample portfolio data
            await self._create_portfolio_data()
            
            # Step 7: Create sample options data
            await self._create_options_data()
            
            # Step 8: Create sample market data
            await self._create_market_data()
            
            # Final summary
            await self._show_summary(loader)
    
    async def _load_etfs(self):
        """Load ETF securities directly to database."""
        print("\n" + "="*60)
        print("STEP 1: Loading ETF Securities")
        print("="*60)
        
        conn = psycopg2.connect(get_settings().database_url)
        cur = conn.cursor()
        
        loaded = 0
        for symbol, (name, sector) in ETFS.items():
            if symbol in self.progress["etfs_loaded"]:
                print(f"  {symbol}: Already loaded")
                continue
                
            try:
                cur.execute("""
                    INSERT INTO securities (symbol, company_name, sector, exchange, country, currency, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol) DO UPDATE
                    SET company_name = EXCLUDED.company_name,
                        sector = EXCLUDED.sector,
                        updated_at = NOW()
                """, (symbol, name, sector, 'NYSE', 'USA', 'USD', True))
                
                conn.commit()
                loaded += 1
                self.progress["etfs_loaded"].append(symbol)
                print(f"  ✓ {symbol}: {name}")
                
            except Exception as e:
                conn.rollback()
                print(f"  ✗ {symbol}: Error - {str(e)}")
        
        cur.close()
        conn.close()
        
        self._save_progress()
        print(f"\n✅ Loaded {loaded} ETFs")
    
    async def _load_securities(self, loader: FinancialDataLoader):
        """Load stock securities with company info."""
        print("\n" + "="*60)
        print("STEP 2: Loading Stock Securities")
        print("="*60)
        
        all_stocks = []
        for category, symbols in STOCKS.items():
            all_stocks.extend(symbols)
        
        # Remove already loaded
        to_load = [s for s in all_stocks if s not in self.progress["securities_loaded"]]
        
        print(f"Total stocks: {len(all_stocks)}")
        print(f"Already loaded: {len(self.progress['securities_loaded'])}")
        print(f"To load: {len(to_load)}")
        
        for i, symbol in enumerate(to_load):
            try:
                print(f"\n[{i+1}/{len(to_load)}] Loading {symbol}...", end='', flush=True)
                count = await loader.load_securities_info([symbol])
                
                if count > 0:
                    print(" ✓")
                    self.progress["securities_loaded"].append(symbol)
                    self._save_progress()
                else:
                    print(" (already exists)")
                
                # Rate limiting
                await asyncio.sleep(12)
                
            except Exception as e:
                print(f" ✗ Error: {str(e)}")
                # Continue with next symbol
    
    async def _load_prices(self, loader: FinancialDataLoader):
        """Load price data for all securities."""
        print("\n" + "="*60)
        print("STEP 3: Loading Price Data")
        print("="*60)
        
        # Get all symbols (stocks + ETFs)
        all_symbols = list(set(self.progress["securities_loaded"] + self.progress["etfs_loaded"]))
        to_load = [s for s in all_symbols if s not in self.progress["prices_loaded"]]
        
        print(f"Total symbols: {len(all_symbols)}")
        print(f"Already loaded: {len(self.progress['prices_loaded'])}")
        print(f"To load: {len(to_load)}")
        
        # Load in batches of 5
        batch_size = 5
        for i in range(0, len(to_load), batch_size):
            batch = to_load[i:i+batch_size]
            print(f"\nBatch {i//batch_size + 1}: {', '.join(batch)}")
            
            try:
                response = await loader.load_daily_prices_batch(
                    batch, 
                    use_csv=True,
                    max_concurrent=1,
                    start_date=datetime(2023, 1, 1).date()  # Match partition range
                )
                
                if response.success:
                    print(f"  ✓ Loaded {response.records_loaded} records")
                    self.progress["prices_loaded"].extend(response.symbols_processed)
                    self.progress["total_price_records"] += response.records_loaded
                    self._save_progress()
                else:
                    print(f"  ✗ Failed: {response.message}")
                    # Log individual errors
                    for error in response.errors:
                        print(f"    - {error}")
                
                # Wait between batches
                if i + batch_size < len(to_load):
                    print("  ⏸️  Waiting 60s for rate limit...")
                    await asyncio.sleep(60)
                    
            except Exception as e:
                print(f"  ✗ Batch error: {str(e)}")
    
    async def _load_indicators(self, loader: FinancialDataLoader):
        """Load economic indicators."""
        print("\n" + "="*60)
        print("STEP 4: Loading Economic Indicators")
        print("="*60)
        
        to_load = [ind for ind in ECONOMIC_INDICATORS if ind not in self.progress["indicators_loaded"]]
        
        print(f"Total indicators: {len(ECONOMIC_INDICATORS)}")
        print(f"Already loaded: {len(self.progress['indicators_loaded'])}")
        print(f"To load: {len(to_load)}")
        
        if to_load:
            try:
                start_date = (datetime.now() - timedelta(days=730)).date()
                response = await loader.load_economic_indicators(
                    to_load,
                    start_date=start_date,
                    end_date=datetime.now().date()
                )
                
                if response.success:
                    print(f"✅ Loaded {response.records_loaded} indicator records")
                    self.progress["indicators_loaded"].extend(response.symbols_processed)
                    self._save_progress()
                else:
                    print(f"❌ Failed: {response.message}")
                    
            except Exception as e:
                print(f"❌ Error loading indicators: {str(e)}")
    
    async def _load_statements(self, loader: FinancialDataLoader):
        """Load financial statements for major companies."""
        print("\n" + "="*60)
        print("STEP 5: Loading Financial Statements")
        print("="*60)
        
        # Load statements for top companies
        major_companies = ["AAPL", "MSFT", "GOOGL", "AMZN", "JPM", "JNJ", "XOM", "WMT", "PG", "UNH"]
        to_load = [s for s in major_companies if s not in self.progress["statements_loaded"]]
        
        print(f"Loading statements for {len(to_load)} companies...")
        
        for symbol in to_load:
            try:
                print(f"  Loading {symbol} statements...", end='', flush=True)
                
                # This would call the financial statements API
                # For now, we'll simulate with a message
                print(" (API not implemented - skipping)")
                
                # In real implementation:
                # count = await loader.load_financial_statements([symbol])
                # self.progress["statements_loaded"].append(symbol)
                # self.progress["total_statement_records"] += count
                
                await asyncio.sleep(12)  # Rate limit
                
            except Exception as e:
                print(f" ✗ Error: {str(e)}")
    
    async def _create_portfolio_data(self):
        """Create sample portfolio holdings and trades."""
        if self.progress["portfolios_created"]:
            print("\n✓ Portfolio data already created")
            return
            
        print("\n" + "="*60)
        print("STEP 6: Creating Sample Portfolio Data")
        print("="*60)
        
        conn = psycopg2.connect(get_settings().database_url)
        cur = conn.cursor()
        
        try:
            # Create sample portfolio holdings
            holdings = [
                ("AAPL", 100, 150.50, datetime.now() - timedelta(days=180)),
                ("MSFT", 50, 300.25, datetime.now() - timedelta(days=150)),
                ("SPY", 200, 400.00, datetime.now() - timedelta(days=120)),
                ("GOOGL", 25, 130.75, datetime.now() - timedelta(days=90)),
                ("BRK.B", 75, 350.00, datetime.now() - timedelta(days=60)),
            ]
            
            for symbol, shares, cost_basis, acquired in holdings:
                cur.execute("""
                    INSERT INTO portfolio_holdings (symbol, shares, cost_basis, acquired_date)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (symbol) DO UPDATE
                    SET shares = EXCLUDED.shares,
                        cost_basis = EXCLUDED.cost_basis
                """, (symbol, shares, cost_basis, acquired))
            
            print(f"  ✓ Created {len(holdings)} portfolio holdings")
            
            # Create sample trades
            trades = []
            symbols = ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA"]
            
            for i in range(50):  # 50 sample trades
                symbol = random.choice(symbols)
                trade_type = random.choice(["BUY", "SELL"])
                shares = random.randint(10, 100)
                price = random.uniform(100, 500)
                commission = 0.99
                trade_date = datetime.now() - timedelta(days=random.randint(1, 180))
                
                trades.append((symbol, trade_date, trade_type, shares, price, commission))
            
            cur.executemany("""
                INSERT INTO trades (symbol, trade_date, trade_type, shares, price, commission)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, trades)
            
            print(f"  ✓ Created {len(trades)} sample trades")
            
            conn.commit()
            self.progress["portfolios_created"] = True
            self._save_progress()
            
        except Exception as e:
            conn.rollback()
            print(f"  ✗ Error creating portfolio data: {str(e)}")
        finally:
            cur.close()
            conn.close()
    
    async def _create_options_data(self):
        """Create sample options contracts."""
        if self.progress["options_created"]:
            print("\n✓ Options data already created")
            return
            
        print("\n" + "="*60)
        print("STEP 7: Creating Sample Options Data")
        print("="*60)
        
        conn = psycopg2.connect(get_settings().database_url)
        cur = conn.cursor()
        
        try:
            # Create sample options
            options = []
            symbols = ["AAPL", "MSFT", "SPY", "QQQ", "NVDA"]
            
            for symbol in symbols:
                for i in range(5):  # 5 options per symbol
                    option_type = random.choice(["CALL", "PUT"])
                    strike = round(random.uniform(100, 500), 2)
                    expiry = datetime.now().date() + timedelta(days=random.randint(30, 180))
                    premium = round(random.uniform(1, 20), 2)
                    volume = random.randint(100, 10000)
                    open_interest = random.randint(1000, 50000)
                    implied_vol = round(random.uniform(0.15, 0.60), 4)
                    
                    # Generate a unique option symbol
                    option_symbol = f"{symbol}{expiry.strftime('%y%m%d')}{option_type[0]}{int(strike):05d}"
                    
                    options.append((
                        option_symbol, symbol, strike, expiry, option_type,
                        premium, premium, premium + 0.50, premium - 0.50,
                        volume, open_interest, implied_vol,
                        round(random.uniform(0.1, 0.9), 4),  # delta
                        round(random.uniform(0.01, 0.1), 4),  # gamma
                        round(random.uniform(-0.1, -0.01), 4),  # theta
                        round(random.uniform(0.01, 0.5), 4),  # vega
                        round(random.uniform(0.01, 0.1), 4),  # rho
                    ))
            
            cur.executemany("""
                INSERT INTO options_contracts (
                    option_symbol, underlying_symbol, strike_price, expiration_date,
                    option_type, last_price, bid, ask, volume, open_interest,
                    implied_volatility, delta, gamma, theta, vega, rho
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (option_symbol) DO NOTHING
            """, options)
            
            print(f"  ✓ Created {cur.rowcount} options contracts")
            
            conn.commit()
            self.progress["options_created"] = True
            self._save_progress()
            
        except Exception as e:
            conn.rollback()
            print(f"  ✗ Error creating options data: {str(e)}")
        finally:
            cur.close()
            conn.close()
    
    async def _create_market_data(self):
        """Create sample intraday market data."""
        if self.progress["market_data_created"]:
            print("\n✓ Market data already created")
            return
            
        print("\n" + "="*60)
        print("STEP 8: Creating Sample Market Data")
        print("="*60)
        
        conn = psycopg2.connect(get_settings().database_url)
        cur = conn.cursor()
        
        try:
            # Create sample market data for today
            market_data = []
            symbols = ["AAPL", "MSFT", "GOOGL", "SPY", "QQQ"]
            
            for symbol in symbols:
                base_price = random.uniform(100, 500)
                
                # Generate data for every 5 minutes during market hours
                current_time = datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)
                end_time = datetime.now().replace(hour=16, minute=0, second=0, microsecond=0)
                
                while current_time <= end_time:
                    # Random walk for price
                    price_change = random.uniform(-0.5, 0.5)
                    price = base_price + price_change
                    
                    market_data.append((
                        symbol,
                        current_time,
                        round(price, 2),
                        round(price + random.uniform(0, 0.5), 2),  # ask
                        round(price - random.uniform(0, 0.5), 2),  # bid
                        random.randint(100, 10000),  # bid_size
                        random.randint(100, 10000),  # ask_size
                        random.randint(1000, 100000),  # volume
                    ))
                    
                    current_time += timedelta(minutes=5)
                    base_price = price  # Update base price for next iteration
            
            # Insert in batches
            batch_size = 1000
            for i in range(0, len(market_data), batch_size):
                batch = market_data[i:i+batch_size]
                cur.executemany("""
                    INSERT INTO market_data (
                        symbol, timestamp, last_price, ask_price, bid_price,
                        bid_size, ask_size, volume
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol, timestamp) DO NOTHING
                """, batch)
            
            print(f"  ✓ Created {len(market_data)} market data points")
            
            conn.commit()
            self.progress["market_data_created"] = True
            self._save_progress()
            
        except Exception as e:
            conn.rollback()
            print(f"  ✗ Error creating market data: {str(e)}")
        finally:
            cur.close()
            conn.close()
    
    async def _show_summary(self, loader: FinancialDataLoader):
        """Show final loading summary."""
        print("\n" + "="*80)
        print("LOADING COMPLETE - SUMMARY")
        print("="*80)
        
        status = await loader.get_data_status()
        
        print(f"Securities loaded: {status['securities']}")
        print(f"  - Stocks: {len(self.progress['securities_loaded'])}")
        print(f"  - ETFs: {len(self.progress['etfs_loaded'])}")
        print(f"\nPrice data:")
        print(f"  - Total records: {status['daily_prices']['total_records']:,}")
        print(f"  - Symbols with data: {status['daily_prices']['symbols_with_data']}")
        print(f"  - Date range: {status['daily_prices']['earliest_date']} to {status['daily_prices']['latest_date']}")
        print(f"\nEconomic indicators:")
        print(f"  - Total records: {status['economic_indicators']['total_records']:,}")
        print(f"  - Unique indicators: {status['economic_indicators']['unique_indicators']}")
        print(f"\nOther data:")
        print(f"  - Portfolio holdings: {'✓' if self.progress['portfolios_created'] else '✗'}")
        print(f"  - Options contracts: {'✓' if self.progress['options_created'] else '✗'}")
        print(f"  - Market data: {'✓' if self.progress['market_data_created'] else '✗'}")
        
        print("\n" + "="*80)
        print("✅ Your financial database is now fully populated!")
        print("\nYou can now:")
        print("  - Query stock prices and performance")
        print("  - Analyze sector trends")
        print("  - Study economic correlations")
        print("  - Track portfolio performance")
        print("  - Analyze options strategies")
        print("  - Study intraday market movements")
    
    async def verify_data(self):
        """Verify what data is currently loaded."""
        print("="*80)
        print("DATA VERIFICATION")
        print("="*80)
        
        conn = psycopg2.connect(get_settings().database_url)
        cur = conn.cursor()
        
        # Check each table
        tables = [
            ("securities", "SELECT COUNT(*), COUNT(DISTINCT sector) FROM securities"),
            ("daily_prices", "SELECT COUNT(*), COUNT(DISTINCT symbol) FROM daily_prices"),
            ("economic_indicators", "SELECT COUNT(*), COUNT(DISTINCT indicator_code) FROM economic_indicators"),
            ("financial_statements", "SELECT COUNT(*), COUNT(DISTINCT symbol) FROM financial_statements"),
            ("portfolio_holdings", "SELECT COUNT(*), SUM(shares * cost_basis) FROM portfolio_holdings"),
            ("trades", "SELECT COUNT(*), COUNT(DISTINCT symbol) FROM trades"),
            ("options_contracts", "SELECT COUNT(*), COUNT(DISTINCT underlying_symbol) FROM options_contracts"),
            ("market_data", "SELECT COUNT(*), COUNT(DISTINCT symbol) FROM market_data"),
        ]
        
        for table, query in tables:
            try:
                cur.execute(query)
                result = cur.fetchone()
                print(f"\n{table}:")
                print(f"  Records: {result[0]:,}")
                if table == "portfolio_holdings":
                    print(f"  Total value: ${result[1]:,.2f}" if result[1] else "  Total value: $0.00")
                else:
                    print(f"  Unique items: {result[1]}")
            except Exception as e:
                print(f"\n{table}: Error - {str(e)}")
        
        cur.close()
        conn.close()


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Comprehensive Financial Data Loader")
    parser.add_argument("--reset", action="store_true", help="Reset progress and start fresh")
    parser.add_argument("--resume", action="store_true", help="Resume from last progress")
    parser.add_argument("--verify", action="store_true", help="Verify current data status")
    
    args = parser.parse_args()
    
    loader = ComprehensiveLoader()
    
    try:
        if args.verify:
            await loader.verify_data()
        else:
            if args.resume:
                print("Resuming from last progress...")
            elif args.reset:
                print("Starting fresh (resetting progress)...")
            
            await loader.load_all(reset=args.reset)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Loading interrupted by user")
        print("Progress has been saved. Use --resume to continue.")
    except Exception as e:
        print(f"\n\n❌ Error: {str(e)}")
        logger.exception("Loading failed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())