#!/usr/bin/env python3
"""
Generate comprehensive sample financial data for SENS.
No API calls required - perfect for development and testing.
"""

import asyncio
import random
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sens.datasource.financial import FinancialDataLoader  # noqa: E402
from sens.datasource.financial.models import Security, StockPrice  # noqa: E402

# Realistic stock symbols with sectors
SAMPLE_STOCKS = {
    "Technology": {
        "AAPL": "Apple Inc.",
        "MSFT": "Microsoft Corporation",
        "GOOGL": "Alphabet Inc.",
        "META": "Meta Platforms Inc.",
        "NVDA": "NVIDIA Corporation",
        "TSLA": "Tesla Inc.",
    },
    "Finance": {
        "JPM": "JPMorgan Chase & Co.",
        "BAC": "Bank of America Corp",
        "GS": "Goldman Sachs Group Inc.",
        "WFC": "Wells Fargo & Company",
    },
    "Healthcare": {
        "JNJ": "Johnson & Johnson",
        "UNH": "UnitedHealth Group Inc.",
        "PFE": "Pfizer Inc.",
        "CVS": "CVS Health Corporation",
    },
    "Consumer": {
        "AMZN": "Amazon.com Inc.",
        "WMT": "Walmart Inc.",
        "HD": "The Home Depot Inc.",
        "DIS": "The Walt Disney Company",
    },
    "Energy": {"XOM": "Exxon Mobil Corporation", "CVX": "Chevron Corporation"},
}

# Price ranges for realistic data
PRICE_RANGES = {
    "AAPL": (150, 200),
    "MSFT": (300, 400),
    "GOOGL": (120, 160),
    "AMZN": (140, 180),
    "NVDA": (400, 600),
    "TSLA": (180, 280),
    "JPM": (140, 180),
    "JNJ": (150, 170),
    "WMT": (140, 160),
    "XOM": (80, 120),
}


def generate_price_series(symbol: str, start_date: datetime, days: int) -> list:
    """Generate realistic price data with trends and volatility."""
    prices = []

    # Get price range or use default
    min_price, max_price = PRICE_RANGES.get(symbol, (50, 150))
    current_price = random.uniform(min_price, max_price)

    # Generate trend
    trend = random.choice([-0.0002, 0, 0.0001, 0.0002, 0.0003])  # Daily trend
    volatility = random.uniform(0.01, 0.03)  # Daily volatility

    for i in range(days):
        date = start_date - timedelta(days=days - i - 1)

        # Apply trend and random walk
        change = trend + random.gauss(0, volatility)
        current_price *= 1 + change

        # Keep within bounds
        current_price = max(min_price * 0.8, min(max_price * 1.2, current_price))

        # Generate OHLCV data
        open_price = current_price * (1 + random.gauss(0, volatility / 2))
        high = max(open_price, current_price) * (1 + random.uniform(0, volatility))
        low = min(open_price, current_price) * (1 - random.uniform(0, volatility))
        close = current_price
        volume = int(
            random.uniform(10_000_000, 50_000_000) * (1 + random.gauss(0, 0.3))
        )

        prices.append(
            {
                "symbol": symbol,
                "trade_date": date.date(),
                "open_price": round(open_price, 2),
                "high_price": round(high, 2),
                "low_price": round(low, 2),
                "close_price": round(close, 2),
                "adj_close": round(close, 2),
                "volume": volume,
            }
        )

    return prices


def generate_economic_data(start_date: datetime, days: int) -> list:
    """Generate realistic economic indicator data."""
    indicators = []

    # Define economic indicators with realistic ranges
    indicator_configs = {
        "GDP": {
            "name": "Gross Domestic Product",
            "value": 25000,
            "volatility": 0.001,
            "unit": "Billions USD",
        },
        "UNRATE": {
            "name": "Unemployment Rate",
            "value": 3.7,
            "volatility": 0.02,
            "unit": "Percent",
        },
        "CPIAUCSL": {
            "name": "Consumer Price Index",
            "value": 310,
            "volatility": 0.002,
            "unit": "Index",
        },
        "FEDFUNDS": {
            "name": "Federal Funds Rate",
            "value": 5.25,
            "volatility": 0.01,
            "unit": "Percent",
        },
        "DGS10": {
            "name": "10-Year Treasury Rate",
            "value": 4.5,
            "volatility": 0.02,
            "unit": "Percent",
        },
        "DGS2": {
            "name": "2-Year Treasury Rate",
            "value": 4.8,
            "volatility": 0.03,
            "unit": "Percent",
        },
        "VIXCLS": {
            "name": "CBOE Volatility Index",
            "value": 15,
            "volatility": 0.1,
            "unit": "Index",
        },
    }

    for code, config in indicator_configs.items():
        current_value = config["value"]

        # Generate monthly data points
        for i in range(0, days, 30):  # Monthly frequency
            date = start_date - timedelta(days=days - i)

            # Apply random walk
            change = random.gauss(0, config["volatility"])
            current_value *= 1 + change

            indicators.append(
                {
                    "indicator_code": code,
                    "indicator_name": config["name"],
                    "date": date.date(),
                    "value": round(current_value, 2),
                    "unit": config["unit"],
                }
            )

    return indicators


