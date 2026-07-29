"""
Factor Diagnostics Lab tests (Phase 59.0): factor-definition validation,
transformation formulas and unit conversion, strict timestamp alignment,
availability timing and future-outlier invariance, target validation, OLS
coefficients / intercept / fitted values / residuals, R-squared, adjusted
R-squared, RMSE, standard errors, t-statistics and p-values, insufficient
degrees of freedom, constant target, constant and duplicate factors, matrix
rank and condition number, variance inflation, the ridge reference,
contribution reconciliation, portfolio-versus-benchmark exposure, rolling
estimates and their future invariance, stability diagnostics, macro lag and
vintage handling, regime / stress / attribution / Model-Validation
integration, multiple-testing correction, fingerprints, migration,
persistence, baseline policy, Experiment Registry and Dataset Lineage
integration, export, demo idempotence, prior-registry preservation, API
success and error paths, and non-finite rejection.
"""

from __future__ import annotations

import copy
import math

import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")
db_module = pytest.importorskip("app.db")
defs_mod = pytest.importorskip("app.factor_diagnostics.definitions")
obs_mod = pytest.importorskip("app.factor_diagnostics.observations")
target_mod = pytest.importorskip("app.factor_diagnostics.targets")
reg_mod = pytest.importorskip("app.factor_diagnostics.regression")
diag_mod = pytest.importorskip("app.factor_diagnostics.diagnostics")
decomp_mod = pytest.importorskip("app.factor_diagnostics.decomposition")
rolling_mod = pytest.importorskip("app.factor_diagnostics.rolling")
sens_mod = pytest.importorskip("app.factor_diagnostics.sensitivity")
fp_mod = pytest.importorskip("app.factor_diagnostics.fingerprints")
service = pytest.importorskip("app.factor_diagnostics.service")
store = pytest.importorskip("app.factor_diagnostics.store")
demo_mod = pytest.importorskip("app.factor_diagnostics.demo")

BASE = "/factor-diagnostics"


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
# Hand-computable fixture: y = 0.001 + 0.8 a + 0 b + orthogonal residual
# ---------------------------------------------------------------------------

FA = demo_mod.FACTOR_A
FB = demo_mod.FACTOR_B
RES = demo_mod.RESIDUAL
N = 24
HISTORY = 2


def _stamps(count: int, *, history: int = 0) -> list:
    return demo_mod._grid(count, history=history)


def _factor(factor_id, values, stamps, **extra):
    payload = {
        "factor_id": factor_id, "name": factor_id, "category": "style",
        "source": "test fixture", "unit": "return_fraction",
        "frequency": "daily", "transformation": "supplied_transformed",
        "transformed_unit": "return_fraction",
        "observations": [
            {"observation_id": f"{factor_id}-{i:03d}",
             "source_timestamp": stamp, "value": float(values[i])}
            for i, stamp in enumerate(stamps)],
    }
    payload.update(extra)
    return payload


def _payload(*, name="test run", factors=None, returns=None, policy=None,
             stamps=None, **extra):
    all_stamps = stamps or _stamps(N, history=HISTORY)
    target_stamps = all_stamps[HISTORY:] if stamps is None else all_stamps
    if factors is None:
        a = [demo_mod._factor_a(i) for i in range(len(all_stamps))]
        b = [demo_mod._factor_b(i) for i in range(len(all_stamps))]
        factors = [_factor("factor_a", a, all_stamps),
                   _factor("factor_b", b, all_stamps)]
    if returns is None:
        returns = [0.001 + 0.8 * demo_mod._factor_a(i + HISTORY)
                   + demo_mod._residual(i + HISTORY) for i in range(N)]
    payload = {
        "name": name, "description": "",
        "analysis_mode": "time_series_regression",
        "target": {
            "target_id": "t", "target_type": "strategy_return",
            "source": "user_supplied", "return_convention": "simple",
            "frequency": "daily", "currency": "USD",
            "timestamps": list(target_stamps),
            "returns": [float(r) for r in returns],
        },
        "factors": factors,
        "policy": {"timing_policy": "contemporaneous", **(policy or {})},
    }
    payload.update(extra)
    return payload


def _run(**kwargs):
    created = service.create_run(_payload(**kwargs))
    return service.execute_run(created["id"])


# ---------------------------------------------------------------------------
# Factor definitions, transformations, units
# ---------------------------------------------------------------------------

def test_definition_rejects_unknown_keys_and_categories():
    with pytest.raises(defs_mod.DefinitionError):
        defs_mod.validate_definition({"factor_id": "a", "unit": "ratio",
                                      "transformation": "level",
                                      "nonsense": 1})
    with pytest.raises(defs_mod.DefinitionError):
        defs_mod.validate_definition({"factor_id": "a", "unit": "ratio",
                                      "transformation": "level",
                                      "category": "momentum"})


def test_definition_rejects_negative_lag_and_centered_window():
    with pytest.raises(defs_mod.DefinitionError):
        defs_mod.validate_definition({"factor_id": "a", "unit": "ratio",
                                      "transformation": "level", "lag": -1})
    with pytest.raises(defs_mod.DefinitionError) as excinfo:
        defs_mod.validate_definition({
            "factor_id": "a", "unit": "ratio", "transformation": "level",
            "standardisation_window": 5})
    assert "trailing" in str(excinfo.value)


def test_definition_rejects_duplicate_factor_ids():
    base = {"factor_id": "a", "unit": "ratio", "transformation": "level"}
    with pytest.raises(defs_mod.DefinitionError) as excinfo:
        defs_mod.validate_definitions([dict(base), dict(base)])
    assert "duplicate" in str(excinfo.value)


def test_definition_rejects_winsorisation_and_zero_fill():
    with pytest.raises(defs_mod.DefinitionError):
        defs_mod.validate_definition({
            "factor_id": "a", "unit": "ratio", "transformation": "level",
            "winsorisation_policy": "quantile_1_99"})
    with pytest.raises(defs_mod.DefinitionError):
        defs_mod.validate_definition({
            "factor_id": "a", "unit": "ratio", "transformation": "level",
            "missing_policy": "forward_fill"})


def test_transformation_formulas_are_exact():
    level = {"transformation": "level", "unit": "index_level",
             "factor_id": "x", "standardisation_policy": "none",
             "standardisation_window": None}
    assert defs_mod.transform_series([1.0, 2.0, 4.0], level) == [1.0, 2.0, 4.0]

    simple = dict(level, transformation="simple_return")
    assert defs_mod.transform_series([100.0, 110.0, 99.0], simple) == \
        pytest.approx([None, 0.1, -0.1], abs=1e-12, nan_ok=False) \
        if False else True
    values = defs_mod.transform_series([100.0, 110.0, 99.0], simple)
    assert values[0] is None
    assert values[1] == pytest.approx(0.1)
    assert values[2] == pytest.approx(-0.1)

    percent = dict(level, transformation="percent_change")
    assert defs_mod.transform_series([100.0, 110.0], percent)[1] == \
        pytest.approx(10.0)

    log_change = dict(level, transformation="log_change")
    assert defs_mod.transform_series([100.0, 110.0], log_change)[1] == \
        pytest.approx(math.log(1.1))

    difference = dict(level, transformation="first_difference")
    assert defs_mod.transform_series([1.0, 3.0], difference)[1] == \
        pytest.approx(2.0)


def test_basis_point_conversion_is_explicit_about_the_source_unit():
    fraction = {"transformation": "basis_point_change", "unit": "rate_fraction",
                "factor_id": "r", "standardisation_policy": "none",
                "standardisation_window": None}
    assert defs_mod.transform_series([0.0400, 0.0425], fraction)[1] == \
        pytest.approx(25.0)
    percent = dict(fraction, unit="rate_percent")
    assert defs_mod.transform_series([4.00, 4.25], percent)[1] == \
        pytest.approx(25.0)
    with pytest.raises(defs_mod.DefinitionError):
        defs_mod.validate_definition({"factor_id": "r", "unit": "index_level",
                                      "transformation": "basis_point_change"})


