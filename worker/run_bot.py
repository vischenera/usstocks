#!/usr/bin/env python3
"""Standalone bot replay: re-runs the paper-trading simulation from data
already in the database — no market-data fetching. Used by the manual
"Run now" button (bot.yml workflow); the daily scan also replays inline.

    DATABASE_URL=postgres://... python run_bot.py
"""

import bot
import db

if __name__ == "__main__":
    conn = db.get_conn()
    try:
        db.init_schema(conn)
        all_bars = db.load_all_ohlcv(conn)
        meta = {}
        with conn.cursor() as cur:
            cur.execute("SELECT symbol, company_name, sector, market_cap FROM tickers")
            for sym, name, sector, mcap in cur.fetchall():
                meta[sym] = (name, sector, mcap or 0)
        bot.run(conn, all_bars, meta)
    finally:
        conn.close()
