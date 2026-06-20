"""
Tests for the AFML Methodology Layer v1 (CUSUM / triple-barrier / uniqueness).

Deterministic synthetic data + pure-function fixtures plus API wiring.
No live data, no network.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.finml import FinmlInputError, run_labeling_demo
from app.finml.cusum import cusum_events
from app.finml.labeling import triple_barrier_labels
from app.finml.sample_data import generate_synthetic_path
from app.finml.uniqueness import average_uniqueness, compute_concurrency, sample_weights

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
# Synthetic data (1, 2, 3)
# ---------------------------------------------------------------------------


def test_path_deterministic_same_seed():
    a = generate_synthetic_path(200, 100, 0.0002, 0.015, 42, 20)
    b = generate_synthetic_path(200, 100, 0.0002, 0.015, 42, 20)
    assert np.array_equal(a["close"], b["close"])
    assert a["dates"] == b["dates"]


def test_path_different_seed_changes_path():
    a = generate_synthetic_path(200, 100, 0.0002, 0.015, 42, 20)
    b = generate_synthetic_path(200, 100, 0.0002, 0.015, 43, 20)
    assert not np.array_equal(a["close"], b["close"])


def test_path_prices_positive():
    p = generate_synthetic_path(300, 100, 0.0, 0.02, 7, 20)
    assert np.all(p["close"] > 0)


def test_path_returns_and_vol_finite():
    p = generate_synthetic_path(300, 100, 0.0, 0.02, 7, 20)
    assert np.all(np.isfinite(p["returns"]))
    assert np.all(np.isfinite(p["rolling_vol"]))
    assert np.all(p["rolling_vol"] > 0)


def test_volatility_input_affects_path_variability():
    low = generate_synthetic_path(500, 100, 0.0, 0.005, 42, 20)
    high = generate_synthetic_path(500, 100, 0.0, 0.03, 42, 20)
    assert float(np.std(high["returns"][1:])) > float(np.std(low["returns"][1:]))


# ---------------------------------------------------------------------------
# CUSUM (4, 5)
# ---------------------------------------------------------------------------


def test_cusum_creates_events_on_fixture():
    rets = np.array([0.0, 0.01, 0.01, 0.01, -0.01, -0.03])
    events = cusum_events(rets, 0.025)
    assert len(events) >= 2
    assert events[0]["index"] == 3 and events[0]["side"] == "positive"
    assert any(e["side"] == "negative" for e in events)


def test_cusum_positive_fixture():
    rets = np.array([0.0, 0.01, 0.01, 0.01])
    events = cusum_events(rets, 0.02)
    assert events == [{"index": 3, "side": "positive", "threshold_used": 0.02, "return_at_event": 0.01}]


def test_cusum_negative_fixture():
    rets = np.array([0.0, -0.01, -0.01, -0.01])
    events = cusum_events(rets, 0.02)
    assert events == [{"index": 3, "side": "negative", "threshold_used": 0.02, "return_at_event": -0.01}]


def test_cusum_no_event_when_threshold_high():
    rets = np.array([0.0, 0.01, 0.01, 0.01, -0.01, -0.03])
    assert cusum_events(rets, 1.0) == []


def test_cusum_vol_scaled_threshold_uses_multiplier():
    rets = np.array([0.0, 0.01, 0.01, 0.01])
    vol = np.full(4, 0.01)
    events = cusum_events(rets, 2.0, threshold_mode="vol_scaled", rolling_vol=vol)
    assert events and events[0]["threshold_used"] == pytest.approx(0.02, abs=1e-12)


def test_cusum_skips_non_finite_returns():
    rets = np.array([0.0, 0.01, np.nan, 0.01, 0.01])
    events = cusum_events(rets, 0.02)
    assert events == []


# ---------------------------------------------------------------------------
# Triple-barrier (6, 7, 8, 9, 10)
# ---------------------------------------------------------------------------


def test_triple_barrier_profit_take():
    close = np.array([100, 101, 103, 106, 110, 112], dtype=float)
    vol = np.full(6, 0.02)
    lab = triple_barrier_labels(close, [0], vol, 1.5, 1.0, 5)[0]
    assert lab["label"] == 1 and lab["touched_barrier"] == "profit_take"


def test_triple_barrier_stop_loss():
    close = np.array([100, 99, 97, 94, 90, 88], dtype=float)
    vol = np.full(6, 0.02)
    lab = triple_barrier_labels(close, [0], vol, 1.5, 1.0, 5)[0]
    assert lab["label"] == -1 and lab["touched_barrier"] == "stop_loss"


def test_triple_barrier_vertical():
    close = np.array([100, 100.2, 99.9, 100.1, 100.05, 100.2], dtype=float)
    vol = np.full(6, 0.05)  # wide barriers → neither touched
    lab = triple_barrier_labels(close, [0], vol, 1.5, 1.0, 5)[0]
    assert lab["touched_barrier"] == "vertical"


def test_triple_barrier_vertical_zero_label_on_flat_path():
    close = np.array([100, 100, 100, 100, 100, 100], dtype=float)
    vol = np.full(6, 0.05)
    lab = triple_barrier_labels(close, [0], vol, 1.5, 1.0, 5)[0]
    assert lab["touched_barrier"] == "vertical"
    assert lab["label"] == 0
    assert lab["realized_return"] == pytest.approx(0.0)


def test_label_end_after_start_and_holding_positive():
    p = generate_synthetic_path(400, 100, 0.0002, 0.02, 5, 20)
    events = cusum_events(p["returns"], 0.02)
    labels = triple_barrier_labels(p["close"], [e["index"] for e in events], p["rolling_vol"], 1.5, 1.0, 10)
    assert labels
    for l in labels:
        assert l["end_index"] >= l["start_index"]
        assert l["holding_period_days"] >= 1


# ---------------------------------------------------------------------------
# Concurrency / uniqueness (11, 12, 13, 14, 15)
# ---------------------------------------------------------------------------


def test_concurrency_one_for_non_overlapping():
    conc = compute_concurrency(10, [(0, 2), (5, 7)])
    assert conc[0] == 1 and conc[6] == 1
    assert conc[3] == 0 and conc[4] == 0


def test_concurrency_above_one_for_overlapping():
    conc = compute_concurrency(10, [(0, 4), (2, 6)])
    assert conc[3] == 2  # both active at bar 3


def test_uniqueness_one_for_non_overlapping():
    intervals = [(0, 2), (5, 7)]
    conc = compute_concurrency(10, intervals)
    u = average_uniqueness(intervals, conc)
    assert u == [1.0, 1.0]


def test_uniqueness_below_one_for_overlapping():
    intervals = [(0, 4), (2, 6)]
    conc = compute_concurrency(10, intervals)
    u = average_uniqueness(intervals, conc)
    assert all(x < 1.0 for x in u)


def test_sample_weights_finite_mean_one():
    intervals = [(0, 4), (2, 6), (8, 9)]
    conc = compute_concurrency(12, intervals)
    u = average_uniqueness(intervals, conc)
    w = sample_weights(u)
    assert all(math.isfinite(x) for x in w)
    assert float(np.mean(w)) == pytest.approx(1.0, abs=1e-9)


def test_concurrency_clamps_out_of_range_intervals():
    conc = compute_concurrency(5, [(-2, 1), (3, 9), (6, 8)])
    assert conc.tolist() == [1.0, 1.0, 0.0, 1.0, 1.0]


# ---------------------------------------------------------------------------
# Orchestrator (16, 19) + reactivity
# ---------------------------------------------------------------------------


def test_label_distribution_sums_to_n_events():
    res = run_labeling_demo()
    s = res["summary"]
    assert s["positive_labels"] + s["negative_labels"] + s["zero_labels"] == s["n_events"]
    assert len(res["labels"]) == s["n_events"]
    assert len(res["events"]) == s["n_events"]


def test_higher_threshold_reduces_events():
    low = run_labeling_demo(cusum_threshold=0.02)
    high = run_labeling_demo(cusum_threshold=0.08)
    assert high["summary"]["n_events"] <= low["summary"]["n_events"]


def test_vol_scaled_demo_threshold_interpreted_as_multiplier():
    res = run_labeling_demo(threshold_mode="vol_scaled", cusum_threshold=2.0)
    assert any("multiplier" in w for w in res["warnings"])


def test_shortened_vertical_barrier_warning():
    res = run_labeling_demo(n_days=60, volatility=0.03, cusum_threshold=0.005, vertical_barrier_days=59)
    assert any("shortened vertical barrier" in w for w in res["warnings"])


def test_no_nan_in_response():
    _assert_all_finite(run_labeling_demo())
    _assert_all_finite(run_labeling_demo(cusum_threshold=0.05, vertical_barrier_days=20))


def test_deterministic_run():
    assert run_labeling_demo() == run_labeling_demo()


# ---------------------------------------------------------------------------
# Validation (17, 18)
# ---------------------------------------------------------------------------


def test_invalid_threshold_rejected():
    with pytest.raises(FinmlInputError):
        run_labeling_demo(cusum_threshold=-1)


def test_invalid_vertical_barrier_rejected():
    with pytest.raises(FinmlInputError):
        run_labeling_demo(vertical_barrier_days=0)
    with pytest.raises(FinmlInputError):
        run_labeling_demo(n_days=100, vertical_barrier_days=100)


def test_invalid_n_days_rejected():
    with pytest.raises(FinmlInputError):
        run_labeling_demo(n_days=10)


def test_invalid_volatility_window_rejected():
    with pytest.raises(FinmlInputError):
        run_labeling_demo(volatility_window=1)


# ---------------------------------------------------------------------------
# API wiring
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(main_module.app)


def test_api_labeling_demo(client):
    body = client.post(
        "/finml/labeling-demo",
        json={"n_days": 500, "start_price": 100, "drift": 0.0002, "volatility": 0.015,
              "seed": 42, "cusum_threshold": 0.02, "volatility_window": 20,
              "profit_take_multiple": 1.5, "stop_loss_multiple": 1.0, "vertical_barrier_days": 10},
    ).json()
    assert body["summary"]["n_events"] >= 0
    assert body["price_series"] and body["labels"]
    assert len(body["events"]) == body["summary"]["n_events"]


@pytest.mark.parametrize(
    "payload",
    [
        {"cusum_threshold": -1},
        {"vertical_barrier_days": 0},
        {"n_days": 10},
        {"volatility_window": 1},
        {"volatility": 0},
        {"profit_take_multiple": 0},
    ],
)
def test_api_labeling_validation_422(client, payload):
    base = {"n_days": 300, "start_price": 100, "drift": 0.0002, "volatility": 0.015,
            "cusum_threshold": 0.02, "volatility_window": 20, "profit_take_multiple": 1.5,
            "stop_loss_multiple": 1.0, "vertical_barrier_days": 10}
    base.update(payload)
    assert client.post("/finml/labeling-demo", json=base).status_code == 422
