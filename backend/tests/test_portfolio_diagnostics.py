"""
Portfolio Diagnostics Lab tests (Phase 56.0): universe validation and
alignment, no-look-ahead estimation with future-outlier invariance,
equal-weight / inverse-volatility / ERC / minimum-variance construction,
covariance estimation + shrinkage + PSD validation + explicit repair,
normalization policies, constraints (bounds, exposure, group caps,
turnover, infeasibility), portfolio-risk identities, risk-budget and
concentration diagnostics, rebalance turnover, cost / regime / validation
integrations, fingerprints, migration, baselines, export, demo
idempotence, and API paths.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta

import numpy as np
import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")
db_module = pytest.importorskip("app.db")
core = pytest.importorskip("app.portfolio_diagnostics.core")
cov_mod = pytest.importorskip("app.portfolio_diagnostics.covariance")
methods = pytest.importorskip("app.portfolio_diagnostics.methods")
cons_mod = pytest.importorskip("app.portfolio_diagnostics.constraints")
risk_mod = pytest.importorskip("app.portfolio_diagnostics.risk")
reb_mod = pytest.importorskip("app.portfolio_diagnostics.rebalance")
fp_mod = pytest.importorskip("app.portfolio_diagnostics.fingerprints")
service = pytest.importorskip("app.portfolio_diagnostics.service")
pd_store = pytest.importorskip("app.portfolio_diagnostics.store")

BASE = "/portfolio-diagnostics"


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


def _assets(n=100, seed=7):
    rng = np.random.default_rng(seed)
    return [
        {"asset_id": "a", "asset_type": "index", "group": "g1",
         "returns": [round(float(v), 8) for v in rng.normal(0.0004, 0.004, n)]},
        {"asset_id": "b", "asset_type": "index", "group": "g1",
         "returns": [round(float(v), 8) for v in rng.normal(0.0004, 0.008, n)]},
        {"asset_id": "c", "asset_type": "index", "group": "g2",
         "returns": [round(float(v), 8) for v in rng.normal(0.0004, 0.016, n)]},
    ]


def _payload(n=100, **overrides):
    payload = {
        "name": "run", "method": "equal_weight", "frequency": "daily",
        "timestamps": _ts(n), "assets": _assets(n),
        "estimation": {"mode": "rolling", "lookback": 40, "lag": 1},
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Universe validation
# ---------------------------------------------------------------------------


def test_universe_validation():
    with pytest.raises(core.PortfolioInputError, match="between 2 and 20"):
        core.normalize_assets([_assets()[0]], 100)
    dup = _assets()
    dup[1]["asset_id"] = "a"
    with pytest.raises(core.PortfolioInputError, match="duplicate asset_id"):
        core.normalize_assets(dup, 100)
    with pytest.raises(core.PortfolioInputError, match="align identically"):
        core.normalize_assets(
            [{**_assets()[0], "returns": [0.0] * 99}, _assets()[1]], 100)
    bad = _assets()
    bad[0]["returns"][3] = float("nan")
    with pytest.raises(core.PortfolioInputError, match="finite"):
        core.normalize_assets(bad, 100)
    mixed = _assets()
    mixed[0]["currency"] = "USD"
    mixed[1]["currency"] = "EUR"
    with pytest.raises(core.PortfolioInputError, match="mixed currencies"):
        core.normalize_assets(mixed, 100)
    with pytest.raises(core.PortfolioInputError, match="strictly increasing"):
        core.normalize_timeline(_ts(30) + [_ts(30)[-1]], "daily")
    stamps = _ts(30)
    stamps[5] = stamps[5] + "+00:00"
    with pytest.raises(core.PortfolioInputError, match="mix timezone"):
        core.normalize_timeline(stamps, "daily")
    with pytest.raises(core.PortfolioInputError, match="never mixed"):
        core.normalize_benchmark([0.0] * 99, 100)


def test_estimation_no_lookahead_windows():
    est = reb_mod.validate_estimation_config(
        {"mode": "rolling", "lookback": 10, "lag": 2})
    # decision at i=15 uses returns[4..13] — never index 14 or 15
    assert reb_mod.estimation_window(15, est, 100) == (4, 13)
    assert reb_mod.estimation_window(10, est, 100) is None  # insufficient
    exp = reb_mod.validate_estimation_config(
        {"mode": "expanding", "lag": 1, "min_history": 12})
    assert reb_mod.estimation_window(12, exp, 100) == (0, 11)
    assert reb_mod.estimation_window(11, exp, 100) is None
    with pytest.raises(core.PortfolioInputError, match="centered"):
        reb_mod.validate_estimation_config({"mode": "rolling", "lookback": 10,
                                            "window": "centered"})
    with pytest.raises(core.PortfolioInputError, match="lag"):
        reb_mod.validate_estimation_config({"mode": "rolling", "lookback": 10,
                                            "lag": 0})
    with pytest.raises(core.PortfolioInputError, match="lag"):
        reb_mod.validate_estimation_config({"mode": "rolling", "lookback": 10,
                                            "lag": -1})


def test_future_outlier_invariance():
    """Future data cannot change an earlier decision's causal artifacts."""
    base = _payload(method="erc")
    run_a = service.create_run(base)
    executed_a = service.execute_run(run_a["id"])
    mutated = _payload(method="erc")
    # The one-time rebalance decides at the first feasible index using only
    # returns[0..40]; mutate observations strictly after that cutoff.
    for asset in mutated["assets"]:
        for k in range(60, len(asset["returns"])):
            asset["returns"][k] = 0.5
    mutated["name"] = "mutated"
    run_b = service.create_run(mutated)
    executed_b = service.execute_run(run_b["id"])
    weights_a = {w["asset_id"]: w["weight"]
                 for w in pd_store.list_weight_results(run_a["id"])}
    weights_b = {w["asset_id"]: w["weight"]
                 for w in pd_store.list_weight_results(run_b["id"])}
    rebalances_a = pd_store.list_rebalances(run_a["id"])
    rebalances_b = pd_store.list_rebalances(run_b["id"])
    assert weights_a == weights_b
    assert rebalances_a[0]["covariance_fingerprint"] == \
        rebalances_b[0]["covariance_fingerprint"]
    assert rebalances_a[0]["weight_fingerprint"] == \
        rebalances_b[0]["weight_fingerprint"]
    assert executed_a["covariance"]["matrix"] == \
        executed_b["covariance"]["matrix"]
    assert executed_a["risk"] == executed_b["risk"]
    # Full-universe identities still differ because the stored inputs differ.
    assert run_a["universe_fingerprint"] != run_b["universe_fingerprint"]
    assert service.get_run(run_a["id"])["integrity_status"] == \
        "verified_causal_rolling"

