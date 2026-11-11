"""Synthetic provider fixtures, not production fallback values; no live network."""
import asyncio
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.market_monitor.catalog import BY_ID, CATALOG, FEEDS
from app.market_monitor.models import Observation, SourceData
from app.market_monitor.parsers import (MAX_BYTES, parse_eia, parse_feed, parse_fomc, parse_market, parse_sec, parse_treasury)
from app.market_monitor.providers import Providers
from app.market_monitor.service import MonitorService, configured_sec
from app import market_monitor_routes as routes

pytestmark = [pytest.mark.usefixtures("isolated_lab_db"), pytest.mark.db_free]
DAY = datetime(2026, 1, 5, 12, tzinfo=timezone.utc)


def treasury(rows):
    properties = "".join('<m:properties><d:NEW_DATE>' + day + 'T00:00:00</d:NEW_DATE>' +
                         "".join(f"<d:{key}>{value}</d:{key}>" for key, value in values.items()) + '</m:properties>' for day, values in rows)
    return ('<feed xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata" '
            'xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices">' + properties + '</feed>').encode()


def rss(items):
    return ("<rss><channel>" + "".join(f"<item><title>{title}</title><link>{link}</link><guid>{guid}</guid><pubDate>{stamp}</pubDate></item>" for title, link, guid, stamp in items) + "</channel></rss>").encode()


def test_treasury_dates_missing_values_and_same_date_spread():
    data = parse_treasury([treasury([
        ("2026-01-02", {"BC_2YEAR": "4", "BC_10YEAR": "4.5", "BC_30YEAR": "5"}),
        ("2025-12-31", {"BC_2YEAR": "3.9", "BC_10YEAR": "4.4", "BC_30YEAR": "4.9"}),
        ("2026-01-05", {"BC_2YEAR": "N/A", "BC_10YEAR": "4.6", "BC_30YEAR": ""}),
    ])])
    obs = {value.instrument_id: value for value in data.observations}
    assert obs["treasury2y"].observation_date == date(2026, 1, 2)
    assert obs["treasury2y"].change == pytest.approx(10)
    assert obs["treasury10y"].change == pytest.approx(10)
    assert obs["treasury10y2y"].value == pytest.approx(50)
    assert obs["treasury10y2y"].observation_date == date(2026, 1, 2)
    assert obs["treasury10y2y"].change == pytest.approx(0)
    assert obs["treasury30y"].value == 5


def test_treasury_requests_only_two_bounded_months_across_year_boundary():
    provider = Providers(); calls = []
    async def get(url, params):
        calls.append(params)
        return treasury([("2025-12-31", {"BC_2YEAR": "4", "BC_10YEAR": "5"})])
    provider.get = get
    asyncio.run(provider.treasury(date(2026, 1, 2)))
    assert [call["field_tdr_date_value_month"] for call in calls] == ["202512", "202601"]


def test_market_no_manufactured_zero_change_or_completed_session():
    row = {"symbol": "^NDX", "currency": "USD", "instrument_type": "INDEX", "timezone": "America/New_York",
           "rows": [{"date": "2026-01-05", "close": 100}]}
    observation = parse_market(row, "nasdaq100").observations[0]
    assert observation.change is None and observation.previous_date is None and observation.session_complete is None
    assert observation.observation_date == date(2026, 1, 5) and observation.timezone == "America/New_York"
    row["rows"].insert(0, {"date": "2026-01-02", "close": 80})
    assert parse_market(row, "nasdaq100").observations[0].change == 25
    row["symbol"] = "NQ=F"
    with pytest.raises(ValueError, match="identity"): parse_market(row, "nasdaq100")


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, None, "not-numeric"])
def test_invalid_market_numbers(value):
    with pytest.raises((ValueError, TypeError)):
        parse_market({"symbol": "NVDA", "currency": "USD", "instrument_type": "EQUITY", "rows": [{"date": "2026-01-05", "close": value}]}, "nvda")


