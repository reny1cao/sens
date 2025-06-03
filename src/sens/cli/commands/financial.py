"""Financial data CLI commands."""

import asyncio
import click
from datetime import datetime, date, timedelta
from typing import List, Optional
import structlog

from sens.datasource.financial import FinancialDataLoader
from sens.datasource.financial.alpha_vantage import AlphaVantageClient
from sens.datasource.financial.fred import FREDClient
from sens.settings import get_settings

logger = structlog.get_logger(__name__)


@click.group()
def financial():
    """Financial data management commands."""
    pass


@financial.command()
@click.option('--symbols', '-s', help='Comma-separated list of symbols (e.g., AAPL,GOOGL,MSFT)')
@click.option('--file', '-f', type=click.Path(exists=True), help='File containing symbols (one per line)')
@click.option('--preset', '-p', type=click.Choice(['sp500_sample', 'tech_giants', 'dow_sample']), 
              help='Preset symbol list')
@click.option('--days', '-d', type=int, default=365, help='Number of days of historical data')
@click.option('--include-fundamentals', is_flag=True, help='Include financial statements')
@click.option('--csv-mode', is_flag=True, help='Use CSV mode for faster loading')
@click.option('--dry-run', is_flag=True, help='Show what would be loaded without loading')
def load(symbols: Optional[str], file: Optional[str], preset: Optional[str], 
         days: int, include_fundamentals: bool, csv_mode: bool, dry_run: bool):
    """Load financial data for specified symbols."""
    
    # Determine symbol list
    symbol_list = []
    
    if symbols:
        symbol_list = [s.strip().upper() for s in symbols.split(',')]
    elif file:
        with open(file, 'r') as f:
            symbol_list = [line.strip().upper() for line in f if line.strip()]
    elif preset:
        symbol_list = _get_preset_symbols(preset)
    else:
        click.echo("Error: Must specify --symbols, --file, or --preset")
        return
    
    if not symbol_list:
        click.echo("Error: No symbols specified")
        return
    
    if dry_run:
        click.echo(f"Would load data for {len(symbol_list)} symbols:")
        for symbol in symbol_list:
            click.echo(f"  - {symbol}")
        click.echo(f"Historical data: {days} days")
        click.echo(f"Include fundamentals: {include_fundamentals}")
        click.echo(f"CSV mode: {csv_mode}")
        return
    
    # Run the loading process
    asyncio.run(_load_financial_data(
        symbol_list, days, include_fundamentals, csv_mode
    ))


@financial.command()
@click.option('--indicators', '-i', help='Comma-separated list of FRED indicators (e.g., GDP,UNRATE,FEDFUNDS)')
@click.option('--preset', '-p', type=click.Choice(['key_economic', 'market_indicators', 'employment']),
              help='Preset indicator list')
@click.option('--start-date', type=click.DateTime(['%Y-%m-%d']), 
              help='Start date (YYYY-MM-DD). Default: 2 years ago')
@click.option('--end-date', type=click.DateTime(['%Y-%m-%d']), 
              help='End date (YYYY-MM-DD). Default: today')
@click.option('--dry-run', is_flag=True, help='Show what would be loaded without loading')
def load_economic(indicators: Optional[str], preset: Optional[str], 
                  start_date: Optional[datetime], end_date: Optional[datetime], 
                  dry_run: bool):
    """Load economic indicators from FRED."""
    
    # Determine indicator list
    indicator_list = []
    
    if indicators:
        indicator_list = [i.strip().upper() for i in indicators.split(',')]
    elif preset:
        indicator_list = _get_preset_indicators(preset)
    else:
        click.echo("Error: Must specify --indicators or --preset")
        return
    
    # Set default date range
    if not start_date:
        start_date = datetime.now() - timedelta(days=730)  # 2 years
    
    if not end_date:
        end_date = datetime.now()
    
    if dry_run:
        click.echo(f"Would load {len(indicator_list)} economic indicators:")
        for indicator in indicator_list:
            click.echo(f"  - {indicator}")
        click.echo(f"Date range: {start_date.date()} to {end_date.date()}")
        return
    
    # Run the loading process
    asyncio.run(_load_economic_data(
        indicator_list, start_date.date(), end_date.date()
    ))


