"""
Portfolio Attribution Lab tests (Phase 58.0): observation validation and
weight timing, future-rebalance / future-return invariance, portfolio-return
reconstruction, asset and group contribution, benchmark validation and
active return, hand-computed Brinson allocation / selection / interaction /
residual, one-sided and zero-weight groups, single-period reconciliation,
arithmetic and Carino linking, time-weighted return, cost attribution and
gross-to-net reconciliation, tracking error / information ratio / active
drawdown, contribution concentration, regime and drawdown integration,
Model Validation linkage, fingerprints, migration, persistence, baselines,
compare/export, demo idempotence, prior-registry preservation and API paths.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")
db_module = pytest.importorskip("app.db")
obs_mod = pytest.importorskip("app.portfolio_attribution.observations")
bench_mod = pytest.importorskip("app.portfolio_attribution.benchmarks")
contrib_mod = pytest.importorskip("app.portfolio_attribution.contribution")
brinson_mod = pytest.importorskip("app.portfolio_attribution.brinson")
link_mod = pytest.importorskip("app.portfolio_attribution.linking")
risk_mod = pytest.importorskip("app.portfolio_attribution.activerisk")
cost_mod = pytest.importorskip("app.portfolio_attribution.costs")
fp_mod = pytest.importorskip("app.portfolio_attribution.fingerprints")
service = pytest.importorskip("app.portfolio_attribution.service")
pa_store = pytest.importorskip("app.portfolio_attribution.store")
pd_service = pytest.importorskip("app.portfolio_diagnostics.service")
pd_store = pytest.importorskip("app.portfolio_diagnostics.store")
reb_mod = pytest.importorskip("app.portfolio_diagnostics.rebalance")
demo_mod = pytest.importorskip("app.portfolio_attribution.demo")

BASE = "/portfolio-attribution"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_quantlab.db"
    monkeypatch.setattr(db_module, "_db_path_override", db_file)
    db_module.init_db()
    yield


@pytest.fixture
def client():
    return TestClient(main_module.app)


# ---------------------------------------------------------------------------
# Fixtures: a hand-computable four-asset book
# ---------------------------------------------------------------------------

N_OBS = demo_mod.N_OBS
FIRST = demo_mod.FIRST_PERIOD_INDEX
ASSETS = list(demo_mod.ASSETS)
CYCLE_A = demo_mod.CYCLE_A
CYCLE_B = demo_mod.CYCLE_B
EQUAL = demo_mod.EQUAL_WEIGHTS
BALANCED = demo_mod.BALANCED_WEIGHTS


def _stamps(n=N_OBS):
    return [(datetime(2024, 3, 1) + timedelta(days=i)).isoformat()
            for i in range(n)]


def _book(weights=None, **extra):
    """Create + execute a Phase 56 book restored to its targets every period."""
    payload = {
        "name": "attribution book", "method": "user_supplied",
        "frequency": "daily", "timestamps": _stamps(),
        "assets": [{"asset_id": a, "name": a, "asset_type": "index",
                    "group": demo_mod.GROUPS[a],
                    "returns": [CYCLE_A[a] if (t - FIRST) % 2 == 0
                                else CYCLE_B[a] for t in range(N_OBS)]}
                   for a in ASSETS],
        "estimation": {"mode": "rolling", "lookback": 3, "lag": 1},
        "rebalance": {"kind": "every_n", "every_n": 1,
                      "initial_turnover_policy": "zero_book"},
        "weights": weights or BALANCED,
        "weight_provenance": {"basis": "causal_rolling"},
        "normalization": "none",
    }
    payload.update(extra)
    run = pd_service.create_run(payload)
    return pd_service.execute_run(run["id"])


def _benchmark(weights=EQUAL, *, asset_ids=None, **extra):
    ids = asset_ids or ASSETS
    definition = {"benchmark_id": "equal-weight", "name": "Equal weight",
                  "kind": "fixed_weights", "source": "demo_fixture",
                  "asset_ids": ids,
                  "weights": (weights if isinstance(weights, list)
                              else [weights[a] for a in ids])}
    definition.update(extra)
    return definition


def _payload(prun_id, **extra):
    stamps = _stamps()
    payload = {"name": "attribution run", "portfolio_run_id": prun_id,
               "policy": {"return_frequency": "daily"},
               "benchmark": _benchmark(),
               "observation_start": stamps[FIRST],
               "observation_end": stamps[N_OBS - 1]}
    payload.update(extra)
    return payload


# ---------------------------------------------------------------------------
# Policy, observations, weight timing
# ---------------------------------------------------------------------------


def test_policy_validation():
    policy = obs_mod.validate_policy({"return_frequency": "monthly"})
    assert policy["return_convention"] == "simple"
    assert policy["weight_timing_policy"] == "beginning_of_period"
    assert obs_mod.periods_per_year("monthly") == 12
    assert obs_mod.periods_per_year("unspecified") is None
    with pytest.raises(obs_mod.ObservationError, match="never silently ignored"):
        obs_mod.validate_policy({"retrun_frequency": "daily"})
    with pytest.raises(obs_mod.ObservationError, match="log-return"):
        obs_mod.validate_policy({"return_convention": "log"})
    with pytest.raises(obs_mod.ObservationError, match="weight_timing_policy"):
        obs_mod.validate_policy({"weight_timing_policy": "centered"})
    with pytest.raises(obs_mod.ObservationError, match="never zero-filled"):
        obs_mod.validate_policy({"missing_input_policy": "zero"})
    with pytest.raises(obs_mod.ObservationError, match="tolerance"):
        obs_mod.validate_policy({"reconciliation_tolerance": 0.5})


def test_beginning_weight_path_matches_phase56_return_series():
    """The Phase 58 weight path must reproduce the canonical Phase 56
    realized return series exactly — reuse verified, not duplicated."""
    prun = _book()
    index = {ts: i for i, ts in enumerate(prun["universe"]["timestamps"])}
    rebalances = [{**r, "decision_index": index[r["decision_timestamp"]]}
                  for r in pd_store.list_rebalances(prun["id"])]
    asset_ids = [a["asset_id"] for a in prun["universe"]["assets"]]
    matrix = [a["returns"] for a in prun["universe"]["assets"]]
    n = len(prun["universe"]["timestamps"])

    canonical = reb_mod.portfolio_returns(rebalances, asset_ids, matrix, n)
    path = obs_mod.beginning_weight_path(rebalances, asset_ids, matrix, n)
    for t in range(n):
        if canonical[t] is None:
            continue
        assert path[t] is not None
        implied = sum(path[t][a] * matrix[k][t]
                      for k, a in enumerate(asset_ids))
        assert implied == pytest.approx(canonical[t], abs=1e-15)


def test_future_rebalance_and_future_return_invariance():
    """A later rebalance or a later return can never change an earlier
    period's beginning weights or contribution."""
    asset_ids = ["a", "b"]
    matrix = [[0.10, -0.05, 0.20], [0.00, 0.10, -0.30]]
    early = [{"decision_index": 0, "weights": {"a": 0.5, "b": 0.5}}]
    late = early + [{"decision_index": 2, "weights": {"a": 1.0, "b": 0.0}}]
    path_early = obs_mod.beginning_weight_path(early, asset_ids, matrix, 3)
    path_late = obs_mod.beginning_weight_path(late, asset_ids, matrix, 3)
    assert path_early[0] == path_late[0]
    assert path_early[1] == path_late[1]
    assert path_late[2] == {"a": 1.0, "b": 0.0}   # only the later period moves

    mutated = [row[:] for row in matrix]
    mutated[0][2] = 5.0                            # a wild FUTURE return
    path_mutated = obs_mod.beginning_weight_path(early, asset_ids, mutated, 3)
    assert path_mutated[0] == path_early[0]
    assert path_mutated[1] == path_early[1]


