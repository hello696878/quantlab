"""Independent timing, fit-boundary and material-child regressions for Phase 65."""

from datetime import datetime
import math
from types import SimpleNamespace

import numpy as np
import pytest

pytestmark = [pytest.mark.usefixtures("isolated_lab_db")]


@pytest.fixture(scope="module")
def prepared():
    from app.ml_lifecycle.demo import prepare_demo
    return prepare_demo()


@pytest.fixture(scope="module")
def snapshot(prepared):
    from app.ml_lifecycle.demo import fit_snapshot
    return fit_snapshot(prepared)


@pytest.mark.db_free
def test_tiny_prices_separate_label_interval_one_shift_and_both_cost_conventions(prepared):
    from app.cost_diagnostics.components import compute_commission
    from app.futures_backtest.futures_vectorized import run_futures_backtest
    from app.instruments import get_instrument
    from app.labels import build_label_matrix
    from app.labels.spec import DEFAULT_ES_LABELS
    from app.ml_lifecycle.adapters import payload
    from app.ml_lifecycle.demo import frame_table

    cont = prepared["cont"].iloc[:6].copy()
    prices = [100.0, 110.0, 99.0, 118.8, 118.8, 106.92]
    for column in ("open_raw", "high_raw", "low_raw", "close_raw",
                   "open_adjusted", "high_adjusted", "low_adjusted", "close_adjusted"):
        cont[column] = prices
    labels = build_label_matrix(cont, specs=[s for s in DEFAULT_ES_LABELS
                                            if s.name in ("forward_return_1", "direction_1")])
    # Direct price ratios: decision 0 labels 110 -> 99, while its target earns
    # 100 -> 110. No production return/position helper constructs these answers.
    np.testing.assert_allclose(labels.forward_return_1.iloc[:4], [-.1, .2, 0, -.1], atol=1e-14)
    assert labels.direction_1.iloc[:4].tolist() == [-1, 1, 0, -1]
    assert labels.forward_return_1.iloc[4:].isna().all()
    signals = cont[["timestamp", "root_symbol", "active_contract"]].copy()
    signals["target_position"] = [1, 0, 1, 1, 0, 1]
    result = run_futures_backtest(cont, signals, get_instrument("ES"), transaction_cost_bps=10)
    assert result.frame.effective_position.tolist() == [0, 1, 0, 1, 1, 0]
    gross = [0, .1, 0, .2, 0, 0]
    net = [0, .0989, -.001, .1988, 0, -.001]
    drag = [0, .0011, .001, .0012, 0, .001]
    np.testing.assert_allclose(result.frame.strategy_return, gross, atol=1e-14)
    np.testing.assert_allclose(result.frame.net_strategy_return, net, atol=1e-14)
    np.testing.assert_allclose(result.frame.transaction_cost, drag, atol=1e-14)
    assert result.frame.equity.iloc[-1] == pytest.approx(10000 * 1.0989 * .999 * 1.1988 * .999)
    record = {"dataset_version_id": 1, "snapshot": {
        "origin": "deterministic_demo", "samples": [], "predictions": [],
        "splits": [{"role": "final"}], "evaluation": {"periods": frame_table(result.frame)}}}
    costs = payload("costs", record, {})
    assert [o["turnover"] for o in costs["observations"]] == [0, 1, 1, 1, 0, 1]
    assert [o["traded_notional"] for o in costs["observations"]] == [0, 10000, 10000, 10000, 0, 10000]
    fees = [compute_commission(o, costs["commission"], "period")["amount"] for o in costs["observations"]]
    assert fees == pytest.approx([0, .001, .001, .001, 0, .001])
    np.testing.assert_allclose([o["gross_return"] for o in costs["observations"]], gross, atol=1e-14)
    np.testing.assert_allclose([o["metadata"]["actual_return_drag"] for o in costs["observations"]], drag, atol=1e-14)


