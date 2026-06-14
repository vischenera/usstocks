# Quick Start Guide - US Stock Scanner for INDmoney

## 🎯 Which Scanner Should You Use?

### 🔥 **indmoney_momentum_scanner.py** (RECOMMENDED)
**Best for**: Indian swing traders on INDmoney focusing on small/mid caps

**Features**:
- ✅ Scans ALL 8,000+ US stocks (complete market coverage)
- ✅ Filters for small/mid cap momentum stocks ($100M-$10B)
- ✅ Liquidity filters (200K+ daily volume)
- ✅ Momentum scoring (price action + volume)
- ✅ 15% trailing stop loss indicator
- ✅ Optimized for swing trading (days/weeks)
- ✅ Auto-downloads ticker lists daily

**Run Command**:
```bash
python indmoney_momentum_scanner.py
```

**Expected Time**: 15-30 minutes for full scan
**Expected Results**: 50-200 qualified stocks

---

### 📊 **stock_scanner_enhanced.py** (ALTERNATIVE)
**Best for**: Quick scans of major indices only

**Features**:
- ✅ Scans S&P 500 + NASDAQ 100 (~600 stocks)
- ✅ Faster scan time (5-10 minutes)
- ✅ Good for large/mega cap stocks
- ⚠️ Misses small cap opportunities
- ⚠️ No momentum scoring

**Run Command**:
```bash
python stock_scanner_enhanced.py
```

---

### 📝 **stock_scanner.py** (BASIC)
**Best for**: Testing/learning

**Features**:
- ✅ Scans ~150 major stocks
- ✅ Very fast (2-5 minutes)
- ⚠️ Limited coverage
- ⚠️ No filters for market cap/liquidity

**Run Command**:
```bash
python stock_scanner.py
```

---

## 🚀 First Time Setup

### Step 1: Install Python
Download from python.org (version 3.8+)

### Step 2: Install Dependencies
```bash
pip install yfinance pandas numpy
```

### Step 3: Run Scanner
```bash
# Recommended for INDmoney swing trading
python indmoney_momentum_scanner.py
```

### Step 4: Check Results
- Output displayed in terminal
- CSV file saved with timestamp
- Open CSV in Excel/Google Sheets

---

## ⚙️ Quick Configuration Tips

### For Faster Testing (First Run)

Open `indmoney_momentum_scanner.py` and find this line:
```python
tickers = get_all_us_tickers()
```

Add this line right after:
```python
tickers = tickers[:500]  # Test with 500 stocks only
```

This reduces scan time from 30 mins to ~5 mins.

---

### Focus on Different Market Caps

**Micro Cap** (Highest risk/reward):
```python
MIN_MCAP = 10_000_000     # $10M
MAX_MCAP = 300_000_000    # $300M
```

**Small Cap** (Balanced - Default):
```python
MIN_MCAP = 100_000_000    # $100M
MAX_MCAP = 2_000_000_000  # $2B
```

**Mid Cap Only**:
```python
MIN_MCAP = 300_000_000     # $300M
MAX_MCAP = 10_000_000_000  # $10B
```

**Large Cap** (Lower volatility):
```python
MIN_MCAP = 10_000_000_000  # $10B+
MAX_MCAP = 1_000_000_000_000  # No real limit
```

---

### Sort by Different Metrics

Change this line:
```python
SORT_BY = 'period_gain_pct'  # Top gainers (default)
```

To:
```python
SORT_BY = 'momentum_score'  # Strongest momentum
# or
SORT_BY = 'volatility'  # Highest volatility
```

---

## 📊 Understanding Your Results

### What to Look For

**Great Swing Trade Candidates**:
- ✅ Gain% > 15%
- ✅ Momentum Score > 5
- ✅ Volume > 500K daily
- ✅ Distance to Stop > 10%
- ✅ Status: ✅ LIVE (not stopped out)

**Risky Signals**:
- ⚠️ Distance to Stop < 5% (could hit stop soon)
- ⚠️ Very low volume (<100K)
- ⚠️ Negative momentum score
- ⚠️ Already hit stop loss (❌ STOP)

---

## 💡 Sample Trade Flow

### 1. Run Scanner
```bash
python indmoney_momentum_scanner.py
```

### 2. Review Top 20 Stocks
Look at CSV file, filter for:
- Market cap: $200M - $2B
- Momentum score: >8
- Volume: >1M daily

### 3. Research Top 5-10
- Check company website
- Read recent news
- Look at earnings reports
- View chart on TradingView