def test_integrity_states():
    prun = _book()
    rebalances = pd_store.list_rebalances(prun["id"])
    policy = obs_mod.validate_policy({"return_frequency": "daily"})
    assert obs_mod.classify_integrity(prun, policy, rebalances)["integrity"] \
        == "verified_causal_weights"
    eop = obs_mod.validate_policy({"weight_timing_policy": "end_of_period"})
    invalid = obs_mod.classify_integrity(prun, eop, rebalances)
    assert invalid["integrity"] == "invalid"
    assert "already embeds that period's return" in invalid["warnings"][0]
    centered = dict(prun)
    centered["configuration"] = {**prun["configuration"],
                                 "user_provenance": {"basis": "centered"}}
    assert obs_mod.classify_integrity(centered, policy,
                                      rebalances)["integrity"] == "invalid"
    full = dict(prun)
    full["configuration"] = {**prun["configuration"],
                             "estimation": {"mode": "full_sample"}}
    assert obs_mod.classify_integrity(full, policy, rebalances)["integrity"] \
        == "full_sample_descriptive"


# ---------------------------------------------------------------------------
# Contribution and group aggregation
# ---------------------------------------------------------------------------


def test_period_contributions_hand_computed():
    rows = [
        {"asset_id": "eq-a", "group_id": "equity",
         "portfolio_beginning_weight": 0.30, "asset_return": 0.02},
        {"asset_id": "eq-b", "group_id": "equity",
         "portfolio_beginning_weight": 0.30, "asset_return": 0.04},
        {"asset_id": "bd-a", "group_id": "bond",
         "portfolio_beginning_weight": 0.20, "asset_return": 0.01},
        {"asset_id": "bd-b", "group_id": "bond",
         "portfolio_beginning_weight": 0.20, "asset_return": -0.01},
    ]
    out = contrib_mod.period_contributions(rows)
    # 0.006 + 0.012 + 0.002 - 0.002 = 0.018
    assert out["portfolio_market_return"] == pytest.approx(0.018)
    assert out["cash_weight"] == pytest.approx(0.0)
    by_id = {r["asset_id"]: r for r in out["rows"]}
    assert by_id["eq-b"]["contribution"] == pytest.approx(0.012)

    groups = contrib_mod.group_aggregate(out["rows"])
    assert groups["equity"]["weight"] == pytest.approx(0.60)
    assert groups["equity"]["contribution"] == pytest.approx(0.018)
    assert groups["equity"]["group_return"] == pytest.approx(0.03)
    assert groups["bond"]["group_return"] == pytest.approx(0.0)
    assert groups["bond"]["return_state"] == "available"


