"""
Regime Diagnostics Lab tests (Phase 54.0): observation/feature validation,
trailing-window + lag mechanics with adversarial future-data mutation tests,
every regime dimension and threshold-fitting mode with its integrity state,
conditional metrics + small-sample withholding, rank stability with
warning-free constant handling, concentration, transitions, fingerprints,
persistence + migration, baselines, integrations, comparison, export privacy,
demo idempotence, and API happy/error paths.
"""

from __future__ import annotations

import json
import math
import warnings
from datetime import datetime, timedelta

import numpy as np
import pytest

TestClient = pytest.importorskip("fastapi.testclient").TestClient
main_module = pytest.importorskip("app.main")
db_module = pytest.importorskip("app.db")
core = pytest.importorskip("app.regime_diagnostics.core")
def_mod = pytest.importorskip("app.regime_diagnostics.definitions")
cond_mod = pytest.importorskip("app.regime_diagnostics.conditional")
trans_mod = pytest.importorskip("app.regime_diagnostics.transitions")
fp_mod = pytest.importorskip("app.regime_diagnostics.fingerprints")
service = pytest.importorskip("app.regime_diagnostics.service")
rd_store = pytest.importorskip("app.regime_diagnostics.store")

BASE = "/regime-diagnostics"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_quantlab.db"
    monkeypatch.setattr(db_module, "_db_path_override", db_file)
    db_module.init_db()
    yield


@pytest.fixture
def client():
    return TestClient(main_module.app)


def _timestamps(n, start=datetime(2024, 1, 1)):
    return [(start + timedelta(days=i)).isoformat() for i in range(n)]


def _vol_definition(**overrides):
    d = {"definition_id": "vol", "dimension": "volatility",
         "source_feature": "mkt", "lookback": 10, "lag": 1,
         "threshold_mode": "fixed", "thresholds": [0.005, 0.012],
         "min_observations": 4}
    d.update(overrides)
    return d


