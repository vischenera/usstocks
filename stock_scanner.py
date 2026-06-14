#!/usr/bin/env python3
"""
US Stock Market Scanner - Top 100 Gainers with 15% Trailing Stop Loss
Uses yfinance for free market data
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
warnings.filterwarnings('ignore')

# List of major US stock indices components to scan
# Using S&P 500, NASDAQ 100, and DOW 30 tickers
def get_us_stock_universe():
    """
    Get a comprehensive list of US stocks to scan.
    Using major index components for reliable data.
    """
    # Common large-cap US stocks (sample of ~150 major stocks)
    # In production, you'd want to use a complete list from an API
    major_stocks = [
        # Tech
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'NFLX', 'ADBE', 'CRM',
        'ORCL', 'CSCO', 'INTC', 'AMD', 'QCOM', 'AVGO', 'TXN', 'INTU', 'IBM', 'NOW',
        'SNOW', 'PANW', 'CRWD', 'ZS', 'DDOG', 'MDB', 'NET', 'OKTA', 'ZM', 'TEAM',
        
        # Finance
        'JPM', 'BAC', 'WFC', 'C', 'GS', 'MS', 'BLK', 'SCHW', 'AXP', 'USB',
        'PNC', 'TFC', 'COF', 'BK', 'STT', 'SPGI', 'MCO', 'CME', 'ICE', 'V', 'MA',
        
        # Healthcare
        'JNJ', 'UNH', 'PFE', 'ABBV', 'TMO', 'ABT', 'LLY', 'MRK', 'DHR', 'BMY',
        'AMGN', 'GILD', 'CVS', 'CI', 'HUM', 'ISRG', 'REGN', 'VRTX', 'ZTS', 'BIIB',
        
        # Consumer
        'WMT', 'HD', 'PG', 'KO', 'PEP', 'COST', 'NKE', 'MCD', 'SBUX', 'TGT',
        'LOW', 'TJX', 'DG', 'DLTR', 'ROST', 'YUM', 'CMG', 'DPZ', 'ULTA', 'EL',
        
        # Industrial
        'BA', 'CAT', 'GE', 'HON', 'UPS', 'LMT', 'RTX', 'DE', 'MMM', 'UNP',
        'FDX', 'NSC', 'CSX', 'EMR', 'ETN', 'ITW', 'PH', 'CMI', 'PCAR', 'ROK',
        
        # Energy
        'XOM', 'CVX', 'COP', 'SLB', 'EOG', 'MPC', 'PSX', 'VLO', 'OXY', 'HAL',
        'KMI', 'WMB', 'HES', 'DVN', 'FANG', 'MRO', 'APA', 'BKR', 'NOV',
        
        # Communication
        'DIS', 'CMCSA', 'T', 'VZ', 'TMUS', 'CHTR', 'NFLX', 'EA', 'TTWO', 'ATVI',
        
        # Other sectors
        'NVDA', 'TSLA', 'BRK-B', 'TSM', 'ASML', 'NVO', 'LIN', 'SHEL', 'NVS', 'HSBC'
    ]
    
    return list(set(major_stocks))  # Remove duplicates


def calculate_trailing_stop(stock_data, stop_percentage=0.15):
    """
    Calculate 15% trailing stop loss level based on highest high in the period.
    
    Args:
        stock_data: DataFrame with OHLCV data
        stop_percentage: Trailing stop percentage (0.15 = 15%)
    
    Returns:
        dict with trailing stop info
    """
    if stock_data is None or len(stock_data) < 2:
        return None
    
    # Calculate the highest high over the period
    highest_high = stock_data['High'].max()
    current_price = stock_data['Close'].iloc[-1]
    
    # Calculate trailing stop level (15% below highest high)
    trailing_stop_level = highest_high * (1 - stop_percentage)
    
    # Calculate price change metrics
    period_start_price = stock_data['Close'].iloc[0]
    period_gain_pct = ((current_price - period_start_price) / period_start_price) * 100
    
    # Distance from current price to stop loss
    distance_to_stop_pct = ((current_price - trailing_stop_level) / current_price) * 100
    
    # Check if stop loss is triggered
    stop_triggered = current_price < trailing_stop_level
    
    return {
        'current_price': current_price,
        'highest_high': highest_high,
        'trailing_stop_level': trailing_stop_level,
        'period_gain_pct': period_gain_pct,
        'distance_to_stop_pct': distance_to_stop_pct,
        'stop_triggered': stop_triggered,
        'volume': stock_data['Volume'].iloc[-1]
    }


def fetch_stock_data(ticker, period='30d'):
    """
    Fetch stock data for a single ticker.
    
    Args:
        ticker: Stock ticker symbol
        period: Time period to fetch (default 30 days)
    
    Returns:
        tuple: (ticker, stock_info_dict)
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        
        if hist.empty or len(hist) < 2:
            return (ticker, None)
        
        # Get stock info
        info = stock.info
        company_name = info.get('longName', ticker)
        sector = info.get('sector', 'N/A')
        
        # Calculate trailing stop info
        stop_info = calculate_trailing_stop(hist)
        
        if stop_info is None:
            return (ticker, None)
        
        result = {
            'ticker': ticker,
            'company_name': company_name,
            'sector': sector,
            **stop_info
        }
        
        return (ticker, result)
        
    except Exception as e:
        print(f"Error fetching {ticker}: {str(e)}")
        return (ticker, None)


