#!/usr/bin/env python3
"""
US Stock Scanner for INDmoney - Enhanced with Caching & Rate Limiting
Optimized for Small/Mid Cap Momentum Stocks - Swing Trading Focus

NEW FEATURES:
- Rate limiting to avoid API blocks
- Local caching of downloaded data
- Resume interrupted scans
- Re-analyze cached data with different parameters
- Progress saving
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
import urllib.request
import json
import os
import pickle
from pathlib import Path
warnings.filterwarnings('ignore')


# Configuration
CACHE_DIR = Path('./stock_data_cache')
CACHE_EXPIRY_HOURS = 6  # Cache valid for 6 hours
REQUEST_DELAY = 0.05  # Delay between requests (50ms)
MAX_RETRIES = 3  # Retry failed requests


def setup_cache_directory():
    """Create cache directory if it doesn't exist."""
    CACHE_DIR.mkdir(exist_ok=True)
    print(f"Cache directory: {CACHE_DIR.absolute()}")


def get_cache_path(cache_type='stock_data'):
    """Get path for cache file."""
    timestamp = datetime.now().strftime('%Y%m%d')
    return CACHE_DIR / f"{cache_type}_{timestamp}.pkl"


def save_to_cache(data, cache_type='stock_data'):
    """Save data to cache file."""
    cache_path = get_cache_path(cache_type)
    cache_data = {
        'timestamp': datetime.now(),
        'data': data
    }
    with open(cache_path, 'wb') as f:
        pickle.dump(cache_data, f)
    print(f"✓ Cached {len(data)} items to {cache_path.name}")


def load_from_cache(cache_type='stock_data', max_age_hours=CACHE_EXPIRY_HOURS):
    """Load data from cache if available and fresh."""
    cache_path = get_cache_path(cache_type)
    
    if not cache_path.exists():
        return None
    
    try:
        with open(cache_path, 'rb') as f:
            cache_data = pickle.load(f)
        
        # Check if cache is still valid
        cache_age = datetime.now() - cache_data['timestamp']
        if cache_age.total_seconds() / 3600 > max_age_hours:
            print(f"⚠ Cache expired (age: {cache_age.total_seconds()/3600:.1f}h)")
            return None
        
        print(f"✓ Loaded {len(cache_data['data'])} items from cache (age: {cache_age.total_seconds()/3600:.1f}h)")
        return cache_data['data']
    
    except Exception as e:
        print(f"⚠ Error loading cache: {e}")
        return None


def save_progress(processed_tickers, results, filename='scan_progress.json'):
    """Save scan progress to resume later."""
    progress_path = CACHE_DIR / filename
    progress_data = {
        'timestamp': datetime.now().isoformat(),
        'processed_tickers': list(processed_tickers),
        'results_count': len(results)
    }
    with open(progress_path, 'w') as f:
        json.dump(progress_data, f)


def load_progress(filename='scan_progress.json'):
    """Load previous scan progress."""
    progress_path = CACHE_DIR / filename
    if not progress_path.exists():
        return None
    
    try:
        with open(progress_path, 'r') as f:
            progress_data = json.load(f)
        print(f"✓ Found previous progress: {progress_data['results_count']} stocks processed")
        return set(progress_data['processed_tickers'])
    except:
        return None


def download_nasdaq_tickers():
    """Download complete list of NASDAQ-listed stocks."""
    # Check cache first
    cached_tickers = load_from_cache('nasdaq_tickers', max_age_hours=24)
    if cached_tickers:
        return cached_tickers
    
    print("Downloading NASDAQ ticker list...")
    url = 'ftp://ftp.nasdaqtrader.com/SymbolDirectory/nasdaqlisted.txt'
    
    try:
        with urllib.request.urlopen(url) as response:
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
        save_to_cache(tickers, 'nasdaq_tickers')
        return tickers
    except Exception as e:
        print(f"⚠ Error downloading NASDAQ list: {e}")
        return []


