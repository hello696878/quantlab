"""
API tests for POST /portfolio/factor-analysis.

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
    "IWM": (0.0004, 0.013, 0.17),
}


def _fake_fetch(ticker: str, start: str, end: str) -> pd.DataFrame:
    base, amp, freq = _PARAMS.get(ticker.upper(), (0.0003, 0.011, 0.09))
    idx = pd.date_range("2018-01-01", periods=600, freq="B")
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
        "end_date": "2020-01-01",
        "initial_capital": 100000,
        "factor_tickers": {
            "market": "SPY",
            "tech_growth": "QQQ",
            "small_cap": "IWM",
            "bonds": "TLT",
            "gold": "GLD",
        },
    }
    req.update(overrides)
    return req


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_valid_equal_weight(client):
    resp = client.post("/portfolio/factor-analysis", json=base_request())
    assert resp.status_code == 200, resp.text
    data = resp.json()
    for key in (
        "alpha_daily", "alpha_annualized", "betas", "r_squared",
        "residual_volatility", "factor_correlation_matrix", "diagnostics",
        "regression_points", "actual_equity_curve", "fitted_equity_curve",
        "historical_note",
    ):
        assert key in data, key
    for w in data["weights"].values():
        assert w == pytest.approx(0.25, abs=1e-6)


def test_valid_custom_weights(client):
    resp = client.post(
        "/portfolio/factor-analysis",
        json=base_request(weights={"SPY": 0.4, "QQQ": 0.3, "GLD": 0.2, "TLT": 0.1}),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["weights"]["SPY"] == pytest.approx(0.4, abs=1e-6)


def test_betas_cover_all_factors(client):
    data = client.post("/portfolio/factor-analysis", json=base_request()).json()
    assert set(data["betas"]) == set(data["factor_tickers"])
    assert isinstance(data["r_squared"], (int, float))
    assert data["residual_volatility"] >= 0


def test_alpha_annualized_relationship(client):
    data = client.post("/portfolio/factor-analysis", json=base_request()).json()
    assert data["alpha_annualized"] == pytest.approx(data["alpha_daily"] * 252, rel=1e-4, abs=1e-8)


def test_factor_correlation_matrix_symmetric(client):
    data = client.post("/portfolio/factor-analysis", json=base_request()).json()
    fac = list(data["factor_tickers"].keys())
    corr = data["factor_correlation_matrix"]
    assert set(corr) == set(fac)
    for a in fac:
        assert corr[a][a] == pytest.approx(1.0, abs=1e-6)
        for b in fac:
            assert corr[a][b] == pytest.approx(corr[b][a], abs=1e-6)
            assert math.isfinite(corr[a][b])


def test_equity_curves_and_regression_points(client):
    data = client.post("/portfolio/factor-analysis", json=base_request()).json()
    assert len(data["actual_equity_curve"]) > 1
    assert len(data["actual_equity_curve"]) == len(data["fitted_equity_curve"])
    assert data["actual_equity_curve"][0]["value"] == pytest.approx(100000, abs=1.0)
    assert data["fitted_equity_curve"][0]["value"] == pytest.approx(100000, abs=1.0)
    assert data["actual_equity_curve"][0]["date"] == "2018-01-01"
    assert data["actual_equity_curve"][1]["date"] != data["actual_equity_curve"][0]["date"]
    pts = data["regression_points"]
    assert len(pts) >= 1
    assert pts[0]["date"] == data["actual_equity_curve"][1]["date"]
    for p in pts[:10]:
        assert p["residual"] == pytest.approx(p["actual_return"] - p["fitted_return"], abs=1e-7)


def test_diagnostics_present(client):
    data = client.post("/portfolio/factor-analysis", json=base_request()).json()
    diag = data["diagnostics"]
    for key in (
        "strongest_positive_factor", "strongest_negative_factor",
        "absolute_largest_exposure", "multicollinearity_warning",
    ):
        assert key in diag


def test_single_factor_market_beta_near_one_when_portfolio_is_market(client):
    """A portfolio that IS the market regressed on the market → beta ≈ 1."""
    data = client.post(
        "/portfolio/factor-analysis",
        json=base_request(
            tickers=["SPY"],
            factor_tickers={"market": "SPY"},
        ),
    ).json()
    assert data["betas"]["market"] == pytest.approx(1.0, abs=1e-3)
    assert data["r_squared"] == pytest.approx(1.0, abs=1e-3)


def test_duplicate_factor_proxies_flag_multicollinearity(client):
    data = client.post(
        "/portfolio/factor-analysis",
        json=base_request(factor_tickers={"market": "SPY", "market_dup": "SPY"}),
    ).json()
    assert data["diagnostics"]["multicollinearity_warning"] is True


def test_factor_tickers_are_normalized(client):
    data = client.post(
        "/portfolio/factor-analysis",
        json=base_request(factor_tickers={"market": "spy", "bonds": "tlt"}),
    ).json()
    assert data["factor_tickers"] == {"market": "SPY", "bonds": "TLT"}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_empty_tickers_rejected(client):
    assert client.post("/portfolio/factor-analysis", json=base_request(tickers=[])).status_code == 422


def test_duplicate_tickers_rejected(client):
    resp = client.post(
        "/portfolio/factor-analysis", json=base_request(tickers=["SPY", "spy", "QQQ"])
    )
    assert resp.status_code == 422


def test_invalid_weights_rejected(client):
    resp = client.post(
        "/portfolio/factor-analysis",
        json=base_request(weights={"SPY": 0.5, "QQQ": 0.3, "GLD": 0.1, "TLT": 0.05}),
    )
    assert resp.status_code == 422


def test_negative_weights_rejected(client):
    resp = client.post(
        "/portfolio/factor-analysis",
        json=base_request(weights={"SPY": 0.8, "QQQ": 0.4, "GLD": 0.0, "TLT": -0.2}),
    )
    assert resp.status_code == 422


def test_missing_ticker_weight_rejected(client):
    resp = client.post(
        "/portfolio/factor-analysis",
        json=base_request(weights={"SPY": 0.5, "QQQ": 0.5}),
    )
    assert resp.status_code == 422


def test_extra_ticker_weight_rejected(client):
    resp = client.post(
        "/portfolio/factor-analysis",
        json=base_request(weights={"SPY": 0.4, "QQQ": 0.3, "GLD": 0.2, "TLT": 0.1, "XOM": 0.0}),
    )
    assert resp.status_code == 422


def test_empty_factors_rejected(client):
    assert client.post("/portfolio/factor-analysis", json=base_request(factor_tickers={})).status_code == 422


def test_too_many_factors_rejected(client):
    factors = {f"f{i}": "SPY" for i in range(11)}
    assert client.post("/portfolio/factor-analysis", json=base_request(factor_tickers=factors)).status_code == 422


def test_empty_factor_ticker_rejected(client):
    resp = client.post(
        "/portfolio/factor-analysis", json=base_request(factor_tickers={"market": "  "})
    )
    assert resp.status_code == 422


def test_bad_dates_rejected(client):
    resp = client.post(
        "/portfolio/factor-analysis",
        json=base_request(start_date="2020-01-01", end_date="2018-01-01"),
    )
    assert resp.status_code == 422


def test_zero_capital_rejected(client):
    assert client.post("/portfolio/factor-analysis", json=base_request(initial_capital=0)).status_code == 422
