-- PostgreSQL schema for BSE Result Analyser Web
-- Applied automatically via docker-entrypoint-initdb.d/init.sql

-- ── Users ────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    name            VARCHAR(255) NOT NULL DEFAULT '',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    settings        JSONB NOT NULL DEFAULT '{}',
    role            VARCHAR(20) NOT NULL DEFAULT 'user',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);


-- ── Broker API Keys (encrypted at rest) ──────────────────────────────────────

CREATE TABLE IF NOT EXISTS broker_keys (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    broker          VARCHAR(50) NOT NULL,          -- upstox | angel_one | kite | dhan | groww
    api_key_enc     TEXT NOT NULL,                  -- AES-256-GCM encrypted
    api_secret_enc  TEXT NOT NULL,                  -- AES-256-GCM encrypted
    totp_secret_enc TEXT,                           -- AES-256-GCM encrypted (nullable)
    redirect_uri    VARCHAR(500),
    mode            VARCHAR(10) NOT NULL DEFAULT 'paper',  -- paper | live
    is_connected    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_broker_keys_user ON broker_keys(user_id);
CREATE UNIQUE INDEX idx_broker_keys_user_broker ON broker_keys(user_id, broker);


-- ── Orders (trade audit log) ─────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS orders (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    broker          VARCHAR(50) NOT NULL,
    order_id        VARCHAR(100) NOT NULL,          -- broker-assigned or PAPER-xxx
    scrip_code      VARCHAR(20) NOT NULL,
    symbol          VARCHAR(50) NOT NULL,
    exchange        VARCHAR(10) NOT NULL DEFAULT 'BSE',
    side            VARCHAR(4) NOT NULL,            -- BUY | SELL
    quantity        INTEGER NOT NULL,
    order_type      VARCHAR(20) NOT NULL,           -- MARKET | LIMIT | SL
    price           NUMERIC(12,2) NOT NULL DEFAULT 0,
    trigger_price   NUMERIC(12,2),
    status          VARCHAR(30) NOT NULL DEFAULT 'PLACED',  -- PLACED | FILLED | REJECTED | SIMULATED | CANCELLED
    filled_qty      INTEGER NOT NULL DEFAULT 0,
    avg_price       NUMERIC(12,2) NOT NULL DEFAULT 0,
    simulated       BOOLEAN NOT NULL DEFAULT FALSE,
    broker_order_id VARCHAR(100),
    response_raw    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_orders_user ON orders(user_id);
CREATE INDEX idx_orders_order_id ON orders(order_id);
CREATE INDEX idx_orders_scrip ON orders(scrip_code);


-- ── Watchlist (optional future feature) ──────────────────────────────────────

CREATE TABLE IF NOT EXISTS watchlist (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scrip_code  VARCHAR(20) NOT NULL,
    added_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, scrip_code)
);
