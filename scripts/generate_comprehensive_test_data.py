#!/usr/bin/env python3
"""
Comprehensive test data generation for SENS agent testing.
Generates realistic financial data with edge cases for value discovery and mapping.
"""

import asyncio
import random
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import structlog

from sens.datasource.storage import DatabaseStorage
from sens.settings import get_settings

logger = structlog.get_logger(__name__)

# Comprehensive stock data with variations for testing value mapping
COMPREHENSIVE_STOCKS = {
    "Technology": {
        # Common variations in naming
        "AAPL": {"name": "Apple Inc.", "aliases": ["Apple", "Apple Computer", "AAPL"]},
        "MSFT": {
            "name": "Microsoft Corporation",
            "aliases": ["Microsoft", "MSFT", "MS"],
        },
        "GOOGL": {"name": "Alphabet Inc.", "aliases": ["Google", "Alphabet", "GOOGL"]},
        "META": {"name": "Meta Platforms Inc.", "aliases": ["Facebook", "Meta", "FB"]},
        "NVDA": {"name": "NVIDIA Corporation", "aliases": ["NVIDIA", "Nvidia", "NVDA"]},
        "TSLA": {"name": "Tesla Inc.", "aliases": ["Tesla", "Tesla Motors", "TSLA"]},
        "CRM": {"name": "Salesforce Inc.", "aliases": ["Salesforce", "CRM", "SFDC"]},
        "ORCL": {"name": "Oracle Corporation", "aliases": ["Oracle", "ORCL"]},
        "ADBE": {"name": "Adobe Inc.", "aliases": ["Adobe", "Adobe Systems", "ADBE"]},
        "NFLX": {"name": "Netflix Inc.", "aliases": ["Netflix", "NFLX"]},
    },
    "Finance": {
        "JPM": {
            "name": "JPMorgan Chase & Co.",
            "aliases": ["JPMorgan", "JP Morgan", "Chase", "JPM"],
        },
        "BAC": {
            "name": "Bank of America Corp",
            "aliases": ["Bank of America", "BofA", "BAC"],
        },
        "GS": {
            "name": "Goldman Sachs Group Inc.",
            "aliases": ["Goldman Sachs", "Goldman", "GS"],
        },
        "WFC": {"name": "Wells Fargo & Company", "aliases": ["Wells Fargo", "WFC"]},
        "MS": {"name": "Morgan Stanley", "aliases": ["Morgan Stanley", "MS"]},
        "V": {"name": "Visa Inc.", "aliases": ["Visa", "V"]},
        "MA": {"name": "Mastercard Incorporated", "aliases": ["Mastercard", "MA"]},
        "PYPL": {"name": "PayPal Holdings Inc.", "aliases": ["PayPal", "PYPL"]},
    },
    "Healthcare": {
        "JNJ": {
            "name": "Johnson & Johnson",
            "aliases": ["J&J", "Johnson and Johnson", "JNJ"],
        },
        "UNH": {
            "name": "UnitedHealth Group Inc.",
            "aliases": ["UnitedHealth", "United Health", "UNH"],
        },
        "PFE": {"name": "Pfizer Inc.", "aliases": ["Pfizer", "PFE"]},
        "CVS": {
            "name": "CVS Health Corporation",
            "aliases": ["CVS", "CVS Health", "CVS Pharmacy"],
        },
        "ABBV": {"name": "AbbVie Inc.", "aliases": ["AbbVie", "ABBV"]},
        "MRK": {"name": "Merck & Co. Inc.", "aliases": ["Merck", "MRK"]},
        "LLY": {
            "name": "Eli Lilly and Company",
            "aliases": ["Lilly", "Eli Lilly", "LLY"],
        },
    },
    "Consumer Discretionary": {
        "AMZN": {"name": "Amazon.com Inc.", "aliases": ["Amazon", "AMZN"]},
        "TSLA": {"name": "Tesla Inc.", "aliases": ["Tesla", "Tesla Motors", "TSLA"]},
        "HD": {"name": "The Home Depot Inc.", "aliases": ["Home Depot", "HD"]},
        "DIS": {
            "name": "The Walt Disney Company",
            "aliases": ["Disney", "Walt Disney", "DIS"],
        },
        "MCD": {
            "name": "McDonald's Corporation",
            "aliases": ["McDonald's", "McDonalds", "MCD"],
        },
        "NKE": {"name": "Nike Inc.", "aliases": ["Nike", "NKE"]},
        "SBUX": {"name": "Starbucks Corporation", "aliases": ["Starbucks", "SBUX"]},
    },
    "Consumer Staples": {
        "WMT": {"name": "Walmart Inc.", "aliases": ["Walmart", "Wal-Mart", "WMT"]},
        "PG": {
            "name": "Procter & Gamble Co.",
            "aliases": ["P&G", "Procter and Gamble", "PG"],
        },
        "KO": {"name": "The Coca-Cola Company", "aliases": ["Coca-Cola", "Coke", "KO"]},
        "PEP": {"name": "PepsiCo Inc.", "aliases": ["Pepsi", "PepsiCo", "PEP"]},
        "COST": {"name": "Costco Wholesale Corporation", "aliases": ["Costco", "COST"]},
    },
    "Energy": {
        "XOM": {
            "name": "Exxon Mobil Corporation",
            "aliases": ["Exxon", "ExxonMobil", "XOM"],
        },
        "CVX": {"name": "Chevron Corporation", "aliases": ["Chevron", "CVX"]},
        "COP": {
            "name": "ConocoPhillips",
            "aliases": ["Conoco", "ConocoPhillips", "COP"],
        },
    },
    "Industrials": {
        "BA": {"name": "The Boeing Company", "aliases": ["Boeing", "BA"]},
        "CAT": {"name": "Caterpillar Inc.", "aliases": ["Caterpillar", "CAT"]},
        "GE": {
            "name": "General Electric Company",
            "aliases": ["GE", "General Electric"],
        },
        "MMM": {"name": "3M Company", "aliases": ["3M", "MMM"]},
    },
    "Communication Services": {
        "GOOGL": {"name": "Alphabet Inc.", "aliases": ["Google", "Alphabet", "GOOGL"]},
        "META": {"name": "Meta Platforms Inc.", "aliases": ["Facebook", "Meta", "FB"]},
        "DIS": {
            "name": "The Walt Disney Company",
            "aliases": ["Disney", "Walt Disney", "DIS"],
        },
        "NFLX": {"name": "Netflix Inc.", "aliases": ["Netflix", "NFLX"]},
        "T": {"name": "AT&T Inc.", "aliases": ["AT&T", "ATT", "T"]},
        "VZ": {"name": "Verizon Communications Inc.", "aliases": ["Verizon", "VZ"]},
    },
}

