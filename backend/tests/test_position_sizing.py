"""
Tests for the position-sizing engine (research v1).

Two layers:
  * pure sizing (`app.position_sizing`) — full / fixed_fraction / max_exposure /
    volatility_target, plus average exposure and the no-lookahead / no-leverage
    guarantees;
  * the API — sizing is echoed, exposure is scaled, full_allocation ==
    no-sizing, and bad input → 422.

All data is deterministic / synthetic — no live yfinance.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from app.position_sizing import apply_sizing, average_exposure, resolve
from app.schemas import PositionSizing

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")


def _close(values: list[float], start: str = "2020-01-01") -> pd.Series:
    idx = pd.date_range(start, periods=len(values), freq="B")
    return pd.Series([float(v) for v in values], index=idx, name="close")


def _pos(values: list[float], idx) -> pd.Series:
    return pd.Series([float(v) for v in values], index=idx, name="position")


# ---------------------------------------------------------------------------
# Pure sizing
# ---------------------------------------------------------------------------


def test_full_and_none_are_identity():
    close = _close([100, 101, 102, 103])
    pos = _pos([0, 1, 1, 0], close.index)
    assert apply_sizing(pos, close, None).equals(pos)
    assert apply_sizing(pos, close, PositionSizing(type="full_allocation")).equals(pos)
    # Legacy alias is still accepted and normalized by the schema.
    assert PositionSizing(type="full").type == "full_allocation"


def test_fixed_fraction_scales_magnitude():
    close = _close([100, 101, 102, 103])
    pos = _pos([0, 1, -1, 1], close.index)
    out = apply_sizing(pos, close, PositionSizing(type="fixed_fraction", fraction=0.5))
    assert out.tolist() == [0.0, 0.5, -0.5, 0.5]


def test_max_exposure_caps_magnitude():
    close = _close([100, 101, 102, 103])
    pos = _pos([0, 1, -1, 1], close.index)
    out = apply_sizing(pos, close, PositionSizing(type="max_exposure", max_exposure=0.8))
    assert out.tolist() == [0.0, 0.8, -0.8, 0.8]


def test_volatility_target_no_leverage_and_no_lookahead():
    # Constant-ish drift → tiny realized vol → scale would explode, but is capped
    # at 1.0 (no leverage).  The first scaled value is 0 (NaN vol, then shift).
    close = _close([100 * (1.01**i) for i in range(60)])
    pos = _pos([1] * 60, close.index)
    out = apply_sizing(
        pos, close, PositionSizing(type="volatility_target", target_volatility=0.15, lookback_days=20)
    )
    assert (out.abs() <= 1.0 + 1e-9).all()  # never leverages
    assert out.iloc[0] == 0.0  # no lookahead — first day has no prior vol


def test_volatility_target_delevers_in_high_vol():
    # A high-vol series should be scaled DOWN toward the target.
    swings = [100.0]
    for i in range(1, 80):
        swings.append(swings[-1] * (1.05 if i % 2 == 0 else 0.96))  # ~±5% daily
    close = _close(swings)
    pos = _pos([1] * 80, close.index)
    out = apply_sizing(
        pos, close, PositionSizing(type="volatility_target", target_volatility=0.10, lookback_days=20)
    )
    # Average exposure well below full investment.
    assert average_exposure(out) < 0.8


def test_volatility_target_matches_prior_day_vol_estimate():
    close = _close([100, 103, 101, 106, 100, 98, 104, 101])
    pos = _pos([1] * len(close), close.index)
    sizing = PositionSizing(
        type="volatility_target",
        target_volatility=0.20,
        lookback_days=3,
        max_exposure=0.75,
    )

    out = apply_sizing(pos, close, sizing)
    daily_returns = close.pct_change()
    target_daily_vol = 0.20 / math.sqrt(252)
    expected_scale = (target_daily_vol / daily_returns.rolling(3).std()).shift(1)
    expected = expected_scale.clip(lower=0.0, upper=0.75).fillna(0.0)

    pd.testing.assert_series_equal(out, expected, check_names=False)


def test_volatility_target_zero_vol_is_finite_and_capped():
    close = _close([100] * 30)
    pos = _pos([1] * 30, close.index)
    out = apply_sizing(
        pos,
        close,
        PositionSizing(
            type="volatility_target",
            target_volatility=0.10,
            lookback_days=5,
            max_exposure=0.6,
        ),
    )
    assert out.notna().all()
    assert (out.abs() <= 0.6 + 1e-12).all()


def test_average_exposure():
    s = pd.Series([0.0, 1.0, 0.5, 0.0])
    assert average_exposure(s) == pytest.approx((0 + 1 + 0.5 + 0) / 4)
    assert average_exposure(pd.Series([], dtype=float)) == 0.0


def test_resolve_labels():
    assert resolve(None).type == "full_allocation"
    assert resolve(PositionSizing(type="full_allocation")).type == "full_allocation"
    r = resolve(PositionSizing(type="fixed_fraction", fraction=0.5))
    assert r.type == "fixed_fraction" and r.fraction == 0.5
    r = resolve(PositionSizing(type="max_exposure", max_exposure=0.8))
    assert r.type == "max_exposure" and r.max_exposure == 0.8
    r = resolve(PositionSizing(type="volatility_target", target_volatility=0.15, lookback_days=20))
    assert r.type == "volatility_target" and r.target_volatility == 0.15 and r.lookback_days == 20


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


def test_api_no_sizing_is_backward_compatible(client):
    body = client.post("/backtest/sma-crossover", json={}).json()
    assert body["position_sizing"]["type"] == "full_allocation"
    assert 0.0 <= body["average_exposure"] <= 1.0


def test_api_full_equals_no_sizing(client):
    a = client.post("/backtest/sma-crossover", json={}).json()
    b = client.post(
        "/backtest/sma-crossover", json={"position_sizing": {"type": "full_allocation"}}
    ).json()
    assert a["equity_curve"] == b["equity_curve"]
    assert a["strategy_metrics"] == b["strategy_metrics"]


def test_api_legacy_full_alias_is_normalized(client):
    body = client.post(
        "/backtest/sma-crossover", json={"position_sizing": {"type": "full"}}
    ).json()
    assert body["position_sizing"]["type"] == "full_allocation"


def test_api_fixed_fraction_one_equals_full(client):
    full = client.post("/backtest/sma-crossover", json={}).json()
    frac1 = client.post(
        "/backtest/sma-crossover",
        json={"position_sizing": {"type": "fixed_fraction", "fraction": 1.0}},
    ).json()
    assert full["equity_curve"] == frac1["equity_curve"]


def test_api_fixed_fraction_halves_exposure(client):
    full = client.post("/backtest/sma-crossover", json={}).json()
    half = client.post(
        "/backtest/sma-crossover",
        json={"position_sizing": {"type": "fixed_fraction", "fraction": 0.5}},
    ).json()
    assert half["position_sizing"]["type"] == "fixed_fraction"
    assert half["average_exposure"] == pytest.approx(full["average_exposure"] * 0.5, rel=1e-6)
    # Same signal timing → same number of trade events.
    assert half["num_trades"] == full["num_trades"]


def test_api_max_exposure_echo_and_bounds(client):
    body = client.post(
        "/backtest/sma-crossover",
        json={"position_sizing": {"type": "max_exposure", "max_exposure": 0.7}},
    ).json()
    assert body["position_sizing"]["type"] == "max_exposure"
    assert body["position_sizing"]["max_exposure"] == 0.7
    assert body["average_exposure"] <= 0.7 + 1e-9


def test_api_volatility_target_runs_and_caps(client):
    body = client.post(
        "/backtest/sma-crossover",
        json={
            "position_sizing": {
                "type": "volatility_target",
                "target_volatility": 0.1,
                "lookback_days": 20,
                "max_exposure": 0.8,
            }
        },
    ).json()
    assert body["position_sizing"]["type"] == "volatility_target"
    assert body["position_sizing"]["lookback_days"] == 20
    assert body["position_sizing"]["max_exposure"] == 0.8
    assert body["average_exposure"] <= 0.8 + 1e-9


def test_api_volatility_target_accepts_legacy_vol_lookback_alias(client):
    body = client.post(
        "/backtest/sma-crossover",
        json={
            "position_sizing": {
                "type": "volatility_target",
                "target_volatility": 0.1,
                "vol_lookback": 20,
            }
        },
    ).json()
    assert body["position_sizing"]["lookback_days"] == 20


def test_api_sizing_composes_with_cost_model(client):
    body = client.post(
        "/backtest/sma-crossover",
        json={
            "position_sizing": {"type": "fixed_fraction", "fraction": 0.5},
            "cost_model": {"type": "conservative"},
        },
    ).json()
    assert body["position_sizing"]["type"] == "fixed_fraction"
    assert body["effective_cost_bps"] == 25.0


def test_api_long_short_sizing_runs(client):
    body = client.post(
        "/backtest/sma-crossover",
        json={
            "position_mode": "long_short",
            "position_sizing": {"type": "fixed_fraction", "fraction": 0.5},
        },
    ).json()
    assert body["position_mode"] == "long_short"
    assert body["num_trades"] > 0
    assert body["average_exposure"] <= 0.5 + 1e-9


@pytest.mark.parametrize(
    "sizing",
    [
        {"type": "fixed_fraction", "fraction": 0},
        {"type": "fixed_fraction", "fraction": 1.5},
        {"type": "fixed_fraction"},
        {"type": "max_exposure", "max_exposure": 0},
        {"type": "max_exposure", "max_exposure": 1.5},
        {"type": "max_exposure"},
        {"type": "volatility_target", "target_volatility": 0},
        {"type": "leveraged"},
    ],
)
def test_api_invalid_sizing_rejected(client, sizing):
    resp = client.post("/backtest/sma-crossover", json={"position_sizing": sizing})
    assert resp.status_code == 422