@financial.command()
def update():
    """Update financial data for existing symbols (daily maintenance)."""
    click.echo("Updating financial data...")
    asyncio.run(_update_daily_data())


@financial.command()
@click.option('--detailed', is_flag=True, help='Show detailed statistics')
def status(detailed: bool):
    """Show financial data status and statistics."""
    asyncio.run(_show_data_status(detailed))


@financial.command()
@click.option('--create-schema', is_flag=True, help='Create database schema')
@click.option('--load-sample', is_flag=True, help='Load sample data')
@click.option('--api-keys', is_flag=True, help='Check API key configuration')
def setup(create_schema: bool, load_sample: bool, api_keys: bool):
    """Setup financial data infrastructure."""
    
    if api_keys:
        _check_api_keys()
        return
    
    if create_schema:
        _create_database_schema()
    
    if load_sample:
        asyncio.run(_load_sample_data())


@financial.command()
@click.argument('symbol')
@click.option('--days', '-d', type=int, default=30, help='Number of days to show')
def prices(symbol: str, days: int):
    """Show recent price data for a symbol."""
    asyncio.run(_show_symbol_prices(symbol.upper(), days))


@financial.command()
@click.option('--symbol', '-s', help='Filter by symbol')
@click.option('--limit', '-l', type=int, default=10, help='Number of records to show')
def indicators(symbol: Optional[str], limit: int):
    """Show economic indicators data."""
    asyncio.run(_show_indicators(symbol, limit))


# Helper functions

def _get_preset_symbols(preset: str) -> List[str]:
    """Get predefined symbol lists."""
    presets = {
        'sp500_sample': [
            'AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA', 'META', 'NVDA', 'BRK.B',
            'UNH', 'JNJ', 'XOM', 'JPM', 'V', 'PG', 'HD', 'CVX', 'MA', 'PFE',
            'ABBV', 'BAC', 'COST', 'DIS', 'KO', 'MRK', 'PEP', 'TMO', 'VZ',
            'ABT', 'ADBE', 'WMT'
        ],
        'tech_giants': [
            'AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA', 'META', 'NVDA', 'NFLX',
            'CRM', 'ORCL', 'ADBE', 'INTC', 'AMD', 'UBER', 'PYPL'
        ],
        'dow_sample': [
            'AAPL', 'MSFT', 'UNH', 'GS', 'HD', 'CAT', 'MCD', 'V', 'BA', 'AXP',
            'JPM', 'JNJ', 'WMT', 'PG', 'CVX', 'NKE', 'MRK', 'KO', 'DIS', 'MMM'
        ]
    }
    return presets.get(preset, [])


def _get_preset_indicators(preset: str) -> List[str]:
    """Get predefined economic indicator lists."""
    presets = {
        'key_economic': [
            'GDP', 'UNRATE', 'FEDFUNDS', 'CPIAUCSL', 'PAYEMS', 'INDPRO'
        ],
        'market_indicators': [
            'VIXCLS', 'DGS10', 'DGS2', 'FEDFUNDS', 'UMCSENT', 'NAPM'
        ],
        'employment': [
            'UNRATE', 'PAYEMS', 'CIVPART', 'EMRATIO', 'UNEMPLOY', 'CLF16OV'
        ]
    }
    return presets.get(preset, [])


async def _load_financial_data(symbols: List[str], days: int, 
                             include_fundamentals: bool, csv_mode: bool):
    """Load financial data for symbols."""
    click.echo(f"Loading financial data for {len(symbols)} symbols...")
    
    async with FinancialDataLoader() as loader:
        # Load securities information
        click.echo("Loading securities information...")
        securities_loaded = await loader.load_securities_info(symbols)
        click.echo(f"✓ Loaded info for {securities_loaded} securities")
        
        # Load daily prices
        click.echo("Loading daily price data...")
        price_response = await loader.load_daily_prices_batch(symbols, csv_mode)
        
        if price_response.success:
            click.echo(f"✓ Loaded {price_response.records_loaded} price records")
        else:
            click.echo(f"✗ Price loading failed: {price_response.message}")
            for error in price_response.errors:
                click.echo(f"  Error: {error}")
        
        # Load financial statements if requested
        if include_fundamentals:
            click.echo("Loading financial statements...")
            statements_response = await loader.load_financial_statements(symbols)
            
            if statements_response.success:
                click.echo(f"✓ Loaded {statements_response.records_loaded} statement records")
            else:
                click.echo(f"✗ Statements loading failed: {statements_response.message}")
                for error in statements_response.errors:
                    click.echo(f"  Error: {error}")
        
        click.echo(f"✓ Financial data loading completed in {price_response.execution_time_seconds:.1f}s")


