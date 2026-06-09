"""
Tests for the transaction-cost / slippage model (research v1).

Two layers:
  * pure resolution (`app.cost_model.resolve`) — simple_bps, commission_slippage,
    conservative, and the None / fallback path;
  * the API — the resolved cost is echoed, the effective per-side bps drives the
    engine, equivalent specs produce identical results, and bad input → 422.

All data is deterministic / synthetic — no live yfinance.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from app.cost_model import resolve
from app.schemas import CostModel

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")


# ---------------------------------------------------------------------------
# Pure resolution
# ---------------------------------------------------------------------------


def test_resolve_none_uses_fallback():
    r = resolve(None, 10.0)
    assert r.type == "simple_bps"
    assert r.effective_bps_per_side == 10.0
    assert (r.commission_bps, r.slippage_bps, r.spread_bps) == (0.0, 0.0, 0.0)


def test_resolve_simple_bps_explicit_value():
    r = resolve(CostModel(type="simple_bps", transaction_cost_bps=25.0), 10.0)
    assert r.effective_bps_per_side == 25.0


def test_resolve_simple_bps_falls_back_when_omitted():
    r = resolve(CostModel(type="simple_bps"), 7.5)
    assert r.effective_bps_per_side == 7.5


def test_resolve_commission_slippage_sums_all_three():
    r = resolve(
        CostModel(
            type="commission_slippage",
            commission_bps=10.0,
            slippage_bps=10.0,
            spread_bps=5.0,
        ),
        10.0,
    )
    assert r.effective_bps_per_side == 25.0
    assert (r.commission_bps, r.slippage_bps, r.spread_bps) == (10.0, 10.0, 5.0)


def test_resolve_commission_slippage_spread_optional():
    r = resolve(
        CostModel(type="commission_slippage", commission_bps=8.0, slippage_bps=4.0),
        10.0,
    )
    assert r.effective_bps_per_side == 12.0
    assert r.spread_bps == 0.0


def test_resolve_conservative_is_fixed_preset():
    r = resolve(CostModel(type="conservative"), 10.0)
    assert r.effective_bps_per_side == 25.0
    assert (r.commission_bps, r.slippage_bps, r.spread_bps) == (10.0, 10.0, 5.0)
    assert "Conservative" in r.label


def test_resolve_conservative_ignores_other_fields():
    # The conservative preset is fixed regardless of any supplied components.
    r = resolve(CostModel(type="conservative", commission_bps=999.0), 10.0)
    assert r.effective_bps_per_side == 25.0


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


def _fake_pairs(asset_y: str, asset_x: str, start: str, end: str):
    base = [100.0 * (1.0 + 0.01 * math.sin(0.05 * i)) for i in range(len(_DATES))]
    close_y = pd.Series(base, index=_DATES, name="y")
    close_x = pd.Series(
        [b * 0.98 + 1.0 for b in base], index=_DATES, name="x"
    )
    return close_y, close_x


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main_module, "_fetch", _fake_fetch)
    monkeypatch.setattr(main_module, "fetch_pairs_close", _fake_pairs)
    return TestClient(main_module.app)


def test_api_no_cost_model_is_backward_compatible(client):
    body = client.post(
        "/backtest/sma-crossover", json={"transaction_cost_bps": 10}
    ).json()
    assert body["transaction_cost_bps"] == 10.0
    assert body["cost_model"] is None  # echo only present when supplied


def test_api_conservative_sets_effective_25(client):
    body = client.post(
        "/backtest/sma-crossover", json={"cost_model": {"type": "conservative"}}
    ).json()
    assert body["cost_model"]["type"] == "conservative"
    assert body["cost_model"]["effective_bps_per_side"] == 25.0
    assert body["transaction_cost_bps"] == 25.0  # reported cost is the effective


def test_api_commission_slippage_sums(client):
    body = client.post(
        "/backtest/sma-crossover",
        json={
            "cost_model": {
                "type": "commission_slippage",
                "commission_bps": 10,
                "slippage_bps": 10,
                "spread_bps": 5,
            }
        },
    ).json()
    assert body["transaction_cost_bps"] == 25.0
    assert body["cost_model"]["effective_bps_per_side"] == 25.0


def test_api_simple_bps_equals_top_level(client):
    """cost_model simple_bps=X is identical to top-level transaction_cost_bps=X."""
    a = client.post(
        "/backtest/sma-crossover", json={"transaction_cost_bps": 30}
    ).json()
    b = client.post(
        "/backtest/sma-crossover",
        json={"cost_model": {"type": "simple_bps", "transaction_cost_bps": 30}},
    ).json()
    assert a["equity_curve"] == b["equity_curve"]
    assert a["strategy_metrics"] == b["strategy_metrics"]


def test_api_commission_slippage_equivalent_to_simple(client):
    """A 15+7+3 = 25 bps spec feeds the engine identically to simple 25 bps."""
    a = client.post(
        "/backtest/sma-crossover", json={"transaction_cost_bps": 25}
    ).json()
    b = client.post(
        "/backtest/sma-crossover",
        json={
            "cost_model": {
                "type": "commission_slippage",
                "commission_bps": 15,
                "slippage_bps": 7,
                "spread_bps": 3,
            }
        },
    ).json()
    assert a["equity_curve"] == b["equity_curve"]
    assert a["strategy_metrics"] == b["strategy_metrics"]


def test_api_simple_bps_falls_back_to_top_level(client):
    body = client.post(
        "/backtest/sma-crossover",
        json={"transaction_cost_bps": 12, "cost_model": {"type": "simple_bps"}},
    ).json()
    assert body["transaction_cost_bps"] == 12.0
    assert body["cost_model"]["effective_bps_per_side"] == 12.0


def test_api_negative_component_rejected(client):
    resp = client.post(
        "/backtest/sma-crossover",
        json={"cost_model": {"type": "commission_slippage", "commission_bps": -1}},
    )
    assert resp.status_code == 422


def test_api_invalid_cost_model_type_rejected(client):
    resp = client.post(
        "/backtest/sma-crossover", json={"cost_model": {"type": "free_lunch"}}
    )
    assert resp.status_code == 422


def test_api_commission_slippage_effective_cost_too_high_rejected(client):
    resp = client.post(
        "/backtest/sma-crossover",
        json={
            "cost_model": {
                "type": "commission_slippage",
                "commission_bps": 5000,
                "slippage_bps": 4000,
                "spread_bps": 1000,
            }
        },
    )
    assert resp.status_code == 422
    assert "less than 10,000 bps" in resp.text


def test_api_pairs_cost_model_applied_and_echoed(client):
    body = client.post(
        "/backtest/pairs",
        json={"asset_y": "KO", "asset_x": "PEP", "cost_model": {"type": "conservative"}},
    ).json()
    assert body["transaction_cost_bps"] == 25.0
    assert body["cost_model"]["type"] == "conservative"
    assert body["cost_model"]["effective_bps_per_side"] == 25.0


def test_api_higher_cost_does_not_increase_return(client):
    """Sanity: more friction never helps. Conservative (25 bps) ≤ 0 bps return."""
    cheap = client.post(
        "/backtest/sma-crossover",
        json={"cost_model": {"type": "simple_bps", "transaction_cost_bps": 0}},
    ).json()["strategy_metrics"]["total_return"]
    pricey = client.post(
        "/backtest/sma-crossover", json={"cost_model": {"type": "conservative"}}
    ).json()["strategy_metrics"]["total_return"]
    assert pricey <= cheap + 1e-9


# ── Cost-transparency output fields ─────────────────────────────────────────


def test_api_output_fields_present_and_consistent(client):
    body = client.post(
        "/backtest/sma-crossover", json={"cost_model": {"type": "conservative"}}
    ).json()
    assert body["effective_cost_bps"] == 25.0
    assert body["total_transaction_cost"] >= 0.0
    # Costs reduce return → drag is non-negative; gross = net + drag.
    assert body["cost_drag_return"] >= -1e-9


def test_api_zero_cost_has_no_drag(client):
    body = client.post(
        "/backtest/sma-crossover",
        json={"cost_model": {"type": "simple_bps", "transaction_cost_bps": 0}},
    ).json()
    assert body["total_transaction_cost"] == pytest.approx(0.0, abs=1e-6)
    assert body["cost_drag_return"] == pytest.approx(0.0, abs=1e-6)


def test_api_higher_cost_increases_drag(client):
    cheap = client.post(
        "/backtest/sma-crossover",
        json={"cost_model": {"type": "simple_bps", "transaction_cost_bps": 5}},
    ).json()["cost_drag_return"]
    pricey = client.post(
        "/backtest/sma-crossover", json={"cost_model": {"type": "conservative"}}
    ).json()["cost_drag_return"]
    assert pricey >= cheap - 1e-9


# ── long_short turnover still works with a cost model ───────────────────────


def test_api_long_short_turnover_cost_with_cost_model(client):
    body = client.post(
        "/backtest/sma-crossover",
        json={
            "position_mode": "long_short",
            "cost_model": {
                "type": "commission_slippage",
                "commission_bps": 5,
                "slippage_bps": 5,
                "spread_bps": 2,
            },
        },
    ).json()
    assert body["position_mode"] == "long_short"
    assert body["effective_cost_bps"] == 12.0
    assert body["num_trades"] > 0
    actions = [t["action"] for t in body["trades"]]
    # Long/short produces flips; flips are charged at 2x turnover by the engine.
    assert any(a in ("FLIP_TO_LONG", "FLIP_TO_SHORT") for a in actions)
    assert body["total_transaction_cost"] > 0.0


def test_api_long_only_simple_cost_model_matches_plain_bps(client):
    """long_only + simple_bps cost model == long_only + plain transaction_cost_bps."""
    a = client.post(
        "/backtest/sma-crossover",
        json={"position_mode": "long_only", "transaction_cost_bps": 15},
    ).json()
    b = client.post(
        "/backtest/sma-crossover",
        json={
            "position_mode": "long_only",
            "cost_model": {"type": "simple_bps", "transaction_cost_bps": 15},
        },
    ).json()
    assert a["equity_curve"] == b["equity_curve"]
    assert a["strategy_metrics"] == b["strategy_metrics"]