def test_zero_and_negative_group_weight_semantics():
    rows = [{"asset_id": "x", "group_id": "empty",
             "portfolio_beginning_weight": 0.0, "asset_return": 0.5}]
    groups = contrib_mod.group_aggregate(
        contrib_mod.period_contributions(rows)["rows"])
    assert groups["empty"]["group_return"] is None
    assert groups["empty"]["return_state"] == "zero_weight"
    assert "never fabricated" in groups["empty"]["return_reason"]

    short_rows = [{"asset_id": "s", "group_id": "short",
                   "portfolio_beginning_weight": -0.20, "asset_return": 0.10}]
    short = contrib_mod.group_aggregate(
        contrib_mod.period_contributions(short_rows)["rows"])
    assert short["short"]["return_state"] == "negative_weight"
    assert short["short"]["group_return"] == pytest.approx(0.10)


def test_cash_residual_is_disclosed():
    rows = [{"asset_id": "a", "group_id": "g",
             "portfolio_beginning_weight": 0.60, "asset_return": 0.10}]
    out = contrib_mod.period_contributions(rows)
    assert out["weight_sum"] == pytest.approx(0.60)
    assert out["cash_weight"] == pytest.approx(0.40)
    assert out["portfolio_market_return"] == pytest.approx(0.06)


def test_supplied_return_is_never_forced_to_match():
    ok = contrib_mod.reconcile_portfolio_return(0.018, 0.018, 1e-9)
    assert ok["state"] == "reconciled" and ok["within_tolerance"]
    bad = contrib_mod.reconcile_portfolio_return(0.018, 0.020, 1e-9)
    assert bad["state"] == "mismatch"
    assert bad["residual"] == pytest.approx(0.002)
    assert bad["supplied_return"] == 0.020      # reported as given
    none = contrib_mod.reconcile_portfolio_return(0.018, None, 1e-9)
    assert none["state"] == "not_supplied"


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------


def test_benchmark_validation_rules():
    groups = {a: demo_mod.GROUPS[a] for a in ASSETS}
    ok = bench_mod.validate_benchmark(_benchmark(),
                                      portfolio_asset_ids=ASSETS,
                                      portfolio_groups=groups, period_count=3)
    assert ok["configured"] and ok["weight_sum_is_one"]
    assert ok["shared_asset_count"] == 4

    assert bench_mod.validate_benchmark(None, portfolio_asset_ids=ASSETS,
                                        portfolio_groups=groups,
                                        period_count=3)["configured"] is False

    with pytest.raises(bench_mod.BenchmarkError, match="never silently ignored"):
        bench_mod.validate_benchmark({**_benchmark(), "wieghts": []},
                                     portfolio_asset_ids=ASSETS,
                                     portfolio_groups=groups, period_count=3)
    with pytest.raises(bench_mod.BenchmarkError, match="written out explicitly"):
        bad = _benchmark()
        del bad["weights"]
        bench_mod.validate_benchmark(bad, portfolio_asset_ids=ASSETS,
                                     portfolio_groups=groups, period_count=3)
    with pytest.raises(bench_mod.BenchmarkError, match="never fabricated"):
        bench_mod.validate_benchmark(
            _benchmark(asset_ids=[*ASSETS, "cm-a"],
                       weights=[0.25, 0.25, 0.25, 0.25, 0.10],
                       groups={"cm-a": "commodity"}),
            portfolio_asset_ids=ASSETS, portfolio_groups=groups,
            period_count=3)
    with pytest.raises(bench_mod.BenchmarkError, match="never inferred"):
        bench_mod.validate_benchmark(
            _benchmark(asset_ids=[*ASSETS, "cm-a"],
                       weights=[0.25, 0.25, 0.25, 0.25, 0.10],
                       returns={"cm-a": [0.0, 0.0, 0.0]}),
            portfolio_asset_ids=ASSETS, portfolio_groups=groups,
            period_count=3)
    with pytest.raises(bench_mod.BenchmarkError, match="must match"):
        bench_mod.validate_benchmark({**_benchmark(),
                                      "return_convention": "log"},
                                     portfolio_asset_ids=ASSETS,
                                     portfolio_groups=groups, period_count=3)
    # a non-unit weight sum is disclosed, never renormalized
    odd = bench_mod.validate_benchmark(
        _benchmark(weights={"eq-a": 0.3, "eq-b": 0.3, "bd-a": 0.3, "bd-b": 0.3}),
        portfolio_asset_ids=ASSETS, portfolio_groups=groups, period_count=3)
    assert odd["weight_sum"] == pytest.approx(1.2)
    assert odd["weight_sum_is_one"] is False


def test_benchmark_weight_paths():
    groups = {a: demo_mod.GROUPS[a] for a in ASSETS}
    returns = [{a: 0.10 if a == "eq-a" else 0.0 for a in ASSETS}
               for _ in range(3)]
    fixed = bench_mod.validate_benchmark(_benchmark(),
                                         portfolio_asset_ids=ASSETS,
                                         portfolio_groups=groups,
                                         period_count=3)
    path = bench_mod.benchmark_weight_path(fixed, returns)
    assert all(p["eq-a"] == pytest.approx(0.25) for p in path)   # restored

    bh = bench_mod.validate_benchmark(_benchmark(kind="buy_and_hold"),
                                      portfolio_asset_ids=ASSETS,
                                      portfolio_groups=groups, period_count=3)
    bh_path = bench_mod.benchmark_weight_path(bh, returns)
    # 0.25 x 1.10 / (1 + 0.025) = 0.26829...
    assert bh_path[1]["eq-a"] == pytest.approx(0.25 * 1.10 / 1.025)
    assert bh_path[2]["eq-a"] > bh_path[1]["eq-a"]               # keeps drifting