# ---------------------------------------------------------------------------
# Methods
# ---------------------------------------------------------------------------


def test_equal_and_inverse_vol_weights():
    ew = methods.equal_weight(["a", "b", "c"], ["c"])
    assert ew["weights"] == {"a": 0.5, "b": 0.5, "c": 0.0}
    assert methods.equal_weight(["a"], ["a"])["weights"] is None
    iv = methods.inverse_volatility(["a", "b"], {"a": 0.01, "b": 0.02}, [])
    assert iv["weights"]["a"] == pytest.approx(2 / 3)
    assert iv["weights"]["b"] == pytest.approx(1 / 3)
    # zero vol without a floor: unavailable; with a floor: clamped + recorded
    no_floor = methods.inverse_volatility(["a", "b"], {"a": 0.0, "b": 0.02}, [])
    assert no_floor["weights"]["a"] == 0.0
    assert no_floor["unavailable_assets"][0]["asset_id"] == "a"
    floored = methods.inverse_volatility(["a", "b"], {"a": 0.0, "b": 0.02},
                                         [], volatility_floor=0.01)
    assert floored["floored_assets"] == ["a"]
    assert floored["weights"]["a"] == pytest.approx(2 / 3)


def test_erc_hits_equal_risk_contributions():
    rng = np.random.default_rng(3)
    x = rng.normal(0, 1, (200, 4)) * np.array([0.005, 0.01, 0.02, 0.04])
    cov = np.cov(x, rowvar=False, ddof=1)
    result = methods.erc(cov, ["a", "b", "c", "d"])
    assert result["solver"]["status"] == "converged"
    w = np.array([result["weights"][k] for k in ("a", "b", "c", "d")])
    sigma = math.sqrt(w @ cov @ w)
    pcr = w * (cov @ w) / sigma ** 2
    assert np.allclose(pcr, 0.25, atol=1e-4)
    # zero-variance asset: honest failure
    bad = cov.copy()
    bad[0, :] = 0.0
    bad[:, 0] = 0.0
    failed = methods.erc(bad, ["a", "b", "c", "d"])
    assert failed["weights"] is None
    assert failed["solver"]["status"] == "failed"


def test_erc_independent_reference_and_failure_cases():
    covariance = np.diag([0.04, 0.01])
    equal = methods.erc(covariance, ["a", "b"])
    assert equal["solver"]["status"] == "converged"
    assert equal["weights"]["a"] == pytest.approx(1 / 3, abs=1e-6)
    assert equal["weights"]["b"] == pytest.approx(2 / 3, abs=1e-6)

    unequal = methods.erc(
        covariance, ["a", "b"], {"a": 0.8, "b": 0.2})
    unequal_weights = np.array([
        unequal["weights"]["a"], unequal["weights"]["b"]])
    variance = float(unequal_weights @ covariance @ unequal_weights)
    measured = unequal_weights * (covariance @ unequal_weights) / variance
    assert measured == pytest.approx([0.8, 0.2], abs=1e-6)

    highly_correlated = np.array([[0.04, 0.039], [0.039, 0.04]])
    correlated = methods.erc(highly_correlated, ["a", "b"])
    assert correlated["weights"] == pytest.approx({"a": 0.5, "b": 0.5})

    singular = np.array([[0.04, 0.04], [0.04, 0.04]])
    singular_result = methods.erc(singular, ["a", "b"])
    assert singular_result["solver"]["status"] == "converged"
    assert singular_result["weights"] == pytest.approx({"a": 0.5, "b": 0.5})

    non_converged = methods.erc(
        covariance, ["a", "b"], {"a": 0.9, "b": 0.1},
        tolerance=1e-12, max_iterations=0)
    assert non_converged["weights"] is None
    assert non_converged["solver"]["status"] == "failed"

