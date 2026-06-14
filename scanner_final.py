#!/usr/bin/env python3
"""
US Stock Momentum Scanner - Complete Working Version
With real-time progress tracking
"""

import yfinance as yf
import pandas as pd
from datetime import datetime
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
import urllib.request
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import threading
import os
warnings.filterwarnings('ignore')

# ============================================================================
# 📊 CONFIGURATION SECTION - EDIT THESE SETTINGS
# ============================================================================

CONFIG = {
    'SCAN_PERIOD': '30d',           
    'TOP_N': 100,                   
    'MAX_WORKERS': 20,              
    'MIN_PRICE': 2.0,               
    'MAX_PRICE': 500,               
    'MIN_VOLUME': 200_000,          
    'MIN_MCAP': 100_000_000,        
    'MAX_MCAP': 10_000_000_000,     
    'TRAILING_STOP_PCT': 0.15,      
    'SORT_BY': 'period_gain_pct',   
    'HIDE_STOPPED_STOCKS': True,    
    'REQUEST_DELAY': 0.05,          
    'MAX_RETRIES': 3,               
}

# ============================================================================

app = Flask(__name__, static_folder='.')
CORS(app)

# Global state
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
    print("Downloading NASDAQ ticker list...")
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
        print(f"✓ Downloaded {len(tickers)} NASDAQ tickers")
        return tickers
    except Exception as e:
        print(f"⚠ Error downloading NASDAQ: {e}")
        return []


def download_other_exchange_tickers():
    print("Downloading NYSE ticker list...")
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
        print(f"✓ Downloaded {len(tickers)} NYSE tickers")
        return tickers
    except Exception as e:
        print(f"⚠ Error downloading NYSE: {e}")
        return []


def get_all_us_tickers():
    nasdaq = download_nasdaq_tickers()
    other = download_other_exchange_tickers()
    all_tickers = list(set(nasdaq + other))
    print(f"Total unique tickers: {len(all_tickers)}")
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


def calculate_trailing_stop(stock_data, stop_percentage=None):
    if stop_percentage is None:
        stop_percentage = CONFIG['TRAILING_STOP_PCT']
    if stock_data is None or len(stock_data) < 5:
        return None
    try:
        highest_high = stock_data['High'].max()
        current_price = stock_data['Close'].iloc[-1]
        if pd.isna(highest_high) or pd.isna(current_price) or current_price <= 0:
            return None
        
        trailing_stop_level = highest_high * (1 - stop_percentage)
        period_start_price = stock_data['Close'].iloc[0]
        period_gain_pct = ((current_price - period_start_price) / period_start_price) * 100
        distance_to_stop_pct = ((current_price - trailing_stop_level) / current_price) * 100
        stop_triggered = current_price < trailing_stop_level
        
        chart_data = []
        for idx, row in stock_data.iterrows():
            chart_data.append({
                'time': int(idx.timestamp()),
                'open': float(row['Open']),
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': float(row['Close']),
                'volume': int(row['Volume'])
            })
        
        return {
            'current_price': float(current_price),
            'highest_high': float(highest_high),
            'trailing_stop_level': float(trailing_stop_level),
            'period_gain_pct': float(period_gain_pct),
            'distance_to_stop_pct': float(distance_to_stop_pct),
            'stop_triggered': bool(stop_triggered),
            'volume': int(stock_data['Volume'].iloc[-1]),
            'avg_volume': int(stock_data['Volume'].mean()),
            'chart_data': chart_data
        }
    except Exception as e:
        return None


def fetch_stock_data_with_retry(ticker, period=None, min_price=None, max_price=None, 
                                 min_volume=None, min_mcap=None, max_mcap=None):
    period = period or CONFIG['SCAN_PERIOD']
    min_price = min_price if min_price is not None else CONFIG['MIN_PRICE']
    max_price = max_price if max_price is not None else CONFIG['MAX_PRICE']
    min_volume = min_volume if min_volume is not None else CONFIG['MIN_VOLUME']
    min_mcap = min_mcap if min_mcap is not None else CONFIG['MIN_MCAP']
    max_mcap = max_mcap if max_mcap is not None else CONFIG['MAX_MCAP']
    
    # Update current ticker
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
            
            if current_price < min_price or current_price > max_price:
                return (ticker, None)
            if avg_volume < min_volume:
                return (ticker, None)
            
            try:
                info = stock.info
                market_cap = info.get('marketCap', 0)
                company_name = info.get('longName', info.get('shortName', ticker))
                sector = info.get('sector', 'N/A')
                if market_cap < min_mcap or market_cap > max_mcap:
                    return (ticker, None)
            except:
                return (ticker, None)
            
            stop_info = calculate_trailing_stop(hist)
            if stop_info is None:
                return (ticker, None)
            
            momentum_score = calculate_momentum_score(hist)
            volatility = calculate_volatility(hist)
            
            result = {
                'ticker': ticker,
                'company_name': company_name,
                'sector': sector,
                'market_cap': market_cap,
                'momentum_score': momentum_score,
                'volatility': volatility,
                **stop_info
            }
            return (ticker, result)
        except Exception as e:
            if attempt < CONFIG['MAX_RETRIES'] - 1:
                time.sleep(1 * (attempt + 1))
                continue
            else:
                return (ticker, None)