# ---------------------------------------------------------------------------
# Brinson
# ---------------------------------------------------------------------------


def _groups(wp_eq, rp_eq, wp_bd, rp_bd):
    return {
        "equity": {"weight": wp_eq, "contribution": wp_eq * rp_eq,
                   "group_return": rp_eq, "return_state": "available"},
        "bond": {"weight": wp_bd, "contribution": wp_bd * rp_bd,
                 "group_return": rp_bd, "return_state": "available"},
    }


def test_brinson_fachler_hand_computed():
    portfolio = _groups(0.60, 0.03, 0.40, 0.00)
    benchmark = _groups(0.50, 0.03, 0.50, 0.00)
    out = brinson_mod.brinson_period(
        portfolio, benchmark, benchmark_total_return=0.015,
        portfolio_return=0.018, benchmark_return=0.015,
        variant="brinson_fachler", tolerance=1e-12)
    # equity (0.60-0.50)(0.03-0.015) = 0.0015; bond (0.40-0.50)(0-0.015) = 0.0015
    assert out["allocation_effect"] == pytest.approx(0.003)
    assert out["selection_effect"] == pytest.approx(0.0)
    assert out["interaction_effect"] == pytest.approx(0.0)
    assert out["active_return"] == pytest.approx(0.003)
    assert out["residual"] == pytest.approx(0.0, abs=1e-15)
    assert out["reconciliation_state"] == "reconciled"


def test_brinson_selection_and_interaction_hand_computed():
    # portfolio holds equity at the benchmark weight but a better mix
    portfolio = _groups(0.50, 0.04, 0.50, 0.00)
    benchmark = _groups(0.50, 0.03, 0.50, 0.00)
    out = brinson_mod.brinson_period(
        portfolio, benchmark, benchmark_total_return=0.015,
        portfolio_return=0.02, benchmark_return=0.015,
        variant="brinson_fachler", tolerance=1e-12)
    assert out["allocation_effect"] == pytest.approx(0.0)
    assert out["selection_effect"] == pytest.approx(0.5 * (0.04 - 0.03))
    assert out["interaction_effect"] == pytest.approx(0.0)
    assert out["residual"] == pytest.approx(0.0, abs=1e-15)

    # overweight AND a better mix -> non-zero interaction
    portfolio2 = _groups(0.70, 0.04, 0.30, 0.00)
    out2 = brinson_mod.brinson_period(
        portfolio2, benchmark, benchmark_total_return=0.015,
        portfolio_return=0.028, benchmark_return=0.015,
        variant="brinson_fachler", tolerance=1e-12)
    assert out2["interaction_effect"] == pytest.approx((0.70 - 0.50)
                                                       * (0.04 - 0.03))
    assert out2["allocation_effect"] == pytest.approx(
        (0.70 - 0.50) * (0.03 - 0.015) + (0.30 - 0.50) * (0.0 - 0.015))
    assert out2["residual"] == pytest.approx(0.0, abs=1e-15)


def test_brinson_hood_beebower_variant():
    portfolio = _groups(0.60, 0.03, 0.40, 0.00)
    benchmark = _groups(0.50, 0.03, 0.50, 0.00)
    out = brinson_mod.brinson_period(
        portfolio, benchmark, benchmark_total_return=0.015,
        portfolio_return=0.018, benchmark_return=0.015,
        variant="brinson_hood_beebower", tolerance=1e-12)
    # BHB: (0.60-0.50)x0.03 + (0.40-0.50)x0.00 = 0.003
    assert out["allocation_effect"] == pytest.approx(0.003)
    assert out["residual"] == pytest.approx(0.0, abs=1e-15)
    assert "Rb_total" not in out["formula"]


def test_brinson_one_sided_groups_and_residual_are_honest():
    portfolio = _groups(0.60, 0.03, 0.40, 0.00)
    benchmark = {"equity": {"weight": 1.0, "contribution": 0.03,
                            "group_return": 0.03, "return_state": "available"}}
    out = brinson_mod.brinson_period(
        portfolio, benchmark, benchmark_total_return=0.03,
        portfolio_return=0.018, benchmark_return=0.03,
        variant="brinson_fachler", tolerance=1e-12)
    bond = next(r for r in out["rows"] if r["group_id"] == "bond")
    assert bond["presence"] == "portfolio_only"
    assert bond["benchmark_weight"] == 0.0
    assert bond["allocation_effect"] is None       # needs a benchmark return
    assert bond["selection_effect"] is None
    assert out["unavailable_terms"]
    # the residual is NOT zero and its reason is stated
    assert out["residual"] != 0.0
    assert any("group return does not exist" in r for r in out["residual_reasons"])
    assert out["reconciliation_state"] == "residual"