def test_min_variance_and_normalization():
    cov = np.array([[0.04, 0.0], [0.0, 0.01]])
    cons = cons_mod.validate_constraints({}, [
        {"asset_id": "a", "group": None}, {"asset_id": "b", "group": None}])
    result = methods.min_variance(cov, ["a", "b"], cons)
    assert result["solver"]["status"] == "converged"
    # closed form: w ∝ 1/variance -> a: 0.2, b: 0.8
    assert result["weights"]["a"] == pytest.approx(0.2, abs=1e-6)
    assert result["weights"]["b"] == pytest.approx(0.8, abs=1e-6)
    # normalization policies
    n = methods.normalize_weights({"a": 2.0, "b": 2.0}, "sum_to_one")
    assert n["weights"] == {"a": 0.5, "b": 0.5}
    refused = methods.normalize_weights({"a": 1.0, "b": -1.0}, "sum_to_one")
    assert refused["status"] == "unavailable"  # never silently long-only
    g = methods.normalize_weights({"a": 1.0, "b": -1.0}, "gross_target",
                                  gross_target=1.0)
    assert g["weights"] == {"a": 0.5, "b": -0.5}
    cash = methods.normalize_weights({"a": 0.4, "b": 0.3}, "cash_residual")
    assert cash["residual"] == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# Covariance
# ---------------------------------------------------------------------------


def test_covariance_estimation_shrinkage_and_validation():
    x = np.array([[0.01, 0.02], [0.00, -0.01], [0.02, 0.03], [-0.01, 0.0]])
    cfg = cov_mod.validate_covariance_config({"method": "sample"})
    sample = cov_mod.estimate_covariance(x, cfg)
    assert np.allclose(sample, np.cov(x, rowvar=False, ddof=1))
    diag = cov_mod.estimate_covariance(
        x, cov_mod.validate_covariance_config({"method": "diagonal"}))
    assert diag[0, 1] == 0.0
    shrunk = cov_mod.estimate_covariance(x, cov_mod.validate_covariance_config(
        {"method": "fixed_shrinkage", "alpha": 0.5, "target": "diagonal"}))
    assert shrunk[0, 1] == pytest.approx(0.5 * sample[0, 1])
    with pytest.raises(cov_mod.CovarianceError, match="\\[0, 1\\]"):
        cov_mod.validate_covariance_config(
            {"method": "fixed_shrinkage", "alpha": 1.5})
    report = cov_mod.validate_matrix(sample)
    assert report["psd"] and report["min_eigenvalue"] > 0
    bad = np.array([[1.0, 2.0], [2.0, 1.0]])  # eigenvalues 3, -1
    bad_report = cov_mod.validate_matrix(bad)
    assert bad_report["psd"] is False
    asym = np.array([[1.0, 0.5], [0.1, 1.0]])
    assert cov_mod.validate_matrix(asym)["valid"] is False


def test_small_negative_eigenvalue_uses_psd_tolerance_wording():
    near_psd = np.array([[1.0, 1.0 + 5e-11], [1.0 + 5e-11, 1.0]])
    report = cov_mod.validate_matrix(near_psd)
    assert report["valid"] is True
    assert report["psd"] is True
    assert any("within the documented PSD tolerance" in warning
               for warning in report["warnings"])
    assert not any("non-PSD covariance" in warning
                   for warning in report["warnings"])

def test_covariance_repair_explicit_only():
    bad = np.array([[1.0, 2.0], [2.0, 1.0]])
    none = cov_mod.repair_matrix(
        bad, cov_mod.validate_covariance_config({"repair": "none"}))
    assert none["repaired"] is False  # never silent
    floored = cov_mod.repair_matrix(bad, cov_mod.validate_covariance_config(
        {"repair": "eigenvalue_floor", "eigenvalue_floor": 1e-6}))
    assert floored["repaired"] is True
    assert min(np.linalg.eigvalsh(floored["matrix"])) >= 1e-6 - 1e-12
    assert floored["original_eigenvalues"][0] == pytest.approx(-1.0)


# ---------------------------------------------------------------------------
# Constraints
# ---------------------------------------------------------------------------


def test_constraint_validation_and_infeasibility():
    assets = [{"asset_id": a, "group": g} for a, g in
              (("a", "g1"), ("b", "g1"), ("c", "g2"))]
    with pytest.raises(cons_mod.ConstraintError, match="min_weight must be <="):
        cons_mod.validate_constraints({"min_weight": 0.5, "max_weight": 0.2},
                                      assets)
    with pytest.raises(cons_mod.ConstraintError, match="infeasible"):
        cons_mod.validate_constraints({"max_weight": 0.2}, assets)  # 3*0.2<1
    with pytest.raises(cons_mod.ConstraintError, match="unknown group"):
        cons_mod.validate_constraints({"group_caps": {"nope": 0.5}}, assets)
    with pytest.raises(cons_mod.ConstraintError, match="frozen and excluded"):
        cons_mod.validate_constraints(
            {"frozen_weights": {"a": 0.1}, "excluded_assets": ["a"]}, assets)
    cons = cons_mod.validate_constraints(
        {"max_weight": 0.5, "group_caps": {"g1": 0.6},
         "turnover_cap": 0.1}, assets)
    violations = cons_mod.check_weights(
        {"a": 0.4, "b": 0.3, "c": 0.3}, cons, assets, turnover=0.25)
    names = {v["constraint"] for v in violations}
    assert names == {"group_caps", "turnover_cap"}  # g1 = 0.7 > 0.6
    assert not cons_mod.check_weights({"a": 0.3, "b": 0.3, "c": 0.4},
                                      cons, assets, turnover=0.05)


