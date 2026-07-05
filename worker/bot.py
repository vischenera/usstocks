"""Paper-trading bot: deterministic replay of the breakout strategy.

Runs after each scan. Replays the FULL simulation from stored OHLCV every
time (no incremental state to corrupt): signals are computed exactly as the
scanner would have seen them at each historical close (no lookahead), all
action happens the next trading day, and fills are approximated realistically:

  - entries / signal-exits fill at next day's (O+H+L+C)/4 +/- slippage
  - trailing-stop exits fill AT the stop the day the low crosses it, unless
    the day gaps open below the stop -- then at the open (you eat the gap)

Position sizing: budget per new trade = realized pool / slots (compounding),
bounded by available cash. Fractional shares. One position per symbol.
Exits: 10% trailing stop from the highest high since entry (intraday), or
the "fading" step-out (position >= 5 sessions old and 3-day slope <= 0,
exits next day) -- whichever comes first.
"""

import traceback

import config
from metrics import breakout_metrics

STOP_PCT = config.PRESETS["breakout"]["stop_percentage"] / 100.0
FADE_MIN_AGE = 5  # sessions since entry before the fading step-out applies

# The signal's longest lookback: 10d slope window + 30d volume baseline.
MIN_HISTORY = 42


def _ohlc4(bar):
    vals = [bar.get("open"), bar.get("high"), bar.get("low"), bar.get("close")]
    vals = [v for v in vals if v]
    return sum(vals) / len(vals) if vals else None


def _passes_entry_gates(cfg, bars, mcap):
    """Breakout-preset gates as of the LAST bar in `bars` (no lookahead)."""
    last_close = bars[-1]["close"]
    if not last_close or last_close < cfg["min_price"] or last_close > cfg["max_price"]:
        return None
    avg_vol = sum(b["volume"] or 0 for b in bars) / len(bars)
    if avg_vol < cfg["min_volume"]:
        return None
    if mcap < cfg["min_mcap"] or mcap > cfg["max_mcap"]:
        return None
    bm = breakout_metrics(bars)
    if bm["slope_pct_day"] < cfg["min_slope_pct_day"]:
        return None
    if bm["trend_r2"] < cfg["min_trend_r2"]:
        return None
    if bm["up_day_ratio"] < cfg["min_up_day_ratio"]:
        return None
    if bm["vol_expansion"] < cfg["min_vol_expansion"]:
        return None
    if bm["breakout_age"] is None or bm["breakout_age"] > cfg["max_breakout_age"]:
        return None
    return bm


def _slope3(bars):
    closes = [b["close"] for b in bars]
    if len(closes) < 4 or not closes[-4] or not closes[-1]:
        return 0.0
    return ((closes[-1] / closes[-4]) - 1) / 3 * 100


