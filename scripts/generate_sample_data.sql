-- Generate comprehensive sample financial data for SENS
-- No API calls required - perfect for development and testing

-- Clear existing sample data (optional)
-- DELETE FROM daily_prices WHERE data_source = 'sample_generator';
-- DELETE FROM economic_indicators WHERE data_source = 'sample_generator';

-- Insert more companies
INSERT INTO securities (symbol, company_name, sector, industry, market_cap, country)
VALUES
    -- Technology
    ('NVDA', 'NVIDIA Corporation', 'Technology', 'Semiconductors', 2800000000000, 'US'),
    ('META', 'Meta Platforms Inc.', 'Technology', 'Internet Services', 1200000000000, 'US'),
    ('TSLA', 'Tesla Inc.', 'Technology', 'Electric Vehicles', 800000000000, 'US'),
    ('ADBE', 'Adobe Inc.', 'Technology', 'Software', 250000000000, 'US'),

    -- Finance
    ('JPM', 'JPMorgan Chase & Co.', 'Finance', 'Banking', 500000000000, 'US'),
    ('BAC', 'Bank of America', 'Finance', 'Banking', 300000000000, 'US'),
    ('GS', 'Goldman Sachs', 'Finance', 'Investment Banking', 150000000000, 'US'),

    -- Healthcare
    ('JNJ', 'Johnson & Johnson', 'Healthcare', 'Pharmaceuticals', 400000000000, 'US'),
    ('UNH', 'UnitedHealth Group', 'Healthcare', 'Health Insurance', 500000000000, 'US'),
    ('PFE', 'Pfizer Inc.', 'Healthcare', 'Pharmaceuticals', 250000000000, 'US'),

    -- Consumer
    ('AMZN', 'Amazon.com Inc.', 'Consumer', 'E-Commerce', 1700000000000, 'US'),
    ('WMT', 'Walmart Inc.', 'Consumer', 'Retail', 450000000000, 'US'),
    ('HD', 'The Home Depot', 'Consumer', 'Retail', 350000000000, 'US'),

    -- Energy
    ('XOM', 'Exxon Mobil', 'Energy', 'Oil & Gas', 450000000000, 'US'),
    ('CVX', 'Chevron Corporation', 'Energy', 'Oil & Gas', 350000000000, 'US'),

    -- ETFs
    ('SPY', 'SPDR S&P 500 ETF', 'ETF', 'Index Fund', 500000000000, 'US'),
    ('QQQ', 'Invesco QQQ Trust', 'ETF', 'Index Fund', 200000000000, 'US'),
    ('VTI', 'Vanguard Total Stock Market ETF', 'ETF', 'Index Fund', 300000000000, 'US')
ON CONFLICT (symbol) DO UPDATE SET
    sector = EXCLUDED.sector,
    industry = EXCLUDED.industry,
    market_cap = EXCLUDED.market_cap;