def test_structured_input_validation_and_short_feasibility(client):
    assets = [{"asset_id": asset_id, "group": group}
              for asset_id, group in (("a", "g1"), ("b", "g1"), ("c", "g2"))]
    with pytest.raises(cons_mod.ConstraintError, match="object"):
        cons_mod.validate_constraints([], assets)
    with pytest.raises(cons_mod.ConstraintError, match="boolean"):
        cons_mod.validate_constraints({"long_only": "false"}, assets)
    with pytest.raises(cons_mod.ConstraintError, match="group_caps"):
        cons_mod.validate_constraints({"group_caps": []}, assets)
    with pytest.raises(cons_mod.ConstraintError, match="excluded_assets"):
        cons_mod.validate_constraints({"excluded_assets": "a"}, assets)
    with pytest.raises(cons_mod.ConstraintError, match="cannot reach"):
        cons_mod.validate_constraints(
            {"long_only": False, "min_weight": -0.2, "max_weight": 0.1,
             "net_exposure_target": 1.0}, assets)
    with pytest.raises(cons_mod.ConstraintError, match="gross_exposure_limit"):
        cons_mod.validate_constraints(
            {"long_only": False, "min_weight": -1.0, "max_weight": 1.0,
             "net_exposure_target": 1.0, "gross_exposure_limit": 0.5}, assets)
    with pytest.raises(cons_mod.ConstraintError, match="group 'g1'"):
        cons_mod.validate_constraints(
            {"long_only": False, "min_weight": -1.0, "max_weight": 1.0,
             "excluded_assets": ["a", "b"],
             "group_minimums": {"g1": 0.1}}, assets)
    with pytest.raises(cons_mod.ConstraintError, match="frozen weights alone"):
        cons_mod.validate_constraints(
            {"long_only": False, "min_weight": -1.0, "max_weight": 1.0,
             "net_exposure_target": 0.0, "gross_exposure_limit": 0.5,
             "frozen_weights": {"a": 0.6}}, assets)
    with pytest.raises(cons_mod.ConstraintError, match="frozen weights in group"):
        cons_mod.validate_constraints(
            {"max_weight": 1.0, "group_caps": {"g1": 0.3},
             "frozen_weights": {"a": 0.4}}, assets)

    malformed = [
        _payload(constraints=[]),
        _payload(constraints={"long_only": "false"}),
        _payload(solver=[]),
        _payload(rebalance={"kind": "fixed_timestamps", "timestamps": [[1]]}),
        _payload(method="user_supplied", weights={"a": 0.4, "b": 0.3, "c": 0.3},
                 weight_provenance=[]),
        _payload(risk_budgets={"a": -0.1, "b": 0.6, "c": 0.5}),
        _payload(sample_ids=["duplicate"] * 100),
    ]
    bad_metadata = _payload()
    bad_metadata["assets"][0]["metadata"] = []
    malformed.append(bad_metadata)
    for payload in malformed:
        response = client.post(f"{BASE}/runs", json=payload)
        assert response.status_code == 422, response.text

# ---------------------------------------------------------------------------
# Risk identities + concentration
# ---------------------------------------------------------------------------


def test_risk_identities_and_contributions():
    cov = np.array([[0.04, 0.01, 0.0], [0.01, 0.02, 0.005],
                    [0.0, 0.005, 0.09]])
    w = [0.5, 0.3, 0.2]
    r = risk_mod.portfolio_risk(w, cov)
    assert r["variance"] == pytest.approx(float(np.array(w) @ cov @ np.array(w)))
    assert sum(r["ccr"]) == pytest.approx(r["volatility"], rel=1e-10)
    assert sum(r["pcr"]) == pytest.approx(1.0, rel=1e-9)
    assert r["identity_ok"] is True
    # long-short: a short hedge against a positively correlated long has a
    # NEGATIVE contribution, and it stays visible (never forced to zero)
    ls = risk_mod.portfolio_risk([1.0, -0.2, 0.0], cov)
    assert any(v < 0 for v in ls["pcr"])
    zero = risk_mod.portfolio_risk([0.0, 0.0, 0.0], cov)
    assert zero["mcr"] is None and "unavailable" in zero["note"]

    budget = risk_mod.budget_diagnostics(
        ["a", "b", "c"], r["pcr"], {"a": 1 / 3, "b": 1 / 3, "c": 1 / 3},
        tolerance=0.05)
    assert budget["target_sum"] == pytest.approx(1.0)
    assert budget["measured_sum"] == pytest.approx(1.0)
    states = {row["state"] for row in budget["rows"]}
    assert states <= {"within configured tolerance",
                      "outside configured tolerance"}

    conc = risk_mod.concentration_diagnostics(["a", "b", "c"], w, r["pcr"], cov)
    assert conc["weight_hhi"] == pytest.approx(0.25 + 0.09 + 0.04)
    assert conc["effective_positions"] == pytest.approx(1 / 0.38)
    assert conc["max_abs_weight"] == 0.5
    assert conc["diversification_ratio"] is not None
    assert conc["diversification_ratio"] >= 1.0 - 1e-9


# ---------------------------------------------------------------------------
# Rebalance + turnover
# ---------------------------------------------------------------------------