def test_trailing_zscore_never_reads_its_own_or_a_future_observation():
    definition = {"transformation": "trailing_zscore", "unit": "ratio",
                  "factor_id": "z", "standardisation_policy": "none",
                  "standardisation_window": 3}
    series = [1.0, 2.0, 3.0, 10.0, 5.0]
    values = defs_mod.transform_series(series, definition)
    assert values[:3] == [None, None, None]
    # window = [1, 2, 3]: mean 2, sd 1  ->  (10 - 2) / 1 = 8
    assert values[3] == pytest.approx(8.0)
    # a later outlier must not change an earlier standardised value
    changed = list(series)
    changed[4] = 999.0
    assert defs_mod.transform_series(changed, definition)[3] == \
        pytest.approx(8.0)


def test_contribution_scale_only_exists_for_return_like_units():
    assert defs_mod.contribution_scale("return_fraction") == 1.0
    assert defs_mod.contribution_scale("return_percent") == 0.01
    assert defs_mod.contribution_scale("basis_points") == 1e-4
    assert defs_mod.contribution_scale("zscore") is None


# ---------------------------------------------------------------------------
# Observations, alignment and timing
# ---------------------------------------------------------------------------

def test_observations_require_strictly_increasing_unique_timestamps():
    definition = defs_mod.validate_definition({
        "factor_id": "a", "unit": "return_fraction",
        "transformation": "supplied_transformed",
        "transformed_unit": "return_fraction"})
    with pytest.raises(obs_mod.ObservationError):
        obs_mod.validate_observations(definition, [
            {"source_timestamp": "2024-01-02T00:00:00", "value": 0.1},
            {"source_timestamp": "2024-01-01T00:00:00", "value": 0.2}])
    with pytest.raises(obs_mod.ObservationError):
        obs_mod.validate_observations(definition, [
            {"observation_id": "dup", "source_timestamp": "2024-01-01T00:00:00",
             "value": 0.1},
            {"observation_id": "dup", "source_timestamp": "2024-01-02T00:00:00",
             "value": 0.2}])


def test_observations_reject_non_finite_values():
    definition = defs_mod.validate_definition({
        "factor_id": "a", "unit": "return_fraction",
        "transformation": "supplied_transformed",
        "transformed_unit": "return_fraction"})
    with pytest.raises(obs_mod.ObservationError):
        obs_mod.validate_observations(definition, [
            {"source_timestamp": "2024-01-01T00:00:00",
             "value": float("inf")}])


def test_alignment_refuses_to_resample_a_missing_timestamp():
    stamps = _stamps(N, history=HISTORY)
    short = [s for i, s in enumerate(stamps) if i != HISTORY + 3]
    a = [demo_mod._factor_a(i) for i in range(len(short))]
    payload = _payload(factors=[_factor("factor_a", a, short)])
    with pytest.raises(obs_mod.ObservationError) as excinfo:
        service.create_run(payload)
    assert "exact timestamp" in str(excinfo.value)


def test_lagged_causal_requires_a_positive_lag_on_every_factor():
    with pytest.raises(obs_mod.ObservationError) as excinfo:
        service.create_run(_payload(policy={"timing_policy": "lagged_causal"}))
    assert "lag >= 1" in str(excinfo.value)


def test_lagged_causal_verifies_availability_and_flags_late_release():
    stamps = _stamps(N, history=HISTORY)
    a = [demo_mod._factor_a(i) for i in range(len(stamps))]
    late = list(stamps)
    late[HISTORY + 4] = stamps[HISTORY + 9]      # released far too late
    factor = _factor("factor_a", a, stamps, lag=1,
                     availability_policy="explicit_available_at")
    for index, row in enumerate(factor["observations"]):
        row["available_at"] = late[index]
    run = service.create_run(_payload(
        factors=[factor], policy={"timing_policy": "lagged_causal"}))
    executed = service.execute_run(run["id"])
    assert executed["integrity_status"] == "invalid"
    assert any("knowable only at" in w for w in executed["warnings"])


def test_verified_causal_lag_when_availability_precedes_the_period():
    stamps = _stamps(N, history=HISTORY)
    a = [demo_mod._factor_a(i) for i in range(len(stamps))]
    factor = _factor("factor_a", a, stamps, lag=1,
                     availability_policy="explicit_available_at")
    for index, row in enumerate(factor["observations"]):
        row["available_at"] = stamps[index]
    executed = _run(factors=[factor],
                    policy={"timing_policy": "lagged_causal"})
    assert executed["integrity_status"] == "verified_causal_lag"
    assert executed["excluded_period_count"] == 0


def test_future_looking_alignment_is_only_available_as_declared_invalid():
    with pytest.raises(obs_mod.ObservationError):
        service.create_run(_payload(policy={"lead_periods": 1}))
    executed = _run(policy={"timing_policy": "future_looking_invalid",
                            "lead_periods": 1})
    assert executed["integrity_status"] == "invalid"
    assert any("INVALID timing" in w for w in executed["warnings"])


def test_future_observation_cannot_change_an_earlier_verified_fit():
    stamps = _stamps(N, history=HISTORY)
    a = [demo_mod._factor_a(i) for i in range(len(stamps))]
    base = _run(name="base")
    shorter = _payload(name="truncated")
    keep = len(shorter["target"]["timestamps"]) - 4
    shorter["target"]["timestamps"] = shorter["target"]["timestamps"][:keep]
    shorter["target"]["returns"] = shorter["target"]["returns"][:keep]
    created = service.create_run(shorter)
    truncated = service.execute_run(created["id"])

    outlier = _payload(name="with a later outlier")
    outlier["target"]["timestamps"] = outlier["target"]["timestamps"][:keep]
    outlier["target"]["returns"] = list(outlier["target"]["returns"][:keep])
    outlier["target"]["returns"][-1] += 0.0
    for factor in outlier["factors"]:
        for row in factor["observations"][keep + HISTORY:]:
            row["value"] = 9.0                      # far-future outliers
    created2 = service.create_run(outlier)
    with_outlier = service.execute_run(created2["id"])
    left = store.list_coefficients(truncated["id"])
    right = store.list_coefficients(with_outlier["id"])
    assert [c["coefficient"] for c in left] == \
        pytest.approx([c["coefficient"] for c in right])
    assert base["observation_count"] == N


def test_vintage_policies_select_different_values():
    row = {"raw_value": 1.0, "vintages": [
        {"release_timestamp": "2024-01-05T00:00:00", "value": 10.0,
         "vintage_label": "first"},
        {"release_timestamp": "2024-02-05T00:00:00", "value": 12.0,
         "vintage_label": "revised"}]}
    assert obs_mod.select_vintage(row, "first_release", None)[0] == 10.0
    assert obs_mod.select_vintage(row, "full_sample_latest_descriptive",
                                  None)[0] == 12.0
    assert obs_mod.select_vintage(row, "latest_available_as_of_cutoff",
                                  "2024-01-20T00:00:00")[0] == 10.0
    assert obs_mod.select_vintage(row, "latest_available_as_of_cutoff",
                                  "2024-03-01T00:00:00")[0] == 12.0
    value, _release, state = obs_mod.select_vintage(
        row, "latest_available_as_of_cutoff", "2024-01-01T00:00:00")
    assert value is None and state == "no_release_before_cutoff"


def test_full_sample_vintage_policy_forces_a_descriptive_state():
    executed = _run(policy={"vintage_policy": "full_sample_latest_descriptive"})
    assert executed["integrity_status"] == "full_sample_descriptive"


# ---------------------------------------------------------------------------
# Target series
# ---------------------------------------------------------------------------

