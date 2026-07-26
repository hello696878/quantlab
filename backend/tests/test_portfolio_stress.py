"""
Portfolio Stress Lab tests (Phase 57.0): shock units and precedence,
hand-computed contributions and drifted weights, integrity classification
with future-looking rejection, volatility/correlation stress with PSD
validation and explicit repair, stressed-risk recomputation, liquidity /
cost stress over a copied Phase 55 model, trailing-only drawdown paths,
episode detection, interval attribution, fingerprints, persistence,
baselines, compare/export, API error paths, demo idempotence, and
prior-registry preservation.
"""

from __future__ import annotations

import copy
import math
from datetime import datetime, timedelta

import numpy as np
import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")
db_module = pytest.importorskip("app.db")
scenario_mod = pytest.importorskip("app.portfolio_stress.scenario")
shocks_mod = pytest.importorskip("app.portfolio_stress.shocks")
stress_mod = pytest.importorskip("app.portfolio_stress.stress")
dd_mod = pytest.importorskip("app.portfolio_stress.drawdown")
fp_mod = pytest.importorskip("app.portfolio_stress.fingerprints")
service = pytest.importorskip("app.portfolio_stress.service")
ps_store = pytest.importorskip("app.portfolio_stress.store")
pd_service = pytest.importorskip("app.portfolio_diagnostics.service")
pd_store = pytest.importorskip("app.portfolio_diagnostics.store")

BASE = "/portfolio-stress"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_quantlab.db"
    monkeypatch.setattr(db_module, "_db_path_override", db_file)
    db_module.init_db()
    yield


@pytest.fixture
def client():
    return TestClient(main_module.app)


def _ts(n, start=datetime(2024, 1, 1)):
    return [(start + timedelta(days=i)).isoformat() for i in range(n)]


def _assets(n=80, seed=57):
    rng = np.random.default_rng(seed)
    return [
        {"asset_id": "a", "asset_type": "index", "group": "g1",
         "returns": [round(float(v), 8) for v in rng.normal(0.0004, 0.004, n)]},
        {"asset_id": "b", "asset_type": "index", "group": "g1",
         "returns": [round(float(v), 8) for v in rng.normal(0.0004, 0.008, n)]},
        {"asset_id": "c", "asset_type": "index", "group": "g2",
         "returns": [round(float(v), 8) for v in rng.normal(0.0004, 0.016, n)]},
    ]


def _portfolio_run(n=80, **overrides):
    """A completed Phase 56 equal-weight run to stress (decision index 40)."""
    payload = {
        "name": "stress anchor", "method": "equal_weight",
        "frequency": "daily", "timestamps": _ts(n), "assets": _assets(n),
        "estimation": {"mode": "rolling", "lookback": 40, "lag": 1},
    }
    payload.update(overrides)
    run = pd_service.create_run(payload)
    return pd_service.execute_run(run["id"])


def _stress_payload(prun_id, scenario, **overrides):
    payload = {"name": "stress run", "portfolio_run_id": prun_id,
               "scenario": scenario}
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Units, validation, precedence
# ---------------------------------------------------------------------------


def test_shock_units_and_bounds():
    assert scenario_mod.shock_to_return(-0.05, "return") == -0.05
    assert scenario_mod.shock_to_return(-5, "percent") == pytest.approx(-0.05)
    assert scenario_mod.shock_to_return(-500, "bps") == pytest.approx(-0.05)
    s = scenario_mod.validate_scenario(
        {"scenario_type": "hypothetical_asset_shock",
         "asset_shocks": {"a": {"value": -250, "unit": "bps"}}},
        asset_ids=["a", "b"], groups=[])
    assert s["asset_shocks"]["a"]["as_return"] == pytest.approx(-0.025)
    with pytest.raises(scenario_mod.ScenarioError, match="±100%"):
        scenario_mod.validate_scenario(
            {"scenario_type": "hypothetical_asset_shock",
             "asset_shocks": {"a": {"value": -1.5, "unit": "return"}}},
            asset_ids=["a"], groups=[])
    with pytest.raises(scenario_mod.ScenarioError, match="reference"):
        scenario_mod.validate_scenario(
            {"scenario_type": "hypothetical_asset_shock",
             "asset_shocks": {"a": {"value": -3.0, "unit": "price"}}},
            asset_ids=["a"], groups=[])
    with pytest.raises(scenario_mod.ScenarioError, match="finite"):
        scenario_mod.validate_scenario(
            {"scenario_type": "hypothetical_asset_shock",
             "asset_shocks": {"a": {"value": float("nan"), "unit": "return"}}},
            asset_ids=["a"], groups=[])


def test_scenario_validation_errors():
    ids, groups = ["a", "b"], ["g1"]
    with pytest.raises(scenario_mod.ScenarioError, match="unknown asset"):
        scenario_mod.validate_scenario(
            {"scenario_type": "hypothetical_asset_shock",
             "asset_shocks": {"zz": {"value": -0.1, "unit": "return"}}},
            asset_ids=ids, groups=groups)
    with pytest.raises(scenario_mod.ScenarioError, match="deferred in v1"):
        scenario_mod.validate_scenario(
            {"scenario_type": "hypothetical_asset_shock",
             "factor_shocks": {"momentum": -0.1}},
            asset_ids=ids, groups=groups)
    with pytest.raises(scenario_mod.ScenarioError, match="missing_shock_policy"):
        scenario_mod.validate_scenario(
            {"scenario_type": "hypothetical_asset_shock",
             "asset_shocks": {"a": {"value": -0.1, "unit": "return"}},
             "missing_shock_policy": "silent"}, asset_ids=ids, groups=groups)
    with pytest.raises(scenario_mod.ScenarioError, match="group shocks"):
        scenario_mod.validate_scenario(
            {"scenario_type": "hypothetical_group_shock"},
            asset_ids=ids, groups=groups)
    with pytest.raises(scenario_mod.ScenarioError, match="alpha"):
        scenario_mod.validate_scenario(
            {"scenario_type": "correlation_stress",
             "correlation_stress": {"mode": "toward_one", "alpha": 1.4}},
            asset_ids=ids, groups=groups)
    with pytest.raises(scenario_mod.ScenarioError, match="n x n"):
        scenario_mod.validate_scenario(
            {"scenario_type": "correlation_stress",
             "correlation_stress": {"mode": "supplied", "matrix": [[1.0]]}},
            asset_ids=ids, groups=groups)
    with pytest.raises(scenario_mod.ScenarioError, match="volatility multiplier"):
        scenario_mod.validate_scenario(
            {"scenario_type": "volatility_stress",
             "volatility_stress": {"mode": "multiplicative",
                                   "multiplier": 25.0}},
            asset_ids=ids, groups=groups)
    with pytest.raises(scenario_mod.ScenarioError, match="at least one"):
        scenario_mod.validate_scenario(
            {"scenario_type": "liquidity_and_cost_stress",
             "liquidity_cost_stress": {}}, asset_ids=ids, groups=groups)
    with pytest.raises(scenario_mod.ScenarioError, match="historical block"):
        scenario_mod.validate_scenario(
            {"scenario_type": "historical_window"},
            asset_ids=ids, groups=groups)
    with pytest.raises(scenario_mod.ScenarioError, match="never silently ignored"):
        scenario_mod.validate_scenario(
            {"scenario_type": "hypothetical_asset_shock",
             "asset_shocks": {"a": {"value": -0.1, "unit": "return"}},
             "correlation_shock": {"mode": "toward_one"}},  # typo'd key
            asset_ids=ids, groups=groups)
    with pytest.raises(scenario_mod.ScenarioError, match="deferred in v1"):
        scenario_mod.validate_scenario(
            {"scenario_type": "liquidity_and_cost_stress",
             "liquidity_cost_stress": {"cost_volatility_multiplier": 3.0}},
            asset_ids=ids, groups=groups)
    with pytest.raises(scenario_mod.ScenarioError, match="never silently symmetrized"):
        scenario_mod.validate_scenario(
            {"scenario_type": "correlation_stress",
             "correlation_stress": {"mode": "supplied",
                                    "matrix": [[1.0, 0.2], [0.4, 1.0]]}},
            asset_ids=ids, groups=groups)
    with pytest.raises(scenario_mod.ScenarioError, match="diagonal must be exactly 1"):
        scenario_mod.validate_scenario(
            {"scenario_type": "correlation_stress",
             "correlation_stress": {"mode": "supplied",
                                    "matrix": [[0.5, 0.2], [0.2, 1.0]]}},
            asset_ids=ids, groups=groups)
    with pytest.raises(scenario_mod.ScenarioError, match="silently overridden"):
        scenario_mod.validate_scenario(
            {"scenario_type": "historical_window",
             "asset_shocks": {"a": {"value": -0.1, "unit": "return"}},
             "historical": {"usage": "descriptive",
                            "start_timestamp": "t0", "end_timestamp": "t1"}},
            asset_ids=ids, groups=groups)
    with pytest.raises(scenario_mod.ScenarioError, match="exactly one stored"):
        scenario_mod.validate_scenario(
            {"scenario_type": "historical_single_period",
             "historical": {"usage": "descriptive",
                            "start_timestamp": "t0", "end_timestamp": "t9"}},
            asset_ids=ids, groups=groups)


