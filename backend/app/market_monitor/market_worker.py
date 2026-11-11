"""Disposable yfinance process: memory-only caches and a hard SQLite refusal.

The dependency's cache hooks are confined to this process, never the research
backend. If an installed yfinance version changes them, fail closed, not to disk.
"""
import json
import logging
import math
import sys
from datetime import timedelta


class MemoryCache:
    def __init__(self, cookie=False):
        self.values, self.cookie = {}, cookie

    def lookup(self, key):
        value = self.values.get(key)
        return {"cookie": value, "age": timedelta(0)} if self.cookie and value is not None else value

    def store(self, key, value):
        self.values[key] = value


def fetch(id):
    from app.market_monitor.catalog import BY_ID
    instrument = BY_ID[id]
    if instrument.source != "yahoo":
        raise ValueError("Unsupported daily market ID")

    def guard(event, args):
        if event == "sqlite3.connect":
            raise RuntimeError("Monitor worker refuses SQLite")

    sys.addaudithook(guard)
    import yfinance as yf
    tz, cookie, isin = MemoryCache(), MemoryCache(True), MemoryCache()
    yf.cache.get_tz_cache = lambda: tz
    yf.cache.get_cookie_cache = lambda: cookie
    yf.cache.get_isin_cache = lambda: isin
    logging.getLogger("yfinance").disabled = True
    ticker = yf.Ticker(instrument.symbol)
    history = ticker.history(period="5d", interval="1d", auto_adjust=True, back_adjust=False, actions=False, timeout=8, raise_errors=True)
    # The public metadata accessor may request intraday history. Read only the
    # metadata already supplied with the daily request; refuse incompatible versions.
    metadata = getattr(getattr(ticker, "_price_history", None), "_history_metadata", None)
    if not isinstance(metadata, dict):
        raise ValueError("Daily provider metadata unavailable")
    rows = []
    for day, value in zip(history.index, history["Close"]):
        if math.isfinite(float(value)):
            rows.append({"date": day.date().isoformat(), "close": float(value)})
    return {"symbol": metadata.get("symbol"), "currency": metadata.get("currency"),
            "instrument_type": metadata.get("instrumentType"), "timezone": str(history.index.tz) if history.index.tz else None,
            "rows": rows}


if __name__ == "__main__":
    try:
        result = fetch(sys.argv[1])
    except Exception:
        # Never serialize provider exceptions/URLs, credentials or local paths.
        result = {"error": "Daily provider request failed"}
    print(json.dumps(result, allow_nan=False))
