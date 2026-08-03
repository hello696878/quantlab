"""
Signal Ensemble Lab tests (Phase 61.0): universe validation and canonical
ordering, strict-intersection and pairwise-complete alignment, missingness
disclosure, no-look-ahead availability with future-entity and
future-outlier invariance, cross-sectional rank/z-score and trailing
z-score normalisation with zero-variance honesty, explicit orientation,
pairwise Pearson/Spearman/Kendall with constants and ties, rank/bucket
agreement, tail co-occurrence, similarity distance, hierarchical
clustering, matrix rank/conditioning/eigenvalue concentration and the
effective signal count, all four combination modes, weight validation and
normalisation, missing-component policies, component-contribution
reconciliation, Signal Decay / cost / regime / validation / factor
integration (via the deterministic demo), leave-one-out diagnostics,
multiple testing, bootstrap and sensitivity determinism, fingerprints,
migration, persistence, baselines, Experiment Registry and Dataset Lineage
integration, export, demo idempotence, prior-registry preservation, API
success and error paths and non-finite rejection.
"""

from __future__ import annotations

import copy
import math

import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")
db_module = pytest.importorskip("app.db")
universe_mod = pytest.importorskip("app.signal_ensemble.universe")
align_mod = pytest.importorskip("app.signal_ensemble.alignment")
norm_mod = pytest.importorskip("app.signal_ensemble.normalisation")
pair_mod = pytest.importorskip("app.signal_ensemble.pairwise")
red_mod = pytest.importorskip("app.signal_ensemble.redundancy")
combo_mod = pytest.importorskip("app.signal_ensemble.combination")
fp_mod = pytest.importorskip("app.signal_ensemble.fingerprints")
service = pytest.importorskip("app.signal_ensemble.service")
store = pytest.importorskip("app.signal_ensemble.store")
demo_mod = pytest.importorskip("app.signal_ensemble.demo")
sd_demo = pytest.importorskip("app.signal_decay.demo")

BASE = "/signal-ensembles"


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


def _stamps(n=N):
    return sd_demo._stamps(n)


def _rows(stamps, values, entity_id="aggregate", explicit=True):
    return demo_mod._rows(stamps, values, entity_id=entity_id,
                          explicit=explicit)


def _definition(signal_id, **kwargs):
    return demo_mod._definition(signal_id, **kwargs)


def _base_values(n=N):
    return [sd_demo._s(i) + i * 1e-6 for i in range(n)]


def _alt_values(n=N):
    return [demo_mod._a(i) + i * 1e-6 for i in range(n)]


def _validated(signals):
    """Raw payload rows -> validated observation rows for engine tests."""
    sd_obs = pytest.importorskip("app.signal_decay.observations")
    out = {}
    for signal_id, rows in signals.items():
        out[signal_id] = sd_obs.validate_signal_observations(
            _definition(signal_id), rows)
    return out


def _payload(*, name="test run", signals=None, alignment=None,
             availability="explicit_available_at", **extra):
    stamps = _stamps()
    if signals is None:
        signals = {"sig-a": _rows(stamps, _base_values()),
                   "sig-b": _rows(stamps, _alt_values())}
    universe = demo_mod._universe(signals, availability=availability)
    if alignment:
        universe["alignment_policy"] = alignment
    payload = {"name": name, "universe": universe}
    payload.update(extra)
    return payload


def _run(**kwargs):
    created = service.create_run(_payload(**kwargs))
    return service.execute_run(created["id"])


# ---------------------------------------------------------------------------
# Universe validation and canonical ordering
# ---------------------------------------------------------------------------

def test_universe_requires_at_least_two_signals():
    stamps = _stamps()
    with pytest.raises(universe_mod.UniverseError) as excinfo:
        universe_mod.validate_universe({
            "signals": [_definition("only")],
            "observations": {"only": _rows(stamps, _base_values())}})
    assert "between 2 and" in str(excinfo.value)


def test_universe_rejects_duplicate_signal_ids():
    with pytest.raises(universe_mod.UniverseError) as excinfo:
        universe_mod.validate_universe({
            "signals": [_definition("dup"), _definition("dup")],
            "observations": {}})
    assert "duplicate signal_id" in str(excinfo.value)


def test_universe_rejects_incompatible_frequencies():
    stamps = _stamps()
    weekly = _definition("sig-b")
    weekly["frequency"] = "weekly"
    with pytest.raises(universe_mod.UniverseError) as excinfo:
        universe_mod.validate_universe({
            "signals": [_definition("sig-a"), weekly],
            "observations": {"sig-a": _rows(stamps, _base_values()),
                             "sig-b": _rows(stamps, _alt_values())}})
    assert "nothing is resampled" in str(excinfo.value)


def test_universe_canonical_ordering_is_sorted():
    stamps = _stamps()
    uni = universe_mod.validate_universe({
        "signals": [_definition("zeta"), _definition("alpha")],
        "observations": {"zeta": _rows(stamps, _base_values()),
                         "alpha": _rows(stamps, _alt_values())}})
    assert uni["signal_ids"] == ["alpha", "zeta"]


def test_universe_rejects_missing_and_unknown_observations():
    stamps = _stamps()
    with pytest.raises(universe_mod.UniverseError):
        universe_mod.validate_universe({
            "signals": [_definition("a"), _definition("b")],
            "observations": {"a": _rows(stamps, _base_values())}})
    with pytest.raises(universe_mod.UniverseError):
        universe_mod.validate_universe({
            "signals": [_definition("a"), _definition("b")],
            "observations": {"a": _rows(stamps, _base_values()),
                             "b": _rows(stamps, _alt_values()),
                             "ghost": _rows(stamps, _alt_values())}})


def test_universe_bounds_signal_count():
    stamps = _stamps(5)
    signals = [_definition(f"s-{i:02d}") for i in range(13)]
    observations = {f"s-{i:02d}": _rows(stamps, [float(i)] * 5)
                    for i in range(13)}
    with pytest.raises(universe_mod.UniverseError):
        universe_mod.validate_universe({"signals": signals,
                                        "observations": observations})


