"use client";

import { useMemo, useState } from "react";

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

// DB columns can arrive as null/string/NaN depending on source (worker vs.
// live-compute) — never trust a raw field before calling .toFixed() on it.
const num = (v: unknown): number => {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
};
const fmt = (v: unknown, digits: number) => num(v).toFixed(digits);

const fmtMcap = (v: unknown) => {
  const n = num(v);
  return n >= 1e9 ? `$${(n / 1e9).toFixed(1)}B` : n >= 1e6 ? `$${(n / 1e6).toFixed(0)}M` : `$${n}`;
};
const fmtVol = (v: unknown) => {
  const n = num(v);
  return n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : `${(n / 1e3).toFixed(0)}K`;
};

type ColumnKey =
  | "symbol" | "company_name" | "sector" | "market_cap" | "period_gain_pct"
  | "current_price" | "trailing_stop_level" | "avg_volume" | "momentum_score";

const COLUMNS: { key: ColumnKey; label: string; align?: "right" | "center" }[] = [
  { key: "symbol", label: "Ticker" },
  { key: "company_name", label: "Company" },
  { key: "sector", label: "Sector" },
  { key: "market_cap", label: "MCap", align: "right" },
  { key: "period_gain_pct", label: "Gain%", align: "right" },
  { key: "current_price", label: "Price", align: "right" },
  { key: "trailing_stop_level", label: "Stop", align: "right" },
  { key: "avg_volume", label: "Vol", align: "right" },
  { key: "momentum_score", label: "Mom", align: "right" },
];

export default function ScannerTable({ rows }: { rows: Row[] }) {
  const [sortKey, setSortKey] = useState<ColumnKey | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const sorted = useMemo(() => {
    if (!sortKey) return rows;
    const copy = [...rows];
    copy.sort((a, b) => {
      const av = a[sortKey], bv = b[sortKey];
      const cmp = typeof av === "string" ? String(av).localeCompare(String(bv)) : Number(av) - Number(bv);
      return sortDir === "asc" ? cmp : -cmp;
    });
    return copy;
  }, [rows, sortKey, sortDir]);

  const onHeaderClick = (key: ColumnKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  if (!rows.length) {
    return <div className="rounded-lg border border-slate-800 p-8 text-center text-slate-400">No matches yet.</div>;
  }
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-800">
      <table className="w-full text-sm">
        <thead className="bg-slate-900 text-left text-slate-400">
          <tr>
            <th className="px-3 py-2">#</th>
            {COLUMNS.map((c) => (
              <th key={c.key} className={`cursor-pointer select-none px-3 py-2 hover:text-slate-200 ${c.align === "right" ? "text-right" : ""}`}
                onClick={() => onHeaderClick(c.key)}>
                {c.label}{sortKey === c.key ? (sortDir === "asc" ? " ▲" : " ▼") : ""}
              </th>
            ))}
            <th className="px-3 py-2 text-center">Status</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((r, i) => (
            <tr key={r.symbol} className="border-t border-slate-800 hover:bg-slate-900/60">
              <td className="px-3 py-2 text-slate-500">{i + 1}</td>
              <td className="px-3 py-2 font-medium">
                <a className="text-sky-400 hover:underline" href={`/stock/${r.symbol}`}>{r.symbol}</a>
              </td>
              <td className="px-3 py-2 text-slate-300">{(r.company_name || "").slice(0, 28)}</td>
              <td className="px-3 py-2 text-slate-400">{(r.sector || "").slice(0, 16)}</td>
              <td className="px-3 py-2 text-right">{fmtMcap(r.market_cap)}</td>
              <td className={`px-3 py-2 text-right ${num(r.period_gain_pct) >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                {fmt(r.period_gain_pct, 1)}%
              </td>
              <td className="px-3 py-2 text-right">${fmt(r.current_price, 2)}</td>
              <td className="px-3 py-2 text-right text-slate-400">${fmt(r.trailing_stop_level, 2)}</td>
              <td className="px-3 py-2 text-right text-slate-400">{fmtVol(r.avg_volume)}</td>
              <td className="px-3 py-2 text-right">{fmt(r.momentum_score, 1)}</td>
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