def run_simulation(conn, all_bars, meta):
    """Replay the sim and persist bot_trades / bot_equity. Returns summary str."""
    cfg_row = _load_config(conn)
    capital = cfg_row["capital"]
    slots = cfg_row["slots"]
    start_days = cfg_row["start_days"]
    slip = cfg_row["slippage_pct"] / 100.0
    gates = config.PRESETS["breakout"]

    # Per-symbol date-indexed bars; global trading calendar.
    sym_bars = {s: b for s, b in all_bars.items() if len(b) >= 5}
    calendar = sorted({b["date"] for bars in sym_bars.values() for b in bars})
    if len(calendar) < MIN_HISTORY + 2:
        return "bot: not enough history yet"
    # index of each date per symbol for O(1) lookup
    sym_idx = {
        s: {b["date"]: i for i, b in enumerate(bars)}
        for s, bars in sym_bars.items()
    }

    # Simulation window: last `start_days` calendar entries, but signals need
    # MIN_HISTORY bars behind them, so the effective start is bounded.
    sim_days = calendar[max(0, len(calendar) - start_days):]

    cash = capital
    positions = {}  # symbol -> dict(entry_date, entry_price, shares, cost, hh, entry_idx)
    pending_entries = []  # symbols signalled at prior close, to fill today
    pending_exits = []  # (symbol, reason) signalled at prior close
    trades = []
    equity_curve = []

    for day in sim_days:
        # ---- 1. fill pending exits (signal-based, at today's OHLC4) ----
        for symbol, reason in pending_exits:
            pos = positions.get(symbol)
            if not pos:
                continue
            idx = sym_idx[symbol].get(day)
            if idx is None:
                continue  # no bar today; retry logic: exit at next bar
            px = _ohlc4(sym_bars[symbol][idx])
            if not px:
                continue
            fill = px * (1 - slip)
            cash += pos["shares"] * fill
            trades.append({**pos, "symbol": symbol, "exit_date": day,
                           "exit_price": fill, "exit_reason": reason,
                           "pnl": pos["shares"] * (fill - pos["entry_price"])})
            del positions[symbol]
        pending_exits = []

        # ---- 2. fill pending entries (at today's OHLC4) ----
        for symbol in pending_entries:
            if symbol in positions or len(positions) >= slots:
                continue
            idx = sym_idx[symbol].get(day)
            if idx is None:
                continue
            bar = sym_bars[symbol][idx]
            px = _ohlc4(bar)
            if not px:
                continue
            realized_pool = cash + sum(p["cost"] for p in positions.values())
            budget = min(realized_pool / slots, cash)
            if budget <= 0:
                continue
            fill = px * (1 + slip)
            shares = budget / fill
            cash -= budget
            positions[symbol] = {
                "entry_date": day, "entry_price": fill, "shares": shares,
                "cost": budget, "hh": bar.get("high") or fill, "age": 0,
            }
        pending_entries = []

        # ---- 3. intraday trailing stops on open positions ----
        for symbol in list(positions.keys()):
            pos = positions[symbol]
            idx = sym_idx[symbol].get(day)
            if idx is None:
                continue
            bar = sym_bars[symbol][idx]
            if pos["entry_date"] != day:  # entry day: stop from entry bar high
                pos["age"] += 1
            stop = pos["hh"] * (1 - STOP_PCT)
            low, opn = bar.get("low"), bar.get("open")
            if low is not None and low <= stop:
                # gap below the stop fills at the open, not the stop
                fill_base = opn if (opn is not None and opn < stop) else stop
                fill = fill_base * (1 - slip)
                cash += pos["shares"] * fill
                trades.append({**pos, "symbol": symbol, "exit_date": day,
                               "exit_price": fill, "exit_reason": "trail",
                               "pnl": pos["shares"] * (fill - pos["entry_price"])})
                del positions[symbol]
                continue
            if bar.get("high"):
                pos["hh"] = max(pos["hh"], bar["high"])

        # ---- 4. EOD: mark equity, then compute tomorrow's signals ----
        mark = cash
        for symbol, pos in positions.items():
            idx = sym_idx[symbol].get(day)
            close = sym_bars[symbol][idx]["close"] if idx is not None else None
            mark += pos["shares"] * (close or pos["entry_price"])
        equity_curve.append((day, mark, cash))

        # fading step-out signals (exit tomorrow)
        for symbol, pos in positions.items():
            idx = sym_idx[symbol].get(day)
            if idx is None or pos["age"] < FADE_MIN_AGE:
                continue
            if _slope3(sym_bars[symbol][max(0, idx - 3):idx + 1]) <= 0:
                pending_exits.append((symbol, "fading"))

        # entry signals for tomorrow, ranked by score, only if slots free
        free = slots - len(positions) + len(pending_exits)
        if free > 0:
            candidates = []
            for symbol, bars in sym_bars.items():
                if symbol in positions:
                    continue
                idx = sym_idx[symbol].get(day)
                if idx is None or idx + 1 < MIN_HISTORY:
                    continue
                window = bars[max(0, idx + 1 - 90):idx + 1]
                mcap = meta.get(symbol, (None, None, 0))[2] or 0
                bm = _passes_entry_gates(gates, window, mcap)
                if bm:
                    candidates.append((bm["breakout_score"], symbol))
            candidates.sort(reverse=True)
            pending_entries = [s for _, s in candidates[:free]]

    # persist
    _persist(conn, trades, positions, sym_bars, sym_idx, calendar[-1], equity_curve)

    realized = sum(t["pnl"] for t in trades)
    open_ct = len(positions)
    return (f"bot: {len(trades)} closed trades, realized P&L {realized:+.2f}, "
            f"{open_ct} open, equity {equity_curve[-1][1]:.2f}")


def _load_config(conn):
    with conn.cursor() as cur:
        cur.execute("INSERT INTO bot_config (id) VALUES (1) ON CONFLICT (id) DO NOTHING")
        cur.execute("SELECT capital, slots, start_days, slippage_pct FROM bot_config WHERE id = 1")
        capital, slots, start_days, slippage = cur.fetchone()
    conn.commit()
    return {"capital": capital, "slots": max(1, slots),
            "start_days": max(10, min(90, start_days)), "slippage_pct": slippage}


def _persist(conn, trades, positions, sym_bars, sym_idx, last_day, equity_curve):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM bot_trades")
        cur.execute("DELETE FROM bot_equity")
        for t in trades:
            cur.execute(
                """INSERT INTO bot_trades (symbol, entry_date, entry_price, shares,
                     cost, exit_date, exit_price, exit_reason, pnl)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (t["symbol"], t["entry_date"], t["entry_price"], t["shares"],
                 t["cost"], t["exit_date"], t["exit_price"], t["exit_reason"], t["pnl"]),
            )
        for symbol, pos in positions.items():
            stop = pos["hh"] * (1 - STOP_PCT)
            cur.execute(
                """INSERT INTO bot_trades (symbol, entry_date, entry_price, shares,
                     cost, stop_level)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (symbol, pos["entry_date"], pos["entry_price"], pos["shares"],
                 pos["cost"], stop),
            )
        for day, equity, cash in equity_curve:
            cur.execute(
                "INSERT INTO bot_equity (date, equity, cash) VALUES (%s,%s,%s)",
                (day, equity, cash),
            )
    conn.commit()


def run(conn, all_bars, meta):
    """Entry point guarded so a bot failure never fails the scan run."""
    try:
        print(run_simulation(conn, all_bars, meta))
    except Exception:  # noqa: BLE001
        print("bot simulation failed:")
        traceback.print_exc()
