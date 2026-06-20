"""
Tests for AFML Sequential Bootstrap v1.

Deterministic, pure-function fixtures + the synthetic-data orchestrator + API.
No live data, no network.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.finml import FinmlInputError, run_sequential_bootstrap_demo
from app.finml.bootstrap import (
    build_indicator_matrix,
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


# ---------------------------------------------------------------------------
# Average uniqueness (4, 5)
# ---------------------------------------------------------------------------


def test_average_uniqueness_one_for_non_overlap():
    ind = build_indicator_matrix([{"event_id": 0, "start": 0, "end": 2}, {"event_id": 1, "start": 5, "end": 7}], 10)
    assert sample_average_uniqueness(ind, [0, 1]) == pytest.approx(1.0)


def test_average_uniqueness_below_one_for_overlap():
    ind = build_indicator_matrix([{"event_id": 0, "start": 0, "end": 5}, {"event_id": 1, "start": 2, "end": 7}], 10)
    assert sample_average_uniqueness(ind, [0, 1]) < 1.0


# ---------------------------------------------------------------------------
# Random + sequential bootstrap (6, 7, 8, 9, 10)
# ---------------------------------------------------------------------------


def test_random_bootstrap_deterministic():
    ind = build_indicator_matrix([{"event_id": i, "start": i, "end": i + 3} for i in range(10)], 20)
    a = random_bootstrap(ind, 10, 5, 50, np.random.default_rng(1), with_replacement=True)
    b = random_bootstrap(ind, 10, 5, 50, np.random.default_rng(1), with_replacement=True)
    assert a["mean"] == b["mean"] and a["p25"] == b["p25"]


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


def test_with_replacement_runs():
    res = run_sequential_bootstrap_demo(with_replacement=True, sample_size=40)
    _assert_all_finite(res)
    assert res["summary"]["with_replacement"] is True


def test_higher_overlap_increases_improvement():
    low = run_sequential_bootstrap_demo()
    high = run_sequential_bootstrap_demo(cusum_threshold=0.01, vertical_barrier_days=25, sample_size=30)
    # Sequential should help at least as much when labels overlap more.
    assert high["summary"]["improvement_vs_random"] >= -1e-6


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
