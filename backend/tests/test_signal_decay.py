"""
Signal Decay Lab tests (Phase 60.0): signal/outcome/horizon validation,
entry-lag handling, future-data rejection and future-outlier invariance,
forward-return construction, overlap detection and deterministic non-overlap
selection, Pearson/Spearman/Kendall with ties/constants/small samples and
REAL p-values, cross-sectional IC, time-series lag alignment, buckets and
boundaries and tie policy, top-minus-bottom, monotonicity, decay curves and
sign-change detection and half-life validity, implementation lags, rank and
membership turnover, Jaccard, one-way turnover, holding-period overlap,
cost/regime/validation/meta-label/feature/factor integration, multiple
testing, bootstrap determinism, fingerprints, migration, persistence,
baselines, Experiment Registry and Dataset Lineage integration, export,
demo idempotence, prior-registry preservation, API paths and non-finite
rejection.
"""

from __future__ import annotations

import copy
import math

import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")
db_module = pytest.importorskip("app.db")
defs_mod = pytest.importorskip("app.signal_decay.definitions")
obs_mod = pytest.importorskip("app.signal_decay.observations")
stats_mod = pytest.importorskip("app.signal_decay.statistics")
bucket_mod = pytest.importorskip("app.signal_decay.buckets")
decay_mod = pytest.importorskip("app.signal_decay.decay")
turnover_mod = pytest.importorskip("app.signal_decay.turnover")
cost_mod = pytest.importorskip("app.signal_decay.costs")
boot_mod = pytest.importorskip("app.signal_decay.bootstrap")
fp_mod = pytest.importorskip("app.signal_decay.fingerprints")
service = pytest.importorskip("app.signal_decay.service")
store = pytest.importorskip("app.signal_decay.store")
demo_mod = pytest.importorskip("app.signal_decay.demo")

BASE = "/signal-decay"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_quantlab.db"
    monkeypatch.setattr(db_module, "_db_path_override", db_file)
    db_module.init_db()
    yield


@pytest.fixture
def client():
    return TestClient(main_module.app)


N = 30


def _payload(*, name="test run", n=N, step_returns=None, signal_values=None,
             horizons=None, lags=None, overlap_policy="overlapping",
             bucket_count=3, **extra):
    stamps = demo_mod._stamps(n)
    if signal_values is None:
        signal_values = [demo_mod._s(i) + i * 1e-6 for i in range(n)]
    if step_returns is None:
        step_returns = [0.01 * signal_values[i] for i in range(n - 1)]
    payload = {
        "name": name,
        "signal": {"signal_id": "test-signal", "name": "test",
                   "signal_type": "continuous_score", "unit": "score",
                   "source": "test", "frequency": "daily",
                   "direction": "higher_is_higher_score",
                   "availability_policy": "explicit_available_at"},
        "outcome": {"outcome_id": "fwd", "name": "fwd",
                    "target_type": "forward_return", "price_field": "close",
                    "source": "test"},
        "observations": demo_mod._signal_rows(stamps, signal_values),
        "prices": demo_mod._prices_from_returns(stamps, step_returns),
        "horizons": {"horizons": horizons or [1], "unit": "observations",
                     "entry_lags": lags or [0],
                     "overlap_policy": overlap_policy},
        "buckets": {"bucket_count": bucket_count, "scope": "global",
                    "minimum_per_bucket": 2},
    }
    payload.update(extra)
    return payload


def _run(**kwargs):
    created = service.create_run(_payload(**kwargs))
    return service.execute_run(created["id"])


def _raw_rows(run_id):
    return [r for r in store.list_horizons(run_id)
            if r["outcome_scope"] == "raw"
            and r["selection"] == "overlapping"]


# ---------------------------------------------------------------------------
# Definitions
# ---------------------------------------------------------------------------

def test_signal_definition_requires_explicit_direction():
    with pytest.raises(defs_mod.DefinitionError) as excinfo:
        defs_mod.validate_signal_definition({
            "signal_id": "s", "signal_type": "continuous_score",
            "unit": "score"})
    assert "never inferred from the signal's name" in str(excinfo.value)


def test_signal_definition_rejects_unknown_keys_and_policies():
    base = {"signal_id": "s", "signal_type": "continuous_score",
            "unit": "score", "direction": "higher_is_higher_score"}
    with pytest.raises(defs_mod.DefinitionError):
        defs_mod.validate_signal_definition({**base, "nonsense": 1})
    with pytest.raises(defs_mod.DefinitionError):
        defs_mod.validate_signal_definition({**base,
                                             "missing_policy": "forward_fill"})
    with pytest.raises(defs_mod.DefinitionError):
        defs_mod.validate_signal_definition({**base,
                                             "transformation": "zscore"})


def test_direction_inversion_is_explicit_and_preserves_raw_values():
    values = [1.0, -2.0, None, 3.0]
    oriented = defs_mod.oriented(values, "higher_is_lower_score")
    assert oriented == [-1.0, 2.0, None, -3.0]
    assert values == [1.0, -2.0, None, 3.0]


def test_outcome_definition_requires_price_field_for_forward_returns():
    with pytest.raises(defs_mod.DefinitionError):
        defs_mod.validate_outcome_definition({
            "outcome_id": "o", "target_type": "forward_return"})


# ---------------------------------------------------------------------------
# Observations, horizons and timing
# ---------------------------------------------------------------------------

