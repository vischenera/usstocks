#!/usr/bin/env python3
"""
US Stock Scanner v3.0 - INCREMENTAL with DUAL RESUME
For INDmoney India - By Vishnu

Features:
- Full scan with resume (handles Yahoo rate limits)
- Incremental updates (fetch only missing days)
- Rolling 90-day window
- Dual resume capability (full scan + updates)
- 30 workers for speed
- Complete filtering system
- Auto-pause 15 min on rate limit with resume
- Handles Yahoo crumb/auth errors as rate limits
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
import urllib.request
import pickle
import os
import json
import threading

warnings.filterwarnings('ignore')

# Cache files
CACHE_FILE = "stock_data_cache.pkl"
CACHE_METADATA_FILE = "cache_metadata.json"

# Full scan progress
FULL_SCAN_PROGRESS = "full_scan_progress.json"
FULL_SCAN_PARTIAL = "full_scan_partial.pkl"

# Update progress
UPDATE_PROGRESS = "update_progress.json"
UPDATE_PARTIAL = "update_partial.pkl"

# Global rate limiter
rate_limit_lock = threading.Lock()
last_request_time = [0]


def enforce_rate_limit(min_interval=0.15):
    """Global rate limiter - ~6-7 req/s with 30 workers"""
    with rate_limit_lock:
        current_time = time.time()
        time_since_last = current_time - last_request_time[0]

        if time_since_last < min_interval:
            sleep_time = min_interval - time_since_last
            time.sleep(sleep_time)

        last_request_time[0] = time.time()


def pause_on_rate_limit():
    """Pause for 15 minutes with countdown feedback"""
    print(f"\n{'=' * 80}")
    print("⏸️  RATE LIMIT DETECTED")
    print("Pausing for 15 minutes (900 seconds)...")
    print(f"{'=' * 80}")

    # Simple countdown (1% increments for feedback)
    total_seconds = 900
    for remaining in range(total_seconds, 0, -30):  # Print every 30s
        if remaining % 60 == 0:
            mins_left = remaining // 60
            print(f"⏳ Waiting {mins_left} more minutes... (Press Ctrl+C to interrupt)")
        time.sleep(30)

    print("✅ Pause complete. Resuming scan...")
    print(f"{'=' * 80}\n")


class IncrementalScanner:
    """Scanner with incremental update and dual resume"""

    def __init__(self):
        self.cached_data = {}
        self.cache_date = None
        self.tickers = []

    # ========== TICKER MANAGEMENT ==========

    def download_nasdaq_tickers(self):
        """Download NASDAQ tickers"""
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
            return tickers
        except Exception as e:
            print(f"⚠ Error: {e}")
            return []

    def download_other_exchange_tickers(self):
        """Download NYSE and other exchanges"""
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

            print(f"✓ Downloaded {len(tickers)} NYSE/Other tickers")
            return tickers
        except Exception as e:
            print(f"⚠ Error: {e}")
            return []

    def get_all_us_tickers(self):
        """Get all US tickers"""
        print("=" * 80)
        print("FETCHING US STOCK UNIVERSE")
        print("=" * 80)

        nasdaq = self.download_nasdaq_tickers()
        other = self.download_other_exchange_tickers()

        self.tickers = list(set(nasdaq + other))

        print("-" * 80)
        print(f"Total tickers: {len(self.tickers)}")
        print("=" * 80)
        print()

        return self.tickers

    # ========== CACHE MANAGEMENT ==========

    def load_cache_metadata(self):
        """Load cache metadata with validation"""
        if os.path.exists(CACHE_METADATA_FILE):
            try:
                with open(CACHE_METADATA_FILE, 'r') as f:
                    data = json.load(f)
                # Validate required keys
                required_keys = ['cache_date', 'stock_count', 'period_days']
                if not all(key in data for key in required_keys):
                    print("⚠ Incomplete metadata. Deleting and regenerating...")
                    os.remove(CACHE_METADATA_FILE)
                    return None
                return data
            except (json.JSONDecodeError, KeyError) as e:
                print(f"⚠ Corrupted metadata: {e}. Deleting...")
                if os.path.exists(CACHE_METADATA_FILE):
                    os.remove(CACHE_METADATA_FILE)
                return None
        return None

    def save_cache_metadata(self, stock_count):
        """Save cache metadata"""
        metadata = {
            'cache_date': datetime.now().isoformat(),
            'stock_count': stock_count,
            'period_days': 90
        }
        with open(CACHE_METADATA_FILE, 'w') as f:
            json.dump(metadata, f, indent=2)

    def load_cache(self):
        """Load cache"""
        if os.path.exists(CACHE_FILE):
            print(f"\n{'=' * 80}")
            print("LOADING CACHE")
            print(f"{'=' * 80}")
            try:
                with open(CACHE_FILE, 'rb') as f:
                    cache_list = pickle.load(f)
                    self.cached_data = {item['ticker']: item for item in cache_list}

                metadata = self.load_cache_metadata()
                if metadata:
                    self.cache_date = datetime.fromisoformat(metadata['cache_date'])
                    age = datetime.now() - self.cache_date
                    print(f"✓ Loaded: {len(self.cached_data)} stocks")
                    print(f"✓ Date: {self.cache_date.strftime('%Y-%m-%d %H:%M')}")
                    print(f"✓ Age: {age.days}d {age.seconds // 3600}h")
                    print(f"{'=' * 80}\n")
                    return True
                else:
                    print("⚠ Loaded data but metadata invalid. Run full scan to fix.")
                    print(f"{'=' * 80}\n")
                    return True  # Data loaded, but metadata needs fix
            except Exception as e:
                print(f"⚠ Error: {e}")
                return False
        return False

    def save_cache(self, data_dict):
        """Save cache"""
        print(f"\n{'=' * 80}")
        print("SAVING CACHE")
        print(f"{'=' * 80}")
        try:
            cache_list = list(data_dict.values())

            with open(CACHE_FILE, 'wb') as f:
                pickle.dump(cache_list, f)

            self.save_cache_metadata(len(cache_list))
            self.cached_data = data_dict

            print(f"✓ Saved: {len(cache_list)} stocks")
            print(f"{'=' * 80}\n")
            return True
        except Exception as e:
            print(f"⚠ Error: {e}")
            return False

    # ========== FULL SCAN PROGRESS ==========

    def load_full_scan_progress(self):
        """Load full scan progress"""
        processed = set()
        results = {}

        if os.path.exists(FULL_SCAN_PROGRESS):
            with open(FULL_SCAN_PROGRESS, 'r') as f:
                data = json.load(f)
                processed = set(data.get('processed', []))

        if os.path.exists(FULL_SCAN_PARTIAL):
            with open(FULL_SCAN_PARTIAL, 'rb') as f:
                result_list = pickle.load(f)
                results = {item['ticker']: item for item in result_list}

        return processed, results

    def save_full_scan_progress(self, processed, results):
        """Save full scan progress"""
        with open(FULL_SCAN_PROGRESS, 'w') as f:
            json.dump({
                'processed': list(processed),
                'count': len(processed),
                'timestamp': datetime.now().isoformat()
            }, f, indent=2)

        with open(FULL_SCAN_PARTIAL, 'wb') as f:
            pickle.dump(list(results.values()), f)

    def clear_full_scan_progress(self):
        """Clear full scan progress"""
        for file in [FULL_SCAN_PROGRESS, FULL_SCAN_PARTIAL]:
            if os.path.exists(file):
                os.remove(file)

    # ========== UPDATE PROGRESS ==========

    def load_update_progress(self):
        """Load update progress"""
        processed = set()
        results = {}

        if os.path.exists(UPDATE_PROGRESS):
            with open(UPDATE_PROGRESS, 'r') as f:
                data = json.load(f)
                processed = set(data.get('processed', []))

        if os.path.exists(UPDATE_PARTIAL):
            with open(UPDATE_PARTIAL, 'rb') as f:
                result_list = pickle.load(f)
                results = {item['ticker']: item for item in result_list}

        return processed, results

    def save_update_progress(self, processed, results):
        """Save update progress"""
        with open(UPDATE_PROGRESS, 'w') as f:
            json.dump({
                'processed': list(processed),
                'count': len(processed),
                'timestamp': datetime.now().isoformat()
            }, f, indent=2)

        with open(UPDATE_PARTIAL, 'wb') as f:
            pickle.dump(list(results.values()), f)

    def clear_update_progress(self):
        """Clear update progress"""
        for file in [UPDATE_PROGRESS, UPDATE_PARTIAL]:
            if os.path.exists(file):
                os.remove(file)

    # ========== DATA FETCHING ==========

    def fetch_stock_full(self, ticker, period='90d', retries=2):
        """Fetch full 90 days with retries and headers"""
        for attempt in range(retries):
            try:
                enforce_rate_limit(min_interval=0.15)

                # Add browser headers to mimic real user
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                stock = yf.Ticker(ticker)
                hist = stock.history(period=period, headers=headers)

                if hist.empty or len(hist) < 5:
                    return (ticker, None)

                current_price = hist['Close'].iloc[-1]
                avg_volume = hist['Volume'].mean()

                # Get info with same headers
                market_cap = 0
                company_name = ticker
                sector = 'N/A'

                try:
                    enforce_rate_limit(min_interval=0.15)
                    info = stock.info
                    market_cap = info.get('marketCap', 0)
                    company_name = info.get('longName', info.get('shortName', ticker))
                    sector = info.get('sector', 'N/A')
                except:
                    pass

                stock_data = {
                    'ticker': ticker,
                    'company_name': company_name,
                    'sector': sector,
                    'market_cap': market_cap,
                    'current_price': float(current_price),
                    'avg_volume': int(avg_volume),
                    'historical_data': hist,
                    'last_updated': datetime.now().isoformat()
                }

                return (ticker, stock_data)

            except Exception as e:
                error_msg = str(e).lower()
                # Expanded keywords: Add 401, unauthorized, crumb, access denied
                if any(x in error_msg for x in
                       ['rate limit', '429', '401', 'unauthorized', 'invalid crumb', 'unable to access',
                        'yahoo-finance-api-feedback']):
                    if attempt < retries - 1:
                        print(f"⚠️  Retry {attempt + 1} for {ticker} (auth error)")
                        time.sleep(5)  # Short wait before retry
                        continue
                    raise Exception(f"RATE_LIMITED: {e}")  # Escalate to trigger pause
                return (ticker, None)

    def fetch_stock_incremental(self, ticker, existing_data, days_to_fetch, retries=2):
        """Fetch only missing days and merge with retries and headers"""
        for attempt in range(retries):
            try:
                enforce_rate_limit(min_interval=0.15)

                # Add browser headers
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                stock = yf.Ticker(ticker)

                # Fetch missing days
                period_str = f"{days_to_fetch}d"
                new_hist = stock.history(period=period_str, headers=headers)

                if new_hist.empty:
                    return (ticker, existing_data)

                # Merge
                old_hist = existing_data['historical_data']
                combined_hist = pd.concat([old_hist, new_hist])
                combined_hist = combined_hist[~combined_hist.index.duplicated(keep='last')]
                combined_hist = combined_hist.sort_index()

                # Keep last 90 days
                if len(combined_hist) > 90:
                    combined_hist = combined_hist.iloc[-90:]

                # Update metrics
                current_price = combined_hist['Close'].iloc[-1]
                avg_volume = combined_hist['Volume'].mean()

                # Update info
                market_cap = existing_data['market_cap']
                company_name = existing_data['company_name']
                sector = existing_data['sector']

                try:
                    enforce_rate_limit(min_interval=0.15)
                    info = stock.info
                    market_cap = info.get('marketCap', market_cap)
                    company_name = info.get('longName', info.get('shortName', company_name))
                    sector = info.get('sector', sector)
                except:
                    pass

                updated_data = {
                    'ticker': ticker,
                    'company_name': company_name,
                    'sector': sector,
                    'market_cap': market_cap,
                    'current_price': float(current_price),
                    'avg_volume': int(avg_volume),
                    'historical_data': combined_hist,
                    'last_updated': datetime.now().isoformat()
                }

                return (ticker, updated_data)

            except Exception as e:
                error_msg = str(e).lower()
                if any(x in error_msg for x in
                       ['rate limit', '429', '401', 'unauthorized', 'invalid crumb', 'unable to access',
                        'yahoo-finance-api-feedback']):
                    if attempt < retries - 1:
                        print(f"⚠️  Retry {attempt + 1} for {ticker} (auth error)")
                        time.sleep(5)
                        continue
                    raise Exception(f"RATE_LIMITED: {e}")
                return (ticker, existing_data)

    # ========== FULL SCAN ==========

    def full_scan(self, max_workers=30, resume=False):
        """Full scan with resume"""
        if not self.tickers:
            self.get_all_us_tickers()

        if not self.tickers:
            print("⚠ No tickers found")
            return False

        # Load progress if resuming
        processed = set()
        results = {}

        if resume:
            processed, results = self.load_full_scan_progress()
            if processed:
                print(f"\n{'=' * 80}")
                print(f"📂 RESUMING FULL SCAN")
                print(f"{'=' * 80}")
                print(f"Processed: {len(processed)}/{len(self.tickers)}")
                print(f"Valid: {len(results)}")
                print(f"Remaining: {len(self.tickers) - len(processed)}")
                print(f"{'=' * 80}\n")

        tickers_to_process = [t for t in self.tickers if t not in processed]

        if not tickers_to_process:
            print("✓ All processed!")
            self.save_cache(results)
            self.clear_full_scan_progress()
            return True

        print(f"\n{'=' * 80}")
        print(f"FULL SCAN - {len(tickers_to_process)} STOCKS")
        print(f"{'=' * 80}")
        print(f"Workers: {max_workers}")
        print(f"Expected: ~{len(tickers_to_process) * 0.35 / 60:.0f} min until rate limit")
        print(f"\n⚠️  Auto-pause on limit/crumb (15 min), then resumes automatically")
        print(f"{'=' * 80}\n")

        total_original = len(self.tickers)  # For final reporting
        processed = set(processed)  # Ensure it's a set
        results = dict(results)  # Ensure dict
        tickers_to_process = [t for t in self.tickers if t not in processed]  # Refresh if resuming

        completed_total = len(processed)
        rate_limited_count = 0
        start_time = time.time()

        while tickers_to_process:  # Loop until all done
            batch_size = len(tickers_to_process)
            print(f"\n🔄 Processing batch of {batch_size} remaining stocks...")
            start_time_batch = time.time()
            batch_rate_limited = False

            try:
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_to_ticker = {
                        executor.submit(self.fetch_stock_full, ticker, '90d'): ticker
                        for ticker in tickers_to_process[:2000]
                        # Limit batch to ~2000 to avoid quick re-limits (adjust if needed)
                    }

                    save_interval = 100
                    batch_completed = 0

                    for future in as_completed(future_to_ticker):
                        try:
                            ticker, data = future.result()
                            batch_completed += 1
                            completed_total += 1
                            processed.add(ticker)

                            if data is not None:
                                results[ticker] = data

                            if batch_completed % save_interval == 0:
                                self.save_full_scan_progress(processed, results)
                                print(f"💾 Saved ({completed_total}/{total_original}, {len(results)} valid)")

                            # Progress update
                            if batch_completed % max(1, batch_size // 20) == 0:
                                pct = (completed_total / total_original) * 100
                                elapsed = time.time() - start_time_batch
                                rate = batch_completed / elapsed if elapsed > 0 else 0
                                eta = (batch_size - batch_completed) / rate if rate > 0 else 0
                                print(f"Batch Progress: {batch_completed}/{batch_size} | "
                                      f"Overall: {completed_total}/{total_original} ({pct:.1f}%) | "
                                      f"Rate: {rate:.1f}/s | Batch ETA: {eta / 60:.1f}min")

                        except Exception as e:
                            error_msg = str(e).lower()
                            if any(x in error_msg for x in
                                   ['rate limit', '429', '401', 'unauthorized', 'invalid crumb', 'unable to access',
                                    'yahoo-finance-api-feedback']):
                                rate_limited_count += 1
                                batch_rate_limited = True
                                print(f"\n⚠️  Rate limit hit on {future_to_ticker[future]} (#{rate_limited_count})")
                                # Mark as processed to skip retry
                                processed.add(future_to_ticker[future])
                                completed_total += 1
                                break  # Break batch on limit
                            else:
                                # Other errors: skip
                                print(f"⚠️  Error on {future_to_ticker[future]}: {e}")
                                processed.add(future_to_ticker[future])
                                completed_total += 1

                    # Update remaining after batch
                    tickers_to_process = [t for t in self.tickers if t not in processed]

            except KeyboardInterrupt:
                print(f"\n⚠️  Interrupted during batch")
                break

            # If rate limited in this batch, pause and continue to next batch
            if batch_rate_limited:
                self.save_full_scan_progress(processed, results)
                pause_on_rate_limit()
                # After pause, loop will process remaining
            else:
                # No limit, but if batch done, break while
                break

        # Final summary
        elapsed = time.time() - start_time
        self.save_full_scan_progress(processed, results)

        print(f"\n{'=' * 80}")
        if len(processed) < total_original:
            print(f"⚠️  SCAN PAUSED (interrupted or partial)")
            print(f"✓ Processed: {len(processed)}/{total_original} ({len(processed) / total_original * 100:.1f}%)")
        else:
            print(f"✓ COMPLETE! (with {rate_limited_count} auto-pauses)")
        print(f"✓ Valid: {len(results)}")
        print(f"⏱️  Total Time: {elapsed / 60:.1f} min")
        if len(processed) == total_original:
            self.save_cache(results)
            self.clear_full_scan_progress()
        else:
            print(f"\n💾 Progress saved! Resume with option 2 if needed.")
        print(f"{'=' * 80}\n")

        return len(processed) == total_original

    # ========== INCREMENTAL UPDATE ==========

    def incremental_update(self, max_workers=30, resume=False):
        """Incremental update with resume"""
        if not self.cached_data:
            if not self.load_cache():
                print("⚠ No cache. Run Full Scan first")
                return False

        if self.cache_date is None:
            print("⚠ Cache date missing. Run Full Scan to fix metadata.")
            return False

        if not self.tickers:
            self.get_all_us_tickers()

        # Calculate days to fetch
        cache_age = datetime.now() - self.cache_date
        days_to_fetch = cache_age.days + 1

        if days_to_fetch < 1:
            print("✓ Cache up to date!")
            return True

        print(f"\n{'=' * 80}")
        print(f"INCREMENTAL UPDATE")
        print(f"{'=' * 80}")
        print(f"Cache age: {cache_age.days}d {cache_age.seconds // 3600}h")
        print(f"Fetching: {days_to_fetch} days")
        print(f"Stocks: {len(self.tickers)}")
        print(f"{'=' * 80}\n")

        # Load progress
        processed = set()
        results = dict(self.cached_data)

        if resume:
            processed, partial_results = self.load_update_progress()
            if processed:
                results.update(partial_results)
                print(f"📂 RESUMING UPDATE")
                print(f"Updated: {len(processed)}/{len(self.tickers)}")
                print(f"Remaining: {len(self.tickers) - len(processed)}\n")

        tickers_to_update = [t for t in self.tickers if t not in processed]

        if not tickers_to_update:
            print("✓ All updated!")
            self.save_cache(results)
            self.clear_update_progress()
            return True

        print(f"Updating {len(tickers_to_update)} stocks...")
        print(f"Workers: {max_workers}")
        print(f"Expected: ~{len(tickers_to_update) * 0.35 / 60:.0f} min until rate limit")
        print(f"\n⚠️  Auto-pause on limit/crumb (15 min), then resumes automatically")
        print(f"{'=' * 80}\n")

        total_original = len(self.tickers)
        processed = set(processed)
        results = dict(self.cached_data)  # Start with cached
        if resume:
            _, partial_results = self.load_update_progress()
            results.update(partial_results)

        tickers_to_update = [t for t in self.tickers if t not in processed]
        completed_total = len(processed)
        rate_limited_count = 0
        start_time = time.time()

        while tickers_to_update:
            batch_size = len(tickers_to_update)
            print(f"\n🔄 Processing batch of {batch_size} remaining stocks...")
            start_time_batch = time.time()
            batch_rate_limited = False

            try:
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_to_ticker = {}

                    # Submit only first 2000 for batch (to manage limits)
                    for ticker in tickers_to_update[:2000]:
                        existing = self.cached_data.get(ticker)
                        if existing:
                            future = executor.submit(self.fetch_stock_incremental, ticker, existing, days_to_fetch)
                        else:
                            future = executor.submit(self.fetch_stock_full, ticker, '90d')
                        future_to_ticker[future] = ticker

                    save_interval = 100
                    batch_completed = 0

                    for future in as_completed(future_to_ticker):
                        try:
                            ticker, data = future.result()
                            batch_completed += 1
                            completed_total += 1
                            processed.add(ticker)

                            if data is not None:
                                results[ticker] = data

                            if batch_completed % save_interval == 0:
                                self.save_update_progress(processed, results)
                                print(f"💾 Saved ({completed_total}/{total_original})")

                            if batch_completed % max(1, batch_size // 20) == 0:
                                pct = (completed_total / total_original) * 100
                                elapsed = time.time() - start_time_batch
                                rate = batch_completed / elapsed if elapsed > 0 else 0
                                eta = (batch_size - batch_completed) / rate if rate > 0 else 0
                                print(f"Batch Progress: {batch_completed}/{batch_size} | "
                                      f"Overall: {completed_total}/{total_original} ({pct:.1f}%) | "
                                      f"Rate: {rate:.1f}/s | Batch ETA: {eta / 60:.1f}min")

                        except Exception as e:
                            error_msg = str(e).lower()
                            if any(x in error_msg for x in
                                   ['rate limit', '429', '401', 'unauthorized', 'invalid crumb', 'unable to access',
                                    'yahoo-finance-api-feedback']):
                                rate_limited_count += 1
                                batch_rate_limited = True
                                print(f"\n⚠️  Rate limit hit on {future_to_ticker[future]} (#{rate_limited_count})")
                                processed.add(future_to_ticker[future])
                                completed_total += 1
                                break
                            else:
                                print(f"⚠️  Error on {future_to_ticker[future]}: {e}")
                                processed.add(future_to_ticker[future])
                                completed_total += 1

                    # Update remaining
                    tickers_to_update = [t for t in self.tickers if t not in processed]

            except KeyboardInterrupt:
                print(f"\n⚠️  Interrupted during batch")
                break

            if batch_rate_limited:
                self.save_update_progress(processed, results)
                pause_on_rate_limit()
            else:
                break

        # Final summary
        elapsed = time.time() - start_time
        self.save_update_progress(processed, results)

        print(f"\n{'=' * 80}")
        if len(processed) < total_original:
            print(f"⚠️  UPDATE PAUSED (interrupted or partial)")
            print(f"✓ Updated: {len(processed)}/{total_original} ({len(processed) / total_original * 100:.1f}%)")
        else:
            print(f"✓ COMPLETE! (with {rate_limited_count} auto-pauses)")
        print(f"⏱️  Total Time: {elapsed / 60:.1f} min")
        if len(processed) == total_original:
            self.save_cache(results)
            self.clear_update_progress()
        else:
            print(f"\n💾 Progress saved! Resume with option 4 if needed.")
        print(f"{'=' * 80}\n")

        return len(processed) == total_original

    # ========== FILTERING ==========

    def calculate_metrics(self, hist, period_days, stop_percentage, is_intraday=False):
        """Calculate metrics"""
        if hist is None or len(hist) < 5:
            return None

        if len(hist) > period_days:
            period_data = hist.iloc[-period_days:]
        else:
            period_data = hist

        if len(period_data) < 2:
            return None

        try:
            current_price = period_data['Close'].iloc[-1]
            current_volume = period_data['Volume'].iloc[-1]
            avg_volume = period_data['Volume'].mean()

            if is_intraday and period_days == 1:
                period_start_price = period_data['Open'].iloc[0]
                highest_high = max(period_data['High'].max(), period_data['Open'].iloc[0])
            else:
                period_start_price = period_data['Close'].iloc[0]
                highest_high = period_data['High'].max()

            period_gain_pct = ((current_price - period_start_price) / period_start_price) * 100

            trailing_stop_level = highest_high * (1 - stop_percentage / 100)
            distance_to_stop_pct = ((current_price - trailing_stop_level) / current_price) * 100
            stop_triggered = current_price < trailing_stop_level

            # Momentum
            momentum_score = 0
            if len(period_data) >= 10:
                split = max(3, len(period_data) // 3)
                recent_avg = period_data['Close'].iloc[-split:].mean()
                previous_avg = period_data['Close'].iloc[:-split].mean()

                if previous_avg > 0:
                    momentum_ratio = (recent_avg / previous_avg - 1) * 100
                    recent_vol = period_data['Volume'].iloc[-split:].mean()
                    previous_vol = period_data['Volume'].iloc[:-split].mean()
                    volume_ratio = (recent_vol / previous_vol) if previous_vol > 0 else 1
                    momentum_score = momentum_ratio * (1 + (volume_ratio - 1) * 0.5)

            # Volatility
            volatility = 0
            if len(period_data) >= 5:
                returns = period_data['Close'].pct_change().dropna()
                volatility = returns.std() * (252 ** 0.5) * 100

            return {
                'period_gain_pct': float(period_gain_pct),
                'current_price': float(current_price),
                'highest_high': float(highest_high),
                'trailing_stop_level': float(trailing_stop_level),
                'distance_to_stop_pct': float(distance_to_stop_pct),
                'stop_triggered': bool(stop_triggered),
                'volume': int(current_volume),
                'avg_volume': int(avg_volume),
                'momentum_score': float(momentum_score),
                'volatility': float(volatility)
            }
        except:
            return None

    def apply_filters(self, config):
        """Apply filters"""
        if not self.cached_data:
            if not self.load_cache():
                print("⚠ No cache")
                return []

        print(f"\n{'=' * 80}")
        print("APPLYING FILTERS")
        print(f"{'=' * 80}")
        print(f"Config: {config['name']}")
        print(f"Period: {config['period_days']}d")
        print(f"Stop: {config['stop_percentage']}%")
        print(f"Price: ${config['min_price']}-${config['max_price']}")
        print(f"Volume: >{config['min_volume']:,}")
        print(f"MCap: ${config['min_mcap'] / 1e6:.0f}M-${config['max_mcap'] / 1e9:.1f}B")
        print(f"{'=' * 80}\n")

        results = []
        is_intraday = config['period_days'] == 1

        start = time.time()

        for ticker, stock in self.cached_data.items():
            if stock['current_price'] < config['min_price'] or stock['current_price'] > config['max_price']:
                continue

            if stock['avg_volume'] < config['min_volume']:
                continue

            if stock['market_cap'] < config['min_mcap'] or stock['market_cap'] > config['max_mcap']:
                continue

            metrics = self.calculate_metrics(
                stock['historical_data'],
                config['period_days'],
                config['stop_percentage'],
                is_intraday
            )

            if metrics is None:
                continue

            if metrics['momentum_score'] < config.get('min_momentum', -999):
                continue

            if config.get('max_volatility', 999) < 999:
                if metrics['volatility'] > config['max_volatility']:
                    continue

            result = {
                'ticker': ticker,
                'company_name': stock['company_name'],
                'sector': stock['sector'],
                'market_cap': stock['market_cap'],
                **metrics
            }

            results.append(result)

        elapsed = time.time() - start

        print(f"✓ Done in {elapsed:.2f}s")
        print(f"✓ Qualified: {len(results)}")
        print(f"{'=' * 80}\n")

        return results


# ========== PRESETS ==========

def get_preset_configs():
    """Preset configs"""
    return {
        '1': {
            'name': 'Day Trading (Intraday)',
            'period_days': 1,
            'stop_percentage': 5,
            'min_price': 10.0,
            'max_price': 500,
            'min_volume': 500_000,
            'min_mcap': 100_000_000,
            'max_mcap': 50_000_000_000,
            'min_momentum': 0,
            'max_volatility': 999
        },
        '2': {
            'name': 'Aggressive Swing (10d)',
            'period_days': 10,
            'stop_percentage': 10,
            'min_price': 5.0,
            'max_price': 300,
            'min_volume': 200_000,
            'min_mcap': 50_000_000,
            'max_mcap': 5_000_000_000,
            'min_momentum': 5,
            'max_volatility': 999
        },
        '3': {
            'name': 'Conservative Swing (30d)',
            'period_days': 30,
            'stop_percentage': 15,
            'min_price': 10.0,
            'max_price': 500,
            'min_volume': 100_000,
            'min_mcap': 100_000_000,
            'max_mcap': 10_000_000_000,
            'min_momentum': 0,
            'max_volatility': 999
        },
        '4': {
            'name': 'Momentum (10d)',
            'period_days': 10,
            'stop_percentage': 12,
            'min_price': 5.0,
            'max_price': 200,
            'min_volume': 300_000,
            'min_mcap': 50_000_000,
            'max_mcap': 3_000_000_000,
            'min_momentum': 10,
            'max_volatility': 999
        },
        '5': {
            'name': 'Small Cap (30d)',
            'period_days': 30,
            'stop_percentage': 15,
            'min_price': 2.0,
            'max_price': 50,
            'min_volume': 100_000,
            'min_mcap': 10_000_000,
            'max_mcap': 500_000_000,
            'min_momentum': 0,
            'max_volatility': 999
        }
    }


def custom_config_menu():
    """Custom config"""
    print(f"\n{'=' * 80}")
    print("CUSTOM CONFIGURATION")
    print(f"{'=' * 80}\n")

    config = {'name': 'Custom'}

    while True:
        try:
            period = int(input("Days (1-90): ").strip())
            if 1 <= period <= 90:
                config['period_days'] = period
                break
        except ValueError:
            pass

    while True:
        try:
            stop = float(input("Trailing stop % (5-25): ").strip())
            if 5 <= stop <= 25:
                config['stop_percentage'] = stop
                break
        except ValueError:
            pass

    min_price = float(input("Min price (default 1): ").strip() or "1")
    max_price = float(input("Max price (default 500): ").strip() or "500")
    config['min_price'] = min_price
    config['max_price'] = max_price

    min_volume = int(input("Min volume (default 100K): ").strip() or "100000")
    config['min_volume'] = min_volume

    print("\nMarket Cap:")
    print("  1. Micro: $10M-$300M")
    print("  2. Small: $300M-$2B")
    print("  3. Mid: $2B-$10B")
    print("  4. Large: $10B+")
    print("  5. Custom")

    mcap_choice = input("Select (1-5): ").strip()
    mcap_ranges = {
        '1': (10_000_000, 300_000_000),
        '2': (300_000_000, 2_000_000_000),
        '3': (2_000_000_000, 10_000_000_000),
        '4': (10_000_000_000, 1_000_000_000_000)
    }

    if mcap_choice in mcap_ranges:
        config['min_mcap'], config['max_mcap'] = mcap_ranges[mcap_choice]
    else:
        min_mcap = float(input("Min (millions): ").strip() or "10") * 1_000_000
        max_mcap = float(input("Max (billions): ").strip() or "10") * 1_000_000_000
        config['min_mcap'] = min_mcap
        config['max_mcap'] = max_mcap

    use_momentum = input("\nMomentum filter? (y/n): ").strip().lower()
    if use_momentum == 'y':
        config['min_momentum'] = float(input("Min momentum: ").strip() or "0")
    else:
        config['min_momentum'] = -999

    config['max_volatility'] = 999

    return config


def display_results(stock_data, config, top_n=300, sort_by='period_gain_pct'):
    """Display results"""
    if not stock_data:
        print("⚠ No stocks matched")
        return

    df = pd.DataFrame(stock_data)
    df = df.sort_values(sort_by, ascending=False)
    top = df.head(top_n)

    print("\n" + "=" * 140)
    print(f"TOP {len(top)} - {config['name'].upper()}")
    print(f"{config['period_days']}d | Stop {config['stop_percentage']}%")
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 140)

    print(f"\n{'#':<4}{'Ticker':<8}{'Company':<26}{'Sector':<16}{'MCap':<8}{'Gain%':<8}"
          f"{'Price':<9}{'Stop$':<9}{'Vol':<10}{'Mom':<10}{'Status':<8}")
    print("-" * 140)

    for idx, row in enumerate(top.itertuples(), 1):
        status = "❌STOP" if row.stop_triggered else "✅LIVE"
        mcap = f"${row.market_cap / 1e6:.0f}M" if row.market_cap < 1e9 else f"${row.market_cap / 1e9:.1f}B"
        vol = f"{row.avg_volume / 1e6:.1f}M" if row.avg_volume >= 1e6 else f"{row.avg_volume / 1e3:.0f}K"

        print(f"{idx:<4}{row.ticker:<8}{row.company_name[:24]:<26}{row.sector[:14]:<16}"
              f"{mcap:<8}{row.period_gain_pct:>6.1f}%  ${row.current_price:>6.2f}  "
              f"${row.trailing_stop_level:>6.2f}  {vol:>8}  "
              f"{row.momentum_score:>8.1f}  {status:<8}")

    print("\n" + "=" * 140)
    print("SUMMARY")
    print("=" * 140)

    active = (~top['stop_triggered']).sum()
    print(f"\nPerformance:")
    print(f"  • Avg: {top['period_gain_pct'].mean():.2f}%")
    print(f"  • Median: {top['period_gain_pct'].median():.2f}%")
    print(f"  • Top: {top.iloc[0]['ticker']} (+{top.iloc[0]['period_gain_pct']:.2f}%)")

    print(f"\nStatus:")
    print(f"  • Active: {active} ({active / len(top) * 100:.1f}%)")

    # Save
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"scan_{config['period_days']}d_{ts}.csv"

    export = top.copy()
    export['rank'] = range(1, len(export) + 1)

    cols = ['rank', 'ticker', 'company_name', 'sector', 'market_cap',
            'period_gain_pct', 'momentum_score', 'volatility',
            'current_price', 'highest_high', 'trailing_stop_level',
            'distance_to_stop_pct', 'stop_triggered', 'volume', 'avg_volume']

    export[cols].to_csv(filename, index=False)

    print(f"\n✓ Saved: {filename}")
    print("=" * 140)


# ========== MAIN MENU ==========

def main_menu():
    """Main menu"""
    scanner = IncrementalScanner()

    print("=" * 140)
    print(" " * 30 + "US STOCK SCANNER V3.0 - INCREMENTAL + DUAL RESUME")
    print(" " * 50 + "For INDmoney India")
    print("=" * 140)

    while True:
        print(f"\n{'=' * 80}")
        print("MAIN MENU")
        print(f"{'=' * 80}")

        # Status
        cache_info = scanner.load_cache_metadata()
        full_prog = os.path.exists(FULL_SCAN_PROGRESS)
        update_prog = os.path.exists(UPDATE_PROGRESS)

        if cache_info:
            # Safely extract values with defaults
            stock_count = cache_info.get('stock_count', 'Unknown')
            cache_date_str = cache_info.get('cache_date', None)
            if cache_date_str:
                try:
                    cache_date = datetime.fromisoformat(cache_date_str)
                    age = datetime.now() - cache_date
                    print(f"\n✓ Cache: {stock_count} stocks")
                    print(f"  Date: {cache_date.strftime('%Y-%m-%d %H:%M')}")
                    print(f"  Age: {age.days}d {age.seconds // 3600}h")
                except (ValueError, KeyError):
                    print(f"\n⚠ Cache metadata invalid (corrupted file?)")
            else:
                print(f"\n⚠ Cache metadata missing date")
        else:
            print(f"\n❌ No cache")

        if full_prog:
            try:
                with open(FULL_SCAN_PROGRESS) as f:
                    prog = json.load(f)
                    print(f"\n📂 Incomplete full scan: {prog.get('count', 0)}/~11K")
            except:
                print(f"\n📂 Incomplete full scan (corrupted progress)")

        if update_prog:
            try:
                with open(UPDATE_PROGRESS) as f:
                    prog = json.load(f)
                    print(f"\n📂 Incomplete update: {prog.get('count', 0)}/~11K")
            except:
                print(f"\n📂 Incomplete update (corrupted progress)")

        print(f"\n{'=' * 80}")
        print("OPTIONS:")
        print(f"{'=' * 80}")
        print("  1. Full Market Scan (90d, all stocks)")
        print("  2. Resume Full Scan")
        print("  3. Update Cache (fetch missing days)")
        print("  4. Resume Update")
        print("  5. Preset Configuration")
        print("  6. Custom Configuration")
        print("  7. View Cache Info")
        print("  8. Delete All")
        print("  0. Exit")
        print(f"{'=' * 80}")

        choice = input("\nSelect: ").strip()

        if choice == '1':
            confirm = input("\n⚠ Full scan (may take several sessions). Continue? (y/n): ").strip().lower()
            if confirm == 'y':
                scanner.full_scan(max_workers=30, resume=False)

        elif choice == '2':
            if not full_prog:
                print("\n❌ No incomplete scan")
                continue
            scanner.full_scan(max_workers=30, resume=True)

        elif choice == '3':
            if not cache_info:
                print("\n❌ No cache. Run Full Scan first")
                continue
            confirm = input("\n⚠ Update cache. Continue? (y/n): ").strip().lower()
            if confirm == 'y':
                scanner.incremental_update(max_workers=30, resume=False)

        elif choice == '4':
            if not update_prog:
                print("\n❌ No incomplete update")
                continue
            scanner.incremental_update(max_workers=30, resume=True)

        elif choice == '5':
            if not cache_info:
                print("\n❌ No cache")
                continue

            scanner.load_cache()
            presets = get_preset_configs()

            print(f"\n{'=' * 80}")
            print("PRESETS:")
            for key, preset in presets.items():
                print(f"  {key}. {preset['name']}")

            preset_choice = input("\nSelect: ").strip()
            if preset_choice in presets:
                config = presets[preset_choice]

                print("\nSort:")
                print("  1. Gain")
                print("  2. Momentum")
                print("  3. Volatility")
                sort_choice = input("Select (default 1): ").strip() or '1'
                sort_map = {'1': 'period_gain_pct', '2': 'momentum_score', '3': 'volatility'}
                sort_by = sort_map.get(sort_choice, 'period_gain_pct')

                top_n = int(input("\nTop N (default 300): ").strip() or "300")

                results = scanner.apply_filters(config)
                display_results(results, config, top_n=top_n, sort_by=sort_by)

        elif choice == '6':
            if not cache_info:
                print("\n❌ No cache")
                continue

            scanner.load_cache()
            config = custom_config_menu()

            print("\nSort:")
            print("  1. Gain")
            print("  2. Momentum")
            print("  3. Volatility")
            sort_choice = input("Select (default 1): ").strip() or '1'
            sort_map = {'1': 'period_gain_pct', '2': 'momentum_score', '3': 'volatility'}
            sort_by = sort_map.get(sort_choice, 'period_gain_pct')

            top_n = int(input("\nTop N (default 300): ").strip() or "300")

            results = scanner.apply_filters(config)
            display_results(results, config, top_n=top_n, sort_by=sort_by)

        elif choice == '7':
            if cache_info:
                print(f"\n{'=' * 80}")
                print("CACHE INFO")
                print(f"{'=' * 80}")
                cache_date_str = cache_info.get('cache_date', None)
                stock_count = cache_info.get('stock_count', 'Unknown')
                if cache_date_str:
                    try:
                        cache_date = datetime.fromisoformat(cache_date_str)
                        age = datetime.now() - cache_date
                        print(f"Date: {cache_date.strftime('%Y-%m-%d %H:%M')}")
                        print(f"Stocks: {stock_count}")
                        print(f"Age: {age.days}d {age.seconds // 3600}h")
                    except (ValueError, KeyError):
                        print("Date: Invalid")
                        print(f"Stocks: {stock_count}")

                if os.path.exists(CACHE_FILE):
                    size = os.path.getsize(CACHE_FILE) / (1024 * 1024)
                    print(f"Size: {size:.1f} MB")
                print(f"{'=' * 80}")
            else:
                print("\n❌ No cache")

        elif choice == '8':
            confirm = input("\n⚠ Delete ALL? (y/n): ").strip().lower()
            if confirm == 'y':
                for file in [CACHE_FILE, CACHE_METADATA_FILE,
                             FULL_SCAN_PROGRESS, FULL_SCAN_PARTIAL,
                             UPDATE_PROGRESS, UPDATE_PARTIAL]:
                    if os.path.exists(file):
                        os.remove(file)
                scanner.cached_data = {}
                scanner.cache_date = None
                print("✓ Deleted")

        elif choice == '0':
            print("\n👋 Goodbye!")
            break


if __name__ == "__main__":
    main_menu()