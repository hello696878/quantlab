"""
Tests for AFML Purged K-Fold + Embargo CV v1.

Deterministic, pure-function fixtures + the synthetic-data orchestrator + API.
No live data, no network.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from app.finml import FinmlInputError, run_labeling_demo, run_purged_cv_demo
from app.finml.cv import (
    apply_embargo,
    build_label_intervals,
    count_overlaps,
    intervals_overlap,
    make_purged_kfold_splits,
    purge_train_indices,
    split_kfold_by_time,
)

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


# Overlapping-label fixture: every event overlaps its neighbours (interval length 5,
# starts step 2), so contiguous folds will leak at the boundaries.
_OVERLAP_INTERVALS = [
    {"event_id": i, "start": 2 * i, "end": 2 * i + 5, "label": 1 if i % 2 == 0 else -1}
    for i in range(20)
]


def _dates(n: int) -> list[str]:
    start = date(2020, 1, 1)
    return [(start + timedelta(days=i)).isoformat() for i in range(n)]


# ---------------------------------------------------------------------------
# Interval overlap (1, 2)
# ---------------------------------------------------------------------------


def test_interval_overlap_detected():
    assert intervals_overlap(0, 5, 3, 8) is True
    assert intervals_overlap(3, 8, 0, 5) is True
    assert intervals_overlap(0, 5, 5, 9) is True  # inclusive touch


def test_inclusive_overlap_boundary_cases():
    assert intervals_overlap(1, 3, 3, 5) is True
    assert intervals_overlap(1, 2, 3, 5) is False
    assert intervals_overlap(2, 6, 3, 5) is True
    assert intervals_overlap(6, 7, 3, 5) is False


def test_non_overlapping_not_flagged():
    assert intervals_overlap(0, 4, 5, 9) is False
    assert intervals_overlap(20, 25, 0, 5) is False


# ---------------------------------------------------------------------------
# K-fold baseline (3)
# ---------------------------------------------------------------------------


def test_standard_kfold_creates_expected_folds():
    blocks = split_kfold_by_time(20, 5)
    assert len(blocks) == 5
    assert sum(len(b) for b in blocks) == 20
    # Time-ordered, contiguous, non-overlapping.
    flat = [p for b in blocks for p in b]
    assert flat == list(range(20))
    assert all(block == list(range(block[0], block[-1] + 1)) for block in blocks)
    assert len(flat) == len(set(flat))


def test_standard_kfold_rejects_more_folds_than_events():
    with pytest.raises(FinmlInputError, match="cannot exceed"):
        split_kfold_by_time(3, 4)


# ---------------------------------------------------------------------------
# Purge (4, 5)
# ---------------------------------------------------------------------------


def test_purge_removes_overlapping_train_events():
    intervals = [
        {"event_id": 0, "start": 0, "end": 5},
        {"event_id": 1, "start": 4, "end": 9},  # overlaps test (0)
        {"event_id": 2, "start": 20, "end": 25},  # no overlap
    ]
    kept, purged = purge_train_indices([1, 2], [0], intervals)
    assert purged == [1]
    assert kept == [2]


def test_no_train_overlaps_test_after_purge():
    intervals = _OVERLAP_INTERVALS
    test_pos = [8, 9, 10, 11]  # a contiguous middle block
    train_std = [p for p in range(len(intervals)) if p not in set(test_pos)]
    kept, _purged = purge_train_indices(train_std, test_pos, intervals)
    assert count_overlaps(kept, test_pos, intervals) == 0


def test_fold_payload_exposes_disjoint_final_train_and_removed_ids():
    folds = make_purged_kfold_splits(_OVERLAP_INTERVALS, 5, 2, _dates(50))
    id_to_pos = {iv["event_id"]: i for i, iv in enumerate(_OVERLAP_INTERVALS)}
    for fold in folds:
        train = set(fold["train_event_ids"])
        test = set(fold["test_event_ids"])
        purged = set(fold["purged_event_ids"])
        embargoed = set(fold["embargoed_event_ids"])
        assert not (train & test or train & purged or train & embargoed)
        assert not (test & purged or test & embargoed or purged & embargoed)
        assert count_overlaps(
            [id_to_pos[event_id] for event_id in train],
            [id_to_pos[event_id] for event_id in test],
            _OVERLAP_INTERVALS,
        ) == 0


# ---------------------------------------------------------------------------
# Embargo (6, 7)
# ---------------------------------------------------------------------------


def test_embargo_removes_events_after_test():
    intervals = [
        {"event_id": 0, "start": 0, "end": 5},
        {"event_id": 1, "start": 4, "end": 9},
        {"event_id": 2, "start": 20, "end": 25},
    ]
    # test ends at bar 5; embargo window (5, 8] → event 1 (start 4) is NOT in it; widen.
    kept, embargoed = apply_embargo([1, 2], test_end_bar=2, intervals=intervals, embargo_bars=3)
    assert embargoed == [1]  # start 4 ∈ (2, 5]
    assert kept == [2]


def test_embargo_zero_removes_nothing():
    intervals = _OVERLAP_INTERVALS
    kept, embargoed = apply_embargo([1, 2, 3], test_end_bar=10, intervals=intervals, embargo_bars=0)
    assert embargoed == []
    assert kept == [1, 2, 3]


def test_embargo_window_is_open_at_test_end_and_closed_at_window_end():
    intervals = [
        {"event_id": 0, "start": 2, "end": 2},
        {"event_id": 1, "start": 3, "end": 3},
        {"event_id": 2, "start": 5, "end": 5},
        {"event_id": 3, "start": 6, "end": 6},
    ]
    kept, embargoed = apply_embargo([0, 1, 2, 3], 2, intervals, 3)
    assert embargoed == [1, 2]
    assert kept == [0, 3]


def test_last_fold_embargo_is_safely_empty():
    intervals = [{"event_id": i, "start": i, "end": i, "label": 1} for i in range(9)]
    last = make_purged_kfold_splits(intervals, 3, 2, _dates(9))[-1]
    assert last["embargoed_count"] == 0
    assert last["embargo_start_date"] is None
    assert last["embargo_end_date"] is None
    assert last["embargo_start_index"] is None
    assert last["embargo_end_index"] is None


@pytest.mark.parametrize("dates", [["not-a-date"] * 9, list(reversed(_dates(9)))])
def test_split_rejects_invalid_or_non_monotonic_dates(dates):
    intervals = [{"event_id": i, "start": i, "end": i, "label": 1} for i in range(9)]
    with pytest.raises(FinmlInputError, match="dates"):
        make_purged_kfold_splits(intervals, 3, 0, dates)


# ---------------------------------------------------------------------------
# Validation (8, 9, 10)
# ---------------------------------------------------------------------------


def test_too_few_events_returns_friendly_error():
    # A very high threshold yields ~0 events → cannot form folds.
    with pytest.raises(FinmlInputError) as exc:
        run_purged_cv_demo(n_days=100, cusum_threshold=5.0, n_splits=5)
    assert "Not enough labeled events" in str(exc.value)


def test_invalid_n_splits_rejected():
    with pytest.raises(FinmlInputError):
        run_purged_cv_demo(n_splits=1)
    with pytest.raises(FinmlInputError):
        run_purged_cv_demo(n_splits=100)


def test_invalid_embargo_pct_rejected():
    with pytest.raises(FinmlInputError):
        run_purged_cv_demo(embargo_pct=-0.1)
    with pytest.raises(FinmlInputError):
        run_purged_cv_demo(embargo_pct=0.5)


# ---------------------------------------------------------------------------
# Diagnostics + orchestrator (11, 12, 13, 14, 15)
# ---------------------------------------------------------------------------


def test_fold_counts_internally_consistent():
    res = run_purged_cv_demo()
    n_events = res["summary"]["n_events"]
    for f in res["folds"]:
        # Every original train event is kept, purged, or embargoed.
        assert f["train_count_after"] + f["purged_count"] + f["embargoed_count"] == f["train_count_before"]
        assert f["train_count_before"] + f["test_count"] == n_events


def test_leakage_before_can_be_positive_and_after_zero():
    res = run_purged_cv_demo()
    assert any(f["standard_train_overlap_count"] > 0 for f in res["folds"])
    assert all(f["purged_overlap_count_after_purge"] == 0 for f in res["folds"])
    assert res["summary"]["folds_with_overlap_after_purge"] == 0


def test_leakage_reduction_non_negative():
    res = run_purged_cv_demo()
    for f in res["folds"]:
        assert f["leakage_reduction"] >= 0


def test_purged_cv_deterministic():
    assert run_purged_cv_demo() == run_purged_cv_demo()


def test_no_nan_in_response():
    _assert_all_finite(run_purged_cv_demo())
    _assert_all_finite(run_purged_cv_demo(embargo_pct=0.0, n_splits=4))


def test_build_label_intervals_sorted():
    labels = [
        {"event_id": 0, "start_index": 10, "end_index": 15, "label": 1},
        {"event_id": 1, "start_index": 2, "end_index": 6, "label": -1},
    ]
    rows = build_label_intervals(labels)
    assert [r["start"] for r in rows] == [2, 10]


@pytest.mark.parametrize(
    "labels",
    [
        [{"event_id": 0, "start_index": 3, "end_index": 2, "label": 1}],
        [{"event_id": 0, "start_index": 1, "label": 1}],
        [{"event_id": 0, "start_index": 1, "end_index": 2, "label": 2}],
        [
            {"event_id": 0, "start_index": 1, "end_index": 2, "label": 1},
            {"event_id": 0, "start_index": 3, "end_index": 4, "label": -1},
        ],
    ],
)
def test_build_label_intervals_rejects_invalid_rows(labels):
    with pytest.raises(FinmlInputError):
        build_label_intervals(labels)


def test_summary_diagnostics_match_fold_totals_and_fractions():
    res = run_purged_cv_demo()
    assert res["summary"]["total_overlap_before_purge"] == sum(
        fold["standard_train_overlap_count"] for fold in res["folds"]
    )
    assert res["summary"]["total_overlap_after_purge"] == 0
    assert all(0.0 <= fold["train_fraction_remaining"] <= 1.0 for fold in res["folds"])


def test_positive_embargo_fraction_rounds_up_to_one_bar():
    res = run_purged_cv_demo(n_days=100, n_splits=2, cusum_threshold=0.01, embargo_pct=0.0001)
    assert res["summary"]["embargo_bars"] == 1


def test_cv_reuses_same_labels_as_labeling_demo():
    labeling = run_labeling_demo(seed=42, threshold_mode="vol_scaled", cusum_threshold=2.0)
    cv = run_purged_cv_demo(seed=42, threshold_mode="vol_scaled", cusum_threshold=2.0)
    assert cv["summary"]["n_events"] == labeling["summary"]["n_events"]
    assert [(row["event_id"], row["start_date"], row["end_date"], row["label"]) for row in cv["timeline"]] == [
        (row["event_id"], row["start_date"], row["end_date"], row["label"])
        for row in labeling["labels"]
    ]
    assert any("multiplier" in warning for warning in cv["warnings"])


# ---------------------------------------------------------------------------
# API wiring
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(main_module.app)


def test_api_purged_cv(client):
    body = client.post(
        "/finml/purged-cv-demo",
        json={"n_days": 500, "start_price": 100, "drift": 0.0002, "volatility": 0.015, "seed": 42,
              "cusum_threshold": 0.02, "profit_take_multiple": 1.5, "stop_loss_multiple": 1.0,
              "vertical_barrier_days": 10, "n_splits": 5, "embargo_pct": 0.01},
    ).json()
    assert body["summary"]["n_splits"] == 5
    assert len(body["folds"]) == 5
    assert body["timeline"]
    assert body["summary"]["folds_with_overlap_after_purge"] == 0
    assert body["summary"]["total_overlap_after_purge"] == 0
    assert all(len(fold["train_event_ids"]) == fold["train_count_after"] for fold in body["folds"])


def test_api_embargo_zero_reduces_embargo(client):
    base = {"n_days": 500, "start_price": 100, "drift": 0.0002, "volatility": 0.015, "seed": 42,
            "cusum_threshold": 0.02, "profit_take_multiple": 1.5, "stop_loss_multiple": 1.0,
            "vertical_barrier_days": 10, "n_splits": 5}
    with_emb = client.post("/finml/purged-cv-demo", json={**base, "embargo_pct": 0.02}).json()
    no_emb = client.post("/finml/purged-cv-demo", json={**base, "embargo_pct": 0.0}).json()
    assert no_emb["summary"]["total_embargoed"] == 0
    assert with_emb["summary"]["total_embargoed"] >= no_emb["summary"]["total_embargoed"]


@pytest.mark.parametrize(
    "payload",
    [
        {"n_splits": 1},
        {"n_splits": 100},
        {"embargo_pct": -0.1},
        {"embargo_pct": 0.5},
        {"cusum_threshold": -1},
        {"vertical_barrier_days": 0},
    ],
)
def test_api_purged_cv_validation_422(client, payload):
    base = {"n_days": 500, "start_price": 100, "drift": 0.0002, "volatility": 0.015, "seed": 42,
            "cusum_threshold": 0.02, "profit_take_multiple": 1.5, "stop_loss_multiple": 1.0,
            "vertical_barrier_days": 10, "n_splits": 5, "embargo_pct": 0.01}
    base.update(payload)
    assert client.post("/finml/purged-cv-demo", json=base).status_code == 422
