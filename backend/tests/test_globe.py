"""
Tests for the Global Markets Globe data layer (Phase 20.2).

Confirms the static sample API shape, validation, JSON-safety (no NaN/Inf), and
that the future adapter stubs perform no live fetch. No network calls.
"""

import math

import pytest
from pydantic import ValidationError

from app.globe import adapters as globe_adapters
from app.globe.adapters import (
    FredMacroAdapter,
    FredMacroConfig,
    clear_fred_cache,
)
from app.globe.models import MarketIndex
from app.globe.service import (
    build_markets_response,
    get_all_markets,
    get_market,
    get_regions,
)

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")

REQUIRED_TOP_FIELDS = [
    "id", "country", "region", "subregion", "flag", "lat", "lon", "currency",
    "exchange", "trading_hours", "timezone", "static_data_notice", "indices",
    "macro", "fx", "rates", "market_structure", "headlines", "links",
    "source_status",
]
VALID_REGIONS = {"Americas", "Europe", "Asia-Pacific"}
REQUIRED_COUNTRIES = {
    "United States", "Canada", "United Kingdom", "Germany", "France",
    "Japan", "China", "Hong Kong", "Taiwan", "South Korea", "India",
    "Singapore", "Australia", "Brazil", "Switzerland",
}


def _assert_all_finite(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            _assert_all_finite(v)
    elif isinstance(obj, list):
        for v in obj:
            _assert_all_finite(v)
    elif isinstance(obj, float):
        assert math.isfinite(obj), f"non-finite float in payload: {obj}"


@pytest.fixture(autouse=True)
def _fred_defaults(monkeypatch):
    """Keep every test deterministic: FRED disabled + clean cache by default."""
    for key in (
        "GLOBE_FRED_ENABLED",
        "FRED_API_KEY",
        "FRED_BASE_URL",
        "FRED_TIMEOUT_SECONDS",
        "GLOBE_FRED_CACHE_TTL_SECONDS",
    ):
        monkeypatch.delenv(key, raising=False)
    clear_fred_cache()
    yield
    clear_fred_cache()


@pytest.fixture
def client():
    return TestClient(main_module.app)


def _fake_fetcher(value="5.33", date="2024-05-01"):
    """A FRED fetcher stub that returns one observation. No network."""

    def fetch(url, timeout):  # noqa: ARG001
        return {"observations": [{"date": date, "value": value}]}

    return fetch


def _enabled_config(key="TEST_KEY", ttl=0):
    return FredMacroConfig(
        enabled=True,
        api_key=key,
        base_url="https://fred.test",
        timeout_seconds=1.0,
        cache_ttl_seconds=ttl,
    )


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


def test_required_countries_present(client):
    names = {m["country"] for m in client.get("/globe/markets").json()["markets"]}
    assert REQUIRED_COUNTRIES <= names


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


def test_every_nested_data_section_is_marked_sample(client):
    for m in client.get("/globe/markets").json()["markets"]:
        assert m["macro"]["is_sample"] is True
        assert m["rates"]["is_sample"] is True
        assert m["market_structure"]["is_sample"] is True
        assert all(item["is_sample"] is True for item in m["indices"])
        assert all(item["is_sample"] is True for item in m["fx"])
        assert all(item["is_sample"] is True for item in m["headlines"])


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


def test_schema_rejects_nonfinite_numbers():
    with pytest.raises(ValidationError):
        MarketIndex(
            name="Sample Index",
            ticker="SAMPLE",
            level=float("nan"),
            change_pct=0.0,
            sparkline=[1.0, 2.0],
        )


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


def test_index_adapter_does_not_fetch():
    with pytest.raises(NotImplementedError):
        globe_adapters.DelayedIndexQuoteAdapter().fetch_index_quotes("us")


def test_fx_adapter_does_not_fetch():
    with pytest.raises(NotImplementedError):
        globe_adapters.FxQuoteAdapter().fetch_fx_quotes("USD", "JPY")


def test_news_adapter_does_not_fetch():
    with pytest.raises(NotImplementedError):
        globe_adapters.NewsSentimentAdapter().fetch_headlines("us")


# ---------------------------------------------------------------------------
# FRED macro adapter (Phase 20.3) — optional, config-gated, fail-closed
# ---------------------------------------------------------------------------

def test_fred_disabled_by_default():
    cfg = FredMacroConfig.from_env({})
    assert cfg.enabled is False
    adapter = FredMacroAdapter(cfg)
    assert adapter.is_live() is False
    assert adapter.source_state() == "static_sample"


def test_disabled_endpoint_is_static(client):
    body = client.get("/globe/markets").json()
    assert body["data_status"] == "static_sample"
    assert all(m["source_status"]["macro"] == "static_sample" for m in body["markets"])
    assert body["warnings"] == []


def test_disabled_adapter_is_not_called():
    def boom(url, timeout):  # noqa: ARG001
        raise AssertionError("fetcher must not be called when FRED is disabled")

    cfg = FredMacroConfig()  # disabled
    adapter = FredMacroAdapter(cfg, fetcher=boom)
    markets, status, _notice, warnings = build_markets_response(cfg, adapter=adapter)
    us = next(m for m in markets if m.id == "us")
    assert status == "static_sample"
    assert us.source_status.macro == "static_sample"
    assert us.macro.is_sample is True
    assert warnings == []


def test_enabled_without_key_falls_back(client, monkeypatch):
    monkeypatch.setenv("GLOBE_FRED_ENABLED", "true")  # no FRED_API_KEY
    body = client.get("/globe/markets").json()
    assert body["data_status"] == "static_sample"  # nothing went live
    assert any("api key" in w.lower() for w in body["warnings"])
    us = next(m for m in body["markets"] if m["id"] == "us")
    assert us["source_status"]["macro"] == "fred_unavailable"
    assert us["macro"]["is_sample"] is True  # data unchanged
    unsupported = [m for m in body["markets"] if m["id"] != "us"]
    assert unsupported
    assert all(m["source_status"]["macro"] == "static_sample" for m in unsupported)


def test_mock_fred_success_enriches_us():
    cfg = _enabled_config()
    adapter = FredMacroAdapter(cfg, fetcher=_fake_fetcher("3.21", "2024-06-01"))
    markets, status, _notice, warnings = build_markets_response(cfg, adapter=adapter)
    us = next(m for m in markets if m.id == "us")
    assert us.source_status.macro == "fred_live"
    assert us.macro.is_sample is True  # inflation and debt/GDP remain static
    assert us.macro.policy_rate == 3.21
    assert us.macro.as_of_date == "2024-06-01"
    assert us.macro.fred_fields == ["policy_rate", "unemployment", "gdp_growth"]
    assert set(us.macro.fred_as_of) == set(us.macro.fred_fields)
    assert set(us.macro.fred_as_of.values()) == {"2024-06-01"}
    assert status == "mixed_static_and_fred"
    assert warnings == []
    # Unsupported markets stay static and never claim live macro.
    jp = next(m for m in markets if m.id == "jp")
    assert jp.source_status.macro == "static_sample"
    assert jp.macro.is_sample is True


def test_mock_fred_invalid_value_falls_back():
    cfg = _enabled_config()
    adapter = FredMacroAdapter(cfg, fetcher=_fake_fetcher("."))  # FRED missing value
    markets, status, _notice, warnings = build_markets_response(cfg, adapter=adapter)
    us = next(m for m in markets if m.id == "us")
    assert us.source_status.macro == "fred_unavailable"
    assert us.macro.is_sample is True  # static value retained
    assert status == "static_sample"
    assert any("us" in w for w in warnings)


def test_mock_fred_network_failure_falls_back():
    def boom(url, timeout):  # noqa: ARG001
        raise RuntimeError("network down")

    cfg = _enabled_config()
    adapter = FredMacroAdapter(cfg, fetcher=boom)
    markets, status, _notice, _warnings = build_markets_response(cfg, adapter=adapter)
    us = next(m for m in markets if m.id == "us")
    assert us.source_status.macro == "fred_unavailable"
    assert us.macro.is_sample is True
    assert status == "static_sample"


def test_api_key_never_in_response():
    secret = "SUPER_SECRET_KEY_123"
    cfg = FredMacroConfig(enabled=True, api_key=secret, base_url="https://fred.test")
    adapter = FredMacroAdapter(cfg, fetcher=_fake_fetcher("2.0", "2024-01-01"))
    markets, _status, notice, warnings = build_markets_response(cfg, adapter=adapter)
    blob = " ".join(m.model_dump_json() for m in markets) + " ".join(warnings) + notice
    assert secret not in blob
    assert "api_key" not in blob


def test_enriched_markets_no_nan_or_inf():
    cfg = _enabled_config()
    adapter = FredMacroAdapter(cfg, fetcher=_fake_fetcher("3.5", "2024-06-01"))
    markets, _status, _notice, _warnings = build_markets_response(cfg, adapter=adapter)
    for m in markets:
        _assert_all_finite(m.model_dump())


def test_series_cache_dedupes_calls():
    calls = {"n": 0}

    def counting(url, timeout):  # noqa: ARG001
        calls["n"] += 1
        return {"observations": [{"date": "2024-01-01", "value": "1.0"}]}

    cfg = _enabled_config(ttl=3600)
    adapter = FredMacroAdapter(cfg, fetcher=counting)
    assert adapter.fetch_series_latest("FEDFUNDS") == (1.0, "2024-01-01")
    assert adapter.fetch_series_latest("FEDFUNDS") == (1.0, "2024-01-01")
    assert calls["n"] == 1  # second call served from cache


def test_single_market_endpoint_static_by_default(client):
    body = client.get("/globe/markets/us").json()
    assert body["id"] == "us"
    assert body["source_status"]["macro"] == "static_sample"


def test_latest_valid_observation_skips_fred_missing_marker():
    seen = {}

    def fetch(url, timeout):  # noqa: ARG001
        seen["url"] = url
        return {
            "observations": [
                {"date": "2024-06-01", "value": "."},
                {"date": "2024-05-01", "value": "4.75"},
            ]
        }

    adapter = FredMacroAdapter(_enabled_config(), fetcher=fetch)
    assert adapter.fetch_series_latest("FEDFUNDS") == (4.75, "2024-05-01")
    assert "limit=10" in seen["url"]


def test_series_with_malformed_date_falls_back_safely():
    adapter = FredMacroAdapter(
        _enabled_config(),
        fetcher=_fake_fetcher("4.75", "not-a-date"),
    )
    assert adapter.fetch_series_latest("FEDFUNDS") is None


def test_partial_fred_success_retains_static_fields_and_warns():
    def partial_fetch(url, timeout):  # noqa: ARG001
        if "FEDFUNDS" in url:
            return {"observations": [{"date": "2024-06-01", "value": "5.25"}]}
        return {"observations": [{"date": "2024-06-01", "value": "."}]}

    cfg = _enabled_config()
    markets, status, _notice, warnings = build_markets_response(
        cfg,
        adapter=FredMacroAdapter(cfg, fetcher=partial_fetch),
    )
    us = next(m for m in markets if m.id == "us")
    assert status == "mixed_static_and_fred"
    assert us.macro.is_sample is True
    assert us.macro.fred_fields == ["policy_rate"]
    assert us.macro.fred_as_of == {"policy_rate": "2024-06-01"}
    assert us.macro.policy_rate == 5.25
    assert us.macro.unemployment == get_market("us").macro.unemployment
    assert any("partial" in warning.lower() for warning in warnings)


def test_macro_aggregate_date_is_oldest_enriched_observation():
    dates = {
        "FEDFUNDS": ("5.25", "2024-06-01"),
        "UNRATE": ("4.0", "2024-05-01"),
        "A191RL1Q225SBEA": ("1.4", "2024-03-01"),
    }

    def dated_fetch(url, timeout):  # noqa: ARG001
        series = next(series_id for series_id in dates if series_id in url)
        value, observation_date = dates[series]
        return {"observations": [{"date": observation_date, "value": value}]}

    cfg = _enabled_config()
    markets, _status, _notice, _warnings = build_markets_response(
        cfg,
        adapter=FredMacroAdapter(cfg, fetcher=dated_fetch),
    )
    us = next(m for m in markets if m.id == "us")
    assert us.macro.as_of_date == "2024-03-01"
    assert us.macro.fred_as_of["policy_rate"] == "2024-06-01"
    assert us.macro.fred_as_of["gdp_growth"] == "2024-03-01"


def test_unsupported_market_never_calls_fred():
    def boom(url, timeout):  # noqa: ARG001
        raise AssertionError("unsupported market must not call FRED")

    adapter = FredMacroAdapter(_enabled_config(), fetcher=boom)
    dossier, state, warnings = adapter.enrich_market_with_fred_macro(get_market("jp"))
    assert dossier.source_status.macro == "static_sample"
    assert state == "static_sample"
    assert warnings == []


def test_fred_environment_config_is_bounded_and_https_only():
    cfg = FredMacroConfig.from_env(
        {
            "GLOBE_FRED_ENABLED": "true",
            "FRED_BASE_URL": "http://example.test/fred?api_key=leak",
            "FRED_TIMEOUT_SECONDS": "inf",
            "GLOBE_FRED_CACHE_TTL_SECONDS": "9999999",
        }
    )
    assert cfg.base_url == globe_adapters.DEFAULT_FRED_BASE_URL
    assert cfg.timeout_seconds == 5.0
    assert cfg.cache_ttl_seconds == globe_adapters.MAX_FRED_CACHE_TTL_SECONDS

    bounded = FredMacroConfig.from_env(
        {
            "FRED_BASE_URL": "https://fred.example.test/custom/",
            "FRED_TIMEOUT_SECONDS": "999",
            "GLOBE_FRED_CACHE_TTL_SECONDS": "-5",
        }
    )
    assert bounded.base_url == "https://fred.example.test/custom"
    assert bounded.timeout_seconds == globe_adapters.MAX_FRED_TIMEOUT_SECONDS
    assert bounded.cache_ttl_seconds == 0


def test_fred_endpoint_success_has_field_provenance_and_no_api_key(
    client, monkeypatch
):
    secret = "ENDPOINT_SECRET_KEY"
    monkeypatch.setenv("GLOBE_FRED_ENABLED", "true")
    monkeypatch.setenv("FRED_API_KEY", secret)
    monkeypatch.setattr(
        globe_adapters,
        "_default_fetcher",
        _fake_fetcher("2.5", "2024-04-01"),
    )

    response = client.get("/globe/markets")
    assert response.status_code == 200
    body = response.json()
    us = next(m for m in body["markets"] if m["id"] == "us")
    assert body["data_status"] == "mixed_static_and_fred"
    assert us["source_status"]["macro"] == "fred_live"
    assert us["macro"]["is_sample"] is True
    assert set(us["macro"]["fred_fields"]) == {
        "policy_rate",
        "unemployment",
        "gdp_growth",
    }
    assert secret not in response.text
    assert "api_key" not in response.text