def test_non_finite_signal_value_rejected():
    stamps = _stamps(5)
    rows = _rows(stamps, [1.0, 2.0, 3.0, 4.0, 5.0])
    rows[2]["value"] = float("nan")
    with pytest.raises(Exception):
        universe_mod.validate_universe({
            "signals": [_definition("a"), _definition("b")],
            "observations": {"a": rows,
                             "b": _rows(stamps, [1, 2, 3, 4, 5])}})


# ---------------------------------------------------------------------------
# Alignment
# ---------------------------------------------------------------------------

def test_strict_intersection_uses_shared_nonnull_keys():
    stamps = _stamps(6)
    grid = align_mod.build_grid(_validated({
        "a": _rows(stamps, [1, 2, None, 4, 5, 6]),
        "b": _rows(stamps[:5], [1, 2, 3, 4, 5]),
    }))
    strict = align_mod.strict_intersection(grid, ["a", "b"])
    assert len(strict) == 4  # index 2 is null in a, index 5 absent in b


def test_pairwise_overlap_is_pair_specific():
    stamps = _stamps(6)
    grid = align_mod.build_grid(_validated({
        "a": _rows(stamps, [1, 2, None, 4, 5, 6]),
        "b": _rows(stamps, [1, 2, 3, 4, 5, 6]),
        "c": _rows(stamps[:3], [1, 2, 3]),
    }))
    assert len(align_mod.pairwise_overlap(grid, "a", "b")) == 5
    assert len(align_mod.pairwise_overlap(grid, "b", "c")) == 3
    assert len(align_mod.strict_intersection(grid, ["a", "b", "c"])) == 2


def test_missingness_summary_discloses_nulls_and_absences():
    stamps = _stamps(6)
    grid = align_mod.build_grid(_validated({
        "a": _rows(stamps, [1, 2, None, 4, 5, 6]),
        "b": _rows(stamps[:5], [1, 2, 3, 4, 5]),
    }))
    strict = align_mod.strict_intersection(grid, ["a", "b"])
    summary = align_mod.missingness_summary(grid, ["a", "b"], strict)
    a = next(s for s in summary["per_signal"] if s["signal_id"] == "a")
    b = next(s for s in summary["per_signal"] if s["signal_id"] == "b")
    assert a["stored_null"] == 1 and a["absent"] == 0
    assert b["absent"] == 1
    assert "no forward fill" in summary["note"]


def test_row_number_alignment_is_impossible_by_construction():
    """Keys are explicit (entity, timestamp) pairs; shifting one signal's
    timestamps changes the intersection instead of silently pairing rows."""
    stamps = _stamps(6)
    shifted = _stamps(7)[1:]
    grid = align_mod.build_grid(_validated({
        "a": _rows(stamps, [1, 2, 3, 4, 5, 6]),
        "b": _rows(shifted, [1, 2, 3, 4, 5, 6]),
    }))
    strict = align_mod.strict_intersection(grid, ["a", "b"])
    assert len(strict) == 5  # only the overlapping stamps align


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

def _norm(values, mode, *, entities=None, n=None, **cfg):
    n = n or len(values)
    stamps = _stamps(n)
    if entities is None:
        keys = [("e", s) for s in stamps]
        oriented = {("e", s): values[i] for i, s in enumerate(stamps)}
    else:
        keys = [(e, stamps[0]) for e in entities]
        oriented = {(e, stamps[0]): values[i]
                    for i, e in enumerate(entities)}
    config = {"mode": mode, "ddof": cfg.get("ddof", 1),
              "minimum_observations": cfg.get("minimum_observations", 3),
              "window": cfg.get("window"),
              "include_current": cfg.get("include_current", False)}
    return norm_mod.normalise_signal(oriented=oriented, stored_keys=keys,
                                     config=config, tie_policy="average")


def test_cross_sectional_rank_percentile_exact():
    result = _norm([10.0, 20.0, 30.0, 40.0],
                   "cross_sectional_rank_percentile",
                   entities=["e1", "e2", "e3", "e4"])
    values = sorted(result["values"].values())
    assert values == [0.125, 0.375, 0.625, 0.875]


def test_cross_sectional_zscore_exact():
    result = _norm([1.0, 2.0, 3.0], "cross_sectional_zscore",
                   entities=["e1", "e2", "e3"], ddof=1)
    z = result["values"][("e1", _stamps(1)[0])]
    assert abs(z + 1.0) < 1e-12  # (1-2)/1


def test_zero_variance_normalisation_unavailable():
    result = _norm([5.0, 5.0, 5.0], "cross_sectional_zscore",
                   entities=["e1", "e2", "e3"])
    assert all(v is None for v in result["values"].values())
    assert any("zero cross-sectional variance" in r
               for r in result["reasons"])


def test_trailing_zscore_is_strictly_trailing():
    values = [1.0, 2.0, 3.0, 4.0, 100.0]
    result = _norm(values, "trailing_zscore", window=4,
                   minimum_observations=3)
    stamps = _stamps(5)
    z4 = result["values"][("e", stamps[4])]
    # window = values[0:4] (strictly before), mean 2.5, std ddof1
    import numpy as np
    expected = (100.0 - 2.5) / float(np.std([1, 2, 3, 4], ddof=1))
    assert abs(z4 - expected) < 1e-12
    assert result["values"][("e", stamps[0])] is None  # no history yet


def test_future_outlier_cannot_change_earlier_trailing_zscore():
    base = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    tampered = base[:-1] + [1e6]
    r1 = _norm(base, "trailing_zscore", window=3, minimum_observations=3)
    r2 = _norm(tampered, "trailing_zscore", window=3,
               minimum_observations=3)
    stamps = _stamps(6)
    for stamp in stamps[:-1]:
        assert r1["values"][("e", stamp)] == r2["values"][("e", stamp)]


def test_future_entity_cannot_change_earlier_cross_sectional_ranks():
    stamps = _stamps(2)
    oriented = {("e1", stamps[0]): 1.0, ("e2", stamps[0]): 2.0,
                ("e3", stamps[0]): 3.0,
                ("e1", stamps[1]): 1.0, ("e2", stamps[1]): 2.0,
                ("e3", stamps[1]): 3.0, ("e9", stamps[1]): 99.0}
    keys = sorted(oriented)
    config = {"mode": "cross_sectional_rank_percentile", "ddof": 1,
              "minimum_observations": 3, "window": None,
              "include_current": False}
    result = norm_mod.normalise_signal(oriented=oriented,
                                       stored_keys=keys, config=config,
                                       tie_policy="average")
    # e9 exists only at stamp 1; stamp-0 percentiles are untouched by it
    assert result["values"][("e2", stamps[0])] == 0.5