def test_precedence_resolution():
    scenario = scenario_mod.validate_scenario(
        {"scenario_type": "combined_scenario",
         "asset_shocks": {"a": {"value": -0.10, "unit": "return"}},
         "group_shocks": {"g1": {"value": -0.05, "unit": "return"}},
         "global_shock": {"value": -0.01, "unit": "return"}},
        asset_ids=["a", "b", "c"], groups=["g1"])
    groups = {"a": "g1", "b": "g1", "c": None}
    out = shocks_mod.resolve_shocks(scenario, ["a", "b", "c"], groups)
    assert out["shocks"] == {"a": -0.10, "b": -0.05, "c": -0.01}
    assert out["sources"] == {"a": "asset", "b": "group", "c": "global"}
    # no global: c falls to the policy
    scenario2 = scenario_mod.validate_scenario(
        {"scenario_type": "combined_scenario",
         "group_shocks": {"g1": {"value": -0.05, "unit": "return"}},
         "missing_shock_policy": "unavailable"},
        asset_ids=["a", "b", "c"], groups=["g1"])
    out2 = shocks_mod.resolve_shocks(scenario2, ["a", "b", "c"], groups)
    assert out2["shocks"]["c"] is None
    assert out2["sources"]["c"] == "unavailable"


def test_direct_contributions_hand_computed():
    weights = {"a": 0.5, "b": 0.3, "c": 0.2}
    shocks = {"a": -0.10, "b": 0.05, "c": None}
    out = shocks_mod.direct_contributions(
        weights, shocks, ["a", "b", "c"], {"a": "g1", "b": "g1", "c": "g2"},
        1_000_000.0)
    # 0.5×−0.10 + 0.3×0.05 = −0.035 over the covered subset only
    assert out["portfolio_scenario_return"] == pytest.approx(-0.035)
    assert out["scenario_pnl"] == pytest.approx(-35_000.0)
    assert out["completeness"] == "partial"
    assert out["unavailable_assets"] == 1
    rows = {r["asset_id"]: r for r in out["rows"]}
    assert rows["a"]["contribution"] == pytest.approx(-0.05)
    assert rows["b"]["contribution"] == pytest.approx(0.015)
    assert rows["c"]["contribution"] is None
    assert rows["a"]["abs_share"] == pytest.approx(0.05 / 0.065)
    assert out["group_contributions"] == {"g1": pytest.approx(-0.035)}
    conc = out["concentration"]
    assert conc["largest_negative_contributor"] == "a"
    assert conc["largest_positive_contributor"] == "b"
    assert conc["positive_total"] == pytest.approx(0.015)
    assert conc["negative_total"] == pytest.approx(-0.05)


def test_drifted_weights_hand_computed():
    # 0.6×0.5=0.3, 0.4×1.0=0.4 → denominator 0.7 → 3/7, 4/7
    out = shocks_mod.drifted_weights({"a": 0.6, "b": 0.4},
                                     {"a": -0.5, "b": 0.0}, ["a", "b"])
    assert out["weights"]["a"] == pytest.approx(3 / 7)
    assert out["weights"]["b"] == pytest.approx(4 / 7)
    assert out["cash_weight"] == pytest.approx(0.0)
    # cash carried unshocked: net 0.8 → cash 0.2
    out2 = shocks_mod.drifted_weights({"a": 0.4, "b": 0.4},
                                      {"a": -0.5, "b": 0.0}, ["a", "b"])
    assert out2["weights"]["a"] == pytest.approx(0.2 / 0.8)
    assert out2["cash_weight"] == pytest.approx(0.2 / 0.8)
    # −100% floors the position at zero value
    out3 = shocks_mod.drifted_weights({"a": 0.5, "b": 0.5},
                                      {"a": -1.0, "b": 0.0}, ["a", "b"])
    assert out3["weights"]["a"] == 0.0
    # long-short wipeout → honest unavailability
    out4 = shocks_mod.drifted_weights({"a": 1.0, "b": -1.0},
                                      {"a": -0.6, "b": 0.7}, ["a", "b"])
    assert out4["weights"] is None
    assert "non-positive" in out4["reason"]
    # missing shock → unavailable
    out5 = shocks_mod.drifted_weights({"a": 1.0}, {"a": None}, ["a"])
    assert out5["weights"] is None
    # levered book: borrowed cash is a SIGNED residual, never clamped —
    # a zero shock must leave the book unchanged (denominator = 1 + Σwr)
    out6 = shocks_mod.drifted_weights({"a": 0.75, "b": 0.75},
                                      {"a": 0.0, "b": 0.0}, ["a", "b"])
    assert out6["weights"]["a"] == pytest.approx(0.75)
    assert out6["weights"]["b"] == pytest.approx(0.75)
    assert out6["cash_weight"] == pytest.approx(-0.5)
    # levered book under a shock: denominator 1 + 1.5×(−0.2) = 0.7
    out7 = shocks_mod.drifted_weights({"a": 0.75, "b": 0.75},
                                      {"a": -0.2, "b": -0.2}, ["a", "b"])
    assert out7["weights"]["a"] == pytest.approx(0.75 * 0.8 / 0.7)
    assert out7["cash_weight"] == pytest.approx(-0.5 / 0.7)


