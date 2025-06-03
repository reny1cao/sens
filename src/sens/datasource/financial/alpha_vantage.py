"""Alpha Vantage API client for financial data."""

import asyncio
import csv
import io
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional
import httpx
import structlog
from sens.settings import get_settings
from .models import (
    StockPrice, 
    FinancialStatement, 
    Security, 
    FinancialDataSource,
    DataLoadResponse
)

logger = structlog.get_logger(__name__)


class AlphaVantageError(Exception):
    """Alpha Vantage API error."""
    pass


class RateLimitError(AlphaVantageError):
    """Rate limit exceeded error."""
    pass


class AlphaVantageClient:
    """Client for Alpha Vantage financial data API."""
    
    BASE_URL = "https://www.alphavantage.co/query"
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Alpha Vantage client.
        
        Args:
            api_key: Alpha Vantage API key. If None, will use settings.
        """
        settings = get_settings()
        self.api_key = api_key or getattr(settings.financial, 'alpha_vantage_api_key', None)
        if not self.api_key:
            raise ValueError("Alpha Vantage API key is required")
        
        self.client = httpx.AsyncClient(timeout=30.0)
        self.rate_limit_delay = 12  # seconds (5 calls per minute for free tier)
        self.last_request_time = None
        
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def _make_request(self, params: Dict[str, str]) -> Dict[str, Any]:
        """Make HTTP request to Alpha Vantage API with rate limiting."""
        # Enforce rate limiting
        if self.last_request_time:
            elapsed = (datetime.now() - self.last_request_time).total_seconds()
            if elapsed < self.rate_limit_delay:
                wait_time = self.rate_limit_delay - elapsed
                logger.info("rate_limit_wait", wait_seconds=wait_time)
                await asyncio.sleep(wait_time)
        
        params['apikey'] = self.api_key
        
        try:
            logger.info("alpha_vantage_request", function=params.get('function'), symbol=params.get('symbol'))
            self.last_request_time = datetime.now()
            
            response = await self.client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            
            # Handle CSV response
            if params.get('datatype') == 'csv':
                return {'csv_data': response.text}
            
            data = response.json()
            
            # Check for API errors
            if 'Error Message' in data:
                raise AlphaVantageError(f"API Error: {data['Error Message']}")
            
            if 'Note' in data and 'API call frequency' in data['Note']:
                raise RateLimitError("Rate limit exceeded")
            
            if 'Information' in data:
                info_msg = data['Information']
                logger.warning("alpha_vantage_info_response", info=info_msg)
                
                # Check if it's about API call frequency
                if 'API call frequency' in info_msg or 'calls per minute' in info_msg:
                    # This is likely a rate limit message, wait longer
                    logger.warning("rate_limit_detected", message="Waiting 60s due to rate limit")
                    await asyncio.sleep(60)
                    # Retry once after waiting
                    params['retry'] = 'true'
                    if params.get('retry') != 'true':
                        return await self._make_request(params)
                
                # Return empty data for other Information messages
                return {}
            
            return data
            
        except httpx.HTTPStatusError as e:
            logger.error("alpha_vantage_http_error", status_code=e.response.status_code, error=str(e))
            raise AlphaVantageError(f"HTTP Error: {e.response.status_code}")
        
        except Exception as e:
            logger.error("alpha_vantage_request_error", error=str(e))
            raise AlphaVantageError(f"Request failed: {str(e)}")
    
    async def get_daily_prices(
        self, 
        symbol: str, 
        outputsize: str = "full"
    ) -> List[StockPrice]:
        """Get daily stock prices for a symbol.
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            outputsize: 'compact' (last 100 days) or 'full' (20+ years)
            
        Returns:
            List of StockPrice objects
        """
        params = {
            'function': 'TIME_SERIES_DAILY',  # Use non-adjusted for free tier
            'symbol': symbol,
            'outputsize': outputsize,
            'datatype': 'json'
        }
        
        data = await self._make_request(params)
        
        if 'Time Series (Daily)' not in data:
            logger.warning("no_daily_data", symbol=symbol, available_keys=list(data.keys()))
            return []
        
        prices = []
        time_series = data['Time Series (Daily)']
        
        for date_str, price_data in time_series.items():
            try:
                price = StockPrice(
                    symbol=symbol,
                    trade_date=datetime.strptime(date_str, '%Y-%m-%d').date(),
                    open_price=Decimal(price_data['1. open']),
                    high_price=Decimal(price_data['2. high']),
                    low_price=Decimal(price_data['3. low']),
                    close_price=Decimal(price_data['4. close']),
                    adj_close=Decimal(price_data.get('5. adjusted close', price_data['4. close'])),  # Use close if no adjusted
                    volume=int(price_data.get('6. volume', price_data.get('5. volume', 0))),  # Volume key changes
                    data_source=FinancialDataSource.ALPHA_VANTAGE
                )
                prices.append(price)
                
            except (ValueError, KeyError) as e:
                logger.warning("price_parse_error", symbol=symbol, date=date_str, error=str(e))
                continue
        
        logger.info("daily_prices_retrieved", symbol=symbol, count=len(prices))
        return prices
    
    async def get_daily_prices_csv(self, symbol: str) -> List[StockPrice]:
        """Get daily prices using CSV format (faster for large datasets)."""
        params = {
            'function': 'TIME_SERIES_DAILY',  # Use non-adjusted for free tier
            'symbol': symbol,
            'outputsize': 'full',
            'datatype': 'csv'
        }
        
        data = await self._make_request(params)
        
        if 'csv_data' not in data:
            return []
        
        prices = []
        csv_reader = csv.DictReader(io.StringIO(data['csv_data']))
        
        for row in csv_reader:
            try:
                price = StockPrice(
                    symbol=symbol,
                    trade_date=datetime.strptime(row['timestamp'], '%Y-%m-%d').date(),
                    open_price=Decimal(row['open']),
                    high_price=Decimal(row['high']),
                    low_price=Decimal(row['low']),
                    close_price=Decimal(row['close']),
                    adj_close=Decimal(row.get('adjusted_close', row['close'])),  # Use close if no adjusted
                    volume=int(row['volume']),
                    data_source=FinancialDataSource.ALPHA_VANTAGE
                )
                prices.append(price)
                
            except (ValueError, KeyError) as e:
                logger.warning("csv_price_parse_error", symbol=symbol, row=row, error=str(e))
                continue
        
        logger.info("csv_daily_prices_retrieved", symbol=symbol, count=len(prices))
        return prices
    
    async def get_company_overview(self, symbol: str) -> Optional[Security]:
        """Get company overview and fundamental data."""
        params = {
            'function': 'OVERVIEW',
            'symbol': symbol
        }
        
        data = await self._make_request(params)
        
        if not data or 'Symbol' not in data:
            logger.warning("no_overview_data", symbol=symbol)
            return None
        
        try:
            security = Security(
                symbol=data['Symbol'],
                company_name=data.get('Name', ''),
                sector=data.get('Sector'),
                industry=data.get('Industry'),
                market_cap=int(data['MarketCapitalization']) if data.get('MarketCapitalization', '').isdigit() else None,
                exchange=data.get('Exchange'),
                country=data.get('Country', 'USA'),
                currency=data.get('Currency', 'USD')
            )
            
            logger.info("company_overview_retrieved", symbol=symbol, name=security.company_name)
            return security
            
        except (ValueError, KeyError) as e:
            logger.error("overview_parse_error", symbol=symbol, error=str(e))
            return None
    
    async def get_income_statement(self, symbol: str) -> List[FinancialStatement]:
        """Get annual income statement data."""
        params = {
            'function': 'INCOME_STATEMENT',
            'symbol': symbol
        }
        
        data = await self._make_request(params)
        
        if 'annualReports' not in data:
            logger.warning("no_income_statement_data", symbol=symbol)
            return []
        
        statements = []
        
        for report in data['annualReports']:
            try:
                # Parse fiscal year from fiscalDateEnding
                fiscal_date = datetime.strptime(report['fiscalDateEnding'], '%Y-%m-%d').date()
                
                statement = FinancialStatement(
                    symbol=symbol,
                    fiscal_year=fiscal_date.year,
                    period_end_date=fiscal_date,
                    revenue=self._parse_int(report.get('totalRevenue')),
                    cost_of_revenue=self._parse_int(report.get('costOfRevenue')),
                    gross_profit=self._parse_int(report.get('grossProfit')),
                    operating_expenses=self._parse_int(report.get('totalOperatingExpenses')),
                    operating_income=self._parse_int(report.get('operatingIncome')),
                    net_income=self._parse_int(report.get('netIncome')),
                    data_source=FinancialDataSource.ALPHA_VANTAGE
                )
                statements.append(statement)
                
            except (ValueError, KeyError) as e:
                logger.warning("income_statement_parse_error", symbol=symbol, error=str(e))
                continue
        
        logger.info("income_statements_retrieved", symbol=symbol, count=len(statements))
        return statements
    
    async def get_balance_sheet(self, symbol: str) -> List[FinancialStatement]:
        """Get annual balance sheet data."""
        params = {
            'function': 'BALANCE_SHEET',
            'symbol': symbol
        }
        
        data = await self._make_request(params)
        
        if 'annualReports' not in data:
            logger.warning("no_balance_sheet_data", symbol=symbol)
            return []
        
        statements = []
        
        for report in data['annualReports']:
            try:
                fiscal_date = datetime.strptime(report['fiscalDateEnding'], '%Y-%m-%d').date()
                
                statement = FinancialStatement(
                    symbol=symbol,
                    fiscal_year=fiscal_date.year,
                    period_end_date=fiscal_date,
                    total_assets=self._parse_int(report.get('totalAssets')),
                    current_assets=self._parse_int(report.get('totalCurrentAssets')),
                    total_liabilities=self._parse_int(report.get('totalLiabilities')),
                    current_liabilities=self._parse_int(report.get('totalCurrentLiabilities')),
                    shareholders_equity=self._parse_int(report.get('totalShareholderEquity')),
                    total_debt=self._parse_int(report.get('longTermDebt')),
                    cash_and_equivalents=self._parse_int(report.get('cashAndCashEquivalentsAtCarryingValue')),
                    data_source=FinancialDataSource.ALPHA_VANTAGE
                )
                statements.append(statement)
                
            except (ValueError, KeyError) as e:
                logger.warning("balance_sheet_parse_error", symbol=symbol, error=str(e))
                continue
        
        logger.info("balance_sheets_retrieved", symbol=symbol, count=len(statements))
        return statements
    
    async def get_technical_indicators(
        self, 
        symbol: str, 
        indicator: str = "RSI",
        interval: str = "daily",
        time_period: int = 14
    ) -> Dict[date, Decimal]:
        """Get technical indicators like RSI, SMA, etc."""
        params = {
            'function': indicator,
            'symbol': symbol,
            'interval': interval,
            'time_period': str(time_period),
            'series_type': 'close'
        }
        
        data = await self._make_request(params)
        
        # Find the technical analysis data key
        tech_key = None
        for key in data.keys():
            if 'Technical Analysis' in key:
                tech_key = key
                break
        
        if not tech_key:
            logger.warning("no_technical_data", symbol=symbol, indicator=indicator)
            return {}
        
        indicators = {}
        tech_data = data[tech_key]
        
        for date_str, values in tech_data.items():
            try:
                trade_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                # Most indicators have a single value with the indicator name as key
                value_key = list(values.keys())[0]
                indicators[trade_date] = Decimal(values[value_key])
                
            except (ValueError, KeyError, IndexError) as e:
                logger.warning("technical_parse_error", symbol=symbol, date=date_str, error=str(e))
                continue
        
        logger.info("technical_indicators_retrieved", 
                   symbol=symbol, indicator=indicator, count=len(indicators))
        return indicators
    
    async def get_multiple_symbols_batch(
        self, 
        symbols: List[str],
        max_concurrent: int = 5
    ) -> Dict[str, List[StockPrice]]:
        """Get daily prices for multiple symbols with rate limiting."""
        results = {}
        
        # Process in batches to respect rate limits
        for i in range(0, len(symbols), max_concurrent):
            batch = symbols[i:i + max_concurrent]
            
            # Process batch concurrently
            tasks = [self.get_daily_prices_csv(symbol) for symbol in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Collect results
            for symbol, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.error("batch_symbol_error", symbol=symbol, error=str(result))
                    results[symbol] = []
                else:
                    results[symbol] = result
            
            # Rate limiting delay between batches
            if i + max_concurrent < len(symbols):
                await asyncio.sleep(self.rate_limit_delay)
        
        return results
    
    def _parse_int(self, value: Optional[str]) -> Optional[int]:
        """Parse string to int, handling None and 'None' values."""
        if not value or value == 'None':
            return None
        try:
            return int(value)
        except ValueError:
            return None
    
    def _parse_decimal(self, value: Optional[str]) -> Optional[Decimal]:
        """Parse string to Decimal, handling None and 'None' values."""
        if not value or value == 'None':
            return None
        try:
            return Decimal(value)
        except (ValueError, TypeError):
            return None