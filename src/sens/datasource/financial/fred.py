"""FRED (Federal Reserve Economic Data) API client."""

import asyncio
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional
import httpx
import structlog
from sens.settings import get_settings
from .models import EconomicIndicator, FinancialDataSource

logger = structlog.get_logger(__name__)


class FREDError(Exception):
    """FRED API error."""
    pass


class FREDClient:
    """Client for Federal Reserve Economic Data (FRED) API."""
    
    BASE_URL = "https://api.stlouisfed.org/fred"
    
    # Common economic indicators
    COMMON_INDICATORS = {
        'GDP': 'Gross Domestic Product',
        'GDPC1': 'Real Gross Domestic Product',
        'UNRATE': 'Unemployment Rate',
        'FEDFUNDS': 'Federal Funds Effective Rate',
        'CPIAUCSL': 'Consumer Price Index for All Urban Consumers',
        'CPILFESL': 'Core CPI (Less Food & Energy)',
        'PAYEMS': 'Total Nonfarm Payrolls',
        'HOUST': 'Housing Starts: Total: New Privately Owned',
        'DEXUSEU': 'US / Euro Foreign Exchange Rate',
        'DGS10': '10-Year Treasury Constant Maturity Rate',
        'DGS2': '2-Year Treasury Constant Maturity Rate',
        'AAA': 'Moody\'s Seasoned Aaa Corporate Bond Yield',
        'BAA': 'Moody\'s Seasoned Baa Corporate Bond Yield',
        'VIXCLS': 'CBOE Volatility Index: VIX',
        'UMCSENT': 'University of Michigan Consumer Sentiment',
        'INDPRO': 'Industrial Production Index',
        'NAPM': 'ISM Manufacturing PMI',
        'NAPMEI': 'ISM Manufacturing Employment Index',
        'TOTALSL': 'Total Consumer Credit Outstanding',
        'DRTSCIS': 'Total Credit to Private Non-Financial Sector',
        'MORTGAGE30US': '30-Year Fixed Rate Mortgage Average',
        'RRSFS': 'Real retail and food services sales',
        'RSAFS': 'Advance Real Retail and Food Services Sales',
    }
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize FRED client.
        
        Args:
            api_key: FRED API key. If None, will use settings.
        """
        settings = get_settings()
        self.api_key = api_key or getattr(settings.financial, 'fred_api_key', None)
        if not self.api_key:
            raise ValueError("FRED API key is required. Get one free at: https://fred.stlouisfed.org/docs/api/api_key.html")
        
        self.client = httpx.AsyncClient(timeout=30.0)
        
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def _make_request(self, endpoint: str, params: Dict[str, str]) -> Dict[str, Any]:
        """Make HTTP request to FRED API."""
        params.update({
            'api_key': self.api_key,
            'file_type': 'json'
        })
        
        url = f"{self.BASE_URL}/{endpoint}"
        
        try:
            logger.info("fred_request", endpoint=endpoint, series_id=params.get('series_id'))
            
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Check for API errors
            if 'error_code' in data:
                raise FREDError(f"FRED API Error {data['error_code']}: {data.get('error_message', 'Unknown error')}")
            
            return data
            
        except httpx.HTTPStatusError as e:
            logger.error("fred_http_error", status_code=e.response.status_code, error=str(e))
            raise FREDError(f"HTTP Error: {e.response.status_code}")
        
        except Exception as e:
            logger.error("fred_request_error", error=str(e))
            raise FREDError(f"Request failed: {str(e)}")
    
    async def get_series_info(self, series_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a FRED series."""
        params = {'series_id': series_id}
        
        data = await self._make_request('series', params)
        
        if 'seriess' in data and data['seriess']:
            return data['seriess'][0]
        
        return None
    
    async def get_series_observations(
        self, 
        series_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: Optional[int] = None
    ) -> List[EconomicIndicator]:
        """Get observations (data points) for a FRED series.
        
        Args:
            series_id: FRED series ID (e.g., 'GDP', 'UNRATE')
            start_date: Start date for observations
            end_date: End date for observations  
            limit: Maximum number of observations to return
            
        Returns:
            List of EconomicIndicator objects
        """
        params = {'series_id': series_id}
        
        if start_date:
            params['observation_start'] = start_date.strftime('%Y-%m-%d')
        
        if end_date:
            params['observation_end'] = end_date.strftime('%Y-%m-%d')
            
        if limit:
            params['limit'] = str(limit)
        
        # Get series info for metadata
        series_info = await self.get_series_info(series_id)
        series_name = series_info.get('title', '') if series_info else ''
        unit = series_info.get('units', '') if series_info else ''
        frequency = series_info.get('frequency', '') if series_info else ''
        
        # Get observations
        data = await self._make_request('series/observations', params)
        
        if 'observations' not in data:
            logger.warning("no_fred_observations", series_id=series_id)
            return []
        
        indicators = []
        
        for obs in data['observations']:
            try:
                # Skip observations with missing values
                if obs['value'] == '.':
                    continue
                
                indicator = EconomicIndicator(
                    indicator_code=series_id,
                    indicator_name=series_name,
                    date=datetime.strptime(obs['date'], '%Y-%m-%d').date(),
                    value=Decimal(obs['value']),
                    unit=unit,
                    frequency=frequency,
                    data_source=FinancialDataSource.FRED
                )
                indicators.append(indicator)
                
            except (ValueError, KeyError) as e:
                logger.warning("fred_observation_parse_error", 
                             series_id=series_id, observation=obs, error=str(e))
                continue
        
        logger.info("fred_observations_retrieved", 
                   series_id=series_id, count=len(indicators))
        return indicators
    
    async def get_multiple_series(
        self, 
        series_ids: List[str],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, List[EconomicIndicator]]:
        """Get observations for multiple FRED series."""
        tasks = [
            self.get_series_observations(series_id, start_date, end_date)
            for series_id in series_ids
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        series_data = {}
        for series_id, result in zip(series_ids, results):
            if isinstance(result, Exception):
                logger.error("fred_series_error", series_id=series_id, error=str(result))
                series_data[series_id] = []
            else:
                series_data[series_id] = result
        
        return series_data
    
    async def get_gdp_data(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[EconomicIndicator]:
        """Get GDP data (quarterly)."""
        return await self.get_series_observations('GDP', start_date, end_date)
    
    async def get_unemployment_rate(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[EconomicIndicator]:
        """Get unemployment rate data (monthly)."""
        return await self.get_series_observations('UNRATE', start_date, end_date)
    
    async def get_federal_funds_rate(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[EconomicIndicator]:
        """Get federal funds rate data (monthly)."""
        return await self.get_series_observations('FEDFUNDS', start_date, end_date)
    
    async def get_inflation_data(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[EconomicIndicator]:
        """Get Consumer Price Index data (monthly)."""
        return await self.get_series_observations('CPIAUCSL', start_date, end_date)
    
    async def get_employment_data(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[EconomicIndicator]:
        """Get total nonfarm payrolls data (monthly)."""
        return await self.get_series_observations('PAYEMS', start_date, end_date)
    
    async def get_treasury_rates(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, List[EconomicIndicator]]:
        """Get treasury rates for different maturities."""
        treasury_series = ['DGS1MO', 'DGS3MO', 'DGS6MO', 'DGS1', 'DGS2', 'DGS5', 'DGS10', 'DGS30']
        return await self.get_multiple_series(treasury_series, start_date, end_date)
    
    async def get_market_indicators(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, List[EconomicIndicator]]:
        """Get key market and economic indicators."""
        indicators = [
            'VIXCLS',      # VIX volatility index
            'DGS10',       # 10-year treasury
            'FEDFUNDS',    # Federal funds rate
            'UNRATE',      # Unemployment rate
            'CPIAUCSL',    # CPI
            'UMCSENT',     # Consumer sentiment
            'INDPRO',      # Industrial production
        ]
        return await self.get_multiple_series(indicators, start_date, end_date)
    
    async def search_series(self, search_text: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for FRED series by text."""
        params = {
            'search_text': search_text,
            'limit': str(limit)
        }
        
        data = await self._make_request('series/search', params)
        
        if 'seriess' not in data:
            return []
        
        return data['seriess']
    
    async def get_categories(self, category_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get FRED categories."""
        params = {}
        if category_id:
            params['category_id'] = str(category_id)
        
        data = await self._make_request('category', params)
        
        if 'categories' not in data:
            return []
        
        return data['categories']
    
    def get_common_indicators_info(self) -> Dict[str, str]:
        """Get information about commonly used indicators."""
        return self.COMMON_INDICATORS.copy()
    
    async def get_latest_values(
        self, 
        series_ids: List[str]
    ) -> Dict[str, Optional[EconomicIndicator]]:
        """Get the latest value for each series."""
        results = {}
        
        for series_id in series_ids:
            try:
                # Get last observation
                observations = await self.get_series_observations(
                    series_id, 
                    limit=1
                )
                
                if observations:
                    results[series_id] = observations[0]
                else:
                    results[series_id] = None
                    
            except Exception as e:
                logger.error("fred_latest_value_error", series_id=series_id, error=str(e))
                results[series_id] = None
        
        return results