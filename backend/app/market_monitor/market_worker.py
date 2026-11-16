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


def fetch(id, *, trend=False):
    from app.market_monitor.catalog import BY_ID
    from app.market_monitor.models import HISTORY_INTERVAL, HISTORY_MAX_ROWS, HISTORY_PERIOD
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
    history = ticker.history(period=HISTORY_PERIOD if trend else "5d", interval=HISTORY_INTERVAL if trend else "1d",
                             auto_adjust=True, back_adjust=False, actions=False, timeout=8, raise_errors=True,
                             **({"keepna": True} if trend else {}))
    # The public metadata accessor may request intraday history. Read only the
    # metadata already supplied with the daily request; refuse incompatible versions.
    metadata = getattr(getattr(ticker, "_price_history", None), "_history_metadata", None)
    if not isinstance(metadata, dict):
        raise ValueError("Daily provider metadata unavailable")
    if trend and len(history.index) > HISTORY_MAX_ROWS:
        raise ValueError("Oversized history")
    rows = []
    for day, value in zip(history.index, history["Close"]):
        if math.isfinite(float(value)):
            rows.append({"date": day.date().isoformat(), "close": float(value)})
        elif trend:
            raise ValueError("Invalid daily close")
    return {"symbol": metadata.get("symbol"), "currency": metadata.get("currency"),
            "instrument_type": metadata.get("instrumentType"), "timezone": str(history.index.tz) if history.index.tz else None,
            "rows": rows}


if __name__ == "__main__":
    try:
        if len(sys.argv) not in (2, 3) or (len(sys.argv) == 3 and sys.argv[2] != "history"):
            raise ValueError("Unsupported worker mode")
        result = fetch(sys.argv[1], trend=len(sys.argv) == 3)
        encoded = json.dumps(result, allow_nan=False)
        if len(sys.argv) == 3:
            from app.market_monitor.models import HISTORY_MAX_BYTES
            if len(encoded.encode("utf-8")) > HISTORY_MAX_BYTES:
                raise ValueError("Oversized history payload")
    except Exception:
        # Never serialize provider exceptions/URLs, credentials or local paths.
        encoded = '{"error": "Daily provider request failed"}'
    print(encoded)
