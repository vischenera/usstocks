#!/usr/bin/env python3
"""
Momentum Chart Viewer with Auto-Flipping Trailing Stop Loss (% of Price)
Displays candlestick charts with dynamic trails from cached data
"""

import pickle
import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, session
import pandas as pd
import numpy as np

app = Flask(__name__)
app.secret_key = 'momentum_chart_viewer_secret_key_2025'  # For session management

CACHE_DIR = '.'


def cleanup_old_cache_files():
    """Remove slope score cache files older than 1 day"""
    try:
        import time
        current_time = time.time()
        for filename in os.listdir('.'):
            if filename.startswith('slope_scores_cache_') and filename.endswith('.pkl'):
                filepath = os.path.join('.', filename)
                # Check if file is older than 24 hours
                if os.path.getmtime(filepath) < current_time - 86400:
                    os.remove(filepath)
                    print(f"Removed old cache file: {filename}")
    except Exception as e:
        print(f"Error cleaning cache files: {e}")


def load_cached_data():
    """Load all cached stock data - handles list-of-dicts from scanner"""
    cache_file = 'stock_data_cache.pkl'
    if not os.path.exists(cache_file):
        return {}

    try:
        with open(cache_file, 'rb') as f:
            raw_data = pickle.load(f)

        cached_data = {}
        skipped_count = 0
        if isinstance(raw_data, list):
            for item in raw_data:
                if isinstance(item, dict) and 'ticker' in item:
                    ticker = item['ticker']
                    if all(key in item for key in ['current_price', 'avg_volume', 'market_cap', 'historical_data']):
                        hist_len = len(item['historical_data'])
                        if isinstance(item['historical_data'], pd.DataFrame) and hist_len > 0:
                            if hist_len < 2:
                                print(f"⚠ Low data for {ticker}: {hist_len} row(s) - defaulting to LONG in charts")
                            cached_data[ticker] = item
                        else:
                            print(f"⚠ Skipping {ticker}: Empty/Invalid historical_data")
                            skipped_count += 1
                    else:
                        print(f"⚠ Skipping {ticker}: Missing required keys")
                        skipped_count += 1
            print(f"✓ Loaded {len(cached_data)} stocks from list format (skipped {skipped_count})")
        elif isinstance(raw_data, dict):
            cached_data = raw_data
            print(f"✓ Loaded {len(cached_data)} stocks from dict format")
        else:
            print("⚠ Invalid cache format - expected list or dict")
            return {}

        return cached_data
    except Exception as e:
        print(f"⚠ Error loading cache: {e}")
        return {}


def calculate_auto_flipping_trail(df, initial_direction='LONG', stop_pct=10.0):
    """Calculate auto-flipping trailing stop using % of price

    LONG: Trail starts at entry - stop%, rises as price rises, stops when hit
    SHORT: Trail starts at entry + stop%, falls as price falls, stops when hit
    """
    df = df.copy()

    trails = []
    directions = []
    flip_indices = []
    current_direction = initial_direction
    current_trail = None
    stop_multiplier = stop_pct / 100.0

    for i in range(len(df)):
        row = df.iloc[i]
        close = row['Close']
        high = row['High']
        low = row['Low']

        if pd.isna(close) or pd.isna(high) or pd.isna(low):
            # Skip invalid rows
            trails.append(np.nan)
            directions.append(current_direction)
            continue

        # Initialize trail on first bar
        if current_trail is None:
            if current_direction == 'LONG':
                current_trail = close * (1 - stop_multiplier)
            else:
                current_trail = close * (1 + stop_multiplier)
            trails.append(current_trail)
            directions.append(current_direction)
            continue

        # Check for flip BEFORE updating trail
        if current_direction == 'LONG':
            # Check if low hit the trail (stop out)
            if low <= current_trail:
                flip_indices.append(i)
                current_direction = 'SHORT'
                # Set new trail for SHORT position
                current_trail = high * (1 + stop_multiplier)  # Use high of flip bar
                trails.append(current_trail)
                directions.append(current_direction)
                continue

            # No flip - update LONG trail (only move up)
            new_trail = close * (1 - stop_multiplier)
            current_trail = max(current_trail, new_trail)  # Trail only rises

        else:  # SHORT
            # Check if high hit the trail (stop out)
            if high >= current_trail:
                flip_indices.append(i)
                current_direction = 'LONG'
                # Set new trail for LONG position
                current_trail = low * (1 - stop_multiplier)  # Use low of flip bar
                trails.append(current_trail)
                directions.append(current_direction)
                continue

            # No flip - update SHORT trail (only move down)
            new_trail = close * (1 + stop_multiplier)
            current_trail = min(current_trail, new_trail)  # Trail only falls

        trails.append(current_trail)
        directions.append(current_direction)

    return trails, directions[-1] if directions else initial_direction, flip_indices, directions


