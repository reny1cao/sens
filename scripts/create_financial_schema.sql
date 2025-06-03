-- Financial Market Database Schema for SENS
-- Optimized for real-time analysis with partitioning and proper indexing

-- Drop existing tables if they exist (for development)
DROP TABLE IF EXISTS portfolio_holdings CASCADE;
DROP TABLE IF EXISTS trades CASCADE;
DROP TABLE IF EXISTS options_contracts CASCADE;
DROP TABLE IF EXISTS market_data CASCADE;
DROP TABLE IF EXISTS financial_statements CASCADE;
DROP TABLE IF EXISTS economic_indicators CASCADE;
DROP TABLE IF EXISTS daily_prices CASCADE;
DROP TABLE IF EXISTS securities CASCADE;

-- Securities/Companies master table
CREATE TABLE securities (
    symbol VARCHAR(10) PRIMARY KEY,
    company_name VARCHAR(255) NOT NULL,
    sector VARCHAR(100),
    industry VARCHAR(100),
    market_cap BIGINT,
    exchange VARCHAR(10),
    country VARCHAR(3) DEFAULT 'USA',
    currency VARCHAR(3) DEFAULT 'USD',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Daily stock prices - PARTITIONED by month for performance
CREATE TABLE daily_prices (
    id BIGSERIAL,
    symbol VARCHAR(10) NOT NULL,
    trade_date DATE NOT NULL,
    open_price NUMERIC(12,4),
    high_price NUMERIC(12,4),
    low_price NUMERIC(12,4),
    close_price NUMERIC(12,4),
    adj_close NUMERIC(12,4),
    volume BIGINT,
    -- Technical indicators
    rsi NUMERIC(6,2),
    moving_avg_20 NUMERIC(12,4),
    moving_avg_50 NUMERIC(12,4),
    moving_avg_200 NUMERIC(12,4),
    volatility NUMERIC(8,4),
    -- Metadata
    data_source VARCHAR(50) DEFAULT 'alpha_vantage',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    PRIMARY KEY (symbol, trade_date)
) PARTITION BY RANGE (trade_date);

-- Create partitions for the last 2 years and next year
DO $$
DECLARE
    start_date DATE := '2023-01-01';
    end_date DATE := '2026-12-31';
    partition_start DATE;
    partition_end DATE;
    partition_name TEXT;
BEGIN
    WHILE start_date < end_date LOOP
        partition_start := DATE_TRUNC('month', start_date);
        partition_end := partition_start + INTERVAL '1 month';
        partition_name := 'daily_prices_' || TO_CHAR(partition_start, 'YYYY_MM');
        
        EXECUTE format('CREATE TABLE %I PARTITION OF daily_prices 
            FOR VALUES FROM (%L) TO (%L)', 
            partition_name, partition_start, partition_end);
            
        start_date := partition_end;
    END LOOP;
END $$;

-- Economic indicators from FRED
CREATE TABLE economic_indicators (
    indicator_code VARCHAR(20) NOT NULL,
    indicator_name VARCHAR(255),
    date DATE NOT NULL,
    value NUMERIC(15,4),
    unit VARCHAR(50),
    frequency VARCHAR(20), -- DAILY, WEEKLY, MONTHLY, QUARTERLY, ANNUAL
    data_source VARCHAR(50) DEFAULT 'fred',
    created_at TIMESTAMP DEFAULT NOW(),
    
    PRIMARY KEY (indicator_code, date)
);

-- Financial statements (quarterly/annual)
CREATE TABLE financial_statements (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    fiscal_year INTEGER NOT NULL,
    fiscal_quarter INTEGER, -- NULL for annual data
    period_end_date DATE,
    
    -- Income Statement
    revenue BIGINT,
    cost_of_revenue BIGINT,
    gross_profit BIGINT,
    operating_expenses BIGINT,
    operating_income BIGINT,
    net_income BIGINT,
    
    -- Balance Sheet
    total_assets BIGINT,
    current_assets BIGINT,
    total_liabilities BIGINT,
    current_liabilities BIGINT,
    shareholders_equity BIGINT,
    total_debt BIGINT,
    cash_and_equivalents BIGINT,
    
    -- Per Share Metrics
    earnings_per_share NUMERIC(8,2),
    book_value_per_share NUMERIC(8,2),
    shares_outstanding BIGINT,
    
    -- Ratios
    pe_ratio NUMERIC(8,2),
    pb_ratio NUMERIC(8,2),
    debt_to_equity NUMERIC(8,4),
    roe NUMERIC(8,4), -- Return on Equity
    roa NUMERIC(8,4), -- Return on Assets
    
    data_source VARCHAR(50) DEFAULT 'alpha_vantage',
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(symbol, fiscal_year, fiscal_quarter)
);

-- Trading transactions for portfolio analysis
CREATE TABLE trades (
    trade_id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    trade_timestamp TIMESTAMPTZ NOT NULL,
    trade_type VARCHAR(4) CHECK (trade_type IN ('BUY', 'SELL')),
    quantity INTEGER NOT NULL,
    price NUMERIC(12,4) NOT NULL,
    commission NUMERIC(8,2) DEFAULT 0,
    
    -- Portfolio tracking
    portfolio_id VARCHAR(50),
    trader_id VARCHAR(50),
    
    -- Metadata
    order_type VARCHAR(20), -- MARKET, LIMIT, STOP
    exchange VARCHAR(10),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Portfolio holdings (current positions)
CREATE TABLE portfolio_holdings (
    id BIGSERIAL PRIMARY KEY,
    portfolio_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(10) NOT NULL,
    quantity INTEGER NOT NULL,
    avg_cost NUMERIC(12,4),
    current_price NUMERIC(12,4),
    market_value NUMERIC(15,2),
    unrealized_pnl NUMERIC(15,2),
    realized_pnl NUMERIC(15,2),
    
    first_purchase_date DATE,
    last_updated TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(portfolio_id, symbol)
);

-- Options contracts (for advanced analysis)
CREATE TABLE options_contracts (
    contract_id VARCHAR(50) PRIMARY KEY,
    underlying_symbol VARCHAR(10) NOT NULL,
    option_type VARCHAR(4) CHECK (option_type IN ('CALL', 'PUT')),
    strike_price NUMERIC(12,4) NOT NULL,
    expiration_date DATE NOT NULL,
    
    -- Pricing and Greeks
    premium NUMERIC(8,2),
    bid_price NUMERIC(8,2),
    ask_price NUMERIC(8,2),
    last_price NUMERIC(8,2),
    volume INTEGER,
    open_interest INTEGER,
    
    -- Greeks
    delta NUMERIC(8,4),
    gamma NUMERIC(8,4),
    theta NUMERIC(8,4),
    vega NUMERIC(8,4),
    rho NUMERIC(8,4),
    implied_volatility NUMERIC(8,4),
    
    trade_date DATE NOT NULL,
    data_source VARCHAR(50) DEFAULT 'alpha_vantage',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Real-time market data (bid/ask spreads, volume)
CREATE TABLE market_data (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    bid_price NUMERIC(12,4),
    ask_price NUMERIC(12,4),
    bid_size INTEGER,
    ask_size INTEGER,
    last_price NUMERIC(12,4),
    volume INTEGER,
    spread NUMERIC(8,4),
    
    data_source VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Add foreign key constraints
ALTER TABLE daily_prices ADD CONSTRAINT fk_daily_prices_symbol 
    FOREIGN KEY (symbol) REFERENCES securities(symbol);

ALTER TABLE financial_statements ADD CONSTRAINT fk_financial_statements_symbol 
    FOREIGN KEY (symbol) REFERENCES securities(symbol);

ALTER TABLE trades ADD CONSTRAINT fk_trades_symbol 
    FOREIGN KEY (symbol) REFERENCES securities(symbol);

ALTER TABLE portfolio_holdings ADD CONSTRAINT fk_portfolio_holdings_symbol 
    FOREIGN KEY (symbol) REFERENCES securities(symbol);

ALTER TABLE options_contracts ADD CONSTRAINT fk_options_contracts_symbol 
    FOREIGN KEY (underlying_symbol) REFERENCES securities(symbol);

ALTER TABLE market_data ADD CONSTRAINT fk_market_data_symbol 
    FOREIGN KEY (symbol) REFERENCES securities(symbol);

-- Optimized indexes following best practices
-- Primary lookup indexes (symbol, date DESC) for point queries
CREATE INDEX idx_daily_prices_symbol_date_desc 
    ON daily_prices (symbol, trade_date DESC);

CREATE INDEX idx_trades_symbol_timestamp_desc 
    ON trades (symbol, trade_timestamp DESC);

CREATE INDEX idx_market_data_symbol_timestamp_desc 
    ON market_data (symbol, timestamp DESC);

-- BRIN indexes for large time-series scans
CREATE INDEX idx_daily_prices_date_brin 
    ON daily_prices USING BRIN (trade_date);

CREATE INDEX idx_trades_timestamp_brin 
    ON trades USING BRIN (trade_timestamp);

CREATE INDEX idx_market_data_timestamp_brin 
    ON market_data USING BRIN (timestamp);

-- Sector and industry analysis indexes
CREATE INDEX idx_securities_sector 
    ON securities (sector, market_cap DESC);

CREATE INDEX idx_securities_industry 
    ON securities (industry, market_cap DESC);

-- Economic indicators lookup
CREATE INDEX idx_economic_indicators_code_date_desc 
    ON economic_indicators (indicator_code, date DESC);

CREATE INDEX idx_economic_indicators_date_brin 
    ON economic_indicators USING BRIN (date);

-- Financial statements analysis indexes
CREATE INDEX idx_financial_statements_symbol_year_quarter 
    ON financial_statements (symbol, fiscal_year DESC, fiscal_quarter DESC);

CREATE INDEX idx_financial_statements_sector_year 
    ON financial_statements (symbol) 
    INCLUDE (fiscal_year, revenue, net_income);

-- Portfolio analysis indexes
CREATE INDEX idx_portfolio_holdings_portfolio_id 
    ON portfolio_holdings (portfolio_id, market_value DESC);

CREATE INDEX idx_trades_portfolio_timestamp 
    ON trades (portfolio_id, trade_timestamp DESC);

-- Options analysis indexes
CREATE INDEX idx_options_underlying_expiration 
    ON options_contracts (underlying_symbol, expiration_date);

CREATE INDEX idx_options_expiration_date 
    ON options_contracts (expiration_date) 
    WHERE expiration_date >= CURRENT_DATE;

-- Create views for common queries
CREATE VIEW stock_performance AS
SELECT 
    s.symbol,
    s.company_name,
    s.sector,
    dp.trade_date,
    dp.close_price,
    dp.volume,
    dp.rsi,
    dp.moving_avg_20,
    dp.moving_avg_50,
    LAG(dp.close_price) OVER (PARTITION BY s.symbol ORDER BY dp.trade_date) as prev_close,
    (dp.close_price - LAG(dp.close_price) OVER (PARTITION BY s.symbol ORDER BY dp.trade_date)) / 
        LAG(dp.close_price) OVER (PARTITION BY s.symbol ORDER BY dp.trade_date) * 100 as daily_return
FROM securities s
JOIN daily_prices dp ON s.symbol = dp.symbol
WHERE s.is_active = true;

CREATE VIEW latest_prices AS
SELECT DISTINCT ON (symbol)
    symbol,
    trade_date,
    close_price,
    volume,
    rsi,
    moving_avg_20,
    moving_avg_50
FROM daily_prices
ORDER BY symbol, trade_date DESC;

CREATE VIEW portfolio_summary AS
SELECT 
    ph.portfolio_id,
    COUNT(*) as positions_count,
    SUM(ph.market_value) as total_market_value,
    SUM(ph.unrealized_pnl) as total_unrealized_pnl,
    SUM(ph.realized_pnl) as total_realized_pnl,
    SUM(ph.unrealized_pnl + ph.realized_pnl) as total_pnl,
    (SUM(ph.unrealized_pnl + ph.realized_pnl) / SUM(ph.market_value - ph.unrealized_pnl)) * 100 as return_percentage
FROM portfolio_holdings ph
WHERE ph.quantity > 0
GROUP BY ph.portfolio_id;

-- Insert sample securities data
INSERT INTO securities (symbol, company_name, sector, industry, market_cap, exchange) VALUES
('AAPL', 'Apple Inc.', 'Technology', 'Consumer Electronics', 3500000000000, 'NASDAQ'),
('GOOGL', 'Alphabet Inc.', 'Technology', 'Internet Services', 1800000000000, 'NASDAQ'),
('MSFT', 'Microsoft Corporation', 'Technology', 'Software', 2800000000000, 'NASDAQ'),
('TSLA', 'Tesla Inc.', 'Consumer Discretionary', 'Auto Manufacturers', 800000000000, 'NASDAQ'),
('AMZN', 'Amazon.com Inc.', 'Consumer Discretionary', 'Internet Retail', 1500000000000, 'NASDAQ'),
('META', 'Meta Platforms Inc.', 'Technology', 'Social Media', 800000000000, 'NASDAQ'),
('NVDA', 'NVIDIA Corporation', 'Technology', 'Semiconductors', 2000000000000, 'NASDAQ'),
('JPM', 'JPMorgan Chase & Co.', 'Financial Services', 'Banks', 500000000000, 'NYSE'),
('JNJ', 'Johnson & Johnson', 'Healthcare', 'Pharmaceuticals', 450000000000, 'NYSE'),
('V', 'Visa Inc.', 'Financial Services', 'Credit Services', 500000000000, 'NYSE'),
('PG', 'Procter & Gamble Co.', 'Consumer Staples', 'Household Products', 350000000000, 'NYSE'),
('HD', 'Home Depot Inc.', 'Consumer Discretionary', 'Home Improvement', 400000000000, 'NYSE'),
('DIS', 'Walt Disney Co.', 'Communication Services', 'Entertainment', 200000000000, 'NYSE'),
('NFLX', 'Netflix Inc.', 'Communication Services', 'Streaming', 180000000000, 'NASDAQ'),
('CRM', 'Salesforce Inc.', 'Technology', 'Software', 220000000000, 'NYSE');

-- Insert sample economic indicators metadata
INSERT INTO economic_indicators (indicator_code, indicator_name, date, value, unit, frequency) VALUES
('GDP', 'Gross Domestic Product', '2024-01-01', 27000000, 'Billions of Dollars', 'QUARTERLY'),
('UNRATE', 'Unemployment Rate', '2024-01-01', 3.7, 'Percent', 'MONTHLY'),
('FEDFUNDS', 'Federal Funds Rate', '2024-01-01', 5.25, 'Percent', 'MONTHLY'),
('CPIAUCSL', 'Consumer Price Index', '2024-01-01', 310.5, 'Index 1982-1984=100', 'MONTHLY'),
('PAYEMS', 'Nonfarm Payrolls', '2024-01-01', 157000, 'Thousands of Persons', 'MONTHLY');

-- Create staging table for efficient bulk loads
CREATE TABLE staging_daily_prices (
    symbol TEXT,
    trade_date TEXT,
    open_price TEXT,
    high_price TEXT,
    low_price TEXT,
    close_price TEXT,
    adj_close TEXT,
    volume TEXT,
    data_source TEXT DEFAULT 'alpha_vantage',
    loaded_at TIMESTAMP DEFAULT NOW()
);

-- Function for upserting daily prices with conflict resolution
CREATE OR REPLACE FUNCTION upsert_daily_prices()
RETURNS INTEGER AS $$
DECLARE
    affected_rows INTEGER;
BEGIN
    INSERT INTO daily_prices (
        symbol, trade_date, open_price, high_price, 
        low_price, close_price, adj_close, volume, data_source
    )
    SELECT 
        symbol,
        trade_date::DATE,
        NULLIF(open_price, '')::NUMERIC(12,4),
        NULLIF(high_price, '')::NUMERIC(12,4),
        NULLIF(low_price, '')::NUMERIC(12,4),
        NULLIF(close_price, '')::NUMERIC(12,4),
        NULLIF(adj_close, '')::NUMERIC(12,4),
        NULLIF(volume, '')::BIGINT,
        data_source
    FROM staging_daily_prices 
    WHERE trade_date != '' AND symbol != ''
    ON CONFLICT (symbol, trade_date) 
    DO UPDATE SET
        open_price = EXCLUDED.open_price,
        high_price = EXCLUDED.high_price,
        low_price = EXCLUDED.low_price,
        close_price = EXCLUDED.close_price,
        adj_close = EXCLUDED.adj_close,
        volume = EXCLUDED.volume,
        updated_at = NOW();
    
    GET DIAGNOSTICS affected_rows = ROW_COUNT;
    
    -- Clean staging table
    TRUNCATE staging_daily_prices;
    
    RETURN affected_rows;
END;
$$ LANGUAGE plpgsql;

-- Create indexes on staging table for better performance
CREATE INDEX idx_staging_daily_prices_symbol 
    ON staging_daily_prices (symbol);

-- Comments for documentation
COMMENT ON TABLE securities IS 'Master table for all securities/stocks with company information';
COMMENT ON TABLE daily_prices IS 'Partitioned table for daily stock prices and technical indicators';
COMMENT ON TABLE economic_indicators IS 'Economic data from FRED (Federal Reserve Economic Data)';
COMMENT ON TABLE financial_statements IS 'Quarterly and annual financial statement data';
COMMENT ON TABLE trades IS 'Individual trading transactions for portfolio tracking';
COMMENT ON TABLE portfolio_holdings IS 'Current portfolio positions and performance';
COMMENT ON TABLE options_contracts IS 'Options contracts data with Greeks for advanced analysis';
COMMENT ON TABLE market_data IS 'Real-time market data including bid/ask spreads';

COMMENT ON FUNCTION upsert_daily_prices() IS 'Efficiently move data from staging to main table with conflict resolution';

-- Grant permissions (adjust as needed for your setup)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO sens_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO sens_user;

-- Display creation summary
SELECT 
    'Financial database schema created successfully!' as status,
    COUNT(*) as tables_created
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN (
    'securities', 'daily_prices', 'economic_indicators', 
    'financial_statements', 'trades', 'portfolio_holdings',
    'options_contracts', 'market_data', 'staging_daily_prices'
);