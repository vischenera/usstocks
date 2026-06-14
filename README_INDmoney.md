# US Stock Momentum Scanner for INDmoney (India)

A Python scanner specifically designed for **Indian investors trading US stocks through INDmoney**, focusing on **small/mid cap momentum stocks** ideal for **swing trading**.

## 🎯 Purpose

This scanner helps you find high-momentum US stocks that are:
- **Small to Mid Cap** ($100M - $10B market cap) - Higher growth potential
- **High Liquidity** (200K+ daily volume) - Easy to enter/exit positions  
- **Strong Momentum** - Trending with volume confirmation
- **Swing Trading Suitable** - Hold for days/weeks (NOT intraday)
- **15% Trailing Stop** - Built-in risk management

## ⚖️ Legal Note for Indian Investors

✅ **ALLOWED**: Swing trading (buying and holding for days/weeks)  
❌ **NOT ALLOWED**: 
- Intraday trading (buying and selling same day)
- Derivatives (options, futures)
- Margin/leverage trading with US brokers

**LRS Limit**: ₹ $250,000/year for all overseas investments (RBI regulation)

## 📊 What Makes This Different?

Unlike generic stock scanners, this tool:

1. **Scans ALL US stocks** (~8,000+ stocks from NASDAQ + NYSE)
2. **Filters for momentum** - Not just gainers, but stocks with strong momentum + volume
3. **Small/Mid cap focus** - Higher volatility = better swing trading opportunities
4. **Liquidity filters** - Ensures you can actually trade these stocks
5. **Auto-downloads ticker lists** - Always up-to-date from official NASDAQ FTP

## 🚀 Quick Start

### Installation

```bash
# Install required packages
pip install yfinance pandas numpy

# Or use requirements file
pip install -r requirements.txt
```

### Run the Scanner

```bash
python indmoney_momentum_scanner.py
```

**First run will take 15-30 minutes** as it scans thousands of stocks. Subsequent runs can be faster if you adjust filters.

## 📈 Understanding the Output

### Column Explanations

| Column | Description |
|--------|-------------|
| **#** | Rank (1 = highest gain/momentum) |
| **Ticker** | Stock symbol (e.g., NVDA, TSLA) |
| **Company** | Company name |
| **Sector** | Industry sector |
| **MCap** | Market capitalization (company size) |
| **Gain%** | Percentage gain over scan period |
| **Price** | Current stock price |
| **Stop$** | 15% trailing stop loss level |
| **Vol** | Average daily trading volume |
| **Momentum** | Momentum score (higher = stronger) |
| **Status** | ✅ LIVE (active) or ❌ STOP (stop hit) |

### Example Output

```
#   Ticker  Company                   Sector          MCap    Gain%   Price    Stop$   Vol      Momentum  Status
1   ABCD    Example Tech Corp         Technology      $450M   +45.2%  $25.50   $21.67  2.5M     +12.3     ✅LIVE
2   WXYZ    Growth Industries Inc     Healthcare      $850M   +38.7%  $42.30   $35.96  1.8M     +10.8     ✅LIVE
```

## ⚙️ Customization

### Basic Filters (in code)

Open `indmoney_momentum_scanner.py` and modify these variables in the `main()` function:

```python
# Scan period
SCAN_PERIOD = '30d'      # Options: '7d', '14d', '30d', '60d', '90d'

# Price range
MIN_PRICE = 2.0          # Minimum: $2 (avoid penny stocks)
MAX_PRICE = 500          # Maximum: $500

# Liquidity (daily volume)
MIN_VOLUME = 200_000     # Minimum: 200K shares/day

# Market cap range
MIN_MCAP = 100_000_000   # Min: $100M (small cap)
MAX_MCAP = 10_000_000_000  # Max: $10B (mid cap)

# Sorting
SORT_BY = 'period_gain_pct'  # Options below
```

### Sorting Options

Change `SORT_BY` to focus on different aspects:

