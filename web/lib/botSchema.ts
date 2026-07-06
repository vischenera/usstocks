import { getSql } from "./db";

// The bot is fully web-side (no worker involvement), so the web app must
// bootstrap its own tables — schema.sql is only applied by the worker.
// Idempotent, and memoized per lambda instance so warm requests skip it.
let ensured = false;

export async function ensureBotTables(sql: ReturnType<typeof getSql>) {
  if (ensured) return;
  await sql`
    CREATE TABLE IF NOT EXISTS bot_config (
      id            INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
      capital       DOUBLE PRECISION NOT NULL DEFAULT 1000,
      slots         INTEGER NOT NULL DEFAULT 5,
      start_days    INTEGER NOT NULL DEFAULT 90,
      slippage_pct  DOUBLE PRECISION NOT NULL DEFAULT 0.25,
      updated_at    TIMESTAMPTZ DEFAULT now()
    )
  `;
  await sql`
    CREATE TABLE IF NOT EXISTS bot_trades (
      id            BIGSERIAL PRIMARY KEY,
      symbol        TEXT NOT NULL,
      entry_date    DATE NOT NULL,
      entry_price   DOUBLE PRECISION NOT NULL,
      shares        DOUBLE PRECISION NOT NULL,
      cost          DOUBLE PRECISION NOT NULL,
      stop_level    DOUBLE PRECISION,
      exit_date     DATE,
      exit_price    DOUBLE PRECISION,
      exit_reason   TEXT,
      pnl           DOUBLE PRECISION
    )
  `;
  await sql`
    CREATE TABLE IF NOT EXISTS bot_equity (
      date    DATE PRIMARY KEY,
      equity  DOUBLE PRECISION NOT NULL,
      cash    DOUBLE PRECISION NOT NULL
    )
  `;
  ensured = true;
}
