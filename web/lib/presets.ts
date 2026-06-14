// Mirrors worker/config.py PRESETS (keys must match what the worker writes).
export const PRESETS: { key: string; name: string }[] = [
  { key: "conservative_swing", name: "Conservative Swing (30d)" },
  { key: "aggressive_swing", name: "Aggressive Swing (10d)" },
  { key: "momentum", name: "Momentum (10d)" },
  { key: "small_cap", name: "Small Cap (30d)" },
  { key: "day_trading", name: "Day Trading (Intraday)" },
];

export const SORT_OPTIONS: { key: string; label: string }[] = [
  { key: "period_gain_pct", label: "Gain %" },
  { key: "momentum_score", label: "Momentum" },
  { key: "volatility", label: "Volatility" },
  { key: "market_cap", label: "Market Cap" },
];
