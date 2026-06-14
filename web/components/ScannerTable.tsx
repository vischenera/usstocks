"use client";

export type Row = {
  symbol: string;
  company_name: string;
  sector: string;
  market_cap: number;
  current_price: number;
  period_gain_pct: number;
  momentum_score: number;
  volatility: number;
  trailing_stop_level: number;
  distance_to_stop_pct: number;
  stop_triggered: boolean;
  avg_volume: number;
};

const fmtMcap = (v: number) =>
  v >= 1e9 ? `$${(v / 1e9).toFixed(1)}B` : v >= 1e6 ? `$${(v / 1e6).toFixed(0)}M` : `$${v}`;
const fmtVol = (v: number) =>
  v >= 1e6 ? `${(v / 1e6).toFixed(1)}M` : `${(v / 1e3).toFixed(0)}K`;

export default function ScannerTable({ rows }: { rows: Row[] }) {
  if (!rows.length) {
    return <div className="rounded-lg border border-slate-800 p-8 text-center text-slate-400">No matches yet.</div>;
  }
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-800">
      <table className="w-full text-sm">
        <thead className="bg-slate-900 text-left text-slate-400">
          <tr>
            <th className="px-3 py-2">#</th>
            <th className="px-3 py-2">Ticker</th>
            <th className="px-3 py-2">Company</th>
            <th className="px-3 py-2">Sector</th>
            <th className="px-3 py-2 text-right">MCap</th>
            <th className="px-3 py-2 text-right">Gain%</th>
            <th className="px-3 py-2 text-right">Price</th>
            <th className="px-3 py-2 text-right">Stop</th>
            <th className="px-3 py-2 text-right">Vol</th>
            <th className="px-3 py-2 text-right">Mom</th>
            <th className="px-3 py-2 text-center">Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.symbol} className="border-t border-slate-800 hover:bg-slate-900/60">
              <td className="px-3 py-2 text-slate-500">{i + 1}</td>
              <td className="px-3 py-2 font-medium">
                <a className="text-sky-400 hover:underline" href={`/stock/${r.symbol}`}>{r.symbol}</a>
              </td>
              <td className="px-3 py-2 text-slate-300">{(r.company_name || "").slice(0, 28)}</td>
              <td className="px-3 py-2 text-slate-400">{(r.sector || "").slice(0, 16)}</td>
              <td className="px-3 py-2 text-right">{fmtMcap(r.market_cap)}</td>
              <td className={`px-3 py-2 text-right ${r.period_gain_pct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                {r.period_gain_pct.toFixed(1)}%
              </td>
              <td className="px-3 py-2 text-right">${r.current_price.toFixed(2)}</td>
              <td className="px-3 py-2 text-right text-slate-400">${r.trailing_stop_level.toFixed(2)}</td>
              <td className="px-3 py-2 text-right text-slate-400">{fmtVol(r.avg_volume)}</td>
              <td className="px-3 py-2 text-right">{r.momentum_score.toFixed(1)}</td>
              <td className="px-3 py-2 text-center">
                {r.stop_triggered ? (
                  <span className="text-rose-400">✕ Stop</span>
                ) : (
                  <span className="text-emerald-400">● Live</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