def test_integrity_classification():
    timeline = _ts(50)
    decision = timeline[30]

    def hist(usage, s, e):
        return {"scenario_type": "historical_window",
                "historical": {"usage": usage, "start_timestamp": timeline[s],
                               "end_timestamp": timeline[e]}}

    ok = scenario_mod.classify_integrity(hist("ex_ante", 5, 20),
                                         timeline=timeline,
                                         decision_timestamp=decision)
    assert ok["integrity"] == "verified_historical_window"
    # ending AT the decision index is already future-looking
    bad = scenario_mod.classify_integrity(hist("ex_ante", 5, 30),
                                          timeline=timeline,
                                          decision_timestamp=decision)
    assert bad["integrity"] == "invalid"
    assert "never labelled ex-ante" in bad["warnings"][0]
    full = scenario_mod.classify_integrity(hist("descriptive", 0, 49),
                                           timeline=timeline,
                                           decision_timestamp=decision)
    assert full["integrity"] == "full_sample_descriptive"
    unknown_ts = {"scenario_type": "historical_window",
                  "historical": {"usage": "ex_ante",
                                 "start_timestamp": "2030-01-01T00:00:00",
                                 "end_timestamp": "2030-01-05T00:00:00"}}
    assert scenario_mod.classify_integrity(
        unknown_ts, timeline=timeline,
        decision_timestamp=decision)["integrity"] == "invalid"
    reversed_win = scenario_mod.classify_integrity(
        hist("ex_ante", 20, 5), timeline=timeline,
        decision_timestamp=decision)
    assert reversed_win["integrity"] == "invalid"
    supplied = scenario_mod.classify_integrity(
        {"scenario_type": "user_supplied_descriptive"},
        timeline=timeline, decision_timestamp=decision)
    assert supplied["integrity"] == "supplied_descriptive"
    rule = scenario_mod.classify_integrity(
        {"scenario_type": "volatility_stress"},
        timeline=timeline, decision_timestamp=decision)
    assert rule["integrity"] == "verified_deterministic_rule"


# ---------------------------------------------------------------------------
# Covariance stress
# ---------------------------------------------------------------------------


def _cov2(sigma_a=0.01, sigma_b=0.02, rho=0.5):
    return np.array([[sigma_a ** 2, rho * sigma_a * sigma_b],
                     [rho * sigma_a * sigma_b, sigma_b ** 2]])


def test_stressed_correlation_modes_hand_computed():
    base = np.array([[1.0, 0.5], [0.5, 1.0]])
    m = stress_mod.stressed_correlation(base, {"mode": "uniform_multiplier",
                                               "value": 1.5})
    assert m["matrix"][0][1] == pytest.approx(0.75)
    assert m["clamped"] is False
    add = stress_mod.stressed_correlation(base, {"mode": "additive",
                                                 "value": 0.6})
    assert add["matrix"][0][1] == pytest.approx(1.0)  # 1.1 clamped to 1
    assert add["clamped"] is True
    toward = stress_mod.stressed_correlation(base, {"mode": "toward_one",
                                                    "alpha": 0.4})
    # 0.5 + 0.4 × (1 − 0.5) = 0.7
    assert toward["matrix"][0][1] == pytest.approx(0.7)
    supplied = stress_mod.stressed_correlation(
        base, {"mode": "supplied", "matrix": [[0.9, 0.2], [0.4, 0.9]]})
    assert supplied["matrix"][0][0] == 1.0          # diagonal refixed
    assert supplied["matrix"][0][1] == pytest.approx(0.3)  # symmetrized


def test_build_stressed_covariance_hand_computed_and_psd():
    cov = _cov2()
    out = stress_mod.build_stressed_covariance(
        cov, ["a", "b"],
        {"mode": "multiplicative", "multiplier": 2.0, "multipliers": {}}, None)
    assert out["matrix"] is not None
    # every entry scales by 4 when both vols double and correlation is fixed
    assert np.allclose(out["matrix"], 4.0 * cov)
    # non-PSD supplied correlation with repair 'none' → honest None
    non_psd = {"mode": "supplied",
               "matrix": [[1.0, 0.9, 0.9], [0.9, 1.0, -0.9],
                          [0.9, -0.9, 1.0]], "repair": "none"}
    cov3 = np.diag([1e-4, 4e-4, 9e-4])
    bad = stress_mod.build_stressed_covariance(cov3, ["a", "b", "c"],
                                               None, non_psd)
    assert bad["matrix"] is None
    assert "no silent repair" in bad["reason"]
    # the same matrix under an explicit eigenvalue floor is repaired
    repaired = stress_mod.build_stressed_covariance(
        cov3, ["a", "b", "c"], None, {**non_psd, "repair": "eigenvalue_floor",
                                      "eigenvalue_floor": 1e-8})
    assert repaired["matrix"] is not None
    assert repaired["repair"]["repaired"] is True
    assert np.linalg.eigvalsh(repaired["matrix"])[0] >= -1e-10
    # zero-variance baseline → correlation undefined, honest reason
    degenerate = stress_mod.build_stressed_covariance(
        np.diag([0.0, 1e-4]), ["a", "b"],
        {"mode": "multiplicative", "multiplier": 2.0, "multipliers": {}}, None)
    assert degenerate["matrix"] is None
    assert "zero-variance" in degenerate["reason"]


# ---------------------------------------------------------------------------
# Drawdown and attribution
# ---------------------------------------------------------------------------


def test_drawdown_path_and_episodes_hand_computed():
    returns = [None, 0.1, -0.05, -0.05, 0.12, -0.02]
    path = dd_mod.drawdown_path(returns, _ts(6))
    assert path["available"] and path["start_index"] == 1
    assert path["wealth"][0] == pytest.approx(1.1)
    assert path["wealth"][2] == pytest.approx(0.99275)
    # trailing-only peaks: the later 1.11188 peak never rewrites history
    assert path["peaks"][:3] == pytest.approx([1.1, 1.1, 1.1])
    assert path["drawdowns"][2] == pytest.approx(0.99275 / 1.1 - 1.0)
    assert path["max_drawdown"] == pytest.approx(-0.0975)
    episodes = dd_mod.detect_episodes(path)
    assert len(episodes) == 2
    first, second = episodes
    assert first["status"] == "recovered"
    assert first["peak_index"] == 0 and first["trough_index"] == 2
    assert first["depth"] == pytest.approx(-0.0975)
    assert first["duration"] == 2 and first["recovery_duration"] == 1
    assert second["status"] == "unrecovered"
    assert second["recovery_timestamp"] is None
    assert second["depth"] == pytest.approx(-0.02)


def test_drawdown_gaps_and_errors():
    gap = dd_mod.drawdown_path([0.01, None, 0.02], _ts(3))
    assert gap["available"] is False and "interior gaps" in gap["reason"]
    short = dd_mod.drawdown_path([None, 0.01], _ts(2))
    assert short["available"] is False
    wiped = dd_mod.drawdown_path([0.01, -1.0, 0.02], _ts(3))
    assert wiped["available"] is False and "non-positive" in wiped["reason"]