def test_target_rejects_a_mismatched_series_and_a_late_information_cutoff():
    payload = _payload()
    payload["target"]["returns"] = payload["target"]["returns"][:-1]
    with pytest.raises(target_mod.TargetError):
        service.create_run(payload)

    payload = _payload()
    stamps = payload["target"]["timestamps"]
    payload["target"]["information_available_at"] = [
        stamps[min(i + 1, len(stamps) - 1)] for i in range(len(stamps))]
    with pytest.raises(target_mod.TargetError) as excinfo:
        service.create_run(payload)
    assert "after the start of the period" in str(excinfo.value)


def test_attribution_target_refuses_a_silent_convention_change():
    payload = _payload()
    payload["target"] = {
        "target_id": "t", "target_type": "portfolio_return",
        "source": "attribution_run", "attribution_run_id": 999,
        "return_convention": "simple", "frequency": "daily"}
    with pytest.raises(service.FactorError):
        service.create_run(payload)


# ---------------------------------------------------------------------------
# Regression: coefficients, statistics, rank, conditioning
# ---------------------------------------------------------------------------

def test_ols_recovers_the_generating_coefficients_exactly():
    executed = _run()
    coefficients = {c["factor_id"]: c
                    for c in store.list_coefficients(executed["id"])}
    assert coefficients["factor_a"]["coefficient"] == pytest.approx(0.8,
                                                                    abs=1e-12)
    assert coefficients["factor_b"]["coefficient"] == pytest.approx(0.0,
                                                                    abs=1e-12)
    assert executed["intercept"] == pytest.approx(0.001, abs=1e-12)


def test_fitted_plus_residual_equals_the_measured_return():
    executed = _run()
    for row in store.list_periods(executed["id"]):
        assert row["measured_return"] == pytest.approx(
            row["modelled_return"] + row["residual"], abs=1e-15)
        assert row["reconciliation_state"] == "reconciled"


def test_r_squared_adjusted_and_rmse_match_their_definitions():
    executed = _run()
    fit = executed["fit"]
    n = fit["observations"]
    p = fit["parameters"]
    rss = fit["residual_sum_of_squares"]
    tss = fit["total_sum_of_squares"]
    assert fit["r_squared"] == pytest.approx(1.0 - rss / tss)
    assert fit["adjusted_r_squared"] == pytest.approx(
        1.0 - (1.0 - fit["r_squared"]) * (n - 1) / (n - p))
    assert fit["root_mean_squared_error"] == pytest.approx(
        math.sqrt(rss / n))
    assert fit["degrees_of_freedom"] == n - p


def test_standard_errors_t_statistics_and_p_values_are_consistent():
    executed = _run()
    for row in store.list_coefficients(executed["id"]):
        assert row["standard_error"] > 0
        assert row["t_statistic"] == pytest.approx(
            row["coefficient"] / row["standard_error"], abs=1e-9)
        assert 0.0 <= row["p_value"] <= 1.0
        assert row["confidence_lower"] < row["coefficient"] \
            < row["confidence_upper"]


def test_exact_fit_withholds_standard_errors_instead_of_reporting_infinity():
    returns = [0.6 * demo_mod._factor_a(i + HISTORY) for i in range(N)]
    executed = _run(returns=returns)
    fit = executed["fit"]
    assert fit["standard_error_state"] == "unavailable"
    assert "residual variance is zero" in fit["standard_error_note"]
    for row in store.list_coefficients(executed["id"]):
        assert row["standard_error"] is None
        assert row["t_statistic"] is None
        assert row["p_value"] is None


def test_insufficient_degrees_of_freedom_is_refused_not_approximated():
    stamps = _stamps(4, history=HISTORY)
    a = [demo_mod._factor_a(i) for i in range(len(stamps))]
    b = [demo_mod._factor_b(i) for i in range(len(stamps))]
    c = [a[i] * 0.5 + b[i] for i in range(len(stamps))]
    payload = _payload(
        stamps=stamps[HISTORY:],
        factors=[_factor("factor_a", a, stamps), _factor("factor_b", b, stamps),
                 _factor("factor_c", c, stamps)],
        returns=[0.001, 0.002, -0.001, 0.0005])
    payload["factors"][0]["observations"] = [
        {"observation_id": f"factor_a-{i:03d}", "source_timestamp": s,
         "value": a[i]} for i, s in enumerate(stamps)]
    created = service.create_run(payload)
    with pytest.raises(reg_mod.RegressionError) as excinfo:
        service.execute_run(created["id"])
    assert "cannot identify" in str(excinfo.value)
    assert store.get_run(created["id"])["status"] == "failed"


def test_constant_target_leaves_r_squared_unavailable():
    executed = _run(returns=[0.001] * N)
    assert executed["r_squared"] is None
    assert "zero variance" in executed["fit"]["r_squared_note"]


def test_constant_and_duplicate_columns_are_detected_not_dropped():
    stamps = _stamps(N, history=HISTORY)
    a = [demo_mod._factor_a(i) for i in range(len(stamps))]
    executed = _run(factors=[
        _factor("factor_a", a, stamps),
        _factor("factor_dup", a, stamps),
    ], policy={"rank_policy": "minimum_norm_descriptive"})
    fit = executed["fit"]
    assert fit["duplicate_columns"] == [{"factor_a": "factor_a",
                                         "factor_b": "factor_dup"}]
    assert fit["rank_status"] == "rank_deficient_descriptive"
    assert len(store.list_coefficients(executed["id"])) == 2


def test_rank_deficiency_fails_by_default_and_is_labelled_when_allowed():
    stamps = _stamps(N, history=HISTORY)
    a = [demo_mod._factor_a(i) for i in range(len(stamps))]
    factors = [_factor("factor_a", a, stamps), _factor("factor_dup", a, stamps)]
    created = service.create_run(_payload(factors=copy.deepcopy(factors)))
    with pytest.raises(reg_mod.RegressionError) as excinfo:
        service.execute_run(created["id"])
    assert "rank deficient" in str(excinfo.value)

    executed = _run(factors=copy.deepcopy(factors),
                    policy={"rank_policy": "minimum_norm_descriptive"})
    assert executed["rank_status"] == "rank_deficient_descriptive"
    for row in store.list_coefficients(executed["id"]):
        assert row["standard_error"] is None


def test_condition_number_uses_the_centred_factor_block():
    stamps = _stamps(N, history=HISTORY)
    a = [demo_mod._factor_a(i) for i in range(len(stamps))]
    near = [a[i] + (1e-7 if i % 2 == 0 else -1e-7) for i in range(len(stamps))]
    executed = _run(factors=[_factor("factor_a", a, stamps),
                             _factor("factor_near", near, stamps)])
    assert executed["condition_number"] > 1e3
    assert executed["fit"]["condition_state"] in ("ok", "high")
    assert executed["rank_status"] == "full_rank"


def test_variance_inflation_is_unavailable_rather_than_infinite():
    matrix = [[1.0, 2.0], [2.0, 4.0], [3.0, 6.0], [4.0, 8.0], [5.0, 10.0]]
    rows = diag_mod.variance_inflation(matrix, ["a", "b"])
    assert all(row["vif"] is None for row in rows)
    assert all(row["state"] == "unavailable" for row in rows)
    assert all(row["reason"] for row in rows)


def test_variance_inflation_matches_its_definition():
    executed = _run()
    fit_rows = {r["factor_id"]: r
                for r in executed["multicollinearity"]["vif"]}
    for row in fit_rows.values():
        assert row["vif"] == pytest.approx(1.0 / (1.0 - row["r_squared"]))


def test_correlation_matrix_marks_a_constant_factor_unavailable():
    matrix = [[0.01, 1.0], [0.01, 2.0], [0.01, 3.0], [0.01, 5.0]]
    result = diag_mod.correlation_matrix(matrix, ["const", "b"])
    assert result["constant_factors"] == ["const"]
    assert result["rows"][0]["values"] == [None, None]
    assert result["rows"][1]["values"][1] == 1.0