- `'period_gain_pct'` - **Top Gainers** (default)
- `'momentum_score'` - **Strongest Momentum** (volume + price action)
- `'volatility'` - **Highest Volatility** (more swing potential)

### Market Cap Focus

Adjust these for different strategies:

**Micro Cap** (Higher risk, higher reward):
```python
MIN_MCAP = 10_000_000    # $10M
MAX_MCAP = 300_000_000   # $300M
```

**Small Cap** (Balanced):
```python
MIN_MCAP = 100_000_000   # $100M
MAX_MCAP = 2_000_000_000 # $2B
```

**Mid Cap Only**:
```python
MIN_MCAP = 2_000_000_000   # $2B
MAX_MCAP = 10_000_000_000  # $10B
```

**Large Cap** (Lower risk):
```python
MIN_MCAP = 10_000_000_000  # $10B
MAX_MCAP = 1_000_000_000_000  # $1T (no limit basically)
```

### Quick Test (Faster Scan)

For testing, limit the number of stocks scanned:

```python
# In main() function, after getting tickers:
tickers = tickers[:500]  # Only scan first 500 stocks
```

## 📊 How the Scanner Works

### 1. **Ticker Collection**
Downloads complete lists from official NASDAQ FTP:
- NASDAQ-listed stocks
- NYSE-listed stocks  
- Other US exchanges

### 2. **Initial Filtering**
Removes stocks that don't meet basic criteria:
- Price too low (<$2) or too high (>$500)
- Low volume (<200K daily)
- Wrong market cap (too small or too large)

### 3. **Metric Calculation**

**Trailing Stop Loss (15%)**:
- Finds highest price in period
- Stop = Highest Price × 0.85 (15% below peak)
- Tracks distance to stop loss

**Momentum Score**:
- Compares recent vs previous price action
- Considers volume trends
- Higher score = stronger momentum

**Volatility**:
- Measures price fluctuation
- Higher volatility = more swing opportunities

### 4. **Ranking & Display**
Sorts stocks by chosen metric and shows top 100.

## 💡 Swing Trading Strategy Guide

### Entry Signals (Combined Indicators)
1. **High momentum score** (>5)
2. **Stock gaining with increasing volume**
3. **Not too close to stop loss** (>10% distance)
4. **Uptrending on daily chart**

### Exit Signals
1. **15% trailing stop hit** (automatic protection)
2. **Momentum score turns negative**
3. **Volume dries up significantly**
4. **Target profit reached** (20-30% gains)

### Risk Management
- Never risk more than 2-3% of capital per trade
- Use the 15% trailing stop religiously
- Diversify across 5-8 positions
- Don't trade with money you need soon

### Typical Swing Trade Timeline
- **Hold period**: 3-30 days
- **Target**: 15-30% gain
- **Stop loss**: 15% from peak
- **Review**: Daily after US market close (8:00 PM IST)

## 🕐 Best Times to Trade (IST)

US Market Hours in Indian Time:
- **Regular Session**: 7:00 PM - 1:30 AM IST (Mon-Fri)
- **Pre-Market**: 5:30 PM - 7:00 PM IST (limited)
- **After-Hours**: 1:30 AM - 6:00 AM IST (limited)

**Best Practice**: Place orders during regular session hours for best liquidity.

## 💰 INDmoney Specific Tips

### Fractional Shares
INDmoney allows fractional share investing. If a stock costs $100:
- You can buy 0.5 shares for $50
- Useful for expensive stocks
- Minimum: $1 worth

### Currency Conversion
- INDmoney converts INR to USD
- Exchange rate: Check SBI TT buying rate
- Usually takes 12-24 hours for funds to reflect

### Tax Implications (India)

**Short Term** (held <24 months):
- Taxed at your income tax slab rate
- Add to your annual income

**Long Term** (held >24 months):
- Taxed at 12.5% (without indexation)
- Lower tax rate benefit

