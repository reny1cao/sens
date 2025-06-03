"""Financial data loading pipeline with COPY-based approach."""

import asyncio
import csv
import tempfile
import os
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
import psycopg2
from psycopg2.extras import DictCursor
import structlog

from sens.settings import get_settings
from .alpha_vantage import AlphaVantageClient, RateLimitError
from .fred import FREDClient
from .models import (
    StockPrice, 
    EconomicIndicator, 
    Security, 
    FinancialStatement,
    DataLoadRequest,
    DataLoadResponse,
    FinancialDataSource
)

logger = structlog.get_logger(__name__)


class FinancialDataLoader:
    """High-performance financial data loader using COPY approach."""
    
    def __init__(self, db_url: Optional[str] = None):
        """Initialize data loader.
        
        Args:
            db_url: PostgreSQL connection URL. If None, uses settings.
        """
        settings = get_settings()
        self.db_url = db_url or settings.database_url
        self.alpha_vantage = None
        self.fred = None
        
    async def __aenter__(self):
        """Async context manager entry."""
        # Initialize API clients
        try:
            self.alpha_vantage = AlphaVantageClient()
            await self.alpha_vantage.__aenter__()
        except ValueError as e:
            logger.warning("alpha_vantage_not_configured", error=str(e))
        
        try:
            self.fred = FREDClient()
            await self.fred.__aenter__()
        except ValueError as e:
            logger.warning("fred_not_configured", error=str(e))
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.alpha_vantage:
            await self.alpha_vantage.__aexit__(exc_type, exc_val, exc_tb)
        
        if self.fred:
            await self.fred.__aexit__(exc_type, exc_val, exc_tb)
    
    def _get_connection(self):
        """Get database connection."""
        return psycopg2.connect(self.db_url)
    
    async def load_securities_info(self, symbols: List[str]) -> int:
        """Load securities information for symbols."""
        if not self.alpha_vantage:
            raise ValueError("Alpha Vantage client not configured")
        
        loaded_count = 0
        conn = self._get_connection()
        
        try:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                for symbol in symbols:
                    try:
                        # Get company overview
                        security = await self.alpha_vantage.get_company_overview(symbol)
                        
                        if security:
                            # Upsert security
                            cur.execute("""
                                INSERT INTO securities (
                                    symbol, company_name, sector, industry, 
                                    market_cap, exchange, country, currency
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (symbol) DO UPDATE SET
                                    company_name = EXCLUDED.company_name,
                                    sector = EXCLUDED.sector,
                                    industry = EXCLUDED.industry,
                                    market_cap = EXCLUDED.market_cap,
                                    exchange = EXCLUDED.exchange,
                                    country = EXCLUDED.country,
                                    currency = EXCLUDED.currency,
                                    updated_at = NOW()
                            """, (
                                security.symbol,
                                security.company_name,
                                security.sector,
                                security.industry,
                                security.market_cap,
                                security.exchange,
                                security.country,
                                security.currency
                            ))
                            loaded_count += 1
                        
                        # Rate limiting
                        await asyncio.sleep(12)  # 5 calls per minute
                        
                    except Exception as e:
                        logger.error("security_load_error", symbol=symbol, error=str(e))
                        continue
                
                conn.commit()
                
        finally:
            conn.close()
        
        logger.info("securities_loaded", count=loaded_count, total_symbols=len(symbols))
        return loaded_count
    
    async def load_daily_prices_batch(
        self, 
        symbols: List[str],
        use_csv: bool = True,
        max_concurrent: int = 5
    ) -> DataLoadResponse:
        """Load daily prices for multiple symbols using efficient batch processing."""
        if not self.alpha_vantage:
            raise ValueError("Alpha Vantage client not configured")
        
        start_time = datetime.now()
        total_records = 0
        errors = []
        processed_symbols = []
        
        try:
            # Get data from Alpha Vantage
            if use_csv:
                # Use CSV method for better performance
                batch_data = await self.alpha_vantage.get_multiple_symbols_batch(
                    symbols, max_concurrent
                )
            else:
                # Use JSON method
                batch_data = {}
                for symbol in symbols:
                    try:
                        prices = await self.alpha_vantage.get_daily_prices(symbol)
                        batch_data[symbol] = prices
                        await asyncio.sleep(12)  # Rate limiting
                    except RateLimitError:
                        logger.warning("rate_limit_hit", symbol=symbol)
                        await asyncio.sleep(60)  # Wait longer on rate limit
                        continue
                    except Exception as e:
                        logger.error("symbol_fetch_error", symbol=symbol, error=str(e))
                        errors.append(f"{symbol}: {str(e)}")
                        continue
            
            # Load data using COPY approach
            for symbol, prices in batch_data.items():
                if not prices:
                    continue
                
                try:
                    records_loaded = await self._copy_daily_prices_to_db(symbol, prices)
                    total_records += records_loaded
                    processed_symbols.append(symbol)
                    
                except Exception as e:
                    logger.error("db_load_error", symbol=symbol, error=str(e))
                    errors.append(f"{symbol} DB load: {str(e)}")
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return DataLoadResponse(
                success=len(errors) == 0,
                message=f"Loaded {total_records} price records for {len(processed_symbols)} symbols",
                symbols_processed=processed_symbols,
                records_loaded=total_records,
                errors=errors,
                execution_time_seconds=execution_time
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error("batch_load_error", error=str(e))
            
            return DataLoadResponse(
                success=False,
                message=f"Batch load failed: {str(e)}",
                symbols_processed=processed_symbols,
                records_loaded=total_records,
                errors=errors + [str(e)],
                execution_time_seconds=execution_time
            )
    
    async def _copy_daily_prices_to_db(self, symbol: str, prices: List[StockPrice]) -> int:
        """Load daily prices using COPY for maximum performance."""
        if not prices:
            return 0
        
        conn = self._get_connection()
        
        try:
            # Create temporary CSV file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
                csv_writer = csv.writer(temp_file)
                
                # Write header
                csv_writer.writerow([
                    'symbol', 'trade_date', 'open_price', 'high_price', 
                    'low_price', 'close_price', 'adj_close', 'volume', 'data_source'
                ])
                
                # Write data - filter to dates that have partitions (2023-2026)
                for price in prices:
                    # Only include data from 2023 onwards
                    if price.trade_date.year >= 2023:
                        csv_writer.writerow([
                            price.symbol,
                            price.trade_date.strftime('%Y-%m-%d'),
                            str(price.open_price) if price.open_price else '',
                            str(price.high_price) if price.high_price else '',
                            str(price.low_price) if price.low_price else '',
                            str(price.close_price) if price.close_price else '',
                            str(price.adj_close) if price.adj_close else '',
                            str(price.volume) if price.volume else '',
                            price.data_source.value
                        ])
                
                temp_file_path = temp_file.name
            
            # COPY to staging table
            with conn.cursor() as cur:
                with open(temp_file_path, 'r') as f:
                    cur.copy_expert(
                        "COPY staging_daily_prices (symbol, trade_date, open_price, high_price, low_price, close_price, adj_close, volume, data_source) FROM STDIN CSV HEADER",
                        f
                    )
                
                # Execute upsert function
                cur.execute("SELECT upsert_daily_prices()")
                records_affected = cur.fetchone()[0]
                
                conn.commit()
            
            # Clean up temp file
            os.unlink(temp_file_path)
            
            logger.info("daily_prices_copied", symbol=symbol, records=records_affected)
            return records_affected
            
        except Exception as e:
            conn.rollback()
            logger.error("copy_daily_prices_error", symbol=symbol, error=str(e))
            raise
        finally:
            conn.close()
    
    async def load_economic_indicators(
        self,
        indicator_codes: List[str],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> DataLoadResponse:
        """Load economic indicators from FRED."""
        if not self.fred:
            raise ValueError("FRED client not configured")
        
        start_time = datetime.now()
        total_records = 0
        errors = []
        processed_indicators = []
        
        try:
            # Get data from FRED
            indicators_data = await self.fred.get_multiple_series(
                indicator_codes, start_date, end_date
            )
            
            # Load to database
            conn = self._get_connection()
            
            try:
                with conn.cursor() as cur:
                    for indicator_code, indicators in indicators_data.items():
                        if not indicators:
                            continue
                        
                        try:
                            # Batch insert with conflict resolution
                            for indicator in indicators:
                                cur.execute("""
                                    INSERT INTO economic_indicators (
                                        indicator_code, indicator_name, date, value, 
                                        unit, frequency, data_source
                                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                                    ON CONFLICT (indicator_code, date) DO UPDATE SET
                                        value = EXCLUDED.value,
                                        indicator_name = EXCLUDED.indicator_name,
                                        unit = EXCLUDED.unit,
                                        frequency = EXCLUDED.frequency
                                """, (
                                    indicator.indicator_code,
                                    indicator.indicator_name,
                                    indicator.date,
                                    indicator.value,
                                    indicator.unit,
                                    indicator.frequency,
                                    indicator.data_source.value
                                ))
                            
                            total_records += len(indicators)
                            processed_indicators.append(indicator_code)
                            
                        except Exception as e:
                            logger.error("indicator_load_error", 
                                       indicator_code=indicator_code, error=str(e))
                            errors.append(f"{indicator_code}: {str(e)}")
                    
                    conn.commit()
                    
            finally:
                conn.close()
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return DataLoadResponse(
                success=len(errors) == 0,
                message=f"Loaded {total_records} economic indicator records",
                symbols_processed=processed_indicators,
                records_loaded=total_records,
                errors=errors,
                execution_time_seconds=execution_time
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error("economic_indicators_load_error", error=str(e))
            
            return DataLoadResponse(
                success=False,
                message=f"Economic indicators load failed: {str(e)}",
                symbols_processed=processed_indicators,
                records_loaded=total_records,
                errors=errors + [str(e)],
                execution_time_seconds=execution_time
            )
    
    async def load_financial_statements(
        self, 
        symbols: List[str]
    ) -> DataLoadResponse:
        """Load financial statements for symbols."""
        if not self.alpha_vantage:
            raise ValueError("Alpha Vantage client not configured")
        
        start_time = datetime.now()
        total_records = 0
        errors = []
        processed_symbols = []
        
        conn = self._get_connection()
        
        try:
            with conn.cursor() as cur:
                for symbol in symbols:
                    try:
                        # Get income statement and balance sheet
                        income_statements = await self.alpha_vantage.get_income_statement(symbol)
                        balance_sheets = await self.alpha_vantage.get_balance_sheet(symbol)
                        
                        # Combine data by fiscal year
                        combined_statements = self._combine_financial_statements(
                            income_statements, balance_sheets
                        )
                        
                        # Insert/update statements
                        for statement in combined_statements:
                            cur.execute("""
                                INSERT INTO financial_statements (
                                    symbol, fiscal_year, period_end_date,
                                    revenue, cost_of_revenue, gross_profit,
                                    operating_expenses, operating_income, net_income,
                                    total_assets, current_assets, total_liabilities,
                                    current_liabilities, shareholders_equity, total_debt,
                                    cash_and_equivalents, data_source
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (symbol, fiscal_year, fiscal_quarter) DO UPDATE SET
                                    period_end_date = EXCLUDED.period_end_date,
                                    revenue = EXCLUDED.revenue,
                                    cost_of_revenue = EXCLUDED.cost_of_revenue,
                                    gross_profit = EXCLUDED.gross_profit,
                                    operating_expenses = EXCLUDED.operating_expenses,
                                    operating_income = EXCLUDED.operating_income,
                                    net_income = EXCLUDED.net_income,
                                    total_assets = EXCLUDED.total_assets,
                                    current_assets = EXCLUDED.current_assets,
                                    total_liabilities = EXCLUDED.total_liabilities,
                                    current_liabilities = EXCLUDED.current_liabilities,
                                    shareholders_equity = EXCLUDED.shareholders_equity,
                                    total_debt = EXCLUDED.total_debt,
                                    cash_and_equivalents = EXCLUDED.cash_and_equivalents,
                                    data_source = EXCLUDED.data_source
                            """, (
                                statement.symbol,
                                statement.fiscal_year,
                                statement.period_end_date,
                                statement.revenue,
                                statement.cost_of_revenue,
                                statement.gross_profit,
                                statement.operating_expenses,
                                statement.operating_income,
                                statement.net_income,
                                statement.total_assets,
                                statement.current_assets,
                                statement.total_liabilities,
                                statement.current_liabilities,
                                statement.shareholders_equity,
                                statement.total_debt,
                                statement.cash_and_equivalents,
                                statement.data_source.value
                            ))
                        
                        total_records += len(combined_statements)
                        processed_symbols.append(symbol)
                        
                        # Rate limiting
                        await asyncio.sleep(24)  # 2 API calls per symbol
                        
                    except Exception as e:
                        logger.error("financial_statements_error", symbol=symbol, error=str(e))
                        errors.append(f"{symbol}: {str(e)}")
                        continue
                
                conn.commit()
                
        finally:
            conn.close()
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        return DataLoadResponse(
            success=len(errors) == 0,
            message=f"Loaded {total_records} financial statement records",
            symbols_processed=processed_symbols,
            records_loaded=total_records,
            errors=errors,
            execution_time_seconds=execution_time
        )
    
    def _combine_financial_statements(
        self, 
        income_statements: List[FinancialStatement],
        balance_sheets: List[FinancialStatement]
    ) -> List[FinancialStatement]:
        """Combine income statement and balance sheet data by fiscal year."""
        combined = {}
        
        # Index income statements by fiscal year
        for stmt in income_statements:
            key = (stmt.symbol, stmt.fiscal_year)
            combined[key] = stmt
        
        # Merge balance sheet data
        for stmt in balance_sheets:
            key = (stmt.symbol, stmt.fiscal_year)
            if key in combined:
                # Update existing statement with balance sheet data
                existing = combined[key]
                existing.total_assets = stmt.total_assets
                existing.current_assets = stmt.current_assets
                existing.total_liabilities = stmt.total_liabilities
                existing.current_liabilities = stmt.current_liabilities
                existing.shareholders_equity = stmt.shareholders_equity
                existing.total_debt = stmt.total_debt
                existing.cash_and_equivalents = stmt.cash_and_equivalents
            else:
                # Create new statement with only balance sheet data
                combined[key] = stmt
        
        return list(combined.values())
    
    async def update_market_data_daily(self) -> DataLoadResponse:
        """Daily update of market data for configured symbols."""
        # Get active symbols from database
        conn = self._get_connection()
        
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT symbol FROM securities WHERE is_active = true ORDER BY market_cap DESC LIMIT 50")
                symbols = [row[0] for row in cur.fetchall()]
        finally:
            conn.close()
        
        if not symbols:
            return DataLoadResponse(
                success=False,
                message="No active symbols found in database",
                symbols_processed=[],
                records_loaded=0,
                errors=["No active symbols found"],
                execution_time_seconds=0.0
            )
        
        # Load recent data (last 100 days)
        return await self.load_daily_prices_batch(symbols, use_csv=True)
    
    async def get_data_status(self) -> Dict[str, Any]:
        """Get status of financial data in the database."""
        conn = self._get_connection()
        
        try:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                # Securities count
                cur.execute("SELECT COUNT(*) as count FROM securities WHERE is_active = true")
                securities_count = cur.fetchone()['count']
                
                # Daily prices stats
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_records,
                        COUNT(DISTINCT symbol) as symbols_with_data,
                        MIN(trade_date) as earliest_date,
                        MAX(trade_date) as latest_date
                    FROM daily_prices
                """)
                prices_stats = dict(cur.fetchone())
                
                # Economic indicators stats
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_records,
                        COUNT(DISTINCT indicator_code) as unique_indicators,
                        MIN(date) as earliest_date,
                        MAX(date) as latest_date
                    FROM economic_indicators
                """)
                indicators_stats = dict(cur.fetchone())
                
                # Financial statements stats
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_records,
                        COUNT(DISTINCT symbol) as symbols_with_data,
                        MIN(fiscal_year) as earliest_year,
                        MAX(fiscal_year) as latest_year
                    FROM financial_statements
                """)
                statements_stats = dict(cur.fetchone())
                
                return {
                    'securities': securities_count,
                    'daily_prices': prices_stats,
                    'economic_indicators': indicators_stats,
                    'financial_statements': statements_stats,
                    'last_updated': datetime.now().isoformat()
                }
                
        finally:
            conn.close()