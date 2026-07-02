// Ported from worker/metrics.py — keep both in sync if the formula changes.

export type Bar = { date: string; open: number; high: number; low: number; close: number; volume: number };

export type Metrics = {
  current_price: number;
  period_gain_pct: number;
  momentum_score: number;
  volatility: number;
  highest_high: number;
  trailing_stop_level: number;
  distance_to_stop_pct: number;
  stop_triggered: boolean;
  volume: number;
  avg_volume: number;
};

export function calculateMetrics(
  bars: Bar[],
  periodDays: number,
  stopPercentage: number,
  isIntraday = false
): Metrics | null {
  if (!bars || bars.length < 5) return null;

  const period = bars.length > periodDays ? bars.slice(-periodDays) : bars;
  if (period.length < 2) return null;

  const closes = period.map((b) => b.close);
  const volumes = period.map((b) => b.volume);
  const highs = period.map((b) => b.high);
  const opens = period.map((b) => b.open);

  const currentPrice = closes[closes.length - 1];
  const currentVolume = volumes[volumes.length - 1];
  const avgVolume = volumes.reduce((a, b) => a + b, 0) / volumes.length;

  let startPrice: number;
  let highestHigh: number;
  if (isIntraday && periodDays === 1) {
    startPrice = opens[0];
    highestHigh = Math.max(Math.max(...highs), opens[0]);
  } else {
    startPrice = closes[0];
    highestHigh = Math.max(...highs);
  }
  if (!startPrice || startPrice <= 0) return null;

  const periodGainPct = ((currentPrice - startPrice) / startPrice) * 100;
  const trailingStopLevel = highestHigh * (1 - stopPercentage / 100);
  const distanceToStopPct = currentPrice ? ((currentPrice - trailingStopLevel) / currentPrice) * 100 : 0;
  const stopTriggered = currentPrice < trailingStopLevel;

  let momentumScore = 0;
  if (period.length >= 10) {
    const split = Math.max(3, Math.floor(period.length / 3));
    const recentAvg = closes.slice(-split).reduce((a, b) => a + b, 0) / split;
    const previousCloses = closes.slice(0, -split);
    const previousAvg = previousCloses.reduce((a, b) => a + b, 0) / Math.max(1, previousCloses.length);
    if (previousAvg > 0) {
      const momentumRatio = (recentAvg / previousAvg - 1) * 100;
      const recentVol = volumes.slice(-split).reduce((a, b) => a + b, 0) / split;
      const previousVolumes = volumes.slice(0, -split);
      const previousVol = previousVolumes.reduce((a, b) => a + b, 0) / Math.max(1, previousVolumes.length);
      const volumeRatio = previousVol > 0 ? recentVol / previousVol : 1;
      momentumScore = momentumRatio * (1 + (volumeRatio - 1) * 0.5);
    }
  }

  let volatility = 0;
  if (period.length >= 5) {
    const returns: number[] = [];
    for (let i = 1; i < closes.length; i++) {
      if (closes[i - 1]) returns.push(closes[i] / closes[i - 1] - 1);
    }
    if (returns.length >= 2) {
      const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
      const variance = returns.reduce((a, r) => a + (r - mean) ** 2, 0) / (returns.length - 1);
      volatility = Math.sqrt(variance) * Math.sqrt(252) * 100;
    }
  }

  return {
    current_price: currentPrice,
    period_gain_pct: periodGainPct,
    momentum_score: momentumScore,
    volatility,
    highest_high: highestHigh,
    trailing_stop_level: trailingStopLevel,
    distance_to_stop_pct: distanceToStopPct,
    stop_triggered: stopTriggered,
    volume: currentVolume,
    avg_volume: avgVolume,
  };
}