@pytest.mark.db_free
def test_actual_estimator_inputs_and_calibrator_are_disjoint_from_outer_holdout(prepared, monkeypatch):
    from app.ml_lifecycle import demo
    from app.ml_signal.models import LogisticRegression

    fitted, calibration_calls, events = [], [], []
    original_fit, original_calibrate = LogisticRegression.fit, demo.fit_sigmoid

    def observe_fit(model, X, y, sample_weight=None):
        fitted.append((np.asarray(X).copy(), np.asarray(y).copy()))
        events.append("model")
        return original_fit(model, X, y, sample_weight=sample_weight)

    def observe_calibration(probs, y):
        calibration_calls.append((np.asarray(probs).copy(), np.asarray(y).copy()))
        events.append("calibration")
        return original_calibrate(probs, y)

    monkeypatch.setattr(LogisticRegression, "fit", observe_fit)
    monkeypatch.setattr(demo, "fit_sigmoid", observe_calibration)
    result = demo.fit_snapshot(prepared)
    assert events == ["model"] * 4 + ["calibration", "model"]
    by_id = {row["sample_id"]: row for row in result["samples"]}
    splits = {row["hash"]: row for row in result["splits"]}
    final = next(row for row in result["splits"] if row["role"] == "final")
    held = set(final["membership"]["test"])
    for artifact, (X, y) in zip(result["models"], fitted, strict=True):
        membership = splits[artifact["split_hash"]]["membership"]
        assert artifact["train_ids"] == membership["train"]
        assert not set(membership["train"]) & (held | set(membership["test"]))
        assert max(by_id[s]["evaluation_time"] for s in membership["train"]) < min(
            by_id[s]["prediction_time"] for s in membership["test"])
        assert artifact["feature_order"] == demo.FEATURES
        np.testing.assert_array_equal(X, [by_id[s]["features"] for s in membership["train"]])
        np.testing.assert_array_equal(y, [by_id[s]["label"] for s in membership["train"]])
        generated = [p["sample_id"] for p in result["predictions"] if p["model_hash"] == artifact["hash"]]
        assert generated == membership["test"]
    oof = [p for p in result["predictions"] if p["role"] == "inner_oof"]
    assert result["calibration"]["fit_ids"] == [p["sample_id"] for p in oof]
    assert not held & set(result["calibration"]["fit_ids"])
    assert len(result["calibration"]["fit_ids"]) == len(set(result["calibration"]["fit_ids"]))
    np.testing.assert_array_equal(calibration_calls[0][0], [p["raw_probability"] for p in oof])
    np.testing.assert_array_equal(calibration_calls[0][1], [int(by_id[p["sample_id"]]["label"] == 1) for p in oof])
    assert result["calibration"]["threshold"] == .5


@pytest.mark.db_free
def test_probability_meaning_feature_order_and_decay_tail_are_explicit(snapshot):
    from app.ml_lifecycle.adapters import payload
    from app.signal_decay.observations import build_pairs, validate_prices, validate_signal_observations

    record = {"dataset_version_id": 1, "snapshot": snapshot}
    samples = {row["sample_id"]: row for row in snapshot["samples"]}
    held = [p for p in snapshot["predictions"] if p["role"] == "held_out"]
    calibration = payload("calibration", record, {})
    assert calibration["calibration_method"] == "none"
    assert calibration["declared_out_of_fold"] is False
    assert calibration["outcome_threshold"] == 0
    params = snapshot["calibration"]["parameters"]
    for prediction, observation in zip(held, calibration["observations"], strict=True):
        p = min(1 - 1e-6, max(1e-6, prediction["raw_probability"]))
        z = params["a"] * math.log(p / (1 - p)) + params["b"]
        expected = min(1 - 1e-6, max(1e-6, 1 / (1 + math.exp(-z))))
        assert prediction["calibrated_probability"] == pytest.approx(expected)
        assert observation["raw_probability"] == prediction["calibrated_probability"]
        assert observation["primary_side"] == 1
        assert (observation["realized_outcome"] > 0) == (samples[prediction["sample_id"]]["label"] == 1)
    features = payload("features", record, {})
    assert [f["feature_name"] for f in features["features"]] == snapshot["feature_order"]
    for row in features["samples"]:
        sample = samples[row["sample_id"]]
        assert list(row["features"]) == snapshot["feature_order"]
        assert list(row["features"].values()) == sample["features"]
        assert row["target"] == int(sample["label"] == 1)
    decay = payload("decay", record, {"costs": {"status": "completed", "destination_id": 5}})
    observations = validate_signal_observations(decay["signal"], decay["observations"])
    pairs = build_pairs(observations, target_type="forward_return", prices=validate_prices(decay["prices"], "close"),
                        supplied=None, horizon=1, entry_lag=1, extreme_loss_policy="mark_unavailable")
    assert pairs["violations"] == []
    assert len(pairs["pairs"]) == 30  # Observation grid, even with 220 prices.
    assert len(pairs["unavailable"]) == 2
    assert [row["signal_timestamp"] for row in pairs["unavailable"]] == [
        row["source_timestamp"] for row in observations[-2:]]
    for pair, prediction in zip(pairs["pairs"], held[:30], strict=True):
        sample = samples[prediction["sample_id"]]
        assert datetime.fromisoformat(pair["signal_timestamp"]) == datetime.fromisoformat(sample["prediction_time"])
        assert datetime.fromisoformat(pair["exit_timestamp"]) == datetime.fromisoformat(sample["evaluation_time"])
        assert pair["outcome_value"] == pytest.approx(sample["outcome"])


