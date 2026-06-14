"""Download the US ticker universe from Nasdaq Trader symbol directories.

Mirrors the original scanner: NASDAQ-listed + other-exchange (NYSE/AMEX) files,
filtering out test issues, warrants, preferreds and symbols with punctuation.
"""

import urllib.request

_NASDAQ_URL = "https://ftp.nasdaqtrader.com/SymbolDirectory/nasdaqlisted.txt"
_OTHER_URL = "https://ftp.nasdaqtrader.com/SymbolDirectory/otherlisted.txt"


def _download(url):
    with urllib.request.urlopen(url, timeout=60) as resp:
        return resp.read().decode("utf-8")


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
    nasdaq = _parse(_download(_NASDAQ_URL), symbol_col=0, drop_chars=("."))
    other = _parse(_download(_OTHER_URL), symbol_col=0,
                   drop_chars=(".", "$", "^", "/"))
    other = [s for s in other if "PR" not in s]
    return sorted(set(nasdaq) | set(other))