def test_normalisation_validation_rejects_bad_config():
    with pytest.raises(norm_mod.NormalisationError):
        norm_mod.validate_normalisation({"x": {"mode": "zscore"}}, ["x"])
    with pytest.raises(norm_mod.NormalisationError):
        norm_mod.validate_normalisation(
            {"x": {"mode": "cross_sectional_zscore", "ddof": 2}}, ["x"])
    with pytest.raises(norm_mod.NormalisationError):
        norm_mod.validate_normalisation(
            {"x": {"mode": "trailing_zscore"}}, ["x"])  # window required
    with pytest.raises(norm_mod.NormalisationError):
        norm_mod.validate_normalisation({"ghost": {"mode": "none"}}, ["x"])


# ---------------------------------------------------------------------------
# Orientation
# ---------------------------------------------------------------------------

def test_orientation_defaults_and_explicit_inversion():
    orientations = universe_mod.validate_orientations(
        {"b": "multiply_by_negative_one"}, ["a", "b"])
    assert orientations == {"a": "as_supplied",
                            "b": "multiply_by_negative_one"}
    oriented = norm_mod.orient_values(
        {"a": {("e", "t"): 2.0}, "b": {("e", "t"): 2.0}}, orientations)
    assert oriented["a"][("e", "t")] == 2.0
    assert oriented["b"][("e", "t")] == -2.0


def test_orientation_rejects_unknown_signal_and_mode():
    with pytest.raises(universe_mod.UniverseError):
        universe_mod.validate_orientations({"ghost": "as_supplied"}, ["a"])
    with pytest.raises(universe_mod.UniverseError):
        universe_mod.validate_orientations({"a": "flip"}, ["a"])


# ---------------------------------------------------------------------------
# Pairwise similarity
# ---------------------------------------------------------------------------

def _pair(values_a, values_b, **kwargs):
    stamps = _stamps(len(values_a))
    keys = [("e", s) for s in stamps]
    va = {("e", s): values_a[i] for i, s in enumerate(stamps)}
    vb = {("e", s): values_b[i] for i, s in enumerate(stamps)}
    policy = pair_mod.validate_similarity_policy(
        kwargs.pop("policy", None))
    return pair_mod.pair_row("a", "b", values_a=va, values_b=vb,
                             keys=keys, stored_a=len(values_a),
                             stored_b=len(values_b), policy=policy,
                             alignment_mode="strict_intersection",
                             comparable_scale=kwargs.pop("comparable",
                                                         True))


def test_pairwise_identical_is_exactly_one_with_real_p():
    values = _base_values(20)
    row = _pair(values, list(values))
    assert abs(row["correlations"]["pearson"]["statistic"] - 1) < 1e-12
    assert abs(row["correlations"]["spearman"]["statistic"] - 1) < 1e-12
    assert row["correlations"]["spearman"]["p_value"] is not None
    assert row["mean_absolute_difference"] == 0.0
    assert row["sign_agreement_rate"] == 1.0


def test_pairwise_constant_unavailable_never_zero():
    row = _pair([1.0] * 10, _base_values(10))
    assert row["correlations"]["pearson"]["state"] == "unavailable"
    assert row["correlations"]["pearson"]["statistic"] is None
    assert "constant" in row["correlations"]["pearson"]["reason"]


def test_pairwise_thin_overlap_unavailable_with_count():
    row = _pair([1.0, 2.0], [2.0, 1.0])
    assert row["state"] == "unavailable"
    assert row["overlap_count"] == 2
    assert "below the minimum" in row["reason"]


def test_pairwise_kendall_only_when_configured():
    values = _base_values(15)
    row = _pair(values, values,
                policy={"correlation_methods":
                        ["pearson", "spearman", "kendall"]})
    assert abs(row["correlations"]["kendall"]["statistic"] - 1) < 1e-12
    row2 = _pair(values, values)
    assert "kendall" not in row2["correlations"]


def test_similarity_policy_rejects_unknown_metric_and_formula():
    with pytest.raises(pair_mod.PairwiseError):
        pair_mod.validate_similarity_policy(
            {"correlation_methods": ["mutual_information"]})
    with pytest.raises(pair_mod.PairwiseError):
        pair_mod.validate_similarity_policy(
            {"distance_formula": "one_minus_corr"})
    with pytest.raises(pair_mod.PairwiseError):
        pair_mod.validate_similarity_policy({"tail_quantile": 0.7})


def test_pair_order_is_canonical():
    assert pair_mod.pair_order(["c", "a", "b"]) == [
        ("a", "b"), ("a", "c"), ("b", "c")]


# ---------------------------------------------------------------------------
# Rank/bucket agreement and tails
# ---------------------------------------------------------------------------

def _cross_section(values_by_entity):
    stamps = _stamps(len(next(iter(values_by_entity.values()))))
    keys = []
    va = {}
    for entity, series in values_by_entity.items():
        for i, s in enumerate(stamps):
            keys.append((entity, s))
    return stamps, sorted(keys)


def test_bucket_agreement_identical_signals():
    stamps = _stamps(5)
    keys = [(e, s) for s in stamps for e in ("e1", "e2", "e3")]
    values = {(e, s): float(ord(e[-1])) for e, s in keys}
    result = pair_mod.bucket_agreement(
        "a", "b", values_a=values, values_b=dict(values), keys=keys,
        bucket_count=3)
    assert result["exact_agreement_rate"] == 1.0
    assert result["top_bucket_jaccard"] == 1.0
    assert result["bottom_bucket_jaccard"] == 1.0
    assert result["directional_disagreement_count"] == 0