def test_rss_actual_semantics_safe_text_dedup_and_unknown_times():
    data = rss([("&lt;b&gt;Statement&lt;/b&gt;", "https://www.federalreserve.gov/new.htm", "same", "Mon, 05 Jan 2026 14:00:00 -0500"),
                ("Duplicate", "https://www.federalreserve.gov/new.htm#part", "other", "bad"),
                ("Bad", "javascript:alert(1)", "bad", "bad"),
                ("No time", "https://www.federalreserve.gov/next.htm", "next", "bad")])
    parsed = parse_feed(data, "fed", FEEDS["fed"][3]).items
    assert [item.title for item in parsed] == ["Statement", "No time"]
    assert parsed[0].published_at.utcoffset() == timedelta(hours=-5)
    assert parsed[1].published_at is None


@pytest.mark.parametrize("data", [b"not xml", b'<rss/>', b'<!DOCTYPE rss [<!ENTITY x "bad">]><rss/>', b"x" * (MAX_BYTES + 1)], ids=["malformed", "no-channel", "entity", "too-large"])
def test_invalid_feed_payloads(data):
    with pytest.raises(ValueError): parse_feed(data, "fed", FEEDS["fed"][3])


def test_valid_empty_feed_replaces_last_good_without_claiming_refresh_failure():
    empty = b'<rss version="2.0"><channel><title>Official releases</title><link>https://www.federalreserve.gov/</link><description>Latest releases</description></channel></rss>'
    assert parse_feed(empty, "fed", FEEDS["fed"][3]).items == []
    bad_items = rss([("Unsafe", "javascript:alert(1)", "bad", "")])
    with pytest.raises(ValueError, match="No usable"):
        parse_feed(bad_items, "fed", FEEDS["fed"][3])

    async def scenario():
        clock = [DAY]
        service = MonitorService(FakeProviders(), lambda: clock[0])
        async def old():
            return parse_feed(rss([("Old release", "https://www.federalreserve.gov/old.htm", "old", "")]), "fed", FEEDS["fed"][3])
        args = ("fed", "Fed", "official", "event", FEEDS["fed"][2], 600)
        first = await service.source(*args, old)
        assert [item.title for item in first.items] == ["Old release"]
        clock[0] += timedelta(seconds=601)
        async def no_releases():
            return parse_feed(empty, "fed", FEEDS["fed"][3])
        refreshed = await service.source(*args, no_releases)
        assert refreshed.status == "ready" and refreshed.items == []
        assert refreshed.retrieved_at == refreshed.checked_at == clock[0]
        assert refreshed.retrieved_at > first.retrieved_at and refreshed.message is None
    asyncio.run(scenario())


def test_rss_retains_bounded_items():
    assert len(parse_feed(rss([(str(i), f"https://www.bbc.com/news/{i}", str(i), "") for i in range(50)]), "bbc", FEEDS["bbc"][3]).items) == 30


def sec_fixture():
    return {"cik": "320193", "tickers": ["AAPL"], "name": "Apple Inc.", "filings": {"recent": {
        "accessionNumber": ["0000320193-26-000001"], "form": ["10-Q/A"], "filingDate": ["2026-01-05"],
        "primaryDocument": ["aapl-report.htm"], "acceptanceDateTime": ["2026-01-05T15:00:00Z"]}}}


def test_sec_aligned_arrays_identity_dates_and_official_links():
    data = sec_fixture()
    filing = parse_sec(data, "aapl").filings[0]
    assert filing.form == "10-Q/A" and filing.filing_date == date(2026, 1, 5)
    assert filing.accepted_at.tzinfo is not None
    assert filing.url == "https://www.sec.gov/Archives/edgar/data/320193/000032019326000001/aapl-report.htm"
    with pytest.raises(ValueError, match="issuer"): parse_sec(data, "msft")
    data["filings"]["recent"]["form"].append("8-K")
    with pytest.raises(ValueError, match="aligned"): parse_sec(data, "aapl")


def test_sec_refuses_path_traversal_and_invented_acceptance_timezone():
    for key, value in (("primaryDocument", "../secret"), ("acceptanceDateTime", "2026-01-05T00:00:00")):
        data = sec_fixture(); data["filings"]["recent"][key] = [value]
        with pytest.raises(ValueError): parse_sec(data, "aapl")