def test_observations_reject_duplicates_and_non_finite_values():
    definition = defs_mod.validate_signal_definition({
        "signal_id": "s", "signal_type": "continuous_score", "unit": "score",
        "direction": "higher_is_higher_score",
        "availability_policy": "same_timestamp"})
    stamp = "2024-01-01T00:00:00"
    with pytest.raises(obs_mod.ObservationError):
        obs_mod.validate_signal_observations(definition, [
            {"entity_id": "a", "source_timestamp": stamp, "value": 1.0},
            {"entity_id": "a", "source_timestamp": stamp, "value": 2.0}])
    with pytest.raises(obs_mod.ObservationError):
        obs_mod.validate_signal_observations(definition, [
            {"entity_id": "a", "source_timestamp": stamp,
             "value": float("inf")}])


def test_explicit_availability_is_required_and_never_fabricated():
    definition = defs_mod.validate_signal_definition({
        "signal_id": "s", "signal_type": "continuous_score", "unit": "score",
        "direction": "higher_is_higher_score",
        "availability_policy": "explicit_available_at"})
    with pytest.raises(obs_mod.ObservationError) as excinfo:
        obs_mod.validate_signal_observations(definition, [
            {"entity_id": "a", "source_timestamp": "2024-01-01T00:00:00",
             "value": 1.0}])
    assert "never fabricated" in str(excinfo.value)


def test_horizons_reject_clock_units_negative_lags_and_duplicates():
    with pytest.raises(obs_mod.ObservationError) as excinfo:
        obs_mod.validate_horizons({"horizons": [1], "unit": "days"},
                                  supplied_outcomes=False)
    assert "deferred" in str(excinfo.value)
    with pytest.raises(obs_mod.ObservationError):
        obs_mod.validate_horizons({"horizons": [1], "entry_lags": [-1]},
                                  supplied_outcomes=False)
    with pytest.raises(obs_mod.ObservationError):
        obs_mod.validate_horizons({"horizons": [2, 2]},
                                  supplied_outcomes=False)
    with pytest.raises(obs_mod.ObservationError):
        obs_mod.validate_horizons({"horizons": [0]}, supplied_outcomes=False)


def test_supplied_outcomes_cannot_be_shifted_or_reconstructed():
    with pytest.raises(obs_mod.ObservationError) as excinfo:
        obs_mod.validate_horizons({"entry_lags": [1]}, supplied_outcomes=True)
    assert "never reconstructs" in str(excinfo.value)


def test_forward_return_formula_and_timestamp_shift_under_lag():
    executed = _run(n=10, horizons=[2], lags=[1])
    rows = _raw_rows(executed["id"])
    assert rows[0]["observations"] == 7  # 10 obs, entry i+1, exit i+3
    # Rebuild by hand from the stored configuration.
    run = store.get_run(executed["id"])
    prices = {(e, t): v for e, t, v in run["configuration"]["prices"]}
    stamps = demo_mod._stamps(10)
    expected_first = (prices[("aggregate", stamps[3])]
                      / prices[("aggregate", stamps[1])] - 1.0)
    detail = rows[0]["detail"]["correlations"]["pearson"]
    assert detail["observations"] == 7
    built = obs_mod.build_pairs(
        run["configuration"]["observations"], target_type="forward_return",
        prices=prices, supplied=None, horizon=2, entry_lag=1,
        extreme_loss_policy="report_verbatim")
    first = built["pairs"][0]
    assert first["entry_timestamp"] == stamps[1]
    assert first["exit_timestamp"] == stamps[3]
    assert first["outcome_value"] == pytest.approx(expected_first)


def test_missing_prices_stay_unavailable_never_interpolated():
    payload = _payload(n=12)
    payload["prices"][5]["close"] = None
    created = service.create_run(payload)
    executed = service.execute_run(created["id"])
    rows = _raw_rows(executed["id"])
    unavailable = rows[0]["detail"]["unavailable"]
    assert any("missing" in u["reason"] and "never interpolated"
               in u["reason"] for u in unavailable)
    assert executed["completeness_status"] == "partial"


def test_outcome_before_availability_marks_the_run_invalid():
    stamps = demo_mod._stamps(8)
    later = demo_mod._stamps(9)
    payload = {
        "name": "invalid", "signal": {
            "signal_id": "late", "signal_type": "continuous_score",
            "unit": "score", "direction": "higher_is_higher_score",
            "availability_policy": "explicit_available_at"},
        "outcome": {"outcome_id": "sup", "target_type": "supplied_outcome",
                    "unit": "score", "source": "test"},
        "observations": [
            {"entity_id": "a", "source_timestamp": s,
             "available_at": later[i + 1], "value": float(i)}
            for i, s in enumerate(stamps)],
        "supplied_outcomes": [
            {"entity_id": "a", "signal_timestamp": s, "period_start": s,
             "period_end": later[i + 1], "value": 0.01 * i}
            for i, s in enumerate(stamps)],
        "horizons": {"unit": "observations"},
        "buckets": {"bucket_count": 2, "minimum_per_bucket": 2},
    }
    created = service.create_run(payload)
    executed = service.execute_run(created["id"])
    assert executed["integrity_status"] == "invalid"
    assert any("INVALID timing" in w for w in executed["warnings"])
    with pytest.raises(service.ConflictError):
        service.mark_baseline(executed["id"])


