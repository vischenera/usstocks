-- US Stock Momentum Scanner — Postgres schema
-- Applied automatically by worker/db.py on startup; kept here as canonical reference.

-- Universe metadata (one row per symbol)
CREATE TABLE IF NOT EXISTS tickers (
    symbol        TEXT PRIMARY KEY,
    company_name  TEXT,
    sector        TEXT,
    exchange      TEXT,
    market_cap    BIGINT,
    updated_at    TIMESTAMPTZ DEFAULT now()
);

-- Rolling daily OHLCV (kept to ~90 trading days per symbol)
CREATE TABLE IF NOT EXISTS daily_ohlcv (
    symbol  TEXT NOT NULL REFERENCES tickers(symbol) ON DELETE CASCADE,
    date    DATE NOT NULL,
    open    DOUBLE PRECISION,
    high    DOUBLE PRECISION,
    low     DOUBLE PRECISION,
    close   DOUBLE PRECISION,
    volume  BIGINT,
    PRIMARY KEY (symbol, date)
);
CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_date ON daily_ohlcv (symbol, date DESC);

-- One row per scan/fetch run (drives the dashboard "Data Status" panel)
CREATE TABLE IF NOT EXISTS scan_runs (
    id                 BIGSERIAL PRIMARY KEY,
    started_at         TIMESTAMPTZ DEFAULT now(),
    finished_at        TIMESTAMPTZ,
    mode               TEXT,            -- 'backfill' | 'incremental'
    status             TEXT,            -- 'running' | 'success' | 'partial' | 'rate_limited' | 'error'
    symbols_total      INTEGER DEFAULT 0,
    symbols_processed  INTEGER DEFAULT 0,
    valid_count        INTEGER DEFAULT 0,
    error_count        INTEGER DEFAULT 0,
    rate_limited       BOOLEAN DEFAULT FALSE,
    message            TEXT
);

-- Pre-computed scan results, one row per (run, preset, symbol).
-- The dashboard reads the latest run for a given preset.
CREATE TABLE IF NOT EXISTS scan_results (
    run_id               BIGINT NOT NULL REFERENCES scan_runs(id) ON DELETE CASCADE,
    preset               TEXT NOT NULL,
    symbol               TEXT NOT NULL,
    company_name         TEXT,
    sector               TEXT,
    market_cap           BIGINT,
    current_price        DOUBLE PRECISION,
    period_gain_pct      DOUBLE PRECISION,
    momentum_score       DOUBLE PRECISION,
    volatility           DOUBLE PRECISION,
    highest_high         DOUBLE PRECISION,
    trailing_stop_level  DOUBLE PRECISION,
    distance_to_stop_pct DOUBLE PRECISION,
    stop_triggered       BOOLEAN,
    volume               BIGINT,
    avg_volume           BIGINT,
    PRIMARY KEY (run_id, preset, symbol)
);
CREATE INDEX IF NOT EXISTS idx_results_preset_run ON scan_results (preset, run_id DESC);

-- Tiny key/value store for the self-resuming backfill cursor & phase.
CREATE TABLE IF NOT EXISTS job_state (
    key         TEXT PRIMARY KEY,
    value       JSONB NOT NULL,
    updated_at  TIMESTAMPTZ DEFAULT now()
);
