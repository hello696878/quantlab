"""
Default-parameter smoke tests.

Verifies that the built-in strategies' *default* parameters (the ones a
first-time user gets) produce a valid backtest response and generate signals on
deterministic synthetic price data — no live yfinance, no network.

`main._fetch` is monkeypatched to a seeded oscillating-plus-drift series so the
result is fully deterministic.  These tests also lock in the calibrated default
values so an accidental change is caught.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")

# 600 business days ≈ 2.3y — enough for every default look-back (max 100).
_DATES = pd.date_range("2015-01-01", periods=600, freq="B")

# Per-ticker (drift, amplitude, frequency).  The oscillation guarantees SMA
# crossovers, RSI swings, Bollinger touches, momentum sign flips and breakouts;
# KO/PEP differ slightly so the pairs spread mean-reverts across ±z.
_PARAMS = {
    "SPY": (0.0004, 0.013, 0.10),
    "KO": (0.0002, 0.011, 0.080),
    "PEP": (0.0002, 0.011, 0.094),
}


def _series(drift: float, amp: float, freq: float) -> list[float]:
    prices = [100.0]
    for i in range(1, len(_DATES)):
        r = drift + amp * math.sin(freq * i) + 0.3 * amp * math.cos(0.31 * i)
        prices.append(prices[-1] * (1.0 + r))
    return prices


def _fake_fetch(ticker: str, start: str, end: str) -> pd.DataFrame:
    drift, amp, freq = _PARAMS.get(ticker.upper(), (0.0004, 0.013, 0.09))
    return pd.DataFrame({"Close": _series(drift, amp, freq)}, index=_DATES)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main_module, "_fetch", _fake_fetch)
    return TestClient(main_module.app)


# All single-asset endpoints reachable with an all-defaults ({}) body.
_SINGLE_ENDPOINTS = [
    "/backtest/sma-crossover",
    "/backtest/rsi-mean-reversion",
    "/backtest/bollinger-band",
    "/backtest/momentum",
    "/backtest/volatility-breakout",
]


# ---------------------------------------------------------------------------
# Defaults never throw and always return a valid response
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("endpoint", _SINGLE_ENDPOINTS)
def test_default_params_return_valid_response(client, endpoint):
    """POST with an empty body → schema defaults → 200 + a valid backtest."""
    resp = client.post(endpoint, json={})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["equity_curve"]) > 1
    assert "strategy_metrics" in body and "benchmark_metrics" in body
    assert isinstance(body["num_trades"], int)
    assert body["num_trades"] >= 0


def test_pairs_default_params_return_valid_response(client):
    """Pairs defaults (KO/PEP) also produce a valid response on synthetic data."""
    resp = client.post("/backtest/pairs", json={})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["equity_curve"]) > 1
    assert isinstance(body["num_trades"], int)
    assert body["num_trades"] >= 0


# ---------------------------------------------------------------------------
# Defaults actually generate trades (not a zero-trade first run)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "endpoint", ["/backtest/sma-crossover", "/backtest/rsi-mean-reversion"]
)
def test_default_params_generate_trades(client, endpoint):
    """On clearly oscillating data, the demo defaults must produce signals."""
    body = client.post(endpoint, json={}).json()
    assert body["num_trades"] > 0, f"{endpoint} produced zero trades on demo data"


# ---------------------------------------------------------------------------
# Lock in the calibrated demo-friendly defaults (regression guard)
# ---------------------------------------------------------------------------


def test_sma_defaults_are_demo_friendly(client):
    body = client.post("/backtest/sma-crossover", json={}).json()
    assert body["fast_window"] == 20
    assert body["slow_window"] == 100


def test_rsi_defaults_are_demo_friendly(client):
    body = client.post("/backtest/rsi-mean-reversion", json={}).json()
    assert body["rsi_window"] == 14
    assert body["oversold_threshold"] == 35
    assert body["exit_threshold"] == 55


def test_bb_defaults_are_demo_friendly(client):
    body = client.post("/backtest/bollinger-band", json={}).json()
    assert body["bb_window"] == 20
    assert body["bb_num_std"] == pytest.approx(1.8)
    assert body["bb_exit_band"] == "middle"


def test_momentum_defaults_are_demo_friendly(client):
    body = client.post("/backtest/momentum", json={}).json()
    assert body["momentum_window"] == 63


def test_vb_defaults_are_demo_friendly(client):
    body = client.post("/backtest/volatility-breakout", json={}).json()
    assert body["vb_lookback_window"] == 20
    assert body["vb_breakout_multiplier"] == pytest.approx(0.3)
    assert body["vb_exit_window"] == 10


def test_pairs_defaults_are_demo_friendly(client):
    body = client.post("/backtest/pairs", json={}).json()
    assert body["pairs_lookback_window"] == 60
    assert body["pairs_entry_z_score"] == pytest.approx(1.5)
    assert body["pairs_exit_z_score"] == pytest.approx(0.5)