# ETFs for sector analysis
SECTOR_ETFS = {
    "SPY": {"name": "SPDR S&P 500 ETF Trust", "sector": "Broad Market"},
    "QQQ": {"name": "Invesco QQQ Trust", "sector": "Technology"},
    "DIA": {"name": "SPDR Dow Jones Industrial Average ETF", "sector": "Broad Market"},
    "IWM": {"name": "iShares Russell 2000 ETF", "sector": "Small Cap"},
    "XLK": {"name": "Technology Select Sector SPDR Fund", "sector": "Technology"},
    "XLF": {"name": "Financial Select Sector SPDR Fund", "sector": "Finance"},
    "XLV": {"name": "Health Care Select Sector SPDR Fund", "sector": "Healthcare"},
    "XLE": {"name": "Energy Select Sector SPDR Fund", "sector": "Energy"},
    "XLI": {"name": "Industrial Select Sector SPDR Fund", "sector": "Industrials"},
    "XLY": {
        "name": "Consumer Discretionary Select Sector SPDR Fund",
        "sector": "Consumer Discretionary",
    },
    "XLP": {
        "name": "Consumer Staples Select Sector SPDR Fund",
        "sector": "Consumer Staples",
    },
}

# Economic indicators with comprehensive data
ECONOMIC_INDICATORS = {
    "GDP": {
        "name": "Gross Domestic Product",
        "frequency": "QUARTERLY",
        "unit": "Billions of Dollars",
    },
    "UNRATE": {"name": "Unemployment Rate", "frequency": "MONTHLY", "unit": "Percent"},
    "FEDFUNDS": {
        "name": "Federal Funds Rate",
        "frequency": "MONTHLY",
        "unit": "Percent",
    },
    "CPIAUCSL": {
        "name": "Consumer Price Index",
        "frequency": "MONTHLY",
        "unit": "Index 1982-1984=100",
    },
    "PAYEMS": {
        "name": "Nonfarm Payrolls",
        "frequency": "MONTHLY",
        "unit": "Thousands of Persons",
    },
    "VIXCLS": {"name": "CBOE Volatility Index", "frequency": "DAILY", "unit": "Index"},
    "DGS10": {"name": "10-Year Treasury Rate", "frequency": "DAILY", "unit": "Percent"},
    "DGS2": {"name": "2-Year Treasury Rate", "frequency": "DAILY", "unit": "Percent"},
    "DEXUSEU": {
        "name": "USD/EUR Exchange Rate",
        "frequency": "DAILY",
        "unit": "USD per EUR",
    },
    "INDPRO": {
        "name": "Industrial Production Index",
        "frequency": "MONTHLY",
        "unit": "Index 2017=100",
    },
    "UMCSENT": {
        "name": "Consumer Sentiment",
        "frequency": "MONTHLY",
        "unit": "Index 1966Q1=100",
    },
    "HOUST": {
        "name": "Housing Starts",
        "frequency": "MONTHLY",
        "unit": "Thousands of Units",
    },
    "RSXFS": {
        "name": "Retail Sales",
        "frequency": "MONTHLY",
        "unit": "Millions of Dollars",
    },
    "DSPIC96": {
        "name": "Real Disposable Personal Income",
        "frequency": "MONTHLY",
        "unit": "Billions of Chained 2012 Dollars",
    },
}

