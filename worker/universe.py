"""Download the US ticker universe from Nasdaq Trader symbol directories.

Mirrors the original scanner: NASDAQ-listed + other-exchange (NYSE/AMEX) files,
filtering out test issues, warrants, preferreds and symbols with punctuation.
"""

import time
import urllib.error
import urllib.request

_NASDAQ_URL = "https://ftp.nasdaqtrader.com/SymbolDirectory/nasdaqlisted.txt"
_OTHER_URL = "https://ftp.nasdaqtrader.com/SymbolDirectory/otherlisted.txt"

# nasdaqtrader.com occasionally TCP-blocks GitHub Actions' IP ranges outright
# (connection never establishes, retries don't help). Fall back to a plain-text
# mirror hosted on GitHub's own CDN, which Actions runners can always reach.
_FALLBACK_URL = "https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/all/all_tickers.txt"

_RETRIES = 4
_BACKOFF_SECONDS = 5


def _download(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    last_err = None
    for attempt in range(_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError) as e:
            last_err = e
            if attempt < _RETRIES - 1:
                time.sleep(_BACKOFF_SECONDS * (attempt + 1))
    raise last_err


def _download_fallback_tickers():
    text = _download(_FALLBACK_URL)
    return [s.strip() for s in text.strip().split("\n") if s.strip()]


def _parse(text, symbol_col=0, drop_chars=(".",)):
    lines = text.strip().split("\n")
    out = []
    # Skip header (first line) and trailing file-creation footer (last line).
    for line in lines[1:-1]:
        parts = line.split("|")
        if not parts:
            continue
        sym = parts[symbol_col].strip()
        if not sym or sym.startswith("$"):
            continue
        if any(ch in sym for ch in drop_chars):
            continue
        out.append(sym)
    return out


def get_all_us_tickers():
    """Return a sorted, de-duplicated list of US tickers."""
    try:
        nasdaq = _parse(_download(_NASDAQ_URL), symbol_col=0, drop_chars=("."))
        other = _parse(_download(_OTHER_URL), symbol_col=0,
                       drop_chars=(".", "$", "^", "/"))
        other = [s for s in other if "PR" not in s]
        return sorted(set(nasdaq) | set(other))
    except (urllib.error.URLError, TimeoutError):
        print("nasdaqtrader.com unreachable, falling back to GitHub mirror...")
        tickers = _download_fallback_tickers()
        return sorted(s for s in set(tickers)
                       if not any(ch in s for ch in (".", "$", "^", "/")))
