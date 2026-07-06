import { NextRequest, NextResponse } from "next/server";
import { getSql } from "@/lib/db";
import { ensureBotTables } from "@/lib/botSchema";

export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";

const NO_STORE = { headers: { "Cache-Control": "no-store, max-age=0" } };

const num = (v: any) => {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
};

// Bot state: config, equity curve, open positions (marked to latest close),
// and the closed-trade log. All data is produced by the worker's replay.
export async function GET() {
  try {
    const sql = getSql();
    await ensureBotTables(sql);
    const [cfgRows, equityRows, tradeRows] = await Promise.all([
      sql`SELECT capital, slots, start_days, slippage_pct, updated_at FROM bot_config WHERE id = 1`,
      sql`SELECT to_char(date, 'YYYY-MM-DD') AS date, equity, cash FROM bot_equity ORDER BY date ASC`,
      sql`
        SELECT t.id, t.symbol, to_char(t.entry_date, 'YYYY-MM-DD') AS entry_date,
               t.entry_price, t.shares, t.cost, t.stop_level,
               to_char(t.exit_date, 'YYYY-MM-DD') AS exit_date,
               t.exit_price, t.exit_reason, t.pnl,
               lc.close AS last_close
        FROM bot_trades t
        LEFT JOIN LATERAL (
          SELECT close FROM daily_ohlcv
          WHERE symbol = t.symbol AND close IS NOT NULL
          ORDER BY date DESC LIMIT 1
        ) lc ON true
        ORDER BY t.entry_date DESC, t.id DESC
      `,
    ]);

    const config = cfgRows[0]
      ? {
          capital: num(cfgRows[0].capital),
          slots: num(cfgRows[0].slots),
          start_days: num(cfgRows[0].start_days),
          slippage_pct: num(cfgRows[0].slippage_pct),
          updated_at: cfgRows[0].updated_at,
        }
      : null;

    const open: any[] = [];
    const closed: any[] = [];
    for (const t of tradeRows as any[]) {
      const base = {
        id: t.id,
        symbol: t.symbol,
        entry_date: t.entry_date,
        entry_price: num(t.entry_price),
        shares: num(t.shares),
        cost: num(t.cost),
      };
      if (t.exit_date) {
        closed.push({
          ...base,
          exit_date: t.exit_date,
          exit_price: num(t.exit_price),
          exit_reason: t.exit_reason,
          pnl: num(t.pnl),
          pnl_pct: num(t.cost) > 0 ? (num(t.pnl) / num(t.cost)) * 100 : 0,
        });
      } else {
        const last = num(t.last_close) || num(t.entry_price);
        const value = num(t.shares) * last;
        open.push({
          ...base,
          last_close: last,
          value,
          stop_level: num(t.stop_level),
          unrealized_pnl: value - num(t.cost),
          unrealized_pct: num(t.cost) > 0 ? ((value - num(t.cost)) / num(t.cost)) * 100 : 0,
        });
      }
    }

    const realized = closed.reduce((a, t) => a + t.pnl, 0);
    const wins = closed.filter((t) => t.pnl > 0).length;
    const equity = (equityRows as any[]).map((r) => ({
      date: r.date, equity: num(r.equity), cash: num(r.cash),
    }));

    return NextResponse.json(
      {
        config,
        equity,
        open,
        closed,
        summary: {
          realized_pnl: realized,
          open_pnl: open.reduce((a, t) => a + t.unrealized_pnl, 0),
          trades: closed.length,
          wins,
          win_rate: closed.length ? (wins / closed.length) * 100 : 0,
          equity_now: equity.length ? equity[equity.length - 1].equity : config?.capital ?? 0,
          cash_now: equity.length ? equity[equity.length - 1].cash : config?.capital ?? 0,
        },
      },
      NO_STORE,
    );
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}

// Update config. Takes effect on the next "Run now" replay.
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const capital = Number(body.capital);
    const slots = Number(body.slots);
    const startDays = Number(body.start_days);
    const slippage = Number(body.slippage_pct);
    if (!Number.isFinite(capital) || capital <= 0) {
      return NextResponse.json({ error: "capital must be > 0" }, { status: 400 });
    }
    if (!Number.isInteger(slots) || slots < 1 || slots > 50) {
      return NextResponse.json({ error: "slots must be 1-50" }, { status: 400 });
    }
    if (!Number.isInteger(startDays) || startDays < 10 || startDays > 90) {
      return NextResponse.json({ error: "start_days must be 10-90" }, { status: 400 });
    }
    if (!Number.isFinite(slippage) || slippage < 0 || slippage > 5) {
      return NextResponse.json({ error: "slippage_pct must be 0-5" }, { status: 400 });
    }
    const sql = getSql();
    await ensureBotTables(sql);
    await sql`
      INSERT INTO bot_config (id, capital, slots, start_days, slippage_pct, updated_at)
      VALUES (1, ${capital}, ${slots}, ${startDays}, ${slippage}, now())
      ON CONFLICT (id) DO UPDATE SET
        capital = EXCLUDED.capital, slots = EXCLUDED.slots,
        start_days = EXCLUDED.start_days, slippage_pct = EXCLUDED.slippage_pct,
        updated_at = now()
    `;
    return NextResponse.json({ ok: true, note: "Config saved — hit Run now to replay." }, NO_STORE);
  } catch (e: any) {
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}