def test_bucket_agreement_inverse_signals():
    stamps = _stamps(5)
    keys = [(e, s) for s in stamps for e in ("e1", "e2", "e3")]
    values = {(e, s): float(ord(e[-1])) for e, s in keys}
    inverse = {k: -v for k, v in values.items()}
    result = pair_mod.bucket_agreement(
        "a", "b", values_a=values, values_b=inverse, keys=keys,
        bucket_count=3)
    assert result["top_bucket_jaccard"] == 0.0
    assert result["directional_disagreement_count"] > 0


def test_tail_cooccurrence_counts():
    values = [float(i) for i in range(20)]
    stamps = _stamps(20)
    keys = [("e", s) for s in stamps]
    va = {("e", s): values[i] for i, s in enumerate(stamps)}
    result = pair_mod.tail_cooccurrence(
        "a", "b", values_a=va, values_b=dict(va), keys=keys,
        quantile=0.2)
    assert result["tail_size"] == 4
    assert result["both_lower_count"] == 4
    assert result["both_upper_count"] == 4
    assert result["opposite_tail_count"] == 0
    assert result["lower_conditional_overlap"] == 1.0


def test_tail_cooccurrence_needs_observations():
    stamps = _stamps(5)
    keys = [("e", s) for s in stamps]
    va = {("e", s): float(i) for i, s in enumerate(stamps)}
    result = pair_mod.tail_cooccurrence(
        "a", "b", values_a=va, values_b=dict(va), keys=keys,
        quantile=0.2)
    assert result["state"] == "unavailable"


# ---------------------------------------------------------------------------
# Distance, matrix diagnostics, clustering
# ---------------------------------------------------------------------------

def _matrix_from(correlations):
    """correlations: {(a, b): value or None} over sorted ids."""
    ids = sorted({s for pair in correlations for s in pair})
    rows = []
    for a, b in pair_mod.pair_order(ids):
        value = correlations[(a, b)]
        state = "available" if value is not None else "unavailable"
        rows.append({"signal_a": a, "signal_b": b, "correlations": {
            "spearman": {"state": state, "statistic": value,
                         "reason": None if value is not None
                         else "test unavailable"}}})
    return red_mod.correlation_matrix(rows, ids, method="spearman")


def test_distance_formula_endpoints():
    matrix = _matrix_from({("a", "b"): 1.0, ("a", "c"): -1.0,
                           ("b", "c"): 0.0})
    distance = red_mod.distance_matrix(matrix)
    ids = distance["signal_ids"]
    i, j, k = ids.index("a"), ids.index("b"), ids.index("c")
    assert distance["cells"][i][j] == 0.0            # corr 1 -> 0
    assert abs(distance["cells"][i][k] - 1.0) < 1e-12  # corr -1 -> 1
    assert abs(distance["cells"][j][k]
               - math.sqrt(0.5)) < 1e-12              # corr 0 -> sqrt(.5)
    assert distance["cells"][i][i] == 0.0


def test_unavailable_correlation_gives_unavailable_distance():
    matrix = _matrix_from({("a", "b"): None, ("a", "c"): 0.5,
                           ("b", "c"): 0.5})
    distance = red_mod.distance_matrix(matrix)
    ids = distance["signal_ids"]
    assert distance["cells"][ids.index("a")][ids.index("b")] is None
    assert not distance["complete"]
    diagnostics = red_mod.matrix_diagnostics(matrix)
    assert diagnostics["state"] == "unavailable"
    assert "nothing is imputed" in diagnostics["reason"]


def test_effective_count_formula_hand_checked():
    # identity 2x2 -> eigenvalues (1, 1) -> (2)^2 / 2 = 2
    matrix = _matrix_from({("a", "b"): 0.0})
    diagnostics = red_mod.matrix_diagnostics(matrix)
    assert abs(diagnostics["effective_signal_count"] - 2.0) < 1e-12
    # perfect 2x2 -> eigenvalues (2, 0) -> 4 / 4 = 1
    matrix = _matrix_from({("a", "b"): 1.0})
    diagnostics = red_mod.matrix_diagnostics(matrix)
    assert abs(diagnostics["effective_signal_count"] - 1.0) < 1e-12
    assert diagnostics["matrix_rank"] == 1
    assert diagnostics["condition_number"] is None
    assert "not the true number" in \
        diagnostics["effective_signal_count_note"]


def test_matrix_not_psd_is_refused_not_repaired():
    # correlation pattern that is not PSD: r(ab)=r(ac)=0.9, r(bc)=-0.9
    matrix = _matrix_from({("a", "b"): 0.9, ("a", "c"): 0.9,
                           ("b", "c"): -0.9})
    diagnostics = red_mod.matrix_diagnostics(matrix)
    assert diagnostics["state"] == "unavailable"
    assert "NOT" in diagnostics["reason"]
    assert diagnostics["negative_eigenvalue_count"] >= 1


def test_clustering_deterministic_and_refuses_incomplete():
    matrix = _matrix_from({("a", "b"): 0.95, ("a", "c"): 0.1,
                           ("b", "c"): 0.1})
    distance = red_mod.distance_matrix(matrix)
    settings = red_mod.validate_clustering({"linkage": "average",
                                            "threshold": 0.5})
    result = red_mod.cluster(distance, settings)
    assert result["state"] == "available"
    clusters = {c["signal_id"]: c["cluster"] for c in result["clusters"]}
    assert clusters["a"] == clusters["b"] != clusters["c"]
    again = red_mod.cluster(distance, settings)
    assert again["merges"] == result["merges"]

    incomplete = _matrix_from({("a", "b"): None, ("a", "c"): 0.1,
                               ("b", "c"): 0.1})
    refused = red_mod.cluster(red_mod.distance_matrix(incomplete),
                              settings)
    assert refused["state"] == "unavailable"
    assert "refused" in refused["reason"]


def test_clustering_validation_requires_explicit_threshold():
    with pytest.raises(red_mod.RedundancyError):
        red_mod.validate_clustering({"linkage": "average"})
    with pytest.raises(red_mod.RedundancyError):
        red_mod.validate_clustering({"linkage": "ward", "threshold": 0.5})


# ---------------------------------------------------------------------------
# Combination modes and weights
# ---------------------------------------------------------------------------