def test_aggregate_brinson_preserves_window_presence():
    portfolio = _groups(0.60, 0.03, 0.40, 0.00)
    benchmark_both = _groups(0.50, 0.03, 0.50, 0.00)
    benchmark_equity_only = {"equity": benchmark_both["equity"]}
    p1 = brinson_mod.brinson_period(
        portfolio, benchmark_both, benchmark_total_return=0.015,
        portfolio_return=0.018, benchmark_return=0.015,
        variant="brinson_fachler", tolerance=1e-12)
    p2 = brinson_mod.brinson_period(
        portfolio, benchmark_equity_only, benchmark_total_return=0.03,
        portfolio_return=0.018, benchmark_return=0.03,
        variant="brinson_fachler", tolerance=1e-12)
    rows = {r["group_id"]: r for r in brinson_mod.aggregate_brinson([p1])}
    assert rows["bond"]["presence"] == "both"
    mixed = {r["group_id"]: r
             for r in brinson_mod.aggregate_brinson([p1, p2])}
    # the bond group is in both books in one period and portfolio-only in the
    # other, so the window-level label is 'mixed' rather than one period's
    assert mixed["bond"]["presence"] == "mixed"
    only = {r["group_id"]: r for r in brinson_mod.aggregate_brinson([p2])}
    assert only["bond"]["presence"] == "portfolio_only"


def test_brinson_rejects_unknown_variant():
    with pytest.raises(brinson_mod.BrinsonError, match="variant"):
        brinson_mod.brinson_period({}, {}, benchmark_total_return=0.0,
                                   portfolio_return=0.0, benchmark_return=0.0,
                                   variant="magic", tolerance=1e-9)


# ---------------------------------------------------------------------------
# Linking and TWR
# ---------------------------------------------------------------------------


def test_arithmetic_linking_discloses_the_compounding_gap():
    effects = [{"allocation_effect": 0.003, "selection_effect": 0.0,
                "interaction_effect": 0.0, "residual": 0.0} for _ in range(2)]
    out = link_mod.link_effects(effects, [0.018, 0.018], [0.015, 0.015],
                                "arithmetic", 1e-12)
    assert out["linked_effects"]["allocation_effect"] == pytest.approx(0.006)
    assert out["arithmetic_active_return"] == pytest.approx(0.006)
    assert out["within_tolerance"] is True
    geometric = (1.018 ** 2 - 1) - (1.015 ** 2 - 1)
    assert out["geometric_active_return"] == pytest.approx(geometric)
    assert out["arithmetic_vs_geometric_gap"] == pytest.approx(0.006 - geometric)
    assert "does not generally reconcile" in out["arithmetic_caveat"]


def test_carino_linking_reconciles_with_geometric_active_return():
    # effects that CLOSE each period (sum == that period's active return)
    port = [0.020, -0.010]
    bench = [0.016, -0.013]
    effects = [{"allocation_effect": 0.003, "selection_effect": 0.001,
                "interaction_effect": 0.0, "residual": 0.0},
               {"allocation_effect": 0.001, "selection_effect": 0.001,
                "interaction_effect": 0.001, "residual": 0.0}]
    out = link_mod.link_effects(effects, port, bench, "carino", 1e-12)
    assert out["available"] is True
    linked_total = sum(out["linked_effects"].values())
    assert linked_total == pytest.approx(out["geometric_active_return"],
                                         abs=1e-12)
    assert out["linking_residual"] == pytest.approx(0.0, abs=1e-12)
    assert out["within_tolerance"] is True
    assert len(out["smoothing_factors"]) == 2


def test_carino_linking_residual_is_the_scaled_period_residual():
    """When single-period effects do NOT close, the linking residual is
    exactly the scaled single-period residual — never an unexplained gap."""
    port = [0.020, -0.010]
    bench = [0.016, -0.013]
    # period 2 leaves 0.002 unexplained, recorded as its residual
    effects = [{"allocation_effect": 0.003, "selection_effect": 0.001,
                "interaction_effect": 0.0, "residual": 0.0},
               {"allocation_effect": -0.002, "selection_effect": 0.002,
                "interaction_effect": 0.001, "residual": 0.002}]
    out = link_mod.link_effects(effects, port, bench, "carino", 1e-12)
    assert out["available"] is True
    assert out["closure_residual"] == pytest.approx(0.0, abs=1e-12)
    assert out["linked_total_including_residual"] == pytest.approx(
        out["geometric_active_return"], abs=1e-12)
    assert out["linking_residual"] == pytest.approx(out["linked_residual_term"],
                                                    abs=1e-12)
    assert out["within_tolerance"] is False    # visibly does not close alone


def test_carino_equal_return_limit_is_exact():
    # x == y uses the analytic limit 1/(1+x), not an epsilon guard
    factor = link_mod._carino_factor(0.05, 0.05)
    assert factor == pytest.approx(1.0 / 1.05, abs=1e-15)
    effects = [{"allocation_effect": 0.0, "selection_effect": 0.0,
                "interaction_effect": 0.0, "residual": 0.0}]
    out = link_mod.link_effects(effects, [0.05], [0.05], "carino", 1e-12)
    assert out["available"] is True
    assert out["geometric_active_return"] == pytest.approx(0.0)


def test_carino_withheld_when_a_return_wipes_out_the_book():
    effects = [{"allocation_effect": 0.0, "selection_effect": 0.0,
                "interaction_effect": 0.0, "residual": 0.0} for _ in range(2)]
    out = link_mod.link_effects(effects, [-1.0, 0.05], [0.01, 0.01],
                                "carino", 1e-12)
    assert out["available"] is False
    assert "logarithm is undefined" in out["reason"]
    assert out["linked_effects"] is None


