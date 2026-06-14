"""Momentum / trailing-stop / volatility metrics.

Ported from the original v3.0 `calculate_metrics`. Operates on an ascending list
of bar dicts: {date, open, high, low, close, volume}.
"""

import math


def calculate_metrics(bars, period_days, stop_percentage, is_intraday=False):
    """Return a metrics dict, or None if there isn't enough data."""
    if not bars or len(bars) < 5:
        return None

    period = bars[-period_days:] if len(bars) > period_days else bars
    if len(period) < 2:
        return None

    try:
        closes = [b["close"] for b in period]
        volumes = [b["volume"] for b in period]
        highs = [b["high"] for b in period]
        opens = [b["open"] for b in period]

        current_price = closes[-1]
        current_volume = volumes[-1]
        avg_volume = sum(volumes) / len(volumes)

        if is_intraday and period_days == 1:
            start_price = opens[0]
            highest_high = max(max(highs), opens[0])
        else:
            start_price = closes[0]
            highest_high = max(highs)

        if not start_price or start_price <= 0:
            return None

        period_gain_pct = ((current_price - start_price) / start_price) * 100

        trailing_stop_level = highest_high * (1 - stop_percentage / 100.0)
        distance_to_stop_pct = (
            ((current_price - trailing_stop_level) / current_price) * 100
            if current_price else 0
        )
        stop_triggered = current_price < trailing_stop_level

        # Momentum: recent vs previous average, scaled by volume expansion.
        momentum_score = 0.0
        if len(period) >= 10:
            split = max(3, len(period) // 3)
            recent_avg = sum(closes[-split:]) / split
            previous_avg = sum(closes[:-split]) / max(1, len(closes) - split)
            if previous_avg > 0:
                momentum_ratio = (recent_avg / previous_avg - 1) * 100
                recent_vol = sum(volumes[-split:]) / split
                previous_vol = sum(volumes[:-split]) / max(1, len(volumes) - split)
                volume_ratio = (recent_vol / previous_vol) if previous_vol > 0 else 1
                momentum_score = momentum_ratio * (1 + (volume_ratio - 1) * 0.5)

        # Annualised volatility from daily returns.
        volatility = 0.0
        if len(period) >= 5:
            returns = [
                (closes[i] / closes[i - 1] - 1)
                for i in range(1, len(closes)) if closes[i - 1]
            ]
            if len(returns) >= 2:
                mean = sum(returns) / len(returns)
                var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
                volatility = math.sqrt(var) * math.sqrt(252) * 100

        return {
            "current_price": float(current_price),
            "period_gain_pct": float(period_gain_pct),
            "momentum_score": float(momentum_score),
            "volatility": float(volatility),
            "highest_high": float(highest_high),
            "trailing_stop_level": float(trailing_stop_level),
            "distance_to_stop_pct": float(distance_to_stop_pct),
            "stop_triggered": bool(stop_triggered),
            "volume": int(current_volume),
            "avg_volume": int(avg_volume),
        }
    except (KeyError, TypeError, ZeroDivisionError):
        return None