def test_equal_weight_combination_is_exact_mean():
    policy = combo_mod.validate_combination_policy(
        {"mode": "equal_weight"}, ["a", "b"])
    keys = [("e", "t1")]
    result = combo_mod.combine(
        keys=keys, component_values={"a": {("e", "t1"): 1.0},
                                     "b": {("e", "t1"): 3.0}},
        policy=policy, signal_ids=["a", "b"])
    assert result["observations"][0]["combined_score"] == 2.0
    assert result["reconciliation"]["state"] == "reconciled"


def test_user_weights_validation():
    with pytest.raises(combo_mod.CombinationError):  # missing weight
        combo_mod.validate_combination_policy(
            {"mode": "user_weights", "weights": {"a": 1.0}}, ["a", "b"])
    with pytest.raises(combo_mod.CombinationError):  # non-finite
        combo_mod.validate_combination_policy(
            {"mode": "user_weights",
             "weights": {"a": float("inf"), "b": 0.5}}, ["a", "b"])
    with pytest.raises(combo_mod.CombinationError) as excinfo:  # negative
        combo_mod.validate_combination_policy(
            {"mode": "user_weights", "weights": {"a": 1.5, "b": -0.5}},
            ["a", "b"])
    assert "allow_negative_weights" in str(excinfo.value)
    with pytest.raises(combo_mod.CombinationError):  # sum != 1
        combo_mod.validate_combination_policy(
            {"mode": "user_weights", "weights": {"a": 0.9, "b": 0.9}},
            ["a", "b"])
    with pytest.raises(combo_mod.CombinationError):  # zero gross
        combo_mod.validate_combination_policy(
            {"mode": "user_weights", "weights": {"a": 0.0, "b": 0.0},
             "weight_normalisation": "none"}, ["a", "b"])


def test_weight_normalise_by_sum_and_gross():
    policy = combo_mod.validate_combination_policy(
        {"mode": "user_weights", "weights": {"a": 2.0, "b": 2.0},
         "weight_normalisation": "normalise_by_sum"}, ["a", "b"])
    assert policy["final_weights"] == {"a": 0.5, "b": 0.5}
    assert policy["configured_weights"] == {"a": 2.0, "b": 2.0}
    policy = combo_mod.validate_combination_policy(
        {"mode": "user_weights", "weights": {"a": 1.5, "b": -0.5},
         "allow_negative_weights": True,
         "weight_normalisation": "normalise_by_gross"}, ["a", "b"])
    assert abs(policy["final_weights"]["a"] - 0.75) < 1e-12
    assert abs(policy["final_weights"]["b"] + 0.25) < 1e-12
    assert abs(policy["gross_weight"] - 1.0) < 1e-12
    assert abs(policy["net_weight"] - 0.5) < 1e-12


def test_rank_average_mode_combines_percentiles():
    # single-entity universe: a cross-sectional rank needs >= 3 entities
    # per stamp, so the engine honestly reports unavailable combined
    # scores instead of fabricating ranks
    run = _run(name="rank average",
               combination={"mode": "rank_average"})
    observations = store.list_observations(run["id"])
    assert all(o["state"] == "unavailable" for o in observations)
    # a 3-entity universe produces percentile-based combined scores
    stamps = _stamps(10)
    signals = {}
    for sig in ("ra", "rb"):
        rows = []
        for k, entity in enumerate(("e1", "e2", "e3")):
            rows.extend(_rows(stamps, [float((i + k) % 5)
                                       for i in range(10)],
                              entity_id=entity))
        signals[sig] = rows
    created = service.create_run({
        "name": "rank multi", "universe": demo_mod._universe(signals),
        "combination": {"mode": "rank_average"}})
    run2 = service.execute_run(created["id"])
    observations = store.list_observations(run2["id"])
    available = [o for o in observations if o["state"] == "available"]
    assert available
    for o in available:
        assert 0.0 < o["combined_score"] < 1.0


def test_majority_sign_mode_votes():
    policy = combo_mod.validate_combination_policy(
        {"mode": "majority_sign"}, ["a", "b", "c"])
    keys = [("e", "t1")]
    result = combo_mod.combine(
        keys=keys,
        component_values={"a": {("e", "t1"): 0.5},
                          "b": {("e", "t1"): 0.4},
                          "c": {("e", "t1"): -0.9}},
        policy=policy, signal_ids=["a", "b", "c"])
    assert result["observations"][0]["combined_score"] == 1.0
    assert result["reconciliation"]["state"] == "not_applicable"
    votes = [c["sign_vote"] for c in result["contributions"]]
    assert sorted(votes) == [-1, 1, 1]


# ---------------------------------------------------------------------------
# Missing-component policies and reconciliation
# ---------------------------------------------------------------------------

def test_require_all_leaves_gaps_unavailable():
    policy = combo_mod.validate_combination_policy(
        {"mode": "equal_weight"}, ["a", "b"])
    keys = [("e", "t1"), ("e", "t2")]
    result = combo_mod.combine(
        keys=keys,
        component_values={"a": {("e", "t1"): 1.0, ("e", "t2"): 2.0},
                          "b": {("e", "t1"): 3.0, ("e", "t2"): None}},
        policy=policy, signal_ids=["a", "b"])
    assert result["observations"][1]["state"] == "unavailable"
    assert result["observations"][1]["missing_signal_ids"] == ["b"]
    assert result["available_count"] == 1


def test_renormalise_available_requires_explicit_selection():
    with pytest.raises(combo_mod.CombinationError):
        combo_mod.validate_combination_policy(
            {"mode": "equal_weight",
             "missing_component_policy": "impute_zero"}, ["a", "b"])
    policy = combo_mod.validate_combination_policy(
        {"mode": "equal_weight",
         "missing_component_policy": "renormalise_available",
         "minimum_component_count": 2}, ["a", "b", "c"])
    keys = [("e", "t1")]
    result = combo_mod.combine(
        keys=keys,
        component_values={"a": {("e", "t1"): 1.0},
                          "b": {("e", "t1"): 3.0},
                          "c": {("e", "t1"): None}},
        policy=policy, signal_ids=["a", "b", "c"])
    observation = result["observations"][0]
    assert observation["state"] == "available"
    assert observation["combined_score"] == 2.0  # renormalised mean
    assert observation["missing_signal_ids"] == ["c"]
    assert abs(observation["effective_weights"]["a"] - 0.5) < 1e-12


