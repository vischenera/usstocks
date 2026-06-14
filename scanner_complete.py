#!/usr/bin/env python3
"""
US Stock Momentum Scanner - Full Cache All Stocks, Filter Later
Scan once/day, no filters during fetch
"""

import yfinance as yf
import pandas as pd
from datetime import datetime
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
import urllib.request
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import threading
import os

warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION - Edit these settings
# ============================================================================

CONFIG = {
    'SCAN_PERIOD': '30d',
    'MAX_WORKERS': 20,
    'MIN_PRICE': 2.0,
    'MAX_PRICE': 500,
    'MIN_VOLUME': 200_000,
    'MIN_MCAP': 100_000_000,
    'MAX_MCAP': 10_000_000_000,
    'MIN_GAIN_PCT': 0.0,  # NEW: Min gain % for positives (UI filter)
    'TRAILING_STOP_PCT': 0.15,
    'SORT_BY': 'period_gain_pct',
    'HIDE_STOPPED_STOCKS': True,
    'REQUEST_DELAY': 0.05,
    'MAX_RETRIES': 3,
    'TEST_MODE': False,  # Stop after 20 for test
    'FULL_CACHE_MODE': True,
}

# ============================================================================

app = Flask(__name__)
CORS(app)


# Error handler to return JSON instead of HTML
@app.errorhandler(Exception)
def handle_exception(e):
    import traceback
    print(f"\n❌ Exception in Flask: {e}", flush=True)
    print(traceback.format_exc(), flush=True)
    return jsonify({
        'success': False,
        'error': str(e)
    }), 500


# Silence favicon errors
@app.route('/favicon.ico')
def favicon():
    return '', 204


STOCK_DATA_CACHE = []
LAST_SCAN_TIME = None
SCAN_PROGRESS = {
    'scanning': False,
    'total': 0,
    'completed': 0,
    'qualified': 0,
    'percentage': 0,
    'eta_seconds': 0,
    'current_ticker': '',
    'start_time': None,
    'error': None
}


def download_nasdaq_tickers():
    print("📥 Downloading NASDAQ ticker list...", flush=True)
    url = 'ftp://ftp.nasdaqtrader.com/SymbolDirectory/nasdaqlisted.txt'
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            data = response.read().decode('utf-8')
        lines = data.strip().split('\n')
        tickers = []
        for line in lines[1:-1]:
            parts = line.split('|')
            if len(parts) > 0:
                ticker = parts[0].strip()
                if ticker and not ticker.startswith('$') and '.' not in ticker:
                    tickers.append(ticker)
        print(f"✓ Downloaded {len(tickers)} NASDAQ tickers", flush=True)
        return tickers
    except Exception as e:
        print(f"⚠ Error: {e}", flush=True)
        return []


def download_other_exchange_tickers():
    print("📥 Downloading NYSE/Other ticker list...", flush=True)
    url = 'ftp://ftp.nasdaqtrader.com/SymbolDirectory/otherlisted.txt'
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            data = response.read().decode('utf-8')
        lines = data.strip().split('\n')
        tickers = []
        for line in lines[1:-1]:
            parts = line.split('|')
            if len(parts) > 0:
                ticker = parts[0].strip()
                if ticker and not any(x in ticker for x in ['.', '$', '^', '/', 'PR']):
                    tickers.append(ticker)
        print(f"✓ Downloaded {len(tickers)} NYSE/Other tickers", flush=True)
        return tickers
    except Exception as e:
        print(f"⚠ Error: {e}", flush=True)
        return []


def get_all_us_tickers():
    global SCAN_PROGRESS

    SCAN_PROGRESS.update({
        'scanning': True,
        'total': 0,
        'completed': 0,
        'qualified': 0,
        'percentage': 0,
        'eta_seconds': 0,
        'current_ticker': 'Downloading ticker lists...',
        'start_time': time.time(),
        'error': None
    })

    nasdaq = download_nasdaq_tickers()
    other = download_other_exchange_tickers()
    all_tickers = list(set(nasdaq + other))
    print(f"✓ Total unique tickers: {len(all_tickers)}\n", flush=True)
    return all_tickers


def calculate_momentum_score(stock_data):
    if len(stock_data) < 20:
        return 0
    recent_avg = stock_data['Close'].iloc[-5:].mean()
    previous_avg = stock_data['Close'].iloc[-20:-5].mean()
    momentum_ratio = (recent_avg / previous_avg - 1) * 100 if previous_avg > 0 else 0
    recent_vol = stock_data['Volume'].iloc[-5:].mean()
    previous_vol = stock_data['Volume'].iloc[-20:-5].mean()
    volume_ratio = (recent_vol / previous_vol) if previous_vol > 0 else 1
    return momentum_ratio * (1 + (volume_ratio - 1) * 0.5)