def test_sec_unrequested_form_document_cannot_hide_supported_filings():
    data = sec_fixture()
    recent = data["filings"]["recent"]
    for key, value in {"accessionNumber": "0000320193-26-000002", "form": "4",
                       "filingDate": "2026-01-06", "primaryDocument": "xslF345X05/ownership.xml",
                       "acceptanceDateTime": "2026-01-06T15:00:00Z"}.items():
        recent[key].insert(0, value)
    filings = parse_sec(data, "aapl").filings
    assert len(filings) == 1 and filings[0].form == "10-Q/A"
    assert filings[0].url == "https://www.sec.gov/Archives/edgar/data/320193/000032019326000001/aapl-report.htm"
    # Shape and issuer checks still apply to the complete provider response.
    with pytest.raises(ValueError, match="issuer"):
        parse_sec(data, "msft")
    recent["form"].append("4")
    with pytest.raises(ValueError, match="aligned"):
        parse_sec(data, "aapl")


def test_eia_validates_series_units_dates_and_finite_numeric_strings():
    data = {"response": {"data": [{"series": "RWTC", "period": "2026-01-05", "value": "65.12", "units": "$/BBL"}]}}
    assert parse_eia(data).observations[0].value == 65.12
    assert parse_eia(data).observations[0].change is None
    for key, value in (("series", "FUTURES"), ("units", "cents/gallon"), ("period", "yesterday"), ("value", "NaN")):
        bad = json.loads(json.dumps(data)); bad["response"]["data"][0][key] = value
        with pytest.raises(ValueError): parse_eia(bad)


@pytest.mark.parametrize("prior, latest, expected_change", [
    (-10, 10, None), (0, 10, None), (10, 11, 10), (10, -5, -150),
])
def test_eia_preserves_signed_prices_without_percentage_from_nonpositive_prior(prior, latest, expected_change):
    data = {"response": {"data": [
        {"series": "RWTC", "period": "2026-01-05", "value": str(latest), "units": "$/BBL"},
        {"series": "RWTC", "period": "2026-01-02", "value": str(prior), "units": "$/BBL"},
    ]}}
    observation = parse_eia(data).observations[0]
    assert observation.value == latest and observation.previous_date == date(2026, 1, 2)
    if expected_change is None:
        assert observation.change is None
    else:
        assert observation.change == pytest.approx(expected_change)


def test_fomc_preserves_ranges_and_does_not_invent_times():
    data = b'<h4>2026 FOMC Meetings</h4><div class="fomc-meeting__month"><strong>April/May</strong></div><div class="fomc-meeting__date">30-1*</div>'
    event = parse_fomc(data, date(2026, 1, 1)).events[0]
    assert (event.start_date, event.end_date) == (date(2026, 4, 30), date(2026, 5, 1))
    assert "start_time" not in event.model_dump()
    with pytest.raises(ValueError): parse_fomc(b"calendar unavailable", date(2026, 1, 1))


class FakeProviders:
    eia_key = sec_user_agent = None
    def __init__(self): self.calls = []
    async def market(self, id): self.calls.append(id); return SourceData(observations=[Observation(instrument_id=id, value=100, observation_date=DAY.date(), unit=BY_ID[id].unit)])
    async def treasury(self, today): self.calls.append("treasury"); return SourceData()
    async def feed(self, id): self.calls.append(id); return SourceData()
    async def calendar(self, today): self.calls.append("calendar"); return SourceData()
    async def eia(self): raise AssertionError("Unconfigured EIA request")
    async def sec(self, company): raise AssertionError("Unconfigured SEC request")


def test_missing_configuration_makes_zero_configured_provider_requests():
    provider = FakeProviders(); service = MonitorService(provider, lambda: DAY)
    result = asyncio.run(service.snapshot(["eia_wti"], "nvda"))
    states = {source.id: source.status for source in result.sources}
    assert states["eia"] == states["sec:nvda"] == "not_configured"
    assert "eia" not in provider.calls and not any(call.startswith("sec") for call in provider.calls)
    assert configured_sec("QuantLab contact@example.com") is None
    assert configured_sec("missing") is None