### 4. Select 2-3 Stocks
- Diversify across sectors
- Choose different market caps
- Stagger your entries

### 5. Execute on INDmoney
- Calculate position size (2-3% risk)
- Enter the trade
- Set price alert at stop level
- Document your trade plan

### 6. Monitor Daily
- Check stop loss levels
- Adjust trailing stop as price rises
- Review momentum changes
- Be ready to exit

---

## ⏰ Recommended Scan Schedule

**Daily Scans** (for active trading):
- Run every evening after US market close
- Best time: 2:00 AM IST (after market closes)
- Review changes in top 100

**Weekly Scans** (for casual swing trading):
- Run every weekend
- Compare week-over-week changes
- Focus on new entries in top 20

**Monthly Scans** (for longer holds):
- First weekend of each month
- Identify new sector trends
- Rebalance portfolio if needed

---

## 🎓 Learning Path

### Week 1: Setup & Understanding
- [ ] Install scanner
- [ ] Run first scan
- [ ] Understand all columns
- [ ] Read README fully

### Week 2: Paper Trading
- [ ] Track 10 stocks daily
- [ ] Note entry/exit signals
- [ ] Practice stop loss discipline
- [ ] Track hypothetical P&L

### Week 3: Small Real Trades
- [ ] Start with $100-500 per trade
- [ ] Trade 1-2 positions max
- [ ] Follow your plan strictly
- [ ] Journal every trade

### Week 4+: Scale Gradually
- [ ] Increase position sizes slowly
- [ ] Add more positions (max 5-8)
- [ ] Refine your strategy
- [ ] Keep learning

---

## 🆘 Common Issues & Solutions

### Issue: Scanner shows "No stocks qualified"
**Solution**: 
```python
# Relax filters
MIN_VOLUME = 100_000  # Lower from 200K
MAX_MCAP = 20_000_000_000  # Increase from 10B
```

### Issue: Takes too long to scan
**Solutions**:
1. Test with 500 stocks first
2. Reduce MAX_WORKERS to 20
3. Use stock_scanner_enhanced.py instead

### Issue: Getting errors on many tickers
**Normal**: Some tickers are delisted/invalid
**Solution**: Scanner automatically skips them

### Issue: Results look outdated
**Solution**: Yahoo Finance has 15-min delay (free tier)

---

## 📞 Where to Get Help

**Scanner Technical Issues**:
- Review code comments
- Check configuration settings
- Test with fewer stocks

**Trading/Strategy Questions**:
- YouTube: Search "swing trading small caps"
- Discord: Join US stock trading communities
- Books: "Swing Trading for Dummies"

**INDmoney Platform**:
- Support: support@indmoney.com
- Website: www.indmoney.com/support
- In-app chat (fastest response)

**Tax/Legal**:
- Chartered Accountant familiar with DTAA
- RBI LRS guidelines
- Income tax form 67 for foreign tax credit

---

## ✅ Pre-Trade Checklist

Before placing ANY trade:

- [ ] Stock price >$2 (avoid penny stocks)
- [ ] Average volume >200K shares/day
- [ ] Positive momentum score
- [ ] At least 10% distance to stop
- [ ] Checked recent company news
- [ ] Position size calculated (2-3% account risk)
- [ ] Stop loss level noted
- [ ] Target profit defined (20-30%)
- [ ] Can monitor trade during US hours (or set alerts)
- [ ] Have funds in INDmoney USD wallet

---

## 🎯 Success Metrics to Track

**Weekly**:
- Number of trades
- Win rate (winning trades / total trades)
- Average gain per winning trade
- Average loss per losing trade
- Largest win/loss

**Monthly**:
- Total P&L
- Return on capital (%)
- Best performing sector
- Most profitable stock
- Lessons learned

**Quarterly**:
- Compare to S&P 500 benchmark
- Review and refine strategy
- Adjust filters if needed
- Portfolio rebalancing

---

## 🚀 Ready to Start?

1. **Run your first scan**:
   ```bash
   python indmoney_momentum_scanner.py
   ```

2. **Study the top 20 results**

3. **Paper trade for 2 weeks minimum**

4. **Start small with real money**

5. **Scale up gradually as you gain confidence**

---

**Remember**: 
- 📚 Education before execution
- 💪 Discipline beats strategy
- 📊 Paper trade first
- 🎯 Small steps, big gains

**Good luck with your swing trading journey!** 🚀📈
