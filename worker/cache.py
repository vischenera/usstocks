"""Local on-disk cache of `all_bars`, persisted across CI runs via actions/cache.

Each scan run used to rebuild `all_bars` (every symbol's full 90-day window)
with one big streamed SELECT over `daily_ohlcv` — that's what was blowing
through Neon's free-tier network-transfer quota, since it moved the whole
table across the wire every day even though only ~1 day per symbol actually
changed. Postgres (`db.load_all_ohlcv`) stays the source of truth; this cache
just avoids re-pulling data we already have, by keeping it as a local file
that `scan.py` mutates in place as new bars come in and persists for the
next run to pick up.

The cache is rebuilt from Postgres (one full read) whenever it's missing,
corrupt, or older than FULL_RELOAD_INTERVAL_DAYS — bounding how far it can
drift from the DB and self-healing anything actions/cache evicts.
"""

import os
import pickle
from datetime import date

import config
import db

CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache")
CACHE_PATH = os.path.join(CACHE_DIR, "ohlcv.pkl")
CACHE_VERSION = 1
LAST_RELOAD_KEY = "last_full_reload"


def _read_local():
    """Return the cached all_bars dict, or None if missing/corrupt/old version."""
    try:
        with open(CACHE_PATH, "rb") as f:
            payload = pickle.load(f)
        if payload.get("version") != CACHE_VERSION:
            return None
        return payload["all_bars"]
    except (FileNotFoundError, EOFError, pickle.UnpicklingError, KeyError):
        return None


def save(all_bars):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_PATH, "wb") as f:
        pickle.dump(
            {"version": CACHE_VERSION, "all_bars": all_bars},
            f,
            protocol=pickle.HIGHEST_PROTOCOL,
        )


def load_or_reload(conn):
    """Return an all_bars dict, reusing the local cache when fresh, otherwise
    rebuilding it from Postgres (source of truth) with one full read."""
    last_reload = db.get_state(conn, LAST_RELOAD_KEY)
    stale = True
    if last_reload:
        try:
            age_days = (date.today() - date.fromisoformat(last_reload)).days
            stale = age_days >= config.FULL_RELOAD_INTERVAL_DAYS
        except ValueError:
            stale = True

    cached = None if stale else _read_local()
    if cached is not None:
        return cached

    print("OHLCV cache miss/stale — full reload from DB.")
    all_bars = db.load_all_ohlcv(conn)
    db.set_state(conn, LAST_RELOAD_KEY, date.today().isoformat())
    return all_bars