def test_cache_shared_inflight_failure_isolation_and_last_good_retention():
    async def scenario():
        provider = FakeProviders(); clock = [DAY]; service = MonitorService(provider, lambda: clock[0])
        entered, release = asyncio.Event(), asyncio.Event()
        async def market(id):
            provider.calls.append(id); entered.set(); await release.wait()
            return SourceData(observations=[Observation(instrument_id=id, value=123, observation_date=DAY.date(), unit="USD/share")])
        provider.market = market
        a = asyncio.create_task(service.snapshot(["nvda"])); await entered.wait()
        b = asyncio.create_task(service.snapshot(["nvda"])); await asyncio.sleep(0)
        release.set(); first, second = await asyncio.gather(a, b)
        assert provider.calls.count("nvda") == 1
        await service.snapshot(["nvda"]); assert provider.calls.count("nvda") == 1
        original = first.sources[0]
        clock[0] += timedelta(minutes=16)
        async def fail(id): raise RuntimeError("private api_key=DO_NOT_LEAK")
        provider.market = fail
        stale = await service.snapshot(["nvda"])
        assert stale.sources[0].status == "stale" and stale.sources[0].observations[0].value == 123
        assert stale.sources[0].retrieved_at == original.retrieved_at and stale.sources[0].checked_at > original.checked_at
        assert "DO_NOT_LEAK" not in stale.model_dump_json()
        assert all(source.status == "ready" for source in stale.sources[1:])
    asyncio.run(scenario())


def test_source_failure_backoff_and_event_age_is_not_source_staleness():
    async def scenario():
        provider = FakeProviders(); clock = [DAY]; service = MonitorService(provider, lambda: clock[0]); calls = []
        async def fail(): calls.append(1); raise ValueError("bad")
        args = ("fed", "Fed", "official", "event", FEEDS["fed"][2], 600, fail)
        assert (await service.source(*args)).status == "unavailable"
        await service.source(*args); assert len(calls) == 1
        clock[0] += timedelta(seconds=61); await service.source(*args); assert len(calls) == 2
        async def old(): return parse_feed(rss([("Old", "https://www.bbc.com/old", "old", "Mon, 01 Jan 2001 00:00:00 GMT")]), "bbc", FEEDS["bbc"][3])
        block = await service.source("bbc", "BBC", "news", "event", FEEDS["bbc"][2], 600, old)
        assert block.status == "ready" and block.items[0].published_at.year == 2001
    asyncio.run(scenario())


def test_minimal_router_contract_and_request_bounds(monkeypatch):
    provider = FakeProviders(); monkeypatch.setattr(routes, "_service", MonitorService(provider, lambda: DAY))
    app = FastAPI(); app.include_router(routes.router)
    with TestClient(app) as client:
        catalog = client.get("/market-monitor/catalog").json()
        assert len(catalog["instruments"]) == 16 and BY_ID["nasdaq100"].symbol == "^NDX"
        assert BY_ID["wti_reference"].symbol == "CL=F" and BY_ID["eia_wti"].symbol == "RWTC"
        assert client.get("/market-monitor/snapshot?ids=&company=nvda").status_code == 200
        for query in ("ids=bogus", "ids=nvda,nvda", "ids=" + ",".join(["nvda"] * 17), "ids=" + "x" * 301, "company=evil"):
            assert client.get("/market-monitor/snapshot?" + query).status_code == 422


def test_demo_policy_refuses_monitor_before_startup():
    from app.read_only_demo import DemoApplication, ROUTES
    assert not any("market-monitor" in route for route in ROUTES)
    app = DemoApplication(FastAPI(), SimpleNamespace(), None)
    with TestClient(app) as client:
        assert client.get("/market-monitor/catalog").status_code == 403
        assert client.get("/market-monitor/snapshot").status_code == 403