def test_turnover_and_schedules():
    assert reb_mod.one_way_turnover({"a": 0.5, "b": 0.5},
                                    {"a": 0.7, "b": 0.3}, "none") == \
        pytest.approx(0.2)
    assert reb_mod.one_way_turnover(None, {"a": 0.6, "b": 0.4}, "none") is None
    assert reb_mod.one_way_turnover(None, {"a": 0.6, "b": 0.4},
                                    "zero_book") == pytest.approx(0.5)
    est = reb_mod.validate_estimation_config(
        {"mode": "rolling", "lookback": 10, "lag": 1})
    policy = reb_mod.validate_rebalance_policy(
        {"kind": "every_n", "every_n": 20}, _ts(100))
    idx = reb_mod.rebalance_indices(policy, est, 100)
    # first feasible: start = i - lag - lookback + 1 >= 0 => i >= 10
    assert idx[0] == 10 and idx[1] == 30


def test_weight_drift_drives_turnover_and_realized_returns():
    asset_ids = ["a", "b"]
    returns_matrix = [[0.10, 0.0], [0.0, 0.10]]
    target = {"a": 0.5, "b": 0.5}
    drifted = reb_mod.drift_weights(
        target, asset_ids, returns_matrix, start=0, end=1)
    assert drifted == pytest.approx({"a": 0.55 / 1.05, "b": 0.5 / 1.05})
    turnover = reb_mod.one_way_turnover(drifted, target, "none")
    assert turnover == pytest.approx(
        0.5 * (abs(0.55 / 1.05 - 0.5) + abs(0.5 / 1.05 - 0.5)))

    realized = reb_mod.portfolio_returns(
        [{"decision_index": 0, "weights": target}], asset_ids,
        returns_matrix, n_periods=2)
    assert realized[0] == pytest.approx(0.05)
    assert realized[1] == pytest.approx((0.5 / 1.05) * 0.10)

def test_service_rebalances_and_turnover_cap(client):
    run = service.create_run(_payload(
        method="inverse_volatility",
        rebalance={"kind": "every_n", "every_n": 25,
                   "initial_turnover_policy": "zero_book"},
        constraints={"long_only": True, "turnover_cap": 0.01}))
    executed = service.execute_run(run["id"])
    rebs = pd_store.list_rebalances(run["id"])
    assert len(rebs) >= 2
    assert rebs[0]["turnover"] == pytest.approx(0.5)  # zero-book start
    # the tight cap is flagged by the independent check, never relaxed
    assert executed["constraint_violation_count"] >= 1
    with pytest.raises(service.ConflictError, match="constraint"):
        service.mark_baseline(run["id"])


# ---------------------------------------------------------------------------
# Integrations
# ---------------------------------------------------------------------------


def test_cost_integration_partial_honesty():
    from app.cost_diagnostics.demo import seed_demo_cost_diagnostics
    from app.cost_diagnostics.store import run_demo_key_id
    seed_demo_cost_diagnostics()
    cost_id = run_demo_key_id("demo:cd:complete-costs")
    run = service.create_run(_payload(
        method="equal_weight",
        rebalance={"kind": "every_n", "every_n": 30,
                   "initial_turnover_policy": "zero_book"},
        cost_diagnostic_run_id=cost_id, cost_notional=1_000_000.0))
    service.execute_run(run["id"])
    rebs = pd_store.list_rebalances(run["id"])
    cost = rebs[0]["cost"]
    assert cost["completeness"] == "partial"
    assert "impact" in cost["component_reasons"]  # sqrt impact unavailable
    assert cost["total_cost_return"] is not None
    assert cost["total_cost_notional"] == pytest.approx(
        cost["total_cost_return"] * 1_000_000.0)
    # Phase 55 record untouched
    from app.cost_diagnostics import store as cost_store
    assert cost_store.get_run(cost_id)["result_fingerprint"]


def test_regime_integration_uses_stored_assignments():
    from app.regime_diagnostics.demo import seed_demo_regime_diagnostics
    from app.regime_diagnostics import store as rd_store
    seed_demo_regime_diagnostics()
    regime_id = rd_store.run_demo_key_id("demo:rd:volatility-trend")
    before = rd_store.get_run(regime_id)
    stamps = before["timestamps"]
    rng = np.random.default_rng(11)
    run = service.create_run({
        "name": "regime", "method": "equal_weight", "frequency": "daily",
        "timestamps": stamps,
        "assets": [
            {"asset_id": "x", "returns": [round(float(v), 8) for v in
                                          rng.normal(0.0005, 0.006, 240)]},
            {"asset_id": "y", "returns": [round(float(v), 8) for v in
                                          rng.normal(0.0005, 0.01, 240)]},
        ],
        "estimation": {"mode": "rolling", "lookback": 40, "lag": 1},
        "regime_run_id": regime_id, "regime_definition_id": "vol"})
    executed = service.execute_run(run["id"])
    rows = executed["regimes"]["rows"]
    assert sum(r["observation_count"] for r in rows) > 0
    after = rd_store.get_run(regime_id)
    assert after["result_fingerprint"] == before["result_fingerprint"]
    assert after["updated_at"] == before["updated_at"]
    with pytest.raises(service.PortfolioDiagnosticsError, match="not found in run"):
        service.create_run(_payload(regime_run_id=regime_id,
                                    regime_definition_id="nope"))