def calculate_slope_score(df, trails, directions, flip_indices, current_direction):
    """
    Calculate slope score for current LONG position only
    Formula: (velocity_score + days_score) × quality_boost
    Returns dict with days_in_trend, long_gain_pct, and slope_score
    """
    # Only process if current direction is LONG
    if current_direction != 'LONG':
        return {'days_in_trend': 0, 'long_gain_pct': 0, 'slope_score': 0}

    # Find the start of current LONG segment
    if len(flip_indices) > 0:
        last_flip = flip_indices[-1]
        current_segment_start = last_flip
    else:
        current_segment_start = 0

    # Extract current LONG segment data
    segment_df = df.iloc[current_segment_start:].copy()
    segment_trails = trails[current_segment_start:]
    segment_close = segment_df['Close'].values

    days_in_trend = len(segment_df)

    # Need minimum 5 days to calculate meaningful score
    if days_in_trend < 5:
        return {'days_in_trend': days_in_trend, 'long_gain_pct': 0, 'slope_score': 0}

    # Calculate LONG-only gain % (from entry to current price)
    entry_price = segment_close[0]
    current_price = segment_close[-1]
    long_gain_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0

    # If gain is zero or negative, return score 0
    if long_gain_pct <= 0:
        return {'days_in_trend': days_in_trend, 'long_gain_pct': long_gain_pct, 'slope_score': 0}

    # Component 1: Trail Consistency (daily % changes)
    trail_pct_changes = []
    for i in range(1, len(segment_trails)):
        if segment_trails[i - 1] > 0:
            pct_change = ((segment_trails[i] / segment_trails[i - 1]) - 1) * 100
            trail_pct_changes.append(pct_change)

    if len(trail_pct_changes) == 0:
        return {'days_in_trend': days_in_trend, 'long_gain_pct': long_gain_pct, 'slope_score': 0}

    mean_change = np.mean(trail_pct_changes)
    std_change = np.std(trail_pct_changes)

    # Coefficient of Variation (lower is better - more consistent)
    if mean_change > 0:
        cv = std_change / mean_change
        # Convert CV to score: lower CV = higher score
        # CV of 0.5 = good, CV of 2.0 = poor
        consistency_score = max(0, min(100, 100 * (1 - min(cv, 2.0) / 2.0)))
    else:
        consistency_score = 0

    # Component 2: Slope Quality (R² and acceleration check)
    x = np.arange(len(segment_trails))
    y = np.array(segment_trails)

    # Linear regression
    if len(x) > 1:
        coeffs = np.polyfit(x, y, 1)
        slope = coeffs[0]
        y_pred = np.polyval(coeffs, x)
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        # R² score (0-100)
        slope_quality = max(0, min(100, r_squared * 100))

        # Check for parabolic acceleration
        if days_in_trend >= 10:
            # Compare recent slope vs earlier slope
            mid_point = days_in_trend // 2
            recent_changes = trail_pct_changes[mid_point:]
            earlier_changes = trail_pct_changes[:mid_point]

            if len(recent_changes) > 0 and len(earlier_changes) > 0:
                recent_avg = np.mean(recent_changes)
                earlier_avg = np.mean(earlier_changes)

                if earlier_avg > 0:
                    acceleration_ratio = recent_avg / earlier_avg

                    # Apply penalty for excessive acceleration
                    if acceleration_ratio > 2.0:
                        slope_quality *= 0.5  # 50% penalty
                    elif acceleration_ratio > 1.5:
                        slope_quality *= 0.8  # 20% penalty
    else:
        slope_quality = 0

    # Component 3: Distance Stability (price/trail ratio)
    price_trail_ratios = []
    for i in range(len(segment_trails)):
        if segment_trails[i] > 0:
            ratio = segment_close[i] / segment_trails[i]
            price_trail_ratios.append(ratio)

    if len(price_trail_ratios) > 1:
        mean_ratio = np.mean(price_trail_ratios)
        std_ratio = np.std(price_trail_ratios)

        # Lower std = more stable = higher score
        # Typical std might be 0.01-0.05 for stable stocks
        distance_stability = max(0, min(100, 100 * (1 - min(std_ratio, 0.1) / 0.1)))

        # Check for abnormal current distance using z-score
        current_ratio = price_trail_ratios[-1]
        if std_ratio > 0:
            z_score = abs((current_ratio - mean_ratio) / std_ratio)
            if z_score > 2.0:
                # Current distance is abnormally large
                distance_stability *= 0.7  # 30% penalty
    else:
        distance_stability = 0

    # NEW FORMULA: base_score × quality_multiplier

    # Velocity score: (gain% / days) × 100
    velocity_score = (long_gain_pct / days_in_trend) * 100

    # Days score: capped at 30 for max benefit
    days_score = min(days_in_trend, 30)

    # Base score: weighted sum of velocity and days
    # Velocity weight = 2, Days weight = 3
    base_score = (velocity_score * 2) + (days_score * 3)

    # Quality average (0-100)
    quality_avg = (consistency_score + slope_quality + distance_stability) / 3

    # Quality multiplier: convert to 0.0-1.0 decimal
    quality_multiplier = quality_avg / 100

    # Final score: base × quality
    final_score = base_score * quality_multiplier

    return {
        'days_in_trend': days_in_trend,
        'long_gain_pct': round(long_gain_pct, 1),
        'slope_score': round(final_score, 1)
    }


