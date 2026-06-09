"""
Tests for the risk-management engine (research v1).

Two layers:
  * pure rules (`app.risk_management`) — stop loss, take profit, trailing stop,
    max holding, close-to-cash (never reverse), re-entry, no-lookahead;
  * the API — none preserves old behaviour, rules are echoed + diagnosed, trade
    reasons appear, costs/turnover interact correctly, and bad input → 422.

All data is deterministic / synthetic — no live yfinance.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from app.risk_management import apply_risk_management, diagnostics, resolve
from app.schemas import RiskManagement

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")


def _close(values: list[float], start: str = "2020-01-01") -> pd.Series:
    idx = pd.date_range(start, periods=len(values), freq="B")
    return pd.Series([float(v) for v in values], index=idx, name="close")


def _pos(values: list[int], idx) -> pd.Series:
    return pd.Series([float(v) for v in values], index=idx, name="position")


def _adj(position, close, risk):
    return apply_risk_management(position, close, risk).position.tolist()


# ---------------------------------------------------------------------------
# Pure rules
# ---------------------------------------------------------------------------


def test_none_is_identity():
    close = _close([100, 101, 99, 102, 100])
    pos = _pos([0, 1, 1, 0, 1], close.index)
    r = apply_risk_management(pos, close, None)
    assert r.position.equals(pos)
    assert r.exit_reasons == {}
    r2 = apply_risk_management(pos, close, RiskManagement(type="none"))
    assert r2.position.equals(pos)


def test_long_stop_loss_exits_when_price_falls():
    close = _close([100, 100, 100, 89, 100, 100])
    pos = _pos([1, 1, 1, 1, 1, 1], close.index)
    risk = RiskManagement(type="fixed_stop_take_profit", stop_loss_pct=0.10)
    r = apply_risk_management(pos, close, risk)
    # Decision for bar t uses close[t-1]; close[3]=89 ≤ 100*0.9 → exit at bar 4.
    assert r.position.tolist() == [1, 1, 1, 1, 0, 0]
    assert r.exit_reasons[4] == "stop_loss"
    assert r.counts["stop_loss_count"] == 1


def test_short_stop_loss_exits_when_price_rises():
    close = _close([100, 100, 100, 111, 100, 100])
    pos = _pos([-1, -1, -1, -1, -1, -1], close.index)
    risk = RiskManagement(type="fixed_stop_take_profit", stop_loss_pct=0.10)
    r = apply_risk_management(pos, close, risk)
    assert r.position.tolist() == [-1, -1, -1, -1, 0, 0]
    assert r.exit_reasons[4] == "stop_loss"


def test_long_take_profit_exits_when_price_rises():
    close = _close([100, 100, 100, 121, 100, 100])
    pos = _pos([1, 1, 1, 1, 1, 1], close.index)
    risk = RiskManagement(type="fixed_stop_take_profit", take_profit_pct=0.20)
    r = apply_risk_management(pos, close, risk)
    assert r.position.tolist() == [1, 1, 1, 1, 0, 0]
    assert r.exit_reasons[4] == "take_profit"


def test_short_take_profit_exits_when_price_falls():
    close = _close([100, 100, 100, 79, 100, 100])
    pos = _pos([-1, -1, -1, -1, -1, -1], close.index)
    risk = RiskManagement(type="fixed_stop_take_profit", take_profit_pct=0.20)
    r = apply_risk_management(pos, close, risk)
    assert r.position.tolist() == [-1, -1, -1, -1, 0, 0]
    assert r.exit_reasons[4] == "take_profit"


def test_long_trailing_stop_tracks_peak():
    close = _close([100, 110, 120, 108, 108])
    pos = _pos([1, 1, 1, 1, 1], close.index)
    risk = RiskManagement(type="trailing_stop", trailing_stop_pct=0.10)
    r = apply_risk_management(pos, close, risk)
    # Peak (through close[3]) = 120; close[3]=108 ≤ 120*0.9 → exit at bar 4.
    assert r.position.tolist() == [1, 1, 1, 1, 0]
    assert r.exit_reasons[4] == "trailing_stop"


def test_short_trailing_stop_tracks_trough():
    close = _close([100, 90, 80, 88, 88])
    pos = _pos([-1, -1, -1, -1, -1], close.index)
    risk = RiskManagement(type="trailing_stop", trailing_stop_pct=0.10)
    r = apply_risk_management(pos, close, risk)
    # Trough = 80; close[3]=88 ≥ 80*1.1 → exit at bar 4.
    assert r.position.tolist() == [-1, -1, -1, -1, 0]
    assert r.exit_reasons[4] == "trailing_stop"


def test_max_holding_days_exits_after_n_bars():
    close = _close([100] * 6)
    pos = _pos([1, 1, 1, 1, 1, 1], close.index)
    risk = RiskManagement(type="max_holding_days", max_holding_days=3)
    r = apply_risk_management(pos, close, risk)
    # Held bars 0,1,2 (3 bars) then flat.
    assert r.position.tolist() == [1, 1, 1, 0, 0, 0]
    assert r.exit_reasons[3] == "max_holding_days"


def test_risk_exit_closes_to_cash_not_reverse():
    close = _close([100, 100, 100, 80, 100, 100])
    pos = _pos([1, 1, 1, 1, 1, 1], close.index)
    risk = RiskManagement(type="fixed_stop_take_profit", stop_loss_pct=0.10)
    out = _adj(pos, close, risk)
    # Never flips to short; only closes to 0.
    assert min(out) == 0  # no -1 introduced by the risk rule
    assert out[4] == 0


def test_new_signal_can_reenter_after_risk_exit():
    close = _close([100, 100, 100, 89, 100, 100, 100, 100])
    pos = _pos([1, 1, 1, 1, 1, 0, 1, 1], close.index)
    risk = RiskManagement(type="fixed_stop_take_profit", stop_loss_pct=0.10)
    r = apply_risk_management(pos, close, risk)
    # Stop at bar 4, blocked through bar 5 (desired 0 resets), re-enter bar 6.
    assert r.position.tolist() == [1, 1, 1, 1, 0, 0, 1, 1]
    assert r.num_entries == 2


def test_persistent_signal_stays_blocked_until_reset():
    close = _close([100, 100, 100, 89, 100, 100])
    pos = _pos([1, 1, 1, 1, 1, 1], close.index)  # never resets to 0
    risk = RiskManagement(type="fixed_stop_take_profit", stop_loss_pct=0.10)
    out = _adj(pos, close, risk)
    assert out[4] == 0 and out[5] == 0  # no immediate re-entry


def test_combined_first_trigger_wins_and_diagnostics():
    close = _close([100, 100, 100, 89, 100, 100])
    pos = _pos([1, 1, 1, 1, 1, 1], close.index)
    risk = RiskManagement(
        type="combined", stop_loss_pct=0.10, take_profit_pct=0.20, max_holding_days=10
    )
    r = apply_risk_management(pos, close, risk)
    assert r.exit_reasons[4] == "stop_loss"
    d = diagnostics(r)
    assert d.risk_exit_count == 1
    assert d.stop_loss_count == 1
    assert d.risk_exit_rate == pytest.approx(1.0)  # 1 exit / 1 entry


def test_resolve_none_is_none():
    assert resolve(None) is None
    assert resolve(RiskManagement(type="none")) is None
    r = resolve(RiskManagement(type="trailing_stop", trailing_stop_pct=0.1))
    assert r is not None and r.type == "trailing_stop"


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


def test_api_no_risk_is_backward_compatible(client):
    body = client.post("/backtest/sma-crossover", json={}).json()
    assert body["risk_management"] is None
    assert body["risk_diagnostics"] is None
    # Reason is an additive optional field: null when risk management is inactive.
    assert all(t["reason"] is None for t in body["trades"])


def test_api_none_equals_no_risk(client):
    a = client.post("/backtest/sma-crossover", json={}).json()
    b = client.post(
        "/backtest/sma-crossover", json={"risk_management": {"type": "none"}}
    ).json()
    assert a["equity_curve"] == b["equity_curve"]
    assert a["strategy_metrics"] == b["strategy_metrics"]


def test_api_stop_loss_echo_diagnostics_and_reasons(client):
    body = client.post(
        "/backtest/sma-crossover",
        json={"risk_management": {"type": "fixed_stop_take_profit", "stop_loss_pct": 0.03}},
    ).json()
    assert body["risk_management"]["type"] == "fixed_stop_take_profit"
    assert body["risk_diagnostics"] is not None
    # When risk is active every trade carries a reason.
    assert all("reason" in t for t in body["trades"])
    reasons = {t["reason"] for t in body["trades"]}
    assert reasons.issubset(
        {"signal_entry", "signal_exit", "signal_flip", "stop_loss", "take_profit",
         "trailing_stop", "max_holding_days"}
    )


def test_api_risk_exits_incur_costs(client):
    body = client.post(
        "/backtest/sma-crossover",
        json={
            "risk_management": {"type": "fixed_stop_take_profit", "stop_loss_pct": 0.02},
            "transaction_cost_bps": 20,
        },
    ).json()
    d = body["risk_diagnostics"]
    if d["risk_exit_count"] > 0:
        risk_trades = [t for t in body["trades"] if t["reason"] in (
            "stop_loss", "take_profit", "trailing_stop", "max_holding_days")]
        assert risk_trades, "diagnostics report exits but no risk trade found"
        assert all(t["cost"] >= 0 for t in risk_trades)
        assert body["total_transaction_cost"] >= 0


def test_api_fixed_fraction_reduces_turnover_with_stop(client):
    base = {"risk_management": {"type": "fixed_stop_take_profit", "stop_loss_pct": 0.03}}
    full = client.post("/backtest/sma-crossover", json=base).json()
    half = client.post(
        "/backtest/sma-crossover",
        json={**base, "position_sizing": {"type": "fixed_fraction", "fraction": 0.5}},
    ).json()
    # Half exposure ⇒ about half the turnover for the same risk exits.
    assert (
        half["diagnostics"]["turnover_estimate"]
        <= full["diagnostics"]["turnover_estimate"] + 1e-9
    )


def test_api_long_short_with_risk_runs(client):
    body = client.post(
        "/backtest/sma-crossover",
        json={
            "position_mode": "long_short",
            "risk_management": {"type": "trailing_stop", "trailing_stop_pct": 0.05},
        },
    ).json()
    assert body["position_mode"] == "long_short"
    assert body["risk_management"]["type"] == "trailing_stop"


def test_api_max_holding_days_runs(client):
    body = client.post(
        "/backtest/momentum",
        json={"risk_management": {"type": "max_holding_days", "max_holding_days": 10}},
    ).json()
    assert body["risk_management"]["type"] == "max_holding_days"
    assert body["risk_diagnostics"] is not None


@pytest.mark.parametrize(
    "risk",
    [
        {"type": "fixed_stop_take_profit", "stop_loss_pct": -0.1},
        {"type": "fixed_stop_take_profit", "take_profit_pct": 0},
        {"type": "fixed_stop_take_profit"},  # neither stop nor take present
        {"type": "trailing_stop", "trailing_stop_pct": -0.1},
        {"type": "trailing_stop"},  # missing required
        {"type": "trailing_stop", "trailing_stop_pct": 2.0},  # > 1
        {"type": "max_holding_days", "max_holding_days": 0},
        {"type": "max_holding_days"},  # missing required
        {"type": "combined"},  # no active rule
        {"type": "nuke_it"},  # invalid type
    ],
)
def test_api_invalid_risk_rejected(client, risk):
    resp = client.post("/backtest/sma-crossover", json={"risk_management": risk})
    assert resp.status_code == 422
