"""Independent tiny matrices, actual keyed inputs and final portfolio constraints."""
from copy import deepcopy

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from app.scanner.advanced import advanced_weights, keyed_panel, neutralise
from app.scanner.cross_sectional import run_scanner_backtest
from app.scanner.pnl import portfolio_pnl
from app.scanner.policies import NeutralisationPolicy, ScannerInputs
from app.scanner.signals import momentum_score

pytestmark = [pytest.mark.db_free, pytest.mark.usefixtures("isolated_lab_db")]


def universe(n=12, days=14):
    dates = pd.bdate_range("2025-01-01", periods=days)
    returns = np.zeros((days, n))
    for t in range(1, days):
        returns[t] = [0.002 * ((i + t) % 5 - 2) + 0.0005 * t for i in range(n)]
    prices = 100 * np.cumprod(1 + returns, axis=0)
    return {"prices": prices, "returns": returns, "date_index": dates, "dates": dates.strftime("%Y-%m-%d").tolist(),
            "tickers": [f"A{i}" for i in range(n)], "sectors": ["X" if i < n // 2 else "Y" for i in range(n)],
            "liquidity": np.ones(n)}


def compute(uni, policy, inputs=None):
    panel = keyed_panel(uni, momentum_score(uni["prices"], 1), inputs)
    return advanced_weights(panel, set(range(1, len(uni["dates"]) - 1)), policy,
                            long_quantile=0.4, short_quantile=0.4, gross=1, min_liquidity=0)


def test_perfect_sector_is_zero_not_alpha():
    row = np.array([1., 1., 1., -2., -2., -2.])
    w, residual, report, status, _ = neutralise(row, np.ones(6, bool), ["X"] * 3 + ["Y"] * 3,
        np.full(6, np.nan), NeutralisationPolicy(mode="sector"), 0.4, 0.4, 1)
    assert status == "no_signal"
    assert np.array_equal(w, np.zeros(6))
    assert np.max(np.abs(residual)) < 1e-12
    assert report["rank"] == 2


def test_known_sector_weights_and_reconstruction():
    row = np.array([3., -3., 1., -1.])
    w, _, report, status, _ = neutralise(row, np.ones(4, bool), ["X", "X", "Y", "Y"],
        np.full(4, np.nan), NeutralisationPolicy(mode="sector"), 0.49, 0.49, 1)
    assert status == "ok"
    np.testing.assert_allclose(w, [0.25, -0.25, 0.25, -0.25], atol=1e-12)
    assert abs(w[:2].sum()) < 1e-12 and abs(w[2:].sum()) < 1e-12
    assert report["reconstruction_error"] < 1e-12


def test_beta_cancels_and_selected_support_can_be_infeasible():
    row, beta = np.array([3., 1., -1., -3.]), np.array([-1., 1., -1., 1.])
    policy = NeutralisationPolicy(mode="beta")
    w, _, _, status, _ = neutralise(row, np.ones(4, bool), ["X"] * 4, beta, policy, 0.49, 0.49, 1)
    assert status == "ok"
    np.testing.assert_allclose(w, [.25, .25, -.25, -.25], atol=1e-12)
    assert abs(w @ beta) < 1e-12
    w, _, _, status, _ = neutralise(row, np.ones(4, bool), ["X"] * 4, beta, policy, 0.2, 0.2, 1)
    assert status == "infeasible" and not w.any()


def test_rank_failure_is_cash_not_ridge():
    w, _, _, status, _ = neutralise(np.array([3., 2., -1., -2.]), np.ones(4, bool), ["X"] * 4,
        np.ones(4), NeutralisationPolicy(mode="beta"), 0.4, 0.4, 1)
    assert status == "rank_failure" and not w.any()


def test_nearly_constant_beta_cannot_amplify_regression_noise():
    w, _, report, status, _ = neutralise(np.array([1., 2., 3., 4.]), np.ones(4, bool), ["X"] * 4,
        1 + np.arange(4) * 1e-10, NeutralisationPolicy(mode="beta"), .49, .49, 1)
    assert status == "rank_failure" and not w.any()
    assert report["condition_number"] > 1e8


def test_full_rank_selected_support_refuses_even_when_selected_betas_nearly_match():
    epsilon = 1e-10
    # Full cross-section is well-conditioned; its two selected names are not.
    scores = np.array([3., -3 * epsilon, 3 * epsilon, -3.])
    beta = np.array([1., 4., 5., 1. + epsilon])
    w, _, report, status, reason = neutralise(scores, np.ones(4, bool), ["X"] * 4, beta,
        NeutralisationPolicy(mode="beta"), .2, .2, 1)
    assert report["condition_number"] < 1e8 and report["support_rank"] == 2
    assert status == "infeasible" and not w.any()
    assert reason == "selected support has no nonzero constraint nullspace"


def test_keyed_rows_reordered_and_missing_not_zero():
    uni = universe()
    rows = [{"asset_id": a, "period": d, "available_at": d + "T00:00:00Z", "sector": s,
             "eligible": True, "liquidity": 1.0} for d in uni["dates"] for a, s in zip(uni["tickers"], uni["sectors"])]
    a = compute(uni, {"mode": "sector"}, {"exposures": rows})
    b = compute(uni, {"mode": "sector"}, {"exposures": list(reversed(rows))})
    np.testing.assert_array_equal(a["weights"], b["weights"])
    rows[12]["sector"] = None
    excluded = compute(uni, {"mode": "sector"}, {"exposures": rows})
    assert {"asset_id": "A0", "reason": "unknown_sector"} in excluded["diagnostics"][0]["excluded"]
    refused = compute(uni, {"mode": "sector", "missing": "refuse"}, {"exposures": rows})
    assert refused["diagnostics"][0]["status"] == "missing_input"
    assert not refused["weights"][1].any()
    with pytest.raises(ValueError, match="duplicate"):
        compute(uni, {"mode": "sector"}, {"exposures": rows + [rows[0]]})


def test_late_observation_excluded_and_cash_fallback_turns_over():
    uni = universe()
    rows = [{"asset_id": a, "period": d, "available_at": d + "T00:00:00Z", "eligible": True,
             "sector": s, "liquidity": 1.0} for d in uni["dates"] for a, s in zip(uni["tickers"], uni["sectors"])]
    for row in rows:
        if row["period"] == uni["dates"][2]:
            row["available_at"] = "2026-01-01T00:00:00Z"
    run = compute(uni, {"mode": "dollar", "missing": "refuse"}, {"exposures": rows})
    assert np.abs(run["weights"][1]).sum() == pytest.approx(1)
    assert not run["weights"][2].any()
    pnl = portfolio_pnl(run["weights"], uni["returns"], 10)
    assert pnl["turnover"][2] == pytest.approx(1)
    assert pnl["net"][3] == pytest.approx(-0.001)


def test_volatility_cap_and_insufficient_history_are_explicit():
    run = compute(universe(), {"mode": "dollar", "gross_cap": 0.2,
                  "volatility": {"target": 1.0, "window": 5, "min_observations": 3}})
    assert run["diagnostics"][0]["status"] == "volatility_unavailable"
    valid = [r for r in run["diagnostics"] if r["status"] == "ok"]
    assert valid and all(r["cap_binding"] for r in valid)
    assert all(r["final"]["gross"] <= 0.2 + 1e-12 and abs(r["final"]["net"]) < 1e-12 for r in valid)
    assert all(r["achieved_ex_ante"] < 1.0 for r in valid)


def test_zero_variance_never_creates_infinite_scale():
    uni = universe()
    uni["returns"][1:] = np.linspace(-.01, .01, 12)
    uni["prices"] = 100 * np.cumprod(1 + uni["returns"], axis=0)
    run = compute(uni, {"mode": "dollar", "volatility": {"target": .2, "window": 5, "min_observations": 3}})
    assert any(r["reason"] == "zero or unknown fixed-weight variance" for r in run["diagnostics"])
    assert not run["weights"].any()


def test_supplied_beta_and_future_factor_availability():
    uni = universe()
    rows = [{"asset_id": a, "period": d, "available_at": d + "T00:00:00Z", "eligible": True,
             "liquidity": 1.0, "beta": float(j % 3)} for d in uni["dates"] for j, a in enumerate(uni["tickers"])]
    supplied = compute(uni, {"mode": "beta"}, {"exposures": rows})
    assert supplied["used"]
    beta = np.array([float(j % 3) for j in range(12)])
    assert max(abs(w @ beta) for w in supplied["weights"]) < 1e-9
    factors = [{"period": d, "available_at": "2026-01-01T00:00:00Z", "value": float(j % 3) / 100} for j, d in enumerate(uni["dates"])]
    late = compute(uni, {"mode": "beta", "beta_window": 5, "beta_min_observations": 5}, {"factor_returns": factors})
    assert not late["weights"].any()
    with pytest.raises(ValueError, match="factor"):
        compute(uni, {"mode": "beta"}, {"factor_returns": factors + [factors[0]]})


@pytest.mark.parametrize("mode", ["dollar", "sector", "beta"])
def test_fixed_historical_panel_future_only_perturbation(mode):
    uni = universe(days=28)
    changed = deepcopy(uni)
    changed["prices"][18:] *= np.linspace(1.02, 1.08, 12)
    changed["returns"][18:] = changed["prices"][18:] / changed["prices"][17:-1] - 1
    policy = {"mode": mode, "beta_window": 8, "beta_min_observations": 5,
              "volatility": {"target": 0.15, "window": 8, "min_observations": 5}}
    a, b = compute(uni, policy), compute(changed, policy)
    np.testing.assert_array_equal(a["weights"][:18], b["weights"][:18])


def test_shared_pnl_alignment_cost_and_no_double_shift():
    weights = np.array([[0., 0.], [.5, -.5], [.25, -.25], [0., 0.]])
    returns = np.array([[0., 0.], [.9, -.9], [.04, .02], [.08, -.04]])
    pnl = portfolio_pnl(weights, returns, 10)
    np.testing.assert_allclose(pnl["gross"], [0, 0, .01, .03])
    np.testing.assert_allclose(pnl["turnover"], [0, 1, .5, .5])
    np.testing.assert_allclose(pnl["net"], [0, 0, .009, .0295])


@pytest.mark.parametrize("policy", [{"mode": "sector_beta"}, {"failed_rebalance": "carry"},
    {"gross_cap": True}, {"gross_cap": float("inf")}, {"beta_window": 2}, {"volatility": {"target": .2, "window": 5, "min_observations": 6}}])
def test_strict_policy_negatives(policy):
    with pytest.raises(ValidationError):
        NeutralisationPolicy.model_validate(policy)


def test_public_advanced_report_reconciles_full_precision(monkeypatch):
    uni = universe()
    monkeypatch.setattr("app.scanner.cross_sectional.generate_sample_universe", lambda *a: uni)
    result = run_scanner_backtest("cross_sectional_momentum", 12, "2025-01-01", "2025-02-01", 1,
        long_quantile=.4, short_quantile=.4, advanced_policy={"mode": "dollar"})
    internal = compute(uni, {"mode": "dollar"})
    pnl = portfolio_pnl(internal["weights"], uni["returns"], 5)
    for row in result["advanced"]["diagnostics"]:
        t = uni["dates"].index(row["date"])
        assert row["net_return"] == pnl["net"][t + 1]
        assert row["cost"] == pnl["cost"][t]
    legacy = run_scanner_backtest("cross_sectional_momentum", 12, "2025-01-01", "2025-02-01", 1)
    assert "advanced" not in legacy
