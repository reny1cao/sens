"""Data models for financial data integration."""

from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class FinancialDataSource(Enum):
    """Financial data source types."""
    ALPHA_VANTAGE = "alpha_vantage"
    FRED = "fred"
    YAHOO_FINANCE = "yahoo_finance"
    POLYGON = "polygon"
    EOD_HISTORICAL = "eod_historical"


class SecurityType(Enum):
    """Types of securities."""
    STOCK = "stock"
    ETF = "etf"
    MUTUAL_FUND = "mutual_fund"
    INDEX = "index"
    CRYPTO = "crypto"
    FOREX = "forex"


class TradeType(Enum):
    """Types of trades."""
    BUY = "BUY"
    SELL = "SELL"


class OptionType(Enum):
    """Types of options."""
    CALL = "CALL"
    PUT = "PUT"


class Security(BaseModel):
    """Security/stock information."""
    symbol: str
    company_name: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    market_cap: Optional[int] = None
    exchange: Optional[str] = None
    country: str = "USA"
    currency: str = "USD"
    security_type: SecurityType = SecurityType.STOCK
    is_active: bool = True


class StockPrice(BaseModel):
    """Daily stock price data."""
    symbol: str
    trade_date: date
    open_price: Optional[Decimal] = None
    high_price: Optional[Decimal] = None
    low_price: Optional[Decimal] = None
    close_price: Optional[Decimal] = None
    adj_close: Optional[Decimal] = None
    volume: Optional[int] = None
    
    # Technical indicators
    rsi: Optional[Decimal] = None
    moving_avg_20: Optional[Decimal] = None
    moving_avg_50: Optional[Decimal] = None
    moving_avg_200: Optional[Decimal] = None
    volatility: Optional[Decimal] = None
    
    data_source: FinancialDataSource = FinancialDataSource.ALPHA_VANTAGE


class EconomicIndicator(BaseModel):
    """Economic indicator data from FRED."""
    indicator_code: str
    indicator_name: Optional[str] = None
    date: date
    value: Optional[Decimal] = None
    unit: Optional[str] = None
    frequency: Optional[str] = None  # DAILY, WEEKLY, MONTHLY, etc.
    data_source: FinancialDataSource = FinancialDataSource.FRED


class FinancialStatement(BaseModel):
    """Financial statement data."""
    symbol: str
    fiscal_year: int
    fiscal_quarter: Optional[int] = None  # None for annual data
    period_end_date: Optional[date] = None
    
    # Income Statement
    revenue: Optional[int] = None
    cost_of_revenue: Optional[int] = None
    gross_profit: Optional[int] = None
    operating_expenses: Optional[int] = None
    operating_income: Optional[int] = None
    net_income: Optional[int] = None
    
    # Balance Sheet
    total_assets: Optional[int] = None
    current_assets: Optional[int] = None
    total_liabilities: Optional[int] = None
    current_liabilities: Optional[int] = None
    shareholders_equity: Optional[int] = None
    total_debt: Optional[int] = None
    cash_and_equivalents: Optional[int] = None
    
    # Per Share Metrics
    earnings_per_share: Optional[Decimal] = None
    book_value_per_share: Optional[Decimal] = None
    shares_outstanding: Optional[int] = None
    
    # Ratios
    pe_ratio: Optional[Decimal] = None
    pb_ratio: Optional[Decimal] = None
    debt_to_equity: Optional[Decimal] = None
    roe: Optional[Decimal] = None  # Return on Equity
    roa: Optional[Decimal] = None  # Return on Assets
    
    data_source: FinancialDataSource = FinancialDataSource.ALPHA_VANTAGE


class TradingTransaction(BaseModel):
    """Trading transaction record."""
    symbol: str
    trade_timestamp: datetime
    trade_type: TradeType
    quantity: int
    price: Decimal
    commission: Decimal = Decimal('0')
    
    # Portfolio tracking
    portfolio_id: Optional[str] = None
    trader_id: Optional[str] = None
    
    # Order details
    order_type: Optional[str] = None  # MARKET, LIMIT, STOP
    exchange: Optional[str] = None


class PortfolioHolding(BaseModel):
    """Portfolio holding information."""
    portfolio_id: str
    symbol: str
    quantity: int
    avg_cost: Optional[Decimal] = None
    current_price: Optional[Decimal] = None
    market_value: Optional[Decimal] = None
    unrealized_pnl: Optional[Decimal] = None
    realized_pnl: Optional[Decimal] = None
    first_purchase_date: Optional[date] = None


class OptionsContract(BaseModel):
    """Options contract data."""
    contract_id: str
    underlying_symbol: str
    option_type: OptionType
    strike_price: Decimal
    expiration_date: date
    
    # Pricing
    premium: Optional[Decimal] = None
    bid_price: Optional[Decimal] = None
    ask_price: Optional[Decimal] = None
    last_price: Optional[Decimal] = None
    volume: Optional[int] = None
    open_interest: Optional[int] = None
    
    # Greeks
    delta: Optional[Decimal] = None
    gamma: Optional[Decimal] = None
    theta: Optional[Decimal] = None
    vega: Optional[Decimal] = None
    rho: Optional[Decimal] = None
    implied_volatility: Optional[Decimal] = None
    
    trade_date: date
    data_source: FinancialDataSource = FinancialDataSource.ALPHA_VANTAGE


class MarketData(BaseModel):
    """Real-time market data."""
    symbol: str
    timestamp: datetime
    bid_price: Optional[Decimal] = None
    ask_price: Optional[Decimal] = None
    bid_size: Optional[int] = None
    ask_size: Optional[int] = None
    last_price: Optional[Decimal] = None
    volume: Optional[int] = None
    spread: Optional[Decimal] = None
    data_source: Optional[FinancialDataSource] = None


class DataLoadRequest(BaseModel):
    """Request for loading financial data."""
    symbols: List[str]
    start_date: date
    end_date: date
    data_types: List[str] = Field(default_factory=lambda: ["daily_prices"])
    include_technical_indicators: bool = True
    data_source: FinancialDataSource = FinancialDataSource.ALPHA_VANTAGE


class DataLoadResponse(BaseModel):
    """Response from data loading operation."""
    success: bool
    message: str
    symbols_processed: List[str]
    records_loaded: int
    errors: List[str] = Field(default_factory=list)
    execution_time_seconds: float


class FinancialMetrics(BaseModel):
    """Financial performance metrics."""
    symbol: str
    period_start: date
    period_end: date
    
    # Price performance
    total_return: Optional[Decimal] = None
    annualized_return: Optional[Decimal] = None
    volatility: Optional[Decimal] = None
    sharpe_ratio: Optional[Decimal] = None
    max_drawdown: Optional[Decimal] = None
    
    # Trading metrics
    beta: Optional[Decimal] = None
    alpha: Optional[Decimal] = None
    correlation_sp500: Optional[Decimal] = None
    
    # Fundamental metrics
    pe_ratio: Optional[Decimal] = None
    pb_ratio: Optional[Decimal] = None
    dividend_yield: Optional[Decimal] = None
    roe: Optional[Decimal] = None
    debt_to_equity: Optional[Decimal] = None