def test_validation_training_only_and_membership():
    from app.model_validation.demo import seed_demo_validation
    from app.model_validation import store as mv_store
    seed_demo_validation()
    vrun_id = mv_store.run_demo_key_id("demo:mv:purged-kfold-embargo")
    vrun = mv_store.get_run(vrun_id)
    splits = mv_store.list_splits(vrun_id)
    split = next(s for s in splits if s["status"] == "valid")
    sample_ids = [s["sample_id"] for s in vrun["samples"]] \
        if vrun["samples"] and isinstance(vrun["samples"][0], dict) \
        else list(vrun["samples"])
    n = len(sample_ids)
    if n < 24:
        pytest.skip("demo validation run smaller than the universe minimum")
    rng = np.random.default_rng(13)
    payload = {
        "name": "train-only", "method": "erc", "frequency": "daily",
        "timestamps": _ts(n),
        "assets": [
            {"asset_id": "x", "returns": [round(float(v), 8) for v in
                                          rng.normal(0.0004, 0.006, n)]},
            {"asset_id": "y", "returns": [round(float(v), 8) for v in
                                          rng.normal(0.0004, 0.012, n)]},
        ],
        "estimation": {"mode": "expanding", "lag": 1, "min_history": 8},
        "validation_run_id": vrun_id,
        "validation_split_label": split["split_label"],
        "sample_ids": sample_ids,
    }
    run = service.create_run(payload)
    executed = service.execute_run(run["id"])
    assert executed["integrity_status"] == "verified_from_validation_split"
    # memberships and split fingerprints untouched
    assert mv_store.list_splits(vrun_id)[0]["split_fingerprint"] == \
        splits[0]["split_fingerprint"]
    # unknown membership fails honestly
    bad = dict(payload)
    bad["name"] = "bad"
    bad["sample_ids"] = ["zzz-" + s for s in sample_ids]
    bad_run = service.create_run(bad)
    with pytest.raises(service.PortfolioDiagnosticsError, match="membership"):
        service.execute_run(bad_run["id"])


# ---------------------------------------------------------------------------
# Fingerprints, migration, baselines, export, demo, API
# ---------------------------------------------------------------------------


def test_fingerprints_material_changes():
    a1 = core.normalize_assets(_assets(), 100)
    fp1 = fp_mod.universe_fingerprint(a1, _ts(100), "daily", None, None)
    a2 = core.normalize_assets(_assets(seed=8), 100)
    fp2 = fp_mod.universe_fingerprint(a2, _ts(100), "daily", None, None)
    assert fp1 != fp2
    with pytest.raises(fp_mod.FingerprintError):
        fp_mod.constraint_fingerprint({"x": float("inf")})
    run = service.create_run(_payload())
    first = service.execute_run(run["id"])
    second = service.execute_run(run["id"])
    assert first["result_fingerprint"] == second["result_fingerprint"]


def test_fingerprints_cover_execution_inputs_and_causal_windows():
    provenance = {"basis": "declared", "lag": 1}
    supplied_a = service.create_run(_payload(
        method="user_supplied", weights={"a": 0.6, "b": 0.3, "c": 0.1},
        weight_provenance=provenance))
    supplied_b = service.create_run(_payload(
        method="user_supplied", weights={"a": 0.4, "b": 0.4, "c": 0.2},
        weight_provenance=provenance))
    assert supplied_a["configuration_fingerprint"] != \
        supplied_b["configuration_fingerprint"]

    floor_a = service.create_run(_payload(
        method="inverse_volatility", volatility_floor=0.001))
    floor_b = service.create_run(_payload(
        method="inverse_volatility", volatility_floor=0.002))
    assert floor_a["configuration_fingerprint"] != \
        floor_b["configuration_fingerprint"]

    assets = core.normalize_assets(_assets(), 100)
    universe_a = fp_mod.universe_fingerprint(
        assets, _ts(100), "daily", None, None,
        prior_weights={"a": 0.5, "b": 0.3, "c": 0.2})
    universe_b = fp_mod.universe_fingerprint(
        assets, _ts(100), "daily", None, None,
        prior_weights={"a": 0.2, "b": 0.3, "c": 0.5})
    assert universe_a != universe_b

    matrix = [asset["returns"] for asset in assets]
    causal_a = fp_mod.estimation_input_fingerprint(
        ["a", "b", "c"], _ts(100), list(range(20)), matrix)
    mutated = [row[:] for row in matrix]
    mutated[0][90] = 0.9
    causal_b = fp_mod.estimation_input_fingerprint(
        ["a", "b", "c"], _ts(100), list(range(20)), mutated)
    assert causal_a == causal_b

    rebalance = {
        "rebalance_id": 0, "decision_timestamp": _ts(1)[0],
        "effective_timestamp": _ts(1)[0], "weights": {"a": 0.5, "b": 0.5},
        "prior_weights": None, "turnover": None, "gross_change": None,
        "solver": {"status": "converged", "residual": 1e-9},
        "constraint_violations": [], "cost": None, "status": "completed",
    }
    result_a = fp_mod.result_fingerprint(
        "cfg", [rebalance], {}, {}, {}, [], [], [], "declared", "converged")
    changed = {**rebalance,
               "solver": {"status": "converged", "residual": 1e-5},
               "cost": {"total_cost_return": 0.001}}
    result_b = fp_mod.result_fingerprint(
        "cfg", [changed], {}, {}, {}, [], [], [], "declared", "converged")
    assert result_a != result_b

def test_migration_and_registries_preserved():
    db_module.init_db()
    db_module.init_db()
    with db_module.get_connection() as conn:
        tables = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    for t in ("portfolio_diagnostic_runs", "portfolio_assets",
              "portfolio_rebalances", "portfolio_weight_results",
              "portfolio_risk_contributions", "portfolio_sensitivity_results",
              "cost_diagnostic_runs", "regime_diagnostic_runs",
              "validation_runs", "experiment_registry", "saved_backtests"):
        assert t in tables, t
    run = service.create_run(_payload())
    service.execute_run(run["id"])
    with db_module.get_connection() as conn:
        for t in ("cost_diagnostic_runs", "regime_diagnostic_runs",
                  "validation_runs"):
            assert conn.execute(
                f"SELECT COUNT(*) AS c FROM {t}").fetchone()["c"] == 0


