#!/usr/bin/env python3
"""
Load essential test data for SENS agent testing.
This script populates the database with enough data to test value discovery and mapping.
"""

import asyncio
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog

from sens.datasource.storage import DatabaseStorage
from sens.settings import get_settings

logger = structlog.get_logger(__name__)

# Essential test data focusing on common query patterns
ESSENTIAL_TEST_DATA = {
    "securities": [
        # Tech giants with variations
        {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "sector": "Technology",
            "aliases": ["Apple", "Apple Computer"],
        },
        {
            "symbol": "MSFT",
            "name": "Microsoft Corporation",
            "sector": "Technology",
            "aliases": ["Microsoft", "MS"],
        },
        {
            "symbol": "GOOGL",
            "name": "Alphabet Inc.",
            "sector": "Technology",
            "aliases": ["Google", "Alphabet"],
        },
        {
            "symbol": "META",
            "name": "Meta Platforms Inc.",
            "sector": "Technology",
            "aliases": ["Facebook", "Meta", "FB"],
        },
        {
            "symbol": "AMZN",
            "name": "Amazon.com Inc.",
            "sector": "Consumer Discretionary",
            "aliases": ["Amazon"],
        },
        {
            "symbol": "NVDA",
            "name": "NVIDIA Corporation",
            "sector": "Technology",
            "aliases": ["NVIDIA", "Nvidia"],
        },
        {
            "symbol": "TSLA",
            "name": "Tesla Inc.",
            "sector": "Consumer Discretionary",
            "aliases": ["Tesla", "Tesla Motors"],
        },
        # Financial sector
        {
            "symbol": "JPM",
            "name": "JPMorgan Chase & Co.",
            "sector": "Finance",
            "aliases": ["JPMorgan", "JP Morgan", "Chase"],
        },
        {
            "symbol": "BAC",
            "name": "Bank of America Corp",
            "sector": "Finance",
            "aliases": ["Bank of America", "BofA"],
        },
        {
            "symbol": "GS",
            "name": "Goldman Sachs Group Inc.",
            "sector": "Finance",
            "aliases": ["Goldman Sachs", "Goldman"],
        },
        # Healthcare
        {
            "symbol": "JNJ",
            "name": "Johnson & Johnson",
            "sector": "Healthcare",
            "aliases": ["J&J", "Johnson and Johnson"],
        },
        {
            "symbol": "PFE",
            "name": "Pfizer Inc.",
            "sector": "Healthcare",
            "aliases": ["Pfizer"],
        },
        {
            "symbol": "UNH",
            "name": "UnitedHealth Group Inc.",
            "sector": "Healthcare",
            "aliases": ["UnitedHealth", "United Health"],
        },
        # Consumer
        {
            "symbol": "WMT",
            "name": "Walmart Inc.",
            "sector": "Consumer Staples",
            "aliases": ["Walmart", "Wal-Mart"],
        },
        {
            "symbol": "DIS",
            "name": "The Walt Disney Company",
            "sector": "Communication Services",
            "aliases": ["Disney", "Walt Disney"],
        },
        {
            "symbol": "MCD",
            "name": "McDonald's Corporation",
            "sector": "Consumer Discretionary",
            "aliases": ["McDonald's", "McDonalds"],
        },
        # ETFs
        {
            "symbol": "SPY",
            "name": "SPDR S&P 500 ETF Trust",
            "sector": "Broad Market",
            "aliases": ["S&P 500 ETF", "SPY"],
        },
        {
            "symbol": "QQQ",
            "name": "Invesco QQQ Trust",
            "sector": "Technology",
            "aliases": ["NASDAQ ETF", "QQQ"],
        },
    ],
    "economic_indicators": [
        {"code": "GDP", "name": "Gross Domestic Product", "frequency": "QUARTERLY"},
        {"code": "UNRATE", "name": "Unemployment Rate", "frequency": "MONTHLY"},
        {"code": "FEDFUNDS", "name": "Federal Funds Rate", "frequency": "MONTHLY"},
        {"code": "CPIAUCSL", "name": "Consumer Price Index", "frequency": "MONTHLY"},
        {"code": "VIXCLS", "name": "CBOE Volatility Index", "frequency": "DAILY"},
    ],
}


