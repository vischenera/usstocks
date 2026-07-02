// Mirrors worker/config.py PRESETS (keys must match what the worker writes).
export const PRESETS: { key: string; name: string }[] = [
  { key: "conservative_swing", name: "Conservative Swing (30d)" },
  { key: "aggressive_swing", name: "Aggressive Swing (10d)" },
  { key: "momentum", name: "Momentum (10d)" },
  { key: "small_cap", name: "Small Cap (30d)" },
  { key: "day_trading", name: "Day Trading (Intraday)" },
  { key: "all_caps", name: "All Caps (30d)" },
];

export const SORT_OPTIONS: { key: string; label: string }[] = [
  { key: "period_gain_pct", label: "Gain %" },
  { key: "momentum_score", label: "Momentum" },
  { key: "volatility", label: "Volatility" },
  { key: "market_cap", label: "Market Cap" },
];

// Full filter thresholds — mirrors worker/config.py PRESETS. Used when a
// custom period-days is requested and results are computed live instead of
// read from the worker's precomputed scan_results table.
export type PresetDef = {
  periodDays: number; stopPercentage: number;
  minPrice: number; maxPrice: number; minVolume: number;
  minMcap: number; maxMcap: number; minMomentum: number; maxVolatility: number;
  isIntraday: boolean;
};

export const PRESET_DEFS: Record<string, PresetDef> = {
  day_trading: {
    periodDays: 1, stopPercentage: 5,
    minPrice: 10, maxPrice: 500, minVolume: 500_000,
    minMcap: 100_000_000, maxMcap: 50_000_000_000, minMomentum: 0, maxVolatility: 999,
    isIntraday: true,
  },
  aggressive_swing: {
    periodDays: 10, stopPercentage: 10,
    minPrice: 5, maxPrice: 300, minVolume: 200_000,
    minMcap: 50_000_000, maxMcap: 5_000_000_000, minMomentum: 5, maxVolatility: 999,
    isIntraday: false,
  },
  conservative_swing: {
    periodDays: 30, stopPercentage: 15,
    minPrice: 10, maxPrice: 500, minVolume: 100_000,
    minMcap: 100_000_000, maxMcap: 10_000_000_000, minMomentum: 0, maxVolatility: 999,
    isIntraday: false,
  },
  momentum: {
    periodDays: 10, stopPercentage: 12,
    minPrice: 5, maxPrice: 200, minVolume: 300_000,
    minMcap: 50_000_000, maxMcap: 3_000_000_000, minMomentum: 10, maxVolatility: 999,
    isIntraday: false,
  },
  small_cap: {
    periodDays: 30, stopPercentage: 15,
    minPrice: 2, maxPrice: 50, minVolume: 100_000,
    minMcap: 10_000_000, maxMcap: 500_000_000, minMomentum: 0, maxVolatility: 999,
    isIntraday: false,
  },
  all_caps: {
    periodDays: 30, stopPercentage: 15,
    minPrice: 5, maxPrice: 100_000, minVolume: 100_000,
    minMcap: 0, maxMcap: Infinity, minMomentum: 0, maxVolatility: 999,
    isIntraday: false,
  },
};