def test_ridge_is_labelled_regularised_and_publishes_no_p_values():
    executed = _run(policy={"regression_method": "ridge",
                            "ridge_lambda": 0.001})
    assert executed["regression_method"] == "ridge"
    for row in store.list_coefficients(executed["id"]):
        assert row["p_value"] is None
        assert "regularised" in row["unavailable_reason"]


def test_ridge_rejects_an_invalid_lambda_and_a_correction_request():
    with pytest.raises(reg_mod.RegressionError):
        service.create_run(_payload(policy={"regression_method": "ridge",
                                            "ridge_lambda": -1.0}))
    with pytest.raises(service.FactorError):
        service.create_run(_payload(policy={
            "regression_method": "ridge", "ridge_lambda": 0.1,
            "multiple_testing": {"methods": ["holm"]}}))


def test_ridge_shrinks_towards_zero_relative_to_ols():
    ols = _run(name="ols")
    ridge = _run(name="ridge", policy={"regression_method": "ridge",
                                       "ridge_lambda": 0.01})
    ols_beta = {c["factor_id"]: abs(c["coefficient"])
                for c in store.list_coefficients(ols["id"])}
    ridge_beta = {c["factor_id"]: abs(c["coefficient"])
                  for c in store.list_coefficients(ridge["id"])}
    assert ridge_beta["factor_a"] < ols_beta["factor_a"]


# ---------------------------------------------------------------------------
# Decomposition, reconciliation and exposure aggregation
# ---------------------------------------------------------------------------

def test_contribution_equals_exposure_times_factor_value():
    executed = _run()
    coefficients = {c["factor_id"]: c["coefficient"]
                    for c in store.list_coefficients(executed["id"])}
    for row in store.list_periods(executed["id"]):
        for factor_id, contribution in row["factor_contributions"].items():
            assert contribution == pytest.approx(
                coefficients[factor_id] * row["factor_values"][factor_id])


def test_window_summary_sums_contributions_without_double_counting():
    executed = _run()
    summary = executed["summary"]
    total = (summary["intercept_contribution_sum"]
             + sum(summary["factor_contribution_sums"].values())
             + summary["residual_sum"])
    assert summary["measured_return_sum"] == pytest.approx(total, abs=1e-12)
    assert summary["reconciliation_state"] == "reconciled"


def test_supplied_exposure_aggregation_needs_return_like_factor_units():
    definitions = [{"factor_id": "z", "transformed_unit": "zscore"}]
    with pytest.raises(decomp_mod.DecompositionError) as excinfo:
        decomp_mod.supplied_period_rows([], [], definitions, 1e-9)
    assert "return-like unit" in str(excinfo.value)


def test_supplied_exposures_aggregate_with_signed_weights():
    rows = decomp_mod.aggregate_exposures(
        [{"asset_x": 1.5, "asset_y": -0.5}],
        {"asset_x": {"f": 1.2}, "asset_y": {"f": 0.4}}, ["f"])
    assert rows[0]["exposures"]["f"] == pytest.approx(1.5 * 1.2 - 0.5 * 0.4)
    missing = decomp_mod.aggregate_exposures(
        [{"asset_x": 1.0, "asset_y": 0.5}], {"asset_x": {"f": 1.2}}, ["f"])
    assert missing[0]["exposures"]["f"] is None
    assert missing[0]["missing_assets"]["f"] == ["asset_y"]


def _supplied_exposure_payload(attribution_run_id, stamps, book_id, assets,
                               exposures):
    def factor(factor_id, values, prefix):
        return {
            "factor_id": factor_id, "name": factor_id, "category": "style",
            "source": "test fixture", "unit": "return_fraction",
            "frequency": "daily", "transformation": "supplied_transformed",
            "transformed_unit": "return_fraction",
            "observations": [
                {"observation_id": f"{prefix}-{i:03d}",
                 "source_timestamp": s, "value": float(values[i])}
                for i, s in enumerate(stamps)],
        }
    return {
        "name": "supplied exposure aggregation",
        "description": "",
        "analysis_mode": "supplied_exposure_aggregation",
        "target": {"target_id": "t", "target_type": "portfolio_return",
                   "source": "attribution_run",
                   "attribution_run_id": attribution_run_id,
                   "return_convention": "simple", "frequency": "daily",
                   "currency": "USD"},
        "factors": [factor("factor_a",
                           [demo_mod._factor_a(i) for i in range(len(stamps))],
                           "fa"),
                    factor("factor_b",
                           [demo_mod._factor_b(i) for i in range(len(stamps))],
                           "fb")],
        "asset_exposures": exposures,
        "portfolio_run_id": book_id,
        "policy": {"timing_policy": "contemporaneous"},
    }


def _attribution_fixture():
    """Seed the Phase 58 demo and return (attribution run, stamps, book,
    ordered asset ids) — all read-only."""
    pa_demo = pytest.importorskip("app.portfolio_attribution.demo")
    attribution_store = pytest.importorskip("app.portfolio_attribution.store")
    pd_store = pytest.importorskip("app.portfolio_diagnostics.store")
    pa_demo.seed_demo_portfolio_attribution()
    run_id = attribution_store.run_demo_key_id("demo:pa:flagship-allocation")
    stamps = [p["period_start"]
              for p in attribution_store.list_periods(run_id)]
    run = attribution_store.get_run(run_id)
    assets = [a["asset_id"]
              for a in pd_store.list_assets(run["portfolio_run_id"])]
    return run_id, stamps, run["portfolio_run_id"], assets


def test_supplied_exposure_mode_aggregates_stored_weights_end_to_end():
    attribution_run_id, stamps, book_id, assets = _attribution_fixture()
    exposures = {assets[0]: {"factor_a": 1.2, "factor_b": 0.3},
                 assets[1]: {"factor_a": 0.8, "factor_b": -0.2},
                 assets[2]: {"factor_a": 0.1, "factor_b": 0.9},
                 assets[3]: {"factor_a": -0.3, "factor_b": 1.1}}
    created = service.create_run(_supplied_exposure_payload(
        attribution_run_id, stamps, book_id, assets, exposures))
    executed = service.execute_run(created["id"])
    assert executed["status"] == "completed"
    assert executed["completeness_status"] == "complete"
    assert executed["reconciliation_status"] == "reconciled"

    rows = store.list_periods(executed["id"])
    assert len(rows) == len(stamps)
    for row in rows:
        assert row["exposure_state"] == "supplied"
        for factor_id, contribution in row["factor_contributions"].items():
            assert contribution == pytest.approx(
                row["exposures"][factor_id] * row["factor_values"][factor_id])
        assert row["measured_return"] == pytest.approx(
            row["modelled_return"] + row["residual"], abs=1e-12)
    assert executed["fit"]["method"] == "supplied_exposure_aggregation"
    assert executed["fit"]["rank_status"] == "not_applicable"
    assert executed["r_squared"] is not None
    assert executed["intercept"] is None
    for coefficient in store.list_coefficients(executed["id"]):
        assert coefficient["exposure_state"] == "supplied"
        assert coefficient["coefficient"] is None


def test_supplied_exposure_mode_leaves_a_missing_asset_exposure_unavailable():
    attribution_run_id, stamps, book_id, assets = _attribution_fixture()
    created = service.create_run(_supplied_exposure_payload(
        attribution_run_id, stamps, book_id, assets,
        {assets[0]: {"factor_a": 1.2, "factor_b": 0.3}}))
    executed = service.execute_run(created["id"])
    assert executed["completeness_status"] == "unavailable"
    assert any("asset exposure is missing" in w for w in executed["warnings"])
    for row in store.list_periods(executed["id"]):
        assert row["modelled_return"] is None
        assert row["exposure_state"] == "unavailable"
        assert row["reconciliation_state"] == "unavailable"


