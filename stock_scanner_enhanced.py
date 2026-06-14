#!/usr/bin/env python3
"""
Enhanced US Stock Market Scanner - Supports larger stock universe
Can download S&P 500 or other index constituents automatically
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
import requests
warnings.filterwarnings('ignore')


def get_sp500_tickers():
    """
    Download current S&P 500 constituents from Wikipedia.
    """
    try:
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        tables = pd.read_html(url)
        sp500_table = tables[0]
        tickers = sp500_table['Symbol'].tolist()
        # Clean up tickers (replace dots with dashes for Yahoo Finance)
        tickers = [ticker.replace('.', '-') for ticker in tickers]
        print(f"✓ Successfully loaded {len(tickers)} S&P 500 tickers")
        return tickers
    except Exception as e:
        print(f"⚠ Could not fetch S&P 500 list: {e}")
        return []


def get_nasdaq100_tickers():
    """
    Get NASDAQ 100 tickers.
    """
    try:
        url = 'https://en.wikipedia.org/wiki/NASDAQ-100'
        tables = pd.read_html(url)
        nasdaq_table = tables[4]  # The constituents table
        tickers = nasdaq_table['Ticker'].tolist()
        print(f"✓ Successfully loaded {len(tickers)} NASDAQ 100 tickers")
        return tickers
    except Exception as e:
        print(f"⚠ Could not fetch NASDAQ 100 list: {e}")
        return []


def get_comprehensive_ticker_list():
    """
    Get a comprehensive list of US stocks from multiple indices.
    """
    print("Fetching ticker lists from multiple sources...")
    print("-" * 80)
    
    all_tickers = []
    
    # Get S&P 500
    sp500 = get_sp500_tickers()
    all_tickers.extend(sp500)
    
    # Get NASDAQ 100
    nasdaq100 = get_nasdaq100_tickers()
    all_tickers.extend(nasdaq100)
    
    # Remove duplicates
    all_tickers = list(set(all_tickers))
    
    print("-" * 80)
    print(f"Total unique tickers: {len(all_tickers)}")
    
    return all_tickers


def calculate_trailing_stop(stock_data, stop_percentage=0.15):
    """
    Calculate 15% trailing stop loss level based on highest high in the period.
    """
    if stock_data is None or len(stock_data) < 2:
        return None
    
    try:
        # Calculate the highest high over the period
        highest_high = stock_data['High'].max()
        current_price = stock_data['Close'].iloc[-1]
        
        # Skip if price data is invalid
        if pd.isna(highest_high) or pd.isna(current_price) or current_price <= 0:
            return None
        
        # Calculate trailing stop level (15% below highest high)
        trailing_stop_level = highest_high * (1 - stop_percentage)
        
        # Calculate price change metrics
        period_start_price = stock_data['Close'].iloc[0]
        period_gain_pct = ((current_price - period_start_price) / period_start_price) * 100
        
        # Distance from current price to stop loss
        distance_to_stop_pct = ((current_price - trailing_stop_level) / current_price) * 100
        
        # Check if stop loss is triggered
        stop_triggered = current_price < trailing_stop_level
        
        # Average volume
        avg_volume = stock_data['Volume'].mean()
        
        return {
            'current_price': float(current_price),
            'highest_high': float(highest_high),
            'trailing_stop_level': float(trailing_stop_level),
            'period_gain_pct': float(period_gain_pct),
            'distance_to_stop_pct': float(distance_to_stop_pct),
            'stop_triggered': bool(stop_triggered),
            'volume': int(stock_data['Volume'].iloc[-1]),
            'avg_volume': int(avg_volume)
        }
    except Exception as e:
        return None


def fetch_stock_data(ticker, period='30d'):
    """
    Fetch stock data for a single ticker with improved error handling.
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        
        if hist.empty or len(hist) < 5:  # Need at least 5 days of data
            return (ticker, None)
        
        # Get stock info with timeout
        try:
            info = stock.info
            company_name = info.get('longName', info.get('shortName', ticker))
            sector = info.get('sector', 'N/A')
            market_cap = info.get('marketCap', 0)
        except:
            company_name = ticker
            sector = 'N/A'
            market_cap = 0
        
        # Calculate trailing stop info
        stop_info = calculate_trailing_stop(hist)
        
        if stop_info is None:
            return (ticker, None)
        
        result = {
            'ticker': ticker,
            'company_name': company_name,
            'sector': sector,
            'market_cap': market_cap,
            **stop_info
        }
        
        return (ticker, result)
        
    except Exception as e:
        return (ticker, None)


