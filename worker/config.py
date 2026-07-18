"""Tunables, filter thresholds and scan presets.

All windows are in *trading days*. The rolling history window is 90 days
(ported from the original v3.0 scanner).
"""

# Rolling history window kept per symbol (trading days)
WINDOW_DAYS = 90

# How often the OHLCV cache (worker/cache.py) is force-rebuilt from Postgres,
# to bound drift and self-heal anything the CI cache got evicted.
FULL_RELOAD_INTERVAL_DAYS = 7

# How many calendar days the daily incremental fetch should look back.
# A small buffer covers weekends/holidays; duplicates are de-duped on upsert.
INCREMENTAL_LOOKBACK_DAYS = 7

# Backfill chunking: symbols pulled per scheduled run before a clean stop.
# A single GitHub Actions run (6h limit) handles the whole ~8,000 universe in
# ~1h, so the chunk spans the full universe; the resume cursor still kicks in if
# a run is throttled or cut short, picking up next schedule.
BACKFILL_CHUNK = 10000

# ---- Rate limiting (cloud / datacenter-IP friendly) ----
# Minimum seconds between requests across all worker threads.
MIN_REQUEST_INTERVAL = 0.20
# Threads. Kept modest because datacenter IPs get throttled faster than home IPs.
MAX_WORKERS = 8
# Per-request retry attempts on transient/auth errors before giving up.
REQUEST_RETRIES = 3
# Backoff base (seconds): wait = BACKOFF_BASE * 2**attempt (+ jitter).
BACKOFF_BASE = 2.0
# Substrings that indicate a Yahoo rate-limit / auth wall (treated as throttle).
RATE_LIMIT_MARKERS = (
    "rate limit", "429", "401", "unauthorized", "invalid crumb",
    "unable to access", "too many requests", "yahoo-finance-api-feedback",
)

# Default trailing-stop % used by the chart's auto-flipping trail.
DEFAULT_STOP_PCT = 10.0

# Scan presets — ported from the original scanner. Each produces its own
# pre-computed scan_results set, selectable on the dashboard.
PRESETS = {
    "day_trading": {
        "name": "Day Trading (Intraday)",
        "period_days": 1, "stop_percentage": 5,
        "min_price": 10.0, "max_price": 500, "min_volume": 500_000,
        "min_mcap": 100_000_000, "max_mcap": 50_000_000_000,
        "min_momentum": 0, "max_volatility": 999,
    },
    "aggressive_swing": {
        "name": "Aggressive Swing (10d)",
        "period_days": 10, "stop_percentage": 10,
        "min_price": 5.0, "max_price": 300, "min_volume": 200_000,
        "min_mcap": 50_000_000, "max_mcap": 5_000_000_000,
        "min_momentum": 5, "max_volatility": 999,
    },
    "conservative_swing": {
        "name": "Conservative Swing (30d)",
        "period_days": 30, "stop_percentage": 15,
        "min_price": 10.0, "max_price": 500, "min_volume": 100_000,
        "min_mcap": 100_000_000, "max_mcap": 10_000_000_000,
        "min_momentum": 0, "max_volatility": 999,
    },
    "momentum": {
        "name": "Momentum (10d)",
        "period_days": 10, "stop_percentage": 12,
        "min_price": 5.0, "max_price": 200, "min_volume": 300_000,
        "min_mcap": 50_000_000, "max_mcap": 3_000_000_000,
        "min_momentum": 10, "max_volatility": 999,
    },
    "small_cap": {
        "name": "Small Cap (30d)",
        "period_days": 30, "stop_percentage": 15,
        "min_price": 2.0, "max_price": 50, "min_volume": 100_000,
        "min_mcap": 10_000_000, "max_mcap": 500_000_000,
        "min_momentum": 0, "max_volatility": 999,
    },
    "all_caps": {
        "name": "All Caps (30d)",
        "period_days": 30, "stop_percentage": 15,
        "min_price": 5.0, "max_price": 100_000, "min_volume": 100_000,
        "min_mcap": 0, "max_mcap": float("inf"),
        "min_momentum": 0, "max_volatility": 999,
    },
    "all_caps_90": {
        "name": "All Caps (90d)",
        "period_days": 90, "stop_percentage": 15,
        "min_price": 5.0, "max_price": 100_000, "min_volume": 100_000,
        "min_mcap": 0, "max_mcap": float("inf"),
        "min_momentum": 0, "max_volatility": 999,
    },
    # Fresh, steep, CLEAN climbs out of a base with volume behind them —
    # thresholds calibrated on the ODD / RGNX June-2026 style setups.
    "breakout": {
        "name": "Breakout (fresh momentum)",
        "period_days": 10, "stop_percentage": 10,
        "min_price": 5.0, "max_price": 100_000, "min_volume": 100_000,
        "min_mcap": 0, "max_mcap": float("inf"),
        "min_momentum": 0, "max_volatility": 999,
        "min_slope_pct_day": 0.8, "min_trend_r2": 0.7,
        "min_up_day_ratio": 0.6, "min_vol_expansion": 1.5,
        "max_breakout_age": 5,
    },
}
