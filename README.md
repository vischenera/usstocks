# US Stock Momentum Scanner

A self-driving US-equity momentum scanner with trailing-stop analysis.

A scheduled worker pulls daily price data for the whole US market into a
Postgres database, scores every stock (momentum, trailing stop, volatility),
and a web dashboard reads the pre-computed results. It runs at **$0/month** and
needs **no manual operation** — the backfill and daily updates run, retry, and
resume on their own.

> See **[ARCHITECTURE.md](ARCHITECTURE.md)** for the full design.

```
GitHub Actions (worker)  →  Neon (Postgres)  →  Vercel (dashboard + read API)
```

## Layout

| Path | What |
|------|------|
| `worker/` | Python batch job: fetch → score → store (runs in GitHub Actions or locally) |
| `web/` | Next.js dashboard + read API routes (deploys to Vercel) |
| `db/schema.sql` | Canonical Postgres schema (also auto-applied by the worker) |
| `.github/workflows/` | `scan.yml` (the cron) + `keepalive.yml` (keeps the schedule alive) |

## Setup

### 1. Database (Neon — free)
1. Create a free project at [neon.tech](https://neon.tech).
2. Copy the connection string (`postgres://…`). The schema is created
   automatically on the first worker run.

### 2. Worker (GitHub Actions)
1. Add the connection string as a repo secret named **`DATABASE_URL`**
   (Settings → Secrets and variables → Actions).
2. Make the repo **public** for the initial backfill (unlimited free minutes),
   then trigger **Actions → scan → Run workflow**. Watch the dashboard's status
   panel show `Backfilling… %` until it reaches 100%.
3. Once backfill is done you can flip the repo **private** — the daily
   incremental stays well under the free 2,000 min/month cap.

The `scan` workflow then runs automatically every day at 22:00 UTC (after the
US close). It resumes on its own if ever interrupted or rate-limited.

### 3. Dashboard (Vercel — free)
1. Import the repo at [vercel.com](https://vercel.com), set **Root Directory =
   `web`**.
2. Add an env var **`DATABASE_URL`** (same Neon string).
3. Deploy. The dashboard reads pre-computed results — it never calls Yahoo.

## Run the worker locally

```bash
cd worker
pip install -r requirements.txt
DATABASE_URL='postgres://…' python run.py
```

Each invocation runs one step (a backfill chunk or a daily incremental) and
exits; the schedule re-invokes it and the state machine resumes.

## Changing the data provider

yfinance is used today. To switch to a paid API later (Alpaca / Finnhub /
Polygon), implement `fetch_history` and `fetch_info` in a new class in
`worker/datasource.py` and return it from `get_source()`. Nothing else changes.

## Disclaimer

For informational purposes only. Not financial advice.