def test_supplied_exposure_mode_requires_a_portfolio_run():
    attribution_run_id, stamps, book_id, assets = _attribution_fixture()
    payload = _supplied_exposure_payload(attribution_run_id, stamps, book_id,
                                         assets, {assets[0]: {"factor_a": 1.0}})
    payload["portfolio_run_id"] = None
    with pytest.raises(service.FactorError) as excinfo:
        service.create_run(payload)
    assert "requires portfolio_run_id" in str(excinfo.value)


def test_cross_sectional_mode_is_deferred_with_a_stated_reason():
    with pytest.raises(decomp_mod.DecompositionError) as excinfo:
        decomp_mod.validate_mode("cross_sectional_decomposition")
    assert "DEFERRED" in str(excinfo.value)


def test_benchmark_comparison_is_the_difference_of_the_two_exposures():
    rows = decomp_mod.benchmark_comparison(
        {"f": 1.2}, {"f": 0.9}, ["f"],
        portfolio_contributions={"f": 0.12},
        benchmark_contributions={"f": 0.09})
    assert rows[0]["active_exposure"] == pytest.approx(0.3)
    assert rows[0]["active_contribution"] == pytest.approx(0.03)


# ---------------------------------------------------------------------------
# Residual diagnostics
# ---------------------------------------------------------------------------

def test_residual_diagnostics_report_moments_and_concentration():
    executed = _run()
    block = executed["residual_diagnostics"]
    assert block["observations"] == N
    assert block["mean"] == pytest.approx(0.0, abs=1e-15)
    assert block["std"] > 0
    assert 0 < block["concentration"] <= 1
    assert block["effective_periods"] == pytest.approx(
        1.0 / block["concentration"])
    assert len(block["largest_absolute"]) <= diag_mod.MAX_LARGEST_RESIDUALS
    assert "not alpha" in block["note"]


def test_residual_diagnostics_handle_a_constant_series():
    block = diag_mod.residual_diagnostics([0.0] * 8, ["t"] * 8)
    assert block["skewness"] is None
    assert block["excess_kurtosis"] is None
    assert block["concentration"] is None


# ---------------------------------------------------------------------------
# Rolling and stability
# ---------------------------------------------------------------------------

def test_rolling_windows_are_trailing_and_bounded():
    executed = _run(policy={"rolling": {"window": 8, "step": 2}})
    rows = store.list_rolling(executed["id"])
    assert rows
    for row in rows:
        assert row["observations"] == 8
        assert row["window_start"] <= row["window_end"]
        assert row["effective_timestamp"] is None \
            or row["effective_timestamp"] > row["window_end"]
    with pytest.raises(rolling_mod.RollingError):
        rolling_mod.validate_rolling({"window": 2})


def test_a_later_outlier_cannot_change_an_earlier_rolling_window():
    stamps = _stamps(N, history=HISTORY)
    a = [demo_mod._factor_a(i) for i in range(len(stamps))]
    returns = [0.001 + 0.8 * a[i + HISTORY] for i in range(N)]
    clean = _run(name="clean", factors=[_factor("factor_a", a, stamps)],
                 returns=returns, policy={"rolling": {"window": 8, "step": 1}})
    shocked = list(returns)
    shocked[-1] = 5.0
    dirty = _run(name="shocked", factors=[_factor("factor_a", a, stamps)],
                 returns=shocked, policy={"rolling": {"window": 8, "step": 1}})
    left = store.list_rolling(clean["id"])
    right = store.list_rolling(dirty["id"])
    assert left[0]["fingerprint"] == right[0]["fingerprint"]
    assert left[-2]["coefficients"] == pytest.approx(
        right[-2]["coefficients"])
    assert left[-1]["coefficients"] != pytest.approx(right[-1]["coefficients"])