def calculate_volatility(stock_data):
    if len(stock_data) < 10:
        return 0
    returns = stock_data['Close'].pct_change().dropna()
    return returns.std() * (252 ** 0.5) * 100


def calculate_trailing_stop_dynamic(stock_data, stop_percentage=None):
    if stop_percentage is None:
        stop_percentage = CONFIG['TRAILING_STOP_PCT']
    if stock_data is None or len(stock_data) < 5:
        return None

    try:
        current_price = stock_data['Close'].iloc[-1]
        period_start_price = stock_data['Close'].iloc[0]
        period_gain_pct = ((current_price - period_start_price) / period_start_price) * 100

        if pd.isna(current_price) or current_price <= 0:
            return None

        running_max = stock_data['High'].iloc[0]
        chart_data = []
        stop_triggered = False

        for idx, row in stock_data.iterrows():
            running_max = max(running_max, row['High'])
            trailing_level = running_max * (1 - stop_percentage)

            if current_price < trailing_level:
                stop_triggered = True

            chart_data.append({
                'time': int(idx.timestamp()),
                'open': float(row['Open']),
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': float(row['Close']),
                'volume': int(row['Volume']),
                'trailing': float(trailing_level)
            })

        highest_high = stock_data['High'].max()
        final_trailing = running_max * (1 - stop_percentage)
        distance_to_stop_pct = ((current_price - final_trailing) / current_price) * 100

        return {
            'current_price': float(current_price),
            'highest_high': float(highest_high),
            'trailing_stop_level': float(final_trailing),
            'period_gain_pct': float(period_gain_pct),
            'distance_to_stop_pct': float(distance_to_stop_pct),
            'stop_triggered': bool(stop_triggered),
            'volume': int(stock_data['Volume'].iloc[-1]),
            'avg_volume': int(stock_data['Volume'].mean()),
            'chart_data': chart_data
        }
    except Exception as e:
        print(f"Trailing calc error: {e}", flush=True)
        return None


def fetch_stock_data_with_retry(ticker, period=None, apply_filters=False):
    """Fetch - Full cache: No filters during scan, filters only on UI display"""
    period = period or CONFIG['SCAN_PERIOD']
    SCAN_PROGRESS['current_ticker'] = ticker

    for attempt in range(CONFIG['MAX_RETRIES']):
        try:
            time.sleep(CONFIG['REQUEST_DELAY'])
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period)

            if hist.empty or len(hist) < 10:
                return (ticker, None)

            current_price = hist['Close'].iloc[-1]
            avg_volume = hist['Volume'].mean()

            # FULL CACHE MODE: NO FILTERS during fetch
            # All filtering happens in /api/stocks endpoint

            try:
                info = stock.info
                market_cap = info.get('marketCap', 0)
                company_name = info.get('longName') or info.get('shortName') or ticker
            except:
                market_cap = 0
                company_name = ticker

            momentum = calculate_momentum_score(hist)
            volatility = calculate_volatility(hist)
            trailing_data = calculate_trailing_stop_dynamic(hist, CONFIG['TRAILING_STOP_PCT'])

            # Don't reject if trailing calculation fails - use defaults instead
            if trailing_data is None:
                # Generate basic chart data from history
                chart_data = []
                if not hist.empty:
                    running_max = hist['High'].iloc[0]
                    for idx, row in hist.iterrows():
                        running_max = max(running_max, row['High'])
                        trailing_level = running_max * (1 - CONFIG['TRAILING_STOP_PCT'])
                        chart_data.append({
                            'time': int(idx.timestamp()),
                            'open': float(row['Open']),
                            'high': float(row['High']),
                            'low': float(row['Low']),
                            'close': float(row['Close']),
                            'volume': int(row['Volume']),
                            'trailing': float(trailing_level)
                        })

                # Use defaults for stocks where trailing calculation fails
                trailing_data = {
                    'current_price': float(current_price),
                    'highest_high': float(hist['High'].max() if not hist.empty else current_price),
                    'trailing_stop_level': float(current_price * 0.85),  # Default 15% below
                    'period_gain_pct': float(
                        ((current_price - hist['Close'].iloc[0]) / hist['Close'].iloc[0]) * 100) if len(
                        hist) > 0 else 0.0,
                    'distance_to_stop_pct': 15.0,
                    'stop_triggered': False,
                    'volume': int(hist['Volume'].iloc[-1]) if not hist.empty else 0,
                    'avg_volume': int(avg_volume),
                    'chart_data': chart_data
                }

            result = {
                'ticker': ticker,
                'company_name': company_name,
                'momentum_score': round(momentum, 2),
                'volatility': round(volatility, 2),
                'market_cap': market_cap,
                **trailing_data
            }

            return (ticker, result)

        except Exception as e:
            if attempt < CONFIG['MAX_RETRIES'] - 1:
                time.sleep(1)
            else:
                return (ticker, None)

    return (ticker, None)