def test_import_has_no_network_or_sqlite_activity():
    script = '''import sys
def guard(event, args):
    if event in ("socket.connect", "sqlite3.connect"): raise RuntimeError("unexpected IO")
sys.addaudithook(guard)
import app.market_monitor_routes
assert app.market_monitor_routes._service is None
'''
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr.decode(errors="replace")


def test_worker_daily_flags_memory_caches_and_sqlite_refusal():
    script = '''import sys, json, sqlite3
from datetime import datetime
from types import SimpleNamespace
class Index(list): tz = "America/New_York"
class History:
    index = Index([datetime(2026, 1, 5)])
    def __getitem__(self, key): assert key == "Close"; return [100.0]
class Ticker:
    def __init__(self, symbol):
        assert symbol == "NVDA"
        self._price_history = SimpleNamespace(_history_metadata={"symbol":"NVDA", "currency":"USD", "instrumentType":"EQUITY"})
    def history(self, **kwargs):
        assert kwargs["period"] == "5d" and kwargs["interval"] == "1d"
        assert kwargs["auto_adjust"] is True and kwargs["back_adjust"] is False
        assert kwargs["actions"] is False and kwargs["timeout"] == 8
        return History()
fake = SimpleNamespace(cache=SimpleNamespace(), Ticker=Ticker)
sys.modules["yfinance"] = fake
from app.market_monitor.market_worker import fetch
result = fetch("nvda")
cache = fake.cache.get_tz_cache(); cache.store("NVDA", "America/New_York")
assert cache.lookup("NVDA") == "America/New_York"
try: sqlite3.connect(":memory:")
except RuntimeError: pass
else: raise AssertionError("SQLite was not refused")
print(json.dumps(result))
'''
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert json.loads(result.stdout)["rows"] == [{"date": "2026-01-05", "close": 100.0}]


def test_http_payload_size_and_redirects_are_bounded(monkeypatch):
    import httpx
    import app.market_monitor.providers as module
    real_client = httpx.AsyncClient
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(200, content=b"x" * (MAX_BYTES + 1))
    def client(**kwargs):
        assert kwargs["follow_redirects"] is False
        return real_client(**kwargs, transport=httpx.MockTransport(handler))
    monkeypatch.setattr(module.httpx, "AsyncClient", client)
    with pytest.raises(ValueError, match="limit"):
        asyncio.run(Providers().get(FEEDS["fed"][2]))
    assert len(seen) == 1


def test_http_trickling_response_has_total_deadline_and_closes_stream(monkeypatch):
    import httpx
    import app.market_monitor.providers as module
    real_client = httpx.AsyncClient
    closed = []
    class TrickleStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            while True:
                yield b"x"
                await asyncio.sleep(0.005)
        async def aclose(self):
            closed.append(True)
    def client(**kwargs):
        return real_client(**kwargs, transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=TrickleStream())))
    monkeypatch.setattr(module.httpx, "AsyncClient", client)
    monkeypatch.setattr(module, "HTTP_TOTAL_SECONDS", 0.02, raising=False)
    async def scenario():
        started = asyncio.get_running_loop().time()
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(Providers().get(FEEDS["fed"][2]), timeout=0.5)
        assert asyncio.get_running_loop().time() - started < 0.3, "Only the outer consumer guard stopped the request"
        assert closed, "Timed-out transport was left open"
    asyncio.run(scenario())


