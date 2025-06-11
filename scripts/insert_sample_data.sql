-- Insert sample stock data for testing
-- This script inserts sample data for AAPL, GOOGL, and MSFT

-- First ensure we have the securities
INSERT INTO securities (symbol, company_name, sector, industry, market_cap, country)
VALUES
    ('AAPL', 'Apple Inc.', 'Technology', 'Consumer Electronics', 3000000000000, 'US'),
    ('GOOGL', 'Alphabet Inc.', 'Technology', 'Internet Services', 2000000000000, 'US'),
    ('MSFT', 'Microsoft Corporation', 'Technology', 'Software', 2500000000000, 'US')
ON CONFLICT (symbol) DO UPDATE SET
    company_name = EXCLUDED.company_name,
    sector = EXCLUDED.sector,
    industry = EXCLUDED.industry,
    market_cap = EXCLUDED.market_cap;

-- Insert sample daily prices for the last 30 days
INSERT INTO daily_prices (symbol, trade_date, open_price, high_price, low_price, close_price, volume, adj_close)
VALUES
    -- AAPL data
    ('AAPL', '2025-11-06', 190.50, 192.80, 189.20, 191.50, 50000000, 191.50),
    ('AAPL', '2025-11-05', 189.00, 191.00, 188.50, 190.50, 48000000, 190.50),
    ('AAPL', '2025-11-04', 188.20, 189.50, 187.00, 189.00, 52000000, 189.00),
    ('AAPL', '2025-11-01', 187.50, 188.80, 186.50, 188.20, 45000000, 188.20),
    ('AAPL', '2025-10-31', 186.00, 188.00, 185.50, 187.50, 47000000, 187.50),
    -- GOOGL data
    ('GOOGL', '2025-11-06', 140.20, 142.50, 139.80, 141.80, 25000000, 141.80),
    ('GOOGL', '2025-11-05', 139.50, 140.80, 138.90, 140.20, 23000000, 140.20),
    ('GOOGL', '2025-11-04', 138.80, 140.00, 138.20, 139.50, 24000000, 139.50),
    ('GOOGL', '2025-11-01', 138.00, 139.20, 137.50, 138.80, 22000000, 138.80),
    ('GOOGL', '2025-10-31', 137.20, 138.50, 136.80, 138.00, 21000000, 138.00),
    -- MSFT data
    ('MSFT', '2025-11-06', 380.50, 385.00, 379.00, 383.50, 30000000, 383.50),
    ('MSFT', '2025-11-05', 378.00, 381.50, 377.20, 380.50, 28000000, 380.50),
    ('MSFT', '2025-11-04', 376.50, 379.00, 375.80, 378.00, 29000000, 378.00),
    ('MSFT', '2025-11-01', 375.00, 377.20, 374.50, 376.50, 27000000, 376.50),
    ('MSFT', '2025-10-31', 373.80, 375.80, 373.00, 375.00, 26000000, 375.00)
ON CONFLICT (symbol, trade_date) DO NOTHING;

-- Add some economic indicators
INSERT INTO economic_indicators (indicator_code, indicator_name, date, value, unit)
VALUES
    ('GDP', 'Gross Domestic Product', '2025-11-01', 25000.00, 'Billions USD'),
    ('UNRATE', 'Unemployment Rate', '2025-11-01', 3.7, 'Percent'),
    ('FEDFUNDS', 'Federal Funds Rate', '2025-11-01', 5.25, 'Percent'),
    ('CPI', 'Consumer Price Index', '2025-11-01', 310.50, 'Index')
ON CONFLICT (indicator_code, date) DO NOTHING;