def test_contribution_reconciliation_service_level():
    run = _run(name="reconcile")
    components = store.list_components(run["id"], limit=2000)
    observations = {(o["entity_id"], o["timestamp"]): o
                    for o in store.list_observations(run["id"])}
    by_key = {}
    for c in components:
        by_key.setdefault((c["entity_id"], c["timestamp"]), []).append(c)
    checked = 0
    for key, rows in by_key.items():
        observation = observations[key]
        if observation["state"] != "available":
            continue
        total = sum(r["contribution"] for r in rows if not r["missing"])
        assert abs(total - observation["combined_score"]) <= 1e-9
        checked += 1
    assert checked > 0
    assert run["reconciliation"]["state"] == "reconciled"


# ---------------------------------------------------------------------------
# Integrity and availability
# ---------------------------------------------------------------------------

def test_availability_violation_marks_run_invalid():
    stamps = _stamps(10)
    rows = _rows(stamps, [float(i) for i in range(10)])
    rows[3]["available_at"] = _stamps(11)[10]  # available in the future
    created = service.create_run({
        "name": "violation",
        "universe": demo_mod._universe({
            "late": rows,
            "ok": _rows(stamps, _alt_values(10))})})
    run = service.execute_run(created["id"])
    assert run["integrity_status"] == "invalid"
    assert any("INVALID" in w for w in run["warnings"])


def test_same_timestamp_with_lag_is_verified_trailing():
    stamps = _stamps(20)
    values = _base_values(20)
    signals = {"a": _rows(stamps, values, explicit=False),
               "b": _rows(stamps, _alt_values(20), explicit=False)}
    universe = demo_mod._universe(signals, availability="same_timestamp")
    prices = sd_demo._prices_from_returns(
        stamps, [0.01 * values[i] for i in range(19)])
    created = service.create_run({
        "name": "trailing", "universe": universe, "prices": prices,
        "analysis": {"horizons": [1], "entry_lags": [1]}})
    run = service.execute_run(created["id"])
    assert run["integrity_status"] == "verified_trailing_transformation"

    created = service.create_run({
        "name": "contemporaneous", "universe": universe,
        "prices": prices, "analysis": {"horizons": [1],
                                       "entry_lags": [0]}})
    run = service.execute_run(created["id"])
    assert run["integrity_status"] == "contemporaneous_descriptive"


def test_full_sample_transformation_demotes_integrity():
    stamps = _stamps(10)
    full = _definition("full-rank")
    full["transformation"] = "rank_full_sample"
    created = service.create_run({
        "name": "full sample",
        "universe": {
            "name": "u",
            "signals": [full, _definition("plain")],
            "observations": {
                "full-rank": _rows(stamps, _base_values(10)),
                "plain": _rows(stamps, _alt_values(10))}}})
    run = service.execute_run(created["id"])
    assert run["integrity_status"] == "full_sample_descriptive"


# ---------------------------------------------------------------------------
# Leave-one-out
# ---------------------------------------------------------------------------

def test_leave_one_out_rows_and_deltas():
    stamps = _stamps(20)
    values = _base_values(20)
    signals = {"a": _rows(stamps, values),
               "b": _rows(stamps, [v * 1.1 for v in values]),
               "c": _rows(stamps, _alt_values(20))}
    prices = sd_demo._prices_from_returns(
        stamps, [0.01 * values[i] for i in range(19)])
    created = service.create_run({
        "name": "loo", "universe": demo_mod._universe(signals),
        "prices": prices, "analysis": {"horizons": [1],
                                       "entry_lags": [0]}})
    run = service.execute_run(created["id"])
    loo = store.list_leave_one_out(run["id"])
    assert [l["omitted_signal_id"] for l in loo] == ["a", "b", "c"]
    for entry in loo:
        assert entry["state"] == "available"
        assert "never an exclusion recommendation" in \
            entry["metrics"]["note"]
        assert entry["metrics"]["effective_signal_count"] is not None
    # omitting the redundant copy changes redundancy more than omitting c
    drop_b = next(l for l in loo if l["omitted_signal_id"] == "b")
    assert drop_b["metrics"]["mean_absolute_correlation_delta"] is not None


def test_leave_one_out_skipped_for_two_signals():
    run = _run(name="loo two")
    assert store.list_leave_one_out(run["id"]) == []


# ---------------------------------------------------------------------------
# Multiple testing, bootstrap, sensitivity
# ---------------------------------------------------------------------------

def test_multiple_testing_keeps_raw_next_to_adjusted():
    created = service.create_run(_payload(
        name="mt",
        analysis={"multiple_testing": {"methods": ["holm"],
                                       "alpha": 0.05}}))
    run = service.execute_run(created["id"])
    pairwise = store.list_pairwise(run["id"])
    assert pairwise[0]["spearman_p"] is not None
    assert pairwise[0]["spearman_p_adjusted"] is not None
    assert run["multiple_testing"]["preferred_method"] == "holm"
    assert "never proof" in run["multiple_testing"]["note"]


def test_multiple_testing_rejects_unknown_method():
    with pytest.raises(service.SignalEnsembleError):
        service.create_run(_payload(
            name="mt bad",
            analysis={"multiple_testing": {"methods": ["by"]}}))


def test_bootstrap_deterministic_under_seed():
    def _boot(seed):
        created = service.create_run(_payload(
            name=f"boot {seed}",
            analysis={"bootstrap": {
                "method": "timestamp",
                "statistics": ["mean_absolute_correlation"],
                "seed": seed, "resamples": 60}}))
        run = service.execute_run(created["id"])
        return store.list_bootstrap(run["id"])[0]["quantiles"]

    first = _boot(7)
    second = _boot(7)
    third = _boot(8)
    assert first == second
    assert first != third


def test_bootstrap_validation():
    with pytest.raises(service.SignalEnsembleError):
        service.create_run(_payload(
            name="boot bad",
            analysis={"bootstrap": {"method": "entity",
                                    "statistics":
                                        ["mean_absolute_correlation"],
                                    "seed": 1, "resamples": 60}}))
    with pytest.raises(service.SignalEnsembleError):
        service.create_run(_payload(
            name="boot bad 2",
            analysis={"bootstrap": {"method": "timestamp",
                                    "statistics":
                                        ["mean_absolute_correlation"],
                                    "seed": 1, "resamples": 10}}))