async def _load_economic_data(indicators: List[str], start_date: date, end_date: date):
    """Load economic indicators data."""
    click.echo(f"Loading {len(indicators)} economic indicators...")
    
    async with FinancialDataLoader() as loader:
        response = await loader.load_economic_indicators(indicators, start_date, end_date)
        
        if response.success:
            click.echo(f"✓ Loaded {response.records_loaded} economic indicator records")
        else:
            click.echo(f"✗ Economic data loading failed: {response.message}")
            for error in response.errors:
                click.echo(f"  Error: {error}")
        
        click.echo(f"✓ Economic data loading completed in {response.execution_time_seconds:.1f}s")


async def _update_daily_data():
    """Update daily financial data."""
    async with FinancialDataLoader() as loader:
        response = await loader.update_market_data_daily()
        
        if response.success:
            click.echo(f"✓ Updated {response.records_loaded} records for {len(response.symbols_processed)} symbols")
        else:
            click.echo(f"✗ Daily update failed: {response.message}")
            for error in response.errors:
                click.echo(f"  Error: {error}")


async def _show_data_status(detailed: bool):
    """Show financial data status."""
    async with FinancialDataLoader() as loader:
        status = await loader.get_data_status()
        
        click.echo("Financial Data Status")
        click.echo("=" * 50)
        click.echo(f"Securities: {status['securities']}")
        click.echo(f"Daily Prices: {status['daily_prices']['total_records']:,} records")
        click.echo(f"  - Symbols with data: {status['daily_prices']['symbols_with_data']}")
        click.echo(f"  - Date range: {status['daily_prices']['earliest_date']} to {status['daily_prices']['latest_date']}")
        
        click.echo(f"Economic Indicators: {status['economic_indicators']['total_records']:,} records")
        click.echo(f"  - Unique indicators: {status['economic_indicators']['unique_indicators']}")
        click.echo(f"  - Date range: {status['economic_indicators']['earliest_date']} to {status['economic_indicators']['latest_date']}")
        
        click.echo(f"Financial Statements: {status['financial_statements']['total_records']:,} records")
        click.echo(f"  - Symbols with data: {status['financial_statements']['symbols_with_data']}")
        click.echo(f"  - Year range: {status['financial_statements']['earliest_year']} to {status['financial_statements']['latest_year']}")
        
        click.echo(f"Last updated: {status['last_updated']}")


def _check_api_keys():
    """Check API key configuration."""
    click.echo("API Key Configuration")
    click.echo("=" * 30)
    
    settings = get_settings()
    
    # Check Alpha Vantage
    alpha_key = getattr(settings.financial, 'alpha_vantage_api_key', None)
    if alpha_key:
        click.echo(f"✓ Alpha Vantage: {alpha_key[:8]}...")
    else:
        click.echo("✗ Alpha Vantage: Not configured")
        click.echo("  Get free key at: https://www.alphavantage.co/support/#api-key")
    
    # Check FRED
    fred_key = getattr(settings.financial, 'fred_api_key', None)
    if fred_key:
        click.echo(f"✓ FRED: {fred_key[:8]}...")
    else:
        click.echo("✗ FRED: Not configured")
        click.echo("  Get free key at: https://fred.stlouisfed.org/docs/api/api_key.html")