def prepare_chart_data(symbol, data, display_days=90, stop_pct=10.0):
    """Prepare data for charting"""
    df = data['historical_data'].copy()
    df = df.reset_index()

    # Ensure 'Date' column
    if 'Date' not in df.columns:
        if 'index' in df.columns and pd.api.types.is_datetime64_any_dtype(df['index']):
            df = df.rename(columns={'index': 'Date'})

    if 'Date' not in df.columns:
        raise ValueError("No valid Date column")

    df['Date'] = pd.to_datetime(df['Date'])

    # Limit to display days
    if display_days < len(df):
        df = df.tail(display_days)

    # Handle NaN: Drop rows with NaN in key columns, forward-fill prices
    df = df.dropna(subset=['Open', 'High', 'Low', 'Close'])
    df[['Open', 'High', 'Low', 'Close']] = df[['Open', 'High', 'Low', 'Close']].ffill()
    if len(df) < 2:
        raise ValueError("Insufficient valid data after cleaning")

    # Calc gain % over displayed days
    first_close = df['Close'].iloc[0]
    last_close = df['Close'].iloc[-1]
    period_gain_pct = ((last_close - first_close) / first_close * 100) if first_close > 0 else 0

    # Initial direction
    initial_direction = 'LONG' if df['Close'].iloc[1] > df['Close'].iloc[0] else 'SHORT'

    # Calc trail
    trails, current_dir, flip_indices, directions = calculate_auto_flipping_trail(df, initial_direction, stop_pct)

    # Calculate slope score
    slope_data = calculate_slope_score(df, trails, directions, flip_indices, current_dir)

    chart_data = {
        'symbol': symbol,
        'dates': df['Date'].dt.strftime('%Y-%m-%d').tolist(),
        'open': df['Open'].round(2).tolist(),
        'high': df['High'].round(2).tolist(),
        'low': df['Low'].round(2).tolist(),
        'close': df['Close'].round(2).tolist(),
        'volume': df['Volume'].fillna(0).tolist(),
        'trail': [round(t, 2) if not pd.isna(t) else np.nan for t in trails],
        'directions': directions,  # Direction at each point
        'current_direction': current_dir,
        'flip_indices': flip_indices,
        'period_gain_pct': round(period_gain_pct, 1),
        'market_cap': data.get('market_cap', 0),
        'slope_score': slope_data['slope_score'],
        'days_in_trend': slope_data['days_in_trend'],
        'long_gain_pct': slope_data['long_gain_pct']
    }

    return chart_data


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/view_charts')
def view_charts():
    # Clean up old cache files on first call
    cleanup_old_cache_files()

    period_days = int(request.args.get('period_days', 10))
    stop_percentage = float(request.args.get('stop_percentage', 10))
    min_price = float(request.args.get('min_price', 1))
    max_price = float(request.args.get('max_price', 500))
    min_volume = int(request.args.get('min_volume', 100000))
    min_mcap = float(request.args.get('min_mcap', 10000000))
    max_mcap = float(request.args.get('max_mcap', 1000000000000))
    min_momentum = float(request.args.get('min_momentum', -999))
    max_volatility = float(request.args.get('max_volatility', 999))
    display_days = int(request.args.get('days', 90))
    page = int(request.args.get('page', 1))
    sort_by = request.args.get('sort_by', 'period_gain_pct')

    cached_data = load_cached_data()
    if not cached_data:
        return "No cached data found. Run the scanner first.", 404

    filtered_symbols = []
    display_gains = {}  # Fresh gain for sorting
    for symbol in cached_data:
        data = cached_data[symbol]
        current_price = data['current_price']
        avg_volume = data['avg_volume']
        market_cap = data['market_cap']

        if current_price < min_price or current_price > max_price:
            continue
        if avg_volume < min_volume:
            continue
        if market_cap < min_mcap or market_cap > max_mcap:
            continue

        # Momentum/vol filter if enabled
        if min_momentum > -999 or max_volatility < 999:
            df = data['historical_data']
            if len(df) < 5:
                continue
            if len(df) >= period_days:
                period_data = df.tail(period_days)
                recent_avg = period_data['Close'].tail(max(3, period_days // 3)).mean()
                previous_avg = period_data['Close'].head(max(3, period_days // 3)).mean()
                if previous_avg > 0:
                    momentum_score = ((recent_avg / previous_avg - 1) * 100)
                    if momentum_score < min_momentum:
                        continue
                if max_volatility < 999:
                    returns = period_data['Close'].pct_change().dropna()
                    volatility = returns.std() * (252 ** 0.5) * 100
                    if volatility > max_volatility:
                        continue

        # Calc fresh gain for this display_days
        df = data['historical_data']
        if len(df) >= display_days:
            display_df = df.tail(display_days)
            first_close = display_df['Close'].iloc[0]
            last_close = display_df['Close'].iloc[-1]
            display_gains[symbol] = ((last_close - first_close) / first_close * 100) if first_close > 0 else 0
        else:
            display_gains[symbol] = 0

        filtered_symbols.append(symbol)

    # Sort symbols based on selected method
    slope_scores = {}  # Initialize here so it's always available
    if sort_by == 'slope_score':
        # Create a cache key based on current filter parameters
        cache_key = f"{display_days}_{stop_percentage}_{min_price}_{max_price}_{min_volume}_{min_mcap}_{max_mcap}_{min_momentum}_{max_volatility}"
        cache_file = f'slope_scores_cache_{cache_key}.pkl'

        # Check if we have cached slope scores for these exact parameters
        if os.path.exists(cache_file):
            try:
                # Load from cache file
                print(f"Loading cached slope scores from file...")
                with open(cache_file, 'rb') as f:
                    cache_data = pickle.load(f)
                slope_scores = cache_data['slope_scores']
                filtered_symbols = cache_data['filtered_symbols']
                print(f"Loaded {len(slope_scores)} cached LONG stocks from file")
            except Exception as e:
                print(f"Error loading cache file: {e}, recalculating...")
                slope_scores = {}

        if not slope_scores:
            # Calculate fresh scores
            # For slope score, we need to calculate scores but only for what we'll display
            # First, do a quick filter to LONG only by checking last price direction
            print(f"Starting slope score calculation for {len(filtered_symbols)} filtered symbols...")
            quick_filtered = []
            for symbol in filtered_symbols:
                try:
                    df = cached_data[symbol]['historical_data']
                    if len(df) >= 2:
                        # Quick check: is recent trend up (likely LONG)?
                        recent_closes = df['Close'].tail(5).values
                        if len(recent_closes) >= 2 and recent_closes[-1] > recent_closes[0]:
                            quick_filtered.append(symbol)
                except:
                    continue

            print(f"Quick filtered to {len(quick_filtered)} potential LONG stocks...")

            # Now calculate slope scores only for likely LONG candidates
            slope_scores = {}
            for idx, symbol in enumerate(quick_filtered):
                if idx % 50 == 0:
                    print(f"Processing {idx}/{len(quick_filtered)} stocks...")
                try:
                    chart_data = prepare_chart_data(symbol, cached_data[symbol], display_days, stop_percentage)
                    if chart_data['current_direction'] == 'LONG' and chart_data['days_in_trend'] >= 5:
                        slope_scores[symbol] = {
                            'score': chart_data['slope_score'],
                            'direction': chart_data['current_direction'],
                            'chart_data': chart_data  # Cache the chart data!
                        }
                except Exception as e:
                    print(f"Error calculating slope score for {symbol}: {e}")
                    continue

            print(f"Final LONG stocks with valid scores: {len(slope_scores)}")

            # Filter to only symbols with valid scores
            filtered_symbols = [s for s in slope_scores.keys()]
            # Sort by slope score
            filtered_symbols.sort(key=lambda s: slope_scores[s]['score'], reverse=True)

            # Save to cache file
            try:
                cache_data = {
                    'slope_scores': slope_scores,
                    'filtered_symbols': filtered_symbols
                }
                with open(cache_file, 'wb') as f:
                    pickle.dump(cache_data, f)
                print(f"Cached {len(slope_scores)} slope scores to file: {cache_file}")
            except Exception as e:
                print(f"Error saving cache file: {e}")
    elif sort_by == 'period_gain_pct':
        filtered_symbols.sort(key=lambda s: display_gains.get(s, 0), reverse=True)
    elif sort_by in ['momentum_score', 'volatility']:
        filtered_symbols.sort(key=lambda s: cached_data[s].get(sort_by, 0), reverse=True)
    else:
        filtered_symbols.sort(key=lambda s: display_gains.get(s, 0), reverse=True)

    per_page = 20
    total_pages = (len(filtered_symbols) + per_page - 1) // per_page
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_symbols = filtered_symbols[start_idx:end_idx]

    charts_data = []
    for symbol in page_symbols:
        if symbol in cached_data:
            try:
                # Use cached chart_data if available (from slope_score calculation)
                if sort_by == 'slope_score' and symbol in slope_scores and 'chart_data' in slope_scores[symbol]:
                    chart_data = slope_scores[symbol]['chart_data']
                    chart_data['period_gain_pct'] = display_gains.get(symbol, chart_data.get('period_gain_pct', 0))
                else:
                    chart_data = prepare_chart_data(symbol, cached_data[symbol], display_days, stop_percentage)
                    chart_data['period_gain_pct'] = display_gains.get(symbol, 0)  # Use fresh for titles
                charts_data.append(chart_data)
            except Exception as e:
                print(f"Error processing {symbol}: {e}")
                continue

    sort_display = sort_by.replace('_', ' ').replace('pct', '%').title()

    return render_template('charts.html',
                           charts=charts_data,
                           page=page,
                           total_pages=total_pages,
                           total_filtered=len(filtered_symbols),
                           config=request.args,
                           days=display_days,
                           sort_by=sort_display,
                           sort_by_raw=sort_by)


@app.route('/api/chart/<symbol>')
def get_chart_data(symbol):
    days = int(request.args.get('days', 90))
    stop_pct = float(request.args.get('stop_percentage', 10))
    cached_data = load_cached_data()
    if symbol not in cached_data:
        return jsonify({'error': 'Symbol not found'}), 404
    try:
        chart_data = prepare_chart_data(symbol, cached_data[symbol], days, stop_pct)
        return jsonify(chart_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)