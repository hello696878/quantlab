"""Synthetic history tests; no provider calls or research database."""
import asyncio
from datetime import date, datetime, timedelta, timezone
import json
import subprocess
import sys
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app import market_monitor_routes as routes
from app.market_monitor.catalog import BY_ID
from app.market_monitor.models import HISTORY_MAX_BYTES, HistoryPoint, HistorySeries, SourceData
from app.market_monitor.parsers import parse_market, parse_market_history
from app.market_monitor.providers import Providers
from app.market_monitor.service import MonitorService

pytestmark = [pytest.mark.usefixtures("isolated_lab_db"), pytest.mark.db_free]
NOW = datetime(2026, 11, 12, tzinfo=timezone.utc)


def payload(rows):
    return json.dumps({"symbol": "^NDX", "currency": "USD", "instrument_type": "INDEX",
                       "timezone": "America/New_York", "rows": rows}).encode()


def parse_history(data, instrument_id):
    return parse_market_history(data, instrument_id, retrieved_at=NOW)


def row(day="2026-11-10", close=100):
    return {"date": day, "close": close}


def test_history_preserves_gaps_and_sorts_dates_with_exact_duplicate_collapse():
    data = parse_history(payload([row("2026-11-10", 102), row("2026-11-06"), row("2026-11-06")]), "nasdaq100")
    assert data.points == [HistoryPoint(date=date(2026, 11, 6), value=100), HistoryPoint(date=date(2026, 11, 10), value=102)]
    assert data.timezone == "America/New_York"
    assert not parse_history(payload([]), "nasdaq100").points
    assert len(parse_history(payload([row()]), "nasdaq100").points) == 1
    assert len(parse_history(payload([row()] * 100), "nasdaq100").points) == 1


@pytest.mark.parametrize("rows", [
    [row(), row(close=101)], [row("2026-02-30")], [row("2026-11-10T00:00:00Z")],
    [row(close=None)], [row(close=float("nan"))], [row(close=float("inf"))], [row(close=0)],
    [row(close=-1)], [row(close=True)], [{"date": "2026-11-10"}], [row()] * 101,
], ids=["conflict", "impossible-date", "timestamp", "null", "nan", "inf", "zero", "negative", "bool", "absent", "oversized"])
def test_history_rejects_invalid_rows(rows):
    with pytest.raises(ValueError):
        parse_history(payload(rows), "nasdaq100")


@pytest.mark.parametrize(("key", "wrong"), [("symbol", "NQ=F"), ("currency", "JPY"), ("instrument_type", "FUTURE")])
def test_history_requires_exact_provider_identity(key, wrong):
    data = json.loads(payload([row()]))
    data[key] = wrong
    with pytest.raises(ValueError, match="mismatch"):
        parse_history(json.dumps(data).encode(), "nasdaq100")


def test_history_byte_cap_and_snapshot_row_limit_are_distinct():
    with pytest.raises(ValueError, match="Oversized"):
        parse_history(b" " * HISTORY_MAX_BYTES + b"{}", "nasdaq100")
    with pytest.raises(ValueError):
        parse_market(json.loads(payload([row()] * 11)), "nasdaq100")
    assert len(parse_history(payload([row()] * 11), "nasdaq100").points) == 1


@pytest.mark.parametrize("day", ["2026-08-10", "2026-11-12"])
def test_history_rejects_out_of_window_dates_on_the_provider_calendar(day):
    # NOW is Nov 12 in UTC and Nov 11 in New York.
    with pytest.raises(ValueError, match="three-month window"):
        parse_history(payload([row(day)]), "nasdaq100")


def test_history_uses_calendar_months_and_allows_shorter_series():
    month_end = datetime(2026, 5, 31, 12, tzinfo=timezone.utc)
    data = payload([row("2026-02-28"), row("2026-05-31")])
    points = parse_market_history(data, "nasdaq100", retrieved_at=month_end).points
    assert [point.date for point in points] == [date(2026, 2, 28), date(2026, 5, 31)]
    short = parse_history(payload([row("2026-11-11")]), "nasdaq100")
    assert short.points == [HistoryPoint(date=date(2026, 11, 11), value=100)]


def test_history_provider_dispatches_only_fixed_worker_mode_with_hard_timeout(monkeypatch):
    import app.market_monitor.providers as module

    monkeypatch.setattr(module, "datetime", SimpleNamespace(now=lambda tz: NOW))
    def run(argv, **kwargs):
        assert argv == [sys.executable, "-m", "app.market_monitor.market_worker", "nasdaq100", "history"]
        assert kwargs["timeout"] == 25 and kwargs["capture_output"]
        return SimpleNamespace(returncode=0, stdout=payload([row()]))
    monkeypatch.setattr(subprocess, "run", run)
    assert asyncio.run(Providers().market_history("nasdaq100")).points[0].value == 100


def test_history_worker_fixed_policy_sqlite_refusal_and_row_cap():
    script = """import sqlite3, sys
from datetime import datetime
from types import SimpleNamespace
class Index(list): tz = 'America/New_York'
class Ticker:
    def __init__(self, symbol):
        assert symbol == '^NDX'
        self._price_history = SimpleNamespace(_history_metadata=dict(symbol=symbol, currency='USD', instrumentType='INDEX'))
    def history(self, **kwargs):
        assert kwargs == dict(period='3mo', interval='1d', auto_adjust=True, back_adjust=False,
                              actions=False, timeout=8, raise_errors=True, keepna=True)
        return self
    @property
    def index(self): return Index([datetime(2026, 11, 10)] * rows)
    def __getitem__(self, name):
        assert name == 'Close'
        return [100.0] * rows
fake = SimpleNamespace(Ticker=Ticker, cache=SimpleNamespace())
sys.modules['yfinance'] = fake
from app.market_monitor.market_worker import fetch
rows = 1
assert fetch('nasdaq100', trend=True)['rows'] == [{'date':'2026-11-10', 'close':100.0}]
assert all(getattr(fake.cache, 'get_' + key + '_cache')() is not None for key in ('tz', 'cookie', 'isin'))
try: sqlite3.connect(':memory:')
except RuntimeError: pass
else: raise AssertionError('SQLite allowed')
rows = 101
try: fetch('nasdaq100', trend=True)
except ValueError as exc: assert 'Oversized history' in str(exc)
else: raise AssertionError('Oversized history accepted')
"""
    proc = subprocess.run([sys.executable, "-c", script], timeout=20, capture_output=True)
    assert proc.returncode == 0, proc.stderr.decode(errors="replace")