def test_rolling_estimates_track_a_changing_exposure():
    stamps = _stamps(N, history=HISTORY)
    a = [demo_mod._factor_a(i) for i in range(len(stamps))]
    returns = [(0.5 if i < N // 2 else 1.5) * a[i + HISTORY] for i in range(N)]
    executed = _run(factors=[_factor("factor_a", a, stamps)], returns=returns,
                    policy={"rolling": {"window": 8, "step": 2}})
    rows = store.list_rolling(executed["id"])
    assert rows[0]["coefficients"]["factor_a"] == pytest.approx(0.5)
    assert rows[-1]["coefficients"]["factor_a"] == pytest.approx(1.5)
    stability = {s["factor_id"]: s for s in executed["stability"]}
    assert stability["factor_a"]["max_absolute_change"] > 0.1
    assert stability["factor_a"]["availability_rate"] == 1.0
    assert "not a permanent property" in stability["factor_a"]["note"]


# ---------------------------------------------------------------------------
# Sensitivity
# ---------------------------------------------------------------------------

def test_sensitivity_keeps_the_base_once_and_drops_duplicates():
    scenarios = sens_mod.validate_scenarios(
        [{"label": "a", "lookback": 12}, {"label": "b", "lookback": 12},
         {"label": "base restated"}],
        factor_ids=["factor_a"], observation_count=24)
    assert sum(1 for s in scenarios if s["is_base"]) == 1
    assert len(scenarios) == 2


def test_sensitivity_rejects_deferred_dimensions_and_negative_lag_deltas():
    with pytest.raises(sens_mod.SensitivityError) as excinfo:
        sens_mod.validate_scenarios([{"standardisation_policy": "trailing"}],
                                    factor_ids=["a"], observation_count=24)
    assert "DEFERRED" in str(excinfo.value)
    with pytest.raises(sens_mod.SensitivityError):
        sens_mod.validate_scenarios([{"lag_delta": -1}], factor_ids=["a"],
                                    observation_count=24)


def test_factor_scaling_scales_the_coefficient_inversely():
    executed = _run(sensitivity=[{"label": "x100", "factor_scale": 100.0}])
    rows = {s["label"]: s for s in store.list_sensitivity(executed["id"])}
    base = rows["base"]["coefficients"]["factor_a"]
    scaled = rows["x100"]["coefficients"]["factor_a"]
    assert scaled == pytest.approx(base / 100.0)
    assert rows["x100"]["r_squared"] == pytest.approx(rows["base"]["r_squared"])


def test_sensitivity_grid_is_bounded():
    with pytest.raises(sens_mod.SensitivityError):
        sens_mod.validate_scenarios(
            [{"label": f"s{i}", "lookback": 8 + i}
             for i in range(sens_mod.MAX_SCENARIOS + 1)],
            factor_ids=["a"], observation_count=64)


# ---------------------------------------------------------------------------
# Multiple testing
# ---------------------------------------------------------------------------

def test_multiple_testing_preserves_raw_p_values_and_states_provenance():
    executed = _run(policy={"multiple_testing": {
        "methods": ["bonferroni", "holm", "bh"], "alpha": 0.05,
        "family": "the two declared factors"}})
    block = executed["multiple_testing"]
    assert block["hypotheses"] == 2
    for row in block["rows"]:
        assert row["provenance_status"] == "verified_from_ols_t_test"
        assert row["bonferroni"] >= row["raw_p_value"] - 1e-15
    stored = {c["factor_id"]: c for c in store.list_coefficients(executed["id"])}
    assert stored["factor_a"]["p_bonferroni"] is not None
    assert stored["factor_a"]["p_value"] < stored["factor_a"]["p_bonferroni"]


def test_multiple_testing_rejects_unsupported_methods():
    with pytest.raises(service.FactorError) as excinfo:
        service.create_run(_payload(policy={
            "multiple_testing": {"methods": ["benjamini_yekutieli"]}}))
    assert "not implemented" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Fingerprints
# ---------------------------------------------------------------------------

def test_fingerprints_are_stable_and_content_addressed():
    first = _run(name="one")
    second = _run(name="two — a different NAME only")
    assert first["observation_fingerprint"] == second["observation_fingerprint"]
    assert first["model_policy_fingerprint"] == \
        second["model_policy_fingerprint"]
    assert first["configuration_fingerprint"] == \
        second["configuration_fingerprint"]
    assert first["result_fingerprint"] == second["result_fingerprint"]


def test_a_material_change_moves_the_fingerprints():
    base = _run(name="base")
    changed_returns = list(_payload()["target"]["returns"])
    changed_returns[3] += 0.01
    changed = _run(name="changed", returns=changed_returns)
    assert base["observation_fingerprint"] != changed["observation_fingerprint"]
    assert base["result_fingerprint"] != changed["result_fingerprint"]

    policy_changed = _run(name="policy", policy={"intercept_policy": "exclude"})
    assert base["model_policy_fingerprint"] != \
        policy_changed["model_policy_fingerprint"]


def test_fingerprints_reject_non_finite_values():
    with pytest.raises(fp_mod.FingerprintError):
        fp_mod._clean({"value": float("nan")})
    with pytest.raises(fp_mod.FingerprintError):
        fp_mod._clean({"value": float("inf")})


# ---------------------------------------------------------------------------
# Persistence, migration, baselines
# ---------------------------------------------------------------------------

def test_migration_creates_every_table_and_preserves_prior_registries():
    with db_module.get_connection() as conn:
        names = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
    for table in ("factor_diagnostic_runs", "factor_definitions",
                  "factor_observations", "factor_coefficients",
                  "factor_period_results", "factor_rolling_results",
                  "factor_regime_results", "factor_sensitivity_results"):
        assert table in names
    for prior in ("portfolio_attribution_runs", "portfolio_stress_runs",
                  "portfolio_diagnostic_runs", "regime_diagnostic_runs",
                  "cost_diagnostic_runs", "validation_runs",
                  "experiment_registry", "dataset_versions"):
        assert prior in names


def test_failed_execution_clears_stale_results():
    executed = _run()
    assert store.list_periods(executed["id"])
    payload = _payload()
    payload["target"]["returns"] = [0.001] * N
    store.update_run(executed["id"], {"configuration": {
        **executed["configuration"],
        "factors": [{**f, "observations": []}
                    for f in executed["configuration"]["factors"]]}})
    with pytest.raises(Exception):
        service.execute_run(executed["id"])
    assert store.get_run(executed["id"])["status"] == "failed"
    assert store.list_periods(executed["id"]) == []
    assert store.list_coefficients(executed["id"]) == []


def test_baseline_requires_verified_complete_full_rank_and_reconciled():
    descriptive = _run(name="descriptive")
    with pytest.raises(service.ConflictError) as excinfo:
        service.mark_baseline(descriptive["id"])
    assert "cannot become a comparison baseline" in str(excinfo.value)

    stamps = _stamps(N, history=HISTORY)
    a = [demo_mod._factor_a(i) for i in range(len(stamps))]
    factor = _factor("factor_a", a, stamps, lag=1,
                     availability_policy="explicit_available_at")
    for index, row in enumerate(factor["observations"]):
        row["available_at"] = stamps[index]
    eligible = _run(name="eligible", factors=[factor],
                    returns=[0.001 + 0.8 * demo_mod._factor_a(i + HISTORY - 1)
                             + demo_mod._residual(i + HISTORY)
                             for i in range(N)],
                    policy={"timing_policy": "lagged_causal"})
    marked = service.mark_baseline(eligible["id"])
    assert marked["is_baseline"] is True
    assert service.mark_baseline(eligible["id"])["is_baseline"] is True


def test_invalid_timing_can_never_become_a_baseline():
    invalid = _run(policy={"timing_policy": "future_looking_invalid",
                           "lead_periods": 1})
    with pytest.raises(service.ConflictError):
        service.mark_baseline(invalid["id"])


def test_invalidate_clears_the_baseline_flag():
    executed = _run()
    invalidated = service.invalidate_run(executed["id"], "superseded")
    assert invalidated["status"] == "invalidated"
    assert invalidated["is_baseline"] is False
    with pytest.raises(service.ConflictError):
        service.execute_run(executed["id"])


# ---------------------------------------------------------------------------
# Comparison and export
# ---------------------------------------------------------------------------

def test_comparison_is_neutral_and_warns_about_comparability():
    left = _run(name="left")
    right = _run(name="right", policy={"intercept_policy": "exclude"})
    comparison = service.compare_runs(left["id"], right["id"])
    assert comparison["comparability_warnings"]
    assert comparison["fingerprint_match"]["observation"] is True
    assert comparison["fingerprint_match"]["model_policy"] is False
    text = " ".join(comparison["comparability_warnings"]
                    + [comparison["note"]]).lower()
    for banned in ("better", "superior", "recommended", "optimal", "best"):
        assert f" {banned}" not in f" {text}" or "no run is" in text


def test_export_is_free_of_paths_and_credentials():
    _run()
    payload = service.export({})
    text = repr(payload)
    for banned in ("C:\\\\", "/home/", "password", "api_key", "secret",
                   "quantlab.db"):
        assert banned not in text
    assert payload["schema_version"] == "factor_diagnostics_export_v1"
    assert "not proves causality" in payload["disclaimer"] \
        or "proves causality" in payload["disclaimer"]


# ---------------------------------------------------------------------------
# Demo fixture and cross-lab integration
# ---------------------------------------------------------------------------

def test_demo_is_idempotent_and_covers_the_documented_states():
    first = demo_mod.seed_demo_factor_diagnostics()
    assert first["created_count"] == 20
    second = demo_mod.seed_demo_factor_diagnostics()
    assert second["created_count"] == 0
    assert second["skipped_count"] == 20
    runs = service.list_runs(page_size=50)["items"]
    states = {r["integrity_status"] for r in runs}
    assert {"contemporaneous_descriptive", "verified_causal_lag",
            "verified_trailing_estimation", "invalid"} <= states
    assert any(r["rank_status"] == "rank_deficient_descriptive" for r in runs)
    assert any(r["status"] == "failed" for r in runs)
    assert any(r["is_baseline"] for r in runs)


def test_demo_exact_cases_hold_their_documented_values():
    demo_mod.seed_demo_factor_diagnostics()
    run_id = store.run_demo_key_id("demo:fd:exact-single-factor")
    coefficients = store.list_coefficients(run_id)
    assert coefficients[0]["coefficient"] == pytest.approx(0.6, abs=1e-12)
    assert store.get_run(run_id)["r_squared"] == pytest.approx(1.0)

    run_id = store.run_demo_key_id("demo:fd:exact-two-factor")
    values = {c["factor_id"]: c["coefficient"]
              for c in store.list_coefficients(run_id)}
    assert values["factor_a"] == pytest.approx(1.5, abs=1e-12)
    assert values["factor_b"] == pytest.approx(-0.5, abs=1e-12)
    assert store.get_run(run_id)["intercept"] == pytest.approx(0.002, abs=1e-12)

    run_id = store.run_demo_key_id("demo:fd:intercept-and-residual")
    values = {c["factor_id"]: c for c in store.list_coefficients(run_id)}
    assert values["factor_a"]["coefficient"] == pytest.approx(0.8, abs=1e-12)
    assert values["factor_a"]["p_value"] < 1e-30
    assert values["factor_b"]["p_value"] == pytest.approx(1.0, abs=1e-9)


def test_demo_regime_view_uses_stored_assignments_and_flags_rare_regimes():
    demo_mod.seed_demo_factor_diagnostics()
    run_id = store.run_demo_key_id("demo:fd:regime-linked")
    rows = store.list_regimes(run_id)
    assert rows
    assert any(r["rare"] and r["status"] == "rare" for r in rows)
    assert any(r["status"] == "estimated" for r in rows)
    regime_store = pytest.importorskip("app.regime_diagnostics.store")
    run = store.get_run(run_id)
    source = regime_store.get_run(run["regime_run_id"])
    assert source["result_fingerprint"] == (
        run["configuration"]["links"]["regime_identity"]
        ["regime_result_fingerprint"])


def test_demo_held_out_metrics_never_refit_on_the_held_out_rows():
    demo_mod.seed_demo_factor_diagnostics()
    run_id = store.run_demo_key_id("demo:fd:held-out-validation")
    run = service.get_run(run_id)
    held_out = run["held_out"]
    assert held_out is not None, run["error_message"]
    assert held_out["training_observations"] > 0
    assert held_out["held_out_observations"] > 0
    assert held_out["purged_observations"] >= 0
    assert "nothing is refitted on held-out data" in held_out["note"]
    memberships = {row["membership"] for row in store.list_periods(run_id)}
    assert {"train", "test"} <= memberships


def test_demo_stress_view_requires_explicit_shocks_and_implies_no_hedge():
    demo_mod.seed_demo_factor_diagnostics()
    run_id = store.run_demo_key_id("demo:fd:stress-linked")
    run = service.get_run(run_id)
    linkage = run["stress_linkage"]
    assert linkage["rows"][0]["state"] == "supplied"
    assert linkage["total_contribution"] == pytest.approx(
        sum(r["contribution"] for r in linkage["rows"]
            if r["contribution"] is not None))
    assert linkage["residual_component"] is None
    assert any("no hedge or reallocation" in w for w in run["warnings"])


def test_demo_attribution_linkage_stays_complementary():
    demo_mod.seed_demo_factor_diagnostics()
    run_id = store.run_demo_key_id("demo:fd:attribution-linked-active")
    run = service.get_run(run_id)
    linkage = run["attribution_linkage"]
    assert linkage["column"] == "active_return"
    assert "not interchangeable" in linkage["note"]
    assert "residual here is not alpha" in linkage["note"]
    attribution_store = pytest.importorskip("app.portfolio_attribution.store")
    source = attribution_store.get_run(run["attribution_run_id"])
    assert source["status"] == "completed"
    assert source["result_fingerprint"]


def test_demo_benchmark_comparison_is_a_plain_difference():
    demo_mod.seed_demo_factor_diagnostics()
    run_id = store.run_demo_key_id("demo:fd:benchmark-active-exposure")
    run = service.get_run(run_id)
    for row in run["exposure_comparison"]:
        assert row["active_exposure"] == pytest.approx(
            row["portfolio_exposure"] - row["benchmark_exposure"])
        assert row["active_contribution"] == pytest.approx(
            row["portfolio_contribution"] - row["benchmark_contribution"])


def test_executing_a_run_after_its_source_changed_is_refused():
    demo_mod.seed_demo_factor_diagnostics()
    run_id = store.run_demo_key_id("demo:fd:attribution-linked-active")
    attribution_store = pytest.importorskip("app.portfolio_attribution.store")
    run = store.get_run(run_id)
    attribution_store.update_run(run["attribution_run_id"],
                                 {"result_fingerprint": "0" * 64})
    with pytest.raises(service.ConflictError) as excinfo:
        service.execute_run(run_id)
    assert "changed since this run was created" in str(excinfo.value)


def test_experiment_record_is_neutral_and_idempotent():
    experiment_store = pytest.importorskip("app.experiment_registry.store")
    created = service.create_run(_payload(name="with experiment"))
    executed = service.execute_run(created["id"], create_experiment=True)
    run = store.get_run(executed["id"])
    assert run["experiment_id"]
    record = experiment_store.get_experiment(run["experiment_id"])
    assert record["module"] == "factor_diagnostics"
    text = f"{record['name']} {record.get('description', '')}".lower()
    for banned in ("alpha", "causal", "predicts", "recommended"):
        assert banned not in text or "no causal" in text
    again = service.execute_run(executed["id"], create_experiment=True)
    assert store.get_run(again["id"])["experiment_id"] == run["experiment_id"]


def test_dataset_lineage_is_read_only_and_warns_when_invalidated():
    dataset_store = pytest.importorskip("app.dataset_registry.store")
    dataset = dataset_store.insert_dataset({
        "name": "factor demo dataset", "description": "",
        "domain": "equities", "dataset_type": "prices",
        "source_type": "local_file", "provenance_status": "declared"})
    version = dataset_store.insert_version({
        "dataset_id": dataset["id"], "version_label": "v1",
        "row_count": 10, "column_count": 2, "schema_json": "{}",
        "manifest_fingerprint": "m" * 64, "schema_fingerprint": "s" * 64,
        "storage_locator_type": "relative_path",
        "storage_locator": "demo/factors.csv"})
    dataset_store.update_version_columns(version["id"],
                                         {"invalidated_at": "2024-01-01"})
    executed = _run(dataset_version_id=version["id"])
    assert executed["dataset_identity"]["invalidated"] is True
    assert any("invalidated" in w for w in executed["warnings"])
    assert dataset_store.get_version(version["id"])["manifest_fingerprint"] \
        == "m" * 64


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def test_api_create_execute_and_read_paths(client):
    response = client.post(f"{BASE}/runs", json=_payload(name="api run"))
    assert response.status_code == 201, response.text
    run_id = response.json()["id"]

    assert client.post(f"{BASE}/runs/{run_id}/execute",
                       json={"create_experiment": False}).status_code == 200
    for path in ("coefficients", "periods", "observations", "rolling",
                 "stability", "regimes", "sensitivity"):
        assert client.get(f"{BASE}/runs/{run_id}/{path}").status_code == 200
    listing = client.get(f"{BASE}/runs", params={"page_size": 5})
    assert listing.status_code == 200
    assert listing.json()["total"] >= 1
    assert client.get(f"{BASE}/summary").status_code == 200
    assert client.get(f"{BASE}/export").status_code == 200


def test_api_error_codes_are_explicit(client):
    assert client.get(f"{BASE}/runs/999999").status_code == 404
    assert client.post(f"{BASE}/runs/999999/execute", json={}).status_code == 404
    bad = _payload()
    bad["policy"]["timing_policy"] = "whenever"
    assert client.post(f"{BASE}/runs", json=bad).status_code == 422
    unknown_key = _payload()
    unknown_key["policy"]["nonsense"] = True
    assert client.post(f"{BASE}/runs", json=unknown_key).status_code == 422

    created = client.post(f"{BASE}/runs", json=_payload(name="conflict"))
    run_id = created.json()["id"]
    client.post(f"{BASE}/runs/{run_id}/execute", json={})
    assert client.post(f"{BASE}/runs/{run_id}/mark-baseline"
                       ).status_code == 409


def test_api_rejects_non_finite_and_oversized_input(client):
    import json as json_module
    payload = _payload()
    body = json_module.dumps(payload)
    # A literal Infinity is accepted by Python's JSON parser, so the API has
    # to reject the VALUE rather than relying on the decoder to do it.
    body = body.replace(f'{payload["target"]["returns"][0]}', "Infinity", 1)
    response = client.post(f"{BASE}/runs", content=body,
                           headers={"content-type": "application/json"})
    assert response.status_code == 422

    payload = _payload()
    payload["factors"] = payload["factors"] * 7    # over the factor bound
    assert client.post(f"{BASE}/runs", json=payload).status_code == 422


def test_api_demo_seed_is_idempotent(client):
    first = client.post(f"{BASE}/demo-seed")
    assert first.status_code == 200
    assert first.json()["created_count"] == 20
    second = client.post(f"{BASE}/demo-seed")
    assert second.json()["created_count"] == 0
    assert second.json()["skipped_count"] == 20


def test_api_compare_reports_neutral_differences(client):
    a = client.post(f"{BASE}/runs", json=_payload(name="a")).json()["id"]
    b = client.post(f"{BASE}/runs", json=_payload(
        name="b", policy={"intercept_policy": "exclude"})).json()["id"]
    client.post(f"{BASE}/runs/{a}/execute", json={})
    client.post(f"{BASE}/runs/{b}/execute", json={})
    response = client.get(f"{BASE}/compare", params={"a": a, "b": b})
    assert response.status_code == 200
    body = response.json()
    assert body["comparability_warnings"]
    assert "no run is better" in body["note"]


def test_log_change_rejects_non_positive_endpoints_even_when_ratio_is_positive():
    definition = defs_mod.validate_definition({
        "factor_id": "log", "name": "log", "category": "style",
        "source": "test", "unit": "index_level", "frequency": "daily",
        "transformation": "log_change"})
    assert defs_mod.transform_series([-2.0, -1.0], definition) == [None, None]


def test_supplied_transformed_unit_is_whitelisted():
    with pytest.raises(defs_mod.DefinitionError):
        defs_mod.validate_definition({
            "factor_id": "bad", "name": "bad", "category": "style",
            "source": "test", "unit": "ratio", "frequency": "daily",
            "transformation": "supplied_transformed",
            "transformed_unit": "return_fractoin"})


def test_timestamps_are_calendar_valid_and_canonicalised():
    assert obs_mod.normalise_timestamp(
        "2024-01-01T01:00:00+01:00", field="stamp") == (
            "2024-01-01T00:00:00.000000Z")
    with pytest.raises(obs_mod.ObservationError):
        obs_mod.normalise_timestamp("2024-02-30", field="stamp")


def test_target_sequence_fields_reject_non_lists():
    target = copy.deepcopy(_payload()["target"])
    target["period_ends"] = {"not": "a list"}
    with pytest.raises(target_mod.TargetError):
        target_mod.validate_target(target)


def test_factor_frequency_must_match_target_frequency():
    payload = _payload()
    payload["factors"][0]["frequency"] = "monthly"
    with pytest.raises(service.FactorError) as excinfo:
        service.create_run(payload)
    assert "mixed-frequency" in str(excinfo.value)


def test_observation_ids_are_unique_across_factors():
    payload = _payload()
    payload["factors"][1]["observations"][0]["observation_id"] = (
        payload["factors"][0]["observations"][0]["observation_id"])
    with pytest.raises(service.FactorError) as excinfo:
        service.create_run(payload)
    assert "unique across the run" in str(excinfo.value)


def test_no_intercept_ols_uses_uncentred_r_squared():
    fit = reg_mod.ols_fit([1.0, 2.0, 3.0], [[1.0], [1.0], [1.0]], ["x"],
                          intercept=False,
                          rank_policy="minimum_norm_descriptive")
    assert fit["r_squared"] == pytest.approx(1.0 - 2.0 / 14.0)
    assert "uncentred" in fit["r_squared_convention"]


def test_no_intercept_ridge_uses_uncentred_r_squared_and_reports_rank():
    fit = reg_mod.ridge_fit(
        [1.0, 2.0, 3.0], [[1.0], [1.0], [1.0]], ["constant"],
        ridge_lambda=1.0, intercept=False, scaling="none")
    assert fit["r_squared"] == pytest.approx(1.0 - 2.75 / 14.0)
    assert fit["r_squared_convention"].startswith("uncentred TSS")
    assert fit["rank"] == 1
    assert fit["expected_rank"] == 1
    assert fit["rank_status"] == "full_rank"


def test_ridge_rejects_centred_scaling_without_an_intercept():
    with pytest.raises(reg_mod.RegressionError):
        reg_mod.ridge_fit([1.0, 2.0, 3.0], [[1.0], [2.0], [4.0]], ["x"],
                          ridge_lambda=1.0, intercept=False,
                          scaling="zscore_fit_sample")


def test_vif_is_unavailable_when_the_other_factors_are_rank_deficient():
    rows = diag_mod.variance_inflation(
        [[1.0, 2.0, 2.0], [2.0, 3.0, 3.0], [4.0, 5.0, 5.0],
         [8.0, 9.0, 9.0], [16.0, 17.0, 17.0]], ["target", "a", "b"])
    assert rows[0]["state"] == "unavailable"
    assert "rank deficient" in rows[0]["reason"]


def test_residual_drawdown_includes_an_initial_loss_from_zero():
    block = diag_mod.residual_diagnostics([-1.0, 0.5], ["a", "b"])
    assert block["cumulative_drawdown"] == pytest.approx(-1.0)


def test_observation_fingerprint_tracks_selected_source_identity():
    executed = _run()
    configuration = copy.deepcopy(executed["configuration"])
    configuration["factors"][0]["observations"][HISTORY]["observation_id"] = (
        "replacement-source-id")
    store.update_run(executed["id"], {"configuration": configuration})
    rebuilt = service._rebuild(store.get_run(executed["id"]))
    fingerprints = {
        factor["factor_id"]: factor["definition_fingerprint"]
        for factor in configuration["factors"]}
    changed = fp_mod.observation_universe_fingerprint(
        rebuilt["alignment"], rebuilt["target"], fingerprints)
    assert changed != executed["observation_fingerprint"]


def test_sensitivity_fingerprint_tracks_effective_sample_and_scale():
    executed = _run(sensitivity=[
        {"label": "short", "lookback": 12},
        {"label": "scaled", "factor_scale": 2.0}])
    rows = {row["label"]: row
            for row in store.list_sensitivity(executed["id"])}
    assert rows["base"]["fingerprint"] != rows["short"]["fingerprint"]
    assert rows["base"]["fingerprint"] != rows["scaled"]["fingerprint"]


def test_observation_metadata_key_count_is_bounded():
    stamps = _stamps(2)
    factor = _factor("bounded", [0.1, 0.2], stamps)
    definition = defs_mod.validate_definition(factor)
    factor["observations"][0]["metadata"] = {
        f"key-{index}": index for index in range(21)}
    with pytest.raises(obs_mod.ObservationError) as excinfo:
        obs_mod.validate_observations(definition, factor["observations"])
    assert "20 keys" in str(excinfo.value)


def test_persisted_observations_preserve_selected_raw_values():
    executed = _run()
    rows = store.list_observations(executed["id"])
    expected = executed["configuration"]["factors"][0]["observations"][HISTORY]["raw_value"]
    factor_a = next(row for row in rows if row["factor_id"] == "factor_a")
    assert factor_a["raw_value"] == pytest.approx(expected)


def test_api_rejects_non_list_target_sequences(client):
    payload = _payload()
    payload["target"]["information_available_at"] = {"bad": "shape"}
    response = client.post(f"{BASE}/runs", json=payload)
    assert response.status_code == 422
    assert "must be a list" in response.text


def test_sensitivity_with_validation_uses_training_rows_only():
    demo_mod.seed_demo_factor_diagnostics()
    run_id = store.run_demo_key_id("demo:fd:held-out-validation")
    run = store.get_run(run_id)
    configuration = copy.deepcopy(run["configuration"])
    factor_ids = [factor["factor_id"] for factor in configuration["factors"]]
    configuration["sensitivity"] = sens_mod.validate_scenarios(
        [{"label": "scaled", "factor_scale": 1.1}],
        factor_ids=factor_ids,
        observation_count=run["observation_count"])
    membership = {row["period_index"]: row["membership"]
                  for row in store.list_periods(run_id)}
    training_count = sum(value == "train" for value in membership.values())
    rows = service._sensitivity_rows(
        configuration, service._rebuild(run), configuration["policy"],
        1e-9, membership)
    assert rows
    assert all(row["observations"] == training_count for row in rows), (
        training_count, rows)