# Price volatility profiles for different stock types
VOLATILITY_PROFILES = {
    "stable": {"trend": 0.0001, "volatility": 0.01},  # Blue chips
    "growth": {"trend": 0.0003, "volatility": 0.02},  # Growth stocks
    "volatile": {"trend": 0.0002, "volatility": 0.04},  # Tech stocks
    "defensive": {"trend": 0.00005, "volatility": 0.008},  # Utilities, consumer staples
}


class ComprehensiveDataGenerator:
    """Generate comprehensive test data for SENS."""

    def __init__(self):
        self.settings = get_settings()
        self.storage = DatabaseStorage(self.settings.db_url)

    async def __aenter__(self):
        await self.storage.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.storage.disconnect()

    async def generate_all_data(self, days: int = 730):  # 2 years by default
        """Generate all test data."""
        logger.info("Starting comprehensive data generation", days=days)

        # Clear existing data for clean test environment
        await self._clear_existing_data()

        # Generate data in order
        await self._create_securities()
        await self._generate_price_data(days)
        await self._generate_economic_indicators(days)
        await self._generate_financial_statements()
        await self._generate_sample_trades()
        await self._generate_portfolio_data()
        await self._generate_market_data()

        # Create indexes for performance
        await self._create_performance_indexes()

        # Summary
        await self._print_summary()

    async def _clear_existing_data(self):
        """Clear existing data for clean test environment."""
        logger.info("Clearing existing data")

        tables = [
            "market_data",
            "portfolio_holdings",
            "trades",
            "options_contracts",
            "financial_statements",
            "economic_indicators",
            "daily_prices",
            "securities",
        ]

        for table in tables:
            try:
                await self.storage.execute(f"TRUNCATE TABLE {table} CASCADE")
                logger.info(f"Cleared table {table}")
            except Exception as e:
                logger.warning(f"Could not clear {table}: {e}")

    async def _create_securities(self):
        """Create all securities with proper metadata."""
        logger.info("Creating securities")

        # Regular stocks
        for sector, stocks in COMPREHENSIVE_STOCKS.items():
            for symbol, data in stocks.items():
                # Skip duplicates (TSLA appears in multiple sectors)
                existing = await self.storage.fetch_one(
                    "SELECT 1 FROM securities WHERE symbol = $1", symbol
                )
                if existing:
                    continue

                market_cap = self._generate_market_cap(symbol)

                await self.storage.execute(
                    """
                    INSERT INTO securities
                    (symbol, company_name, sector, industry, market_cap, exchange, country, currency)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    symbol,
                    data["name"],
                    sector,
                    self._get_industry(sector),
                    market_cap,
                    (
                        "NASDAQ"
                        if symbol
                        in ["AAPL", "MSFT", "GOOGL", "META", "NVDA", "TSLA", "NFLX"]
                        else "NYSE"
                    ),
                    "USA",
                    "USD",
                )

        # ETFs
        for symbol, data in SECTOR_ETFS.items():
            await self.storage.execute(
                """
                INSERT INTO securities
                (symbol, company_name, sector, industry, market_cap, exchange, country, currency)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                symbol,
                data["name"],
                data["sector"],
                "Exchange Traded Fund",
                random.randint(10, 500) * 1_000_000_000,
                "NYSE",
                "USA",
                "USD",
            )

        logger.info(
            "Securities created",
            stocks=len([s for stocks in COMPREHENSIVE_STOCKS.values() for s in stocks]),
            etfs=len(SECTOR_ETFS),
        )

    async def _generate_price_data(self, days: int):
        """Generate comprehensive price data."""
        logger.info("Generating price data", days=days)

        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # Get all securities
        securities = await self.storage.fetch_all(
            "SELECT symbol, sector FROM securities"
        )

        for security in securities:
            symbol = security["symbol"]
            sector = security["sector"]

            # Determine volatility profile
            if symbol in ["AAPL", "MSFT", "JNJ", "PG", "KO"]:
                profile = VOLATILITY_PROFILES["stable"]
            elif symbol in ["NVDA", "TSLA", "NFLX", "CRM"]:
                profile = VOLATILITY_PROFILES["volatile"]
            elif sector in ["Consumer Staples", "Healthcare"]:
                profile = VOLATILITY_PROFILES["defensive"]
            else:
                profile = VOLATILITY_PROFILES["growth"]

            # Generate price series
            prices = self._generate_price_series(symbol, start_date, end_date, profile)

            # Bulk insert
            await self._bulk_insert_prices(prices)

        logger.info("Price data generated", total_records=len(securities) * days)

    def _generate_price_series(
        self, symbol: str, start_date: datetime, end_date: datetime, profile: dict
    ) -> List[dict]:
        """Generate realistic price series with technical indicators."""
        prices = []

        # Initial price based on symbol
        base_prices = {
            "AAPL": 175,
            "MSFT": 380,
            "GOOGL": 140,
            "AMZN": 170,
            "NVDA": 600,
            "TSLA": 240,
            "META": 500,
            "NFLX": 600,
            "JPM": 180,
            "JNJ": 155,
            "WMT": 170,
            "XOM": 110,
            "SPY": 450,
            "QQQ": 400,
            "DIA": 380,
        }

        current_price = base_prices.get(symbol, random.uniform(50, 200))
        prices_history = []

        current_date = start_date
        while current_date <= end_date:
            # Skip weekends
            if current_date.weekday() in [5, 6]:
                current_date += timedelta(days=1)
                continue

            # Apply trend and volatility
            daily_return = random.gauss(profile["trend"], profile["volatility"])
            current_price *= 1 + daily_return

            # Generate OHLCV
            open_price = current_price * (
                1 + random.gauss(0, profile["volatility"] / 2)
            )
            high = max(open_price, current_price) * (
                1 + random.uniform(0, profile["volatility"])
            )
            low = min(open_price, current_price) * (
                1 - random.uniform(0, profile["volatility"])
            )
            close = current_price

            # Volume based on price movement
            base_volume = random.randint(10_000_000, 50_000_000)
            volume = int(base_volume * (1 + abs(daily_return) * 10))

            prices_history.append(close)

            # Calculate technical indicators
            rsi = (
                self._calculate_rsi(prices_history[-14:])
                if len(prices_history) >= 14
                else None
            )
            ma20 = sum(prices_history[-20:]) / 20 if len(prices_history) >= 20 else None
            ma50 = sum(prices_history[-50:]) / 50 if len(prices_history) >= 50 else None
            ma200 = (
                sum(prices_history[-200:]) / 200 if len(prices_history) >= 200 else None
            )

            # Volatility (standard deviation of returns)
            if len(prices_history) >= 20:
                returns = [
                    (prices_history[i] - prices_history[i - 1]) / prices_history[i - 1]
                    for i in range(-19, 0)
                ]
                volatility = (
                    sum((r - sum(returns) / len(returns)) ** 2 for r in returns)
                    / len(returns)
                ) ** 0.5
            else:
                volatility = None

            prices.append(
                {
                    "symbol": symbol,
                    "trade_date": current_date.date(),
                    "open_price": round(open_price, 4),
                    "high_price": round(high, 4),
                    "low_price": round(low, 4),
                    "close_price": round(close, 4),
                    "adj_close": round(close, 4),
                    "volume": volume,
                    "rsi": round(rsi, 2) if rsi else None,
                    "moving_avg_20": round(ma20, 4) if ma20 else None,
                    "moving_avg_50": round(ma50, 4) if ma50 else None,
                    "moving_avg_200": round(ma200, 4) if ma200 else None,
                    "volatility": round(volatility * 100, 4) if volatility else None,
                }
            )

            current_date += timedelta(days=1)

        return prices

    def _calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate RSI indicator."""
        if len(prices) < period:
            return 50.0

        gains = []
        losses = []

        for i in range(1, len(prices)):
            change = prices[i] - prices[i - 1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))

        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    async def _bulk_insert_prices(self, prices: List[dict]):
        """Bulk insert price data."""
        if not prices:
            return

        # Prepare values for bulk insert
        values = []
        for p in prices:
            values.append(
                (
                    p["symbol"],
                    p["trade_date"],
                    p["open_price"],
                    p["high_price"],
                    p["low_price"],
                    p["close_price"],
                    p["adj_close"],
                    p["volume"],
                    p.get("rsi"),
                    p.get("moving_avg_20"),
                    p.get("moving_avg_50"),
                    p.get("moving_avg_200"),
                    p.get("volatility"),
                )
            )

        # Insert in batches
        batch_size = 1000
        for i in range(0, len(values), batch_size):
            batch = values[i : i + batch_size]

            await self.storage.execute_many(
                """
                INSERT INTO daily_prices
                (symbol, trade_date, open_price, high_price, low_price, close_price,
                 adj_close, volume, rsi, moving_avg_20, moving_avg_50, moving_avg_200, volatility)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                ON CONFLICT (symbol, trade_date) DO NOTHING
                """,
                batch,
            )

    async def _generate_economic_indicators(self, days: int):
        """Generate economic indicator data."""
        logger.info("Generating economic indicators")

        end_date = datetime.now()

        for code, config in ECONOMIC_INDICATORS.items():
            # Determine frequency
            if config["frequency"] == "DAILY":
                interval = 1
            elif config["frequency"] == "MONTHLY":
                interval = 30
            elif config["frequency"] == "QUARTERLY":
                interval = 90
            else:
                interval = 30

            # Generate data points
            current_date = end_date - timedelta(days=days)

            # Starting values
            start_values = {
                "GDP": 27000,
                "UNRATE": 3.7,
                "FEDFUNDS": 5.25,
                "CPIAUCSL": 310,
                "PAYEMS": 157000,
                "VIXCLS": 15,
                "DGS10": 4.5,
                "DGS2": 4.8,
                "DEXUSEU": 1.08,
                "INDPRO": 105,
                "UMCSENT": 65,
                "HOUST": 1400,
                "RSXFS": 700000,
                "DSPIC96": 15000,
            }

            current_value = start_values.get(code, 100)

            while current_date <= end_date:
                # Add some realistic variation
                if code == "VIXCLS":  # VIX is more volatile
                    change = random.gauss(0, 0.1)
                elif code in ["FEDFUNDS", "DGS10", "DGS2"]:  # Interest rates
                    change = random.gauss(0, 0.01)
                else:
                    change = random.gauss(0, 0.005)

                current_value *= 1 + change

                await self.storage.execute(
                    """
                    INSERT INTO economic_indicators
                    (indicator_code, indicator_name, date, value, unit, frequency)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (indicator_code, date) DO NOTHING
                    """,
                    code,
                    config["name"],
                    current_date.date(),
                    round(current_value, 4),
                    config["unit"],
                    config["frequency"],
                )

                current_date += timedelta(days=interval)

        logger.info("Economic indicators generated")

    async def _generate_financial_statements(self):
        """Generate quarterly financial statements."""
        logger.info("Generating financial statements")

        # Get all non-ETF securities
        securities = await self.storage.fetch_all(
            """
            SELECT symbol, sector, market_cap
            FROM securities
            WHERE industry != 'Exchange Traded Fund'
            """
        )

        current_year = datetime.now().year

        for security in securities:
            symbol = security["symbol"]
            market_cap = security["market_cap"] or 100_000_000_000

            # Generate last 8 quarters
            for year in range(current_year - 1, current_year + 1):
                for quarter in range(1, 5):
                    if year == current_year and quarter > (
                        (datetime.now().month - 1) // 3 + 1
                    ):
                        continue

                    # Base financials on market cap
                    revenue = int(
                        market_cap * random.uniform(0.2, 0.4) / 4
                    )  # Quarterly

                    await self.storage.execute(
                        """
                        INSERT INTO financial_statements
                        (symbol, fiscal_year, fiscal_quarter, period_end_date,
                         revenue, cost_of_revenue, gross_profit, operating_expenses,
                         operating_income, net_income, total_assets, current_assets,
                         total_liabilities, current_liabilities, shareholders_equity,
                         total_debt, cash_and_equivalents, earnings_per_share,
                         book_value_per_share, shares_outstanding, pe_ratio, pb_ratio,
                         debt_to_equity, roe, roa)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12,
                                $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25)
                        ON CONFLICT (symbol, fiscal_year, fiscal_quarter) DO NOTHING
                        """,
                        symbol,
                        year,
                        quarter,
                        datetime(year, quarter * 3, 1).date(),
                        revenue,
                        int(revenue * random.uniform(0.6, 0.8)),  # cost_of_revenue
                        int(revenue * random.uniform(0.2, 0.4)),  # gross_profit
                        int(revenue * random.uniform(0.1, 0.2)),  # operating_expenses
                        int(revenue * random.uniform(0.1, 0.3)),  # operating_income
                        int(revenue * random.uniform(0.05, 0.2)),  # net_income
                        int(market_cap * random.uniform(1.2, 2.0)),  # total_assets
                        int(market_cap * random.uniform(0.3, 0.6)),  # current_assets
                        int(market_cap * random.uniform(0.4, 0.8)),  # total_liabilities
                        int(
                            market_cap * random.uniform(0.2, 0.4)
                        ),  # current_liabilities
                        int(
                            market_cap * random.uniform(0.4, 0.8)
                        ),  # shareholders_equity
                        int(market_cap * random.uniform(0.1, 0.4)),  # total_debt
                        int(
                            market_cap * random.uniform(0.05, 0.2)
                        ),  # cash_and_equivalents
                        round(random.uniform(1, 10), 2),  # earnings_per_share
                        round(random.uniform(10, 50), 2),  # book_value_per_share
                        int(market_cap / random.uniform(50, 200)),  # shares_outstanding
                        round(random.uniform(10, 40), 2),  # pe_ratio
                        round(random.uniform(1, 5), 2),  # pb_ratio
                        round(random.uniform(0.2, 1.5), 4),  # debt_to_equity
                        round(random.uniform(0.05, 0.25), 4),  # roe
                        round(random.uniform(0.02, 0.15), 4),  # roa
                    )

        logger.info("Financial statements generated")

    async def _generate_sample_trades(self):
        """Generate sample trading data."""
        logger.info("Generating sample trades")

        # Portfolio IDs
        portfolios = [
            "portfolio_001",
            "portfolio_002",
            "portfolio_003",
            "growth_fund",
            "value_fund",
        ]

        # Get some securities
        securities = await self.storage.fetch_all(
            "SELECT symbol FROM securities LIMIT 20"
        )

        end_date = datetime.now()

        for _ in range(500):  # Generate 500 trades
            symbol = random.choice(securities)["symbol"]
            portfolio = random.choice(portfolios)

            # Random date in last 90 days
            days_ago = random.randint(0, 90)
            trade_date = end_date - timedelta(days=days_ago)

            # Get price for that date
            price_data = await self.storage.fetch_one(
                """
                SELECT close_price FROM daily_prices
                WHERE symbol = $1 AND trade_date <= $2
                ORDER BY trade_date DESC LIMIT 1
                """,
                symbol,
                trade_date.date(),
            )

            if price_data:
                price = float(price_data["close_price"])
                quantity = random.randint(10, 1000)

                await self.storage.execute(
                    """
                    INSERT INTO trades
                    (symbol, trade_timestamp, trade_type, quantity, price,
                     commission, portfolio_id, trader_id, order_type, exchange)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    """,
                    symbol,
                    trade_date,
                    random.choice(["BUY", "SELL"]),
                    quantity,
                    price,
                    round(random.uniform(0, 10), 2),
                    portfolio,
                    f"trader_{random.randint(1, 10)}",
                    random.choice(["MARKET", "LIMIT"]),
                    random.choice(["NYSE", "NASDAQ"]),
                )

        logger.info("Sample trades generated")

    async def _generate_portfolio_data(self):
        """Generate portfolio holdings."""
        logger.info("Generating portfolio holdings")

        portfolios = [
            "portfolio_001",
            "portfolio_002",
            "portfolio_003",
            "growth_fund",
            "value_fund",
        ]

        # Get securities by sector
        for portfolio in portfolios:
            # Get 10-20 random securities
            securities = await self.storage.fetch_all(
                "SELECT symbol FROM securities ORDER BY RANDOM() LIMIT $1",
                random.randint(10, 20),
            )

            for security in securities:
                symbol = security["symbol"]

                # Get latest price
                price_data = await self.storage.fetch_one(
                    """
                    SELECT close_price FROM daily_prices
                    WHERE symbol = $1
                    ORDER BY trade_date DESC LIMIT 1
                    """,
                    symbol,
                )

                if price_data:
                    current_price = float(price_data["close_price"])
                    quantity = random.randint(100, 5000)
                    avg_cost = current_price * random.uniform(0.8, 1.2)
                    market_value = quantity * current_price
                    unrealized_pnl = (current_price - avg_cost) * quantity

                    await self.storage.execute(
                        """
                        INSERT INTO portfolio_holdings
                        (portfolio_id, symbol, quantity, avg_cost, current_price,
                         market_value, unrealized_pnl, realized_pnl, first_purchase_date)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        ON CONFLICT (portfolio_id, symbol) DO UPDATE
                        SET quantity = EXCLUDED.quantity,
                            current_price = EXCLUDED.current_price,
                            market_value = EXCLUDED.market_value,
                            unrealized_pnl = EXCLUDED.unrealized_pnl
                        """,
                        portfolio,
                        symbol,
                        quantity,
                        round(avg_cost, 4),
                        round(current_price, 4),
                        round(market_value, 2),
                        round(unrealized_pnl, 2),
                        round(random.uniform(-1000, 5000), 2),  # realized_pnl
                        (
                            datetime.now() - timedelta(days=random.randint(30, 365))
                        ).date(),
                    )

        logger.info("Portfolio holdings generated")

    async def _generate_market_data(self):
        """Generate recent market data (bid/ask spreads)."""
        logger.info("Generating market data")

        # Get active securities
        securities = await self.storage.fetch_all(
            "SELECT symbol FROM securities LIMIT 30"
        )

        now = datetime.now()

        for security in securities:
            symbol = security["symbol"]

            # Get latest price
            price_data = await self.storage.fetch_one(
                """
                SELECT close_price FROM daily_prices
                WHERE symbol = $1
                ORDER BY trade_date DESC LIMIT 1
                """,
                symbol,
            )

            if price_data:
                base_price = float(price_data["close_price"])

                # Generate intraday ticks
                for i in range(100):  # 100 ticks
                    timestamp = now - timedelta(minutes=i * 5)

                    # Small price movements
                    price_change = random.gauss(0, 0.001)
                    current_price = base_price * (1 + price_change)

                    # Bid/ask spread
                    spread = current_price * random.uniform(0.0001, 0.001)
                    bid = current_price - spread / 2
                    ask = current_price + spread / 2

                    await self.storage.execute(
                        """
                        INSERT INTO market_data
                        (symbol, timestamp, bid_price, ask_price, bid_size, ask_size,
                         last_price, volume, spread)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        """,
                        symbol,
                        timestamp,
                        round(bid, 4),
                        round(ask, 4),
                        random.randint(100, 10000),
                        random.randint(100, 10000),
                        round(current_price, 4),
                        random.randint(1000, 100000),
                        round(spread, 4),
                    )

        logger.info("Market data generated")

    async def _create_performance_indexes(self):
        """Create additional indexes for query performance."""
        logger.info("Creating performance indexes")

        # Additional indexes for common query patterns
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_securities_name_lower ON securities (LOWER(company_name))",
            "CREATE INDEX IF NOT EXISTS idx_securities_sector_lower ON securities (LOWER(sector))",
            "CREATE INDEX IF NOT EXISTS idx_daily_prices_symbol_close ON daily_prices (symbol, close_price)",
            "CREATE INDEX IF NOT EXISTS idx_financial_statements_revenue ON financial_statements (symbol, revenue DESC)",
            "CREATE INDEX IF NOT EXISTS idx_portfolio_holdings_value ON portfolio_holdings (portfolio_id, market_value DESC)",
        ]

        for index in indexes:
            try:
                await self.storage.execute(index)
            except Exception as e:
                logger.warning(f"Could not create index: {e}")

        logger.info("Performance indexes created")

    async def _print_summary(self):
        """Print summary of generated data."""
        logger.info("Generating summary")

        # Get counts
        counts = {}
        tables = [
            "securities",
            "daily_prices",
            "economic_indicators",
            "financial_statements",
            "trades",
            "portfolio_holdings",
            "market_data",
        ]

        for table in tables:
            result = await self.storage.fetch_one(
                f"SELECT COUNT(*) as count FROM {table}"
            )
            counts[table] = result["count"]

        print("\n" + "=" * 70)
        print("📊 COMPREHENSIVE TEST DATA GENERATION COMPLETE")
        print("=" * 70)
        print("\nData Summary:")
        print(f"  Securities: {counts['securities']:,}")
        print(f"  Price Records: {counts['daily_prices']:,}")
        print(f"  Economic Indicators: {counts['economic_indicators']:,}")
        print(f"  Financial Statements: {counts['financial_statements']:,}")
        print(f"  Trades: {counts['trades']:,}")
        print(f"  Portfolio Holdings: {counts['portfolio_holdings']:,}")
        print(f"  Market Data Points: {counts['market_data']:,}")
        print(f"\n  Total Records: {sum(counts.values()):,}")

        print("\n✨ Test Scenarios Supported:")
        print("  - Company name variations (Apple, AAPL, Apple Inc.)")
        print("  - Sector queries (technology, tech, Technology)")
        print("  - Similar companies discovery")
        print("  - Financial metrics comparison")
        print("  - Portfolio analysis")
        print("  - Market trends and correlations")
        print("  - Economic indicator analysis")

        print("\n🧪 Example Test Queries:")
        print("  - 'Show me Apple stock' (tests: Apple → AAPL mapping)")
        print("  - 'Technology sector performance' (tests: sector normalization)")
        print("  - 'Compare Google and Microsoft' (tests: name variations)")
        print("  - 'Stocks similar to Tesla' (tests: similarity discovery)")
        print("  - 'GDP vs stock market correlation' (tests: multi-table queries)")
        print("  - 'Portfolio performance last month' (tests: date handling)")
        print("=" * 70)

    def _generate_market_cap(self, symbol: str) -> int:
        """Generate realistic market cap based on symbol."""
        mega_caps = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META"]
        large_caps = ["JPM", "JNJ", "WMT", "UNH", "V", "PG", "HD", "DIS"]

        if symbol in mega_caps:
            return random.randint(1000, 3000) * 1_000_000_000
        elif symbol in large_caps:
            return random.randint(200, 800) * 1_000_000_000
        else:
            return random.randint(10, 200) * 1_000_000_000

    def _get_industry(self, sector: str) -> str:
        """Get industry based on sector."""
        industry_map = {
            "Technology": "Software & Services",
            "Finance": "Banks & Financial Services",
            "Healthcare": "Pharmaceuticals & Biotech",
            "Consumer Discretionary": "Retail & E-commerce",
            "Consumer Staples": "Food & Beverages",
            "Energy": "Oil & Gas",
            "Industrials": "Manufacturing & Aerospace",
            "Communication Services": "Media & Entertainment",
        }
        return industry_map.get(sector, "Diversified")


async def main():
    """Main entry point."""
    print("🚀 Starting Comprehensive Test Data Generation")
    print("This will create extensive test data for SENS agent testing")
    print("-" * 70)

    try:
        async with ComprehensiveDataGenerator() as generator:
            await generator.generate_all_data(days=730)  # 2 years of data

    except Exception as e:
        logger.error("Data generation failed", error=str(e))
        print(f"\n❌ Error: {str(e)}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    print("\n✅ Data generation completed successfully!")
    print("You can now run the agent tests with realistic data.")


if __name__ == "__main__":
    asyncio.run(main())