def test_future_outlier_cannot_change_earlier_pairs():
    clean = _run(name="clean", n=20)
    payload = _payload(name="shocked", n=20)
    payload["prices"][-1]["close"] = 999999.0   # far-future price shock
    created = service.create_run(payload)
    shocked = service.execute_run(created["id"])
    clean_rows = store.list_horizons(clean["id"])
    shocked_rows = store.list_horizons(shocked["id"])
    # every pair except the last one is identical; the correlation uses the
    # last pair too, so compare the stored per-pair outcomes instead
    clean_run = store.get_run(clean["id"])
    prices = {(e, t): v for e, t, v in clean_run["configuration"]["prices"]}
    built = obs_mod.build_pairs(
        clean_run["configuration"]["observations"],
        target_type="forward_return", prices=prices, supplied=None,
        horizon=1, entry_lag=0, extreme_loss_policy="report_verbatim")
    shocked_run = store.get_run(shocked["id"])
    shocked_prices = {(e, t): v
                      for e, t, v in shocked_run["configuration"]["prices"]}
    shocked_built = obs_mod.build_pairs(
        shocked_run["configuration"]["observations"],
        target_type="forward_return", prices=shocked_prices, supplied=None,
        horizon=1, entry_lag=0, extreme_loss_policy="report_verbatim")
    for a, b in zip(built["pairs"][:-1], shocked_built["pairs"][:-1]):
        assert a["outcome_value"] == pytest.approx(b["outcome_value"])
    assert built["pairs"][-1]["outcome_value"] != pytest.approx(
        shocked_built["pairs"][-1]["outcome_value"])
    assert clean_rows[0]["observations"] == shocked_rows[0]["observations"]


def test_cross_sectional_ranks_use_only_the_contemporaneous_universe():
    stamps = demo_mod._stamps(6)
    observations = []
    prices = []
    for k, entity in enumerate(["a", "b", "c", "d"]):
        values = [float((i + k) % 4) for i in range(len(stamps))]
        observations.extend(demo_mod._signal_rows(stamps, values,
                                                  entity_id=entity))
        prices.extend(demo_mod._prices_from_returns(
            stamps, [0.001 * values[i] for i in range(len(stamps) - 1)],
            entity_id=entity))
    payload = {
        "name": "cs", "signal": {
            "signal_id": "cs", "signal_type": "continuous_score",
            "unit": "score", "direction": "higher_is_higher_score",
            "availability_policy": "explicit_available_at",
            "transformation": "rank_cross_sectional"},
        "outcome": {"outcome_id": "fwd", "target_type": "forward_return",
                    "price_field": "close", "source": "test"},
        "observations": observations, "prices": prices,
        "horizons": {"horizons": [1], "unit": "observations",
                     "entry_lags": [0]},
        "buckets": {"bucket_count": 2, "scope": "per_timestamp",
                    "minimum_per_bucket": 1},
    }
    created = service.create_run(payload)
    executed = service.execute_run(created["id"])
    rows = _raw_rows(executed["id"])
    ic = rows[0]["detail"]["cross_sectional_ic"]
    assert ic["aggregate"]["mean_spearman_ic"] == pytest.approx(1.0)
    for row in ic["rows"]:
        assert row["eligible_entities"] == 4
    # ranks were computed per timestamp: every stamp has ranks 1..4
    stored = store.list_observations(executed["id"])
    by_stamp = {}
    for o in stored:
        by_stamp.setdefault(o["source_timestamp"], []).append(o["rank_value"])
    for ranks in by_stamp.values():
        assert sorted(ranks) == [1.0, 2.0, 3.0, 4.0]


def test_full_sample_ranking_forces_a_descriptive_state():
    payload = _payload()
    payload["signal"]["transformation"] = "rank_full_sample"
    created = service.create_run(payload)
    executed = service.execute_run(created["id"])
    assert executed["integrity_status"] == "full_sample_descriptive"


# ---------------------------------------------------------------------------
# Overlap
# ---------------------------------------------------------------------------

def test_overlap_detection_and_deterministic_selection():
    executed = _run(n=20, horizons=[4], overlap_policy="non_overlapping")
    rows = store.list_horizons(executed["id"])
    overlapping = next(r for r in rows if r["selection"] == "overlapping")
    selected = next(r for r in rows if r["selection"] == "non_overlapping")
    assert overlapping["overlap_state"] == "overlapping"
    assert overlapping["overlap_ratio"] == pytest.approx(1.0)
    assert overlapping["max_simultaneous_overlap"] == 4
    assert overlapping["p_value_note"] is not None
    assert selected["overlap_state"] == "non_overlapping"
    # earliest-first: entries at indices 0, 4, 8, 12 -> exits 4, 8, 12, 16
    assert selected["observations"] == 4
    assert selected["p_value_note"] is None
    assert overlapping["effective_non_overlapping"] == math.ceil(
        overlapping["observations"] / 4)


def test_back_to_back_intervals_do_not_overlap():
    pairs = [{"entity_id": "a", "entry_index": 0, "exit_index": 2,
              "entry_timestamp": "t0", "exit_timestamp": "t2"},
             {"entity_id": "a", "entry_index": 2, "exit_index": 4,
              "entry_timestamp": "t2", "exit_timestamp": "t4"}]
    overlap = obs_mod._overlap_from_intervals(pairs, by_stamp=False)
    assert overlap["overlapping_interval_count"] == 0
    assert overlap["state"] == "non_overlapping"


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def test_correlations_are_real_scipy_values():
    scipy_stats = pytest.importorskip("scipy.stats")
    x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    y = [1.2, 1.9, 3.4, 3.9, 5.1, 5.8]
    result = stats_mod.correlation(x, y, method="pearson",
                                   minimum_observations=4,
                                   overlapping=False)
    expected = scipy_stats.pearsonr(x, y)
    assert result["statistic"] == pytest.approx(float(expected.statistic))
    assert result["p_value"] == pytest.approx(float(expected.pvalue))
    kendall = stats_mod.correlation(x, y, method="kendall",
                                    minimum_observations=4,
                                    overlapping=False)
    assert kendall["statistic"] == pytest.approx(
        float(scipy_stats.kendalltau(x, y).statistic))