@pytest.mark.db_free
def test_content_excludes_only_known_database_envelopes(monkeypatch):
    from app.ml_lifecycle import adapters

    raw = {"id": 1, "status": "completed", "started_at": "runtime-1", "dataset_version_id": 2,
           "samples": [{"sample_id": "s", "metadata": {"id": "event-1", "created_at": "event-time-1"}}]}
    split = {"id": 3, "validation_run_id": 1, "train_ids": ["s"], "metrics": {"id": "metric-1"}}
    service = SimpleNamespace(get_run=lambda _: {"status": "completed"}, list_splits=lambda _: [split])
    store = SimpleNamespace(get_run=lambda _: raw)
    monkeypatch.setitem(adapters.ADAPTERS, "validation", (service, store, None, "unused"))
    original = adapters.content("validation", 1)
    raw.update(id=20, started_at="runtime-2", dataset_version_id=30)
    split.update(id=40, validation_run_id=20)
    assert adapters.content("validation", 1) == original
    for key in ("id", "created_at"):
        old = raw["samples"][0]["metadata"][key]
        raw["samples"][0]["metadata"][key] = "changed-event"
        assert adapters.content("validation", 1) != original
        raw["samples"][0]["metadata"][key] = old
    split["metrics"]["id"] = "changed-metric"
    assert adapters.content("validation", 1) != original


@pytest.mark.db_free
def test_calibration_content_includes_observations_after_public_page_limit(monkeypatch):
    from app.ml_lifecycle import adapters

    rows = [{"sample_id": str(i), "raw_probability": .5} for i in range(201)]
    store = SimpleNamespace(get_run=lambda _: {"status": "completed"}, all_observations=lambda _: rows,
                            list_observations=lambda *a, **kw: {"items": rows[:200], "total": 201},
                            list_bins=lambda _: {})
    service = SimpleNamespace(get_run=store.get_run)
    monkeypatch.setitem(adapters.ADAPTERS, "calibration", (service, store, None, "unused"))
    before = adapters.content("calibration", 1)
    rows[-1]["raw_probability"] = .6
    assert adapters.content("calibration", 1) != before


@pytest.mark.db_free
def test_cost_content_reads_every_page_and_preserves_input_metadata(monkeypatch):
    from app.ml_lifecycle import adapters

    rows = [{"observation_id": str(i), "net_return": .01} for i in range(101)]
    raw = {"status": "completed", "observations": [{"gross_return": .02, "metadata": {"id": "source"}}]}
    calls = []

    def paged(_, *, page=1, page_size=25):
        calls.append(page)
        return {"items": rows[(page - 1) * page_size:page * page_size], "total": len(rows),
                "total_pages": math.ceil(len(rows) / page_size)}

    store = SimpleNamespace(get_run=lambda _: raw, list_observation_results=paged, get_cost_model=lambda _: {},
                            list_sensitivity_results=lambda _: [], list_capacity_results=lambda _: [])
    monkeypatch.setitem(adapters.ADAPTERS, "costs", (SimpleNamespace(get_run=store.get_run), store, None, "unused"))
    before = adapters.content("costs", 1)
    assert calls == [1, 2]
    rows[-1]["net_return"] = .03
    assert adapters.content("costs", 1) != before
    rows[-1]["net_return"] = .01
    raw["observations"][0]["metadata"]["id"] = "changed-source"
    assert adapters.content("costs", 1) != before