**Dividends**:
- 25% US withholding tax (automatic)
- Can claim as foreign tax credit in India (Form 67)

## 📁 Output Files

Each scan creates a CSV file with timestamp:
```
indmoney_top_100_momentum_stocks_20251106_143022.csv
```

**CSV Contents**:
- All displayed data in spreadsheet format
- Import to Excel/Google Sheets for analysis
- Track stocks over time

## ⚠️ Important Warnings

1. **Not Financial Advice**: This is a screening tool, not investment advice
2. **Do Your Research**: Always research companies before investing
3. **Past Performance ≠ Future Results**: Historical gains don't guarantee future gains
4. **Small Caps Are Risky**: Higher volatility means higher risk
5. **API Rate Limits**: Yahoo Finance may rate-limit if you scan too frequently
6. **Data Delays**: Market data may have 15-minute delay
7. **Currency Risk**: USD/INR fluctuations affect returns

## 🔧 Troubleshooting

### "No stocks met the criteria"
**Solution**: Relax filters - increase MAX_MCAP or decrease MIN_VOLUME

### Scan taking too long
**Solutions**:
- Test with fewer stocks first (limit to 500-1000)
- Increase MAX_WORKERS (but don't exceed 50)
- Check internet connection

### "Connection timed out" errors  
**Solutions**:
- Reduce MAX_WORKERS (try 20)
- Wait a few minutes and retry
- Some tickers may be delisted (normal)

### Getting old data
**Solution**: Yahoo Finance cache - wait 15 mins or change SCAN_PERIOD

## 🎓 Learning Resources

### Swing Trading
- Investopedia: Swing Trading Guide
- TradingView: Chart analysis tutorials
- YouTube: Indian US Stock investing channels

### INDmoney Platform
- INDmoney Support: support.indmoney.com
- INDmoney Blog: US Stock trading articles
- LRS Guidelines: RBI website

### Technical Analysis
- Moving averages
- RSI (Relative Strength Index)
- Volume analysis
- Support/resistance levels

## 📞 Support

For scanner issues:
- Check code comments
- Review configuration settings
- Test with small dataset first

For INDmoney platform issues:
- Visit: support.indmoney.com
- Email: support@indmoney.com
- In-app chat support

## 📋 Checklist Before Trading

- [ ] INDmoney account opened and KYC completed
- [ ] Federal Bank account linked (for USD conversion)
- [ ] Understand LRS limit ($250K/year)
- [ ] Researched the company fundamentals
- [ ] Checked recent news and earnings
- [ ] Set realistic profit target (20-30%)
- [ ] Know your stop loss level (15% trailing)
- [ ] Calculated position size (2-3% risk max)
- [ ] Have exit plan ready

## 🚀 Advanced Usage

### Scan Specific Sectors Only

Modify `fetch_stock_data()` to filter by sector:

```python
# In fetch_stock_data() after getting sector
allowed_sectors = ['Technology', 'Healthcare', 'Consumer Cyclical']
if sector not in allowed_sectors:
    return (ticker, None)
```

### Add Price Alerts

Combine with price alert scripts to get notified when:
- New stocks meet criteria
- Stop losses hit
- Target profits reached

### Backtesting

Export CSV data to backtest strategies:
- Track which stocks hit stops
- Measure average hold time
- Calculate win rate

## 📜 Disclaimer

This tool is for **educational and informational purposes only**. It is **not financial advice**.

- **Risk Warning**: Stock trading involves substantial risk of loss
- **No Guarantees**: Past performance does not indicate future results  
- **Your Responsibility**: All investment decisions are yours alone
- **Consult Professionals**: Speak to a SEBI registered advisor if unsure
- **Tax Compliance**: Ensure proper tax filing for US investments

The creator assumes no liability for trading losses.

## 📄 License

MIT License - Free to use and modify

---

**Happy Swing Trading! 📈🚀**

*Remember: The best trade is often the one you don't take. Be patient, be disciplined, and manage your risk.*