def test_time_weighted_return_convention():
    twr = link_mod.time_weighted_return([0.10, -0.05], supports_twr=True)
    assert twr["available"] is True
    assert twr["value"] == pytest.approx(1.10 * 0.95 - 1.0)
    assert "no money-weighted (IRR)" in twr["convention"]
    withheld = link_mod.time_weighted_return([0.10], supports_twr=False)
    assert withheld["available"] is False
    assert "no result is labelled a time-weighted return" in withheld["reason"]
    wiped = link_mod.time_weighted_return([-1.0], supports_twr=True)
    assert wiped["available"] is False


# ---------------------------------------------------------------------------
# Active risk and concentration
# ---------------------------------------------------------------------------


def test_active_risk_hand_computed():
    port = [0.02, 0.01, 0.03]
    bench = [0.01, 0.01, 0.01]
    out = risk_mod.active_risk(port, bench, periods_per_year=252,
                               frequency="daily")
    # active = [0.01, 0.0, 0.02]; mean 0.01; sample sd = 0.01
    assert out["mean_active_return"] == pytest.approx(0.01)
    assert out["tracking_error"] == pytest.approx(0.01)
    assert out["annualized_tracking_error"] == pytest.approx(0.01 * math.sqrt(252))
    assert out["information_ratio"] == pytest.approx(1.0)
    assert out["hit_rate"] == pytest.approx(2 / 3)
    assert out["std_convention"].startswith("sample")


def test_zero_tracking_error_leaves_information_ratio_unavailable():
    out = risk_mod.active_risk([0.01, 0.02], [0.01, 0.02],
                               periods_per_year=252, frequency="daily")
    assert out["tracking_error"] == pytest.approx(0.0)
    assert out["information_ratio"] is None
    assert out["information_ratio_state"] == "unavailable"
    assert "never reported as infinite" in out["information_ratio_reason"]


def test_unspecified_frequency_withholds_annualization():
    out = risk_mod.active_risk([0.02, 0.01], [0.01, 0.00],
                               periods_per_year=None, frequency="unspecified")
    assert out["tracking_error"] is not None
    assert out["annualized_tracking_error"] is None
    assert "never assumed" in out["annualization_note"]


def test_single_observation_is_unavailable_not_zero():
    out = risk_mod.active_risk([0.02], [0.01], periods_per_year=252,
                               frequency="daily")
    assert out["tracking_error"] is None
    assert out["information_ratio"] is None


def test_active_drawdown_convention():
    out = risk_mod.active_drawdown([0.10, -0.20, 0.05])
    assert out["available"] is True
    # wealth 1.10, 0.88, 0.924; peak 1.10 -> max dd = 0.88/1.10 - 1
    assert out["max_active_drawdown"] == pytest.approx(0.88 / 1.10 - 1.0)
    assert "not a realizable loss" in out["convention"]
    wiped = risk_mod.active_drawdown([-1.0])
    assert wiped["available"] is False


def test_concentration_separates_signed_and_absolute():
    out = risk_mod.concentration([0.08, -0.02, 0.0], label="asset")
    assert out["state"] == "available"
    assert out["largest_absolute_share"] == pytest.approx(0.8)
    assert out["positive_total"] == pytest.approx(0.08)
    assert out["negative_total"] == pytest.approx(-0.02)
    assert out["effective_contributors"] == pytest.approx(1.0 / out["herfindahl"])
    offsetting = risk_mod.concentration([0.05, -0.05], label="asset")
    assert offsetting["state"] == "available"      # absolute total is non-zero
    empty = risk_mod.concentration([0.0, 0.0], label="asset")
    assert empty["state"] == "unavailable"


# ---------------------------------------------------------------------------
# Costs
# ---------------------------------------------------------------------------


def test_period_costs_distinguish_no_trade_from_unavailable():
    rebalances = [
        {"decision_timestamp": "t1", "rebalance_id": 1,
         "cost": {"total_cost_return": 0.0004, "completeness": "partial",
                  "components": {"commission": 0.0001, "spread": 0.0002,
                                 "slippage": 0.0001, "impact": None},
                  "component_reasons": {"impact": "needs ADV"}}},
        {"decision_timestamp": "t2", "rebalance_id": 2, "cost": None},
    ]
    rows = cost_mod.period_costs([0, 1, 2], ["t0", "t1", "t2"], rebalances)
    assert rows[0]["state"] == "no_trade"
    assert rows[0]["total_cost_return"] == 0.0
    assert "structural zero" in rows[0]["reason"]
    assert rows[1]["state"] == "partial"
    assert rows[1]["components"]["impact"] is None
    assert rows[2]["state"] == "unavailable"
    assert rows[2]["total_cost_return"] is None

    agg = cost_mod.aggregate_costs(rows, {0: 0.01, 1: 0.02, 2: 0.03})
    assert agg["total_cost_return"] == pytest.approx(0.0004)
    assert agg["completeness"] == "partial"
    assert agg["unavailable_period_count"] == 1
    # the net leg covers the SAME periods as its cost leg
    assert agg["gross_market_return_costed_periods"] == pytest.approx(0.03)
    assert agg["net_return_costed_periods"] == pytest.approx(0.03 - 0.0004)
    assert agg["gross_market_return_all_periods"] == pytest.approx(0.06)
    assert "never netted against a narrower cost figure" in agg["basis_note"]


# ---------------------------------------------------------------------------
# Fingerprints
# ---------------------------------------------------------------------------


