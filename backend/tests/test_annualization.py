"""
Tests for the annualization convention engine (research v1).

Covers the pure resolver, the metrics-engine scaling, and the API wiring on the
single-asset backtest + strategy-comparison endpoints.  All synthetic data — no
live yfinance.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from app.annualization import resolve_annualization
from app.metrics import compute_metrics

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")


# ---------------------------------------------------------------------------
# Pure resolver
# ---------------------------------------------------------------------------


def test_resolve_default_and_explicit_252():
    r = resolve_annualization("SPY", None)  # missing → backward-compatible 252
    assert r.mode == "trading_days_252" and r.mode_used == "trading_days_252"
    assert r.periods_per_year == 252 and r.warning is None
    r2 = resolve_annualization("SPY", "trading_days_252")
    assert r2.periods_per_year == 252


def test_resolve_explicit_crypto_365():
    r = resolve_annualization("SPY", "crypto_365")  # honored even for an equity
    assert r.mode_used == "crypto_365" and r.periods_per_year == 365


def test_resolve_auto_btc_is_365():
    r = resolve_annualization("BTC-USD", "auto")
    assert r.mode == "auto" and r.mode_used == "crypto_365"
    assert r.periods_per_year == 365 and r.warning is None


def test_resolve_auto_eth_is_365():
    assert resolve_annualization("ETH-USD", "auto").periods_per_year == 365


def test_resolve_auto_spy_is_252_no_warning():
    r = resolve_annualization("SPY", "auto")
    assert r.mode_used == "trading_days_252" and r.periods_per_year == 252
    assert r.warning is None


def test_resolve_auto_unknown_defaults_252_with_warning():
    r = resolve_annualization("ZZZZ", "auto")
    assert r.mode_used == "trading_days_252" and r.periods_per_year == 252
    assert r.warning is not None  # uncertain → 252 + caveat


# ---------------------------------------------------------------------------
# Metrics-engine scaling
# ---------------------------------------------------------------------------


def _equity() -> pd.Series:
    rng = np.random.default_rng(7)
    rets = rng.normal(3e-4, 0.011, 300)
    vals = 100_000.0 * (1 + rets).cumprod()
    idx = pd.date_range("2020-01-01", periods=300, freq="D")
    return pd.Series(vals, index=idx)


def test_metrics_default_is_252():
    eq = _equity()
    assert compute_metrics(eq) == compute_metrics(eq, periods_per_year=252)


def test_metrics_volatility_and_sharpe_scale_with_periods():
    eq = _equity()
    m252 = compute_metrics(eq, periods_per_year=252)
    m365 = compute_metrics(eq, periods_per_year=365)
    factor = math.sqrt(365 / 252)
    assert m365["volatility"] == pytest.approx(m252["volatility"] * factor, rel=1e-4)
    if m252["sharpe_ratio"] != 0:
        assert m365["sharpe_ratio"] == pytest.approx(m252["sharpe_ratio"] * factor, rel=1e-4)


def test_metrics_total_return_and_drawdown_unchanged_by_convention():
    eq = _equity()
    m252 = compute_metrics(eq, periods_per_year=252)
    m365 = compute_metrics(eq, periods_per_year=365)
    assert m365["total_return"] == m252["total_return"]
    assert m365["max_drawdown"] == m252["max_drawdown"]
    # CAGR differs (fewer years implied by more periods/year).
    assert m365["cagr"] != m252["cagr"]


def test_metrics_rejects_nonpositive_periods():
    with pytest.raises(ValueError):
        compute_metrics(_equity(), periods_per_year=0)


# ---------------------------------------------------------------------------
# API integration
# ---------------------------------------------------------------------------

_DATES = pd.date_range("2015-01-01", periods=400, freq="B")


def _fake_fetch(ticker: str, start: str, end: str) -> pd.DataFrame:
    prices = [100.0]
    for i in range(1, len(_DATES)):
        r = 0.012 * math.sin(0.045 * i) + 0.004 * math.cos(0.23 * i)
        prices.append(prices[-1] * (1.0 + r))
    return pd.DataFrame({"Close": prices}, index=_DATES)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main_module, "_fetch", _fake_fetch)
    return TestClient(main_module.app)


def test_api_default_is_252(client):
    body = client.post("/backtest/sma-crossover", json={}).json()
    assert body["annualization_mode"] == "trading_days_252"
    assert body["annualization_mode_used"] == "trading_days_252"
    assert body["periods_per_year"] == 252
    assert body["annualization_warning"] is None


def test_api_crypto_365_echo(client):
    body = client.post(
        "/backtest/sma-crossover", json={"annualization_mode": "crypto_365"}
    ).json()
    assert body["annualization_mode_used"] == "crypto_365"
    assert body["periods_per_year"] == 365


def test_api_auto_btc_resolves_365(client):
    body = client.post(
        "/backtest/sma-crossover",
        json={"ticker": "BTC-USD", "annualization_mode": "auto"},
    ).json()
    assert body["annualization_mode"] == "auto"
    assert body["annualization_mode_used"] == "crypto_365"
    assert body["periods_per_year"] == 365


def test_api_auto_spy_resolves_252(client):
    body = client.post(
        "/backtest/sma-crossover",
        json={"ticker": "SPY", "annualization_mode": "auto"},
    ).json()
    assert body["annualization_mode_used"] == "trading_days_252"


def test_api_invalid_mode_rejected(client):
    resp = client.post(
        "/backtest/sma-crossover", json={"annualization_mode": "weekly_52"}
    )
    assert resp.status_code == 422


def test_api_convention_changes_metrics_not_equity_or_total_return(client):
    a = client.post(
        "/backtest/sma-crossover", json={"annualization_mode": "trading_days_252"}
    ).json()
    b = client.post(
        "/backtest/sma-crossover", json={"annualization_mode": "crypto_365"}
    ).json()
    # Equity curve + total return identical.
    assert a["equity_curve"] == b["equity_curve"]
    assert a["strategy_metrics"]["total_return"] == b["strategy_metrics"]["total_return"]
    assert a["strategy_metrics"]["max_drawdown"] == b["strategy_metrics"]["max_drawdown"]
    assert a["num_trades"] == b["num_trades"]
    # Annualized risk metrics differ.
    assert a["strategy_metrics"]["volatility"] != b["strategy_metrics"]["volatility"]


def test_api_comparison_accepts_and_echoes_annualization(client):
    body = client.post(
        "/research/strategy-comparison",
        json={"ticker": "BTC-USD", "annualization_mode": "auto"},
    ).json()
    assert body["annualization_mode"] == "auto"
    assert body["annualization_mode_used"] == "crypto_365"
    assert body["periods_per_year"] == 365


def test_api_comparison_default_is_252(client):
    body = client.post("/research/strategy-comparison", json={}).json()
    assert body["annualization_mode_used"] == "trading_days_252"
    assert body["periods_per_year"] == 252