def scan_market(tickers=None):
    global STOCK_DATA_CACHE, LAST_SCAN_TIME, SCAN_PROGRESS

    try:
        SCAN_PROGRESS['scanning'] = True
        SCAN_PROGRESS['error'] = None

        if tickers is None:
            tickers = get_all_us_tickers()
        else:
            SCAN_PROGRESS.update({
                'scanning': True,
                'total': len(tickers),
                'completed': 0,
                'qualified': 0,
                'percentage': 0,
                'eta_seconds': 0,
                'current_ticker': '',
                'start_time': time.time(),
                'error': None
            })

        if not tickers:
            raise ValueError("No tickers to scan")

        total = len(tickers)
        if CONFIG['TEST_MODE']:
            total = min(20, total)
            tickers = tickers[:total]

        SCAN_PROGRESS['total'] = total

        print(f"🔍 Full cache: Scanning {total} stocks (NO filters)...\n", flush=True)

        results = []
        completed = 0
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=CONFIG['MAX_WORKERS']) as executor:
            future_to_ticker = {
                executor.submit(fetch_stock_data_with_retry, ticker, CONFIG['SCAN_PERIOD'], apply_filters=False): ticker
                for ticker in tickers
            }

            for future in as_completed(future_to_ticker):
                ticker, data = future.result()
                completed += 1

                if data is not None:
                    # Store ALL stocks in cache (no filtering)
                    results.append(data)
                    if CONFIG['TEST_MODE'] and len(results) >= 20:
                        print("🧪 Test mode: Stopped at 20", flush=True)
                        for f in future_to_ticker:
                            if not f.done():
                                f.cancel()
                        break

                elapsed = time.time() - start_time
                rate = completed / elapsed if elapsed > 0 else 0
                eta = (total - completed) / rate if rate > 0 else 0

                SCAN_PROGRESS.update({
                    'completed': completed,
                    'qualified': len(results),
                    'percentage': int((completed / total) * 100),
                    'eta_seconds': int(eta)
                })

                if completed % max(1, total // 20) == 0:
                    print(
                        f"Progress: {completed}/{total} ({SCAN_PROGRESS['percentage']}%) | Cached: {len(results)} | ETA: {eta:.0f}s",
                        flush=True)

        elapsed = time.time() - start_time
        print(f"\n{'=' * 80}", flush=True)
        print(f"✅ Full cache done in {elapsed:.1f}s", flush=True)
        print(f"✅ Cached {len(results)} stocks (UI filters apply)", flush=True)
        if CONFIG['TEST_MODE']:
            print("🧪 Test mode - 20 stocks cached", flush=True)
        print("💡 Run once/day for refresh", flush=True)
        print(f"{'=' * 80}\n", flush=True)

        STOCK_DATA_CACHE = results
        LAST_SCAN_TIME = datetime.now()
        SCAN_PROGRESS['scanning'] = False

        return results

    except Exception as e:
        print(f"❌ Error: {e}", flush=True)
        SCAN_PROGRESS['scanning'] = False
        SCAN_PROGRESS['error'] = str(e)
        raise


@app.route('/')
def index():
    html_file = 'index_final.html'
    if not os.path.exists(html_file):
        return jsonify({
            'error': 'index_final.html not found',
            'message': 'Make sure index_final.html is in the same folder'
        }), 404
    return send_file(html_file)


@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify({
        'config': CONFIG,
        'last_scan_time': LAST_SCAN_TIME.isoformat() if LAST_SCAN_TIME else None
    })


@app.route('/api/config', methods=['POST'])
def update_config():
    data = request.get_json(silent=True) or {}
    for key, value in data.items():
        if key in CONFIG:
            CONFIG[key] = value
    return jsonify({'success': True, 'config': CONFIG})


@app.route('/api/progress', methods=['GET'])
def get_progress():
    return jsonify(SCAN_PROGRESS)


@app.route('/api/scan', methods=['POST'])
def trigger_scan():
    global SCAN_PROGRESS

    data = request.get_json(silent=True) or {}
    tickers = data.get('tickers')

    if SCAN_PROGRESS['scanning']:
        return jsonify({
            'success': False,
            'error': 'Scan already in progress',
            'progress': SCAN_PROGRESS
        }), 400

    def run_scan():
        import sys
        try:
            print("\n🔍 Starting full cache scan...", flush=True)
            sys.stdout.flush()
            scan_market(tickers)
            print("✅ Scan complete", flush=True)
            sys.stdout.flush()
        except Exception as e:
            import traceback
            print(f"\n❌ Scan error: {e}", flush=True)
            print(traceback.format_exc(), flush=True)
            sys.stdout.flush()
            SCAN_PROGRESS['scanning'] = False
            SCAN_PROGRESS['error'] = str(e)

    print("\n📡 Triggering full cache scan...", flush=True)
    thread = threading.Thread(target=run_scan, daemon=True)
    thread.start()
    print("✓ Thread started", flush=True)

    return jsonify({'success': True, 'message': 'Full cache scan started'})


@app.route('/api/scan/reset', methods=['POST'])
def reset_scan():
    global SCAN_PROGRESS
    SCAN_PROGRESS['scanning'] = False
    SCAN_PROGRESS['error'] = None
    return jsonify({'success': True, 'message': 'Scan state reset'})


@app.route('/api/stocks', methods=['GET'])
def get_stocks():
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    sort_by = request.args.get('sort_by', CONFIG['SORT_BY'])

    # UI filters applied to full cache
    filter_min_price = float(request.args.get('filter_min_price', CONFIG['MIN_PRICE']))
    filter_max_price = float(request.args.get('filter_max_price', CONFIG['MAX_PRICE']))
    filter_min_volume = int(request.args.get('filter_min_volume', CONFIG['MIN_VOLUME']))
    filter_min_mcap = int(request.args.get('filter_min_mcap', CONFIG['MIN_MCAP']))
    filter_max_mcap = int(request.args.get('filter_max_mcap', CONFIG['MAX_MCAP']))
    filter_min_gain = float(request.args.get('filter_min_gain', CONFIG['MIN_GAIN_PCT']))

    if not STOCK_DATA_CACHE:
        return jsonify({
            'stocks': [],
            'total': 0,
            'page': page,
            'per_page': per_page,
            'total_pages': 0,
            'cached_total': 0
        })

    df = pd.DataFrame(STOCK_DATA_CACHE)

    # FIXED: Apply filters correctly - keep stocks that MATCH the criteria
    df = df[
        (df['current_price'] >= filter_min_price) &
        (df['current_price'] <= filter_max_price) &
        (df['avg_volume'] >= filter_min_volume) &
        (df['market_cap'] >= filter_min_mcap) &
        (df['market_cap'] <= filter_max_mcap) &
        (df['period_gain_pct'] >= filter_min_gain)
        ]

    df = df.sort_values(sort_by, ascending=False)

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page

    paginated_stocks = df.iloc[start_idx:end_idx].to_dict('records')

    return jsonify({
        'stocks': paginated_stocks,
        'total': len(df),
        'page': page,
        'per_page': per_page,
        'total_pages': (len(df) + per_page - 1) // per_page,
        'last_scan_time': LAST_SCAN_TIME.isoformat() if LAST_SCAN_TIME else None,
        'cached_total': len(STOCK_DATA_CACHE)  # Full cache size
    })


@app.route('/api/stock/<ticker>', methods=['GET'])
def get_stock_detail(ticker):
    period = request.args.get('period', CONFIG['SCAN_PERIOD'])
    try:
        _, result = fetch_stock_data_with_retry(ticker, period=period, apply_filters=False)
        if result is None:
            return jsonify({'success': False, 'error': 'Stock not found'}), 404
        return jsonify({'success': True, 'stock': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def main():
    global SCAN_PROGRESS

    SCAN_PROGRESS['scanning'] = False
    SCAN_PROGRESS['error'] = None

    print("\n" + "=" * 80)
    print(" " * 15 + "🚀 US STOCK MOMENTUM SCANNER")
    print(" " * 20 + "Full Cache Mode v1.1 FIXED")
    print("=" * 80)

    if not os.path.exists('index_final.html'):
        print("\n❌ ERROR: index_final.html not found!")
        print("   Make sure both files are in the same folder")
        print("\n" + "=" * 80)
        return

    print("\n📊 Configuration:")
    for key, value in CONFIG.items():
        print(f"   • {key}: {value}")

    print("\n" + "=" * 80)
    print("🌐 Starting Flask web server...")
    print("=" * 80)
    print("\n✅ SERVER IS RUNNING!")
    print("\n📱 Open your browser and go to:")
    print("   👉 http://localhost:8080")
    print("\n💡 Scan once/day for fresh cache")
    print("\n💡 Keep this terminal window open!")
    print("💡 Press Ctrl+C to stop the server")
    print("\n" + "=" * 80 + "\n")

    try:
        app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\n\n" + "=" * 80)
        print("👋 Server stopped")
        print("=" * 80 + "\n")
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")
        print("   Try using a different port (e.g., 5001)")
        print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