def test_fingerprints_are_deterministic_and_material():
    policy = obs_mod.validate_policy({"return_frequency": "daily"})
    a = fp_mod.attribution_policy_fingerprint(policy, "brinson",
                                              "brinson_fachler",
                                              "arithmetic", "none")
    b = fp_mod.attribution_policy_fingerprint(policy, "brinson",
                                              "brinson_fachler",
                                              "arithmetic", "none")
    assert a == b and len(a) == 64
    c = fp_mod.attribution_policy_fingerprint(policy, "brinson",
                                              "brinson_hood_beebower",
                                              "arithmetic", "none")
    assert c != a
    d = fp_mod.attribution_policy_fingerprint(policy, "brinson",
                                              "brinson_fachler", "carino",
                                              "none")
    assert d != a
    with pytest.raises(fp_mod.FingerprintError, match="non-finite"):
        fp_mod.configuration_fingerprint("x", "y", {"v": float("inf")}, {},
                                         {}, {})


# ---------------------------------------------------------------------------
# Service + API integration
# ---------------------------------------------------------------------------


def test_execute_reconciles_and_is_deterministic(client):
    prun = _book()
    created = client.post(f"{BASE}/runs", json=_payload(prun["id"]))
    assert created.status_code == 201, created.text
    run_id = created.json()["id"]
    done = client.post(f"{BASE}/runs/{run_id}/execute", json={})
    assert done.status_code == 200, done.text
    run = done.json()
    assert run["status"] == "completed"
    assert run["integrity_status"] == "verified_causal_weights"
    assert run["completeness_status"] == "complete"
    assert run["reconciliation_status"] == "reconciled"

    periods = client.get(f"{BASE}/runs/{run_id}/periods").json()["items"]
    first = periods[0]
    # hand-computed type-A period
    assert first["portfolio_market_return"] == pytest.approx(0.018)
    assert first["benchmark_return"] == pytest.approx(0.015)
    assert first["active_return"] == pytest.approx(0.003)
    assert first["allocation_effect"] == pytest.approx(0.003)
    assert first["selection_effect"] == pytest.approx(0.0, abs=1e-15)
    assert first["interaction_effect"] == pytest.approx(0.0, abs=1e-15)
    assert first["residual"] == pytest.approx(0.0, abs=1e-12)

    assets = client.get(f"{BASE}/runs/{run_id}/assets").json()["items"]
    total = sum(a["arithmetic_contribution"] for a in assets)
    assert total == pytest.approx(run["portfolio_market_return"])
    groups = client.get(f"{BASE}/runs/{run_id}/groups").json()["items"]
    assert sum(g["arithmetic_contribution"] for g in groups) == pytest.approx(total)

    again = client.post(f"{BASE}/runs/{run_id}/execute", json={})
    assert again.json()["result_fingerprint"] == run["result_fingerprint"]
    assert run["configuration"]["execution_order"] == service.EXECUTION_ORDER


def test_zero_active_return_and_baseline(client):
    prun = _book()
    run = service.create_run(_payload(prun["id"],
                                      benchmark=_benchmark(BALANCED)))
    done = service.execute_run(run["id"])
    assert done["active_return"] == pytest.approx(0.0, abs=1e-15)
    assert done["tracking_error"] == pytest.approx(0.0, abs=1e-15)
    assert done["information_ratio"] is None
    brinson = pa_store.list_brinson(done["id"])
    for row in brinson:
        assert row["allocation_effect"] == pytest.approx(0.0, abs=1e-12)
        assert row["selection_effect"] == pytest.approx(0.0, abs=1e-12)
        assert row["interaction_effect"] == pytest.approx(0.0, abs=1e-12)
    marked = service.mark_baseline(done["id"])
    assert marked["is_baseline"] is True


def test_invalid_timing_blocks_baseline(client):
    prun = _book()
    run = service.create_run(_payload(
        prun["id"], policy={"return_frequency": "daily",
                            "weight_timing_policy": "end_of_period"}))
    done = service.execute_run(run["id"])
    assert done["integrity_status"] == "invalid"
    assert any("descriptive only" in w for w in done["warnings"])
    with pytest.raises(service.ConflictError, match="verified"):
        service.mark_baseline(done["id"])
    resp = TestClient(main_module.app).post(
        f"{BASE}/runs/{done['id']}/mark-baseline")
    assert resp.status_code == 409


def test_brinson_requires_an_explicit_benchmark():
    prun = _book()
    with pytest.raises(service.AttributionError, match="never selected"):
        service.create_run(_payload(prun["id"], benchmark=None))
    # contribution-only works without one
    run = service.create_run(_payload(prun["id"], benchmark=None,
                                      attribution_method="contribution_only"))
    done = service.execute_run(run["id"])
    assert done["benchmark_return"] is None
    assert done["active_return"] is None
    assets = pa_store.list_assets(done["id"])
    assert sum(a["arithmetic_contribution"] for a in assets) == pytest.approx(
        done["portfolio_market_return"])


def test_portfolio_change_detected_at_execution(monkeypatch):
    prun = _book()
    run = service.create_run(_payload(prun["id"]))
    original = pd_store.get_run

    def tampered(run_id):
        row = original(run_id)
        if row and row["id"] == prun["id"]:
            row = {**row, "configuration_fingerprint": "tampered"}
        return row

    monkeypatch.setattr(service.pd_store, "get_run", tampered)
    with pytest.raises(service.AttributionError, match="changed since"):
        service.execute_run(run["id"])
    failed = pa_store.get_run(run["id"])
    assert failed["status"] == "failed"
    assert failed["result_fingerprint"] is None
    assert pa_store.list_periods(run["id"]) == []


