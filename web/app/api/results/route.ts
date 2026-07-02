import { NextRequest, NextResponse } from "next/server";
import { getSql } from "@/lib/db";
import { PRESET_DEFS } from "@/lib/presets";
import { calculateMetrics, Bar } from "@/lib/metrics";

export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";

// Whitelist sortable columns (all numeric) — used for JS sort, never interpolated into SQL.
const SORTABLE = new Set([
  "period_gain_pct", "momentum_score", "volatility", "market_cap", "current_price",
]);

const NO_STORE = { headers: { "Cache-Control": "no-store, max-age=0" } };

// Descending numeric sort that treats a real 0 as 0, not "missing" — a plain
// `Number(v) || -Infinity` sends legitimate zero values to the bottom.
function sortDesc<T extends Record<string, any>>(rows: T[], key: string) {
  const val = (v: any) => (v === null || v === undefined || Number.isNaN(Number(v)) ? -Infinity : Number(v));
  rows.sort((a, b) => val(b[key]) - val(a[key]));
}

// Symbols keep at most this many stored days (mirrors worker/config.py WINDOW_DAYS).
const STORED_WINDOW_DAYS = 90;

// Recompute results live from stored OHLCV for a custom day-window, using the
// preset's other filter thresholds unchanged. Only hit when `days` differs
// from the preset's own default — otherwise the precomputed path below (fast,
// worker-side) is used.
//
// Mirrors worker/scan.py's evaluate_symbol: price/volume/mcap gates are
// checked against the *full* stored history (not the requested day-window),
// same as the worker does — only the returned metrics (gain%, momentum,
// trailing stop, etc.) are computed over the `days` window.
async function computeLive(sql: ReturnType<typeof getSql>, preset: string, days: number) {
  const def = PRESET_DEFS[preset];
  if (!def) return [];

  const [barRows, metaRows] = await Promise.all([
    sql`
      SELECT symbol, to_char(date, 'YYYY-MM-DD') AS date, open, high, low, close, volume
      FROM (
        SELECT *, row_number() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
        FROM daily_ohlcv
        WHERE close IS NOT NULL AND open IS NOT NULL AND high IS NOT NULL AND low IS NOT NULL
      ) t
      WHERE rn <= ${STORED_WINDOW_DAYS}
      ORDER BY symbol, date ASC
    `,
    sql`SELECT symbol, company_name, sector, market_cap FROM tickers`,
  ]);

  const bySymbol = new Map<string, Bar[]>();
  for (const r of barRows as any[]) {
    const bars = bySymbol.get(r.symbol) ?? [];
    bars.push({ date: r.date, open: r.open, high: r.high, low: r.low, close: r.close, volume: Number(r.volume) });
    bySymbol.set(r.symbol, bars);
  }

  const meta = new Map<string, { company_name: string; sector: string; market_cap: number }>();
  for (const r of metaRows as any[]) {
    meta.set(r.symbol, { company_name: r.company_name, sector: r.sector, market_cap: Number(r.market_cap) || 0 });
  }

  const rows: any[] = [];
  for (const [symbol, bars] of bySymbol) {
    const m = meta.get(symbol) ?? { company_name: symbol, sector: "N/A", market_cap: 0 };
    // Full-history average volume, same basis as the worker's own gate —
    // independent of the requested `days` window.
    const fullHistoryAvgVolume = bars.reduce((a, b) => a + b.volume, 0) / bars.length;
    const lastClose = bars[bars.length - 1].close;
    if (lastClose < def.minPrice || lastClose > def.maxPrice) continue;
    if (fullHistoryAvgVolume < def.minVolume) continue;
    if (m.market_cap < def.minMcap || m.market_cap > def.maxMcap) continue;

    const metrics = calculateMetrics(bars, days, def.stopPercentage, def.isIntraday);
    if (!metrics) continue;
    if (metrics.momentum_score < def.minMomentum) continue;
    if (def.maxVolatility < 999 && metrics.volatility > def.maxVolatility) continue;
    rows.push({ symbol, company_name: m.company_name, sector: m.sector, market_cap: m.market_cap, ...metrics });
  }
  return rows;
}

