"""
Tests for Stability Lab v1 (SMA parameter-sensitivity sweep).

Pure layer: grid building, invalid combinations, matrix shape, stability score
bounds, best-value consistency.  API layer: disabled preserves behaviour,
enabled returns the block, metric switching, max_runs enforcement, unsupported
strategies, compact payload (no per-cell equity curves).

All deterministic / monkeypatched — no live yfinance.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from app.schemas import SensitivityConfig
from app.sensitivity import (
    build_parameter_grid,
    compute_stability_score,
    run_sensitivity_grid,
    unsupported_sensitivity,
)

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")


def _close(n: int = 400) -> pd.Series:
    idx = pd.date_range("2015-01-01", periods=n, freq="B")
    prices = [100.0]
    for i in range(1, n):
        r = 0.012 * math.sin(0.045 * i) + 0.004 * math.cos(0.23 * i)
        prices.append(prices[-1] * (1.0 + r))
    return pd.Series(prices, index=idx, name="Close")


def _cfg(**kw) -> SensitivityConfig:
    base = dict(enabled=True, metric="sharpe")
    base.update(kw)
    return SensitivityConfig(**base)


def _run(close=None, config=None, fast=20, slow=100):
    return run_sensitivity_grid(
        close if close is not None else _close(),
        config or _cfg(),
        current_fast=fast,
        current_slow=slow,
        position_mode="long_only",
        risk_management=None,
        position_sizing=None,
        effective_cost_bps=10.0,
        initial_capital=100_000.0,
        periods_per_year=252,
    )


# ---------------------------------------------------------------------------
# Pure engine
# ---------------------------------------------------------------------------


def test_grid_includes_current_params():
    xs, ys = build_parameter_grid(_cfg(), current_fast=22, current_slow=111)
    assert 22 in xs and 111 in ys
    assert xs == sorted(xs) and ys == sorted(ys)


def test_default_grid_runs_and_matrix_shape():
    res = _run()
    assert res.supported is True
    assert len(res.matrix) == len(res.y_values)
    assert all(len(row) == len(res.x_values) for row in res.matrix)
    assert len(res.runs) == len(res.x_values) * len(res.y_values)
    valid_runs = [r for r in res.runs if r.valid]
    assert len(valid_runs) > 0


def test_invalid_fast_ge_slow_marked_invalid():
    res = _run(config=_cfg(x_values=[50, 80], y_values=[60, 100]), fast=50, slow=100)
    bad = [r for r in res.runs if r.fast_window >= r.slow_window]
    assert bad and all(not r.valid and r.metrics is None for r in bad)
    # Invalid cells are null in the matrix, valid ones are numbers.
    xi = res.x_values.index(80)
    yi = res.y_values.index(60)
    assert res.matrix[yi][xi] is None  # fast 80 ≥ slow 60


def test_selected_point_reported_with_value():
    res = _run(fast=20, slow=100)
    assert res.selected_point is not None
    assert res.selected_point.fast_window == 20
    assert res.selected_point.slow_window == 100
    assert res.selected_point.value is not None
    assert res.summary is not None
    assert res.summary.selected_value == pytest.approx(res.selected_point.value)


def test_metric_changes_matrix_values():
    sharpe = _run(config=_cfg(metric="sharpe"))
    ret = _run(config=_cfg(metric="total_return"))
    assert sharpe.metric == "sharpe" and ret.metric == "total_return"
    assert sharpe.matrix != ret.matrix  # same grid, different metric surface


def test_max_runs_enforced():
    cfg = _cfg(
        x_values=[5, 10, 15, 20, 25, 30, 35, 40, 45, 50],
        y_values=[60, 70, 80, 90, 100, 110, 120, 130, 140, 150],
        max_runs=50,
    )
    with pytest.raises(ValueError, match="exceeding the limit"):
        _run(config=cfg)


def test_stability_score_bounds_and_flag():
    res = _run()
    s = res.summary
    assert s is not None
    if s.stability_score is not None:
        assert 0.0 <= s.stability_score <= 1.0
    assert isinstance(s.fragility_flag, bool)
    assert s.explanation


def test_best_value_matches_runs():
    res = _run(config=_cfg(metric="total_return"))
    values = [r.metrics.total_return for r in res.runs if r.valid and r.metrics]
    assert res.summary is not None and res.summary.best_value is not None
    assert res.summary.best_value == pytest.approx(max(values), abs=1e-6)
    bp = res.summary.best_params
    assert bp is not None
    match = next(
        r for r in res.runs if r.fast_window == bp.fast_window and r.slow_window == bp.slow_window
    )
    assert match.valid


def test_max_drawdown_best_is_shallowest():
    res = _run(config=_cfg(metric="max_drawdown"))
    dds = [r.metrics.max_drawdown for r in res.runs if r.valid and r.metrics]
    # "Best" drawdown = highest value (closest to zero / least negative).
    assert res.summary.best_value == pytest.approx(max(dds), abs=1e-6)


def test_isolated_spike_is_fragile():
    # Synthetic neighborhood: selected cell hugely above all neighbors.
    xs, ys = [10, 20, 30], [60, 100, 140]
    cells = {(x, y): 0.1 for x in xs for y in ys}
    cells[(20, 100)] = 5.0
    score, fragile, median, _mn, text = compute_stability_score(
        xs, ys, cells, 20, 100, 5.0
    )
    assert score is not None and score < 0.5
    assert fragile is True
    assert median == pytest.approx(0.1)
    assert "sensitive" in text


def test_flat_plateau_is_stable():
    xs, ys = [10, 20, 30], [60, 100, 140]
    cells = {(x, y): 0.8 for x in xs for y in ys}
    score, fragile, _med, _mn, text = compute_stability_score(xs, ys, cells, 20, 100, 0.8)
    assert score is not None and score > 0.9
    assert fragile is False
    assert "similar" in text


def test_too_few_neighbors_gives_null_score():
    xs, ys = [10, 20, 30], [60, 100, 140]
    cells = {(x, y): None for x in xs for y in ys}
    cells[(20, 100)] = 1.0
    score, fragile, *_ = compute_stability_score(xs, ys, cells, 20, 100, 1.0)
    assert score is None and fragile is False


def test_unsupported_strategy_block():
    block = unsupported_sensitivity("rsi_mean_reversion", _cfg())
    assert block.supported is False
    assert any("SMA Crossover" in w for w in block.warnings)
    assert block.matrix == [] and block.runs == []


# ---------------------------------------------------------------------------
# API integration
# ---------------------------------------------------------------------------

_DATES = pd.date_range("2015-01-01", periods=400, freq="B")


def _fake_fetch(ticker: str, start: str, end: str) -> pd.DataFrame:
    return pd.DataFrame({"Close": _close(len(_DATES)).to_numpy()}, index=_DATES)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main_module, "_fetch", _fake_fetch)
    return TestClient(main_module.app)


def test_api_disabled_preserves_normal_response(client):
    a = client.post("/backtest/sma-crossover", json={}).json()
    b = client.post(
        "/backtest/sma-crossover", json={"sensitivity": {"enabled": False}}
    ).json()
    assert a["sensitivity"] is None and b["sensitivity"] is None
    assert a["equity_curve"] == b["equity_curve"]
    assert a["strategy_metrics"] == b["strategy_metrics"]
    assert (
        a["reproducibility"]["config_hash_full"]
        == b["reproducibility"]["config_hash_full"]
    )


def test_api_enabled_returns_block_core_unchanged(client):
    plain = client.post("/backtest/sma-crossover", json={}).json()
    body = client.post(
        "/backtest/sma-crossover", json={"sensitivity": {"enabled": True}}
    ).json()
    s = body["sensitivity"]
    assert s["supported"] is True
    assert s["strategy"] == "sma_crossover"
    assert s["x_param"] == "fast_window" and s["y_param"] == "slow_window"
    assert 20 in s["x_values"] and 100 in s["y_values"]  # selected params included
    assert s["selected_point"]["fast_window"] == 20
    assert s["summary"]["stability_score"] is None or 0 <= s["summary"]["stability_score"] <= 1
    # Core results unchanged by the sweep.
    assert body["equity_curve"] == plain["equity_curve"]
    assert body["strategy_metrics"] == plain["strategy_metrics"]
    assert (
        body["reproducibility"]["config_hash_full"]
        == plain["reproducibility"]["config_hash_full"]
    )


def test_api_no_equity_curves_in_runs(client):
    body = client.post(
        "/backtest/sma-crossover", json={"sensitivity": {"enabled": True}}
    ).json()
    for run in body["sensitivity"]["runs"]:
        assert "equity_curve" not in run
        assert set(run.keys()) <= {
            "fast_window", "slow_window", "valid", "metrics", "num_trades", "warning"
        }


def test_api_oversized_grid_rejected(client):
    resp = client.post(
        "/backtest/sma-crossover",
        json={
            "sensitivity": {
                "enabled": True,
                "x_values": [4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32],
                "y_values": [40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170, 180],
                "max_runs": 200,
            }
        },
    )
    assert resp.status_code == 422
    assert "exceeding the limit" in resp.json()["detail"]


def test_api_unsupported_strategy_warns_no_crash(client):
    body = client.post(
        "/backtest/momentum", json={"sensitivity": {"enabled": True}}
    ).json()
    s = body["sensitivity"]
    assert s["supported"] is False
    assert any("SMA Crossover" in w for w in s["warnings"])
    assert body["strategy_metrics"]["total_return"] is not None  # backtest ran


def test_api_invalid_sensitivity_config_rejected(client):
    resp = client.post(
        "/backtest/sma-crossover",
        json={"sensitivity": {"enabled": True, "metric": "alpha_magic"}},
    )
    assert resp.status_code == 422


def test_api_sensitivity_respects_shared_simulation_settings(client):
    """Selected grid cell should match the base backtest under all shared controls."""
    req = {
        "fast_window": 10,
        "slow_window": 30,
        "cost_model": {"type": "conservative"},
        "position_sizing": {"type": "fixed_fraction", "fraction": 0.5},
        "risk_management": {"type": "max_holding_days", "max_holding_days": 8},
        "annualization_mode": "crypto_365",
        "sensitivity": {
            "enabled": True,
            "metric": "cagr",
            "x_values": [10],
            "y_values": [30],
        },
    }
    body = client.post("/backtest/sma-crossover", json=req).json()

    assert body["periods_per_year"] == 365
    assert body["cost_model"]["effective_bps_per_side"] == 25.0
    assert body["position_sizing"]["type"] == "fixed_fraction"
    assert body["risk_management"]["type"] == "max_holding_days"
    assert body["risk_diagnostics"]["risk_exit_count"] > 0
    assert body["sensitivity"]["selected_point"]["value"] == pytest.approx(
        body["strategy_metrics"]["cagr"], abs=1e-9
    )
