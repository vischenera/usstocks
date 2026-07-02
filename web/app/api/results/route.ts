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

// Recompute results live from stored OHLCV for a custom day-window, using the
// preset's other filter thresholds unchanged. Only hit when `days` differs
// from the preset's own default — otherwise the precomputed path below (fast,
// worker-side) is used.
async function computeLive(sql: ReturnType<typeof getSql>, preset: string, days: number) {
  const def = PRESET_DEFS[preset];
  if (!def) return [];

  const barRows = await sql`
    SELECT symbol, to_char(date, 'YYYY-MM-DD') AS date, open, high, low, close, volume
    FROM (
      SELECT *, row_number() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
      FROM daily_ohlcv WHERE close IS NOT NULL
    ) t
    WHERE rn <= ${days}
    ORDER BY symbol, date ASC
  `;
  const bySymbol = new Map<string, Bar[]>();
  for (const r of barRows as any[]) {
    const bars = bySymbol.get(r.symbol) ?? [];
    bars.push({ date: r.date, open: r.open, high: r.high, low: r.low, close: r.close, volume: Number(r.volume) });
    bySymbol.set(r.symbol, bars);
  }

  const metaRows = await sql`SELECT symbol, company_name, sector, market_cap FROM tickers`;
  const meta = new Map<string, { company_name: string; sector: string; market_cap: number }>();
  for (const r of metaRows as any[]) {
    meta.set(r.symbol, { company_name: r.company_name, sector: r.sector, market_cap: Number(r.market_cap) || 0 });
  }

  const rows: any[] = [];
  for (const [symbol, bars] of bySymbol) {
    const m = meta.get(symbol) ?? { company_name: symbol, sector: "N/A", market_cap: 0 };
    const metrics = calculateMetrics(bars, days, def.stopPercentage, def.isIntraday);
    if (!metrics) continue;
    if (metrics.current_price < def.minPrice || metrics.current_price > def.maxPrice) continue;
    if (metrics.avg_volume < def.minVolume) continue;
    if (m.market_cap < def.minMcap || m.market_cap > def.maxMcap) continue;
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
    const daysParam = p.get("days");
    const days = daysParam ? Math.min(90, Math.max(1, Number(daysParam))) : null;

    if (days && days !== PRESET_DEFS[preset]?.periodDays) {
      let rows = await computeLive(sql, preset, days);
      if (onlyActive) rows = rows.filter((r) => !r.stop_triggered);
      rows.sort((a, b) => (Number(b[sortKey]) || -Infinity) - (Number(a[sortKey]) || -Infinity));
      return NextResponse.json({ runId: null, rows: rows.slice(0, limit) }, NO_STORE);
    }

    // Latest run that actually has rows for this preset.
    const latest = await sql`
      SELECT max(run_id) AS run_id FROM scan_results WHERE preset = ${preset}
    `;
    const runId = latest[0]?.run_id;
    if (!runId) return NextResponse.json({ runId: null, rows: [] }, NO_STORE);

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

    // Neon returns BIGINT columns as strings — coerce to numbers so the
    // Row type is honest and sorting/formatting is safe.
    const coerced = rows.map((r: any) => ({
      ...r,
      market_cap: Number(r.market_cap),
      volume: Number(r.volume),
      avg_volume: Number(r.avg_volume),
    }));

    // Sort by the chosen numeric column (desc) and cap to limit.
    coerced.sort((a: any, b: any) => (Number(b[sortKey]) || -Infinity) - (Number(a[sortKey]) || -Infinity));

    return NextResponse.json({ runId, rows: coerced.slice(0, limit) }, NO_STORE);
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