async def generate_sample_data():
    """Generate comprehensive sample data."""
    print("🎲 Generating Sample Financial Data")
    print("=" * 60)

    end_date = datetime.now()
    days = 365  # 1 year of data

    async with FinancialDataLoader() as loader:
        # Insert securities
        print("\n📊 Creating securities...")
        total_symbols = sum(len(stocks) for stocks in SAMPLE_STOCKS.values())
        created = 0

        for sector, stocks in SAMPLE_STOCKS.items():
            for symbol, name in stocks.items():
                try:
                    # Check if exists
                    existing = await loader.execute_query(
                        "SELECT 1 FROM securities WHERE symbol = %s", (symbol,)
                    )

                    if not existing:
                        await loader.execute_query(
                            """
                            INSERT INTO securities (symbol, company_name, sector, market_cap, country)
                            VALUES (%s, %s, %s, %s, %s)
                        """,
                            (
                                symbol,
                                name,
                                sector,
                                random.randint(10, 3000) * 1_000_000_000,
                                "US",
                            ),
                        )
                        created += 1
                        print(f"  ✓ Created {symbol} - {name}")
                    else:
                        print(f"  → {symbol} already exists")

                except Exception as e:
                    print(f"  ✗ Error creating {symbol}: {e}")

        print(f"\n✅ Created {created}/{total_symbols} securities")

        # Generate price data
        print("\n📈 Generating price data...")
        total_prices = 0

        for sector, stocks in SAMPLE_STOCKS.items():
            for symbol in stocks.keys():
                prices = generate_price_series(symbol, end_date, days)

                # Bulk insert
                for price_batch in [
                    prices[i : i + 100] for i in range(0, len(prices), 100)
                ]:
                    values = []
                    for p in price_batch:
                        values.extend(
                            [
                                p["symbol"],
                                p["trade_date"],
                                p["open_price"],
                                p["high_price"],
                                p["low_price"],
                                p["close_price"],
                                p["adj_close"],
                                p["volume"],
                            ]
                        )

                    placeholders = ",".join(
                        ["(%s,%s,%s,%s,%s,%s,%s,%s)"] * len(price_batch)
                    )

                    await loader.execute_query(
                        f"""
                        INSERT INTO daily_prices
                        (symbol, trade_date, open_price, high_price, low_price, close_price, adj_close, volume)
                        VALUES {placeholders}
                        ON CONFLICT (symbol, trade_date) DO NOTHING
                    """,
                        values,
                    )

                total_prices += len(prices)
                print(f"  ✓ Generated {len(prices)} days for {symbol}")

        print(f"\n✅ Generated {total_prices} price records")

        # Generate economic indicators
        print("\n📊 Generating economic indicators...")
        indicators = generate_economic_data(end_date, days)

        for ind in indicators:
            try:
                await loader.execute_query(
                    """
                    INSERT INTO economic_indicators
                    (indicator_code, indicator_name, date, value, unit)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (indicator_code, date) DO UPDATE
                    SET value = EXCLUDED.value
                """,
                    (
                        ind["indicator_code"],
                        ind["indicator_name"],
                        ind["date"],
                        ind["value"],
                        ind["unit"],
                    ),
                )
            except Exception as e:
                print(f"  ✗ Error inserting {ind['indicator_code']}: {e}")

        print(f"✅ Generated {len(indicators)} economic data points")

        # Summary
        print("\n📊 Data Generation Summary")
        print("=" * 60)
        print(f"Securities: {total_symbols} companies across 5 sectors")
        print(
            f"Price Data: {total_prices} daily records ({days} days × {total_symbols} stocks)"
        )
        print(f"Economic Data: {len(indicators)} monthly indicators")
        print(f"\nTotal Data Points: ~{total_prices + len(indicators):,}")

        print("\n✨ Sample data generation complete!")
        print("\nYou can now run queries like:")
        print("- 'Show me tech stocks'")
        print("- 'What is Apple's latest price?'")
        print("- 'Compare MSFT and GOOGL over the last month'")
        print("- 'Show me the unemployment rate trend'")


if __name__ == "__main__":
    asyncio.run(generate_sample_data())
