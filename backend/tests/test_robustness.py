"""
Tests for Robustness Lab v1 (block bootstrap on daily strategy returns).

Pure layer: determinism per seed, percentile ordering, edge cases (all-positive,
all-negative, flat, insufficient data), block length, grade values.
API layer: disabled preserves behaviour, enabled returns the block, seed
determinism, benchmark outperform probability.

All deterministic / monkeypatched — no live yfinance.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from app.robustness import (
    bootstrap_returns,
    build_robustness_report,
    compute_robustness_grade,
)
from app.schemas import RobustnessConfig, RobustnessSummary

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")


def _cfg(**kw) -> RobustnessConfig:
    base = dict(enabled=True, n_simulations=300, block_size=5, seed=42)
    base.update(kw)
    return RobustnessConfig(**base)


def _returns(n: int = 250, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(4e-4, 0.01, n)


# ---------------------------------------------------------------------------
# Pure engine
# ---------------------------------------------------------------------------


def test_same_seed_same_summary():
    r = _returns()
    a = build_robustness_report(r, config=_cfg(), periods_per_year=252)
    b = build_robustness_report(r, config=_cfg(), periods_per_year=252)
    assert a.summary == b.summary
    assert a.grade == b.grade
    assert a.final_return_histogram == b.final_return_histogram


def test_different_seed_changes_summary():
    r = _returns()
    a = build_robustness_report(r, config=_cfg(seed=42), periods_per_year=252)
    b = build_robustness_report(r, config=_cfg(seed=43), periods_per_year=252)
    assert a.summary != b.summary  # distribution shifts with the seed


def test_percentiles_ordered_and_probability_bounded():
    rep = build_robustness_report(_returns(), config=_cfg(), periods_per_year=252)
    s = rep.summary
    assert s is not None
    assert s.p05_final_return <= s.median_final_return <= s.p95_final_return
    assert 0.0 <= s.probability_of_loss <= 1.0
    assert s.p05_sharpe <= s.median_sharpe <= s.p95_sharpe
    # Drawdowns: the p95 severity tail is more negative than the median; both ≤ 0.
    assert s.p95_max_drawdown <= s.median_max_drawdown <= 0.0
    assert math.isfinite(s.p95_max_drawdown)


def test_all_positive_returns():
    rep = build_robustness_report(
        np.full(120, 0.002), config=_cfg(), periods_per_year=252
    )
    s = rep.summary
    assert s is not None
    assert s.probability_of_loss == 0.0
    assert s.median_final_return > 0
    assert s.median_max_drawdown == 0.0
    assert rep.grade in ("A", "B", "C", "D", "F")


def test_all_negative_returns():
    rep = build_robustness_report(
        np.full(120, -0.002), config=_cfg(), periods_per_year=252
    )
    s = rep.summary
    assert s is not None
    assert s.probability_of_loss == 1.0
    assert s.median_final_return < 0
    assert rep.grade == "F"


def test_flat_returns_no_nan():
    rep = build_robustness_report(np.zeros(120), config=_cfg(), periods_per_year=252)
    s = rep.summary
    assert s is not None
    for v in (
        s.median_final_return, s.p05_final_return, s.p95_final_return,
        s.probability_of_loss, s.median_max_drawdown, s.p95_max_drawdown,
        s.median_sharpe, s.p05_sharpe, s.p95_sharpe,
    ):
        assert math.isfinite(v)
    assert s.median_sharpe == 0.0


def test_insufficient_data_warns_no_crash():
    rep = build_robustness_report(_returns(10), config=_cfg(), periods_per_year=252)
    assert rep.summary is None
    assert rep.grade is None
    assert any("Analysis skipped" in w for w in rep.warnings)


def test_block_bootstrap_output_length_matches_input():
    r = _returns(101)  # not divisible by block_size → truncation path
    sims = bootstrap_returns(r, n_simulations=8, block_size=5, seed=1)
    assert sims.shape == (8, 101)
    # Every simulated value comes from the original sample.
    assert np.isin(sims, r).all()


def test_block_size_larger_than_sample_is_clamped():
    r = _returns(40)
    rep = build_robustness_report(
        r, config=_cfg(block_size=60), periods_per_year=252
    )
    assert rep.summary is not None
    assert any("clamped" in w for w in rep.warnings)


def test_grade_values_and_f_for_negative_median():
    s = RobustnessSummary(
        median_final_return=-0.05, p05_final_return=-0.3, p95_final_return=0.2,
        probability_of_loss=0.55, median_max_drawdown=-0.2, p95_max_drawdown=-0.4,
        median_sharpe=0.1, p05_sharpe=-0.5, p95_sharpe=0.8,
    )
    assert compute_robustness_grade(s) == "F"
    a = RobustnessSummary(
        median_final_return=0.3, p05_final_return=0.05, p95_final_return=0.6,
        probability_of_loss=0.05, median_max_drawdown=-0.1, p95_max_drawdown=-0.2,
        median_sharpe=1.3, p05_sharpe=0.4, p95_sharpe=2.0,
    )
    assert compute_robustness_grade(a) == "A"


def test_benchmark_outperform_probability():
    rep = build_robustness_report(
        _returns(), config=_cfg(), periods_per_year=252, benchmark_total_return=0.0
    )
    p = rep.summary.probability_of_outperforming_benchmark
    assert p is not None and 0.0 <= p <= 1.0
    rep_none = build_robustness_report(_returns(), config=_cfg(), periods_per_year=252)
    assert rep_none.summary.probability_of_outperforming_benchmark is None


def test_deflated_sharpe_is_null_v1():
    rep = build_robustness_report(_returns(), config=_cfg(), periods_per_year=252)
    assert rep.deflated_sharpe is None


def test_histogram_counts_sum_to_simulations():
    rep = build_robustness_report(
        _returns(), config=_cfg(n_simulations=300), periods_per_year=252
    )
    assert sum(b.count for b in rep.final_return_histogram) == 300
    lowers = [b.lower for b in rep.final_return_histogram]
    assert lowers == sorted(lowers)


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


def test_api_disabled_preserves_normal_response(client):
    a = client.post("/backtest/sma-crossover", json={}).json()
    b = client.post(
        "/backtest/sma-crossover", json={"robustness": {"enabled": False}}
    ).json()
    assert a["robustness"] is None and b["robustness"] is None
    assert a["equity_curve"] == b["equity_curve"]
    assert a["strategy_metrics"] == b["strategy_metrics"]
    # Core config hash unaffected by the robustness request.
    assert (
        a["reproducibility"]["config_hash_full"]
        == b["reproducibility"]["config_hash_full"]
    )


def test_api_enabled_returns_block_and_core_results_unchanged(client):
    plain = client.post("/backtest/sma-crossover", json={}).json()
    body = client.post(
        "/backtest/sma-crossover",
        json={"robustness": {"enabled": True, "n_simulations": 300, "seed": 42}},
    ).json()
    rob = body["robustness"]
    assert rob["enabled"] is True
    assert rob["method"] == "block_bootstrap_returns"
    assert rob["n_simulations"] == 300 and rob["seed"] == 42
    assert rob["summary"]["probability_of_loss"] >= 0.0
    assert rob["grade"] in ("A", "B", "C", "D", "F", None)
    assert len(rob["final_return_histogram"]) > 0
    # Core results identical with/without robustness.
    assert body["equity_curve"] == plain["equity_curve"]
    assert body["strategy_metrics"] == plain["strategy_metrics"]
    assert (
        body["reproducibility"]["config_hash_full"]
        == plain["reproducibility"]["config_hash_full"]
    )


def test_api_same_seed_deterministic_different_seed_differs(client):
    req = {"robustness": {"enabled": True, "n_simulations": 300, "seed": 42}}
    a = client.post("/backtest/sma-crossover", json=req).json()
    b = client.post("/backtest/sma-crossover", json=req).json()
    assert a["robustness"]["summary"] == b["robustness"]["summary"]
    c = client.post(
        "/backtest/sma-crossover",
        json={"robustness": {"enabled": True, "n_simulations": 300, "seed": 7}},
    ).json()
    assert c["robustness"]["summary"] != a["robustness"]["summary"]


def test_api_benchmark_outperform_present_with_default_benchmark(client):
    body = client.post(
        "/backtest/sma-crossover",
        json={"robustness": {"enabled": True, "n_simulations": 200}},
    ).json()
    p = body["robustness"]["summary"]["probability_of_outperforming_benchmark"]
    assert p is not None and 0.0 <= p <= 1.0
    none_bench = client.post(
        "/backtest/sma-crossover",
        json={
            "robustness": {"enabled": True, "n_simulations": 200},
            "benchmark": {"mode": "none"},
        },
    ).json()
    assert (
        none_bench["robustness"]["summary"]["probability_of_outperforming_benchmark"]
        is None
    )


def test_api_invalid_robustness_config_rejected(client):
    resp = client.post(
        "/backtest/sma-crossover",
        json={"robustness": {"enabled": True, "n_simulations": 5}},
    )
    assert resp.status_code == 422