def test_opening_decline_is_a_real_drawdown():
    # the initial 1.0 capital IS a peak: a book that opens down 20% shows
    # a −20% drawdown, never zero
    path = dd_mod.drawdown_path([-0.2, 0.0], _ts(2))
    assert path["max_drawdown"] == pytest.approx(-0.2)
    episodes = dd_mod.detect_episodes(path)
    assert len(episodes) == 1
    assert episodes[0]["status"] == "unrecovered"
    assert episodes[0]["peak_is_initial_capital"] is True
    assert episodes[0]["start_index"] == 0
    # compounding case: peaks measured against initial capital
    path2 = dd_mod.drawdown_path([-0.1, -0.1, 0.5], _ts(3))
    assert path2["max_drawdown"] == pytest.approx(0.81 / 1.0 - 1.0)


def test_attribute_interval_hand_computed():
    weights = {"a": 0.5, "b": 0.5}
    series = [None, weights, weights, weights]
    returns_matrix = [[0.0, -0.02, -0.04, 0.01], [0.0, 0.01, -0.02, 0.03]]
    out = dd_mod.attribute_interval(1, 2, ["a", "b"], series, returns_matrix,
                                    {"a": "g1", "b": "g2"},
                                    static_weights=True)
    rows = {r["asset_id"]: r for r in out["rows"]}
    assert rows["a"]["contribution"] == pytest.approx(0.5 * (-0.02 - 0.04))
    assert rows["b"]["contribution"] == pytest.approx(0.5 * (0.01 - 0.02))
    assert out["portfolio_contribution_sum"] == pytest.approx(-0.035)
    assert rows["a"]["average_weight"] == pytest.approx(0.5)
    assert out["group_contributions"]["g1"] == pytest.approx(-0.03)
    assert "static stored target" in out["weight_policy"]
    missing = dd_mod.attribute_interval(0, 2, ["a", "b"], series,
                                        returns_matrix, {},
                                        static_weights=True)
    assert missing["available"] is False


# ---------------------------------------------------------------------------
# Fingerprints
# ---------------------------------------------------------------------------


def test_fingerprints_deterministic_and_reject_non_finite():
    scenario = scenario_mod.validate_scenario(
        {"scenario_type": "volatility_stress",
         "volatility_stress": {"mode": "multiplicative", "multiplier": 2.0}},
        asset_ids=["a", "b"], groups=[])
    fp1 = fp_mod.scenario_fingerprint(scenario, "verified_deterministic_rule")
    fp2 = fp_mod.scenario_fingerprint(scenario, "verified_deterministic_rule")
    assert fp1 == fp2 and len(fp1) == 64
    other = dict(scenario)
    other["volatility_stress"] = {"mode": "multiplicative", "multiplier": 2.5,
                                  "multipliers": {}}
    assert fp_mod.scenario_fingerprint(other, "verified_deterministic_rule") != fp1
    with pytest.raises(fp_mod.FingerprintError, match="non-finite"):
        fp_mod.matrix_fingerprint("k", [[float("inf")]])
    assert fp_mod.stressed_cost_model_fingerprint(
        "base", {"spread_multiplier": 3.0}) != \
        fp_mod.stressed_cost_model_fingerprint(
        "base", {"spread_multiplier": 2.0})


# ---------------------------------------------------------------------------
# Service + API integration
# ---------------------------------------------------------------------------


def test_create_execute_reconcile_and_determinism(client):
    prun = _portfolio_run()
    body = _stress_payload(prun["id"], {
        "scenario_type": "hypothetical_asset_shock",
        "asset_shocks": {"a": {"value": -10, "unit": "percent"},
                         "b": {"value": 5, "unit": "percent"}},
        "missing_shock_policy": "zero"}, notional=1_000_000.0)
    created = client.post(f"{BASE}/runs", json=body)
    assert created.status_code == 201, created.text
    run_id = created.json()["id"]
    done = client.post(f"{BASE}/runs/{run_id}/execute", json={})
    assert done.status_code == 200, done.text
    run = done.json()
    assert run["status"] == "completed"
    assert run["integrity_status"] == "verified_deterministic_rule"
    # equal weights 1/3: (−0.10 + 0.05 + 0) / 3
    assert run["scenario_return"] == pytest.approx(-0.05 / 3)
    assert run["scenario_pnl"] == pytest.approx(-1_000_000.0 * 0.05 / 3)
    rec = run["reconciliation"]
    assert rec["net_scenario_return"] == rec["direct_shock_return"]
    assert rec["stressed_cost_return"] is None
    items = client.get(f"{BASE}/runs/{run_id}/asset-results").json()["items"]
    assert sum(r["contribution"] for r in items) == \
        pytest.approx(run["scenario_return"])
    assert {r["shock_source"] for r in items} == {"asset", "policy_zero"}
    # deterministic re-execution: identical result fingerprint
    fp_first = run["result_fingerprint"]
    again = client.post(f"{BASE}/runs/{run_id}/execute", json={})
    assert again.json()["result_fingerprint"] == fp_first
    # the documented execution order is stored and fingerprinted
    assert run["configuration"]["execution_order"] == service.EXECUTION_ORDER


def test_unit_equivalence_across_definitions():
    prun = _portfolio_run()
    results = []
    fps = []
    for spec in ({"value": -5, "unit": "percent"},
                 {"value": -500, "unit": "bps"},
                 {"value": -0.05, "unit": "return"}):
        run = service.create_run(_stress_payload(prun["id"], {
            "scenario_type": "hypothetical_asset_shock",
            "asset_shocks": {"a": spec}, "missing_shock_policy": "zero"}))
        done = service.execute_run(run["id"])
        results.append(done["scenario_return"])
        fps.append(done["scenario_fingerprint"])
    assert results[0] == pytest.approx(results[1])
    assert results[0] == pytest.approx(results[2])
    assert len(set(fps)) == 3  # definitions differ even when results agree


def test_missing_policy_unavailable_partial(client):
    prun = _portfolio_run()
    run = service.create_run(_stress_payload(prun["id"], {
        "scenario_type": "hypothetical_asset_shock",
        "asset_shocks": {"a": {"value": -10, "unit": "percent"}},
        "missing_shock_policy": "unavailable"}))
    done = service.execute_run(run["id"])
    assert done["completeness_status"] == "partial"
    assert done["drifted"]["available"] is False
    assert any("missing-shock policy" in w for w in done["warnings"])
    # partial total covers the shocked subset only (labelled, not hidden)
    assert done["scenario_return"] == pytest.approx(-0.10 / 3)