def scan_market(tickers=None):
    global STOCK_DATA_CACHE, LAST_SCAN_TIME, SCAN_PROGRESS
    
    try:
        if tickers is None:
            tickers = get_all_us_tickers()
        
        if not tickers:
            raise Exception("No tickers found")
        
        results = []
        total = len(tickers)
        
        # Initialize progress
        SCAN_PROGRESS.update({
            'scanning': True,
            'total': total,
            'completed': 0,
            'qualified': 0,
            'percentage': 0,
            'eta_seconds': 0,
            'start_time': time.time(),
            'error': None
        })
        
        print(f"\n{'='*80}")
        print(f"Starting scan of {total} stocks...")
        print(f"{'='*80}\n")
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=CONFIG['MAX_WORKERS']) as executor:
            future_to_ticker = {
                executor.submit(fetch_stock_data_with_retry, ticker): ticker 
                for ticker in tickers
            }
            
            completed = 0
            for future in as_completed(future_to_ticker):
                ticker, data = future.result()
                completed += 1
                
                if data is not None:
                    if CONFIG['HIDE_STOPPED_STOCKS'] and data['stop_triggered']:
                        pass
                    else:
                        results.append(data)
                
                # Update progress
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
                    print(f"Progress: {completed}/{total} ({SCAN_PROGRESS['percentage']}%) | "
                          f"Qualified: {len(results)} | ETA: {eta:.0f}s")
        
        elapsed = time.time() - start_time
        print(f"\n{'='*80}")
        print(f"✓ Scan completed in {elapsed:.1f} seconds")
        print(f"✓ Active stocks (stop not triggered): {len(results)}")
        print(f"{'='*80}\n")
        
        STOCK_DATA_CACHE = results
        LAST_SCAN_TIME = datetime.now()
        SCAN_PROGRESS['scanning'] = False
        
        return results
        
    except Exception as e:
        print(f"ERROR in scan_market: {e}")
        SCAN_PROGRESS['scanning'] = False
        SCAN_PROGRESS['error'] = str(e)
        raise


# API Routes
@app.route('/')
def index():
    """Serve HTML page."""
    return send_from_directory('.', 'templates/index.html')


@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify({
        'config': CONFIG,
        'last_scan_time': LAST_SCAN_TIME.isoformat() if LAST_SCAN_TIME else None
    })


@app.route('/api/config', methods=['POST'])
def update_config():
    data = request.json
    for key, value in data.items():
        if key in CONFIG:
            CONFIG[key] = value
    return jsonify({'success': True, 'config': CONFIG})


@app.route('/api/progress', methods=['GET'])
def get_progress():
    """Get current scan progress."""
    return jsonify(SCAN_PROGRESS)


@app.route('/api/scan', methods=['POST'])
def trigger_scan():
    # Don't start new scan if one is running
    if SCAN_PROGRESS['scanning']:
        return jsonify({
            'success': False, 
            'error': 'Scan already in progress'
        }), 400
    
    data = request.json or {}
    tickers = data.get('tickers')
    
    # Run scan in background thread
    def run_scan():
        try:
            print("\n🔍 Starting background scan...")
            scan_market(tickers)
            print("✓ Background scan completed successfully\n")
        except Exception as e:
            print(f"❌ Background scan error: {e}\n")
            SCAN_PROGRESS['scanning'] = False
            SCAN_PROGRESS['error'] = str(e)
    
    thread = threading.Thread(target=run_scan, daemon=True)
    thread.start()
    
    return jsonify({
        'success': True,
        'message': 'Scan started in background'
    })


@app.route('/api/stocks', methods=['GET'])
def get_stocks():
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    sort_by = request.args.get('sort_by', CONFIG['SORT_BY'])
    
    if not STOCK_DATA_CACHE:
        return jsonify({
            'stocks': [],
            'total': 0,
            'page': page,
            'per_page': per_page,
            'total_pages': 0
        })
    
    df = pd.DataFrame(STOCK_DATA_CACHE)
    df = df.sort_values(sort_by, ascending=False)
    
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    
    paginated_stocks = df.iloc[start_idx:end_idx].to_dict('records')
    
    return jsonify({
        'stocks': paginated_stocks,
        'total': len(STOCK_DATA_CACHE),
        'page': page,
        'per_page': per_page,
        'total_pages': (len(STOCK_DATA_CACHE) + per_page - 1) // per_page,
        'last_scan_time': LAST_SCAN_TIME.isoformat() if LAST_SCAN_TIME else None
    })


@app.route('/api/stock/<ticker>', methods=['GET'])
def get_stock_detail(ticker):
    period = request.args.get('period', CONFIG['SCAN_PERIOD'])
    try:
        _, result = fetch_stock_data_with_retry(ticker, period=period)
        if result is None:
            return jsonify({'success': False, 'error': 'Stock not found'}), 404
        return jsonify({'success': True, 'stock': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def main():
    print("\n" + "=" * 80)
    print(" " * 15 + "🚀 US STOCK MOMENTUM SCANNER - WEB VERSION")
    print(" " * 20 + "Optimized for INDmoney Trading")
    print("=" * 80)
    print("\n📊 Configuration:")
    for key, value in CONFIG.items():
        print(f"   • {key}: {value}")
    print("\n" + "=" * 80)
    print("🌐 Starting Flask web server...")
    print("=" * 80)
    print("\n✅ Server is running!")
    print("📱 Open your browser and go to: http://localhost:5000")
    print("\n💡 Tip: Keep this terminal open while using the scanner")
    print("=" * 80 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)


if __name__ == "__main__":
    main()