def scan_market(tickers, max_workers=10):
    """
    Scan multiple stocks concurrently.
    
    Args:
        tickers: List of ticker symbols
        max_workers: Number of concurrent threads
    
    Returns:
        List of stock data dictionaries
    """
    results = []
    total = len(tickers)
    
    print(f"Scanning {total} stocks...")
    print("=" * 80)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_ticker = {
            executor.submit(fetch_stock_data, ticker): ticker 
            for ticker in tickers
        }
        
        # Process completed tasks
        completed = 0
        for future in as_completed(future_to_ticker):
            ticker, data = future.result()
            completed += 1
            
            if data is not None:
                results.append(data)
            
            # Progress indicator
            if completed % 10 == 0:
                print(f"Progress: {completed}/{total} stocks scanned...")
    
    print(f"\nSuccessfully scanned {len(results)} stocks")
    return results


def display_top_gainers(stock_data, top_n=100):
    """
    Display top N gainers with trailing stop information.
    
    Args:
        stock_data: List of stock data dictionaries
        top_n: Number of top gainers to display
    """
    if not stock_data:
        print("No data to display.")
        return
    
    # Convert to DataFrame for easier sorting and display
    df = pd.DataFrame(stock_data)
    
    # Sort by period gain percentage (descending)
    df = df.sort_values('period_gain_pct', ascending=False)
    
    # Get top N
    top_stocks = df.head(top_n)
    
    # Display results
    print("\n" + "=" * 120)
    print(f"TOP {len(top_stocks)} GAINERS WITH 15% TRAILING STOP LOSS")
    print("=" * 120)
    print(f"\n{'Rank':<6}{'Ticker':<8}{'Company':<30}{'Sector':<20}{'Gain %':<10}{'Current':<12}{'Stop':<12}{'Distance':<12}{'Status':<10}")
    print("-" * 120)
    
    for idx, row in enumerate(top_stocks.itertuples(), 1):
        status = "❌ STOPPED" if row.stop_triggered else "✅ ACTIVE"
        
        print(f"{idx:<6}{row.ticker:<8}{row.company_name[:28]:<30}{row.sector[:18]:<20}"
              f"{row.period_gain_pct:>8.2f}%  ${row.current_price:>9.2f}  "
              f"${row.trailing_stop_level:>9.2f}  {row.distance_to_stop_pct:>9.2f}%  {status:<10}")
    
    # Summary statistics
    print("\n" + "=" * 120)
    print("SUMMARY STATISTICS")
    print("=" * 120)
    print(f"Average Gain: {top_stocks['period_gain_pct'].mean():.2f}%")
    print(f"Median Gain: {top_stocks['period_gain_pct'].median():.2f}%")
    print(f"Highest Gain: {top_stocks['period_gain_pct'].max():.2f}% ({top_stocks.iloc[0]['ticker']})")
    print(f"Stops Triggered: {top_stocks['stop_triggered'].sum()} out of {len(top_stocks)}")
    print(f"Active Positions: {(~top_stocks['stop_triggered']).sum()} out of {len(top_stocks)}")
    
    # Save to CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"top_gainers_{timestamp}.csv"
    top_stocks.to_csv(filename, index=False)
    print(f"\nResults saved to: {filename}")


def main():
    """
    Main execution function.
    """
    print("=" * 80)
    print("US STOCK MARKET SCANNER - TOP 100 GAINERS")
    print("Trailing Stop Loss: 15%")
    print("Data Source: Yahoo Finance (via yfinance)")
    print("=" * 80)
    print()
    
    # Get stock universe
    tickers = get_us_stock_universe()
    print(f"Stock Universe: {len(tickers)} major US stocks")
    print()
    
    # Scan the market
    start_time = time.time()
    stock_data = scan_market(tickers, max_workers=20)
    end_time = time.time()
    
    print(f"\nScan completed in {end_time - start_time:.2f} seconds")
    
    # Display top gainers
    display_top_gainers(stock_data, top_n=100)
    
    print("\n" + "=" * 80)
    print("Scan Complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
