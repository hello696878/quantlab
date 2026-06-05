"""
Tests for long / short / long-short position modes.

Covers three layers:
  * the backtest engine (short returns, flip turnover, trade-log actions),
  * the signal generators (SMA / Momentum / Volatility Breakout mode mapping,
    with long_only proven identical to the original behaviour), and
  * the API (position_mode echoed, valid trade actions, 422 on bad input).

All data is deterministic / synthetic — no live yfinance.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from app.backtest import run_backtest
from app.strategies import (
    momentum_signals,
    sma_crossover_signals,
    volatility_breakout_signals,
)

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")


def _close(values: list[float], start: str = "2020-01-01") -> pd.Series:
    idx = pd.date_range(start, periods=len(values), freq="B")
    return pd.Series([float(v) for v in values], index=idx, name="close")


# ---------------------------------------------------------------------------
# Engine: short returns, flip turnover, trade-log actions
# ---------------------------------------------------------------------------


def test_short_position_inverts_return():
    close = _close([100.0, 110.0, 100.0])
    pos = pd.Series([0, -1, -1], index=close.index)  # short over days 1..2
    eq, _bench, _trades = run_backtest(
        close, pos, transaction_cost_bps=0.0, initial_capital=1000.0
    )
    # Day 1: short a +10% move → −10% → 900.
    assert eq.iloc[1] == pytest.approx(900.0)
    # Day 2: short a −9.0909% move → +9.0909% → 900 * (1 + 10/110).
    assert eq.iloc[2] == pytest.approx(900.0 * (1.0 + 10.0 / 110.0), rel=1e-9)


def test_flip_long_to_short_actions_and_double_turnover_cost():
    close = _close([100.0, 100.0, 100.0, 100.0])  # flat → isolate costs
    pos = pd.Series([0, 1, -1, 0], index=close.index)
    eq, _bench, trades = run_backtest(
        close, pos, transaction_cost_bps=100.0, initial_capital=1000.0
    )  # 100 bps = 1%
    assert [t["action"] for t in trades] == ["BUY", "FLIP_TO_SHORT", "COVER"]
    # BUY costs 1% of 1000 → equity 990.
    assert eq.iloc[1] == pytest.approx(990.0)
    # FLIP has turnover 2 → 2% of 990 → equity 970.2; logged cost = 990*2*1%.
    assert trades[1]["cost"] == pytest.approx(19.8, rel=1e-6)
    assert eq.iloc[2] == pytest.approx(970.2, rel=1e-9)


def test_short_then_cover_actions():
    close = _close([100.0, 100.0, 100.0])
    pos = pd.Series([0, -1, 0], index=close.index)
    _eq, _bench, trades = run_backtest(close, pos, transaction_cost_bps=10.0)
    assert [t["action"] for t in trades] == ["SHORT", "COVER"]


def test_long_only_engine_unchanged():
    """A 0/1 position series still yields only BUY/SELL (regression guard)."""
    close = _close([100.0, 105.0, 110.0, 108.0, 100.0])
    pos = pd.Series([0, 1, 1, 0, 0], index=close.index)
    _eq, _bench, trades = run_backtest(close, pos, transaction_cost_bps=10.0)
    assert [t["action"] for t in trades] == ["BUY", "SELL"]


def test_position_out_of_range_rejected():
    close = _close([100.0, 101.0, 102.0])
    with pytest.raises(ValueError, match="between -1"):
        run_backtest(close, pd.Series([0, 2, 2], index=close.index))


# ---------------------------------------------------------------------------
# Signals: mode mapping + long_only equivalence
# ---------------------------------------------------------------------------

# Up then down → guaranteed bullish and bearish regimes for every strategy.
_UP_DOWN = list(range(100, 180)) + list(range(180, 100, -1))


def test_sma_mode_mapping_and_long_only_identity():
    close = _close(_UP_DOWN)
    lo = sma_crossover_signals(close, 5, 20, "long_only")
    so = sma_crossover_signals(close, 5, 20, "short_only")
    ls = sma_crossover_signals(close, 5, 20, "long_short")

    # long_only matches the original (default) call exactly.
    assert lo.equals(sma_crossover_signals(close, 5, 20))
    assert set(lo.unique()).issubset({0, 1})
    assert set(so.unique()).issubset({0, -1})
    assert set(ls.unique()).issubset({-1, 0, 1})
    assert (ls == 1).any() and (ls == -1).any()
    # Consistency: long_short longs ⊆ long_only longs; shorts ⊆ short_only shorts.
    assert (lo[ls == 1] == 1).all()
    assert (so[ls == -1] == -1).all()


def test_momentum_mode_mapping_and_long_only_identity():
    close = _close(_UP_DOWN)
    lo = momentum_signals(close, 10, position_mode="long_only")
    so = momentum_signals(close, 10, position_mode="short_only")
    ls = momentum_signals(close, 10, position_mode="long_short")

    assert lo.equals(momentum_signals(close, 10))
    assert set(lo.unique()).issubset({0, 1})
    assert set(so.unique()).issubset({0, -1})
    assert (ls == 1).any() and (ls == -1).any()


def test_volatility_breakout_short_mode_generates_shorts():
    # Stable, then a sharp drop (downside breakdown), then recovery (cover).
    close = _close([100.0] * 30 + [80.0] + [80.0 + i * 0.4 for i in range(40)])
    lo = volatility_breakout_signals(close, 20, 0.3, 10, "long_only")
    so = volatility_breakout_signals(close, 20, 0.3, 10, "short_only")

    # long_only unchanged vs the default call.
    assert lo.equals(volatility_breakout_signals(close, 20, 0.3, 10))
    assert set(so.unique()).issubset({0, -1})
    assert (so == -1).any(), "short mode should breakdown-short the sharp drop"


def test_invalid_position_mode_raises():
    close = _close(_UP_DOWN)
    for fn in (
        lambda: sma_crossover_signals(close, 5, 20, "bogus"),
        lambda: momentum_signals(close, 10, position_mode="bogus"),
        lambda: volatility_breakout_signals(close, 20, 0.3, 10, "bogus"),
    ):
        with pytest.raises(ValueError, match="position_mode"):
            fn()


# ---------------------------------------------------------------------------
# API: position_mode echoed, valid actions, validation
# ---------------------------------------------------------------------------

_DATES = pd.date_range("2015-01-01", periods=600, freq="B")


def _fake_fetch(ticker: str, start: str, end: str) -> pd.DataFrame:
    # Drift-free, long-period oscillation (~140 days) so the trailing return
    # over the default 63-day momentum window swings clearly positive AND
    # negative — i.e. every strategy sees both bullish and bearish regimes.
    prices = [100.0]
    for i in range(1, len(_DATES)):
        r = 0.012 * math.sin(0.045 * i) + 0.004 * math.cos(0.23 * i)
        prices.append(prices[-1] * (1.0 + r))
    return pd.DataFrame({"Close": prices}, index=_DATES)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main_module, "_fetch", _fake_fetch)
    return TestClient(main_module.app)


_LONG_SHORT_ENDPOINTS = [
    "/backtest/sma-crossover",
    "/backtest/momentum",
    "/backtest/volatility-breakout",
]

_VALID_ACTIONS = {"BUY", "SELL", "SHORT", "COVER", "FLIP_TO_LONG", "FLIP_TO_SHORT"}


@pytest.mark.parametrize("endpoint", _LONG_SHORT_ENDPOINTS)
def test_api_defaults_to_long_only(client, endpoint):
    body = client.post(endpoint, json={}).json()
    assert body["position_mode"] == "long_only"
    for t in body["trades"]:
        assert t["action"] in ("BUY", "SELL")


@pytest.mark.parametrize("endpoint", _LONG_SHORT_ENDPOINTS)
def test_api_short_only(client, endpoint):
    body = client.post(endpoint, json={"position_mode": "short_only"}).json()
    assert body["position_mode"] == "short_only"
    assert body["num_trades"] > 0
    for t in body["trades"]:
        assert t["action"] in ("SHORT", "COVER")


@pytest.mark.parametrize("endpoint", _LONG_SHORT_ENDPOINTS)
def test_api_long_short(client, endpoint):
    body = client.post(endpoint, json={"position_mode": "long_short"}).json()
    assert body["position_mode"] == "long_short"
    assert body["num_trades"] > 0
    actions = {t["action"] for t in body["trades"]}
    assert actions.issubset(_VALID_ACTIONS)
    # Long/short should put on both long and short exposure on oscillating data.
    assert actions & {"BUY", "FLIP_TO_LONG"}
    assert actions & {"SHORT", "FLIP_TO_SHORT"}


@pytest.mark.parametrize("endpoint", _LONG_SHORT_ENDPOINTS)
def test_api_invalid_mode_returns_422(client, endpoint):
    resp = client.post(endpoint, json={"position_mode": "sideways"})
    assert resp.status_code == 422


def test_api_long_only_matches_omitted_mode(client):
    """Explicit long_only equals the implicit default (no behaviour drift)."""
    a = client.post("/backtest/sma-crossover", json={}).json()
    b = client.post(
        "/backtest/sma-crossover", json={"position_mode": "long_only"}
    ).json()
    assert a["num_trades"] == b["num_trades"]
    assert a["strategy_metrics"]["total_return"] == pytest.approx(
        b["strategy_metrics"]["total_return"]
    )
