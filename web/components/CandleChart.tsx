"use client";

import { useEffect, useRef } from "react";
import { createChart, ColorType, IChartApi } from "lightweight-charts";
import { autoFlippingTrail, Bar } from "@/lib/trail";

export default function CandleChart({ bars, stopPct = 10 }: { bars: Bar[]; stopPct?: number }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || bars.length === 0) return;

    const chart: IChartApi = createChart(ref.current, {
      layout: { background: { type: ColorType.Solid, color: "#020617" }, textColor: "#cbd5e1" },
      grid: { vertLines: { color: "#1e293b" }, horzLines: { color: "#1e293b" } },
      height: 460,
      timeScale: { borderColor: "#334155" },
      rightPriceScale: { borderColor: "#334155" },
    });

    const candles = chart.addCandlestickSeries({
      upColor: "#10b981", downColor: "#ef4444",
      borderUpColor: "#10b981", borderDownColor: "#ef4444",
      wickUpColor: "#10b981", wickDownColor: "#ef4444",
    });
    candles.setData(bars.map((b) => ({ time: b.date, open: b.open, high: b.high, low: b.low, close: b.close })));

    // Auto-flipping trailing stop overlay. Split into LONG/SHORT colored lines.
    const { points, flips } = autoFlippingTrail(bars, stopPct);
    const longLine = chart.addLineSeries({ color: "#22c55e", lineWidth: 2 });
    const shortLine = chart.addLineSeries({ color: "#f97316", lineWidth: 2 });
    longLine.setData(points.map((p) => ({ time: p.date, value: p.direction === "LONG" ? p.trail : NaN })) as any);
    shortLine.setData(points.map((p) => ({ time: p.date, value: p.direction === "SHORT" ? p.trail : NaN })) as any);

    if (flips.length) {
      candles.setMarkers(
        flips.map((i) => ({
          time: bars[i].date,
          position: points[i].direction === "LONG" ? "belowBar" : "aboveBar",
          color: points[i].direction === "LONG" ? "#22c55e" : "#f97316",
          shape: points[i].direction === "LONG" ? "arrowUp" : "arrowDown",
          text: points[i].direction,
        })) as any
      );
    }

    chart.timeScale().fitContent();
    const onResize = () => chart.applyOptions({ width: ref.current!.clientWidth });
    onResize();
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      chart.remove();
    };
  }, [bars, stopPct]);

  return <div ref={ref} className="w-full" />;
}