export async function GET(req: NextRequest) {
  try {
    const sql = getSql();
    const p = req.nextUrl.searchParams;
    const preset = p.get("preset") || "conservative_swing";
    const sortKey = SORTABLE.has(p.get("sort") || "") ? (p.get("sort") as string) : "period_gain_pct";
    const limit = Math.min(1000, Math.max(1, Number(p.get("limit") || 300)));
    const onlyActive = p.get("onlyActive") === "1";
    const daysParam = Number(p.get("days"));
    const days = Number.isFinite(daysParam) && daysParam > 0 ? Math.min(90, Math.max(1, daysParam)) : null;

    const liveDays = days ?? PRESET_DEFS[preset]?.periodDays;
    const wantsLive = days !== null && days !== PRESET_DEFS[preset]?.periodDays;

    if (wantsLive) {
      let rows = await computeLive(sql, preset, liveDays!);
      if (onlyActive) rows = rows.filter((r) => !r.stop_triggered);
      sortDesc(rows, sortKey);
      return NextResponse.json({ runId: null, rows: rows.slice(0, limit) }, NO_STORE);
    }

    // Latest run that actually has rows for this preset.
    const latest = await sql`
      SELECT max(run_id) AS run_id FROM scan_results WHERE preset = ${preset}
    `;
    const runId = latest[0]?.run_id;
    if (!runId) {
      // No precomputed data yet (e.g. a newly added preset the worker hasn't
      // scanned since deploy) — compute live instead of returning empty.
      let rows = liveDays ? await computeLive(sql, preset, liveDays) : [];
      if (onlyActive) rows = rows.filter((r) => !r.stop_triggered);
      sortDesc(rows, sortKey);
      return NextResponse.json({ runId: null, rows: rows.slice(0, limit) }, NO_STORE);
    }

    // Parameterized fetch (two typed branches for the optional active filter).
    const rows = onlyActive
      ? await sql`
          SELECT symbol, company_name, sector, market_cap, current_price,
                 period_gain_pct, momentum_score, volatility, highest_high,
                 trailing_stop_level, distance_to_stop_pct, stop_triggered,
                 volume, avg_volume
          FROM scan_results
          WHERE run_id = ${runId} AND preset = ${preset} AND stop_triggered = false`
      : await sql`
          SELECT symbol, company_name, sector, market_cap, current_price,
                 period_gain_pct, momentum_score, volatility, highest_high,
                 trailing_stop_level, distance_to_stop_pct, stop_triggered,
                 volume, avg_volume
          FROM scan_results
          WHERE run_id = ${runId} AND preset = ${preset}`;

    // Neon returns BIGINT columns as strings, and any numeric column can be
    // null for a symbol with incomplete data — coerce everything to a real
    // finite number so the client never has to defend against NaN/null/string.
    const safeNum = (v: any) => {
      const n = Number(v);
      return Number.isFinite(n) ? n : 0;
    };
    const coerced = rows.map((r: any) => ({
      ...r,
      market_cap: safeNum(r.market_cap),
      volume: safeNum(r.volume),
      avg_volume: safeNum(r.avg_volume),
      current_price: safeNum(r.current_price),
      period_gain_pct: safeNum(r.period_gain_pct),
      momentum_score: safeNum(r.momentum_score),
      volatility: safeNum(r.volatility),
      highest_high: safeNum(r.highest_high),
      trailing_stop_level: safeNum(r.trailing_stop_level),
      distance_to_stop_pct: safeNum(r.distance_to_stop_pct),
    }));

    // Sort by the chosen numeric column (desc) and cap to limit.
    sortDesc(coerced, sortKey);

    return NextResponse.json({ runId, rows: coerced.slice(0, limit) }, NO_STORE);
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
