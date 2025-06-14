#!/usr/bin/env python3
"""
Load test data for SENS agent testing.
This script populates the database with sample data for testing the agent's
value discovery and mapping capabilities.
"""

import asyncio
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from sens.execution.executor import SQLExecutor
from sens.settings import get_settings

# Common stock mappings for testing
STOCK_DATA = [
    # Tech companies
    ("AAPL", "Apple Inc.", "Technology"),
    ("MSFT", "Microsoft Corporation", "Technology"),
    ("GOOGL", "Alphabet Inc.", "Technology"),
    ("AMZN", "Amazon.com Inc.", "Technology"),
    ("META", "Meta Platforms Inc.", "Technology"),
    ("NVDA", "NVIDIA Corporation", "Technology"),
    # Finance
    ("JPM", "JPMorgan Chase & Co.", "Finance"),
    ("BAC", "Bank of America Corp.", "Finance"),
    ("WFC", "Wells Fargo & Co.", "Finance"),
    # Healthcare
    ("JNJ", "Johnson & Johnson", "Healthcare"),
    ("PFE", "Pfizer Inc.", "Healthcare"),
    ("UNH", "UnitedHealth Group Inc.", "Healthcare"),
    # Energy
    ("XOM", "Exxon Mobil Corp.", "Energy"),
    ("CVX", "Chevron Corp.", "Energy"),
    # Consumer
    ("WMT", "Walmart Inc.", "Consumer"),
    ("KO", "The Coca-Cola Company", "Consumer"),
    ("PEP", "PepsiCo Inc.", "Consumer"),
    ("MCD", "McDonald's Corp.", "Consumer"),
]


def generate_price_data(symbol: str, base_price: float, days: int = 90):
    """Generate realistic stock price data."""
    prices = []
    current_price = base_price
    end_date = datetime.now().date()

    for i in range(days):
        trade_date = end_date - timedelta(days=days - i - 1)

        # Random walk with trend
        daily_return = random.gauss(0.0002, 0.02)  # 0.02% daily return, 2% volatility
        current_price *= 1 + daily_return

        # OHLC data
        open_price = current_price * random.uniform(0.99, 1.01)
        high_price = max(open_price, current_price * random.uniform(1.0, 1.02))
        low_price = min(open_price, current_price * random.uniform(0.98, 1.0))
        close_price = current_price
        volume = int(random.uniform(10_000_000, 50_000_000))

        prices.append(
            {
                "symbol": symbol,
                "trade_date": trade_date,
                "open_price": round(open_price, 2),
                "high_price": round(high_price, 2),
                "low_price": round(low_price, 2),
                "close_price": round(close_price, 2),
                "adj_close": round(close_price, 2),
                "volume": volume,
                "data_source": "test_data",
            }
        )

    return prices