def test_historical_replay_hand_computed_and_future_rejection(client):
    prun = _portfolio_run()
    timeline = prun["universe"]["timestamps"]
    returns = {a["asset_id"]: a["returns"]
               for a in prun["universe"]["assets"]}
    run = service.create_run(_stress_payload(prun["id"], {
        "scenario_type": "historical_window",
        "historical": {"usage": "ex_ante", "start_timestamp": timeline[10],
                       "end_timestamp": timeline[12]}}))
    done = service.execute_run(run["id"])
    assert done["integrity_status"] == "verified_historical_window"
    expected = 0.0
    for aid in ("a", "b", "c"):
        level = 1.0
        for t in (10, 11, 12):
            level *= 1.0 + returns[aid][t]
        expected += (level - 1.0) / 3.0
    assert done["scenario_return"] == pytest.approx(expected)
    # an off-timeline window is arithmetically undefined → rejected at create
    with pytest.raises(service.PortfolioStressError, match="stored"):
        service.create_run(_stress_payload(prun["id"], {
            "scenario_type": "historical_window",
            "historical": {"usage": "descriptive",
                           "start_timestamp": "2099-01-01T00:00:00",
                           "end_timestamp": "2099-01-05T00:00:00"}}))
    # a reversed window is never silently replayed as zero shocks
    with pytest.raises(service.PortfolioStressError, match="precedes"):
        service.create_run(_stress_payload(prun["id"], {
            "scenario_type": "historical_window",
            "historical": {"usage": "descriptive",
                           "start_timestamp": timeline[20],
                           "end_timestamp": timeline[10]}}))
    # ex-ante window reaching the decision cutoff (index 40) is invalid
    bad = service.create_run(_stress_payload(prun["id"], {
        "scenario_type": "historical_window",
        "historical": {"usage": "ex_ante", "start_timestamp": timeline[10],
                       "end_timestamp": timeline[40]}}))
    assert bad["integrity_status"] == "invalid"  # classified at create
    bad_done = service.execute_run(bad["id"])
    assert bad_done["integrity_status"] == "invalid"
    with pytest.raises(service.ConflictError, match="verified"):
        service.mark_baseline(bad["id"])
    resp = TestClient(main_module.app).post(
        f"{BASE}/runs/{bad['id']}/mark-baseline")
    assert resp.status_code == 409


def test_volatility_stress_scales_risk_not_pnl():
    prun = _portfolio_run()
    run = service.create_run(_stress_payload(prun["id"], {
        "scenario_type": "volatility_stress",
        "volatility_stress": {"mode": "multiplicative", "multiplier": 2.0},
        "missing_shock_policy": "zero"}))
    done = service.execute_run(run["id"])
    assert done["scenario_return"] == 0.0          # risk effect only
    rs = done["risk_summary"]
    assert rs["stressed_volatility"] == pytest.approx(
        2.0 * rs["baseline_volatility"])
    assert rs["baseline_identity_ok"] and rs["stressed_identity_ok"]
    rows = ps_store.list_risk_results(run["id"])
    for r in rows:                                  # proportional scaling
        assert r["pcr_change"] == pytest.approx(0.0, abs=1e-12)
        assert r["rank_change"] == 0
    assert done["reconciliation"]["risk_effect_note"].startswith(
        "volatility/correlation stress changes risk estimates only")


def test_supplied_non_psd_honest_vs_repaired():
    prun = _portfolio_run()
    matrix = [[1.0, 0.9, 0.9], [0.9, 1.0, -0.9], [0.9, -0.9, 1.0]]
    honest = service.execute_run(service.create_run(_stress_payload(
        prun["id"], {"scenario_type": "correlation_stress",
                     "correlation_stress": {"mode": "supplied",
                                            "matrix": matrix,
                                            "repair": "none"},
                     "missing_shock_policy": "zero"}))["id"])
    assert honest["covariance_stress"]["available"] is False
    assert honest["completeness_status"] == "partial"
    assert honest["stressed_covariance_fingerprint"] is None
    with pytest.raises(service.ConflictError, match="complete"):
        service.mark_baseline(honest["id"])
    repaired = service.execute_run(service.create_run(_stress_payload(
        prun["id"], {"scenario_type": "correlation_stress",
                     "correlation_stress": {"mode": "supplied",
                                            "matrix": matrix,
                                            "repair": "eigenvalue_floor",
                                            "eigenvalue_floor": 1e-8},
                     "missing_shock_policy": "zero"}))["id"])
    assert repaired["covariance_stress"]["available"] is True
    assert repaired["covariance_stress"]["repair"]["repaired"] is True
    assert repaired["stressed_covariance_fingerprint"]


def test_constraint_breaches_on_drifted_book_only():
    prun = _portfolio_run(constraints={"long_only": True, "max_weight": 0.4})
    run = service.create_run(_stress_payload(prun["id"], {
        "scenario_type": "hypothetical_asset_shock",
        "asset_shocks": {"a": {"value": 80, "unit": "percent"},
                         "b": {"value": -50, "unit": "percent"},
                         "c": {"value": -50, "unit": "percent"}},
        "missing_shock_policy": "zero"}))
    done = service.execute_run(run["id"])
    rows = ps_store.list_constraint_results(run["id"])
    assert done["breach_count"] == len(rows) > 0
    assert all(r["book"] == "drifted" for r in rows)
    assert any(r["asset_id"] == "a" and r["constraint"] == "max_weight"
               for r in rows)
    # drifted a = (1/3×1.8) / (1/3×1.8 + 1/3×0.5×2) = 0.6/0.93333
    drifted = {r["asset_id"]: r["drifted_weight"]
               for r in ps_store.list_asset_results(run["id"])}
    assert drifted["a"] == pytest.approx(0.6 / (0.6 + 1 / 3), rel=1e-6)


def test_cost_stress_copies_model_and_multiplies():
    base_model = {
        "commission": {"model": "bps_of_notional", "value": 1.0},
        "spread": {"model": "fixed_bps", "value": 2.0, "fraction": 0.5,
                   "sides": "round_trip"},
        "slippage": {"model": "fixed_bps_per_side", "value": 1.5,
                     "stress_multiplier": 1.0},
        "impact": {"model": "none"},
        "liquidity_policy": {}, "fingerprint": "base-fp",
    }
    snapshot = {k: (dict(v) if isinstance(v, dict) else v)
                for k, v in base_model.items()}
    block = service._cost_block(
        {"spread_multiplier": 3.0, "slippage_multiplier": 2.0,
         "adv_multiplier": 0.25, "base_adv_notional": 5_000_000.0,
         "participation_threshold": 0.25},
        base_model, {"a": 0.5, "b": 0.5}, 1_000_000.0)
    assert block["reference_turnover"] == pytest.approx(0.5)
    # base: commission 1e-4, spread 0.5×2 bps = 1e-4, slippage 1.5e-4
    assert block["base"]["total_cost_return"] == pytest.approx(3.5e-4)
    # stressed: spread ×3 → 3e-4, slippage ×2 → 3e-4, commission unchanged
    assert block["stressed"]["total_cost_return"] == pytest.approx(7.0e-4)
    part = block["participation"]
    assert part["participation"] == pytest.approx(
        (2 * 0.5 * 1_000_000.0) / (5_000_000.0 * 0.25))
    assert part["above_threshold"] is True
    assert base_model == snapshot          # the linked model is never mutated
    assert block["stressed_model_fingerprint"] != "base-fp"


