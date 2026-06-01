"""
API tests for POST /portfolio/efficient-frontier.

main._fetch is monkeypatched to deterministic synthetic prices; no network.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")

_PARAMS = {
    "SPY": (0.0005, 0.010, 0.10),
    "QQQ": (0.0007, 0.016, 0.13),
    "GLD": (0.0002, 0.008, 0.07),
    "TLT": (0.0001, 0.006, 0.05),
}


def _fake_fetch(ticker: str, start: str, end: str) -> pd.DataFrame:
    base, amp, freq = _PARAMS.get(ticker.upper(), (0.0003, 0.011, 0.09))
    idx = pd.date_range("2018-01-01", periods=400, freq="B")
    prices = [100.0]
    for i in range(1, len(idx)):
        r = base + amp * math.sin(freq * i) + 0.4 * amp * math.cos(0.31 * i)
        prices.append(prices[-1] * (1.0 + r))
    return pd.DataFrame({"Close": prices}, index=idx)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main_module, "_fetch", _fake_fetch)
    return TestClient(main_module.app)


def base_request(**overrides) -> dict:
    req = {
        "tickers": ["SPY", "QQQ", "GLD", "TLT"],
        "start_date": "2018-01-01",
        "end_date": "2019-06-01",
        "risk_free_rate": 0.02,
        "num_portfolios": 500,
    }
    req.update(overrides)
    return req


def _assert_valid_special(p, tickers):
    assert set(p["weights"]) == set(tickers)
    assert sum(p["weights"].values()) == pytest.approx(1.0, abs=1e-4)
    for w in p["weights"].values():
        assert w >= -1e-9
    assert p["volatility"] >= 0


# ---------------------------------------------------------------------------
# Happy path / response shape
# ---------------------------------------------------------------------------


def test_valid_efficient_frontier(client):
    resp = client.post("/portfolio/efficient-frontier", json=base_request())
    assert resp.status_code == 200, resp.text
    data = resp.json()
    for key in (
        "expected_returns", "covariance_matrix", "random_portfolios",
        "equal_weight", "min_volatility", "max_sharpe", "frontier_points",
        "in_sample_note",
    ):
        assert key in data, key


def test_expected_returns_and_covariance(client):
    data = client.post("/portfolio/efficient-frontier", json=base_request()).json()
    tickers = data["tickers"]
    assert set(data["expected_returns"]) == set(tickers)
    cov = data["covariance_matrix"]
    assert set(cov) == set(tickers)
    for a in tickers:
        assert cov[a][a] > 0
        for b in tickers:
            assert cov[a][b] == pytest.approx(cov[b][a], rel=1e-6)


def test_random_portfolios_generated_and_valid(client):
    data = client.post(
        "/portfolio/efficient-frontier", json=base_request(num_portfolios=750)
    ).json()
    rps = data["random_portfolios"]
    assert len(rps) == 750
    for p in rps:
        assert set(p["weights"]) == set(data["tickers"])
        assert sum(p["weights"].values()) == pytest.approx(1.0, abs=1e-4)
        for w in p["weights"].values():
            assert w >= -1e-9


def test_special_portfolios_generated(client):
    data = client.post("/portfolio/efficient-frontier", json=base_request()).json()
    _assert_valid_special(data["equal_weight"], data["tickers"])
    _assert_valid_special(data["min_volatility"], data["tickers"])
    _assert_valid_special(data["max_sharpe"], data["tickers"])
    # Equal weight is exactly 1/N.
    for w in data["equal_weight"]["weights"].values():
        assert w == pytest.approx(0.25, abs=1e-6)


def test_min_vol_has_lowest_vol_among_specials(client):
    data = client.post("/portfolio/efficient-frontier", json=base_request()).json()
    mv = data["min_volatility"]["volatility"]
    assert mv <= data["equal_weight"]["volatility"] + 1e-6
    assert mv <= data["max_sharpe"]["volatility"] + 1e-6


def test_max_sharpe_has_highest_sharpe_among_specials(client):
    data = client.post("/portfolio/efficient-frontier", json=base_request()).json()
    ms = data["max_sharpe"]["sharpe"]
    assert ms >= data["equal_weight"]["sharpe"] - 1e-6
    assert ms >= data["min_volatility"]["sharpe"] - 1e-6


def test_frontier_points_generated(client):
    data = client.post("/portfolio/efficient-frontier", json=base_request()).json()
    pts = data["frontier_points"]
    assert len(pts) >= 1
    vols = [p["volatility"] for p in pts]
    assert vols == sorted(vols)
    for p in pts:
        assert "expected_return" in p and "volatility" in p
        assert "weights" not in p  # curve points are lightweight


def test_deterministic_random_portfolios(client):
    a = client.post("/portfolio/efficient-frontier", json=base_request()).json()
    b = client.post("/portfolio/efficient-frontier", json=base_request()).json()
    assert a["random_portfolios"][0] == b["random_portfolios"][0]
    assert a["random_portfolios"][100] == b["random_portfolios"][100]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_empty_tickers_rejected(client):
    assert client.post("/portfolio/efficient-frontier", json=base_request(tickers=[])).status_code == 422


def test_duplicate_tickers_rejected(client):
    resp = client.post(
        "/portfolio/efficient-frontier", json=base_request(tickers=["SPY", "spy"])
    )
    assert resp.status_code == 422


def test_too_many_tickers_rejected(client):
    many = [f"T{i}" for i in range(21)]
    assert client.post("/portfolio/efficient-frontier", json=base_request(tickers=many)).status_code == 422


def test_bad_dates_rejected(client):
    resp = client.post(
        "/portfolio/efficient-frontier",
        json=base_request(start_date="2019-01-01", end_date="2018-01-01"),
    )
    assert resp.status_code == 422


@pytest.mark.parametrize("num", [99, 10001, 0, -5])
def test_invalid_num_portfolios_rejected(client, num):
    assert client.post("/portfolio/efficient-frontier", json=base_request(num_portfolios=num)).status_code == 422


def test_negative_risk_free_rate_rejected(client):
    assert client.post("/portfolio/efficient-frontier", json=base_request(risk_free_rate=-0.01)).status_code == 422


def test_insufficient_common_data_returns_422(client, monkeypatch):
    def disjoint_fetch(ticker: str, start: str, end: str) -> pd.DataFrame:
        if ticker.upper() == "AAA":
            idx = pd.date_range("2018-01-01", periods=50, freq="B")
        else:
            idx = pd.date_range("2019-06-01", periods=50, freq="B")
        return pd.DataFrame({"Close": [100.0 + i for i in range(50)]}, index=idx)

    monkeypatch.setattr(main_module, "_fetch", disjoint_fetch)
    resp = client.post(
        "/portfolio/efficient-frontier", json=base_request(tickers=["AAA", "BBB"])
    )
    assert resp.status_code == 422
    assert "common trading day" in resp.json()["detail"]