-- Generate price data for all securities
-- This creates 365 days of price history with realistic patterns
INSERT INTO daily_prices (symbol, trade_date, open_price, high_price, low_price, close_price, adj_close, volume, data_source)
SELECT
    s.symbol,
    dates.trade_date,
    -- Generate prices based on symbol characteristics
    CASE
        WHEN s.symbol = 'AAPL' THEN 170 + (random() * 30)
        WHEN s.symbol = 'MSFT' THEN 350 + (random() * 50)
        WHEN s.symbol = 'GOOGL' THEN 130 + (random() * 30)
        WHEN s.symbol = 'AMZN' THEN 150 + (random() * 30)
        WHEN s.symbol = 'NVDA' THEN 500 + (random() * 100)
        WHEN s.symbol = 'META' THEN 350 + (random() * 50)
        WHEN s.symbol = 'TSLA' THEN 200 + (random() * 80)
        WHEN s.symbol = 'JPM' THEN 150 + (random() * 30)
        WHEN s.symbol = 'JNJ' THEN 155 + (random() * 15)
        WHEN s.symbol = 'WMT' THEN 150 + (random() * 10)
        WHEN s.symbol = 'SPY' THEN 450 + (random() * 50)
        WHEN s.symbol = 'QQQ' THEN 380 + (random() * 40)
        ELSE 100 + (random() * 50)
    END as open_price,
    -- High is open + random gain
    CASE
        WHEN s.symbol = 'AAPL' THEN 170 + (random() * 30) + (random() * 5)
        WHEN s.symbol = 'MSFT' THEN 350 + (random() * 50) + (random() * 10)
        WHEN s.symbol = 'GOOGL' THEN 130 + (random() * 30) + (random() * 5)
        WHEN s.symbol = 'AMZN' THEN 150 + (random() * 30) + (random() * 5)
        WHEN s.symbol = 'NVDA' THEN 500 + (random() * 100) + (random() * 20)
        WHEN s.symbol = 'META' THEN 350 + (random() * 50) + (random() * 10)
        WHEN s.symbol = 'TSLA' THEN 200 + (random() * 80) + (random() * 15)
        WHEN s.symbol = 'JPM' THEN 150 + (random() * 30) + (random() * 5)
        WHEN s.symbol = 'JNJ' THEN 155 + (random() * 15) + (random() * 3)
        WHEN s.symbol = 'WMT' THEN 150 + (random() * 10) + (random() * 2)
        WHEN s.symbol = 'SPY' THEN 450 + (random() * 50) + (random() * 10)
        WHEN s.symbol = 'QQQ' THEN 380 + (random() * 40) + (random() * 8)
        ELSE 100 + (random() * 50) + (random() * 5)
    END as high_price,
    -- Low is open - random loss
    CASE
        WHEN s.symbol = 'AAPL' THEN 170 + (random() * 30) - (random() * 5)
        WHEN s.symbol = 'MSFT' THEN 350 + (random() * 50) - (random() * 10)
        WHEN s.symbol = 'GOOGL' THEN 130 + (random() * 30) - (random() * 5)
        WHEN s.symbol = 'AMZN' THEN 150 + (random() * 30) - (random() * 5)
        WHEN s.symbol = 'NVDA' THEN 500 + (random() * 100) - (random() * 20)
        WHEN s.symbol = 'META' THEN 350 + (random() * 50) - (random() * 10)
        WHEN s.symbol = 'TSLA' THEN 200 + (random() * 80) - (random() * 15)
        WHEN s.symbol = 'JPM' THEN 150 + (random() * 30) - (random() * 5)
        WHEN s.symbol = 'JNJ' THEN 155 + (random() * 15) - (random() * 3)
        WHEN s.symbol = 'WMT' THEN 150 + (random() * 10) - (random() * 2)
        WHEN s.symbol = 'SPY' THEN 450 + (random() * 50) - (random() * 10)
        WHEN s.symbol = 'QQQ' THEN 380 + (random() * 40) - (random() * 8)
        ELSE 100 + (random() * 50) - (random() * 5)
    END as low_price,
    -- Close is between low and high
    CASE
        WHEN s.symbol = 'AAPL' THEN 170 + (random() * 30) + (random() - 0.5) * 3
        WHEN s.symbol = 'MSFT' THEN 350 + (random() * 50) + (random() - 0.5) * 5
        WHEN s.symbol = 'GOOGL' THEN 130 + (random() * 30) + (random() - 0.5) * 3
        WHEN s.symbol = 'AMZN' THEN 150 + (random() * 30) + (random() - 0.5) * 3
        WHEN s.symbol = 'NVDA' THEN 500 + (random() * 100) + (random() - 0.5) * 10
        WHEN s.symbol = 'META' THEN 350 + (random() * 50) + (random() - 0.5) * 5
        WHEN s.symbol = 'TSLA' THEN 200 + (random() * 80) + (random() - 0.5) * 8
        WHEN s.symbol = 'JPM' THEN 150 + (random() * 30) + (random() - 0.5) * 3
        WHEN s.symbol = 'JNJ' THEN 155 + (random() * 15) + (random() - 0.5) * 2
        WHEN s.symbol = 'WMT' THEN 150 + (random() * 10) + (random() - 0.5) * 1
        WHEN s.symbol = 'SPY' THEN 450 + (random() * 50) + (random() - 0.5) * 5
        WHEN s.symbol = 'QQQ' THEN 380 + (random() * 40) + (random() - 0.5) * 4
        ELSE 100 + (random() * 50) + (random() - 0.5) * 3
    END as close_price,
    -- Adj close same as close for simplicity
    CASE
        WHEN s.symbol = 'AAPL' THEN 170 + (random() * 30) + (random() - 0.5) * 3
        WHEN s.symbol = 'MSFT' THEN 350 + (random() * 50) + (random() - 0.5) * 5
        WHEN s.symbol = 'GOOGL' THEN 130 + (random() * 30) + (random() - 0.5) * 3
        WHEN s.symbol = 'AMZN' THEN 150 + (random() * 30) + (random() - 0.5) * 3
        WHEN s.symbol = 'NVDA' THEN 500 + (random() * 100) + (random() - 0.5) * 10
        WHEN s.symbol = 'META' THEN 350 + (random() * 50) + (random() - 0.5) * 5
        WHEN s.symbol = 'TSLA' THEN 200 + (random() * 80) + (random() - 0.5) * 8
        WHEN s.symbol = 'JPM' THEN 150 + (random() * 30) + (random() - 0.5) * 3
        WHEN s.symbol = 'JNJ' THEN 155 + (random() * 15) + (random() - 0.5) * 2
        WHEN s.symbol = 'WMT' THEN 150 + (random() * 10) + (random() - 0.5) * 1
        WHEN s.symbol = 'SPY' THEN 450 + (random() * 50) + (random() - 0.5) * 5
        WHEN s.symbol = 'QQQ' THEN 380 + (random() * 40) + (random() - 0.5) * 4
        ELSE 100 + (random() * 50) + (random() - 0.5) * 3
    END as adj_close,
    -- Volume based on market cap
    CASE
        WHEN s.market_cap > 1000000000000 THEN (20000000 + random() * 30000000)::bigint
        WHEN s.market_cap > 500000000000 THEN (15000000 + random() * 20000000)::bigint
        WHEN s.market_cap > 100000000000 THEN (10000000 + random() * 15000000)::bigint
        ELSE (5000000 + random() * 10000000)::bigint
    END as volume,
    'sample_generator' as data_source