def download_other_exchange_tickers():
    """Download stocks from NYSE and other exchanges."""
    # Check cache first
    cached_tickers = load_from_cache('nyse_tickers', max_age_hours=24)
    if cached_tickers:
        return cached_tickers
    
    print("Downloading NYSE and other exchange tickers...")
    url = 'ftp://ftp.nasdaqtrader.com/SymbolDirectory/otherlisted.txt'
    
    try:
        with urllib.request.urlopen(url) as response:
            data = response.read().decode('utf-8')
        
        lines = data.strip().split('\n')
        tickers = []
        
        for line in lines[1:-1]:
            parts = line.split('|')
            if len(parts) > 0:
                ticker = parts[0].strip()
                if ticker and not any(x in ticker for x in ['.', '$', '^', '/', 'PR']):
                    tickers.append(ticker)
        
        print(f"✓ Downloaded {len(tickers)} NYSE/Other exchange tickers")
        save_to_cache(tickers, 'nyse_tickers')
        return tickers
    except Exception as e:
        print(f"⚠ Error downloading NYSE/Other list: {e}")
        return []


def get_all_us_tickers():
    """Get comprehensive list of all US stock tickers."""
    print("=" * 80)
    print("FETCHING COMPLETE US STOCK UNIVERSE")
    print("=" * 80)
    
    nasdaq_tickers = download_nasdaq_tickers()
    other_tickers = download_other_exchange_tickers()
    
    all_tickers = list(set(nasdaq_tickers + other_tickers))
    
    print("-" * 80)
    print(f"Total unique US stock tickers: {len(all_tickers)}")
    print("=" * 80)
    print()
    
    return all_tickers


def calculate_momentum_score(stock_data):
    """Calculate momentum score based on recent price action."""
    if len(stock_data) < 20:
        return 0
    
    recent_avg = stock_data['Close'].iloc[-5:].mean()
    previous_avg = stock_data['Close'].iloc[-20:-5].mean()
    momentum_ratio = (recent_avg / previous_avg - 1) * 100 if previous_avg > 0 else 0
    
    recent_vol = stock_data['Volume'].iloc[-5:].mean()
    previous_vol = stock_data['Volume'].iloc[-20:-5].mean()
    volume_ratio = (recent_vol / previous_vol) if previous_vol > 0 else 1
    
    momentum_score = momentum_ratio * (1 + (volume_ratio - 1) * 0.5)
    
    return momentum_score


def calculate_volatility(stock_data):
    """Calculate recent volatility."""
    if len(stock_data) < 10:
        return 0
    
    returns = stock_data['Close'].pct_change().dropna()
    volatility = returns.std() * (252 ** 0.5) * 100
    
    return volatility


def calculate_trailing_stop(stock_data, stop_percentage=0.15):
    """Calculate 15% trailing stop loss."""
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
        
        return {
            'current_price': float(current_price),
            'highest_high': float(highest_high),
            'trailing_stop_level': float(trailing_stop_level),
            'period_gain_pct': float(period_gain_pct),
            'distance_to_stop_pct': float(distance_to_stop_pct),
            'stop_triggered': bool(stop_triggered),
            'volume': int(stock_data['Volume'].iloc[-1]),
            'avg_volume': int(stock_data['Volume'].mean())
        }
    except:
        return None


def fetch_stock_data_with_retry(ticker, period='30d', min_price=1.0, max_price=500, 
                                 min_volume=100000, min_mcap=50_000_000, max_mcap=10_000_000_000):
    """
    Fetch stock data with retry logic and rate limiting.
    """
    for attempt in range(MAX_RETRIES):
        try:
            # Rate limiting - small delay between requests
            time.sleep(REQUEST_DELAY)
            
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period)
            
            if hist.empty or len(hist) < 10:
                return (ticker, None)
            
            current_price = hist['Close'].iloc[-1]
            avg_volume = hist['Volume'].mean()
            
            # Price filter
            if current_price < min_price or current_price > max_price:
                return (ticker, None)
            
            # Volume filter
            if avg_volume < min_volume:
                return (ticker, None)
            
            # Get stock info with timeout
            try:
                info = stock.info
                market_cap = info.get('marketCap', 0)
                company_name = info.get('longName', info.get('shortName', ticker))
                sector = info.get('sector', 'N/A')
                
                # Market cap filter
                if market_cap < min_mcap or market_cap > max_mcap:
                    return (ticker, None)
                    
            except:
                return (ticker, None)
            
            # Calculate metrics
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
            if attempt < MAX_RETRIES - 1:
                time.sleep(1 * (attempt + 1))  # Exponential backoff
                continue
            else:
                return (ticker, None)