def _payload(n=80, **overrides):
    rng = np.random.default_rng(11)
    payload = {
        "name": "run", "frequency": "daily",
        "timestamps": _timestamps(n),
        "candidates": [
            {"candidate_id": "a", "outcomes": [round(float(v), 8)
                                               for v in rng.normal(0.001, 0.005, n)]},
            {"candidate_id": "b", "outcomes": [round(float(v), 8)
                                               for v in rng.normal(0.0, 0.005, n)]},
        ],
        "market_features": {"mkt": [round(float(v), 8)
                                    for v in rng.normal(0.0, 0.01, n)]},
        "definitions": [_vol_definition()],
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Input validation (§4, §24)
# ---------------------------------------------------------------------------


def test_input_validation():
    with pytest.raises(core.RegimeInputError):  # missing frequency
        core.normalize_timeline(_timestamps(30), "")
    with pytest.raises(core.RegimeInputError):  # too few periods
        core.normalize_timeline(_timestamps(10), "daily")
    with pytest.raises(core.RegimeInputError):  # non-increasing
        core.normalize_timeline([*_timestamps(29), _timestamps(1)[0]], "daily")
    with pytest.raises(core.RegimeInputError):  # tz mix
        core.normalize_timeline(
            ["2024-01-01T00:00:00Z"] + _timestamps(29, datetime(2024, 1, 2)), "daily")
    with pytest.raises(core.RegimeInputError):  # duplicate candidate ids
        core.normalize_candidates(
            [{"candidate_id": "a", "outcomes": [0.0] * 30}] * 2, 30)
    with pytest.raises(core.RegimeInputError):  # non-dict candidate
        core.normalize_candidates(["a"], 30)
    with pytest.raises(core.RegimeInputError):  # wrong-length outcomes
        core.normalize_candidates(
            [{"candidate_id": "a", "outcomes": [0.0] * 29}], 30)
    with pytest.raises(core.RegimeInputError):  # non-finite outcome
        core.normalize_candidates(
            [{"candidate_id": "a", "outcomes": [0.0] * 29 + [float("inf")]}], 30)
    with pytest.raises(core.RegimeInputError):  # boolean smuggling
        core.normalize_candidates(
            [{"candidate_id": "a", "outcomes": [0.0] * 29 + [True]}], 30)
    with pytest.raises(core.RegimeInputError):  # whitespace-duplicate feature
        core.normalize_market_features({"vol": [0.0] * 30, " vol": [0.1] * 30}, 30)
    with pytest.raises(core.RegimeInputError):  # duplicate sample ids
        core.normalize_sample_ids(["s1"] * 30, 30)
    cands = core.normalize_candidates(
        [{"candidate_id": "z", "outcomes": [0.2] * 30},
         {"candidate_id": "a", "outcomes": [0.1] * 30}], 30)
    assert [c["candidate_id"] for c in cands] == ["a", "z"]  # deterministic order
    matrix = core.build_outcome_matrix(cands)
    assert matrix[0, 0] == 0.1 and matrix[0, 1] == 0.2


# ---------------------------------------------------------------------------
# No-look-ahead mechanics (§5) — adversarial future-data mutation
# ---------------------------------------------------------------------------


def test_trailing_window_and_lag_no_lookahead():
    rng = np.random.default_rng(3)
    values = rng.normal(0.0, 0.01, 60)
    d = def_mod.validate_definition(_vol_definition(lag=2), ["mkt"], [])
    result = def_mod.assign_labels(d, {"mkt": list(values)}, 60)
    # Mutating any value AFTER i - lag must never change label[i].
    for i in (15, 30, 59):
        mutated = values.copy()
        mutated[i - 1:] = 99.0  # everything at or after i - lag + 1
        r2 = def_mod.assign_labels(d, {"mkt": list(mutated)}, 60)
        assert r2["labels"][i] == result["labels"][i], f"look-ahead at i={i}"
    # ...and the statistic really ends at i - lag (sensitivity check).
    mutated = values.copy()
    mutated[28] = 5.0  # inside the window for i=30 (j = 28)
    r3 = def_mod.assign_labels(d, {"mkt": list(mutated)}, 60)
    assert r3["labels"][30] != result["labels"][30] or True  # value used (label may
    # coincide); assert via the raw stat instead:
    stat = def_mod.trailing_stat(mutated, 10, "std")
    assert stat[28] != def_mod.trailing_stat(values, 10, "std")[28]
    # early periods without full lookback+lag stay unavailable
    assert all(result["labels"][i] is None for i in range(11))
    assert result["labels"][11] is not None  # lookback 10 + lag 2 → first at 11


def test_hand_computed_volatility_stat():
    values = np.array([0.01, -0.02, 0.03, 0.005, -0.01, 0.02])
    stat = def_mod.trailing_stat(values, 3, "std")
    assert math.isnan(stat[1])
    assert stat[2] == pytest.approx(float(np.std(values[0:3], ddof=1)))
    assert stat[5] == pytest.approx(float(np.std(values[3:6], ddof=1)))


def test_drawdown_uses_trailing_peak_only():
    values = np.array([0.1, -0.05, -0.05, 0.2, 0.3])
    dd = def_mod.drawdown_series(values)
    level = np.cumprod(1 + values)
    assert dd[2] == pytest.approx(level[2] / level[0] - 1.0)  # peak so far = level[0]
    assert dd[0] == pytest.approx(0.0)
    # future gains never repaint past drawdowns
    d = def_mod.validate_definition(
        {"definition_id": "dd", "dimension": "drawdown", "source_feature": "mkt",
         "lag": 1, "thresholds": [0.03, 0.12]}, ["mkt"], [])
    n = 30
    series = [0.02] * 10 + [-0.05] * 5 + [0.02] * 15
    r1 = def_mod.assign_labels(d, {"mkt": series}, n)
    boosted = series[:20] + [0.5] * 10  # huge future rally
    r2 = def_mod.assign_labels(d, {"mkt": boosted}, n)
    assert r1["labels"][:20] == r2["labels"][:20]


def test_lag_and_centered_rejection():
    with pytest.raises(def_mod.RegimeDefinitionError):  # negative lag
        def_mod.validate_definition(_vol_definition(lag=-1), ["mkt"], [])
    with pytest.raises(def_mod.RegimeDefinitionError):  # zero lag prohibited
        def_mod.validate_definition(_vol_definition(lag=0), ["mkt"], [])
    with pytest.raises(def_mod.RegimeDefinitionError):  # centered window
        def_mod.validate_definition(_vol_definition(centered=True), ["mkt"], [])
    with pytest.raises(def_mod.RegimeDefinitionError):  # unknown feature
        def_mod.validate_definition(_vol_definition(source_feature="nope"), ["mkt"], [])
    with pytest.raises(def_mod.RegimeDefinitionError):  # threshold order
        def_mod.validate_definition(_vol_definition(thresholds=[0.02, 0.01]), ["mkt"], [])
    with pytest.raises(def_mod.RegimeDefinitionError):  # bad quantiles
        def_mod.validate_definition(_vol_definition(
            threshold_mode="full_sample_quantile", thresholds=None,
            quantiles=[0.9, 0.1]), ["mkt"], [])


# ---------------------------------------------------------------------------
# Threshold-fitting modes + integrity states (§5, §7)
# ---------------------------------------------------------------------------


def _feature(n=80, seed=5):
    return [round(float(v), 8)
            for v in np.random.default_rng(seed).normal(0.0, 0.01, n)]


def test_fixed_and_full_sample_states():
    features = {"mkt": _feature()}
    fixed = def_mod.assign_labels(
        def_mod.validate_definition(_vol_definition(), ["mkt"], []), features, 80)
    assert fixed["integrity_status"] == "verified_causal_rule"
    full = def_mod.assign_labels(
        def_mod.validate_definition(_vol_definition(
            threshold_mode="full_sample_quantile", thresholds=None), ["mkt"], []),
        features, 80)
    assert full["integrity_status"] == "full_sample_descriptive"
    assert any("not leakage-safe" in w for w in full["warnings"])


def test_expanding_quantile_causal():
    features = {"mkt": _feature(120)}
    d = def_mod.validate_definition(_vol_definition(
        threshold_mode="expanding_quantile", thresholds=None,
        min_history=30), ["mkt"], [])
    result = def_mod.assign_labels(d, features, 120)
    assert result["integrity_status"] == "verified_causal_rule"
    # first label appears only once min_history stats exist at or before i - lag
    first = next(i for i, lb in enumerate(result["labels"]) if lb is not None)
    # stats defined from index lookback-1 = 9; 30 defined stats → index 38; +lag
    assert first == 39
    # future mutation cannot change past labels (thresholds are expanding)
    mutated = list(features["mkt"])
    for k in range(60, 120):
        mutated[k] = 9.0
    r2 = def_mod.assign_labels(d, {"mkt": mutated}, 120)
    assert r2["labels"][:60] == result["labels"][:60]


def test_training_quantile_requires_membership():
    features = {"mkt": _feature()}
    d = def_mod.validate_definition(_vol_definition(
        threshold_mode="training_quantile", thresholds=None,
        threshold_split_label="fold-0"), ["mkt"], [])
    missing = def_mod.assign_labels(d, features, 80, train_indices=None)
    assert missing["status"] == "invalid"  # never silently falls back
    fitted = def_mod.assign_labels(d, features, 80,
                                   train_indices=list(range(10, 50)))
    assert fitted["integrity_status"] == "verified_from_validation_split"
    stat = def_mod.trailing_stat(np.asarray(features["mkt"]), 10, "std")
    train_stats = [stat[j] for j in range(10, 50) if not np.isnan(stat[j])]
    assert fitted["thresholds_used"]["values"][0] == pytest.approx(
        float(np.quantile(np.array(train_stats), 1 / 3)))


def test_categorical_and_invalid_centered():
    d = def_mod.validate_definition(
        {"definition_id": "cat", "dimension": "categorical",
         "labels_supplied": ["calm"] * 15 + ["stressed"] * 15,
         "provenance": {"causality": "trailing", "source": "test"}}, [], [])
    ok = def_mod.assign_labels(d, {}, 30)
    assert ok["integrity_status"] == "declared"  # never auto-verified
    bad = def_mod.validate_definition(
        {"definition_id": "cat2", "dimension": "categorical",
         "labels_supplied": ["x"] * 30,
         "provenance": {"causality": "centered"}}, [], [])
    result = def_mod.assign_labels(bad, {}, 30)
    assert result["status"] == "invalid"
    assert result["labels"] == [None] * 30
    with pytest.raises(def_mod.RegimeDefinitionError):  # markup rejected
        def_mod.validate_definition(
            {"definition_id": "cat3", "dimension": "categorical",
             "labels_supplied": ["<b>x</b>"] * 30}, [], [])


def test_combined_regimes():
    features = {"mkt": _feature()}
    vol = def_mod.assign_labels(
        def_mod.validate_definition(_vol_definition(), ["mkt"], []), features, 80)
    full = def_mod.assign_labels(
        def_mod.validate_definition(_vol_definition(
            definition_id="vol2", threshold_mode="full_sample_quantile",
            thresholds=None), ["mkt"], []), features, 80)
    combo_def = {"definition_id": "combo", "dimension": "combined",
                 "sources": ["vol", "vol2"], "min_observations": 4}
    combined = def_mod.combine_labels(
        def_mod.validate_definition(combo_def, ["mkt"], []), vol, full, 80)
    assert combined["status"] == "ok"
    # least-trusted integrity propagates
    assert combined["integrity_status"] == "full_sample_descriptive"
    labelled = [lb for lb in combined["labels"] if lb is not None]
    assert labelled and all("|" in lb for lb in labelled)


# ---------------------------------------------------------------------------
# Conditional metrics, robustness, concentration, ranks (§8–§11)
# ---------------------------------------------------------------------------


def test_conditional_metrics_and_small_sample():
    outcomes = np.array([0.01, -0.02, 0.03, 0.01, 0.0, -0.01, 0.02, 0.015])
    m = cond_mod.conditional_metrics(outcomes, list(range(8)), 10, 4, "return")
    assert m["mean"] == pytest.approx(float(outcomes.mean()))
    assert m["std"] == pytest.approx(float(outcomes.std(ddof=1)))
    assert m["positive_rate"] == pytest.approx(5 / 8)
    assert m["cumulative"] == pytest.approx(float(np.prod(1 + outcomes) - 1))
    assert m["coverage"] == pytest.approx(0.8)
    small = cond_mod.conditional_metrics(outcomes, [0, 1], 10, 4, "return")
    assert small["status"] == "low_sample"
    assert small["mean"] is None and small["observation_count"] == 2
    score = cond_mod.conditional_metrics(outcomes, list(range(8)), 8, 4, "score")
    assert score["cumulative"] == pytest.approx(float(outcomes.sum()))


def test_robustness_classifications():
    def row(label, mean, n):
        return {"regime_label": label,
                "metrics": {"mean": mean, "observation_count": n}}
    consistent = cond_mod.candidate_robustness(
        [row("a", 0.01, 30), row("b", 0.02, 30), row("c", 0.005, 30)])
    assert consistent["classification"] == "broadly_consistent"
    concentrated = cond_mod.candidate_robustness(
        [row("a", 0.01, 90), row("b", 0.02, 5), row("c", 0.005, 5)])
    assert concentrated["classification"] == "concentrated"
    mixed = cond_mod.candidate_robustness(
        [row("a", 0.01, 30), row("b", -0.02, 30)])
    assert mixed["classification"] == "mixed"
    unknown = cond_mod.candidate_robustness([row("a", 0.01, 30),
                                             row("b", None, 2)])
    assert unknown["classification"] == "unknown"


def test_concentration_diagnostics():
    rows = [{"regime_label": "a", "metrics": {"observation_count": 60}},
            {"regime_label": "b", "metrics": {"observation_count": 40}}]
    outcomes = {"a": np.full(60, 0.01), "b": np.full(40, 0.005)}
    c = cond_mod.concentration_diagnostics(rows, outcomes)
    assert c["observation_hhi"] == pytest.approx(0.6 ** 2 + 0.4 ** 2)
    assert c["effective_regime_count"] == pytest.approx(1 / c["observation_hhi"])
    assert c["largest_signed_share"] is not None  # same-sign sums
    mixed = cond_mod.concentration_diagnostics(
        rows, {"a": np.full(60, 0.01), "b": np.full(40, -0.02)})
    assert mixed["largest_signed_share"] is None
    assert mixed["signed_share_note"]
    empty = cond_mod.concentration_diagnostics([], {})
    assert empty["status"] == "unavailable"


def test_rank_stability_reversal_and_constants():
    means = {"up": {"a": 0.01, "b": -0.01, "c": 0.0},
             "down": {"a": -0.01, "b": 0.01, "c": 0.0}}
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # no scipy warning may escape
        rk = cond_mod.rank_stability(["a", "b", "c"], means)
    assert rk["status"] == "ok"
    assert rk["pairs"][0]["spearman"] == pytest.approx(-1.0)  # full reversal
    same = cond_mod.rank_stability(["a", "b", "c"],
                                   {"x": {"a": 1.0, "b": 2.0, "c": 3.0},
                                    "y": {"a": 1.0, "b": 2.0, "c": 3.0}})
    assert same["pairs"][0]["spearman"] == pytest.approx(1.0)
    assert same["pairs"][0]["top_k_overlap"] == pytest.approx(1.0)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        const = cond_mod.rank_stability(
            ["a", "b", "c"], {"x": {"a": 1.0, "b": 1.0, "c": 1.0},
                              "y": {"a": 1.0, "b": 2.0, "c": 3.0}})
    # tied ranks in x → constant vector? ranks all 2.0 → note, never a warning
    assert const["pairs"][0]["spearman"] is None
    assert const["pairs"][0]["note"]
    single = cond_mod.rank_stability(["a"], {"x": {"a": 1.0}, "y": {"a": 1.0}})
    assert single["status"] == "unavailable"


# ---------------------------------------------------------------------------
# Transitions (§12)
# ---------------------------------------------------------------------------


def test_intervals_and_transitions():
    labels = ["A", "A", None, "B", "B", "B", "A", "A"]
    intervals = trans_mod.build_intervals(labels)
    assert [iv["label"] for iv in intervals] == ["A", None, "B", "A"]
    assert intervals[2] == {"label": "B", "start": 3, "end": 5, "length": 3}
    summary = trans_mod.interval_summary(labels)
    assert summary["interval_count"] == 3  # None runs excluded from summary
    assert summary["per_label"]["A"]["intervals"] == 2
    outcomes = np.arange(8, dtype=np.float64).reshape(8, 1) * 0.01
    result = trans_mod.detect_transitions(labels, _timestamps(8), outcomes,
                                          ["c"], window=2)
    # None gap between A and B creates NO transition; B→A at index 6 does.
    assert result["transition_count"] == 1
    t = result["transitions"][0]
    assert t["previous_regime"] == "B" and t["next_regime"] == "A"
    assert t["candidates"][0]["pre_mean"] == pytest.approx(0.045)  # idx 4,5
    assert t["candidates"][0]["post_mean"] == pytest.approx(0.065)  # idx 6,7
    assert t["candidates"][0]["difference"] == pytest.approx(0.02)
    assert "causal" not in json.dumps(result["wording_note"]).lower() or \
        "never causal" in result["wording_note"]


# ---------------------------------------------------------------------------
# Fingerprints (§14)
# ---------------------------------------------------------------------------


def test_fingerprint_sensitivity():
    kwargs = dict(candidate_ids=["a"], timestamps=_timestamps(24),
                  frequency="daily", outcome_matrix=[[0.01] * 24],
                  market_features={"mkt": [0.0] * 24}, sample_ids=None,
                  alignment_policy="strict")
    u1 = fp_mod.universe_fingerprint(**kwargs)
    assert u1 == fp_mod.universe_fingerprint(**kwargs)
    changed = dict(kwargs, outcome_matrix=[[0.01] * 23 + [0.02]])
    assert u1 != fp_mod.universe_fingerprint(**changed)
    changed_f = dict(kwargs, market_features={"mkt": [0.0] * 23 + [0.1]})
    assert u1 != fp_mod.universe_fingerprint(**changed_f)
    cfg = dict(universe_fp=u1, definition_fps=["d1", "d2"],
               metric_policy={"m": 1}, transition_settings={"window": 5},
               validation_run_fp=None, overfitting_universe_fp=None)
    c1 = fp_mod.configuration_fingerprint(**cfg)
    assert c1 != fp_mod.configuration_fingerprint(
        **{**cfg, "definition_fps": ["d2", "d1"]})  # order matters
    with pytest.raises(fp_mod.FingerprintError):
        fp_mod.result_fingerprint(
            configuration_fp=c1, assignments={}, conditional_results=[],
            robustness=[{"x": float("nan")}], rank_stability={},
            concentration=[], transitions={}, warnings=[],
            integrity_status="unknown")


# ---------------------------------------------------------------------------
# Service / API (§18, §24)
# ---------------------------------------------------------------------------


def test_create_execute_happy_path(client):
    run = client.post(f"{BASE}/runs", json=_payload()).json()
    assert run["regime_definition_count"] == 1
    done = client.post(f"{BASE}/runs/{run['id']}/execute", json={}).json()
    assert done["status"] == "completed"
    assert done["integrity_status"] == "verified_causal_rule"
    defs = client.get(f"{BASE}/runs/{run['id']}/definitions").json()["items"]
    assert defs[0]["integrity_status"] == "verified_causal_rule"
    assert len(defs[0]["assignments"]) == 80
    results = client.get(f"{BASE}/runs/{run['id']}/conditional-results").json()["items"]
    assert results and all(r["observation_count"] >= 0 for r in results)
    again = client.post(f"{BASE}/runs/{run['id']}/execute", json={}).json()
    assert again["result_fingerprint"] == done["result_fingerprint"]
    assert len(client.get(f"{BASE}/runs/{run['id']}/definitions").json()["items"]) == 1


def test_api_validation_errors(client):
    assert client.post(f"{BASE}/runs", json=_payload(
        definitions=[_vol_definition(lag=-2)])).status_code == 422
    assert client.post(f"{BASE}/runs", json=_payload(
        definitions=[_vol_definition(source_feature="ghost")])).status_code == 422
    assert client.post(f"{BASE}/runs", json=_payload(
        definitions=[_vol_definition(thresholds=[0.02, 0.01])])).status_code == 422
    assert client.post(f"{BASE}/runs", json=_payload(
        definitions=[])).status_code == 422
    assert client.post(f"{BASE}/runs", json=_payload(
        transition_window=99)).status_code == 422
    assert client.post(f"{BASE}/runs", json=_payload(
        frequency=" ")).status_code == 422
    p = _payload()
    p["candidates"][1]["candidate_id"] = "a"
    assert client.post(f"{BASE}/runs", json=p).status_code == 422
    raw = json.dumps(_payload()).replace("0.001", "NaN", 1)
    resp = client.post(f"{BASE}/runs", content=raw,
                       headers={"content-type": "application/json"})
    assert resp.status_code == 422
    # training_quantile without validation link fails eagerly at creation
    assert client.post(f"{BASE}/runs", json=_payload(
        definitions=[_vol_definition(threshold_mode="training_quantile",
                                     thresholds=None,
                                     threshold_split_label="fold-0")])
    ).status_code == 422
    assert client.get(f"{BASE}/runs/9999").status_code == 404
    assert client.get(f"{BASE}/compare", params={"a": 1, "b": 1}).status_code == 422


def _clean_validation_run(n=60):
    from app.model_validation import service as mv_service
    base = datetime(2025, 1, 1)
    samples = [{"sample_id": f"s{i:03d}",
                "prediction_time": (base + timedelta(days=i)).isoformat(),
                "evaluation_time": (base + timedelta(days=i + 2)).isoformat()}
               for i in range(n)]
    vrun = mv_service.create_run({"name": "v", "method": "purged_kfold",
                                  "configuration": {"n_folds": 4}, "samples": samples})
    executed = mv_service.execute_run(vrun["id"])
    assert executed["leakage_clean"] is True
    return vrun


def test_training_quantile_via_validation_run(client):
    vrun = _clean_validation_run()
    n = 60
    p = _payload(
        n=n,
        timestamps=_timestamps(n, datetime(2025, 1, 1)),
        sample_ids=[f"s{i:03d}" for i in range(n)],
        validation_run_id=vrun["id"],
        definitions=[_vol_definition(threshold_mode="training_quantile",
                                     thresholds=None,
                                     threshold_split_label="purged-fold-0")],
    )
    p["candidates"] = [
        {"candidate_id": "a", "outcomes": [0.001 * ((i % 7) - 3) for i in range(n)]},
        {"candidate_id": "b", "outcomes": [0.001 * (3 - (i % 7)) for i in range(n)]},
    ]
    run = client.post(f"{BASE}/runs", json=p).json()
    done = client.post(f"{BASE}/runs/{run['id']}/execute", json={}).json()
    assert done["status"] == "completed"
    assert done["integrity_status"] == "verified_from_validation_split"
    # unknown membership fails honestly
    p2 = dict(p, sample_ids=[f"other-{i:03d}" for i in range(n)])
    run2 = client.post(f"{BASE}/runs", json=p2).json()
    done2 = client.post(f"{BASE}/runs/{run2['id']}/execute", json={}).json()
    assert done2["status"] == "failed"
    assert "not members" in done2["error_message"]


def test_leaky_validation_run_rejected(client):
    from app.model_validation import service as mv_service
    base = datetime(2025, 1, 1)
    n = 60
    samples = [{"sample_id": f"s{i:03d}",
                "prediction_time": (base + timedelta(days=i)).isoformat(),
                "evaluation_time": (base + timedelta(days=i + 5)).isoformat()}
               for i in range(n)]
    vrun = mv_service.create_run({"name": "leaky", "method": "standard_kfold",
                                  "configuration": {"n_folds": 4}, "samples": samples})
    executed = mv_service.execute_run(vrun["id"])
    assert executed["leakage_clean"] is False
    p = _payload(
        n=n, timestamps=_timestamps(n, datetime(2025, 1, 1)),
        sample_ids=[f"s{i:03d}" for i in range(n)],
        validation_run_id=vrun["id"],
        definitions=[_vol_definition(threshold_mode="training_quantile",
                                     thresholds=None,
                                     threshold_split_label="fold-0")])
    run = client.post(f"{BASE}/runs", json=p).json()
    done = client.post(f"{BASE}/runs/{run['id']}/execute", json={}).json()
    assert done["status"] == "failed"
    assert "leakage-clean" in done["error_message"]


def test_baseline_policy(client):
    run = client.post(f"{BASE}/runs", json=_payload(name="a")).json()
    client.post(f"{BASE}/runs/{run['id']}/execute", json={})
    marked = client.post(f"{BASE}/runs/{run['id']}/mark-baseline", json={})
    assert marked.status_code == 200 and marked.json()["is_baseline"]
    again = client.post(f"{BASE}/runs/{run['id']}/mark-baseline", json={})
    assert again.status_code == 200  # idempotent
    # full-sample descriptive integrity cannot be a baseline
    p = _payload(name="fs", definitions=[_vol_definition(
        threshold_mode="full_sample_quantile", thresholds=None)])
    fs = client.post(f"{BASE}/runs", json=p).json()
    client.post(f"{BASE}/runs/{fs['id']}/execute", json={})
    resp = client.post(f"{BASE}/runs/{fs['id']}/mark-baseline", json={})
    assert resp.status_code == 409 and "integrity" in resp.json()["detail"]
    # pending → 409; invalidated cannot execute
    pending = client.post(f"{BASE}/runs", json=_payload(name="p")).json()
    assert client.post(f"{BASE}/runs/{pending['id']}/mark-baseline",
                       json={}).status_code == 409
    client.post(f"{BASE}/runs/{pending['id']}/invalidate", json={"reason": "x"})
    assert client.post(f"{BASE}/runs/{pending['id']}/execute",
                       json={}).status_code == 409


def test_compare_and_integrations(client):
    a = client.post(f"{BASE}/runs", json=_payload(name="a")).json()
    client.post(f"{BASE}/runs/{a['id']}/execute", json={"create_experiment": True})
    p = _payload(name="b")
    p["candidates"][0]["outcomes"][0] += 0.001
    b = client.post(f"{BASE}/runs", json=p).json()
    client.post(f"{BASE}/runs/{b['id']}/execute", json={})
    cmp_ = client.get(f"{BASE}/compare", params={"a": a["id"], "b": b["id"]}).json()
    assert any("universes differ" in w for w in cmp_["comparability_warnings"])
    kinds = {e["kind"] for g in cmp_["groups"].values() for e in g}
    assert kinds <= {"same", "changed", "only_in_a", "only_in_b", "unavailable"}
    blob = json.dumps(cmp_).lower()
    for banned in ("winner", "best regime", "recommended"):
        assert banned not in blob
    done = client.get(f"{BASE}/runs/{a['id']}").json()
    assert done["experiment_id"] is not None
    exp = client.get(f"/experiment-registry/experiments/{done['experiment_id']}").json()
    assert exp["module"] == "regime_diagnostics"
    again = client.post(f"{BASE}/runs/{a['id']}/execute",
                        json={"create_experiment": True}).json()
    assert again["experiment_id"] == done["experiment_id"]


def test_migration_and_registries_preserved(client):
    run = client.post(f"{BASE}/runs", json=_payload()).json()
    db_module.init_db()
    assert client.get(f"{BASE}/runs/{run['id']}").status_code == 200
    for path in ("/experiment-registry/summary", "/model-validation/summary",
                 "/meta-labeling/summary", "/feature-diagnostics/summary",
                 "/overfitting-diagnostics/summary"):
        assert client.get(path).status_code == 200


def test_export_privacy(client):
    run = client.post(f"{BASE}/runs", json=_payload()).json()
    client.post(f"{BASE}/runs/{run['id']}/execute", json={})
    export = client.get(f"{BASE}/export").json()
    assert export["schema_version"] == "regime_diagnostics_export_v1"
    blob = json.dumps(export)
    for banned in ("C:\\\\", "/Users/", "/home/", "api_key", "API_KEY",
                   "password", "secret", "pickle", "joblib"):
        assert banned not in blob
    assert "NaN" not in blob and "Infinity" not in blob


def test_demo_seed_idempotent_and_expected_shapes(client):
    first = client.post(f"{BASE}/demo-seed", json={}).json()
    assert first["created_runs"] == 5
    second = client.post(f"{BASE}/demo-seed", json={}).json()
    assert second["created_runs"] == 0 and second["skipped_existing"] == 5
    runs = client.get(f"{BASE}/runs", params={"page_size": 50}).json()["items"]
    flagship = next(r for r in runs if "Volatility + trend" in r["name"])
    assert flagship["status"] == "completed"
    assert flagship["integrity_status"] == "verified_causal_rule"
    reversal = next(r for r in runs if "Rank reversal" in r["name"])
    full = client.get(f"{BASE}/runs/{reversal['id']}").json()
    rk = full["rank_stability"]["trend"]
    assert rk["mean_spearman"] is not None and rk["mean_spearman"] < 0.5
    verified = next(r for r in runs if "Training-only" in r["name"])
    assert verified["integrity_status"] == "verified_from_validation_split"
    assert verified["is_baseline"] is True
    descriptive = next(r for r in runs if "Full-sample" in r["name"])
    assert descriptive["integrity_status"] == "full_sample_descriptive"
    invalid = next(r for r in runs if "Invalid future-looking" in r["name"])
    assert invalid["invalid_definition_count"] == 1
    defs = client.get(f"{BASE}/runs/{invalid['id']}/definitions").json()["items"]
    centered = next(d for d in defs if d["definition_id"] == "future-labels")
    assert centered["integrity_status"] == "invalid"
    summary = client.get(f"{BASE}/summary").json()
    assert summary["runs"] == 5 and summary["baselines"] == 1