def test_sensitivity_base_once_and_duplicates_removed():
    created = service.create_run(_payload(
        name="sensitivity",
        analysis={"sensitivity": {"scenarios": [
            {"label": "pearson matrix", "matrix_method": "pearson"},
            {"label": "duplicate pearson", "matrix_method": "pearson"},
            {"label": "coarser buckets", "bucket_count": 2},
        ]}}))
    run = service.execute_run(created["id"])
    rows = store.list_sensitivity(run["id"])
    bases = [r for r in rows if r["is_base"]]
    assert len(bases) == 1 and bases[0]["scenario_index"] == 0
    labels = [r["label"] for r in rows]
    assert "duplicate pearson" not in labels  # same overrides collapse
    assert len(rows) == 3
    again = service.execute_run(created["id"])
    assert store.list_sensitivity(run["id"]) == rows  # deterministic


# ---------------------------------------------------------------------------
# Fingerprints
# ---------------------------------------------------------------------------

def test_fingerprints_material_change():
    a = service.create_run(_payload(name="fp a"))
    b = service.create_run(_payload(name="fp b"))
    assert a["universe_fingerprint"] == b["universe_fingerprint"]
    stamps = _stamps()
    values = _base_values()
    values[0] += 1e-6
    c = service.create_run(_payload(
        name="fp c", signals={"sig-a": _rows(stamps, values),
                              "sig-b": _rows(stamps, _alt_values())}))
    assert c["universe_fingerprint"] != a["universe_fingerprint"]
    d = service.create_run(_payload(
        name="fp d",
        combination={"mode": "user_weights",
                     "weights": {"sig-a": 0.6, "sig-b": 0.4}}))
    assert d["combination_fingerprint"] != a["combination_fingerprint"]
    assert d["universe_fingerprint"] == a["universe_fingerprint"]


def test_fingerprints_reject_non_finite():
    with pytest.raises(fp_mod.FingerprintError):
        fp_mod.analysis_policy_fingerprint({
            "horizons": [], "entry_lags": [], "bucket": None,
            "turnover": None, "reference_notional": float("inf"),
            "regime_policy": None, "validation_policy": None,
            "factor_residual_policy": None, "multiple_testing": None,
            "bootstrap": None, "sensitivity": None,
            "reconciliation_tolerance": 1e-9})


def test_execution_is_reproducible():
    created = service.create_run(_payload(name="repro"))
    first = service.execute_run(created["id"])
    second = service.execute_run(created["id"])
    assert first["result_fingerprint"] == second["result_fingerprint"]


# ---------------------------------------------------------------------------
# Persistence, migration, failure handling
# ---------------------------------------------------------------------------

def test_migration_preserves_prior_registries():
    with db_module.get_connection() as conn:
        tables = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
    for prior in ("saved_backtests", "experiment_registry",
                  "validation_runs", "feature_runs", "meta_label_runs",
                  "regime_diagnostic_runs", "cost_diagnostic_runs",
                  "portfolio_diagnostic_runs", "portfolio_stress_runs",
                  "portfolio_attribution_runs", "factor_diagnostic_runs",
                  "signal_decay_runs"):
        assert prior in tables, prior
    for new in store.CHILD_TABLES + ("signal_ensemble_runs",):
        assert new in tables, new


def test_failed_execution_clears_stale_results():
    created = service.create_run(_payload(name="will fail"))
    service.execute_run(created["id"])
    assert store.list_pairwise(created["id"])
    with db_module.get_connection() as conn:
        conn.execute(
            "UPDATE signal_ensemble_runs SET configuration = "
            "replace(configuration, '\"strict_intersection\"', "
            "'\"bogus_policy\"') WHERE id = ?", (created["id"],))
    with pytest.raises(service.ENGINE_ERRORS):
        service.execute_run(created["id"])
    run = store.get_run(created["id"])
    assert run["status"] == "failed"
    assert run["error_message"]
    assert store.list_pairwise(created["id"]) == []


def test_children_replaced_not_duplicated():
    created = service.create_run(_payload(name="replace"))
    service.execute_run(created["id"])
    first = len(store.list_pairwise(created["id"]))
    service.execute_run(created["id"])
    assert len(store.list_pairwise(created["id"])) == first


# ---------------------------------------------------------------------------
# Baseline policy
# ---------------------------------------------------------------------------

def test_baseline_requires_verified_integrity():
    stamps = _stamps(10)
    signals = {"a": _rows(stamps, _base_values(10), explicit=False),
               "b": _rows(stamps, _alt_values(10), explicit=False)}
    created = service.create_run({
        "name": "descriptive",
        "universe": demo_mod._universe(signals,
                                       availability="same_timestamp")})
    service.execute_run(created["id"])
    with pytest.raises(service.ConflictError) as excinfo:
        service.mark_baseline(created["id"])
    assert "never chosen by IC" in str(excinfo.value)


def test_baseline_same_scope_replacement_is_transactional():
    a = service.create_run(_payload(name="baseline a"))
    service.execute_run(a["id"])
    b = service.create_run(_payload(name="baseline b"))
    service.execute_run(b["id"])
    service.mark_baseline(a["id"])
    service.mark_baseline(b["id"])
    assert store.get_run(a["id"])["is_baseline"] is False
    assert store.get_run(b["id"])["is_baseline"] is True
    # idempotent re-marking
    service.mark_baseline(b["id"])
    assert store.get_run(b["id"])["is_baseline"] is True


def test_invalidated_run_loses_baseline_and_refuses_execution():
    a = service.create_run(_payload(name="invalidate me"))
    service.execute_run(a["id"])
    service.mark_baseline(a["id"])
    run = service.invalidate_run(a["id"], "test invalidation")
    assert run["status"] == "invalidated"
    assert run["is_baseline"] is False
    with pytest.raises(service.ConflictError):
        service.execute_run(a["id"])


# ---------------------------------------------------------------------------
# Demo + linked-lab integration (one cascade for runtime economy)
# ---------------------------------------------------------------------------