def test_execution_snapshot_replacement_is_atomic(monkeypatch):
    run = service.create_run(_payload())
    service.execute_run(run["id"])
    before_run = service.get_run(run["id"])
    before_assets = pd_store.list_assets(run["id"])
    before_rebalances = pd_store.list_rebalances(run["id"])

    def fail_mid_transaction(*_args, **_kwargs):
        raise RuntimeError("injected child write failure")

    monkeypatch.setattr(
        pd_store, "_replace_weight_results_in_connection", fail_mid_transaction)
    with pytest.raises(RuntimeError, match="injected"):
        pd_store.replace_execution_results(
            run["id"], assets=[], rebalances=[], weights=[], contributions=[],
            sensitivity=[], run_updates={"status": "pending"})

    after_run = service.get_run(run["id"])
    assert pd_store.list_assets(run["id"]) == before_assets
    assert pd_store.list_rebalances(run["id"]) == before_rebalances
    assert after_run["status"] == before_run["status"]
    assert after_run["result_fingerprint"] == before_run["result_fingerprint"]


def test_unexpected_execution_error_is_sanitized(monkeypatch, client):
    run = service.create_run(_payload())

    def explode(*_args, **_kwargs):
        raise RuntimeError("sqlite secret C:/private/data.db")

    monkeypatch.setattr(pd_store, "replace_execution_results", explode)
    with pytest.raises(service.InternalExecutionError) as caught:
        service.execute_run(run["id"])
    assert "sqlite secret" not in str(caught.value)
    stored = service.get_run(run["id"])
    assert stored["status"] == "failed"
    assert "sqlite secret" not in stored["error_message"]
    api_run = service.create_run(_payload(name="api internal failure"))
    response = client.post(
        f"{BASE}/runs/{api_run['id']}/execute",
        json={"create_experiment": False})
    assert response.status_code == 500
    assert response.json()["detail"] == str(caught.value)
    assert "sqlite secret" not in response.text


def test_baseline_policy_and_scope():
    run = service.create_run(_payload(method="erc"))
    with pytest.raises(service.ConflictError, match="completed"):
        service.mark_baseline(run["id"])
    service.execute_run(run["id"])
    marked = service.mark_baseline(run["id"])
    assert marked["is_baseline"] and marked["baseline_scope"]
    again = service.mark_baseline(run["id"])
    assert again["is_baseline"]
    other = service.create_run(_payload(name="other", method="equal_weight"))
    service.execute_run(other["id"])
    service.mark_baseline(other["id"])  # different method => different scope
    assert service.get_run(run["id"])["is_baseline"]
    service.invalidate_run(run["id"], "superseded")
    assert not service.get_run(run["id"])["is_baseline"]


def test_sensitivity_grid_and_export(client):
    run = service.create_run(_payload(
        method="erc",
        sensitivity={"shrinkage_alpha": [0.2, 0.5],
                     "correlation_multiplier": [0.5, 1.5]},
        covariance={"method": "fixed_shrinkage", "alpha": 0.1,
                    "target": "diagonal"}))
    service.execute_run(run["id"])
    rows = pd_store.list_sensitivity_results(run["id"])
    assert sum(1 for r in rows if r["is_base"]) == 1
    assert len(rows) == 5
    assert len({r["fingerprint"] for r in rows}) == 5
    resp = client.get(f"{BASE}/export")
    assert resp.status_code == 200
    blob = resp.text
    assert "NaN" not in blob and "Infinity" not in blob
    assert "C:\\\\" not in blob and "C:/" not in blob
    assert resp.json()["schema_version"] == "portfolio_diagnostics_export_v1"
    with pytest.raises(service.PortfolioDiagnosticsError, match="dimensions"):
        service.create_run(_payload(sensitivity={"nope": [1]}))


def test_demo_idempotent_and_expectations():
    from app.portfolio_diagnostics.demo import seed_demo_portfolio_diagnostics
    first = seed_demo_portfolio_diagnostics()
    assert first["created_runs"] == 11
    second = seed_demo_portfolio_diagnostics()
    assert second["created_runs"] == 0 and second["skipped_existing"] == 11
    erc = pd_store.get_run(pd_store.run_demo_key_id("demo:pd:erc"))
    assert erc["is_baseline"] and erc["max_budget_deviation"] < 0.01
    assert erc["experiment_id"] is not None
    iv = pd_store.run_demo_key_id("demo:pd:inverse-vol")
    weights = {w["asset_id"]: w["weight"]
               for w in pd_store.list_weight_results(iv)}
    assert weights["lowvol-a"] > weights["highvol-b"]
    fail = pd_store.get_run(
        pd_store.run_demo_key_id("demo:pd:singular-honest-failure"))
    assert fail["solver_status"] == "failed"
    repaired = pd_store.get_run(
        pd_store.run_demo_key_id("demo:pd:singular-repaired"))
    assert repaired["covariance"]["repair"]["repaired"] is True
    invalid = pd_store.get_run(
        pd_store.run_demo_key_id("demo:pd:future-looking"))
    assert invalid["integrity_status"] == "invalid"
    fs = pd_store.get_run(pd_store.run_demo_key_id("demo:pd:full-sample"))
    assert fs["integrity_status"] == "full_sample_descriptive"