def scan_market(tickers, max_workers=20, period='30d'):
    """
    Scan multiple stocks concurrently with progress tracking.
    """
    results = []
    errors = 0
    total = len(tickers)
    
    print(f"\nScanning {total} stocks (period: {period})...")
    print("=" * 80)
    
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_ticker = {
            executor.submit(fetch_stock_data, ticker, period): ticker 
            for ticker in tickers
        }
        
        # Process completed tasks
        completed = 0
        for future in as_completed(future_to_ticker):
            ticker, data = future.result()
            completed += 1
            
            if data is not None:
                results.append(data)
            else:
                errors += 1
            
            # Progress indicator every 5%
            if completed % max(1, total // 20) == 0:
                progress = (completed / total) * 100
                elapsed = time.time() - start_time
                rate = completed / elapsed if elapsed > 0 else 0
                eta = (total - completed) / rate if rate > 0 else 0
                print(f"Progress: {completed}/{total} ({progress:.1f}%) | "
                      f"Found: {len(results)} | Rate: {rate:.1f}/s | ETA: {eta:.0f}s")
    
    elapsed_time = time.time() - start_time
    
    print("=" * 80)
    print(f"✓ Scan completed in {elapsed_time:.1f} seconds")
    print(f"✓ Successfully scanned: {len(results)} stocks")
    print(f"✗ Errors/No data: {errors} stocks")
    
    return results


def display_top_gainers(stock_data, top_n=100):
    """
    Display top N gainers with enhanced formatting.
    """
    if not stock_data:
        print("No data to display.")
        return
    
    # Convert to DataFrame
    df = pd.DataFrame(stock_data)
    
    # Sort by period gain percentage (descending)
    df = df.sort_values('period_gain_pct', ascending=False)
    
    # Get top N
    top_stocks = df.head(top_n)
    
    # Display header
    print("\n" + "=" * 130)
    print(f"TOP {len(top_stocks)} GAINERS WITH 15% TRAILING STOP LOSS")
    print(f"Scan Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 130)
    
    # Column headers
    print(f"\n{'#':<4}{'Ticker':<8}{'Company':<28}{'Sector':<18}{'Gain%':<9}{'Price':<10}"
          f"{'Stop$':<10}{'Dist%':<9}{'Volume':<12}{'Status':<10}")
    print("-" * 130)
    
    # Display each stock
    for idx, row in enumerate(top_stocks.itertuples(), 1):
        status = "❌ STOP" if row.stop_triggered else "✅ LIVE"
        volume_str = f"{row.volume/1e6:.1f}M" if row.volume >= 1e6 else f"{row.volume/1e3:.1f}K"
        
        print(f"{idx:<4}{row.ticker:<8}{row.company_name[:26]:<28}{row.sector[:16]:<18}"
              f"{row.period_gain_pct:>7.2f}%  ${row.current_price:>7.2f}  "
              f"${row.trailing_stop_level:>7.2f}  {row.distance_to_stop_pct:>7.2f}%  "
              f"{volume_str:>10}  {status:<10}")
    
    # Summary statistics
    print("\n" + "=" * 130)
    print("SUMMARY STATISTICS")
    print("=" * 130)
    
    active_count = (~top_stocks['stop_triggered']).sum()
    stopped_count = top_stocks['stop_triggered'].sum()
    
    print(f"Total Stocks Analyzed: {len(df)}")
    print(f"Top Gainers Shown: {len(top_stocks)}")
    print(f"")
    print(f"Gain Statistics:")
    print(f"  • Average Gain: {top_stocks['period_gain_pct'].mean():.2f}%")
    print(f"  • Median Gain: {top_stocks['period_gain_pct'].median():.2f}%")
    print(f"  • Highest Gain: {top_stocks['period_gain_pct'].max():.2f}% ({top_stocks.iloc[0]['ticker']})")
    print(f"  • Lowest Gain (in top {top_n}): {top_stocks['period_gain_pct'].min():.2f}%")
    print(f"")
    print(f"Stop Loss Status:")
    print(f"  • Active Positions: {active_count} ({active_count/len(top_stocks)*100:.1f}%)")
    print(f"  • Stopped Out: {stopped_count} ({stopped_count/len(top_stocks)*100:.1f}%)")
    print(f"")
    print(f"Sector Distribution (Top 5):")
    sector_counts = top_stocks['sector'].value_counts().head(5)
    for sector, count in sector_counts.items():
        print(f"  • {sector}: {count} stocks")
    
    # Save to CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"top_{top_n}_gainers_{timestamp}.csv"
    
    # Prepare export DataFrame
    export_df = top_stocks.copy()
    export_df['rank'] = range(1, len(export_df) + 1)
    
    # Reorder columns for better readability
    column_order = ['rank', 'ticker', 'company_name', 'sector', 'period_gain_pct', 
                   'current_price', 'highest_high', 'trailing_stop_level', 
                   'distance_to_stop_pct', 'stop_triggered', 'volume', 'avg_volume', 'market_cap']
    
    export_df = export_df[column_order]
    export_df.to_csv(filename, index=False)
    
    print(f"\n✓ Results saved to: {filename}")
    print("=" * 130)


def main():
    """
    Main execution function.
    """
    print("=" * 130)
    print(" " * 40 + "US STOCK MARKET SCANNER")
    print(" " * 35 + "TOP 100 GAINERS - 15% TRAILING STOP")
    print("=" * 130)
    print()
    
    # Configuration
    SCAN_PERIOD = '30d'  # Options: '1d', '5d', '1mo', '3mo', '6mo', '1y', etc.
    TOP_N = 100
    MAX_WORKERS = 25  # Number of concurrent threads
    
    print("Configuration:")
    print(f"  • Scan Period: {SCAN_PERIOD}")
    print(f"  • Trailing Stop: 15%")
    print(f"  • Top Gainers to Display: {TOP_N}")
    print(f"  • Concurrent Workers: {MAX_WORKERS}")
    print()
    
    # Get comprehensive ticker list
    tickers = get_comprehensive_ticker_list()
    
    if not tickers:
        print("⚠ No tickers found. Exiting.")
        return
    
    print()
    
    # Scan the market
    stock_data = scan_market(tickers, max_workers=MAX_WORKERS, period=SCAN_PERIOD)
    
    if not stock_data:
        print("⚠ No stock data retrieved. Exiting.")
        return
    
    # Display top gainers
    display_top_gainers(stock_data, top_n=TOP_N)
    
    print("\n" + "=" * 130)
    print(" " * 50 + "SCAN COMPLETE")
    print("=" * 130)


if __name__ == "__main__":
    main()
