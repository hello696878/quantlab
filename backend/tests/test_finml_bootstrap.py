"""
Tests for AFML Sequential Bootstrap v1.

Deterministic, pure-function fixtures + the synthetic-data orchestrator + API.
No live data, no network.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.finml import FinmlInputError, run_labeling_demo, run_sequential_bootstrap_demo
from app.finml.bootstrap import (
    build_indicator_matrix,
    candidate_probabilities,
    event_uniqueness,
    random_bootstrap,
    sample_average_uniqueness,
    sequential_bootstrap,
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


# ---------------------------------------------------------------------------
# Indicator matrix (1, 2, 3)
# ---------------------------------------------------------------------------


def test_indicator_matrix_shape():
    intervals = [{"event_id": 0, "start": 0, "end": 2}, {"event_id": 1, "start": 5, "end": 7}]
    ind = build_indicator_matrix(intervals, 10)
    assert ind.shape == (10, 2)
    assert ind[:, 0].sum() == 3 and ind[:, 1].sum() == 3


def test_indicator_matrix_non_overlap():
    intervals = [{"event_id": 0, "start": 0, "end": 2}, {"event_id": 1, "start": 5, "end": 7}]
    ind = build_indicator_matrix(intervals, 10)
    assert int((ind[:, 0] + ind[:, 1]).max()) == 1  # never both active


def test_indicator_matrix_overlap():
    intervals = [{"event_id": 0, "start": 0, "end": 5}, {"event_id": 1, "start": 3, "end": 8}]
    ind = build_indicator_matrix(intervals, 10)
    assert int((ind[:, 0] + ind[:, 1]).max()) == 2  # both active in [3,5]


def test_indicator_matrix_inclusive_boundary_overlap():
    intervals = [{"event_id": 10, "start": 1, "end": 3}, {"event_id": 20, "start": 3, "end": 5}]
    ind = build_indicator_matrix(intervals, 7)
    assert ind[3].tolist() == [1, 1]
    assert int((ind[:, 0] + ind[:, 1]).sum()) == 6


def test_indicator_columns_preserve_event_order():
    intervals = [{"event_id": 42, "start": 4, "end": 4}, {"event_id": 7, "start": 1, "end": 2}]
    ind = build_indicator_matrix(intervals, 6)
    assert np.where(ind[:, 0] == 1)[0].tolist() == [4]
    assert np.where(ind[:, 1] == 1)[0].tolist() == [1, 2]


@pytest.mark.parametrize(
    "intervals,n_bars",
    [
        ([{"event_id": 0, "start": 3, "end": 2}], 5),
        ([{"event_id": 0, "start": -1, "end": 2}], 5),
        ([{"event_id": 0, "start": 1, "end": 5}], 5),
        ([{"event_id": 0, "start": 1}], 5),
        ([{"event_id": 0, "start": 1, "end": 2}, {"event_id": 0, "start": 3, "end": 4}], 5),
        ([], 0),
    ],
)
def test_indicator_matrix_rejects_invalid_intervals(intervals, n_bars):
    with pytest.raises(FinmlInputError):
        build_indicator_matrix(intervals, n_bars)


# ---------------------------------------------------------------------------
# Average uniqueness (4, 5)
# ---------------------------------------------------------------------------


def test_average_uniqueness_one_for_non_overlap():
    ind = build_indicator_matrix([{"event_id": 0, "start": 0, "end": 2}, {"event_id": 1, "start": 5, "end": 7}], 10)
    assert sample_average_uniqueness(ind, [0, 1]) == pytest.approx(1.0)


def test_average_uniqueness_below_one_for_overlap():
    ind = build_indicator_matrix([{"event_id": 0, "start": 0, "end": 5}, {"event_id": 1, "start": 2, "end": 7}], 10)
    assert sample_average_uniqueness(ind, [0, 1]) < 1.0


def test_event_uniqueness_aligns_with_selected_positions_and_mean():
    ind = build_indicator_matrix([{"event_id": 0, "start": 0, "end": 2}, {"event_id": 1, "start": 2, "end": 4}], 5)
    values = event_uniqueness(ind, [1, 0])
    assert values == pytest.approx([5 / 6, 5 / 6])
    assert sample_average_uniqueness(ind, [1, 0]) == pytest.approx(np.mean(values))


def test_empty_selection_and_repeated_event_uniqueness():
    ind = build_indicator_matrix([{"event_id": 0, "start": 0, "end": 2}], 4)
    assert event_uniqueness(ind, []) == []
    assert sample_average_uniqueness(ind, []) == 1.0
    assert sample_average_uniqueness(ind, [0, 0]) == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Random + sequential bootstrap (6, 7, 8, 9, 10)
# ---------------------------------------------------------------------------


def test_random_bootstrap_deterministic():
    ind = build_indicator_matrix([{"event_id": i, "start": i, "end": i + 3} for i in range(10)], 20)
    a = random_bootstrap(ind, 10, 5, 50, np.random.default_rng(1), with_replacement=True)
    b = random_bootstrap(ind, 10, 5, 50, np.random.default_rng(1), with_replacement=True)
    assert a["mean"] == b["mean"] and a["p25"] == b["p25"]
    assert a["min"] <= a["p25"] <= a["median"] <= a["p75"] <= a["max"]


def test_random_bootstrap_without_replacement_draws_unique_positions():
    class RecordingRng:
        def __init__(self):
            self.rng = np.random.default_rng(4)
            self.draws = []

        def choice(self, *args, **kwargs):
            draw = self.rng.choice(*args, **kwargs)
            self.draws.append(draw.tolist())
            return draw

    ind = build_indicator_matrix([{"event_id": i, "start": i, "end": i + 1} for i in range(8)], 10)
    rng = RecordingRng()
    random_bootstrap(ind, 8, 5, 10, rng, with_replacement=False)
    assert all(len(draw) == len(set(draw)) == 5 for draw in rng.draws)


def test_sequential_bootstrap_deterministic():
    ind = build_indicator_matrix([{"event_id": i, "start": i, "end": i + 3} for i in range(10)], 20)
    a = sequential_bootstrap(ind, 10, 5, np.random.default_rng(7), with_replacement=False)
    b = sequential_bootstrap(ind, 10, 5, np.random.default_rng(7), with_replacement=False)
    assert a[0] == b[0] and a[1] == b[1]


def test_sequential_bootstrap_sample_size():
    ind = build_indicator_matrix([{"event_id": i, "start": i, "end": i + 3} for i in range(12)], 20)
    sel, probs, path = sequential_bootstrap(ind, 12, 6, np.random.default_rng(3), with_replacement=False)
    assert len(sel) == 6 and len(probs) == 6 and len(path) == 6


def test_sequential_bootstrap_ids_valid():
    ind = build_indicator_matrix([{"event_id": i, "start": i, "end": i + 3} for i in range(12)], 20)
    sel, _p, _path = sequential_bootstrap(ind, 12, 6, np.random.default_rng(3), with_replacement=False)
    assert all(0 <= s < 12 for s in sel)


def test_sequential_bootstrap_without_replacement_no_duplicates():
    ind = build_indicator_matrix([{"event_id": i, "start": i, "end": i + 3} for i in range(12)], 20)
    sel, _p, _path = sequential_bootstrap(ind, 12, 12, np.random.default_rng(9), with_replacement=False)
    assert len(sel) == len(set(sel))


def test_candidate_probabilities_are_normalized_and_prefer_less_overlap():
    ind = build_indicator_matrix(
        [
            {"event_id": 0, "start": 0, "end": 4},
            {"event_id": 1, "start": 2, "end": 6},
            {"event_id": 2, "start": 8, "end": 9},
        ],
        10,
    )
    scores, probabilities = candidate_probabilities(ind, selected=[0], candidates=[1, 2])
    assert all(math.isfinite(value) and value >= 0 for value in scores + probabilities)
    assert sum(probabilities) == pytest.approx(1.0)
    assert scores[1] > scores[0]
    assert probabilities[1] > probabilities[0]


def test_sequential_helper_rejects_oversized_sample_without_replacement():
    ind = build_indicator_matrix([{"event_id": i, "start": i, "end": i} for i in range(3)], 3)
    with pytest.raises(FinmlInputError, match="cannot exceed"):
        sequential_bootstrap(ind, 3, 4, np.random.default_rng(1), with_replacement=False)


# ---------------------------------------------------------------------------
# Orchestrator + validation (11..17)
# ---------------------------------------------------------------------------


def test_sample_size_exceeds_events_without_replacement_rejected():
    with pytest.raises(FinmlInputError):
        run_sequential_bootstrap_demo(cusum_threshold=0.06, sample_size=2000, with_replacement=False)


def test_uniqueness_values_finite():
    res = run_sequential_bootstrap_demo()
    s = res["summary"]
    assert math.isfinite(s["sequential_average_uniqueness"])
    assert math.isfinite(s["random_average_uniqueness"])
    assert math.isfinite(s["improvement_vs_random"])


def test_invalid_random_trials_rejected():
    with pytest.raises(FinmlInputError):
        run_sequential_bootstrap_demo(random_trials=0)
    with pytest.raises(FinmlInputError):
        run_sequential_bootstrap_demo(random_trials=5000)


def test_invalid_sample_size_rejected():
    with pytest.raises(FinmlInputError):
        run_sequential_bootstrap_demo(sample_size=0)


def test_too_few_events_friendly_error():
    with pytest.raises(FinmlInputError) as exc:
        run_sequential_bootstrap_demo(n_days=100, cusum_threshold=5.0, sample_size=10)
    assert "Not enough labeled events" in str(exc.value)


def test_demo_deterministic_and_finite():
    a = run_sequential_bootstrap_demo()
    b = run_sequential_bootstrap_demo()
    assert a == b
    _assert_all_finite(a)
    assert len(a["selected_events"]) == a["summary"]["sample_size"]
    assert len(a["uniqueness_path"]) == a["summary"]["sample_size"]
    assert a["selected_events"][0]["draw_order"] == 1
    assert a["uniqueness_path"][0]["draw"] == 1
    assert a["summary"]["sequential_average_uniqueness"] == pytest.approx(
        a["uniqueness_path"][-1]["sequential_uniqueness"], abs=1e-6
    )
    assert all(event["start_index"] <= event["end_index"] for event in a["selected_events"])


def test_with_replacement_runs():
    res = run_sequential_bootstrap_demo(with_replacement=True, sample_size=40)
    _assert_all_finite(res)
    assert res["summary"]["with_replacement"] is True


def test_higher_overlap_scenario_remains_finite_without_performance_guarantee():
    high = run_sequential_bootstrap_demo(cusum_threshold=0.01, vertical_barrier_days=25, sample_size=30)
    assert math.isfinite(high["summary"]["improvement_vs_random"])
    assert "seeded sequential" in high["summary"]["overlap_reduction_note"]


def test_different_seed_produces_valid_sample():
    first = run_sequential_bootstrap_demo(seed=42)
    second = run_sequential_bootstrap_demo(seed=43)
    _assert_all_finite(second)
    assert first["selected_events"] != second["selected_events"]


def test_unsafe_combined_workload_rejected():
    with pytest.raises(FinmlInputError, match="workload"):
        run_sequential_bootstrap_demo(sample_size=2000, random_trials=1000, with_replacement=True)


def test_vol_scaled_bootstrap_reuses_labeling_semantics():
    labeling = run_labeling_demo(threshold_mode="vol_scaled", cusum_threshold=2.0)
    bootstrap = run_sequential_bootstrap_demo(
        threshold_mode="vol_scaled", cusum_threshold=2.0, sample_size=10, random_trials=20
    )
    assert bootstrap["summary"]["n_events"] == labeling["summary"]["n_events"]
    assert any("multiplier" in warning for warning in bootstrap["warnings"])


# ---------------------------------------------------------------------------
# API wiring
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(main_module.app)


def test_api_sequential_bootstrap(client):
    body = client.post(
        "/finml/sequential-bootstrap-demo",
        json={"n_days": 500, "start_price": 100, "drift": 0.0002, "volatility": 0.015, "seed": 42,
              "cusum_threshold": 0.02, "profit_take_multiple": 1.5, "stop_loss_multiple": 1.0,
              "vertical_barrier_days": 10, "sample_size": 25, "random_trials": 200, "with_replacement": False},
    ).json()
    assert body["summary"]["sample_size"] == 25
    assert len(body["selected_events"]) == 25
    assert body["random_baseline"]["n_trials"] == 200
    assert body["summary"]["sequential_average_uniqueness"] == pytest.approx(
        body["uniqueness_path"][-1]["sequential_uniqueness"], abs=1e-6
    )
    assert "indicator" not in body
    ids = [e["event_id"] for e in body["selected_events"]]
    assert len(ids) == len(set(ids))  # without replacement


@pytest.mark.parametrize(
    "payload",
    [
        {"sample_size": 0},
        {"sample_size": 99999},  # exceeds events without replacement
        {"random_trials": 0},
        {"random_trials": 5000},
        {"cusum_threshold": -1},
        {"vertical_barrier_days": 0},
    ],
)
def test_api_sequential_bootstrap_validation_422(client, payload):
    base = {"n_days": 500, "start_price": 100, "drift": 0.0002, "volatility": 0.015, "seed": 42,
            "cusum_threshold": 0.02, "profit_take_multiple": 1.5, "stop_loss_multiple": 1.0,
            "vertical_barrier_days": 10, "sample_size": 25, "random_trials": 200, "with_replacement": False}
    base.update(payload)
    assert client.post("/finml/sequential-bootstrap-demo", json=base).status_code == 422
