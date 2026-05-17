-- Phase 4 migration: financial data tables
-- Run once on existing installations:
--   docker exec -i <postgres_container> psql -U tradingagents tradingagents < scripts/add_financial_tables.sql

CREATE TABLE IF NOT EXISTS stock_revenue (
    id          SERIAL PRIMARY KEY,
    stock_id    VARCHAR(10) NOT NULL,
    date        DATE        NOT NULL,
    revenue     BIGINT,
    revenue_mom DECIMAL(8, 4),
    revenue_yoy DECIMAL(8, 4),
    fetched_at  TIMESTAMP DEFAULT NOW(),
    UNIQUE (stock_id, date)
);

-- General-purpose store for FinMind financial statement datasets.
-- dataset: 'income_statement' | 'balance_sheet' | 'cash_flow'
CREATE TABLE IF NOT EXISTS stock_financials (
    id         SERIAL PRIMARY KEY,
    stock_id   VARCHAR(10)  NOT NULL,
    date       DATE         NOT NULL,
    dataset    VARCHAR(50)  NOT NULL,
    data       JSONB,
    fetched_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (stock_id, date, dataset)
);

CREATE TABLE IF NOT EXISTS stock_dividends (
    id                         SERIAL PRIMARY KEY,
    stock_id                   VARCHAR(10)   NOT NULL,
    date                       DATE          NOT NULL,
    cash_earnings_distribution DECIMAL(10, 4),
    stock_earnings_distribution DECIMAL(10, 4),
    fetched_at                 TIMESTAMP DEFAULT NOW(),
    UNIQUE (stock_id, date)
);

CREATE INDEX IF NOT EXISTS idx_revenue_stock_date     ON stock_revenue    (stock_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_financials_stock_date  ON stock_financials (stock_id, date DESC, dataset);
CREATE INDEX IF NOT EXISTS idx_dividends_stock_date   ON stock_dividends  (stock_id, date DESC);
