"use client";

import { useEffect, useState } from "react";
import CandleChart from "@/components/CandleChart";
import { Bar } from "@/lib/trail";

export default function StockPage({ params }: { params: { ticker: string } }) {
  const symbol = params.ticker.toUpperCase();
  const [bars, setBars] = useState<Bar[]>([]);
  const [meta, setMeta] = useState<any>(null);
  const [stopPct, setStopPct] = useState(10);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`/api/ohlcv/${symbol}?days=90`)
      .then((r) => r.json())
      .then((d) => {
        setBars(d.bars || []);
        setMeta(d.meta || null);
      })
      .finally(() => setLoading(false));
  }, [symbol]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <a href="/" className="text-sm text-sky-400 hover:underline">← Back</a>
          <h1 className="text-2xl font-semibold">{symbol}</h1>
          {meta && <p className="text-slate-400">{meta.company_name} · {meta.sector}</p>}
        </div>
        <label className="text-sm">
          <span className="mb-1 block text-slate-400">Trailing stop %</span>
          <select value={stopPct} onChange={(e) => setStopPct(Number(e.target.value))}
            className="rounded border border-slate-700 bg-slate-900 px-3 py-1.5">
            {[5, 8, 10, 12, 15, 20].map((v) => <option key={v} value={v}>{v}%</option>)}
          </select>
        </label>
      </div>

      {loading ? (
        <div className="rounded-lg border border-slate-800 p-8 text-center text-slate-400">Loading chart…</div>
      ) : bars.length ? (
        <div className="rounded-lg border border-slate-800 p-2">
          <CandleChart bars={bars} stopPct={stopPct} />
          <p className="px-2 py-2 text-xs text-slate-500">
            Green line = LONG trailing stop, orange = SHORT. Arrows mark auto-flips.
          </p>
        </div>
      ) : (
        <div className="rounded-lg border border-slate-800 p-8 text-center text-slate-400">
          No data for {symbol} yet.
        </div>
      )}
    </div>
  );
}
