"""Independent Phase 68 timing, portfolio and pre-68 legacy expectations."""
from copy import deepcopy
import math

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from app.scanner.advanced import _inputs_at, advanced_weights, keyed_panel, neutralise
from app.scanner.cross_sectional import ScannerInputError, run_scanner_backtest
from app.scanner.metrics import portfolio_metrics
from app.scanner.policies import ExposureObservation, FactorObservation, NeutralisationPolicy

pytestmark = [pytest.mark.db_free, pytest.mark.usefixtures("isolated_lab_db")]


def _panel(returns, start="2025-01-23"):
    returns = np.asarray(returns, dtype=float)
    days, assets = returns.shape
    index = pd.bdate_range(start, periods=days)
    return {"returns": returns, "prices": 100 * np.cumprod(1 + returns, axis=0),
            "dates": index.strftime("%Y-%m-%d").tolist(), "date_index": index,
            "tickers": [f"A{i}" for i in range(assets)],
            "sectors": ["Generated"] * assets, "liquidity": np.ones(assets)}


@pytest.mark.parametrize("strategy,side", [("cross_sectional_momentum", 1),
                                           ("cross_sectional_reversal", -1)])
@pytest.mark.parametrize("frequency", ["daily", "weekly", "monthly"])
@pytest.mark.parametrize("cost_bps", [0, 10])
def test_legacy_engine_matches_independent_pre68_path(monkeypatch, strategy, side, frequency, cost_bps):
    # This fixed panel distinguishes daily, first-week and first-month decisions.
    # Equal-score days 2/5/8 must carry the old legacy basket without new costs.
    tilts = [0, 1, 0, -1, 1, 0, -1, -1, 0, 1]
    vector = np.array([.125, .0625, .03125, -.03125, -.0625, -.125])
    uni = _panel(np.asarray(tilts)[:, None] * vector)
    monkeypatch.setattr("app.scanner.cross_sectional.generate_sample_universe", lambda *args: uni)
    result = run_scanner_backtest(strategy, 6, uni["dates"][0], uni["dates"][-1], 1,
                                 .4, .4, frequency, 1, cost_bps)

    if frequency == "daily":
        held = [0, 1, 1, -1, 1, 1, -1, -1, -1, -1]
        successful, skipped = [1, 3, 4, 6, 7], 3
    else:
        held = [0, 1, 1, 1, 1, 1, 1, -1, -1, -1]
        successful, skipped = [1, 7], 1 if frequency == "weekly" else 0
    # Equal weights +/-1/4 on the two extremes give 3/32 per unit tilt.
    gross = [side * held[t - 1] * tilts[t] * (3 / 32) for t in range(1, 10)]
    turnover = [abs(held[t] - (held[t - 1] if t else 0)) for t in range(10)]
    net = [gross[t - 1] - turnover[t - 1] * cost_bps / 10000 for t in range(1, 10)]
    equity, drawdown = [], []
    wealth, peak = 1.0, 1.0
    for value in net:
        wealth *= 1 + value
        peak = max(peak, wealth)
        equity.append(round(wealth, 6))
        drawdown.append(round(wealth / peak - 1, 6))

    assert "advanced" not in result
    assert [row["gross"] for row in result["returns"]] == [round(v, 6) for v in gross]
    assert [row["net"] for row in result["returns"]] == [round(v, 6) for v in net]
    assert [row["equity"] for row in result["equity_curve"]] == equity
    assert [row["drawdown"] for row in result["equity_curve"]] == drawdown
    assert [row["turnover"] for row in result["turnover"]] == turnover[:-1]
    assert [row["gross"] for row in result["exposures"]] == list(map(abs, held[:-1]))
    assert result["summary"]["total_return"] == round(wealth - 1, 6)
    assert result["summary"]["max_drawdown"] == min(drawdown)
    assert result["summary"]["average_turnover"] == round(sum(turnover[t] for t in successful) / len(successful), 6)
    assert result["diagnostics"]["valid_rebalance_dates"] == len(successful)
    assert result["diagnostics"]["skipped_dates"] == skipped
    assert result["latest_rebalance_date"] == uni["dates"][7]
    by_asset = {row["ticker"]: row["weight"] for row in result["latest_ranking"]}
    assert by_asset == dict(zip(uni["tickers"], [-side * .25, -side * .25, 0, 0, side * .25, side * .25]))
    if skipped:
        assert any("previous basket was carried forward" in warning for warning in result["diagnostics"]["warnings"])


