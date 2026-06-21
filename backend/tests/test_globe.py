"""
Tests for the Global Markets Globe data layer (Phase 20.2).

Confirms the static sample API shape, validation, JSON-safety (no NaN/Inf), and
that the future adapter stubs perform no live fetch. No network calls.
"""

import math

import pytest

from app.globe import adapters as globe_adapters
from app.globe.service import get_all_markets, get_market, get_regions

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")

REQUIRED_TOP_FIELDS = [
    "id", "country", "region", "subregion", "flag", "lat", "lon", "currency",
    "exchange", "trading_hours", "timezone", "static_data_notice", "indices",
    "macro", "fx", "rates", "market_structure", "headlines", "links",
    "source_status",
]
VALID_REGIONS = {"Americas", "Europe", "Asia-Pacific"}


def _assert_all_finite(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            _assert_all_finite(v)
    elif isinstance(obj, list):
        for v in obj:
            _assert_all_finite(v)
    elif isinstance(obj, float):
        assert math.isfinite(obj), f"non-finite float in payload: {obj}"


@pytest.fixture
def client():
    return TestClient(main_module.app)


# ---------------------------------------------------------------------------
# Endpoint: GET /globe/markets
# ---------------------------------------------------------------------------

def test_markets_endpoint_returns_200(client):
    assert client.get("/globe/markets").status_code == 200


def test_markets_list_has_at_least_15(client):
    body = client.get("/globe/markets").json()
    assert body["count"] >= 15
    assert len(body["markets"]) == body["count"]
    assert body["data_status"] == "static_sample"
    assert "planned" in body["notice"].lower()


def test_every_market_has_required_fields(client):
    for m in client.get("/globe/markets").json()["markets"]:
        for field in REQUIRED_TOP_FIELDS:
            assert field in m, f"market {m.get('id')} missing {field}"


def test_market_ids_unique(client):
    ids = [m["id"] for m in client.get("/globe/markets").json()["markets"]]
    assert len(ids) == len(set(ids))


def test_country_names_unique(client):
    names = [m["country"] for m in client.get("/globe/markets").json()["markets"]]
    assert len(names) == len(set(names))


def test_lat_lon_valid(client):
    for m in client.get("/globe/markets").json()["markets"]:
        assert -90.0 <= m["lat"] <= 90.0
        assert -180.0 <= m["lon"] <= 180.0


def test_region_currency_exchange_valid(client):
    for m in client.get("/globe/markets").json()["markets"]:
        assert m["region"] in VALID_REGIONS
        assert isinstance(m["currency"], str) and m["currency"].strip()
        assert isinstance(m["exchange"], str) and m["exchange"].strip()


def test_static_data_notice_present(client):
    for m in client.get("/globe/markets").json()["markets"]:
        assert m["static_data_notice"].strip()
        assert "planned" in m["static_data_notice"].lower()


def test_source_status_all_static_sample(client):
    for m in client.get("/globe/markets").json()["markets"]:
        ss = m["source_status"]
        assert ss["macro"] == "static_sample"
        assert ss["indices"] == "static_sample"
        assert ss["fx"] == "static_sample"
        assert ss["news"] == "static_sample"


def test_every_market_has_at_least_one_index(client):
    for m in client.get("/globe/markets").json()["markets"]:
        assert len(m["indices"]) >= 1
        for idx in m["indices"]:
            assert idx["is_sample"] is True


def test_every_market_has_macro_section(client):
    for m in client.get("/globe/markets").json()["markets"]:
        macro = m["macro"]
        for key in ["gdp_growth", "inflation", "unemployment", "policy_rate", "debt_to_gdp"]:
            assert key in macro
        assert macro["is_sample"] is True


def test_every_market_has_structure_section(client):
    for m in client.get("/globe/markets").json()["markets"]:
        ms = m["market_structure"]
        for key in ["market_cap", "listed_companies", "settlement", "notes"]:
            assert ms[key]
        assert m["rates"]["is_sample"] is True


# ---------------------------------------------------------------------------
# Endpoint: GET /globe/markets/{id}
# ---------------------------------------------------------------------------

def test_get_single_market_us(client):
    r = client.get("/globe/markets/us")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "us"
    assert body["country"] == "United States"


def test_get_single_market_case_insensitive(client):
    assert client.get("/globe/markets/US").json()["id"] == "us"


def test_unknown_market_returns_friendly_404(client):
    r = client.get("/globe/markets/atlantis")
    assert r.status_code == 404
    assert r.json()["detail"] == "Market not found."


# ---------------------------------------------------------------------------
# Endpoint: GET /globe/regions
# ---------------------------------------------------------------------------

def test_regions_endpoint(client):
    body = client.get("/globe/regions").json()
    assert body["data_status"] == "static_sample"
    total = sum(r["count"] for r in body["regions"])
    assert total == len(client.get("/globe/markets").json()["markets"])
    for r in body["regions"]:
        assert r["region"] in VALID_REGIONS


# ---------------------------------------------------------------------------
# JSON safety
# ---------------------------------------------------------------------------

def test_markets_no_nan_or_inf(client):
    _assert_all_finite(client.get("/globe/markets").json())


def test_single_market_no_nan_or_inf(client):
    for mid in ["us", "jp", "tw", "de", "in", "br"]:
        _assert_all_finite(client.get(f"/globe/markets/{mid}").json())


# ---------------------------------------------------------------------------
# Service layer
# ---------------------------------------------------------------------------

def test_service_get_all_and_one():
    markets = get_all_markets()
    assert len(markets) >= 15
    assert get_market("jp").country == "Japan"
    assert get_market("nope") is None


def test_service_regions_rollup():
    regions = get_regions()
    assert sum(r.count for r in regions) == len(get_all_markets())


# ---------------------------------------------------------------------------
# Adapter stubs: no live fetch
# ---------------------------------------------------------------------------

def test_adapters_report_planned_and_not_live():
    for cls in globe_adapters.PLANNED_ADAPTERS:
        a = cls()
        assert a.source_state() == "planned"
        assert a.is_live() is False


def test_fred_adapter_does_not_fetch():
    with pytest.raises(NotImplementedError):
        globe_adapters.FredMacroAdapter().fetch_country_macro("us")


def test_index_adapter_does_not_fetch():
    with pytest.raises(NotImplementedError):
        globe_adapters.DelayedIndexQuoteAdapter().fetch_index_quotes("us")


def test_fx_adapter_does_not_fetch():
    with pytest.raises(NotImplementedError):
        globe_adapters.FxQuoteAdapter().fetch_fx_quotes("USD", "JPY")


def test_news_adapter_does_not_fetch():
    with pytest.raises(NotImplementedError):
        globe_adapters.NewsSentimentAdapter().fetch_headlines("us")