async def load_test_data():
    """Load essential test data for agent testing."""
    settings = get_settings()
    storage = DatabaseStorage(settings.db_url)

    try:
        await storage.connect()
        logger.info("Connected to database")

        # Clear existing data for clean testing
        logger.info("Clearing existing data")
        tables = ["daily_prices", "economic_indicators", "securities"]
        for table in tables:
            try:
                await storage.execute(f"DELETE FROM {table}")
                logger.info(f"Cleared {table}")
            except Exception as e:
                logger.warning(f"Could not clear {table}: {e}")

        # Load securities
        logger.info("Loading securities")
        for sec in ESSENTIAL_TEST_DATA["securities"]:
            market_cap = random.randint(100, 3000) * 1_000_000_000
            exchange = "NASDAQ" if sec["sector"] == "Technology" else "NYSE"

            await storage.execute(
                """
                INSERT INTO securities
                (symbol, company_name, sector, market_cap, exchange, country, currency, is_active)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (symbol) DO UPDATE
                SET company_name = EXCLUDED.company_name,
                    sector = EXCLUDED.sector,
                    market_cap = EXCLUDED.market_cap
                """,
                sec["symbol"],
                sec["name"],
                sec["sector"],
                market_cap,
                exchange,
                "USA",
                "USD",
                True,
            )
            logger.info(f"Added security: {sec['symbol']} - {sec['name']}")

        # Generate price data for last 90 days
        logger.info("Generating price data")
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)

        for sec in ESSENTIAL_TEST_DATA["securities"]:
            symbol = sec["symbol"]

            # Base prices
            base_prices = {
                "AAPL": 175,
                "MSFT": 380,
                "GOOGL": 140,
                "AMZN": 170,
                "NVDA": 600,
                "TSLA": 240,
                "META": 500,
                "JPM": 180,
                "JNJ": 155,
                "WMT": 170,
                "SPY": 450,
                "QQQ": 400,
            }

            current_price = base_prices.get(symbol, random.uniform(50, 200))

            current_date = start_date
            price_records = []

            while current_date <= end_date:
                # Skip weekends
                if current_date.weekday() in [5, 6]:
                    current_date += timedelta(days=1)
                    continue

                # Random walk
                change = random.gauss(0, 0.02)
                current_price *= 1 + change

                # OHLCV
                open_price = current_price * (1 + random.gauss(0, 0.01))
                high = max(open_price, current_price) * (1 + random.uniform(0, 0.01))
                low = min(open_price, current_price) * (1 - random.uniform(0, 0.01))
                close = current_price
                volume = random.randint(10_000_000, 50_000_000)

                price_records.append(
                    (
                        symbol,
                        current_date.date(),
                        round(open_price, 4),
                        round(high, 4),
                        round(low, 4),
                        round(close, 4),
                        round(close, 4),  # adj_close
                        volume,
                    )
                )

                current_date += timedelta(days=1)

            # Bulk insert prices
            await storage.execute_many(
                """
                INSERT INTO daily_prices
                (symbol, trade_date, open_price, high_price, low_price, close_price, adj_close, volume)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (symbol, trade_date) DO NOTHING
                """,
                price_records,
            )
            logger.info(f"Generated {len(price_records)} price records for {symbol}")

        # Load economic indicators
        logger.info("Loading economic indicators")
        indicator_values = {
            "GDP": 27000,
            "UNRATE": 3.7,
            "FEDFUNDS": 5.25,
            "CPIAUCSL": 310,
            "VIXCLS": 15,
        }

        for ind in ESSENTIAL_TEST_DATA["economic_indicators"]:
            code = ind["code"]

            # Generate data points based on frequency
            if ind["frequency"] == "DAILY":
                interval_days = 1
            elif ind["frequency"] == "MONTHLY":
                interval_days = 30
            else:  # QUARTERLY
                interval_days = 90

            current_date = start_date
            current_value = indicator_values.get(code, 100)

            while current_date <= end_date:
                # Add variation
                change = random.gauss(0, 0.01)
                current_value *= 1 + change

                await storage.execute(
                    """
                    INSERT INTO economic_indicators
                    (indicator_code, indicator_name, date, value, unit, frequency)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (indicator_code, date) DO UPDATE
                    SET value = EXCLUDED.value
                    """,
                    code,
                    ind["name"],
                    current_date.date(),
                    round(current_value, 4),
                    "Index" if code == "VIXCLS" else "Percent",
                    ind["frequency"],
                )

                current_date += timedelta(days=interval_days)

            logger.info(f"Generated data for indicator: {code}")

        # Get summary
        securities_count = await storage.fetch_one(
            "SELECT COUNT(*) as count FROM securities"
        )
        prices_count = await storage.fetch_one(
            "SELECT COUNT(*) as count FROM daily_prices"
        )
        indicators_count = await storage.fetch_one(
            "SELECT COUNT(*) as count FROM economic_indicators"
        )

        print("\n" + "=" * 60)
        print("✅ TEST DATA LOADED SUCCESSFULLY")
        print("=" * 60)
        print(f"Securities: {securities_count['count']}")
        print(f"Price Records: {prices_count['count']:,}")
        print(f"Economic Indicators: {indicators_count['count']:,}")
        print("\nTest Queries:")
        print("- 'Show me Apple stock prices'")
        print("- 'Technology sector performance'")
        print("- 'Compare Microsoft and Google'")
        print("- 'What is the current GDP?'")
        print("- 'Show me bank stocks'")
        print("=" * 60)

    except Exception as e:
        logger.error("Failed to load test data", error=str(e))
        raise
    finally:
        await storage.disconnect()


if __name__ == "__main__":
    asyncio.run(load_test_data())
