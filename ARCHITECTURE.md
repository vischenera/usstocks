# US Stock Momentum Scanner — Architecture

A self-driving US-equity momentum scanner. A scheduled worker pulls daily price
data for the whole US market into a database, scores each stock (momentum,
trailing-stop, volatility), and a web dashboard reads the pre-computed results.

Designed to run at **$0/month** and to require **zero manual operation** — the
backfill and daily updates run, retry, and resume on their own.

---

## High-level shape

```
┌──────────────────── VERCEL (Frontend + read API) ─────────────────┐
│  Next.js (App Router) + Tailwind + Lightweight Charts              │
│   • Scanner table   (filters: preset / mcap / volume / sort)      │
│   • Stock chart     (candles + auto-flipping trailing stop)       │
│   • Data Status panel (freshness, backfill %, rate-limit state)   │
│   • API routes (/app/api/*) read Neon directly via SQL            │
└───────────────────────────────┬───────────────────────────────────┘
                                │  reads (never calls Yahoo)
                                ▼
┌──────────────────────────── NEON (Postgres) ──────────────────────┐
│  tickers · daily_ohlcv · scan_runs · scan_results · job_state     │
└───────────────────────────────▲───────────────────────────────────┘
                                │  writes
┌────────────────────── GITHUB ACTIONS (worker) ────────────────────┐
│  Scheduled cron (self-resuming state machine):                    │
│    backfill not done?  → pull next chunk of 90-day history         │
│    else                → fetch last few days (incremental)         │
│  Then: compute metrics for every preset → write scan_results      │
│  Rate-limit safe: global limiter + backoff + resume cursor        │
│  Data source behind an interface → yfinance now, swappable later  │
└────────────────────────────────────────────────────────────────────┘
```

### Why this split (and not Railway/FastAPI)
A separate always-on backend isn't needed: the scan is a once-a-day batch, and
the API only reads a tiny pre-computed table. So:
- the **worker** lives in **GitHub Actions** (free cron, no idle server), and
- the **read API** collapses into **Next.js route handlers on Vercel** (no
  cold-start backend, no extra deploy).

The heavy Python logic (fetching + scoring) lives only in the worker. The data
layer sits behind `worker/datasource.py`, so swapping yfinance for Alpaca/
Finnhub later touches one file and nothing else.

---

## Repository layout

```
worker/                 Python batch job (runs in GitHub Actions or locally)
  config.py             Presets, filter thresholds, tunables (90-day window)
  db.py                 Postgres connection + schema bootstrap + upserts
  datasource.py         Market-data interface (yfinance impl; swappable)
  universe.py           Download the US ticker universe (NASDAQ + others)
  metrics.py            Momentum / trailing-stop / volatility / auto-flip trail
  scan.py               State machine: backfill ↔ incremental, compute, persist
  run.py                CLI entrypoint (also used by the cron)
  requirements.txt

web/                    Next.js dashboard + read API (deploys to Vercel)
  app/
    page.tsx            Dashboard (status panel + scanner table + filters)
    stock/[ticker]/page.tsx   Chart page
    api/                Route handlers reading Neon
  components/
  lib/

db/schema.sql           Canonical schema (also applied by worker/db.py)
.github/workflows/scan.yml   The scheduled worker
```

---

## Data flow / lifecycle

**One-time (automatic on first run):** the worker detects an empty DB, marks
state `backfill`, and pulls the rolling 90-day history for the whole universe in
chunks, saving a cursor after each chunk. If it is interrupted or rate-limited it
stops cleanly; the next scheduled run resumes from the cursor. When the cursor
reaches the end, state flips to `incremental`.

**Every day after US close (~5pm ET):** the worker fetches only the last few
days per symbol, upserts into `daily_ohlcv` (keeping a rolling 90 days),
recomputes metrics for every preset, and writes a fresh `scan_results` set plus a
`scan_runs` status row.

**When you open the dashboard:** the browser hits a Next.js route handler that
runs one indexed query against Neon and returns pre-computed results. No Yahoo
call, millisecond response, works even if Yahoo is down.

---

## Reliability & autonomy

- **Self-resuming backfill** via `job_state` cursor — no "forgot to run it".
- **Global rate limiter + exponential backoff**; on a hard rate-limit the run
  stops gracefully and resumes next schedule (no hammering, no spam).
- **Status surfaced in the UI**: `scan_runs` records mode, counts, errors, and
  rate-limit state → the Data Status panel shows freshness / backfill % /
  "rate-limited, retrying".
- **Idempotent** upserts → safe to re-run anytime.
- **Keep-alive**: the workflow periodically commits a small status file so
  GitHub doesn't auto-disable the schedule after 60 days of repo inactivity.

## Cost & free-tier notes

- **GitHub Actions** — unlimited minutes while the repo is **public**
  (use during the heavy initial backfill); after backfill, flip the repo
  **private** — the tiny daily incremental stays well under the 2,000 min/mo cap.
- **Neon** — 0.5 GB free; 90-day data for ~8,000 symbols ≈ 70–100 MB.
- **Vercel** — Hobby (free) for the dashboard + API routes.
- **Total: $0/month.**

## Configuration (secrets / env)

| Name | Where | Purpose |
|------|-------|---------|
| `DATABASE_URL` | GitHub Actions secret + Vercel env | Neon Postgres connection string |

See `README.md` for setup steps.