def test_demo_seed_idempotent_and_linked_labs():
    first = demo_mod.seed_demo_signal_ensemble()
    assert first["created_count"] == 24
    second = demo_mod.seed_demo_signal_ensemble()
    assert second["created_count"] == 0
    assert second["skipped_count"] == 24

    def by_name(fragment):
        listing = store.list_runs(filters={"query": fragment},
                                  page_size=50)
        assert listing["items"], fragment
        return service.get_run(listing["items"][0]["id"])

    # Signal Decay-style evaluation of the combination
    run = by_name("Equal-weight combination")
    horizons = store.list_horizons(run["id"])
    assert {h["scope"] for h in horizons} == {"combination", "component"}

    # regimes: stored assignments, rare withheld
    run = by_name("Regime-dependent similarity")
    regimes = store.list_regimes(run["id"])
    assert regimes
    assert all(g["state"] in ("available", "rare") for g in regimes)

    # validation: training vs held-out, nothing refitted
    run = by_name("Training versus held-out")
    assert run["held_out"]["training_observations"] > 0
    assert "nothing" in run["held_out"]["note"] \
        and "refitted" in run["held_out"]["note"]
    assert run["integrity_status"] == "verified_from_validation_split"

    # cost: pinned model, gross separate from cost-adjusted
    run = by_name("Cost-linked combination")
    assert run["cost"] is not None
    combo = [h for h in store.list_horizons(run["id"])
             if h["scope"] == "combination"]
    assert combo[0]["top_minus_bottom"] != combo[0]["cost_adjusted_spread"]

    # factor: outcome residuals only, signal residualisation deferred
    run = by_name("Raw versus factor-residual")
    assert run["factor_residual"]["signal_value_residualisation"][
        "state"] == "deferred"

    # experiment registry record for the baseline candidate
    run = by_name("Baseline candidate")
    assert run["is_baseline"] is True
    assert run["experiment_id"] is not None
    from app.experiment_registry import store as exp_store
    record = exp_store.get_experiment(run["experiment_id"])
    assert record["module"] == "signal_ensemble_diagnostics"
    banned = ("recommended ensemble", "preferred signal",
              "optimal weights", "validated signal combination")
    text = str(record).lower()
    assert not any(b in text for b in banned)

    # turnover contrast pair
    run = by_name("Churning components")
    assert run["turnover_summary"]["mean_one_way_turnover"] == 0.0
    run = by_name("Stable components")
    assert run["turnover_summary"]["mean_one_way_turnover"] > 0.5


# ---------------------------------------------------------------------------
# API paths
# ---------------------------------------------------------------------------

def test_api_create_execute_read(client):
    response = client.post(f"{BASE}/runs", json=_payload(name="api run"))
    assert response.status_code == 201, response.text
    run_id = response.json()["id"]
    response = client.post(f"{BASE}/runs/{run_id}/execute", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["redundancy"]["mean_absolute_correlation"] is not None
    response = client.get(f"{BASE}/runs/{run_id}/pairwise")
    assert response.status_code == 200
    assert response.json()["items"]
    response = client.get(f"{BASE}/runs/{run_id}/matrix")
    assert response.status_code == 200
    assert response.json()["diagnostics"]["effective_signal_count"]
    response = client.get(f"{BASE}/runs/{run_id}/components")
    assert response.status_code == 200
    assert response.json()["reconciliation"]["state"] == "reconciled"


def test_api_error_codes(client):
    assert client.get(f"{BASE}/runs/99999").status_code == 404
    response = client.post(f"{BASE}/runs", json={"name": "bad",
                                                 "universe": {}})
    assert response.status_code == 422
    created = client.post(f"{BASE}/runs",
                          json=_payload(name="conflict"))
    run_id = created.json()["id"]
    client.post(f"{BASE}/runs/{run_id}/execute", json={})
    client.post(f"{BASE}/runs/{run_id}/invalidate",
                json={"reason": "test"})
    response = client.post(f"{BASE}/runs/{run_id}/execute", json={})
    assert response.status_code == 409
    response = client.post(f"{BASE}/runs/{run_id}/mark-baseline")
    assert response.status_code == 409


def test_api_list_filters_and_summary(client):
    client.post(f"{BASE}/runs", json=_payload(name="list me"))
    response = client.get(f"{BASE}/runs",
                          params={"query": "list me"})
    assert response.status_code == 200
    assert response.json()["total"] == 1
    response = client.get(f"{BASE}/runs",
                          params={"combination_mode": "majority_sign"})
    assert response.json()["total"] == 0
    response = client.get(f"{BASE}/summary")
    assert response.status_code == 200
    assert response.json()["runs"] == 1


def test_api_rejects_unknown_body_keys(client):
    payload = _payload(name="extra")
    payload["surprise"] = True
    response = client.post(f"{BASE}/runs", json=payload)
    assert response.status_code == 422


def test_dataset_link_unknown_version_rejected():
    with pytest.raises(service.SignalEnsembleError):
        service.create_run(_payload(name="ds", dataset_version_id=424242))


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def test_export_schema_and_hygiene(client):
    created = service.create_run(_payload(name="export me"))
    service.execute_run(created["id"])
    response = client.get(f"{BASE}/export")
    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "signal_ensemble_export_v1"
    assert body["run_count"] == 1
    assert "proves signal" in body["disclaimer"]
    text = response.text
    for banned in ("C:\\\\", "/home/", "quantlab.db", "api_key",
                   "password"):
        assert banned not in text
    assert "NaN" not in text and "Infinity" not in text


def test_comparison_neutral_states(client):
    a = service.create_run(_payload(name="cmp a"))
    service.execute_run(a["id"])
    b = service.create_run(_payload(
        name="cmp b",
        combination={"mode": "user_weights",
                     "weights": {"sig-a": 0.6, "sig-b": 0.4}}))
    service.execute_run(b["id"])
    response = client.get(f"{BASE}/compare",
                          params={"a": a["id"], "b": b["id"]})
    assert response.status_code == 200
    body = response.json()
    states = {f["field"]: f["state"] for f in body["fields"]}
    assert states["universe_fingerprint"] == "same"
    assert states["combination_fingerprint"] == "changed"
    assert "no winner" in body["note"]
    assert any("combination policies differ" in w
               for w in body["warnings"])
