"use client";

import { useEffect, useState } from "react";

type OpenPos = {
  id: number; symbol: string; entry_date: string; entry_price: number;
  shares: number; cost: number; last_close: number; value: number;
  stop_level: number; unrealized_pnl: number; unrealized_pct: number;
};
type ClosedTrade = {
  id: number; symbol: string; entry_date: string; entry_price: number;
  shares: number; cost: number; exit_date: string; exit_price: number;
  exit_reason: string; pnl: number; pnl_pct: number;
};
type BotData = {
  config: { capital: number; slots: number; start_days: number; slippage_pct: number } | null;
  equity: { date: string; equity: number; cash: number }[];
  open: OpenPos[];
  closed: ClosedTrade[];
  summary: {
    realized_pnl: number; open_pnl: number; trades: number; wins: number;
    win_rate: number; equity_now: number; cash_now: number;
  };
};

const fmt$ = (v: number) => `$${v.toFixed(2)}`;
const fmtPnl = (v: number) => `${v >= 0 ? "+" : "−"}$${Math.abs(v).toFixed(2)}`;
const pnlCls = (v: number) => (v >= 0 ? "text-emerald-400" : "text-rose-400");

function EquityChart({ data }: { data: { date: string; equity: number }[] }) {
  if (data.length < 2) return null;
  const w = 720, h = 160, pad = 6;
  const vals = data.map((d) => d.equity);
  const min = Math.min(...vals), max = Math.max(...vals);
  const span = max - min || 1;
  const pts = vals.map((v, i) =>
    `${(pad + (i * (w - 2 * pad)) / (vals.length - 1)).toFixed(1)},${(h - pad - ((v - min) / span) * (h - 2 * pad)).toFixed(1)}`
  ).join(" ");
  return (
    <div className="rounded-lg border border-slate-800 p-3">
      <div className="mb-1 flex justify-between text-xs text-slate-400">
        <span>Equity — {data[0].date} → {data[data.length - 1].date}</span>
        <span>low {fmt$(min)} · high {fmt$(max)}</span>
      </div>
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full" aria-label="Equity curve">
        <polyline points={pts} fill="none" stroke="#38bdf8" strokeWidth="2"
          strokeLinejoin="round" strokeLinecap="round" />
      </svg>
    </div>
  );
}

function Tile({ label, value, cls }: { label: string; value: string; cls?: string }) {
  return (
    <div className="rounded-lg border border-slate-800 px-4 py-3">
      <div className="text-xs text-slate-400">{label}</div>
      <div className={`text-lg font-semibold ${cls ?? ""}`}>{value}</div>
    </div>
  );
}

