-- Migration: move all MongoDB collections into Postgres.
-- Replaces: all_stocks, filtered_stocks, result_calendar, seen_announcements,
--           financial_results, monitor_rules, notifications, monitor_status, estimates
--
-- filtered_stocks is not recreated as a table — it was always a derived
-- subset of all_stocks (market_cap > threshold), so callers now query
-- `stocks` with a WHERE clause instead of maintaining a duplicate copy.

-- ── stocks (was all_stocks + filtered_stocks) ────────────────────────────────

CREATE TABLE IF NOT EXISTS stocks (
    scrip_code   VARCHAR(20) PRIMARY KEY,
    scrip_name   VARCHAR(100) NOT NULL DEFAULT '',
    company_name VARCHAR(255) NOT NULL DEFAULT '',
    grp          VARCHAR(10) NOT NULL DEFAULT '',   -- "group" is a reserved word
    industry     VARCHAR(100) NOT NULL DEFAULT '',
    market_cap   NUMERIC(18,2) NOT NULL DEFAULT 0,
    face_value   VARCHAR(20) NOT NULL DEFAULT '',
    isin         VARCHAR(20) NOT NULL DEFAULT '',
    segment      VARCHAR(50) NOT NULL DEFAULT '',
    status       VARCHAR(20) NOT NULL DEFAULT '',
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stocks_market_cap ON stocks(market_cap DESC);


-- ── result_calendar ───────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS result_calendar (
    id           SERIAL PRIMARY KEY,
    scrip_code   VARCHAR(20) NOT NULL,
    short_name   VARCHAR(100) NOT NULL DEFAULT '',
    long_name    VARCHAR(255) NOT NULL DEFAULT '',
    meeting_date VARCHAR(50) NOT NULL DEFAULT '',   -- kept as free-text (source format varies)
    url          TEXT NOT NULL DEFAULT '',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_result_calendar_unique
    ON result_calendar(scrip_code, meeting_date, short_name);
CREATE INDEX IF NOT EXISTS idx_result_calendar_meeting_date ON result_calendar(meeting_date);
CREATE INDEX IF NOT EXISTS idx_result_calendar_long_name ON result_calendar(long_name);


-- ── seen_announcements (dedup) ────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS seen_announcements (
    id         SERIAL PRIMARY KEY,
    scrip_code VARCHAR(20) NOT NULL,
    news_date  VARCHAR(40) NOT NULL,
    subject    TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_seen_announcements_unique
    ON seen_announcements(scrip_code, news_date, subject);
CREATE INDEX IF NOT EXISTS idx_seen_announcements_created_at ON seen_announcements(created_at);


-- ── financial_results ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS financial_results (
    id                     SERIAL PRIMARY KEY,
    scrip_code             VARCHAR(20) NOT NULL,
    scrip_name             VARCHAR(100) NOT NULL DEFAULT '',
    company_name           VARCHAR(255) NOT NULL DEFAULT '',
    market_cap             NUMERIC(18,2) NOT NULL DEFAULT 0,
    news_date              VARCHAR(40) NOT NULL DEFAULT '',
    subject                TEXT NOT NULL DEFAULT '',
    pdf_link               TEXT NOT NULL DEFAULT '',
    raw_analysis           TEXT NOT NULL DEFAULT '',
    company_name_extracted VARCHAR(255) NOT NULL DEFAULT '',
    unit                   TEXT NOT NULL DEFAULT '',      -- AI-generated free text, unbounded
    quarter                TEXT NOT NULL DEFAULT '',       -- AI-generated free text, unbounded
    growth                 JSONB NOT NULL DEFAULT '{}',
    absolute_numbers       JSONB NOT NULL DEFAULT '{}',
    margins                JSONB NOT NULL DEFAULT '{}',
    signal                 VARCHAR(20) NOT NULL DEFAULT 'NEUTRAL',
    confidence             NUMERIC(5,2) NOT NULL DEFAULT 0,
    ai_model               VARCHAR(100) NOT NULL DEFAULT '',
    extracted_via          VARCHAR(50) NOT NULL DEFAULT '',
    analyzed_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at             TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS idx_financial_results_scrip_analyzed
    ON financial_results(scrip_code, analyzed_at DESC);
CREATE INDEX IF NOT EXISTS idx_financial_results_scrip_name ON financial_results(scrip_name);
CREATE INDEX IF NOT EXISTS idx_financial_results_analyzed_at ON financial_results(analyzed_at DESC);
CREATE INDEX IF NOT EXISTS idx_financial_results_not_deleted
    ON financial_results(deleted_at) WHERE deleted_at IS NULL;


-- ── monitor_rules ─────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS monitor_rules (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(255) NOT NULL DEFAULT '',
    field      VARCHAR(50) NOT NULL,
    operator   VARCHAR(20) NOT NULL,
    value      JSONB,
    enabled    BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_monitor_rules_enabled ON monitor_rules(enabled);


-- ── notifications (WebSocket event feed) ─────────────────────────────────────

CREATE TABLE IF NOT EXISTS notifications (
    id         SERIAL PRIMARY KEY,
    event      VARCHAR(50) NOT NULL,
    data       JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notifications_created_at ON notifications(created_at);


-- ── monitor_status (single-row runtime counters) ─────────────────────────────

CREATE TABLE IF NOT EXISTS monitor_status (
    id                  INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    last_poll           TIMESTAMPTZ,
    announcements_count INTEGER NOT NULL DEFAULT 0,
    polls_today         INTEGER NOT NULL DEFAULT 0,
    results_today       INTEGER NOT NULL DEFAULT 0,
    reload_rules        BOOLEAN NOT NULL DEFAULT FALSE
);


-- ── estimates (analyst estimates import) ─────────────────────────────────────

CREATE TABLE IF NOT EXISTS estimates (
    scrip_code          VARCHAR(20) PRIMARY KEY,
    scrip_name          VARCHAR(100) NOT NULL DEFAULT '',
    sector              VARCHAR(100) NOT NULL DEFAULT '',
    cap_size            VARCHAR(50) NOT NULL DEFAULT '',
    revenue_estimate    NUMERIC(18,2),
    ebitda_estimate     NUMERIC(18,2),
    net_profit_estimate NUMERIC(18,2),
    imported_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_estimates_scrip_name ON estimates(scrip_name);