def test_adversarial_review_regressions(client):
    # MAJOR: full_sample + validation split must be rejected — a whole-sample
    # window would let traded periods inform their own weights
    with pytest.raises(service.PortfolioDiagnosticsError, match="full_sample"):
        service.create_run(_payload(
            estimation={"mode": "full_sample", "lag": 1},
            validation_run_id=123, validation_split_label="s",
            sample_ids=["x"] * 100))
    # defense in depth: even if such a config existed, integrity stays
    # full_sample_descriptive
    assert service._integrity_state(
        {"method": "erc", "estimation": {"mode": "full_sample"}},
        {1, 2, 3}) == "full_sample_descriptive"
    # MAJOR: a sensitivity max_weight below min_weight is rejected at create
    with pytest.raises(service.PortfolioDiagnosticsError,
                       match="below the\\s+configured min_weight"):
        service.create_run(_payload(
            constraints={"long_only": True, "min_weight": 0.2,
                         "max_weight": 0.5},
            sensitivity={"max_weight": [0.1]}))
    # inapplicable sensitivity dimensions are rejected, not silent no-ops
    with pytest.raises(service.PortfolioDiagnosticsError, match="rolling"):
        service.create_run(_payload(
            estimation={"mode": "expanding", "lag": 1, "min_history": 12},
            sensitivity={"lookback": [30]}))
    with pytest.raises(service.PortfolioDiagnosticsError,
                       match="fixed_shrinkage"):
        service.create_run(_payload(sensitivity={"shrinkage_alpha": [0.2]}))
    # supplied initial-turnover policy requires prior weights
    with pytest.raises(service.PortfolioDiagnosticsError,
                       match="prior_weights"):
        service.create_run(_payload(
            rebalance={"kind": "one_time",
                       "initial_turnover_policy": "supplied"}))
    # excessive rebalance schedules are rejected eagerly
    with pytest.raises(service.PortfolioDiagnosticsError, match="rebalances"):
        service.create_run(_payload(
            n=200, rebalance={"kind": "every_n", "every_n": 1}))
    # non-dict covariance config is a clean 422, never a raw TypeError
    assert client.post(f"{BASE}/runs",
                       json=_payload(covariance=42)).status_code == 422
    # a failing sensitivity scenario never voids the run
    run = service.create_run(_payload(
        method="erc", sensitivity={"correlation_multiplier": [1.5]}))
    executed = service.execute_run(run["id"])
    assert executed["status"] == "completed"
    # baseline requires every rebalance solved
    fail_run = service.create_run(_payload(
        method="erc",
        assets=[{"asset_id": "const", "returns": [0.0002] * 100},
                *_assets()[:1]]))
    service.execute_run(fail_run["id"])
    assert service.get_run(fail_run["id"])["solver_status"] == "failed"
    with pytest.raises(service.ConflictError):
        service.mark_baseline(fail_run["id"])


def test_api_happy_and_error_paths(client):
    resp = client.post(f"{BASE}/runs", json=_payload())
    assert resp.status_code == 201
    run_id = resp.json()["id"]
    resp = client.post(f"{BASE}/runs/{run_id}/execute",
                       json={"create_experiment": False})
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"
    assert client.get(f"{BASE}/summary").json()["runs"] == 1
    weights = client.get(f"{BASE}/runs/{run_id}/weights").json()["items"]
    assert abs(sum(w["weight"] for w in weights) - 1.0) < 1e-9
    contribs = client.get(
        f"{BASE}/runs/{run_id}/risk-contributions").json()["items"]
    assert abs(sum(c["pcr"] for c in contribs) - 1.0) < 1e-7
    assert client.get(f"{BASE}/runs/{run_id}/rebalances").json()["items"]
    assert client.get(f"{BASE}/runs/999").status_code == 404
    assert client.post(f"{BASE}/runs", json=_payload(
        method="max_diversification")).status_code == 422
    assert client.post(f"{BASE}/runs", json=_payload(
        method="mean_variance")).status_code == 422
    assert client.post(f"{BASE}/runs", json=_payload(
        estimation={"mode": "rolling", "lookback": 40,
                    "lag": -1})).status_code == 422
    assert client.post(f"{BASE}/runs", json=_payload(
        constraints={"max_weight": 0.1})).status_code == 422  # infeasible
    raw = json.dumps(_payload()).replace('"lag": 1', '"lag": 1, "x": NaN')
    assert client.post(f"{BASE}/runs", content=raw,
                       headers={"content-type": "application/json"}
                       ).status_code == 422
    other = client.post(f"{BASE}/runs", json=_payload(name="b")).json()
    client.post(f"{BASE}/runs/{other['id']}/execute",
                json={"create_experiment": False})
    cmp_resp = client.get(f"{BASE}/compare",
                          params={"a": run_id, "b": other["id"]})
    assert cmp_resp.status_code == 200
    assert cmp_resp.json()["fingerprint_match"]["universe"] is True
    assert client.get(f"{BASE}/compare",
                      params={"a": run_id, "b": run_id}).status_code == 422
    client.post(f"{BASE}/runs/{run_id}/invalidate", json={"reason": "t"})
    assert client.post(f"{BASE}/runs/{run_id}/invalidate",
                       json={"reason": "t"}).status_code == 409