def test_partial_shock_with_cost_leg_withholds_net():
    """A subset-basis shock leg is never netted against a whole-book cost
    leg — the net is withheld with an explicit reason."""
    from app.cost_diagnostics.demo import seed_demo_cost_diagnostics
    from app.cost_diagnostics.store import run_demo_key_id
    seed_demo_cost_diagnostics()
    cost_run = run_demo_key_id("demo:cd:complete-costs")
    prun = _portfolio_run()
    run = service.create_run(_stress_payload(prun["id"], {
        "scenario_type": "combined_scenario",
        "asset_shocks": {"a": {"value": -10, "unit": "percent"}},
        "missing_shock_policy": "unavailable",
        "liquidity_cost_stress": {"spread_multiplier": 2.0}},
        notional=1_000_000.0, cost_diagnostic_run_id=cost_run))
    done = service.execute_run(run["id"])
    rec = done["reconciliation"]
    assert rec["direct_shock_return"] is not None
    assert rec["stressed_cost_return"] is not None
    assert rec["net_scenario_return"] is None
    assert rec["scenario_pnl"] is None
    assert "different bases" in rec["net_basis_note"]
    assert any("net withheld" in w for w in done["warnings"])
    assert done["completeness_status"] == "partial"


def test_weight_change_detected_at_execution(monkeypatch):
    prun = _portfolio_run()
    run = service.create_run(_stress_payload(prun["id"], {
        "scenario_type": "hypothetical_asset_shock",
        "asset_shocks": {"a": {"value": -10, "unit": "percent"}},
        "missing_shock_policy": "zero"}))
    original = pd_store.list_rebalances

    def tampered(run_id):
        rows = original(run_id)
        for r in rows:
            r["weight_fingerprint"] = "tampered"
        return rows

    monkeypatch.setattr(service.pd_store, "list_rebalances", tampered)
    with pytest.raises(service.PortfolioStressError, match="changed since"):
        service.execute_run(run["id"])
    assert ps_store.get_run(run["id"])["status"] == "failed"


def test_failed_reexecution_clears_every_derived_field(monkeypatch):
    prun = _portfolio_run()
    run = service.create_run(_stress_payload(prun["id"], {
        "scenario_type": "hypothetical_asset_shock",
        "asset_shocks": {"a": {"value": -10, "unit": "percent"}},
        "missing_shock_policy": "zero"},
        sensitivity={"global_shock": [-0.10]}))
    done = service.execute_run(run["id"])
    assert done["scenario_count"] == 2 and done["result_fingerprint"]
    assert ps_store.list_sensitivity_results(run["id"])

    original = pd_store.list_rebalances

    def tampered(run_id):
        rows = original(run_id)
        for r in rows:
            r["weight_fingerprint"] = "tampered"
        return rows

    monkeypatch.setattr(service.pd_store, "list_rebalances", tampered)
    with pytest.raises(service.PortfolioStressError):
        service.execute_run(run["id"])
    failed = ps_store.get_run(run["id"])
    assert failed["status"] == "failed"
    # no stale numbers, warnings, counts or child rows survive
    assert failed["scenario_return"] is None
    assert failed["result_fingerprint"] is None
    assert failed["reconciliation"] is None
    assert failed["scenario_count"] == 0
    assert failed["warnings"] == []
    assert ps_store.list_sensitivity_results(run["id"]) == []
    assert ps_store.list_asset_results(run["id"]) == []
    assert ps_store.list_episodes(run["id"]) == []


def test_opening_decline_episode_labels_initial_capital():
    """An episode whose peak is the initial capital says so in its stored
    row, so a peak timestamp is never mistaken for an at-peak observation."""
    path = dd_mod.drawdown_path([-0.05, -0.02, 0.20], _ts(3))
    episodes = dd_mod.detect_episodes(path)
    assert episodes[0]["peak_is_initial_capital"] is True
    prun = _portfolio_run()
    run = service.create_run(_stress_payload(prun["id"], {
        "scenario_type": "volatility_stress",
        "volatility_stress": {"mode": "multiplicative", "multiplier": 2.0},
        "missing_shock_policy": "zero"}))
    service.execute_run(run["id"])
    stored = ps_store.list_episodes(run["id"])
    assert stored
    assert all("peak_is_initial_capital" in e for e in stored)
    assert all(isinstance(e["peak_is_initial_capital"], bool) for e in stored)


def test_scenario_metadata_preserved_but_outside_the_fingerprint():
    prun = _portfolio_run()
    base = {"scenario_type": "volatility_stress",
            "volatility_stress": {"mode": "multiplicative", "multiplier": 2.0},
            "missing_shock_policy": "zero"}
    plain = service.create_run(_stress_payload(prun["id"], dict(base)))
    tagged = service.create_run(_stress_payload(
        prun["id"], {**base, "metadata": {"desk": "macro", "ticket": 4412}}))
    stored = tagged["configuration"]["scenario"]["metadata"]
    assert stored == {"desk": "macro", "ticket": 4412}
    # metadata is descriptive labelling: it cannot change any computation
    assert plain["scenario_fingerprint"] == tagged["scenario_fingerprint"]


def test_trailing_unobserved_returns_are_not_called_interior_gaps():
    path = dd_mod.drawdown_path([None, 0.02, -0.03, 0.01, None], _ts(5))
    assert path["available"] is True
    assert path["start_index"] == 1 and path["end_index"] == 3
    assert path["trailing_unobserved"] == 1
    assert len(path["timestamps"]) == len(path["wealth"]) == 3
    interior = dd_mod.drawdown_path([0.01, None, 0.02], _ts(3))
    assert interior["available"] is False
    assert "interior gaps" in interior["reason"]


def test_sensitivity_bounds_and_rows():
    prun = _portfolio_run()
    with pytest.raises(service.PortfolioStressError, match="at most 5"):
        service.create_run(_stress_payload(prun["id"], {
            "scenario_type": "hypothetical_asset_shock",
            "asset_shocks": {"a": {"value": -10, "unit": "percent"}},
            "missing_shock_policy": "zero"},
            sensitivity={"global_shock": [-0.5, -0.4, -0.3, -0.2, -0.1, 0.1]}))
    with pytest.raises(service.PortfolioStressError, match="linked cost run"):
        service.create_run(_stress_payload(prun["id"], {
            "scenario_type": "hypothetical_asset_shock",
            "asset_shocks": {"a": {"value": -10, "unit": "percent"}},
            "missing_shock_policy": "zero"},
            sensitivity={"spread_multiplier": [2.0]}))
    run = service.create_run(_stress_payload(prun["id"], {
        "scenario_type": "hypothetical_asset_shock",
        "asset_shocks": {"a": {"value": -10, "unit": "percent"}},
        "missing_shock_policy": "zero"},
        sensitivity={"global_shock": [-0.10, 0.05],
                     "volatility_multiplier": [2.0]}))
    done = service.execute_run(run["id"])
    rows = ps_store.list_sensitivity_results(run["id"])
    assert len(rows) == 4                    # base + 3 probes
    assert rows[0]["is_base"] is True
    # the base row shares the run's NET basis (never a second counting)
    assert rows[0]["scenario_return"] == pytest.approx(done["scenario_return"])
    assert done["scenario_count"] == len(rows)
    assert len({r["fingerprint"] for r in rows}) == len(rows)
    vol_row = next(r for r in rows if r["dimension"] == "volatility_multiplier")
    assert vol_row["stressed_volatility"] == pytest.approx(
        2.0 * done["risk_summary"]["baseline_volatility"]
        if done["risk_summary"] else vol_row["stressed_volatility"])
    global_row = next(r for r in rows if r["dimension"] == "global_shock"
                      and r["value"] == pytest.approx(-0.10))
    assert global_row["scenario_return"] == pytest.approx(-0.10)