def test_eia_total_deadline_stops_real_blocking_worker_without_exposing_key(monkeypatch, tmp_path):
    import app.market_monitor.providers as module
    real_run = subprocess.run
    started = tmp_path / "eia-worker-started"
    finished = tmp_path / "eia-worker-finished"
    sentinel = "TEST_ONLY_KEY_NEVER_IN_ARGV"
    calls = []
    child = ("from pathlib import Path; import time; "
             f"Path({str(started)!r}).write_text('started'); "
             "time.sleep(0.6); "
             f"Path({str(finished)!r}).write_text('worker still running')")
    def bounded_worker(argv, **kwargs):
        calls.append((argv, kwargs))
        assert all(sentinel not in str(value) for value in argv)
        request = kwargs["input"].decode() if isinstance(kwargs["input"], bytes) else kwargs["input"]
        assert sentinel in request
        return real_run([sys.executable, "-c", child], **kwargs)
    def refuse_inline_transport(*args, **kwargs):
        raise AssertionError("EIA retrieval bypassed the bounded worker")
    monkeypatch.setattr(module.subprocess, "run", bounded_worker)
    monkeypatch.setattr(module, "build_opener", refuse_inline_transport, raising=False)
    monkeypatch.setattr(module, "EIA_TOTAL_SECONDS", 0.2, raising=False)
    async def scenario():
        with pytest.raises(subprocess.TimeoutExpired):
            await asyncio.wait_for(Providers(sentinel).eia(), timeout=2)
        assert calls and started.exists(), "No real blocking child was exercised"
        await asyncio.sleep(0.7)
        assert not finished.exists(), "Deadline returned while underlying provider work continued"
    asyncio.run(scenario())


@pytest.mark.parametrize("case", ["success", "oversize", "status", "error"])
def test_eia_worker_stdin_bounded_transport_redaction_and_sqlite_refusal(case):
    script = '''import io, json, sqlite3, sys
from urllib import request
from urllib.parse import parse_qs, urlsplit
CASE = __CASE__
KEY = "TEST_ONLY_KEY_NEVER_PRINTED"
payload = {"response":{"data":[{"series":"RWTC", "period":"2026-01-05", "value":"65.12", "units":"$/BBL"}]}}
class Response:
    status = 503 if CASE == "status" else 200
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self, size):
        assert size == 2 * 1024 * 1024 + 1
        return b"x" * size if CASE == "oversize" else json.dumps(payload).encode()
class Opener:
    def open(self, req, timeout):
        url = urlsplit(req.full_url)
        assert url.scheme == "https" and url.netloc == "api.eia.gov"
        assert url.path == "/v2/petroleum/pri/spt/data/" and timeout == 12
        params = parse_qs(url.query)
        assert params["api_key"] == [KEY]
        assert params["facets[series][]"] == ["RWTC", "RBRTE"]
        assert params["data[0]"] == ["value"] and params["length"] == ["40"]
        if CASE == "error": raise RuntimeError("private provider URL api_key=" + KEY)
        return Response()
def opener(handler):
    assert handler.redirect_request(None, None, None, None, None, None) is None
    return Opener()
request.build_opener = opener
from app.market_monitor.eia_worker import main
sys.stdin = io.TextIOWrapper(io.BytesIO(json.dumps({"api_key": KEY}).encode()))
code = main()
try: sqlite3.connect(":memory:")
except RuntimeError: pass
else: raise AssertionError("SQLite was not refused")
raise SystemExit(code)
'''.replace("__CASE__", repr(case))
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, timeout=5)
    assert b"TEST_ONLY_KEY_NEVER_PRINTED" not in result.stdout + result.stderr
    if case == "success":
        assert result.returncode == 0, result.stderr.decode(errors="replace")
        assert parse_eia(json.loads(result.stdout)).observations[0].value == 65.12
    else:
        assert result.returncode == 1 and result.stderr == b""
        assert json.loads(result.stdout) == {"error": "EIA provider request failed"}


def test_cancelled_consumer_does_not_duplicate_requests():
    async def scenario():
        service = MonitorService(FakeProviders(), lambda: DAY)
        entered, release = asyncio.Event(), asyncio.Event(); calls = []
        async def fetch(): calls.append(1); entered.set(); await release.wait(); return SourceData()
        args = ("test", "Test", "official", "event", FEEDS["fed"][2], 600, fetch)
        consumer = asyncio.create_task(service.source(*args)); await entered.wait(); consumer.cancel()
        with pytest.raises(asyncio.CancelledError): await consumer
        second = asyncio.create_task(service.source(*args)); release.set(); await second
        assert len(calls) == 1 and not service.inflight
    asyncio.run(scenario())
