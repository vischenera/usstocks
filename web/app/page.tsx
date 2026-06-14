"use client";

import { useEffect, useState } from "react";
import StatusPanel from "@/components/StatusPanel";
import ScannerTable, { Row } from "@/components/ScannerTable";
import { PRESETS, SORT_OPTIONS } from "@/lib/presets";

export default function Dashboard() {
  const [status, setStatus] = useState<any>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [preset, setPreset] = useState(PRESETS[0].key);
  const [sort, setSort] = useState(SORT_OPTIONS[0].key);
  const [onlyActive, setOnlyActive] = useState(true);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch("/api/status").then((r) => r.json()).then(setStatus).catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    const qs = new URLSearchParams({ preset, sort, limit: "300", onlyActive: onlyActive ? "1" : "0" });
    fetch(`/api/results?${qs}`)
      .then((r) => r.json())
      .then((d) => setRows(d.rows || []))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, [preset, sort, onlyActive]);

  return (
    <div className="space-y-5">
      <StatusPanel status={status} />

      <div className="flex flex-wrap items-end gap-4">
        <label className="text-sm">
          <span className="mb-1 block text-slate-400">Preset</span>
          <select value={preset} onChange={(e) => setPreset(e.target.value)}
            className="rounded border border-slate-700 bg-slate-900 px-3 py-1.5">
            {PRESETS.map((p) => <option key={p.key} value={p.key}>{p.name}</option>)}
          </select>
        </label>
        <label className="text-sm">
          <span className="mb-1 block text-slate-400">Sort by</span>
          <select value={sort} onChange={(e) => setSort(e.target.value)}
            className="rounded border border-slate-700 bg-slate-900 px-3 py-1.5">
            {SORT_OPTIONS.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={onlyActive} onChange={(e) => setOnlyActive(e.target.checked)} />
          <span>Active only (stop not triggered)</span>
        </label>
        {loading && <span className="text-sm text-slate-500">Loading…</span>}
      </div>

      <ScannerTable rows={rows} />
    </div>
  );
}
