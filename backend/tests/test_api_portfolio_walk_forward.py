"""
API tests for POST /portfolio/walk-forward-optimize.

main._fetch is monkeypatched to deterministic synthetic prices with genuine
return variance; no network is used.
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
    idx = pd.date_range("2015-01-01", periods=1000, freq="B")
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
        "start_date": "2015-01-01",
        "end_date": "2018-12-31",
        "train_window_days": 252,
        "test_window_days": 63,
        "step_days": 63,
        "objective": "max_sharpe",
        "risk_free_rate": 0.02,
        "initial_capital": 100000,
        "transaction_cost_bps": 10,
    }
    req.update(overrides)
    return req


def _assert_valid_window(w, tickers):
    assert set(w["weights"]) == set(tickers)
    assert sum(w["weights"].values()) == pytest.approx(1.0, abs=1e-4)
    for v in w["weights"].values():
        assert v >= -1e-9


# ---------------------------------------------------------------------------
# Happy paths per objective
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("objective", ["max_sharpe", "min_volatility", "equal_weight"])
def test_walk_forward_valid(client, objective):
    resp = client.post(
        "/portfolio/walk-forward-optimize", json=base_request(objective=objective)
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["objective"] == objective
    assert data["num_windows"] >= 1
    assert len(data["windows"]) == data["num_windows"]
    for w in data["windows"]:
        _assert_valid_window(w, data["tickers"])


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------


def test_response_sections_present(client):
    data = client.post("/portfolio/walk-forward-optimize", json=base_request()).json()
    for key in (
        "windows", "stitched_equity_curve", "benchmark_equity_curve",
        "drawdown", "metrics", "benchmark_metrics", "weight_stability", "oos_note",
    ):
        assert key in data, key


def test_stitched_and_benchmark_aligned_and_anchored(client):
    data = client.post("/portfolio/walk-forward-optimize", json=base_request()).json()
    se = data["stitched_equity_curve"]
    be = data["benchmark_equity_curve"]
    assert len(se) > 1
    assert len(se) == len(be) == len(data["drawdown"])
    assert se[0]["value"] == pytest.approx(100000, abs=1.0)
    assert be[0]["value"] == pytest.approx(100000, abs=1.0)
    assert se[0]["date"] == be[0]["date"]


def test_window_fields_present(client):
    data = client.post("/portfolio/walk-forward-optimize", json=base_request()).json()
    w = data["windows"][0]
    for key in (
        "train_start_date", "train_end_date", "test_start_date", "test_end_date",
        "weights", "train_expected_return", "train_volatility", "train_sharpe",
        "test_metrics", "turnover", "transaction_cost",
    ):
        assert key in w, key
    # Training period precedes the test period.
    assert w["train_end_date"] < w["test_start_date"]


def test_first_window_entry_turnover(client):
    data = client.post("/portfolio/walk-forward-optimize", json=base_request()).json()
    assert data["windows"][0]["turnover"] == pytest.approx(1.0, abs=1e-4)


def test_weight_stability_present(client):
    data = client.post("/portfolio/walk-forward-optimize", json=base_request()).json()
    stab = data["weight_stability"]
    for key in (
        "average_turnover", "max_turnover",
        "average_weight_by_asset", "min_weight_by_asset", "max_weight_by_asset",
    ):
        assert key in stab, key
    assert set(stab["average_weight_by_asset"]) == set(data["tickers"])


def test_metrics_blocks_present(client):
    data = client.post("/portfolio/walk-forward-optimize", json=base_request()).json()
    for block in (data["metrics"], data["benchmark_metrics"]):
        for key in ("total_return", "cagr", "sharpe_ratio", "max_drawdown", "num_days"):
            assert key in block


def test_transaction_cost_effect(client):
    free = client.post(
        "/portfolio/walk-forward-optimize", json=base_request(transaction_cost_bps=0)
    ).json()
    costly = client.post(
        "/portfolio/walk-forward-optimize", json=base_request(transaction_cost_bps=100)
    ).json()
    assert (
        costly["stitched_equity_curve"][-1]["value"]
        < free["stitched_equity_curve"][-1]["value"]
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_duplicate_tickers_rejected(client):
    resp = client.post(
        "/portfolio/walk-forward-optimize", json=base_request(tickers=["SPY", "spy"])
    )
    assert resp.status_code == 422


def test_invalid_objective_rejected(client):
    resp = client.post(
        "/portfolio/walk-forward-optimize", json=base_request(objective="max_return")
    )
    assert resp.status_code == 422


def test_bad_dates_rejected(client):
    resp = client.post(
        "/portfolio/walk-forward-optimize",
        json=base_request(start_date="2019-01-01", end_date="2018-01-01"),
    )
    assert resp.status_code == 422


@pytest.mark.parametrize("field", ["train_window_days", "test_window_days", "step_days"])
def test_non_positive_window_sizes_rejected(client, field):
    resp = client.post(
        "/portfolio/walk-forward-optimize", json=base_request(**{field: 0})
    )
    assert resp.status_code == 422


def test_too_few_days_for_a_window_returns_422(client):
    # Train + test exceeds the ~1000 available days.
    resp = client.post(
        "/portfolio/walk-forward-optimize",
        json=base_request(train_window_days=900, test_window_days=200),
    )
    assert resp.status_code == 422
    assert "need at least" in resp.json()["detail"]


def test_empty_tickers_rejected(client):
    assert (
        client.post("/portfolio/walk-forward-optimize", json=base_request(tickers=[])).status_code
        == 422
    )


def test_zero_capital_rejected(client):
    assert (
        client.post("/portfolio/walk-forward-optimize", json=base_request(initial_capital=0)).status_code
        == 422
    )
