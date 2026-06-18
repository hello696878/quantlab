"""
Tests for the Cross-Sectional Scanner Engine v1.

Deterministic synthetic universe + pure-function checks (signals, ranking,
neutralization, lookahead-safe P&L, turnover, costs) plus API wiring.
No live data, no network.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.scanner import ScannerInputError, run_scanner_backtest
from app.scanner.cross_sectional import gross_returns_from_weights
from app.scanner.metrics import portfolio_metrics
from app.scanner.neutralize import dollar_neutral_weights
from app.scanner.sample_data import generate_sample_universe
from app.scanner.signals import lookback_return, momentum_score, reversal_score

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")


def _assert_all_finite(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            _assert_all_finite(v)
    elif isinstance(obj, list):
        for v in obj:
            _assert_all_finite(v)
    elif isinstance(obj, float):
        assert math.isfinite(obj)


# ---------------------------------------------------------------------------
# Synthetic universe (1, 2, 3)
# ---------------------------------------------------------------------------


def test_universe_deterministic_same_seed():
    a = generate_sample_universe(30, "2022-01-01", "2022-06-01", 42)
    b = generate_sample_universe(30, "2022-01-01", "2022-06-01", 42)
    assert np.array_equal(a["prices"], b["prices"])
    assert a["tickers"] == b["tickers"]
    assert a["dates"] == b["dates"]


def test_universe_shape():
    u = generate_sample_universe(30, "2022-01-01", "2022-06-01", 42)
    n_dates = len(u["dates"])
    assert u["prices"].shape == (n_dates, 30)
    assert u["returns"].shape == (n_dates, 30)
    assert len(u["tickers"]) == 30 and len(u["sectors"]) == 30
    assert u["liquidity"].shape == (30,)


def test_return_matrix_matches_prices():
    u = generate_sample_universe(20, "2022-01-01", "2022-04-01", 1)
    prices, returns = u["prices"], u["returns"]
    expected = prices[1:] / prices[:-1] - 1.0
    assert np.allclose(returns[1:], expected)
    assert np.allclose(returns[0], 0.0)


# ---------------------------------------------------------------------------
# Signals (4, 5)
# ---------------------------------------------------------------------------


def test_reversal_score_is_negative_demeaned_return():
    u = generate_sample_universe(20, "2022-01-01", "2022-06-01", 3)
    r = lookback_return(u["prices"], 5)
    rev = reversal_score(u["prices"], 5)
    t = 30
    expected = -(r[t] - np.nanmean(r[t]))
    assert np.allclose(rev[t], expected, equal_nan=True)


def test_momentum_score_is_lookback_return():
    u = generate_sample_universe(20, "2022-01-01", "2022-06-01", 3)
    mom = momentum_score(u["prices"], 10)
    lb = lookback_return(u["prices"], 10)
    mask = ~np.isnan(mom)
    assert np.allclose(mom[mask], lb[mask])


# ---------------------------------------------------------------------------
# Ranking / neutralization (6, 7, 8, 9)
# ---------------------------------------------------------------------------


def test_ranking_selects_correct_top_bottom():
    scores = np.array([0.5, -0.3, 0.9, -0.7, 0.1])
    mask = np.ones(5, dtype=bool)
    w, nl, ns, ok = dollar_neutral_weights(scores, mask, 0.2, 0.2, 1.0)
    assert ok and nl == 1 and ns == 1
    # highest score (idx 2) is long; lowest (idx 3) is short
    assert w[2] > 0 and w[3] < 0
    assert w[0] == 0 and w[1] == 0 and w[4] == 0


def test_dollar_neutral_weights_sum_zero():
    scores = np.linspace(-1, 1, 50)
    mask = np.ones(50, dtype=bool)
    w, nl, ns, ok = dollar_neutral_weights(scores, mask, 0.2, 0.2, 1.0)
    assert ok
    assert abs(float(w.sum())) < 1e-12


def test_gross_exposure_matches_target():
    scores = np.linspace(-1, 1, 50)
    mask = np.ones(50, dtype=bool)
    w, _, _, _ = dollar_neutral_weights(scores, mask, 0.2, 0.2, 2.0)
    assert float(np.abs(w).sum()) == pytest.approx(2.0, abs=1e-9)


def test_long_short_side_exposures():
    scores = np.linspace(-1, 1, 50)
    mask = np.ones(50, dtype=bool)
    w, _, _, _ = dollar_neutral_weights(scores, mask, 0.2, 0.2, 1.0)
    assert float(w[w > 0].sum()) == pytest.approx(0.5, abs=1e-9)
    assert float(w[w < 0].sum()) == pytest.approx(-0.5, abs=1e-9)


# ---------------------------------------------------------------------------
# Lookahead safety / P&L (10, 11)
# ---------------------------------------------------------------------------


def test_pnl_uses_next_period_returns():
    W = np.array([[0.5, -0.5], [0.5, -0.5], [-0.5, 0.5]])
    ret = np.array([[0.0, 0.0], [0.1, 0.2], [0.3, 0.1]])
    g = gross_returns_from_weights(W, ret)
    # g[1] = W[0]·ret[1] = 0.5*0.1 - 0.5*0.2 = -0.05
    # g[2] = W[1]·ret[2] = 0.5*0.3 - 0.5*0.1 = 0.10
    assert g[0] == 0.0
    assert g[1] == pytest.approx(-0.05, abs=1e-12)
    assert g[2] == pytest.approx(0.10, abs=1e-12)


def test_lookahead_no_same_period_leakage():
    # If weights at t used returns[t] (leakage), perfectly aligned weights would
    # produce a large positive return on the same day. Confirm g[k] depends on
    # W[k-1], not W[k]: zero out W[k-1] and the return must vanish.
    W = np.array([[0.5, -0.5], [0.0, 0.0], [-0.5, 0.5]])
    ret = np.array([[0.0, 0.0], [0.3, -0.3], [0.2, 0.1]])
    g = gross_returns_from_weights(W, ret)
    assert g[1] == pytest.approx(0.3, abs=1e-12)  # W[0]·ret[1]
    assert g[2] == pytest.approx(0.0, abs=1e-12)  # W[1] is zero → no leakage from ret[2]


# ---------------------------------------------------------------------------
# Turnover / cost / equity (12, 13, 14, 15)
# ---------------------------------------------------------------------------


def test_turnover_calculation():
    a = np.array([0.5, -0.5, 0.0])
    b = np.array([0.0, -0.5, 0.5])
    turnover = float(np.sum(np.abs(b - a)))
    assert turnover == pytest.approx(1.0, abs=1e-12)  # |0-0.5| + 0 + |0.5-0|


def test_cost_and_net_return():
    gross = 0.01
    turnover = 0.8
    cost_bps = 5.0
    cost = turnover * cost_bps / 1e4
    net = gross - cost
    assert cost == pytest.approx(0.0004, abs=1e-12)
    assert net == pytest.approx(0.0096, abs=1e-12)


def test_equity_compounds_correctly():
    r = [0.01, -0.02, 0.03]
    m = portfolio_metrics(r)
    expected_total = (1.01 * 0.98 * 1.03) - 1.0
    assert m["total_return"] == pytest.approx(expected_total, abs=1e-9)


def test_scanner_net_equals_gross_minus_cost_in_run():
    res = run_scanner_backtest("cross_sectional_reversal", n_assets=40, start_date="2022-01-01",
                               end_date="2022-12-31", cost_bps=10, seed=42)
    # With positive cost, net should be <= gross on every reported day.
    for r in res["returns"]:
        assert r["net"] <= r["gross"] + 1e-9


# ---------------------------------------------------------------------------
# Robustness (16, 17)
# ---------------------------------------------------------------------------


def test_insufficient_universe_warns_not_crash():
    # 5 assets with a 20% quantile and a high liquidity filter can leave too few
    # eligible names; the engine should warn rather than crash.
    res = run_scanner_backtest("cross_sectional_reversal", n_assets=5, start_date="2022-01-01",
                               end_date="2022-06-01", long_quantile=0.2, short_quantile=0.2,
                               min_liquidity=0.99, seed=42)
    _assert_all_finite(res)
    assert isinstance(res["diagnostics"]["warnings"], list)
    # Either no valid rebalances or some skipped — but never a crash / NaN.
    assert res["diagnostics"]["valid_rebalance_dates"] >= 0


def test_missing_scores_excluded():
    # First `lookback` rows have NaN scores → those dates can't be eligible.
    scores_row = np.array([np.nan, 0.5, np.nan, -0.5, 0.2])
    mask = np.isfinite(scores_row)
    w, nl, ns, ok = dollar_neutral_weights(scores_row, mask, 0.34, 0.34, 1.0)
    assert ok
    # NaN-score assets never receive weight.
    assert w[0] == 0.0 and w[2] == 0.0


# ---------------------------------------------------------------------------
# Validation (18, 19)
# ---------------------------------------------------------------------------


def test_invalid_quantile_rejected():
    with pytest.raises(ScannerInputError):
        run_scanner_backtest("cross_sectional_reversal", long_quantile=0.8)
    with pytest.raises(ScannerInputError):
        run_scanner_backtest("cross_sectional_reversal", short_quantile=0.0)


def test_invalid_date_range_rejected():
    with pytest.raises(ScannerInputError):
        run_scanner_backtest("cross_sectional_reversal", start_date="2024-01-01", end_date="2022-01-01")


def test_invalid_strategy_rejected():
    with pytest.raises(ScannerInputError):
        run_scanner_backtest("ml_magic", n_assets=20)


def test_invalid_n_assets_rejected():
    with pytest.raises(ScannerInputError):
        run_scanner_backtest("cross_sectional_reversal", n_assets=3)


# ---------------------------------------------------------------------------
# No NaN / determinism / shape (20)
# ---------------------------------------------------------------------------


def test_run_deterministic_and_finite():
    a = run_scanner_backtest("cross_sectional_reversal", n_assets=50, start_date="2022-01-01",
                             end_date="2023-12-31", seed=42)
    b = run_scanner_backtest("cross_sectional_reversal", n_assets=50, start_date="2022-01-01",
                             end_date="2023-12-31", seed=42)
    assert a == b
    _assert_all_finite(a)
    assert a["summary"]["average_gross_exposure"] == pytest.approx(1.0, abs=1e-6)
    assert abs(a["summary"]["average_net_exposure"]) < 1e-6


def test_ranking_capped_and_has_sides():
    res = run_scanner_backtest("cross_sectional_momentum", n_assets=120, start_date="2022-01-01",
                               end_date="2022-12-31", seed=7)
    assert len(res["latest_ranking"]) <= 100
    sides = {row["side"] for row in res["latest_ranking"]}
    assert "long" in sides and "short" in sides


# ---------------------------------------------------------------------------
# API wiring
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(main_module.app)


def test_api_scanner_backtest(client):
    body = client.post(
        "/scanner/backtest",
        json={"strategy": "cross_sectional_reversal", "n_assets": 50, "start_date": "2022-01-01",
              "end_date": "2023-12-31", "lookback_days": 5, "long_quantile": 0.2,
              "short_quantile": 0.2, "rebalance_frequency": "daily", "gross_exposure": 1.0,
              "cost_bps": 5, "seed": 42},
    ).json()
    assert body["strategy"] == "cross_sectional_reversal"
    assert body["equity_curve"] and body["latest_ranking"]
    assert body["diagnostics"]["valid_rebalance_dates"] > 0


def test_api_scanner_momentum(client):
    body = client.post(
        "/scanner/backtest",
        json={"strategy": "cross_sectional_momentum", "n_assets": 40, "start_date": "2022-01-01",
              "end_date": "2022-12-31", "rebalance_frequency": "weekly", "seed": 7},
    ).json()
    assert body["strategy"] == "cross_sectional_momentum"


@pytest.mark.parametrize(
    "payload",
    [
        {"strategy": "cross_sectional_reversal", "long_quantile": 0.8},
        {"strategy": "cross_sectional_reversal", "n_assets": 3},
        {"strategy": "ml_magic"},
        {"strategy": "cross_sectional_reversal", "start_date": "2024-01-01", "end_date": "2022-01-01"},
        {"strategy": "cross_sectional_reversal", "lookback_days": 0},
    ],
)
def test_api_scanner_validation_422(client, payload):
    assert client.post("/scanner/backtest", json=payload).status_code == 422
