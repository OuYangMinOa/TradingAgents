-- TradingAgents-TW Database Schema

CREATE TABLE IF NOT EXISTS stock_daily (
    id          SERIAL PRIMARY KEY,
    stock_id    VARCHAR(10) NOT NULL,
    date        DATE        NOT NULL,
    open        DECIMAL(10, 2),
    high        DECIMAL(10, 2),
    low         DECIMAL(10, 2),
    close       DECIMAL(10, 2),
    volume      BIGINT,
    created_at  TIMESTAMP DEFAULT NOW(),
    UNIQUE (stock_id, date)
);

CREATE TABLE IF NOT EXISTS ptt_posts (
    id          SERIAL PRIMARY KEY,
    article_id  VARCHAR(50) UNIQUE,
    title       TEXT,
    author      VARCHAR(50),
    push_count  INT,
    boo_count   INT,
    posted_at   TIMESTAMP,
    crawled_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS news_articles (
    id            SERIAL PRIMARY KEY,
    source        VARCHAR(50),
    title         TEXT,
    summary       TEXT,
    url           TEXT UNIQUE,
    published_at  TIMESTAMP,
    crawled_at    TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS institutional_investors (
    id           SERIAL PRIMARY KEY,
    stock_id     VARCHAR(10),
    date         DATE,
    foreign_buy  BIGINT,
    foreign_sell BIGINT,
    trust_buy    BIGINT,
    trust_sell   BIGINT,
    dealer_buy   BIGINT,
    dealer_sell  BIGINT,
    UNIQUE (stock_id, date)
);

CREATE TABLE IF NOT EXISTS agent_reports (
    id          SERIAL PRIMARY KEY,
    stock_id    VARCHAR(10),
    report_date DATE,
    agent_type  VARCHAR(50),
    report      JSONB,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS daily_recommendations (
    id            SERIAL PRIMARY KEY,
    report_date   DATE,
    stock_id      VARCHAR(10),
    action        VARCHAR(20),
    position_size DECIMAL(5, 4),
    stop_loss     DECIMAL(10, 2),
    take_profit   DECIMAL(10, 2),
    rationale     TEXT,
    approved      BOOLEAN,
    risk_notes    JSONB,
    created_at    TIMESTAMP DEFAULT NOW()
);

-- Phase 4: financial data tables (fetched via Python FinMind client)
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

CREATE TABLE IF NOT EXISTS stock_financials (
    id         SERIAL PRIMARY KEY,
    stock_id   VARCHAR(10) NOT NULL,
    date       DATE        NOT NULL,
    dataset    VARCHAR(50) NOT NULL,
    data       JSONB,
    fetched_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (stock_id, date, dataset)
);

CREATE TABLE IF NOT EXISTS stock_dividends (
    id                          SERIAL PRIMARY KEY,
    stock_id                    VARCHAR(10)   NOT NULL,
    date                        DATE          NOT NULL,
    cash_earnings_distribution  DECIMAL(10, 4),
    stock_earnings_distribution DECIMAL(10, 4),
    fetched_at                  TIMESTAMP DEFAULT NOW(),
    UNIQUE (stock_id, date)
);

CREATE INDEX IF NOT EXISTS idx_stock_daily_stock_date   ON stock_daily (stock_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_institutional_stock_date ON institutional_investors (stock_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_agent_reports_stock_date ON agent_reports (stock_id, report_date DESC);
CREATE INDEX IF NOT EXISTS idx_ptt_posted_at            ON ptt_posts (posted_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_published_at        ON news_articles (published_at DESC);