def test_real_feature_samples_and_last_cost_result_are_material():
    from app.ml_lifecycle import adapters, service, store

    run = service.demo()
    assert run["integrity"] == "intact"
    links = {link["adapter"]: link["destination_id"] for link in run["links"]}
    before = adapters.content("features", links["features"])
    with store.connection() as conn:
        row = conn.execute("SELECT id, target FROM feature_samples WHERE run_id=? ORDER BY id LIMIT 1",
                           (links["features"],)).fetchone()
        conn.execute("UPDATE feature_samples SET target=? WHERE id=?", (1 - row["target"], row["id"]))
    assert adapters.content("features", links["features"]) != before
    assert service.get_run(run["id"])["integrity"] == "changed"
    with pytest.raises(service.ConflictError):
        service.export(run["id"])
    with store.connection() as conn:
        conn.execute("UPDATE feature_samples SET target=? WHERE id=?", (row["target"], row["id"]))
    assert service.get_run(run["id"])["integrity"] == "intact"
    before = adapters.content("costs", links["costs"])
    with store.connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM cost_observation_results WHERE run_id=?",
                            (links["costs"],)).fetchone()[0] == 32
        conn.execute("UPDATE cost_observation_results SET net_return=net_return+0.1 WHERE id=("
                     "SELECT id FROM cost_observation_results WHERE run_id=? ORDER BY timestamp DESC LIMIT 1)",
                     (links["costs"],))
    assert adapters.content("costs", links["costs"]) != before
    assert service.get_run(run["id"])["integrity"] == "changed"


@pytest.mark.db_free
def test_decay_content_pins_price_inputs_event_times_and_preserves_legacy_hashes(monkeypatch):
    from app.ml_lifecycle import adapters

    raw = {"status": "completed", "started_at": "runtime-1", "configuration_fingerprint": "legacy-hash",
           "configuration": {"prices": [["ES", "2022-01-01", 100]],
                             "links": {"ids": {"cost_diagnostic_run_id": 1},
                                       "cost_identity": {"cost_diagnostic_run_id": 1, "model_fingerprint": "fee"}}}}
    observations = [{"observation_id": "event", "generated_at": "2022-01-01", "raw_value": .5}]
    definition = {"dataset_version_id": 1, "signal_id": "up", "metadata": {"id": "meaningful"}}
    store = SimpleNamespace(get_run=lambda _: raw, get_definition=lambda _: definition,
                            list_observations=lambda *a, **kw: observations, list_horizons=lambda _: [],
                            list_buckets=lambda _: [], list_turnover=lambda _: [], list_regimes=lambda _: [],
                            list_bootstrap=lambda _: [])
    monkeypatch.setitem(adapters.ADAPTERS, "decay", (SimpleNamespace(get_run=store.get_run), store, None, "unused"))
    before = adapters.content("decay", 1)
    raw["started_at"] = "runtime-2"
    raw["configuration"]["links"]["ids"]["cost_diagnostic_run_id"] = 2
    raw["configuration"]["links"]["cost_identity"]["cost_diagnostic_run_id"] = 2
    definition["dataset_version_id"] = 2
    assert adapters.content("decay", 1) == before
    for parent, key, value in ((observations[0], "generated_at", "2022-01-02"),
                               (definition["metadata"], "id", "changed"),
                               (raw, "configuration_fingerprint", "new-legacy-hash")):
        old = parent[key]
        parent[key] = value
        assert adapters.content("decay", 1) != before
        parent[key] = old
    raw["configuration"]["prices"][0][2] = 101
    assert adapters.content("decay", 1) != before
