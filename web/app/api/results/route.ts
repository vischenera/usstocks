import { NextRequest, NextResponse } from "next/server";
import { getSql } from "@/lib/db";

export const dynamic = "force-dynamic";

// Whitelist sortable columns (all numeric) — used for JS sort, never interpolated into SQL.
const SORTABLE = new Set([
  "period_gain_pct", "momentum_score", "volatility", "market_cap", "current_price",
]);

export async function GET(req: NextRequest) {
  try {
    const sql = getSql();
    const p = req.nextUrl.searchParams;
    const preset = p.get("preset") || "conservative_swing";
    const sortKey = SORTABLE.has(p.get("sort") || "") ? (p.get("sort") as string) : "period_gain_pct";
    const limit = Math.min(1000, Math.max(1, Number(p.get("limit") || 300)));
    const onlyActive = p.get("onlyActive") === "1";

    // Latest run that actually has rows for this preset.
    const latest = await sql`
      SELECT max(run_id) AS run_id FROM scan_results WHERE preset = ${preset}
    `;
    const runId = latest[0]?.run_id;
    if (!runId) return NextResponse.json({ runId: null, rows: [] });

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

    return NextResponse.json({ runId, rows: coerced.slice(0, limit) });
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