def _create_database_schema():
    """Create financial database schema."""
    import subprocess
    import os
    
    schema_file = os.path.join(
        os.path.dirname(__file__), 
        '..', '..', '..', '..', 'scripts', 'create_financial_schema.sql'
    )
    
    if not os.path.exists(schema_file):
        click.echo(f"✗ Schema file not found: {schema_file}")
        return
    
    try:
        # Execute schema creation
        settings = get_settings()
        db_url = settings.database_url
        if not db_url:
            click.echo("✗ Database URL not configured")
            return
        
        click.echo("Creating financial database schema...")
        result = subprocess.run([
            'psql', db_url, '-f', schema_file
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            click.echo("✓ Financial schema created successfully")
        else:
            click.echo(f"✗ Schema creation failed: {result.stderr}")
            
    except FileNotFoundError:
        click.echo("✗ psql command not found. Please install PostgreSQL client.")
    except Exception as e:
        click.echo(f"✗ Schema creation failed: {str(e)}")


async def _load_sample_data():
    """Load sample financial data."""
    sample_symbols = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN']
    sample_indicators = ['GDP', 'UNRATE', 'FEDFUNDS', 'CPIAUCSL']
    
    click.echo("Loading sample financial data...")
    
    async with FinancialDataLoader() as loader:
        # Load sample stocks
        await loader.load_securities_info(sample_symbols)
        price_response = await loader.load_daily_prices_batch(sample_symbols, use_csv=True)
        
        # Load sample economic data
        start_date = date.today() - timedelta(days=365)
        econ_response = await loader.load_economic_indicators(
            sample_indicators, start_date, date.today()
        )
        
        click.echo(f"✓ Sample data loaded: {price_response.records_loaded + econ_response.records_loaded} total records")


async def _show_symbol_prices(symbol: str, days: int):
    """Show recent prices for a symbol."""
    import psycopg2
    from psycopg2.extras import DictCursor
    
    settings = get_settings()
    conn = psycopg2.connect(settings.database_url)
    
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("""
                SELECT trade_date, close_price, volume, 
                       (close_price - LAG(close_price) OVER (ORDER BY trade_date)) / 
                       LAG(close_price) OVER (ORDER BY trade_date) * 100 as daily_return
                FROM daily_prices 
                WHERE symbol = %s 
                ORDER BY trade_date DESC 
                LIMIT %s
            """, (symbol, days))
            
            prices = cur.fetchall()
            
            if not prices:
                click.echo(f"No price data found for {symbol}")
                return
            
            click.echo(f"Recent prices for {symbol} (last {len(prices)} days)")
            click.echo("=" * 60)
            click.echo(f"{'Date':<12} {'Price':<10} {'Volume':<12} {'Return %':<10}")
            click.echo("-" * 60)
            
            for price in prices:
                return_str = f"{price['daily_return']:.2f}%" if price['daily_return'] else "N/A"
                click.echo(f"{price['trade_date']:<12} {price['close_price']:<10} {price['volume']:<12,} {return_str:<10}")
                
    finally:
        conn.close()


async def _show_indicators(symbol: Optional[str], limit: int):
    """Show economic indicators."""
    import psycopg2
    from psycopg2.extras import DictCursor
    
    settings = get_settings()
    conn = psycopg2.connect(settings.database_url)
    
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            if symbol:
                # This doesn't make sense for economic indicators, show message
                click.echo("Economic indicators are not symbol-specific. Showing all indicators.")
            
            cur.execute("""
                SELECT indicator_code, indicator_name, date, value, unit
                FROM economic_indicators 
                ORDER BY date DESC, indicator_code
                LIMIT %s
            """, (limit,))
            
            indicators = cur.fetchall()
            
            if not indicators:
                click.echo("No economic indicator data found")
                return
            
            click.echo(f"Recent economic indicators (last {len(indicators)} records)")
            click.echo("=" * 80)
            click.echo(f"{'Code':<12} {'Date':<12} {'Value':<15} {'Unit':<20} {'Name':<20}")
            click.echo("-" * 80)
            
            for ind in indicators:
                name = (ind['indicator_name'] or '')[:20]
                unit = (ind['unit'] or '')[:20]
                click.echo(f"{ind['indicator_code']:<12} {ind['date']:<12} {ind['value']:<15} {unit:<20} {name:<20}")
                
    finally:
        conn.close()


# Register the financial command group
if __name__ == '__main__':
    financial()