def main():
    """Load test data into the database."""
    print("🚀 Loading test data for SENS agent testing...")

    # Get database connection
    settings = get_settings()
    executor = SQLExecutor(settings.db_url)

    try:
        # 1. Create securities table if needed and populate
        print("\n📊 Loading securities data...")

        # Clear existing test data
        symbols = [s[0] for s in STOCK_DATA]
        placeholders = ",".join(["%s"] * len(symbols))
        executor.execute_with_params(
            f"DELETE FROM securities WHERE symbol IN ({placeholders})", tuple(symbols)
        )

        # Insert securities
        for symbol, name, sector in STOCK_DATA:
            try:
                executor.execute_with_params(
                    """
                    INSERT INTO securities (symbol, name, exchange, sector, market_cap, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (symbol) DO UPDATE SET name = EXCLUDED.name
                """,
                    (
                        symbol,
                        name,
                        "NASDAQ",
                        sector,
                        random.randint(10, 2000) * 1_000_000_000,
                        True,
                    ),
                )
            except Exception as e:
                print(f"Warning: Could not insert {symbol}: {e}")

        print(f"✅ Loaded {len(STOCK_DATA)} securities")

        # 2. Load price data into recent tables
        print("\n📈 Loading price data...")

        # Base prices for each stock
        base_prices = {
            "AAPL": 175.0,
            "MSFT": 380.0,
            "GOOGL": 140.0,
            "AMZN": 170.0,
            "META": 500.0,
            "NVDA": 880.0,
            "JPM": 200.0,
            "BAC": 35.0,
            "WFC": 55.0,
            "JNJ": 155.0,
            "PFE": 30.0,
            "UNH": 550.0,
            "XOM": 110.0,
            "CVX": 160.0,
            "WMT": 165.0,
            "KO": 60.0,
            "PEP": 180.0,
            "MCD": 280.0,
        }

        # Generate data for the last 90 days
        total_rows = 0
        for symbol, _, _ in STOCK_DATA:
            base_price = base_prices.get(symbol, 100.0)
            price_data = generate_price_data(symbol, base_price, days=90)

            # Group by month
            for price in price_data:
                # Determine table name based on date
                year_month = price["trade_date"].strftime("%Y_%m")
                table_name = f"daily_prices_{year_month}"

                try:
                    # Insert into appropriate table
                    executor.execute_with_params(
                        f"""
                        INSERT INTO {table_name}
                        (symbol, trade_date, open_price, high_price, low_price,
                         close_price, adj_close, volume, data_source)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (symbol, trade_date) DO UPDATE SET
                            close_price = EXCLUDED.close_price
                    """,
                        (
                            price["symbol"],
                            price["trade_date"],
                            price["open_price"],
                            price["high_price"],
                            price["low_price"],
                            price["close_price"],
                            price["adj_close"],
                            price["volume"],
                            price["data_source"],
                        ),
                    )
                    total_rows += 1
                except Exception as e:
                    # Table might not exist for this month
                    pass

        print(f"✅ Loaded {total_rows} price records")

        # 3. Load some economic indicators
        print("\n📊 Loading economic indicators...")

        indicators = [
            ("GDP", "GDP Growth Rate", "Gross Domestic Product Growth"),
            ("CPI", "Consumer Price Index", "Inflation Indicator"),
            ("UNRATE", "Unemployment Rate", "US Unemployment Rate"),
            ("DFF", "Federal Funds Rate", "Federal Interest Rate"),
            ("VIX", "Volatility Index", "Market Volatility"),
        ]

        # Clear existing test indicators
        executor.execute_with_params(
            "DELETE FROM economic_indicators WHERE data_source = %s", ("test_data",)
        )

        # Generate indicator data
        end_date = datetime.now().date()
        for days_ago in range(90):
            date = end_date - timedelta(days=days_ago)

            for code, name, desc in indicators:
                value = (
                    random.uniform(0.5, 5.0)
                    if code != "VIX"
                    else random.uniform(10, 30)
                )

                try:
                    executor.execute_with_params(
                        """
                        INSERT INTO economic_indicators
                        (indicator_code, indicator_name, value, report_date, data_source)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (indicator_code, report_date) DO UPDATE SET
                            value = EXCLUDED.value
                    """,
                        (code, name, round(value, 2), date, "test_data"),
                    )
                except Exception as e:
                    pass

        print(f"✅ Loaded economic indicators")

        # 4. Verify data
        print("\n🔍 Verifying data...")

        # Check securities
        result = executor.execute(
            "SELECT COUNT(*) FROM securities WHERE symbol = 'AAPL'"
        )
        if result.rows[0][0] > 0:
            print("✅ Securities table populated")

        # Check recent price data
        current_month = datetime.now().strftime("%Y_%m")
        table_name = f"daily_prices_{current_month}"
        try:
            result = executor.execute(
                f"SELECT COUNT(*) FROM {table_name} WHERE symbol = 'AAPL'"
            )
            if result.rows[0][0] > 0:
                print(f"✅ Price data in {table_name} populated")
        except:
            pass

        # Test value search
        result = executor.execute(
            """
            SELECT DISTINCT symbol
            FROM securities
            WHERE LOWER(name) LIKE '%apple%' OR symbol = 'AAPL'
        """
        )
        if result.rows:
            print("✅ Value search test passed - found Apple/AAPL mapping")

        print("\n✨ Test data loaded successfully!")
        print("\nYou can now run agent tests with:")
        print("  poetry run python test_agent_improvements.py")
        print("  poetry run python test_single_agent.py")

    except Exception as e:
        print(f"\n❌ Error loading data: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