def test_constant_series_and_small_samples_are_unavailable():
    constant = stats_mod.correlation([1, 1, 1, 1], [1, 2, 3, 4],
                                     method="spearman",
                                     minimum_observations=4,
                                     overlapping=False)
    assert constant["state"] == "unavailable"
    assert "constant" in constant["reason"]
    small = stats_mod.correlation([1, 2], [1, 2], method="pearson",
                                  minimum_observations=4, overlapping=False)
    assert small["state"] == "unavailable"
    assert "below the minimum" in small["reason"]


def test_tie_counts_are_reported():
    result = stats_mod.correlation([1, 1, 2, 2, 3], [1, 2, 3, 4, 5],
                                   method="spearman",
                                   minimum_observations=4, overlapping=False)
    assert result["signal_tie_count"] == 4
    assert result["unique_signal_values"] == 3


def test_overlapping_p_values_carry_the_limitation():
    result = stats_mod.correlation([1, 2, 3, 4, 5], [1, 2, 3, 4, 5],
                                   method="spearman",
                                   minimum_observations=4, overlapping=True)
    assert result["p_value_note"] is not None
    assert "overlap" in result["p_value_note"]


def test_signal_autocorrelation_is_distinct_from_prediction():
    rows = stats_mod.signal_autocorrelation([1.0, 2.0, 1.0, 2.0, 1.0, 2.0,
                                             1.0, 2.0], max_lag=2)
    assert rows[0]["autocorrelation"] == pytest.approx(-1.0)
    assert rows[1]["autocorrelation"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Buckets, spread, monotonicity
# ---------------------------------------------------------------------------

def test_bucket_boundaries_counts_and_monotone_means():
    executed = _run(n=60, bucket_count=5)
    buckets = [b for b in store.list_buckets(executed["id"])
               if b["outcome_scope"] == "raw"]
    assert len(buckets) == 5
    counts = [b["observations"] for b in buckets]
    assert sum(counts) == 59
    assert max(counts) - min(counts) <= 1
    means = [b["mean_outcome"] for b in buckets]
    assert all(means[i] < means[i + 1] for i in range(4))
    for b in buckets:
        assert b["score_minimum"] is not None
        assert b["score_maximum"] is not None
    rows = _raw_rows(executed["id"])
    assert rows[0]["monotonicity_spearman"] == pytest.approx(1.0)
    assert rows[0]["top_minus_bottom"] == pytest.approx(
        means[-1] - means[0])


def test_tie_split_spread_is_conservatively_unavailable():
    values = [1.0 if i % 2 == 0 else 0.0 for i in range(N)]
    executed = _run(signal_values=values,
                    step_returns=[0.01 * values[i] for i in range(N - 1)],
                    bucket_count=3)
    rows = _raw_rows(executed["id"])
    assert rows[0]["top_minus_bottom"] is None
    assert "unique score" in rows[0]["detail"]["spread"]["reason"]


def test_non_monotonic_buckets_report_violations():
    values = [demo_mod._s(i) for i in range(60)]
    executed = _run(n=60, signal_values=values,
                    step_returns=[0.01 * abs(values[i]) for i in range(59)],
                    bucket_count=5)
    rows = _raw_rows(executed["id"])
    mono = rows[0]["detail"]["monotonicity"]
    assert mono["adjacent_violations"] > 0
    assert "do not prove predictability" in mono["note"]


def test_empty_bucket_stays_visible():
    outcomes = bucket_mod.bucket_outcomes(
        [{"outcome_value": 1.0}], [1], bucket_count=3, minimum_per_bucket=1)
    assert outcomes[1]["state"] == "unavailable"
    assert "empty bucket" in outcomes[1]["reason"]
    spread = bucket_mod.top_minus_bottom(outcomes, bucket_count=3)
    assert spread["state"] == "unavailable"
    assert "never substituted" in spread["reason"]


# ---------------------------------------------------------------------------
# Decay
# ---------------------------------------------------------------------------

def test_decay_summary_locates_sign_change_and_threshold():
    rows = [{"horizon": 1, "spearman": 0.8},
            {"horizon": 2, "spearman": 0.4},
            {"horizon": 3, "spearman": 0.05},
            {"horizon": 4, "spearman": -0.2}]
    summary = decay_mod.decay_summary(rows, statistic_key="spearman",
                                      absolute_threshold=0.1)
    assert summary["first_sign_change_horizon"] == 4
    assert summary["first_below_threshold_horizon"] == 3
    assert summary["max_absolute_statistic"] == pytest.approx(0.8)
    assert summary["max_absolute_horizon"] == 1
    assert "never an optimal or recommended horizon" in summary["note"]


def test_half_life_requires_a_coherent_exponential_fit():
    clean = [{"horizon": h, "spearman": 0.8 * math.exp(-0.3 * h)}
             for h in (1, 2, 3, 4, 5)]
    summary = decay_mod.decay_summary(clean, statistic_key="spearman",
                                      absolute_threshold=None)
    fit = summary["exponential_fit"]
    assert fit["state"] == "available"
    assert fit["half_life"] == pytest.approx(math.log(2) / 0.3, rel=1e-6)

    mixed = [{"horizon": 1, "spearman": 0.5},
             {"horizon": 2, "spearman": -0.3},
             {"horizon": 3, "spearman": 0.2}]
    summary = decay_mod.decay_summary(mixed, statistic_key="spearman",
                                      absolute_threshold=None)
    assert summary["exponential_fit"]["state"] == "unavailable"
    assert "changes sign" in summary["exponential_fit"]["reason"]

    growing = [{"horizon": h, "spearman": 0.1 * h} for h in (1, 2, 3, 4)]
    summary = decay_mod.decay_summary(growing, statistic_key="spearman",
                                      absolute_threshold=None)
    assert summary["exponential_fit"]["half_life"] is None
    assert "no half-life" in summary["exponential_fit"]["reason"]


# ---------------------------------------------------------------------------
# Implementation lags
# ---------------------------------------------------------------------------

def test_lag_grid_shifts_entry_and_exit_together():
    executed = _run(n=40, horizons=[2], lags=[0, 1, 2])
    rows = sorted(_raw_rows(executed["id"]), key=lambda r: r["entry_lag"])
    assert [r["entry_lag"] for r in rows] == [0, 1, 2]
    assert [r["observations"] for r in rows] == [38, 37, 36]
    run = store.get_run(executed["id"])
    prices = {(e, t): v for e, t, v in run["configuration"]["prices"]}
    stamps = demo_mod._stamps(40)
    for lag in (0, 1, 2):
        built = obs_mod.build_pairs(
            run["configuration"]["observations"],
            target_type="forward_return", prices=prices, supplied=None,
            horizon=2, entry_lag=lag,
            extreme_loss_policy="report_verbatim")
        first = built["pairs"][0]
        assert first["entry_timestamp"] == stamps[lag]
        assert first["exit_timestamp"] == stamps[lag + 2]


# ---------------------------------------------------------------------------
# Turnover and holding overlap
# ---------------------------------------------------------------------------

def test_one_way_turnover_formula_and_initial_policy():
    previous = {"a", "b"}
    current = {"b", "c"}
    value = turnover_mod.one_way_turnover(previous, current,
                                          initial_policy="no_prior_unavailable")
    assert value == pytest.approx(0.5)
    assert turnover_mod.one_way_turnover(
        None, {"a"}, initial_policy="no_prior_unavailable") is None
    assert turnover_mod.one_way_turnover(
        None, {"a"}, initial_policy="zero_prior_full_build") == 1.0


def test_membership_timeline_jaccard_and_holding_duration():
    demo_mod.seed_demo_signal_decay.__wrapped__ if False else None
    pairs = []
    assignments = []
    stamps = demo_mod._stamps(4)
    for i, stamp in enumerate(stamps):
        for k, entity in enumerate(["a", "b", "c"]):
            pairs.append({"entity_id": entity, "signal_timestamp": stamp})
            top_entity = "a" if i < 2 else "b"
            assignments.append(3 if entity == top_entity else 1)
    timeline = turnover_mod.membership_timeline(
        pairs, assignments, bucket_count=3,
        initial_policy="no_prior_unavailable")
    rows = timeline["rows"]
    assert rows[0]["one_way_turnover"] is None
    assert rows[1]["one_way_turnover"] == pytest.approx(0.0)
    assert rows[2]["one_way_turnover"] == pytest.approx(1.0)
    assert rows[1]["jaccard_top"] == pytest.approx(1.0)
    assert rows[2]["jaccard_top"] == pytest.approx(0.0)
    assert timeline["summary"]["average_holding_duration"] == pytest.approx(2.0)


def test_holding_overlap_discloses_gross_exposure():
    overlap = turnover_mod.holding_overlap(
        10, 4, cohort_normalisation="none_disclosed")
    assert overlap["max_concurrent_cohorts"] == 4
    assert overlap["gross_exposure_overlapping"] == pytest.approx(8.0)
    assert "disclosed, never hidden" in overlap["gross_exposure_note"]
    split = turnover_mod.holding_overlap(
        10, 4, cohort_normalisation="per_cohort_equal_split")
    assert split["gross_exposure_overlapping"] == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def test_bootstrap_is_deterministic_and_bounded():
    pairs = [{"entity_id": "a", "signal_timestamp": demo_mod._stamps(30)[i],
              "signal_value": demo_mod._s(i) + i * 1e-6,
              "outcome_value": 0.01 * demo_mod._s(i) + demo_mod._e(i)}
             for i in range(30)]
    config = boot_mod.validate_bootstrap_config(
        {"method": "iid", "seed": 7, "resamples": 100,
         "statistic": "spearman"})
    first = boot_mod.run_bootstrap(pairs, config, bucket_count=3)
    second = boot_mod.run_bootstrap(pairs, config, bucket_count=3)
    assert first["quantiles"] == second["quantiles"]
    assert first["state"] == "available"
    assert "not a p-value" in first["note"]
    with pytest.raises(boot_mod.BootstrapError):
        boot_mod.validate_bootstrap_config({"method": "iid", "seed": 1,
                                            "resamples": 999999})
    with pytest.raises(boot_mod.BootstrapError):
        boot_mod.validate_bootstrap_config({"method": "moving_block",
                                            "seed": 1})


def test_moving_block_bootstrap_needs_an_explicit_block_length():
    pairs = [{"entity_id": "a", "signal_timestamp": demo_mod._stamps(40)[i],
              "signal_value": float(i), "outcome_value": float(i) + 0.1}
             for i in range(40)]
    config = boot_mod.validate_bootstrap_config(
        {"method": "moving_block", "seed": 3, "resamples": 100,
         "block_length": 5, "statistic": "pearson"})
    result = boot_mod.run_bootstrap(pairs, config, bucket_count=3)
    assert result["state"] == "available"
    assert result["block_length"] == 5


# ---------------------------------------------------------------------------
# Cost mapping
# ---------------------------------------------------------------------------

def test_cost_mapping_computes_bps_components_and_refuses_the_rest():
    model = {"commission": {"model": "bps_of_notional", "value": 2.0},
             "spread": {"model": "fixed_bps", "value": 4.0, "fraction": 0.5},
             "slippage": {"model": "none"},
             "impact": {"model": "square_root", "coefficient": 0.1},
             "fingerprint": "f" * 64}
    rows = [{"timestamp": "t1", "one_way_turnover": None},
            {"timestamp": "t2", "one_way_turnover": 0.5}]
    estimate = cost_mod.cost_estimate(model, turnover_rows=rows,
                                      reference_notional=100000.0)
    assert estimate["per_side_bps_computable"] == pytest.approx(4.0)
    assert "impact" in estimate["unavailable_components"]
    assert estimate["completeness"] == "partial"
    costed = estimate["rows"][1]
    per_side = 2.0 * 0.5 * 100000.0
    assert costed["cost"] == pytest.approx(4.0 / 1e4 * 2.0 * per_side)
    assert estimate["rows"][0]["state"] == "unavailable"


def test_reference_notional_is_bounded():
    with pytest.raises(cost_mod.CostError):
        cost_mod.validate_reference_notional(1.0)
    with pytest.raises(cost_mod.CostError):
        cost_mod.validate_reference_notional(float("inf"))


# ---------------------------------------------------------------------------
# Fingerprints
# ---------------------------------------------------------------------------

def test_fingerprints_are_stable_and_move_on_material_change():
    first = _run(name="one")
    second = _run(name="two — a different NAME only")
    assert first["universe_fingerprint"] == second["universe_fingerprint"]
    assert first["configuration_fingerprint"] == \
        second["configuration_fingerprint"]
    assert first["result_fingerprint"] == second["result_fingerprint"]

    changed = _payload(name="changed")
    changed["observations"][3]["value"] = 42.0
    created = service.create_run(changed)
    third = service.execute_run(created["id"])
    assert third["universe_fingerprint"] != first["universe_fingerprint"]
    assert third["result_fingerprint"] != first["result_fingerprint"]

    policy_changed = _payload(name="policy")
    policy_changed["horizons"]["horizons"] = [1, 2]
    created = service.create_run(policy_changed)
    fourth = service.execute_run(created["id"])
    assert fourth["horizon_fingerprint"] != first["horizon_fingerprint"]


def test_fingerprints_reject_non_finite_values():
    with pytest.raises(fp_mod.FingerprintError):
        fp_mod._clean({"value": float("nan")})


# ---------------------------------------------------------------------------
# Persistence, migration, baselines
# ---------------------------------------------------------------------------

def test_migration_creates_all_tables_and_preserves_prior_registries():
    with db_module.get_connection() as conn:
        names = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
    for table in ("signal_decay_runs", "signal_definitions",
                  "signal_observations", "signal_horizon_results",
                  "signal_bucket_results", "signal_turnover_results",
                  "signal_regime_results", "signal_bootstrap_results"):
        assert table in names
    for prior in ("factor_diagnostic_runs", "portfolio_attribution_runs",
                  "portfolio_stress_runs", "portfolio_diagnostic_runs",
                  "regime_diagnostic_runs", "cost_diagnostic_runs",
                  "validation_runs", "meta_label_runs", "feature_runs",
                  "experiment_registry", "dataset_versions"):
        assert prior in names


def test_failed_execution_clears_stale_results():
    executed = _run()
    assert store.list_horizons(executed["id"])
    broken = store.get_run(executed["id"])
    configuration = dict(broken["configuration"])
    configuration["horizons"] = dict(configuration["horizons"],
                                     horizons=["bogus"])
    store.update_run(executed["id"], {"configuration": configuration})
    with pytest.raises(Exception):
        service.execute_run(executed["id"])
    assert store.get_run(executed["id"])["status"] == "failed"
    assert store.list_horizons(executed["id"]) == []


def test_baseline_requires_verified_integrity_and_is_transactional():
    payload = _payload(name="descriptive")
    payload["signal"]["transformation"] = "rank_full_sample"
    created = service.create_run(payload)
    descriptive = service.execute_run(created["id"])
    with pytest.raises(service.ConflictError):
        service.mark_baseline(descriptive["id"])

    eligible = _run(name="eligible")
    marked = service.mark_baseline(eligible["id"])
    assert marked["is_baseline"] is True
    assert service.mark_baseline(eligible["id"])["is_baseline"] is True

    replacement = _run(name="same scope replacement")
    service.mark_baseline(replacement["id"])
    assert store.get_run(eligible["id"])["is_baseline"] is False
    assert store.get_run(replacement["id"])["is_baseline"] is True


def test_invalidate_clears_the_baseline_and_blocks_execution():
    executed = _run()
    service.mark_baseline(executed["id"])
    invalidated = service.invalidate_run(executed["id"], "superseded")
    assert invalidated["status"] == "invalidated"
    assert invalidated["is_baseline"] is False
    with pytest.raises(service.ConflictError):
        service.execute_run(executed["id"])


# ---------------------------------------------------------------------------
# Comparison and export
# ---------------------------------------------------------------------------

def test_comparison_uses_neutral_states_and_declares_no_winner():
    left = _run(name="left")
    right_payload = _payload(name="right")
    right_payload["horizons"]["horizons"] = [1, 2]
    created = service.create_run(right_payload)
    right = service.execute_run(created["id"])
    comparison = service.compare_runs(left["id"], right["id"])
    assert comparison["fields"]["universe_fingerprint"] == "same"
    assert comparison["fields"]["horizon_fingerprint"] == "changed"
    assert comparison["comparability_warnings"]
    assert any(r["presence"] == "only_in_b"
               for r in comparison["horizon_rows"])
    assert "no winner is declared" in comparison["note"]


def test_export_is_free_of_paths_and_credentials():
    _run()
    payload = service.export({})
    text = repr(payload)
    for banned in ("C:\\\\", "/home/", "password", "api_key", "secret",
                   "quantlab.db"):
        assert banned not in text
    assert payload["schema_version"] == "signal_decay_export_v1"
    assert "proves" in payload["disclaimer"]


# ---------------------------------------------------------------------------
# Demo fixture and cross-lab integration
# ---------------------------------------------------------------------------

def test_demo_is_idempotent_and_covers_documented_states():
    first = demo_mod.seed_demo_signal_decay()
    assert first["created_count"] == 24
    second = demo_mod.seed_demo_signal_decay()
    assert second["created_count"] == 0
    assert second["skipped_count"] == 24
    runs = service.list_runs(page_size=50)["items"]
    states = {r["integrity_status"] for r in runs}
    assert {"verified_point_in_time", "verified_trailing_signal",
            "verified_from_validation_split", "invalid"} <= states
    assert any(r["overlap_status"] == "overlapping" for r in runs)
    assert any(r["is_baseline"] for r in runs)


def test_demo_perfect_cases_hold_their_documented_values():
    demo_mod.seed_demo_signal_decay()
    run_id = store.run_demo_key_id("demo:sd:perfect-positive")
    rows = _raw_rows(run_id)
    assert rows[0]["spearman"] == pytest.approx(1.0)
    assert rows[0]["pearson"] == pytest.approx(1.0)
    run_id = store.run_demo_key_id("demo:sd:perfect-negative")
    rows = _raw_rows(run_id)
    assert rows[0]["spearman"] == pytest.approx(-1.0)


def test_demo_constant_cases_are_unavailable_with_reasons():
    demo_mod.seed_demo_signal_decay()
    for key, phrase in (("demo:sd:constant-signal", "signal is constant"),
                        ("demo:sd:constant-outcome", "outcome is constant")):
        rows = _raw_rows(store.run_demo_key_id(key))
        assert rows[0]["state"] == "unavailable"
        assert phrase in rows[0]["reason"]


def test_demo_sign_change_is_located():
    demo_mod.seed_demo_signal_decay()
    run = service.get_run(store.run_demo_key_id("demo:sd:sign-change"))
    spearman_decay = next(d for d in run["decay"]
                          if d["statistic"] == "spearman")
    assert spearman_decay["first_sign_change_horizon"] == 2
    assert run["decay"][0]["exponential_fit"]["state"] == "unavailable"


def test_demo_cost_case_is_gross_positive_net_nonpositive():
    demo_mod.seed_demo_signal_decay()
    run_id = store.run_demo_key_id("demo:sd:cost-adjusted")
    rows = _raw_rows(run_id)
    assert rows[0]["top_minus_bottom"] > 0
    assert rows[0]["cost_adjusted_spread"] <= 0
    run = service.get_run(run_id)
    assert run["cost"]["completeness"] in ("partial", "complete")
    assert run["cost"]["model_fingerprint"]
    cost_store = pytest.importorskip("app.cost_diagnostics.store")
    model = cost_store.get_cost_model(run["cost_diagnostic_run_id"])
    assert model["fingerprint"] == run["cost"]["model_fingerprint"]


def test_demo_regime_case_marks_rare_regimes():
    demo_mod.seed_demo_signal_decay()
    run_id = store.run_demo_key_id("demo:sd:regime-linked")
    rows = store.list_regimes(run_id)
    assert any(r["rare"] and r["state"] == "rare" for r in rows)
    assert any(r["state"] == "available" for r in rows)


def test_demo_held_out_uses_frozen_train_thresholds():
    demo_mod.seed_demo_signal_decay()
    run = service.get_run(store.run_demo_key_id(
        "demo:sd:held-out-validation"))
    held_out = run["held_out"]
    assert held_out["training_observations"] > 0
    assert held_out["held_out_observations"] > 0
    assert held_out["frozen_bucket_thresholds"] is not None
    assert "nothing is refitted" in held_out["note"]
    assert run["integrity_status"] == "verified_from_validation_split"


def test_demo_factor_residual_scopes_are_separate():
    demo_mod.seed_demo_signal_decay()
    run_id = store.run_demo_key_id("demo:sd:factor-residual")
    rows = store.list_horizons(run_id)
    scopes = {r["outcome_scope"] for r in rows}
    assert {"raw", "factor_residual"} <= scopes
    run = service.get_run(run_id)
    assert run["factor_residual"]["state"] == "available"
    assert "not alpha" in run["factor_residual"]["convention"]


def test_executing_after_a_linked_record_changed_is_refused():
    demo_mod.seed_demo_signal_decay()
    run_id = store.run_demo_key_id("demo:sd:factor-residual")
    factor_store = pytest.importorskip("app.factor_diagnostics.store")
    run = store.get_run(run_id)
    factor_store.update_run(run["factor_run_id"],
                            {"result_fingerprint": "0" * 64})
    with pytest.raises(service.ConflictError) as excinfo:
        service.execute_run(run_id)
    assert "changed since this run was created" in str(excinfo.value)


def test_meta_label_and_feature_links_pin_fingerprints():
    meta_demo = pytest.importorskip("app.meta_labeling.demo")
    meta_store = pytest.importorskip("app.meta_labeling.store")
    meta_demo.seed_demo_meta_labeling()
    meta_runs = meta_store.list_runs(page_size=5,
                                     filters={"status": "completed"})
    meta_id = meta_runs["items"][0]["id"]
    executed = _run(meta_label_run_id=meta_id)
    assert executed["meta_label_identity"]["meta_label_run_id"] == meta_id
    assert "signal VALUE only" in executed["meta_label_identity"]["note"]
    stored = meta_store.get_run(meta_id)
    assert stored["configuration_fingerprint"] == \
        executed["meta_label_identity"]["configuration_fingerprint"]


def test_multiple_testing_preserves_raw_p_values():
    executed = _run(horizons=[1, 2, 3], policy={
        "multiple_testing": {"methods": ["bonferroni", "holm", "bh"],
                             "alpha": 0.05,
                             "family": "the three evaluated horizons"}})
    block = executed["multiple_testing"]
    assert block["hypotheses"] == 3
    for row in block["rows"]:
        if row["raw_p_value"] is not None:
            assert row["bonferroni"] >= row["raw_p_value"] - 1e-15
    rows = _raw_rows(executed["id"])
    assert any(r["spearman_p_adjusted"] is not None for r in rows)
    assert "does not mean the signal is predictive" in block["note"]


def test_experiment_record_is_neutral_and_idempotent():
    experiment_store = pytest.importorskip("app.experiment_registry.store")
    created = service.create_run(_payload(name="with experiment"))
    executed = service.execute_run(created["id"], create_experiment=True)
    run = store.get_run(executed["id"])
    assert run["experiment_id"]
    record = experiment_store.get_experiment(run["experiment_id"])
    assert record["module"] == "signal_decay_diagnostics"
    text = f"{record['name']} {record.get('description', '')}".lower()
    for banned in ("predictive", "profitable", "validated", "recommended"):
        assert banned not in text or "no " in text
    again = service.execute_run(executed["id"], create_experiment=True)
    assert store.get_run(again["id"])["experiment_id"] == run["experiment_id"]


def test_dataset_lineage_is_read_only_and_warns_when_invalidated():
    dataset_store = pytest.importorskip("app.dataset_registry.store")
    dataset = dataset_store.insert_dataset({
        "name": "signal demo dataset", "description": "",
        "domain": "equities", "dataset_type": "signals",
        "source_type": "local_file", "provenance_status": "declared"})
    version = dataset_store.insert_version({
        "dataset_id": dataset["id"], "version_label": "v1",
        "row_count": 10, "column_count": 2, "schema_json": "{}",
        "manifest_fingerprint": "m" * 64, "schema_fingerprint": "s" * 64,
        "storage_locator_type": "relative_path",
        "storage_locator": "demo/signals.csv"})
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
    for path in ("horizons", "buckets", "turnover", "observations",
                 "regimes", "bootstrap"):
        assert client.get(f"{BASE}/runs/{run_id}/{path}").status_code == 200
    listing = client.get(f"{BASE}/runs", params={"page_size": 5})
    assert listing.status_code == 200
    assert listing.json()["total"] >= 1
    assert client.get(f"{BASE}/summary").status_code == 200
    assert client.get(f"{BASE}/export").status_code == 200


def test_api_error_codes_are_explicit(client):
    assert client.get(f"{BASE}/runs/999999").status_code == 404
    assert client.post(f"{BASE}/runs/999999/execute",
                       json={}).status_code == 404
    bad = _payload()
    bad["horizons"]["unit"] = "days"
    assert client.post(f"{BASE}/runs", json=bad).status_code == 422
    unknown = _payload()
    unknown["policy"] = {"nonsense": True}
    assert client.post(f"{BASE}/runs", json=unknown).status_code == 422

    payload = _payload(name="conflict")
    payload["signal"]["transformation"] = "rank_full_sample"
    created = client.post(f"{BASE}/runs", json=payload)
    run_id = created.json()["id"]
    client.post(f"{BASE}/runs/{run_id}/execute", json={})
    assert client.post(f"{BASE}/runs/{run_id}/mark-baseline"
                       ).status_code == 409


def test_api_rejects_non_finite_input(client):
    import json as json_module
    payload = _payload()
    body = json_module.dumps(payload)
    body = body.replace(str(payload["observations"][0]["value"]),
                        "Infinity", 1)
    response = client.post(f"{BASE}/runs", content=body,
                           headers={"content-type": "application/json"})
    assert response.status_code == 422


def test_api_demo_seed_is_idempotent(client):
    first = client.post(f"{BASE}/demo-seed")
    assert first.status_code == 200
    assert first.json()["created_count"] == 24
    second = client.post(f"{BASE}/demo-seed")
    assert second.json()["created_count"] == 0
    assert second.json()["skipped_count"] == 24