FROM
    securities s
    CROSS JOIN (
        SELECT generate_series(
            CURRENT_DATE - INTERVAL '365 days',
            CURRENT_DATE - INTERVAL '1 day',
            INTERVAL '1 day'
        )::date as trade_date
    ) dates
WHERE s.symbol IN (
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA',
    'JPM', 'JNJ', 'WMT', 'SPY', 'QQQ', 'XOM', 'BAC', 'UNH'
)
ON CONFLICT (symbol, trade_date) DO NOTHING;

-- Add more economic indicators with realistic data
INSERT INTO economic_indicators (indicator_code, indicator_name, date, value, unit, data_source)
VALUES
    -- Interest rates
    ('DGS10', '10-Year Treasury Rate', CURRENT_DATE - INTERVAL '1 day', 4.52, 'Percent', 'sample_generator'),
    ('DGS2', '2-Year Treasury Rate', CURRENT_DATE - INTERVAL '1 day', 4.87, 'Percent', 'sample_generator'),
    ('DGS30', '30-Year Treasury Rate', CURRENT_DATE - INTERVAL '1 day', 4.65, 'Percent', 'sample_generator'),

    -- Economic indicators
    ('VIXCLS', 'CBOE Volatility Index', CURRENT_DATE - INTERVAL '1 day', 14.2, 'Index', 'sample_generator'),
    ('DEXUSEU', 'US Dollar to Euro', CURRENT_DATE - INTERVAL '1 day', 1.08, 'Exchange Rate', 'sample_generator'),
    ('DEXCHUS', 'US Dollar to Chinese Yuan', CURRENT_DATE - INTERVAL '1 day', 7.24, 'Exchange Rate', 'sample_generator'),
    ('DEXJPUS', 'US Dollar to Japanese Yen', CURRENT_DATE - INTERVAL '1 day', 156.8, 'Exchange Rate', 'sample_generator'),

    -- Monthly indicators
    ('HOUST', 'Housing Starts', CURRENT_DATE - INTERVAL '30 days', 1420, 'Thousands of Units', 'sample_generator'),
    ('INDPRO', 'Industrial Production Index', CURRENT_DATE - INTERVAL '30 days', 103.5, 'Index', 'sample_generator'),
    ('PAYEMS', 'All Employees: Total Nonfarm', CURRENT_DATE - INTERVAL '30 days', 157000, 'Thousands', 'sample_generator'),
    ('UMCSENT', 'University of Michigan Consumer Sentiment', CURRENT_DATE - INTERVAL '30 days', 69.5, 'Index', 'sample_generator')
ON CONFLICT (indicator_code, date) DO UPDATE
SET value = EXCLUDED.value;

-- Summary of generated data
SELECT
    'Data Generation Complete!' as status,
    COUNT(DISTINCT s.symbol) as total_securities,
    COUNT(DISTINCT dp.symbol) as stocks_with_prices,
    COUNT(dp.*) as total_price_records,
    COUNT(DISTINCT ei.indicator_code) as economic_indicators
FROM securities s
LEFT JOIN daily_prices dp ON s.symbol = dp.symbol
CROSS JOIN economic_indicators ei;