def test_history_route_eligibility_and_serialized_contract(monkeypatch):
    calls = []

    async def market_history(id):
        calls.append(id)
        return parse_history(payload([row()]), id)

    service = MonitorService(SimpleNamespace(market_history=market_history), clock=lambda: NOW)
    monkeypatch.setattr(routes, "_service", service)
    app = FastAPI()
    app.include_router(routes.router)
    with TestClient(app) as client:
        url = "/market-monitor/history"
        for query in ("", "?instrument_id=NQ=F", "?instrument_id=unknown", "?instrument_id=eia_wti",
                      "?instrument_id=treasury2y", "?instrument_id=nasdaq100&interval=1m",
                      "?instrument_id=nasdaq100&instrument_id=nasdaq100", "?instrument_id=" + "s" * 33):
            assert client.get(url + query).status_code == 422
        assert not calls
        response = client.get(url + "?instrument_id=nasdaq100")
        assert response.status_code == 200
        result = response.json()
        assert result["instrument"] == BY_ID["nasdaq100"].model_dump()
        assert (result["period"], result["interval"], result["adjustment"]) == ("3mo", "1d", "provider_adjusted_close")
        assert result["status"] == "ready" and result["retrieved_at"] == result["checked_at"]
        assert result["points"] == [{"date": "2026-11-10", "value": 100}]
        assert result["timezone"] == "America/New_York"
        assert calls == ["nasdaq100"]
        assert len(response.content) < HISTORY_MAX_BYTES
    with pytest.raises(ValueError):
        asyncio.run(service.history("eia_brent"))


def test_history_deduplication_ttl_backoff_and_whole_series_replacement():
    async def scenario():
        now = NOW
        entered, release = asyncio.Event(), asyncio.Event()
        calls = []
        mode = "first"

        async def market_history(id):
            calls.append(id)
            if id == "gold_reference":
                return HistorySeries(points=[])
            if mode == "first":
                entered.set()
                await release.wait()
                return parse_history(payload([row("2026-11-09", 90), row()]), id)
            if mode == "fail":
                raise RuntimeError("private provider diagnostic")
            return parse_history(payload([row("2026-11-11", 120)]), id)

        service = MonitorService(SimpleNamespace(market_history=market_history), clock=lambda: now)
        consumer = asyncio.create_task(service.history("nasdaq100"))
        await entered.wait()
        other = asyncio.create_task(service.history("nasdaq100"))
        consumer.cancel()
        with pytest.raises(asyncio.CancelledError):
            await consumer
        release.set()
        first = await other
        assert len(first.points) == 2
        assert (await service.history("nasdaq100")) == first
        assert calls == ["nasdaq100"]
        # Snapshot and history have distinct payloads and cache identities.
        async def snapshot():
            return SourceData()
        snapshot_block = await service.source("market:nasdaq100", "^NDX", "market", "daily", "", 900, snapshot)
        assert snapshot_block.status == "ready" and not snapshot_block.observations
        assert (await service.history("nasdaq100")) == first
        empty = await service.history("gold_reference")
        assert empty.status == "unavailable" and not empty.points and empty.retrieved_at is None
        assert "No daily closes" in empty.message
        mode = "fail"
        now += timedelta(seconds=900)
        stale = await service.history("nasdaq100")
        assert stale.status == "stale" and stale.points == first.points and stale.retrieved_at == first.retrieved_at
        assert stale.checked_at > first.checked_at and "private" not in stale.message
        now += timedelta(seconds=59)
        assert (await service.history("nasdaq100")) == stale
        assert calls == ["nasdaq100", "gold_reference", "nasdaq100"]
        now += timedelta(seconds=1)
        mode = "recover"
        recovered = await service.history("nasdaq100")
        assert recovered.status == "ready" and recovered.retrieved_at == now
        assert recovered.points == [HistoryPoint(date=date(2026, 11, 11), value=120)]
        assert calls == ["nasdaq100", "gold_reference", "nasdaq100", "nasdaq100"]

    asyncio.run(scenario())


def test_history_uses_snapshot_provider_concurrency_limit():
    async def scenario():
        service = MonitorService(clock=lambda: NOW)
        entered, release, history_started = asyncio.Event(), asyncio.Event(), asyncio.Event()
        count = 0

        async def fetch():
            nonlocal count
            count += 1
            if count == 4:
                entered.set()
            await release.wait()
            return SourceData()

        async def history(id):
            history_started.set()
            return parse_history(payload([row()]), id)

        service.providers.market_history = history
        sources = [asyncio.create_task(service.source(f"market:{i}", "Test", "market", "daily", "", 900, fetch)) for i in range(4)]
        await entered.wait()
        selected = asyncio.create_task(service.history("nasdaq100"))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert not history_started.is_set()
        release.set()
        await asyncio.gather(*sources)
        assert (await selected).status == "ready"
        assert history_started.is_set()

    asyncio.run(scenario())
