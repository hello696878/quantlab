"""
Engine tests for the Model Validation Lab (Phase 50.0): temporal-event
validation, interval overlap + boundary convention, splitters (k-fold /
walk-forward / purged k-fold / CPCV), purge cases, embargo modes, the leakage
audit invariant, fingerprints, and metrics.  Pure logic — no database.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

events = pytest.importorskip("app.model_validation.events")
engine = pytest.importorskip("app.model_validation.engine")
fingerprints = pytest.importorskip("app.model_validation.fingerprints")
metrics_mod = pytest.importorskip("app.model_validation.metrics")

BASE = datetime(2025, 1, 1)


def raw(i, *, start_day=None, end_day=None, horizon=5, **extra):
    start = start_day if start_day is not None else i
    end = end_day if end_day is not None else start + horizon
    return {
        "sample_id": f"s{i:03d}",
        "prediction_time": (BASE + timedelta(days=start)).isoformat(),
        "evaluation_time": (BASE + timedelta(days=end)).isoformat(),
        **extra,
    }


def make(n=40, horizon=5, **extra):
    return events.normalize_samples([raw(i, horizon=horizon, **extra) for i in range(n)])


# ---------------------------------------------------------------------------
# Event model
# ---------------------------------------------------------------------------


def test_eval_before_pred_rejected():
    with pytest.raises(events.EventError):
        events.normalize_samples([raw(0, start_day=5, end_day=1)] + [raw(i) for i in range(1, 5)])


def test_duplicate_ids_rejected():
    bad = [raw(0), raw(0), raw(1), raw(2)]
    with pytest.raises(events.EventError):
        events.normalize_samples(bad)


def test_invalid_timestamp_rejected():
    bad = [dict(raw(0), prediction_time="not-a-date")] + [raw(i) for i in range(1, 5)]
    with pytest.raises(events.EventError):
        events.normalize_samples(bad)


def test_mixed_timezone_awareness_rejected():
    bad = [raw(i) for i in range(4)] + [
        dict(raw(4), prediction_time="2025-01-05T00:00:00+00:00",
             evaluation_time="2025-01-10T00:00:00+00:00")
    ]
    with pytest.raises(events.EventError):
        events.normalize_samples(bad)


def test_non_finite_values_rejected():
    bad = [dict(raw(0), label=float("nan"))] + [raw(i) for i in range(1, 5)]
    with pytest.raises(events.EventError):
        events.normalize_samples(bad)


def test_missing_evaluation_requires_explicit_policy():
    missing = [dict(raw(i)) for i in range(5)]
    del missing[2]["evaluation_time"]
    with pytest.raises(events.EventError):
        events.normalize_samples(missing)
    ok = events.normalize_samples(missing, allow_missing_evaluation="prediction_time")
    zero = next(s for s in ok if s["sample_id"] == "s002")
    assert zero["pred_dt"] == zero["eval_dt"]


def test_deterministic_sort_with_equal_timestamps():
    same = [
        dict(raw(0), sample_id="zzz"),
        dict(raw(0), sample_id="aaa"),
        dict(raw(0), sample_id="mmm"),
        raw(1),
    ]
    out = events.normalize_samples(same)
    assert [s["sample_id"] for s in out[:3]] == ["aaa", "mmm", "zzz"]


def test_sample_count_bounds():
    with pytest.raises(events.EventError):
        events.normalize_samples([raw(0)])
    with pytest.raises(events.EventError):
        events.normalize_samples([raw(i) for i in range(events.MAX_SAMPLES + 1)])


# ---------------------------------------------------------------------------
# Interval convention + purge cases (§6)
# ---------------------------------------------------------------------------


def _purge_case(train_iv, test_iv):
    """Build 4+ samples; return True iff the train sample got purged."""
    samples = events.normalize_samples([
        {"sample_id": "train", "prediction_time": train_iv[0], "evaluation_time": train_iv[1]},
        {"sample_id": "test", "prediction_time": test_iv[0], "evaluation_time": test_iv[1]},
        raw(90, start_day=90), raw(95, start_day=95),
    ])
    pos = {s["sample_id"]: i for i, s in enumerate(samples)}
    kept, purged, reasons = engine.purge_positions(samples, [pos["train"]], [pos["test"]])
    if purged:
        assert reasons[samples[purged[0]]["sample_id"]].startswith("overlaps test sample")
    return bool(purged)


D = lambda d: (BASE + timedelta(days=d)).isoformat()


def test_purge_train_starts_inside_test():
    assert _purge_case((D(5), D(12)), (D(3), D(8)))


def test_purge_train_ends_inside_test():
    assert _purge_case((D(0), D(5)), (D(3), D(8)))


def test_purge_train_contains_test():
    assert _purge_case((D(0), D(20)), (D(5), D(8)))


def test_purge_test_contains_train():
    assert _purge_case((D(5), D(6)), (D(3), D(8)))


def test_purge_exact_boundary_contact_counts_as_overlap():
    # Closed intervals: train ends exactly where test starts → overlap → purged.
    assert _purge_case((D(0), D(3)), (D(3), D(8)))
    # And clear separation is kept.
    assert not _purge_case((D(0), D(2)), (D(3), D(8)))


def test_purge_multiple_disjoint_test_intervals():
    samples = events.normalize_samples([
        {"sample_id": "t1", "prediction_time": D(0), "evaluation_time": D(2)},
        {"sample_id": "trainA", "prediction_time": D(4), "evaluation_time": D(5)},
        {"sample_id": "t2", "prediction_time": D(8), "evaluation_time": D(10)},
        {"sample_id": "trainB", "prediction_time": D(9), "evaluation_time": D(12)},
    ])
    pos = {s["sample_id"]: i for i, s in enumerate(samples)}
    kept, purged, _ = engine.purge_positions(
        samples, [pos["trainA"], pos["trainB"]], [pos["t1"], pos["t2"]]
    )
    kept_ids = {samples[p]["sample_id"] for p in kept}
    purged_ids = {samples[p]["sample_id"] for p in purged}
    assert kept_ids == {"trainA"}          # between the blocks, no overlap
    assert purged_ids == {"trainB"}        # overlaps second block


def test_purge_long_horizon_and_irregular_timestamps():
    samples = events.normalize_samples([
        {"sample_id": "long", "prediction_time": D(0), "evaluation_time": D(50)},
        {"sample_id": "test", "prediction_time": D(30), "evaluation_time": D(31)},
        {"sample_id": "far", "prediction_time": D(100), "evaluation_time": D(101)},
        {"sample_id": "odd", "prediction_time": D(51) + "T07:13:22"[10:], "evaluation_time": D(52)},
    ])
    pos = {s["sample_id"]: i for i, s in enumerate(samples)}
    kept, purged, _ = engine.purge_positions(
        samples, [pos["long"], pos["far"], pos["odd"]], [pos["test"]]
    )
    assert {samples[p]["sample_id"] for p in purged} == {"long"}


# ---------------------------------------------------------------------------
# Embargo
# ---------------------------------------------------------------------------


def test_embargo_duration_removes_starts_in_window():
    samples = make(30, horizon=0)  # zero-length intervals: purge won't fire
    test_pos = list(range(10, 15))
    train_pos = [p for p in range(30) if p not in set(test_pos)]
    delta = engine.resolve_embargo_delta(samples, {"mode": "duration_days", "value": 3})
    kept, embargoed, windows = engine.apply_embargo_positions(samples, train_pos, test_pos, delta)
    embargoed_ids = {samples[p]["sample_id"] for p in embargoed}
    # test block ends day 14; window (day14, day17] → samples 15, 16, 17
    assert embargoed_ids == {"s015", "s016", "s017"}
    assert len(windows) == 1


def test_embargo_fraction_and_bounds():
    samples = make(30, horizon=0)
    assert engine.resolve_embargo_delta(samples, {"mode": "none"}) is None
    delta = engine.resolve_embargo_delta(samples, {"mode": "fraction", "value": 0.1})
    assert delta is not None and delta.total_seconds() > 0
    for bad in (
        {"mode": "fraction", "value": 0.5},
        {"mode": "duration_days", "value": -1},
        {"mode": "banana", "value": 1},
        {"mode": "duration_days", "value": float("nan")},
    ):
        with pytest.raises(engine.SplitConfigError):
            engine.resolve_embargo_delta(samples, bad)


def test_embargo_applied_after_each_disjoint_block():
    samples = make(40, horizon=0)
    test_pos = list(range(5, 8)) + list(range(25, 28))  # two disjoint blocks
    train_pos = [p for p in range(40) if p not in set(test_pos)]
    delta = engine.resolve_embargo_delta(samples, {"mode": "duration_days", "value": 2})
    _, embargoed, windows = engine.apply_embargo_positions(samples, train_pos, test_pos, delta)
    assert len(windows) == 2
    embargoed_ids = {samples[p]["sample_id"] for p in embargoed}
    assert embargoed_ids == {"s008", "s009", "s028", "s029"}


def test_embargo_at_final_boundary_is_harmless():
    samples = make(10, horizon=0)
    test_pos = list(range(7, 10))  # last block: window extends past the data end
    train_pos = list(range(0, 7))
    delta = engine.resolve_embargo_delta(samples, {"mode": "duration_days", "value": 5})
    kept, embargoed, _ = engine.apply_embargo_positions(samples, train_pos, test_pos, delta)
    assert embargoed == [] and len(kept) == 7


# ---------------------------------------------------------------------------
# Splitters + audit invariant
# ---------------------------------------------------------------------------


def test_standard_kfold_reference_leaks_and_audits_invalid():
    samples = make(40)
    splits = engine.standard_kfold(samples, {"n_folds": 4})
    audits = [engine.audit_split(samples, s, "standard_kfold") for s in splits]
    assert any(a["remaining_overlap_count"] > 0 for a in audits)
    assert all(not a["valid"] for a in audits if a["remaining_overlap_count"] > 0)


def test_standard_kfold_shuffle_requires_seed_and_is_deterministic():
    samples = make(20, horizon=0)
    with pytest.raises(engine.SplitConfigError):
        engine.standard_kfold(samples, {"n_folds": 4, "shuffle": True})
    a = engine.standard_kfold(samples, {"n_folds": 4, "shuffle": True, "random_seed": 7})
    b = engine.standard_kfold(samples, {"n_folds": 4, "shuffle": True, "random_seed": 7})
    assert [s["test_pos"] for s in a] == [s["test_pos"] for s in b]


def test_walk_forward_expanding_and_rolling():
    samples = make(40, horizon=2)
    exp = engine.walk_forward(samples, {"min_train_size": 10, "test_size": 5})
    assert all(max(s["train_pos"], default=-1) < min(s["test_pos"]) for s in exp)
    # Expanding: training always starts at 0.
    assert all(min(s["train_pos"]) == 0 for s in exp)
    roll = engine.walk_forward(
        samples, {"min_train_size": 10, "test_size": 5, "window": "rolling", "rolling_size": 8}
    )
    assert all(len(s["train_pos"]) + len(s["purged_pos"]) + len(s["embargoed_pos"]) <= 8 for s in roll)
    audits = [engine.audit_split(samples, s, "walk_forward") for s in exp]
    assert all(a["valid"] for a in audits)
    assert all(a["chronological_violations"] == 0 for a in audits)


def test_purged_kfold_invariant_no_remaining_overlap():
    samples = make(50, horizon=7)
    splits = engine.purged_kfold(
        samples, {"n_folds": 5, "embargo": {"mode": "duration_days", "value": 2}}
    )
    for s in splits:
        audit = engine.audit_split(samples, s, "purged_kfold")
        assert audit["remaining_overlap_count"] == 0
        assert audit["valid"]
        assert audit["duplicate_assignments"] == 0
        assert audit["unassigned_samples"] == 0
        # purge and embargo reported separately
        assert set(s["purged_pos"]).isdisjoint(set(s["embargoed_pos"]))


def test_cpcv_combinations_deterministic_and_bounded():
    samples = make(40, horizon=3)
    splits = engine.cpcv(samples, {"n_groups": 5, "test_groups": 2})
    assert len(splits) == 10  # C(5,2)
    labels = [s["split_label"] for s in splits]
    assert labels == sorted(labels) or labels == labels  # deterministic order
    again = engine.cpcv(samples, {"n_groups": 5, "test_groups": 2})
    assert [s["split_label"] for s in again] == labels
    for s in splits:
        assert engine.audit_split(samples, s, "cpcv")["remaining_overlap_count"] == 0
    with pytest.raises(engine.SplitConfigError):
        engine.cpcv(samples, {"n_groups": 12, "test_groups": 6})  # C=924 > limit
    with pytest.raises(engine.SplitConfigError):
        engine.cpcv(samples, {"n_groups": 4, "test_groups": 4})
    with pytest.raises(engine.SplitConfigError):
        engine.cpcv(samples, {"n_groups": 30, "test_groups": 1})


def test_folds_greater_than_samples_rejected():
    samples = make(6, horizon=0)
    with pytest.raises(engine.SplitConfigError):
        engine.purged_kfold(samples, {"n_folds": 10})
    with pytest.raises(engine.SplitConfigError):
        engine.validate_config("purged_kfold", samples, {"n_folds": 10})


def test_audit_detects_duplicates_and_unassigned():
    samples = make(10, horizon=0)
    split = {
        "split_label": "x", "train_pos": [0, 1, 2], "test_pos": [2, 3],
        "purged_pos": [], "embargoed_pos": [], "purge_reasons": {},
        "embargo_windows": [],
    }
    audit = engine.audit_split(samples, split, "purged_kfold")
    assert audit["duplicate_assignments"] == 1
    assert audit["unassigned_samples"] == 6
    assert not audit["valid"]


def test_audit_rejects_empty_required_set():
    # A split that purged away its entire training set has no remaining overlap
    # only because nothing is left — it must NOT be reported valid/leakage-clean.
    samples = make(10, horizon=0)
    empty_train = {
        "split_label": "degenerate", "train_pos": [], "test_pos": [5, 6],
        "purged_pos": [0, 1, 2, 3, 4, 7, 8, 9], "embargoed_pos": [],
        "purge_reasons": {}, "embargo_windows": [],
    }
    audit = engine.audit_split(samples, empty_train, "purged_kfold")
    assert audit["remaining_overlap_count"] == 0
    assert audit["empty_train"] is True
    assert not audit["valid"]

    empty_test = {
        "split_label": "degenerate2", "train_pos": [0, 1, 2], "test_pos": [],
        "purged_pos": [], "embargoed_pos": [], "purge_reasons": {}, "embargo_windows": [],
    }
    audit2 = engine.audit_split(samples, empty_test, "purged_kfold")
    assert audit2["empty_test"] is True
    assert not audit2["valid"]


def test_embargo_fraction_span_uses_latest_evaluation_time():
    # Irregular horizons: the sample with the LATEST prediction time has a short
    # horizon, while an earlier sample carries the latest evaluation time. The
    # fraction span must run to that latest eval time (per the documented policy),
    # not to the last-by-prediction sample's eval time.
    samples = events.normalize_samples([
        raw(0, start_day=0, end_day=1),     # pred 0,  eval 1
        raw(1, start_day=2, end_day=40),    # pred 2,  eval 40  ← latest eval
        raw(2, start_day=5, end_day=6),     # pred 5,  eval 6   ← last by prediction
        raw(3, start_day=3, end_day=4),
    ])
    delta = engine.resolve_embargo_delta(samples, {"mode": "fraction", "value": 0.1})
    # earliest pred = day 0, latest eval = day 40 → span 40d → 10% = 4 days.
    assert delta == timedelta(days=4)


# ---------------------------------------------------------------------------
# Fingerprints
# ---------------------------------------------------------------------------


def test_configuration_fingerprint_deterministic_and_sensitive():
    samples = make(10)
    fp = lambda **o: fingerprints.configuration_fingerprint(
        method=o.pop("method", "purged_kfold"), samples=samples,
        configuration=o.pop("configuration", {"n_folds": 5}), **o)
    assert fp() == fp()
    assert fp(configuration={"n_folds": 4}) != fp()
    assert fp(method="cpcv") != fp()
    assert fp(random_seed=1) != fp()


def test_split_and_result_fingerprints():
    a = fingerprints.split_fingerprint(
        configuration_fp="c" * 64, split_label="f0",
        train_ids=["b", "a"], test_ids=["c"], purged_ids=[], embargoed_ids=[])
    b = fingerprints.split_fingerprint(
        configuration_fp="c" * 64, split_label="f0",
        train_ids=["a", "b"], test_ids=["c"], purged_ids=[], embargoed_ids=[])
    assert a == b  # membership identity is order-independent
    c2 = fingerprints.split_fingerprint(
        configuration_fp="c" * 64, split_label="f0",
        train_ids=["a"], test_ids=["b", "c"], purged_ids=[], embargoed_ids=[])
    assert a != c2
    r1 = fingerprints.result_fingerprint(
        configuration_fp="c" * 64, split_fps=[a], aggregate_metrics={"x": 1},
        leakage_summary={"leakage_clean": True})
    r2 = fingerprints.result_fingerprint(
        configuration_fp="c" * 64, split_fps=[a], aggregate_metrics={"x": 2},
        leakage_summary={"leakage_clean": True})
    assert r1 != r2


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def test_classification_metrics_and_reasons():
    samples = make(20, horizon=0, label=1, prediction=1)
    block = metrics_mod.split_metrics(samples, list(range(20)))
    assert block["metrics"]["accuracy"] == 1.0
    assert block["metrics"]["recall"] == 1.0
    # No negative labels → roc_auc undefined with a reason, never Infinity.
    assert block["metrics"]["roc_auc"] is None
    assert "roc_auc" in block["reasons"]


def test_regression_metrics():
    rawlist = [raw(i, horizon=0, label=i * 1.5, prediction=i * 1.5 + 1.0) for i in range(10)]
    samples = events.normalize_samples(rawlist)
    block = metrics_mod.split_metrics(samples, list(range(10)))
    assert block["metrics"]["mae"] == pytest.approx(1.0)
    assert block["metrics"]["rmse"] == pytest.approx(1.0)
    assert block["metrics"]["r2"] is not None


def test_undefined_metrics_are_null_with_reason_not_zero():
    samples = make(10, horizon=0)  # no labels/predictions/returns at all
    block = metrics_mod.split_metrics(samples, list(range(10)))
    for name in ("accuracy", "roc_auc", "mae", "sharpe_like"):
        assert block["metrics"][name] is None
        assert block["reasons"][name]


def test_zero_variance_r2_and_zero_std_sharpe_are_null():
    rawlist = [raw(i, horizon=0, label=2.5, prediction=2.0, ret=0.01) for i in range(8)]
    samples = events.normalize_samples(rawlist)
    block = metrics_mod.split_metrics(samples, list(range(8)))
    assert block["metrics"]["r2"] is None
    assert block["metrics"]["sharpe_like"] is None


def test_aggregate_metrics():
    blocks = [
        {"metrics": {"accuracy": 0.5}, "reasons": {}},
        {"metrics": {"accuracy": 0.7}, "reasons": {}},
        {"metrics": {"accuracy": None}, "reasons": {"accuracy": "n/a"}},
    ]
    agg = metrics_mod.aggregate_metrics(blocks)
    assert agg["accuracy"]["valid_folds"] == 2
    assert agg["accuracy"]["mean"] == pytest.approx(0.6)
    assert agg["accuracy"]["min"] == 0.5 and agg["accuracy"]["max"] == 0.7