export default function BotPage() {
  const [data, setData] = useState<BotData | null>(null);
  const [form, setForm] = useState({ capital: "1000", slots: "5", start_days: "90", slippage_pct: "0.25" });
  const [saving, setSaving] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const load = () =>
    fetch("/api/bot")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!d) return;
        setData(d);
        if (d.config) {
          setForm({
            capital: String(d.config.capital),
            slots: String(d.config.slots),
            start_days: String(d.config.start_days),
            slippage_pct: String(d.config.slippage_pct),
          });
        }
      })
      .catch(() => {});

  useEffect(() => { load(); }, []);

  const save = async () => {
    setSaving(true);
    setNote(null);
    try {
      const res = await fetch("/api/bot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          capital: Number(form.capital),
          slots: Number(form.slots),
          start_days: Number(form.start_days),
          slippage_pct: Number(form.slippage_pct),
        }),
      });
      const d = await res.json();
      setNote(res.ok ? d.note : d.error ?? "Save failed");
    } catch {
      setNote("Save failed");
    } finally {
      setSaving(false);
    }
  };

  const s = data?.summary;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <a href="/" className="text-sm text-sky-400 hover:underline">← Scanner</a>
          <h1 className="text-2xl font-semibold">Paper Bot</h1>
          <p className="text-sm text-slate-400">
            Trades the Breakout signals with virtual money — EOD signals, next-day fills,
            10% trail + fading step-out. Replays on every scan run.
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-4 rounded-lg border border-slate-800 p-4">
        {([
          ["Capital ($)", "capital"],
          ["Slots", "slots"],
          ["Start (days)", "start_days"],
          ["Slippage (%)", "slippage_pct"],
        ] as const).map(([label, key]) => (
          <label key={key} className="text-sm">
            <span className="mb-1 block text-slate-400">{label}</span>
            <input type="number" value={form[key]}
              onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
              className="w-28 rounded border border-slate-700 bg-slate-900 px-3 py-1.5" />
          </label>
        ))}
        <button onClick={save} disabled={saving}
          className="rounded bg-sky-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-sky-500 disabled:bg-slate-800 disabled:text-slate-500">
          {saving ? "Saving…" : "Save config"}
        </button>
        {note && <span className="pb-2 text-sm text-slate-400">{note}</span>}
      </div>

      {!data || !data.equity.length ? (
        <div className="rounded-lg border border-slate-800 p-8 text-center text-slate-400">
          No simulation results yet — the bot runs as part of the worker scan.
          Trigger <span className="text-slate-300">Actions → scan → Run workflow</span> (or wait for the next scheduled run).
        </div>
      ) : (
        <>
          {s && (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
              <Tile label="Equity" value={fmt$(s.equity_now)} />
              <Tile label="Cash" value={fmt$(s.cash_now)} />
              <Tile label="Realized P&L" value={fmtPnl(s.realized_pnl)} cls={pnlCls(s.realized_pnl)} />
              <Tile label="Open P&L" value={fmtPnl(s.open_pnl)} cls={pnlCls(s.open_pnl)} />
              <Tile label="Closed trades" value={String(s.trades)} />
              <Tile label="Win rate" value={`${s.win_rate.toFixed(0)}%`} />
            </div>
          )}

          <EquityChart data={data.equity} />

          <div>
            <h2 className="mb-2 text-lg font-medium">Open positions ({data.open.length})</h2>
            {data.open.length ? (
              <div className="overflow-x-auto rounded-lg border border-slate-800">
                <table className="w-full text-sm">
                  <thead className="bg-slate-900 text-left text-slate-400">
                    <tr>
                      <th className="px-3 py-2">Ticker</th>
                      <th className="px-3 py-2">Entry date</th>
                      <th className="px-3 py-2 text-right">Entry</th>
                      <th className="px-3 py-2 text-right">Shares</th>
                      <th className="px-3 py-2 text-right">Now</th>
                      <th className="px-3 py-2 text-right">Open P&L</th>
                      <th className="px-3 py-2 text-right">Expected exit</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.open.map((p) => (
                      <tr key={p.id} className="border-t border-slate-800">
                        <td className="px-3 py-2 font-medium">
                          <a className="text-sky-400 hover:underline" href={`/stock/${p.symbol}`}>{p.symbol}</a>
                        </td>
                        <td className="px-3 py-2 text-slate-400">{p.entry_date}</td>
                        <td className="px-3 py-2 text-right">{fmt$(p.entry_price)}</td>
                        <td className="px-3 py-2 text-right text-slate-400">{p.shares.toFixed(3)}</td>
                        <td className="px-3 py-2 text-right">{fmt$(p.last_close)}</td>
                        <td className={`px-3 py-2 text-right ${pnlCls(p.unrealized_pnl)}`}>
                          {fmtPnl(p.unrealized_pnl)} ({p.unrealized_pct >= 0 ? "+" : ""}{p.unrealized_pct.toFixed(1)}%)
                        </td>
                        <td className="px-3 py-2 text-right text-slate-400">{fmt$(p.stop_level)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-slate-500">None — all slots in cash.</p>
            )}
          </div>

          <div>
            <h2 className="mb-2 text-lg font-medium">Closed trades ({data.closed.length})</h2>
            <div className="overflow-x-auto rounded-lg border border-slate-800">
              <table className="w-full text-sm">
                <thead className="bg-slate-900 text-left text-slate-400">
                  <tr>
                    <th className="px-3 py-2">Ticker</th>
                    <th className="px-3 py-2">Entry</th>
                    <th className="px-3 py-2">Exit</th>
                    <th className="px-3 py-2 text-right">In</th>
                    <th className="px-3 py-2 text-right">Out</th>
                    <th className="px-3 py-2">Reason</th>
                    <th className="px-3 py-2 text-right">P&L</th>
                  </tr>
                </thead>
                <tbody>
                  {data.closed.map((t) => (
                    <tr key={t.id} className="border-t border-slate-800">
                      <td className="px-3 py-2 font-medium">
                        <a className="text-sky-400 hover:underline" href={`/stock/${t.symbol}`}>{t.symbol}</a>
                      </td>
                      <td className="px-3 py-2 text-slate-400">{t.entry_date}</td>
                      <td className="px-3 py-2 text-slate-400">{t.exit_date}</td>
                      <td className="px-3 py-2 text-right">{fmt$(t.entry_price)}</td>
                      <td className="px-3 py-2 text-right">{fmt$(t.exit_price)}</td>
                      <td className="px-3 py-2 text-slate-400">{t.exit_reason}</td>
                      <td className={`px-3 py-2 text-right ${pnlCls(t.pnl)}`}>
                        {fmtPnl(t.pnl)} ({t.pnl_pct >= 0 ? "+" : ""}{t.pnl_pct.toFixed(1)}%)
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