def test_compare_export_summary(client):
    prun = _portfolio_run()
    a = service.execute_run(service.create_run(_stress_payload(prun["id"], {
        "scenario_type": "hypothetical_asset_shock",
        "asset_shocks": {"a": {"value": -10, "unit": "percent"}},
        "missing_shock_policy": "zero"}))["id"])
    b = service.execute_run(service.create_run(_stress_payload(
        prun["id"], {"scenario_type": "user_supplied_descriptive",
                     "global_shock": {"value": -0.02, "unit": "return"},
                     "missing_shock_policy": "zero"},
        notional=100_000.0))["id"])
    cmp_resp = client.get(f"{BASE}/compare", params={"a": a["id"],
                                                     "b": b["id"]})
    assert cmp_resp.status_code == 200
    comparison = cmp_resp.json()
    assert any("notional" in w for w in comparison["comparability_warnings"])
    assert any("integrity" in w for w in comparison["comparability_warnings"])
    assert comparison["fingerprint_match"]["configuration"] is False
    assert {r["availability"] for r in comparison["contributions"]} == {"both"}
    export = client.get(f"{BASE}/export").json()
    assert export["schema_version"] == "portfolio_stress_export_v1"
    assert export["total_matching_runs"] == 2
    assert set(export["asset_results"]) == {str(a["id"]), str(b["id"])} or \
        set(export["asset_results"]) == {a["id"], b["id"]}
    summary = client.get(f"{BASE}/summary").json()
    assert summary["runs"] == 2 and summary["completed"] == 2


def test_api_error_paths(client):
    assert client.get(f"{BASE}/runs/999").status_code == 404
    prun = _portfolio_run()
    missing = client.post(f"{BASE}/runs", json=_stress_payload(999999, {
        "scenario_type": "volatility_stress",
        "volatility_stress": {"mode": "multiplicative", "multiplier": 2.0}}))
    assert missing.status_code == 422
    extra = client.post(f"{BASE}/runs", json={
        **_stress_payload(prun["id"], {
            "scenario_type": "volatility_stress",
            "volatility_stress": {"mode": "multiplicative",
                                  "multiplier": 2.0}}),
        "surprise": True})
    assert extra.status_code == 422
    bool_id = client.post(f"{BASE}/runs", json=_stress_payload(True, {
        "scenario_type": "volatility_stress",
        "volatility_stress": {"mode": "multiplicative", "multiplier": 2.0}}))
    assert bool_id.status_code == 422
    nan_notional = client.post(f"{BASE}/runs", json=_stress_payload(
        prun["id"], {"scenario_type": "volatility_stress",
                     "volatility_stress": {"mode": "multiplicative",
                                           "multiplier": 2.0}},
        notional=-5.0))
    assert nan_notional.status_code == 422
    run = service.create_run(_stress_payload(prun["id"], {
        "scenario_type": "volatility_stress",
        "volatility_stress": {"mode": "multiplicative", "multiplier": 2.0},
        "missing_shock_policy": "zero"}))
    service.invalidate_run(run["id"], "test")
    assert client.post(f"{BASE}/runs/{run['id']}/invalidate",
                       json={"reason": "again"}).status_code == 409
    assert client.post(f"{BASE}/runs/{run['id']}/execute",
                       json={}).status_code == 409


def test_demo_idempotent_and_prior_registries_preserved(client):
    from app.portfolio_stress.demo import seed_demo_portfolio_stress
    first = seed_demo_portfolio_stress()
    assert first["created_count"] == 16
    listing = ps_store.list_runs(page_size=100)
    assert listing["total"] == 16
    assert all(r["status"] == "completed" for r in listing["items"])
    # snapshot upstream registries, then re-seed: nothing may change
    with db_module.get_connection() as conn:
        def counts():
            return {t: conn.execute(
                f"SELECT COUNT(*) AS c FROM {t}").fetchone()["c"]
                for t in ("portfolio_diagnostic_runs", "cost_diagnostic_runs",
                          "experiment_registry", "portfolio_rebalances")}
        before = counts()
        weight_fp_before = conn.execute(
            "SELECT weight_fingerprint FROM portfolio_rebalances "
            "ORDER BY id LIMIT 1").fetchone()["weight_fingerprint"]
        second = seed_demo_portfolio_stress()
        assert second["created_count"] == 0
        assert second["skipped_count"] == 16
        after = counts()
        weight_fp_after = conn.execute(
            "SELECT weight_fingerprint FROM portfolio_rebalances "
            "ORDER BY id LIMIT 1").fetchone()["weight_fingerprint"]
    assert before == after
    assert weight_fp_before == weight_fp_after
    # exactly one experiment record (the flagship)
    with db_module.get_connection() as conn:
        stress_experiments = conn.execute(
            "SELECT COUNT(*) AS c FROM experiment_registry "
            "WHERE name LIKE 'Portfolio stress:%'").fetchone()["c"]
    assert stress_experiments == 1
    seed_resp = client.post(f"{BASE}/demo-seed")
    assert seed_resp.status_code == 200
    assert seed_resp.json()["created"] is False


def test_nested_scenario_validation_is_strict_and_type_honest():
    ids, groups = ["a", "b"], ["g1"]
    with pytest.raises(scenario_mod.ScenarioError, match="unsupported shock unit"):
        scenario_mod.shock_to_return(1.0, "ticks")
    with pytest.raises(scenario_mod.ScenarioError, match="asset_shocks must be an object"):
        scenario_mod.validate_scenario(
            {"scenario_type": "hypothetical_asset_shock",
             "asset_shocks": [["a", {"value": -0.1, "unit": "return"}]]},
            asset_ids=ids, groups=groups)
    with pytest.raises(scenario_mod.ScenarioError, match="never silently ignored"):
        scenario_mod.validate_scenario(
            {"scenario_type": "hypothetical_asset_shock",
             "asset_shocks": {"a": {"value": -0.1, "unit": "return",
                                      "units": "percent"}}},
            asset_ids=ids, groups=groups)
    with pytest.raises(scenario_mod.ScenarioError, match="never silently ignored"):
        scenario_mod.validate_scenario(
            {"scenario_type": "volatility_stress",
             "volatility_stress": {"mode": "multiplicative",
                                   "multiplier": 2.0, "multiplir": 3.0}},
            asset_ids=ids, groups=groups)
    with pytest.raises(scenario_mod.ScenarioError, match="combined_scenario"):
        scenario_mod.validate_scenario(
            {"scenario_type": "volatility_stress",
             "volatility_stress": {"mode": "multiplicative",
                                   "multiplier": 2.0},
             "asset_shocks": {"a": {"value": -0.1, "unit": "return"}}},
            asset_ids=ids, groups=groups)
    with pytest.raises(scenario_mod.ScenarioError, match="at least one"):
        scenario_mod.validate_scenario(
            {"scenario_type": "combined_scenario"},
            asset_ids=ids, groups=groups)
    with pytest.raises(scenario_mod.ScenarioError, match="NaN or Infinity"):
        scenario_mod.validate_scenario(
            {"scenario_type": "hypothetical_asset_shock",
             "asset_shocks": {"a": {"value": -0.1, "unit": "return"}},
             "metadata": {"score": float("nan")}},
            asset_ids=ids, groups=groups)