def scan_market_with_cache(tickers, max_workers=20, period='30d', 
                           min_price=1.0, max_price=500,
                           min_volume=100000, min_mcap=50_000_000, max_mcap=10_000_000_000,
                           use_cache=True, save_cache=True):
    """
    Scan market with caching and resume capability.
    """
    # Try to load from cache first
    if use_cache:
        cached_results = load_from_cache('stock_data', max_age_hours=CACHE_EXPIRY_HOURS)
        if cached_results:
            print("=" * 80)
            print("Using cached data - applying new filters...")
            print("=" * 80)
            
            # Re-filter cached data with new parameters
            filtered_results = []
            for result in cached_results:
                if result is None:
                    continue
                
                # Apply current filters
                if (result['current_price'] >= min_price and 
                    result['current_price'] <= max_price and
                    result['avg_volume'] >= min_volume and
                    result['market_cap'] >= min_mcap and
                    result['market_cap'] <= max_mcap):
                    
                    filtered_results.append(result)
            
            print(f"✓ Filtered to {len(filtered_results)} stocks matching current criteria")
            return filtered_results
    
    # Check for previous incomplete scan
    processed_tickers = load_progress()
    if processed_tickers:
        remaining_tickers = [t for t in tickers if t not in processed_tickers]
        print(f"⚠ Resuming previous scan: {len(remaining_tickers)} tickers remaining")
        tickers = remaining_tickers
    
    results = []
    errors = 0
    filtered_out = 0
    total = len(tickers)
    processed = set()
    
    print(f"Scanning {total} US stocks with rate limiting...")
    print(f"Filters: Price ${min_price}-${max_price} | Volume >{min_volume:,} | MCap ${min_mcap/1e6:.0f}M-${max_mcap/1e9:.1f}B")
    print(f"Rate Limit: {REQUEST_DELAY*1000:.0f}ms delay | Max Retries: {MAX_RETRIES}")
    print("=" * 80)
    
    start_time = time.time()
    
    # Reduce workers to avoid rate limiting
    max_workers = min(max_workers, 20)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_ticker = {
            executor.submit(fetch_stock_data_with_retry, ticker, period, min_price, max_price, 
                          min_volume, min_mcap, max_mcap): ticker 
            for ticker in tickers
        }
        
        completed = 0
        for future in as_completed(future_to_ticker):
            ticker, data = future.result()
            completed += 1
            processed.add(ticker)
            
            if data is not None:
                results.append(data)
            else:
                filtered_out += 1
            
            # Save progress every 100 stocks
            if completed % 100 == 0:
                save_progress(processed, results)
            
            # Progress indicator
            if completed % max(1, total // 25) == 0:
                progress = (completed / total) * 100
                elapsed = time.time() - start_time
                rate = completed / elapsed if elapsed > 0 else 0
                eta = (total - completed) / rate if rate > 0 else 0
                print(f"Progress: {completed}/{total} ({progress:.1f}%) | "
                      f"Qualified: {len(results)} | Rate: {rate:.1f}/s | ETA: {eta:.0f}s")
    
    elapsed_time = time.time() - start_time
    
    # Save final results to cache
    if save_cache and results:
        save_to_cache(results, 'stock_data')
    
    print("=" * 80)
    print(f"✓ Scan completed in {elapsed_time:.1f} seconds")
    print(f"✓ Qualified stocks: {len(results)}")
    print(f"⊘ Filtered out: {filtered_out}")
    
    return results


def analyze_cached_data(min_price=1.0, max_price=500, min_volume=100000, 
                       min_mcap=50_000_000, max_mcap=10_000_000_000,
                       top_n=100, sort_by='period_gain_pct'):
    """
    Analyze cached data with different parameters WITHOUT re-downloading.
    """
    print("=" * 80)
    print("ANALYZING CACHED DATA WITH NEW PARAMETERS")
    print("=" * 80)
    
    # Load cached data
    cached_results = load_from_cache('stock_data', max_age_hours=24)
    
    if not cached_results:
        print("⚠ No cached data found. Run a full scan first.")
        return None
    
    print(f"Loaded {len(cached_results)} stocks from cache")
    print(f"Applying filters: Price ${min_price}-${max_price} | Volume >{min_volume:,} | MCap ${min_mcap/1e6:.0f}M-${max_mcap/1e9:.1f}B")
    
    # Filter with new parameters
    filtered_results = []
    for result in cached_results:
        if result is None:
            continue
        
        if (result['current_price'] >= min_price and 
            result['current_price'] <= max_price and
            result['avg_volume'] >= min_volume and
            result['market_cap'] >= min_mcap and
            result['market_cap'] <= max_mcap):
            
            filtered_results.append(result)
    
    print(f"✓ {len(filtered_results)} stocks match new criteria")
    print()
    
    return filtered_results


def display_top_momentum_stocks(stock_data, top_n=100, sort_by='period_gain_pct'):
    """Display top momentum stocks with trailing stop info."""
    if not stock_data:
        print("No data to display.")
        return
    
    df = pd.DataFrame(stock_data)
    df = df.sort_values(sort_by, ascending=False)
    top_stocks = df.head(top_n)
    
    print("\n" + "=" * 140)
    print(f"TOP {len(top_stocks)} MOMENTUM STOCKS FOR SWING TRADING (Sorted by {sort_by.replace('_', ' ').title()})")
    print(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Focus: Small/Mid Cap | High Liquidity | Strong Momentum")
    print("=" * 140)
    
    print(f"\n{'#':<4}{'Ticker':<8}{'Company':<26}{'Sector':<16}{'MCap':<8}{'Gain%':<8}"
          f"{'Price':<9}{'Stop$':<9}{'Vol':<10}{'Momentum':<10}{'Status':<8}")
    print("-" * 140)
    
    for idx, row in enumerate(top_stocks.itertuples(), 1):
        status = "❌STOP" if row.stop_triggered else "✅LIVE"
        mcap_str = f"${row.market_cap/1e6:.0f}M" if row.market_cap < 1e9 else f"${row.market_cap/1e9:.1f}B"
        vol_str = f"{row.avg_volume/1e6:.1f}M" if row.avg_volume >= 1e6 else f"{row.avg_volume/1e3:.0f}K"
        
        print(f"{idx:<4}{row.ticker:<8}{row.company_name[:24]:<26}{row.sector[:14]:<16}"
              f"{mcap_str:<8}{row.period_gain_pct:>6.1f}%  ${row.current_price:>6.2f}  "
              f"${row.trailing_stop_level:>6.2f}  {vol_str:>8}  "
              f"{row.momentum_score:>8.1f}  {status:<8}")
    
    # Summary statistics
    print("\n" + "=" * 140)
    print("SUMMARY STATISTICS")
    print("=" * 140)
    
    active_count = (~top_stocks['stop_triggered']).sum()
    
    print(f"\nPerformance Metrics:")
    print(f"  • Average Gain: {top_stocks['period_gain_pct'].mean():.2f}%")
    print(f"  • Median Gain: {top_stocks['period_gain_pct'].median():.2f}%")
    print(f"  • Top Gainer: {top_stocks.iloc[0]['ticker']} (+{top_stocks.iloc[0]['period_gain_pct']:.2f}%)")
    
    print(f"\nMomentum Analysis:")
    print(f"  • Average Momentum Score: {top_stocks['momentum_score'].mean():.2f}")
    print(f"  • Average Volatility: {top_stocks['volatility'].mean():.2f}%")
    
    print(f"\nTrading Status:")
    print(f"  • Active Positions: {active_count} ({active_count/len(top_stocks)*100:.1f}%)")
    
    # Save to CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"indmoney_top_{top_n}_momentum_{timestamp}.csv"
    
    export_df = top_stocks.copy()
    export_df['rank'] = range(1, len(export_df) + 1)
    
    column_order = ['rank', 'ticker', 'company_name', 'sector', 'market_cap', 
                   'period_gain_pct', 'momentum_score', 'volatility',
                   'current_price', 'highest_high', 'trailing_stop_level', 
                   'distance_to_stop_pct', 'stop_triggered', 'volume', 'avg_volume']
    
    export_df[column_order].to_csv(filename, index=False)
    
    print(f"\n✓ Results saved to: {filename}")
    print("=" * 140)


def main():
    """Main execution function with caching support."""
    setup_cache_directory()
    
    print("=" * 140)
    print(" " * 45 + "US STOCK MOMENTUM SCANNER FOR INDMONEY")
    print(" " * 35 + "Enhanced with Caching & Rate Limiting")
    print("=" * 140)
    print()
    
    # Configuration
    SCAN_PERIOD = '30d'
    TOP_N = 100
    MAX_WORKERS = 20  # Reduced for rate limiting
    
    # Filters
    MIN_PRICE = 2.0
    MAX_PRICE = 500
    MIN_VOLUME = 200_000
    MIN_MCAP = 100_000_000
    MAX_MCAP = 10_000_000_000
    
    SORT_BY = 'period_gain_pct'
    
    # Check for cached data
    print("🔍 Checking for cached data...")
    cached_data = load_from_cache('stock_data', max_age_hours=CACHE_EXPIRY_HOURS)
    
    if cached_data:
        print("✓ Found recent cached data!")
        print("\nOptions:")
        print("1. Use cached data (FAST - no download)")
        print("2. Re-scan all stocks (SLOW - fresh data)")
        choice = input("\nEnter choice (1 or 2) [default=1]: ").strip() or "1"
        
        if choice == "1":
            stock_data = analyze_cached_data(
                min_price=MIN_PRICE,
                max_price=MAX_PRICE,
                min_volume=MIN_VOLUME,
                min_mcap=MIN_MCAP,
                max_mcap=MAX_MCAP
            )
        else:
            tickers = get_all_us_tickers()
            stock_data = scan_market_with_cache(
                tickers,
                max_workers=MAX_WORKERS,
                period=SCAN_PERIOD,
                min_price=MIN_PRICE,
                max_price=MAX_PRICE,
                min_volume=MIN_VOLUME,
                min_mcap=MIN_MCAP,
                max_mcap=MAX_MCAP,
                use_cache=False
            )
    else:
        print("⚠ No cached data found. Starting fresh scan...")
        tickers = get_all_us_tickers()
        
        stock_data = scan_market_with_cache(
            tickers,
            max_workers=MAX_WORKERS,
            period=SCAN_PERIOD,
            min_price=MIN_PRICE,
            max_price=MAX_PRICE,
            min_volume=MIN_VOLUME,
            min_mcap=MIN_MCAP,
            max_mcap=MAX_MCAP
        )
    
    if not stock_data:
        print("⚠ No stocks met the criteria.")
        return
    
    display_top_momentum_stocks(stock_data, top_n=TOP_N, sort_by=SORT_BY)
    
    print("\n" + "=" * 140)
    print(" " * 55 + "SCAN COMPLETE")
    print("=" * 140)
    print("\n💡 TIP: Run again to use cached data and try different filters instantly!")


if __name__ == "__main__":
    main()