@pytest.mark.parametrize("change", [
    {"strategy": "unknown"}, {"n_assets": True}, {"lookback_days": 0},
    {"long_quantile": .5}, {"cost_bps": -1}, {"seed": True},
    {"start_date": "2025-02-01", "end_date": "2025-01-01"},
], ids=["strategy", "asset-type", "lookback", "quantile", "cost", "seed", "dates"])
def test_legacy_invalid_requests_still_fail_before_generation(monkeypatch, change):
    def forbidden(*args):
        raise AssertionError("invalid legacy request reached generation")
    monkeypatch.setattr("app.scanner.cross_sectional.generate_sample_universe", forbidden)
    request = {"strategy": "cross_sectional_momentum", **change}
    with pytest.raises(ScannerInputError):
        run_scanner_backtest(**request)


def test_preexisting_metric_peak_convention_is_not_silently_rewritten():
    # This direct legacy helper omits initial capital from its running peak.
    # Public scanner paths include an initial zero-return warmup, anchoring 1.
    assert portfolio_metrics([-.1, 0])["max_drawdown"] == 0
    assert portfolio_metrics([0, -.1, 0])["max_drawdown"] == pytest.approx(-.1)


@pytest.mark.parametrize("kind", ["exposure", "factor"])
@pytest.mark.parametrize("available_at", [
    "0001-01-01T00:00:00+01:00", "9999-12-31T23:59:59-01:00",
    "2025-01-24T00:00:00.0000001Z", "2025-01-24T00:00:00,1234567+00:00",
], ids=["utc-underflow", "utc-overflow", "sub-microsecond", "comma-precision"])
def test_declaration_times_refuse_overflow_and_silent_precision_loss(kind, available_at):
    value = {"period": "2025-01-24", "available_at": available_at}
    model = FactorObservation if kind == "factor" else ExposureObservation
    value.update({"value": .01} if kind == "factor" else
                 {"asset_id": "A0", "eligible": True, "liquidity": 1.0, "sector": "X"})
    with pytest.raises(ValidationError):
        model.model_validate(value)


def test_offset_equivalence_preserves_microseconds_and_cutoff_exclusion():
    common = {"period": "2025-01-24", "asset_id": "A0", "eligible": True, "liquidity": 1.0}
    utc = ExposureObservation(**common, available_at="2025-01-24T00:00:00.000001Z")
    offset = ExposureObservation(**common, available_at="2025-01-23T19:00:00.000001-05:00")
    assert utc == offset
    assert utc.available_at == "2025-01-24T00:00:00.000001+00:00"
    uni = _panel([[0] * 6, [.03, .02, .01, -.01, -.02, -.03], [0] * 6])
    rows = [{**common, "asset_id": asset, "available_at": "2025-01-24T00:00:00Z"} for asset in uni["tickers"]]
    rows[0] = utc.model_dump(mode="json")
    panel = keyed_panel(uni, np.tile(np.arange(6.), (3, 1)), {"exposures": rows})
    _, _, eligible, exclusions = _inputs_at(panel, 1, NeutralisationPolicy(mode="dollar"), 0)
    assert eligible.tolist() == [False, True, True, True, True, True]
    assert exclusions == [{"asset_id": "A0", "reason": "not_available_at_cutoff"}]


@pytest.mark.parametrize("gross_cap", [2.0, .2], ids=["target", "capped"])
def test_volatility_uses_exact_trailing_sample_and_preserves_final_neutrality(gross_cap):
    observations = [0, .02, .04, .06, .9]
    uni = _panel([[-v, -v, 0, 0, v, v] for v in observations])
    scores = np.tile([-3., -2., -1., 1., 2., 3.], (5, 1))
    result = advanced_weights(keyed_panel(uni, scores), {1, 2, 3},
        {"mode": "dollar", "gross_cap": gross_cap,
         "volatility": {"target": .1, "window": 3, "min_observations": 3}},
        long_quantile=.34, short_quantile=.34, gross=1, min_liquidity=0)
    # Fixed unscaled book earns [.02,.04,.06], whose sample SD is .02.
    estimate = .02 * math.sqrt(252)
    scale = min(.1 / estimate, gross_cap)
    diagnostic = result["diagnostics"][-1]
    assert [row["status"] for row in result["diagnostics"][:2]] == ["volatility_unavailable"] * 2
    assert not result["weights"][:3].any()
    assert diagnostic["status"] == "ok"
    assert diagnostic["volatility_estimate"] == pytest.approx(estimate)
    assert diagnostic["volatility_scale"] == pytest.approx(scale)
    assert diagnostic["achieved_ex_ante"] == pytest.approx(estimate * scale)
    assert diagnostic["cap_binding"] is (gross_cap == .2)
    np.testing.assert_allclose(result["weights"][3], np.array([-.25, -.25, 0, 0, .25, .25]) * scale, atol=1e-12)
    assert abs(diagnostic["final"]["net"]) < 1e-12
    assert diagnostic["final"]["gross"] == pytest.approx(scale)


