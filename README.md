# US Stock Market Scanner - Top 100 Gainers

A Python program that scans US stocks and displays the top 100 gainers with 15% trailing stop-loss indicators.

## Features

- ✅ Scans major US stocks (S&P 500, NASDAQ, DOW components)
- ✅ Identifies top 100 gainers based on 30-day performance
- ✅ Calculates 15% trailing stop-loss levels
- ✅ Shows distance to stop-loss for each stock
- ✅ Indicates if stop-loss has been triggered
- ✅ Exports results to CSV file
- ✅ Uses free Yahoo Finance API (via yfinance)
- ✅ Multi-threaded for faster scanning

## Installation

1. Install Python 3.8 or higher

2. Install required packages:
```bash
pip install -r requirements.txt
```

Or install manually:
```bash
pip install yfinance pandas numpy
```

## Usage

Run the scanner:
```bash
python stock_scanner.py
```

The program will:
1. Scan ~150 major US stocks
2. Calculate trailing stop-loss levels
3. Display top 100 gainers
4. Save results to CSV file with timestamp

## Output

The program displays:
- **Rank**: Position in top gainers list
- **Ticker**: Stock symbol
- **Company**: Company name
- **Sector**: Industry sector
- **Gain %**: Percentage gain over the period
- **Current**: Current stock price
- **Stop**: Trailing stop-loss level (15% below highest high)
- **Distance**: Percentage distance from current price to stop
- **Status**: ✅ ACTIVE or ❌ STOPPED (if stop triggered)

## Customization

### Change the scan period
Edit the `period` parameter in `fetch_stock_data()`:
```python
hist = stock.history(period='60d')  # Change from 30d to 60d
```

### Change trailing stop percentage
Edit the default in `calculate_trailing_stop()`:
```python
def calculate_trailing_stop(stock_data, stop_percentage=0.10):  # 10% instead of 15%
```

### Add more stocks
Add tickers to the `major_stocks` list in `get_us_stock_universe()`:
```python
major_stocks = [
    'AAPL', 'MSFT', 'YOUR_TICKER_HERE',
    # ... more tickers
]
```

### Change number of top stocks displayed
Modify the `top_n` parameter when calling the script:
```python
display_top_gainers(stock_data, top_n=50)  # Show top 50 instead of 100
```

## How Trailing Stop Loss Works

The 15% trailing stop-loss is calculated as follows:

1. **Find the highest high**: Identify the highest price during the scan period
2. **Calculate stop level**: Stop = Highest High × (1 - 0.15)
3. **Monitor current price**: If current price falls below stop level, position is "STOPPED"

### Example:
- Highest High: $100
- Trailing Stop: $100 × 0.85 = $85
- Current Price: $90 → Status: ✅ ACTIVE (above stop)
- Current Price: $80 → Status: ❌ STOPPED (below stop)

## Performance

- Scans ~150 stocks in approximately 10-30 seconds
- Uses multi-threading for concurrent API requests
- Rate-limited to avoid API restrictions

## Limitations

- Free Yahoo Finance API has rate limits
- Limited to stocks with available data on Yahoo Finance
- 30-day historical data by default
- Sample includes ~150 major stocks (can be expanded)

## Future Enhancements

- Add real-time streaming data
- Include pre-market and after-hours data
- Add technical indicators (RSI, MACD, etc.)
- Implement alerts when stops are triggered
- Add visualization with charts
- Expand to full US market (all NASDAQ/NYSE stocks)

## Disclaimer

This tool is for informational purposes only. Not financial advice. Always do your own research before making investment decisions.

## License

MIT License - Free to use and modify