def test_cost_attribution_keeps_market_and_cost_separate():
    from app.cost_diagnostics.demo import seed_demo_cost_diagnostics
    from app.cost_diagnostics.store import run_demo_key_id
    seed_demo_cost_diagnostics()
    cost_id = run_demo_key_id("demo:cd:complete-costs")
    prun = _book(cost_diagnostic_run_id=cost_id, cost_notional=1_000_000.0)
    run = service.create_run(_payload(prun["id"],
                                      cost_diagnostic_run_id=cost_id))
    done = service.execute_run(run["id"])
    cost = done["cost"]
    assert cost["total_cost_return"] > 0
    assert cost["component_totals"]["impact"] is None       # honestly missing
    assert done["portfolio_net_return"] == pytest.approx(
        cost["gross_market_return_costed_periods"] - cost["total_cost_return"])
    # the Phase 55 record is untouched
    from app.cost_diagnostics import store as cost_store
    assert cost_store.get_run(cost_id)["result_fingerprint"]


def test_regime_and_drawdown_integration_use_stored_records():
    from app.regime_diagnostics.demo import seed_demo_regime_diagnostics
    from app.regime_diagnostics import store as rd_store
    seed_demo_regime_diagnostics()
    regime_id = rd_store.run_demo_key_id("demo:rd:volatility-trend")
    before = rd_store.get_run(regime_id)
    prun = _book()
    # the regime timeline differs from this book's, so every period is
    # 'unassigned' — the join is by EXACT timestamp and never approximated
    run = service.create_run(_payload(prun["id"], regime_run_id=regime_id,
                                      regime_definition_id="vol"))
    done = service.execute_run(run["id"])
    rows = pa_store.list_regimes(done["id"])
    assert rows and all(r["observation_count"] > 0 for r in rows)
    assert rd_store.get_run(regime_id)["result_fingerprint"] == \
        before["result_fingerprint"]


def test_compare_and_export(client):
    prun = _book()
    a = service.execute_run(service.create_run(_payload(prun["id"]))["id"])
    b = service.execute_run(service.create_run(_payload(
        prun["id"], linking_method="carino",
        benchmark=_benchmark(BALANCED)))["id"])
    comparison = client.get(f"{BASE}/compare",
                            params={"a": a["id"], "b": b["id"]}).json()
    assert any("linking" in w for w in comparison["comparability_warnings"])
    assert comparison["fingerprint_match"]["attribution_policy"] is False
    assert comparison["brinson"]
    assert "no run is declared better" in comparison["note"]

    export = client.get(f"{BASE}/export").json()
    assert export["schema_version"] == "portfolio_attribution_export_v1"
    assert export["total_matching_runs"] == 2
    text = str(export)
    for banned in ("C:\\\\", "/home/", "password", "api_key", "secret"):
        assert banned not in text


def test_api_error_paths(client):
    assert client.get(f"{BASE}/runs/999").status_code == 404
    prun = _book()
    assert client.post(f"{BASE}/runs",
                       json=_payload(999999)).status_code == 422
    assert client.post(f"{BASE}/runs", json={**_payload(prun["id"]),
                                             "surprise": True}).status_code == 422
    assert client.post(f"{BASE}/runs", json=_payload(
        prun["id"], attribution_method="magic")).status_code == 422
    assert client.post(f"{BASE}/runs", json=_payload(
        prun["id"], linking_method="magic")).status_code == 422
    run = service.create_run(_payload(prun["id"]))
    service.invalidate_run(run["id"], "test")
    assert client.post(f"{BASE}/runs/{run['id']}/invalidate",
                       json={"reason": "again"}).status_code == 409
    assert client.post(f"{BASE}/runs/{run['id']}/execute",
                       json={}).status_code == 409


def test_demo_idempotent_and_prior_registries_preserved(client):
    first = demo_mod.seed_demo_portfolio_attribution()
    assert first["created_count"] == 17
    listing = pa_store.list_runs(page_size=100)
    assert listing["total"] == 17
    assert all(r["status"] == "completed" for r in listing["items"])

    with db_module.get_connection() as conn:
        def counts():
            return {t: conn.execute(
                f"SELECT COUNT(*) AS c FROM {t}").fetchone()["c"]
                for t in ("portfolio_diagnostic_runs", "cost_diagnostic_runs",
                          "experiment_registry", "portfolio_rebalances")}
        before = counts()
        second = demo_mod.seed_demo_portfolio_attribution()
        assert second["created_count"] == 0
        assert second["skipped_count"] == 17
        assert counts() == before
        attribution_experiments = conn.execute(
            "SELECT COUNT(*) AS c FROM experiment_registry "
            "WHERE name LIKE 'Portfolio attribution:%'").fetchone()["c"]
    assert attribution_experiments == 1

    resp = client.post(f"{BASE}/demo-seed")
    assert resp.status_code == 200 and resp.json()["created"] is False
    summary = client.get(f"{BASE}/summary").json()
    assert summary["runs"] == 17 and summary["completed"] == 17