def test_notional_scale_requires_notional_and_bool_id_is_rejected():
    prun = _portfolio_run()
    with pytest.raises(service.PortfolioStressError, match="notional_scale"):
        service.create_run(_stress_payload(prun["id"], {
            "scenario_type": "liquidity_and_cost_stress",
            "liquidity_cost_stress": {"notional_scale": 2.0}}))
    with pytest.raises(service.PortfolioStressError, match="portfolio_run_id"):
        service._load_portfolio(True)


def test_drift_below_minus_one_is_unavailable_not_silently_floored():
    out = shocks_mod.drifted_weights(
        {"a": 1.0}, {"a": -1.01}, ["a"])
    assert out["weights"] is None
    assert "below -100%" in out["reason"]


def test_explicit_floor_repairs_singular_psd_with_accurate_disclosure():
    singular_psd = np.array([[0.01, 0.01], [0.01, 0.01]])
    result = stress_mod.build_stressed_covariance(
        singular_psd, ["a", "b"], None,
        {"mode": "toward_one", "alpha": 0.0,
         "repair": "eigenvalue_floor", "eigenvalue_floor": 1e-5})
    assert result["report"]["psd"] is True
    assert result["repair"]["repaired"] is True
    assert min(result["repair"]["original_eigenvalues"]) == pytest.approx(0.0)
    assert min(result["repair"]["repaired_eigenvalues"]) == pytest.approx(1e-5)


def test_material_result_and_sensitivity_fingerprints_cover_outputs():
    config_fp = "a" * 64
    base = {
        "drawdown": {"max_drawdown": -0.10},
        "constraint_results": [{"constraint": "gross", "amount": 0.1}],
        "sensitivity_results": [{"dimension": "global_shock",
                                  "scenario_return": -0.05}],
    }
    original = fp_mod.result_fingerprint(config_fp, base)
    changed = copy.deepcopy(base)
    changed["drawdown"]["max_drawdown"] = -0.11
    assert fp_mod.result_fingerprint(config_fp, changed) != original
    changed = copy.deepcopy(base)
    changed["constraint_results"][0]["amount"] = 0.2
    assert fp_mod.result_fingerprint(config_fp, changed) != original
    row = {"dimension": "global_shock", "value": -0.1, "is_base": False,
           "scenario_return": -0.1, "status": "completed"}
    row_changed = {**row, "scenario_return": -0.2}
    assert fp_mod.sensitivity_fingerprint(config_fp, row) != \
        fp_mod.sensitivity_fingerprint(config_fp, row_changed)


def test_verified_historical_result_ignores_appended_future_observation(
        monkeypatch):
    prun = _portfolio_run()
    timeline = prun["universe"]["timestamps"]
    payload = _stress_payload(prun["id"], {
        "scenario_type": "historical_window",
        "historical": {"usage": "ex_ante",
                       "start_timestamp": timeline[10],
                       "end_timestamp": timeline[12]}})
    first = service.execute_run(service.create_run(payload)["id"])
    original_get = pd_store.get_run

    def with_extreme_future(run_id):
        current = original_get(run_id)
        if current is None or run_id != prun["id"]:
            return current
        current = copy.deepcopy(current)
        future = (datetime.fromisoformat(current["universe"]["timestamps"][-1])
                  + timedelta(days=1)).isoformat()
        current["universe"]["timestamps"].append(future)
        for asset, shock in zip(current["universe"]["assets"],
                                (0.99, -0.99, 0.75)):
            asset["returns"].append(shock)
        return current

    monkeypatch.setattr(service.pd_store, "get_run", with_extreme_future)
    second = service.execute_run(first["id"])
    assert second["configuration_fingerprint"] == first["configuration_fingerprint"]
    assert second["result_fingerprint"] == first["result_fingerprint"]
    assert second["scenario_return"] == first["scenario_return"]
    assert second["drawdown"] == first["drawdown"]
    assert second["drawdown"]["analysis_scope"].startswith("strictly pre-decision")


def test_failed_state_and_child_cleanup_roll_back_together():
    prun = _portfolio_run()
    run = service.create_run(_stress_payload(prun["id"], {
        "scenario_type": "hypothetical_asset_shock",
        "asset_shocks": {"a": {"value": -10, "unit": "percent"}},
        "missing_shock_policy": "zero"}))
    completed = service.execute_run(run["id"])
    before_assets = ps_store.list_asset_results(run["id"])
    with db_module.get_connection() as conn:
        conn.execute(
            "CREATE TRIGGER reject_failed_parent BEFORE UPDATE OF status "
            "ON portfolio_stress_runs WHEN NEW.status = 'failed' "
            "BEGIN SELECT RAISE(ABORT, 'forced rollback'); END")
        conn.commit()
    with pytest.raises(Exception, match="forced rollback"):
        ps_store.fail_execution(run["id"], "failure", _ts(1)[0])
    after = ps_store.get_run(run["id"])
    assert after["status"] == completed["status"] == "completed"
    assert after["result_fingerprint"] == completed["result_fingerprint"]
    assert ps_store.list_asset_results(run["id"]) == before_assets


def test_unexpected_execution_error_is_sanitized(client, monkeypatch):
    prun = _portfolio_run()
    run = service.create_run(_stress_payload(prun["id"], {
        "scenario_type": "hypothetical_asset_shock",
        "asset_shocks": {"a": {"value": -10, "unit": "percent"}},
        "missing_shock_policy": "zero"}))

    def explode(*args, **kwargs):
        raise RuntimeError("secret C:/private/path token=abc")

    monkeypatch.setattr(service, "_execute_body", explode)
    response = client.post(f"{BASE}/runs/{run['id']}/execute", json={})
    assert response.status_code == 500
    assert "secret" not in response.text
    stored = ps_store.get_run(run["id"])
    assert stored["status"] == "failed"
    assert stored["error_message"] == "Internal execution error; see server logs."

def test_linked_cost_identity_is_pinned_and_rechecked(monkeypatch):
    from app.cost_diagnostics.demo import seed_demo_cost_diagnostics
    from app.cost_diagnostics.store import run_demo_key_id

    seed_demo_cost_diagnostics()
    cost_run_id = run_demo_key_id("demo:cd:complete-costs")
    prun = _portfolio_run()
    run = service.create_run(_stress_payload(prun["id"], {
        "scenario_type": "liquidity_and_cost_stress",
        "liquidity_cost_stress": {"spread_multiplier": 2.0}},
        notional=1_000_000.0, cost_diagnostic_run_id=cost_run_id))
    original = service.cost_store.get_run

    def changed_identity(run_id):
        linked = copy.deepcopy(original(run_id))
        linked["result_fingerprint"] = "changed-after-stress-create"
        return linked

    monkeypatch.setattr(service.cost_store, "get_run", changed_identity)
    with pytest.raises(service.PortfolioStressError, match="identity changed"):
        service.execute_run(run["id"])
    stored = ps_store.get_run(run["id"])
    assert stored["status"] == "failed"
    assert stored["result_fingerprint"] is None