def test_trailing_beta_has_exact_minimum_window_and_never_reads_future():
    factor = np.array([0, -.02, 0, .02, .04, .06, .5])
    expected_beta = np.array([-1., 0., .5, 1., 2., 3.])
    returns = factor[:, None] * expected_beta + .001
    returns[0] = 0
    # Keep the future shock within positive-price scope.
    uni = _panel(returns)
    declared = [{"period": day, "available_at": day + "T00:00:00Z", "value": float(value)}
                for day, value in zip(uni["dates"], factor)]
    scores = np.tile(np.arange(6.), (7, 1))
    policy = NeutralisationPolicy(mode="beta", beta_window=5, beta_min_observations=5)
    panel = keyed_panel(uni, scores, {"factor_returns": declared})
    assert not _inputs_at(panel, 4, policy, 0)[2].any()
    beta = _inputs_at(panel, 5, policy, 0)[1]
    np.testing.assert_allclose(beta, expected_beta, atol=1e-12)
    changed = deepcopy(uni)
    changed["returns"][6] = np.linspace(-.4, .8, 6)
    changed["prices"][6] = changed["prices"][5] * (1 + changed["returns"][6])
    later = keyed_panel(changed, scores, {"factor_returns": declared})
    np.testing.assert_array_equal(_inputs_at(later, 5, policy, 0)[1], beta)


def test_tiny_sector_residuals_are_not_amplified_to_full_gross():
    row = np.array([1., 1., 1., -2., -2., -2.]) + np.array([1, -1, 0, 1, -1, 0]) * 1e-14
    weights, _, _, status, _ = neutralise(row, np.ones(6, bool), ["X"] * 3 + ["Y"] * 3,
        np.full(6, np.nan), NeutralisationPolicy(mode="sector"), .34, .34, 2)
    assert status == "no_signal"
    assert not weights.any()


def test_latest_advanced_ranking_reports_cash_and_actual_missing_sectors(monkeypatch):
    uni = _panel([[0] * 6] + [[.03, .02, .01, -.01, -.02, -.03]] * 3)
    rows = [{"period": day, "asset_id": asset, "available_at": day + "T00:00:00Z",
             "sector": "Declared" if t == 1 else None, "eligible": t == 1, "liquidity": 1.0}
            for t, day in enumerate(uni["dates"]) for asset in uni["tickers"]]
    monkeypatch.setattr("app.scanner.cross_sectional.generate_sample_universe", lambda *args: uni)
    result = run_scanner_backtest("cross_sectional_momentum", 6, uni["dates"][0], uni["dates"][-1], 1,
        .34, .34, advanced_policy={"mode": "sector"}, advanced_inputs={"exposures": rows})
    assert result["diagnostics"]["valid_rebalance_dates"] == 1
    assert result["latest_rebalance_date"] == uni["dates"][2]
    assert result["latest_ranking"]
    assert all(row["weight"] == 0 and row["side"] == "neutral" and row["sector"] is None
               for row in result["latest_ranking"])
    assert result["advanced"]["diagnostics"][-1]["turnover"] == pytest.approx(1)


def test_advanced_refuses_compounded_wealth_underflow_without_changing_legacy(monkeypatch):
    vector = np.array([.01, .008, .003, -.003, -.008, -.01])
    returns = np.array([(-1) ** t * vector for t in range(600)])
    returns[0] = 0
    uni = _panel(returns)
    monkeypatch.setattr("app.scanner.cross_sectional.generate_sample_universe", lambda *args: uni)
    with pytest.raises(ScannerInputError, match="finite positive wealth"):
        run_scanner_backtest("cross_sectional_momentum", 6, uni["dates"][0], uni["dates"][-1], 1,
            .34, .34, gross_exposure=4, cost_bps=1000,
            advanced_policy={"mode": "dollar", "gross_cap": 4.0})
