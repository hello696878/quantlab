"""
Overfitting Diagnostics Lab tests (Phase 53.0): candidate input + strict
alignment, CSCV block construction + combinations + limits, the fixed rank/
lambda/PBO conventions with deterministic tie handling, invalid-split
exclusion, PSR/DSR/expected-max-Sharpe/MinTRL against hand-computed
references, Bonferroni/Holm/BH (including the classic BH example and ties),
p-value provenance, dependence diagnostics with warning-free constant
handling, fingerprints, persistence + migration, baselines, registry
integrations, comparison, export privacy, demo idempotence, and adversarial
API paths.
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
core = pytest.importorskip("app.overfitting_diagnostics.core")
metrics_mod = pytest.importorskip("app.overfitting_diagnostics.metrics")
cscv = pytest.importorskip("app.overfitting_diagnostics.cscv")
sharpe_mod = pytest.importorskip("app.overfitting_diagnostics.sharpe")
mt_mod = pytest.importorskip("app.overfitting_diagnostics.multiple_testing")
dep_mod = pytest.importorskip("app.overfitting_diagnostics.dependence")
fp_mod = pytest.importorskip("app.overfitting_diagnostics.fingerprints")
service = pytest.importorskip("app.overfitting_diagnostics.service")
od_store = pytest.importorskip("app.overfitting_diagnostics.store")
sp_stats = pytest.importorskip("scipy.stats")

BASE = "/overfitting-diagnostics"


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


def _cand(cid, returns, **extra):
    return {"candidate_id": cid, "returns": [float(v) for v in returns], **extra}


def _noise(n, seed, loc=0.0, scale=0.01):
    return np.random.default_rng(seed).normal(loc, scale, n)


def _payload(n=64, s=4, **overrides):
    payload = {
        "name": "run", "metric": "sharpe_like", "block_count": s,
        "timestamps": _timestamps(n),
        "candidates": [
            _cand("a", _noise(n, 1, loc=0.001)),
            _cand("b", _noise(n, 2)),
            _cand("c", _noise(n, 3)),
        ],
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Candidate input + alignment (§4, §30)
# ---------------------------------------------------------------------------


def test_candidate_input_validation():
    ts = core.normalize_timestamps(_timestamps(24))
    with pytest.raises(core.CandidateInputError):  # fewer than two candidates
        core.normalize_candidates([_cand("a", [0.0] * 24)], 24)
    with pytest.raises(core.CandidateInputError):  # duplicate ids
        core.normalize_candidates([_cand("a", [0.0] * 24)] * 2, 24)
    with pytest.raises(core.CandidateInputError):  # mismatched observation count
        core.normalize_candidates(
            [_cand("a", [0.0] * 24), _cand("b", [0.0] * 23)], 24)
    with pytest.raises(core.CandidateInputError):  # non-finite return
        core.normalize_candidates(
            [_cand("a", [0.0] * 23 + [float("nan")]), _cand("b", [0.0] * 24)], 24)
    with pytest.raises(core.CandidateInputError):  # p-value out of range
        core.normalize_candidates(
            [_cand("a", [0.0] * 24, nominal_p_value=1.2), _cand("b", [0.0] * 24)], 24)
    with pytest.raises(core.CandidateInputError):  # too few observations
        core.normalize_timestamps(_timestamps(10))
    with pytest.raises(core.CandidateInputError):  # non-increasing timestamps
        core.normalize_timestamps([*_timestamps(23), _timestamps(1)[0]])
    with pytest.raises(core.CandidateInputError):  # mixed timezone styles
        core.normalize_timestamps(
            ["2024-01-01T00:00:00Z"] + _timestamps(23, datetime(2024, 1, 2)))
    assert ts[0] == "2024-01-01T00:00:00"


def test_candidate_order_deterministic():
    cands = core.normalize_candidates(
        [_cand("zeta", [0.0] * 24), _cand("alpha", [0.1] * 24)], 24)
    assert [c["candidate_id"] for c in cands] == ["alpha", "zeta"]
    matrix = core.build_matrix(cands)
    assert matrix[0, 0] == 0.1 and matrix[0, 1] == 0.0  # column order matches


# ---------------------------------------------------------------------------
# Metric policy (§5)
# ---------------------------------------------------------------------------


def test_metric_policy():
    r = np.array([0.01, -0.02, 0.03, 0.005])
    value, reason = metrics_mod.metric_value("sharpe_like", r)
    assert reason is None
    assert value == pytest.approx(float(r.mean() / r.std(ddof=1)))
    value, reason = metrics_mod.metric_value("sharpe_like", np.full(10, 0.01))
    assert value is None and "zero" in reason  # never zero-substituted
    value, reason = metrics_mod.metric_value("mean_return", np.array([0.01]))
    assert value is None and "at least" in reason
    with pytest.raises(metrics_mod.MetricError):
        metrics_mod.validate_metric("cumulative_return")  # descriptive only
    assert metrics_mod.cumulative_return(np.array([0.1, 0.1])) == pytest.approx(0.21)


# ---------------------------------------------------------------------------
# CSCV blocks + combinations (§6, §7)
# ---------------------------------------------------------------------------


def test_block_construction_and_limits():
    blocks = cscv.build_blocks(26, 4)  # uneven: sizes differ by at most one
    sizes = [b["size"] for b in blocks]
    assert sum(sizes) == 26 and max(sizes) - min(sizes) <= 1
    covered = [i for b in blocks for i in range(b["start"], b["end"] + 1)]
    assert covered == list(range(26))  # every observation exactly once
    assert cscv.combination_count(8) == 70
    with pytest.raises(cscv.CSCVError):  # odd
        cscv.validate_block_count(5, 100)
    with pytest.raises(cscv.CSCVError):  # below minimum
        cscv.validate_block_count(2, 100)
    with pytest.raises(cscv.CSCVError):  # above maximum (combination limit)
        cscv.validate_block_count(14, 1000)
    with pytest.raises(cscv.CSCVError):  # too few observations for the blocks
        cscv.validate_block_count(8, 24)
    assert cscv.validate_block_count(12, 1000) == 12  # C(12,6)=924 is the cap


def test_combination_ordering_deterministic():
    matrix = np.column_stack([_noise(24, 1), _noise(24, 2)])
    blocks = cscv.build_blocks(24, 4)
    r1 = cscv.run_cscv(matrix, blocks, "mean_return", ["a", "b"])
    r2 = cscv.run_cscv(matrix, blocks, "mean_return", ["a", "b"])
    assert r1 == r2  # deterministic repeated execution
    assert [r["split_id"] for r in r1] == [f"cscv-{i:04d}" for i in range(6)]
    assert r1[0]["is_block_ids"] == [0, 1] and r1[0]["oos_block_ids"] == [2, 3]


# ---------------------------------------------------------------------------
# Rank convention, lambda, PBO (§6, §9)
# ---------------------------------------------------------------------------


def _alternating_universe(n=48):
    """Candidate 'lure' is in-sample best in every combination but OOS-worst;
    'steady' is the mirror.  Built by giving lure a higher mean everywhere
    except it collapses out of sample is impossible with strict alignment —
    instead alternate block-wise so every IS half favours lure and every OOS
    half favours steady is not achievable for ALL combinations; we use the
    exact two-candidate construction where lure > steady on every block's IS
    metric via variance: lure has huge positive outliers early in each block."""
    # Simpler exact construction: lure beats steady in-sample by mean_return in
    # every block, but OOS uses the SAME blocks — so instead make a
    # 2-candidate case with mean_return where lure's mean is higher in every
    # block; then lure wins IS and OOS everywhere → PBO 0, lambda = ln(2).
    lure = np.full(n, 0.002)
    steady = np.full(n, 0.001)
    lure[0] += 1e-9  # break constant-ness is irrelevant for mean_return
    return np.column_stack([lure, steady])


def test_pbo_zero_when_winner_persists():
    matrix = _alternating_universe()
    blocks = cscv.build_blocks(48, 4)
    records = cscv.run_cscv(matrix, blocks, "mean_return", ["lure", "steady"])
    agg = cscv.aggregate_pbo(records, ["lure", "steady"])
    assert agg["pbo_estimate"] == 0.0
    # rank 2 of 2 OOS → omega = 2/3 → lambda = ln(2)
    for r in records:
        assert r["selected_candidate_id"] == "lure"
        assert r["oos_rank"] == 2.0
        assert r["lambda"] == pytest.approx(math.log(2.0))


def test_pbo_one_when_selection_always_fails_oos():
    """IS-best candidate is OOS-worst in every combination: block-wise
    anti-correlated construction with S=4 and mean_return."""
    n = 48
    blocks = cscv.build_blocks(n, 4)
    a = np.zeros(n)
    b = np.zeros(n)
    # In every block, a's mean is +x and b's is -x, with x alternating sign
    # per block — then whichever half is IS, the winner there loses OOS.
    for i, blk in enumerate(blocks):
        sl = slice(blk["start"], blk["end"] + 1)
        a[sl] = 0.01 if i % 2 == 0 else -0.01
        b[sl] = -0.01 if i % 2 == 0 else 0.01
    matrix = np.column_stack([a, b])
    records = cscv.run_cscv(matrix, blocks, "mean_return", ["a", "b"])
    agg = cscv.aggregate_pbo(records, ["a", "b"])
    valid = [r for r in records if r["status"] == "valid"]
    # Combinations with equal +/- blocks IS produce ties (mean 0 both) — the
    # unequal ones select the block-favoured candidate which is OOS-worst.
    non_tied = [r for r in valid if not r["tie_in_sample"]]
    assert non_tied and all(r["lambda"] == pytest.approx(math.log(0.5)) for r in non_tied)
    assert all(r["oos_rank"] == 1.0 for r in non_tied)  # rank 1 = worst OOS
    # Tied splits (lambda == 0) count in the denominator but never as overfit.
    tied = [r for r in valid if r["tie_in_sample"]]
    assert all(r["lambda"] == pytest.approx(0.0) for r in tied)
    assert agg["pbo_estimate"] == pytest.approx(len(non_tied) / len(valid))
    assert agg["lambda_stats"]["fraction_at_zero"] == pytest.approx(len(tied) / len(valid))


def test_tie_handling():
    n = 48
    matrix = np.column_stack([np.full(n, 0.001), np.full(n, 0.001),
                              np.full(n, 0.0005)])
    blocks = cscv.build_blocks(n, 4)
    records = cscv.run_cscv(matrix, blocks, "mean_return", ["a", "b", "c"])
    for r in records:
        assert r["selected_candidate_id"] == "a"  # smallest id among exact ties
        assert r["tie_in_sample"] is True
        assert r["tie_out_of_sample"] is True
        # a and b tie OOS for ranks 2,3 → average 2.5; omega = 2.5/4
        assert r["oos_rank"] == pytest.approx(2.5)
        assert r["lambda"] == pytest.approx(math.log((2.5 / 4) / (1 - 2.5 / 4)))
    # All candidates exactly tied → average rank 2 of 3 → omega 0.5, lambda 0.
    m2 = np.column_stack([np.full(n, 0.001)] * 3)
    r2 = cscv.run_cscv(m2, blocks, "mean_return", ["a", "b", "c"])
    agg = cscv.aggregate_pbo(r2, ["a", "b", "c"])
    assert all(r["lambda"] == pytest.approx(0.0) for r in r2)
    assert agg["pbo_estimate"] == 0.0  # lambda == 0 is not overfit


def test_invalid_split_exclusion():
    """Selected candidate constant in its OOS region under sharpe_like →
    invalid split, excluded from the PBO denominator, never dropped."""
    n = 48
    blocks = cscv.build_blocks(n, 4)
    rng = np.random.default_rng(9)
    a = np.zeros(n)
    half = blocks[1]["end"] + 1
    a[:half] = rng.normal(0.05, 0.01, half)  # dominant + varying early
    a[half:] = 0.0                            # constant in blocks 2, 3
    b = rng.normal(0.0, 0.01, n)
    records = cscv.run_cscv(np.column_stack([a, b]), blocks, "sharpe_like", ["a", "b"])
    agg = cscv.aggregate_pbo(records, ["a", "b"])
    invalid = [r for r in records if r["status"] == "invalid"]
    assert invalid, "expected at least one invalid split"
    assert all("undefined" in r["warning"] for r in invalid)
    assert agg["invalid_split_count"] == len(invalid)
    assert agg["valid_split_count"] + len(invalid) == 6


# ---------------------------------------------------------------------------
# Sharpe moments, PSR, DSR, MinTRL (§11–13)
# ---------------------------------------------------------------------------


def test_sharpe_and_moment_conventions():
    r = np.array([0.01, -0.02, 0.015, 0.005, -0.01, 0.02, 0.0, 0.01,
                  -0.005, 0.012, 0.003, -0.015])
    m = sharpe_mod.sharpe_moments(r)
    assert m["sharpe"] == pytest.approx(float(r.mean() / r.std(ddof=1)))
    # population-moment skew and NON-excess kurtosis, hand-computed
    mu, sd = r.mean(), r.std(ddof=0)
    assert m["skewness"] == pytest.approx(float(((r - mu) ** 3).mean() / sd**3))
    assert m["kurtosis"] == pytest.approx(float(((r - mu) ** 4).mean() / sd**4))
    assert m["kurtosis"] > 0  # non-excess: normal would be 3
    assert m["small_sample_warning"]  # 12 < 30
    assert sharpe_mod.sharpe_moments(np.full(20, 0.01))["status"] == "unavailable"
    assert sharpe_mod.sharpe_moments(np.array([0.01] * 5))["status"] == "unavailable"


def test_psr_reference_values():
    # skew 0, kurt 3 (normal): PSR = Phi(SR*sqrt(T-1)/sqrt(1 + SR^2/2))
    out = sharpe_mod.probabilistic_sharpe(0.1, 0.0, 100, 0.0, 3.0)
    expected = float(sp_stats.norm.cdf(0.1 * math.sqrt(99) / math.sqrt(1 + 0.005)))
    assert out["psr"] == pytest.approx(expected, abs=1e-12)
    assert 0.0 <= out["psr"] <= 1.0
    # benchmark above observed → PSR < 0.5
    assert sharpe_mod.probabilistic_sharpe(0.1, 0.3, 100, 0.0, 3.0)["psr"] < 0.5
    # non-positive variance expansion → unavailable, never NaN
    bad = sharpe_mod.probabilistic_sharpe(2.0, 0.0, 100, 3.0, 1.0)
    assert bad["status"] == "unavailable" and bad["psr"] is None
    assert sharpe_mod.probabilistic_sharpe(0.1, 0.0, 5, 0.0, 3.0)["status"] == "unavailable"


def test_expected_max_sharpe_and_dsr():
    emax = sharpe_mod.expected_max_sharpe(10.0, 0.04)
    g = sharpe_mod.EULER_MASCHERONI
    expected = 0.2 * ((1 - g) * sp_stats.norm.ppf(1 - 1 / 10)
                      + g * sp_stats.norm.ppf(1 - 1 / (10 * math.e)))
    assert emax["expected_max_sharpe"] == pytest.approx(float(expected), abs=1e-12)
    dsr = sharpe_mod.deflated_sharpe(0.15, 200, 0.0, 3.0, 10.0, 0.04)
    ref = sharpe_mod.probabilistic_sharpe(0.15, emax["expected_max_sharpe"],
                                          200, 0.0, 3.0)
    assert dsr["dsr"] == pytest.approx(ref["psr"])
    assert dsr["dsr"] < sharpe_mod.probabilistic_sharpe(0.15, 0.0, 200, 0.0, 3.0)["psr"]
    # one trial → unavailable; zero variance → benchmark 0 with note; bound
    assert sharpe_mod.expected_max_sharpe(1.0, 0.04)["status"] == "unavailable"
    zero_v = sharpe_mod.expected_max_sharpe(10.0, 0.0)
    assert zero_v["expected_max_sharpe"] == 0.0 and zero_v["note"]
    assert sharpe_mod.expected_max_sharpe(1e9, 0.04)["status"] == "unavailable"


def test_minimum_track_record_length():
    out = sharpe_mod.minimum_track_record_length(0.15, 0.0, -0.5, 4.0, 0.95, 252)
    z = float(sp_stats.norm.ppf(0.95))
    denom_sq = 1 - (-0.5) * 0.15 + ((4 - 1) / 4) * 0.15**2
    expected = 1 + denom_sq * (z / 0.15) ** 2
    assert out["min_track_record"] == pytest.approx(expected, abs=1e-9)
    assert out["approx_years"] == pytest.approx(expected / 252)
    # internal consistency: PSR at T = MinTRL equals the confidence level
    check = sharpe_mod.probabilistic_sharpe(0.15, 0.0, out["min_track_record"], -0.5, 4.0)
    assert check["psr"] == pytest.approx(0.95, abs=1e-9)
    assert sharpe_mod.minimum_track_record_length(
        0.1, 0.2, 0.0, 3.0, 0.95)["status"] == "unavailable"  # SR <= SR*
    with pytest.raises(sharpe_mod.SharpeError):
        sharpe_mod.validate_confidence(1.5)
    with pytest.raises(sharpe_mod.SharpeError):
        sharpe_mod.validate_benchmark_sharpe(float("inf"))


# ---------------------------------------------------------------------------
# Multiple testing (§14, §15)
# ---------------------------------------------------------------------------


def _mt(ps, alpha=0.05):
    entries = [{"candidate_id": f"c{i:02d}", "raw_p": p, "provenance": None}
               for i, p in enumerate(ps)]
    return mt_mod.adjust_p_values(entries, alpha)


def test_bonferroni_holm_bh_reference():
    ps = [0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, 0.212, 0.216]
    rows = _mt(ps)
    m = len(ps)
    for row, p in zip(rows, ps):
        assert row["bonferroni"] == pytest.approx(min(1.0, p * m))
    # Holm: cumulative max of (m - j) * p_(j)
    expected_holm = []
    running = 0.0
    for j, p in enumerate(ps):
        running = max(running, min(1.0, (m - j) * p))
        expected_holm.append(running)
    assert [r["holm"] for r in rows] == pytest.approx(expected_holm)
    # BH for this classic example (reverse cumulative minimum)
    expected_bh = []
    running_min = 1.0
    for j in range(m - 1, -1, -1):
        running_min = min(running_min, min(1.0, m / (j + 1) * ps[j]))
        expected_bh.insert(0, running_min)
    assert [r["bh"] for r in rows] == pytest.approx(expected_bh)
    assert rows[0]["bh"] == pytest.approx(0.01)
    # monotone in the sorted order; everything bounded [0, 1]
    assert all(0.0 <= r[k] <= 1.0 for r in rows for k in ("bonferroni", "holm", "bh"))


def test_multiple_testing_ties_missing_and_order():
    rows = _mt([0.01, 0.01, 0.05])
    assert rows[0]["holm"] == rows[1]["holm"] == pytest.approx(0.03)
    rows = mt_mod.adjust_p_values([
        {"candidate_id": "z", "raw_p": 0.04, "provenance": None},
        {"candidate_id": "a", "raw_p": None, "provenance": None},
        {"candidate_id": "m", "raw_p": 0.01, "provenance": None},
    ], 0.05)
    assert [r["candidate_id"] for r in rows] == ["z", "a", "m"]  # order preserved
    assert rows[1]["bonferroni"] is None  # missing stays unavailable
    assert rows[1]["provenance_status"] == "unavailable"
    assert rows[0]["bonferroni"] == pytest.approx(0.08)  # m = 2, not 3
    assert rows[2]["provenance_status"] == "declared"  # never 'verified'
    # invalid values never enter m nor contaminate others (module-level guard)
    rows = mt_mod.adjust_p_values([
        {"candidate_id": "bad", "raw_p": float("nan"), "provenance": None},
        {"candidate_id": "ok", "raw_p": 0.001, "provenance": None},
    ], 0.05)
    assert rows[0]["provenance_status"] == "invalid"
    assert rows[0]["bonferroni"] is None
    assert rows[1]["holm"] == pytest.approx(0.001)  # m = 1
    with pytest.raises(mt_mod.MultipleTestingError):
        mt_mod.validate_alpha(0.9)


# ---------------------------------------------------------------------------
# Dependence (§16)
# ---------------------------------------------------------------------------


def test_dependence_diagnostics_and_constant_handling():
    n = 60
    base = _noise(n, 5)
    matrix = np.column_stack([base, 0.97 * base + _noise(n, 6, scale=0.001),
                              _noise(n, 7), np.full(n, 0.1)])
    ids = ["a", "a_twin", "other", "const"]
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any warning fails the test
        diag = dep_mod.dependence_diagnostics(matrix, ids, 0.9)
    assert diag["constant_candidates"] == ["const"]  # [0.1]*n IS constant
    assert diag["defined_candidate_count"] == 3
    assert any({p["candidate_a"], p["candidate_b"]} == {"a", "a_twin"}
               for p in diag["high_correlation_pairs"])
    assert diag["clusters"] and diag["clusters"][0]["candidates"] == ["a", "a_twin"]
    k, mean_abs = 3, diag["mean_abs_correlation"]
    assert diag["effective_trials_estimate"] == pytest.approx(
        min(k, max(1.0, 1 + (k - 1) * (1 - mean_abs))))
    with pytest.raises(dep_mod.DependenceError):
        dep_mod.validate_dependence_config({"threshold": 1.5})


# ---------------------------------------------------------------------------
# Fingerprints (§20)
# ---------------------------------------------------------------------------


def test_fingerprint_sensitivity():
    kwargs = dict(candidate_ids=["a", "b"], candidate_config_fps=[None, None],
                  timestamps=_timestamps(24),
                  returns_matrix=[[0.01] * 24, [0.02] * 24],
                  alignment_policy="strict")
    u1 = fp_mod.universe_fingerprint(**kwargs)
    assert u1 == fp_mod.universe_fingerprint(**kwargs)  # equivalent input
    changed = dict(kwargs, returns_matrix=[[0.01] * 23 + [0.011], [0.02] * 24])
    assert u1 != fp_mod.universe_fingerprint(**changed)  # changed observation
    cfg = dict(universe_fp=u1, metric="sharpe_like", block_count=8,
               cscv_policy={"x": 1}, tie_policy="t", rank_convention="r",
               sharpe_convention="s", benchmark_sharpe=0.0,
               trial_count_policy={"mode": "raw", "manual_value": None},
               confidence=0.95, alpha=0.05,
               multiple_testing_methods=("bonferroni",),
               dependence_config={"threshold": 0.7}, periods_per_year=None)
    c1 = fp_mod.configuration_fingerprint(**cfg)
    assert c1 != fp_mod.configuration_fingerprint(**{**cfg, "block_count": 6})
    result_kwargs = dict(
        configuration_fp=c1, split_results=[], pbo_aggregate={"pbo_estimate": 0.4},
        sharpe_diagnostics={}, multiple_testing=[{"candidate_id": "a",
                                                  "raw_p_value": 0.01}],
        dependence={}, warnings=[], status="completed")
    r1 = fp_mod.result_fingerprint(**result_kwargs)
    changed_p = dict(result_kwargs,
                     multiple_testing=[{"candidate_id": "a", "raw_p_value": 0.02}])
    assert r1 != fp_mod.result_fingerprint(**changed_p)  # changed p-value
    with pytest.raises(fp_mod.FingerprintError):
        fp_mod.result_fingerprint(**dict(result_kwargs,
                                         pbo_aggregate={"x": float("nan")}))


# ---------------------------------------------------------------------------
# Service / API (§22, §30)
# ---------------------------------------------------------------------------


def test_create_execute_happy_path(client):
    run = client.post(f"{BASE}/runs", json=_payload()).json()
    assert run["combination_count"] == 6
    done = client.post(f"{BASE}/runs/{run['id']}/execute", json={}).json()
    assert done["status"] == "completed"
    assert done["pbo_estimate"] is not None
    assert 0.0 <= done["pbo_estimate"] <= 1.0
    splits = client.get(f"{BASE}/runs/{run['id']}/pbo-splits").json()
    assert splits["total"] == 6
    cands = client.get(f"{BASE}/runs/{run['id']}/candidates").json()["items"]
    assert len(cands) == 3 and all(c["selection_frequency"] is not None for c in cands)
    sd = client.get(f"{BASE}/runs/{run['id']}/sharpe-diagnostics").json()
    assert sd["focus_candidate_id"] and sd["kurtosis_convention"].startswith("NON-excess")
    # repeated execution: no duplicated rows, identical result fingerprint
    again = client.post(f"{BASE}/runs/{run['id']}/execute", json={}).json()
    assert again["result_fingerprint"] == done["result_fingerprint"]
    assert client.get(f"{BASE}/runs/{run['id']}/pbo-splits").json()["total"] == 6
    assert len(client.get(f"{BASE}/runs/{run['id']}/candidates").json()["items"]) == 3


def test_api_validation_errors(client):
    assert client.post(f"{BASE}/runs", json=_payload(block_count=5)).status_code == 422
    assert client.post(f"{BASE}/runs", json=_payload(block_count=14)).status_code == 422
    assert client.post(f"{BASE}/runs", json=_payload(n=24, s=8)).status_code == 422
    assert client.post(f"{BASE}/runs", json=_payload(metric="sortino")).status_code == 422
    assert client.post(f"{BASE}/runs", json=_payload(alpha=0.9)).status_code == 422
    assert client.post(f"{BASE}/runs", json=_payload(confidence=1.5)).status_code == 422
    assert client.post(f"{BASE}/runs", json=_payload(benchmark_sharpe=99)).status_code == 422
    assert client.post(f"{BASE}/runs", json=_payload(
        trial_count_policy={"mode": "manual", "manual_value": 99})).status_code == 422
    assert client.post(f"{BASE}/runs", json=_payload(
        trial_count_policy={"mode": "psychic"})).status_code == 422
    assert client.post(f"{BASE}/runs", json=_payload(
        dependence={"threshold": 2.0})).status_code == 422
    p = _payload()
    p["candidates"] = p["candidates"][:1]
    assert client.post(f"{BASE}/runs", json=p).status_code == 422  # < 2 candidates
    p = _payload()
    p["candidates"][1]["candidate_id"] = "a"
    assert client.post(f"{BASE}/runs", json=p).status_code == 422  # duplicate ids
    p = _payload()
    p["candidates"][0]["returns"] = p["candidates"][0]["returns"][:-1]
    assert client.post(f"{BASE}/runs", json=p).status_code == 422  # mismatch
    p = _payload()
    p["candidates"][0]["nominal_p_value"] = 1.5
    assert client.post(f"{BASE}/runs", json=p).status_code == 422
    raw = json.dumps(_payload()).replace("0.001", "NaN", 1)
    resp = client.post(f"{BASE}/runs", content=raw,
                       headers={"content-type": "application/json"})
    assert resp.status_code == 422  # raw NaN token sanitized
    assert client.post(f"{BASE}/runs", json=_payload(
        dataset_version_id=9999)).status_code == 404
    assert client.get(f"{BASE}/runs/9999").status_code == 404
    assert client.get(f"{BASE}/compare", params={"a": 1, "b": 1}).status_code == 422


def test_honest_failure_and_invalidate(client):
    n = 48
    p = _payload(n=n, candidates=[
        _cand("a", [0.001] * n), _cand("b", [0.002] * n)])
    run = client.post(f"{BASE}/runs", json=p).json()
    done = client.post(f"{BASE}/runs/{run['id']}/execute", json={}).json()
    assert done["status"] == "failed"
    assert "no valid CSCV splits" in done["error_message"]
    # failed run cannot become baseline
    assert client.post(f"{BASE}/runs/{run['id']}/mark-baseline",
                       json={}).status_code == 409
    client.post(f"{BASE}/runs/{run['id']}/invalidate", json={"reason": "x"})
    assert client.post(f"{BASE}/runs/{run['id']}/execute", json={}).status_code == 409


def test_baseline_scope_transitions(client):
    a = client.post(f"{BASE}/runs", json=_payload(name="a")).json()
    client.post(f"{BASE}/runs/{a['id']}/execute", json={})
    b = client.post(f"{BASE}/runs", json=_payload(name="b")).json()
    client.post(f"{BASE}/runs/{b['id']}/execute", json={})
    assert client.post(f"{BASE}/runs/{a['id']}/mark-baseline",
                       json={}).json()["is_baseline"] is True
    # same scope (same universe/metric/blocks/window) → b replaces a
    client.post(f"{BASE}/runs/{b['id']}/mark-baseline", json={})
    assert client.get(f"{BASE}/runs/{a['id']}").json()["is_baseline"] is False
    assert client.get(f"{BASE}/runs/{b['id']}").json()["is_baseline"] is True
    again = client.post(f"{BASE}/runs/{b['id']}/mark-baseline", json={})
    assert again.status_code == 200 and again.json()["is_baseline"]  # idempotent
    # different scope (different block count) preserved independently
    c = client.post(f"{BASE}/runs", json=_payload(name="c", block_count=6)).json()
    client.post(f"{BASE}/runs/{c['id']}/execute", json={})
    client.post(f"{BASE}/runs/{c['id']}/mark-baseline", json={})
    assert client.get(f"{BASE}/runs/{b['id']}").json()["is_baseline"] is True


def test_compare_neutral_with_comparability_warnings(client):
    a = client.post(f"{BASE}/runs", json=_payload(name="a")).json()
    client.post(f"{BASE}/runs/{a['id']}/execute", json={})
    p = _payload(name="b")
    p["candidates"][0]["returns"][0] += 0.001  # different universe
    b = client.post(f"{BASE}/runs", json=p).json()
    client.post(f"{BASE}/runs/{b['id']}/execute", json={})
    cmp_ = client.get(f"{BASE}/compare", params={"a": a["id"], "b": b["id"]}).json()
    assert any("universes differ" in w for w in cmp_["comparability_warnings"])
    kinds = {e["kind"] for g in cmp_["groups"].values() for e in g}
    assert kinds <= {"same", "changed", "only_in_a", "only_in_b", "unavailable"}
    blob = json.dumps(cmp_).lower()
    for banned in ("winner", "better run", "recommended", "best strategy"):
        assert banned not in blob


def test_integrations(client):
    from app.dataset_registry.demo import seed_demo_lineage
    from app.dataset_registry.store import version_demo_key_id
    from app.feature_diagnostics.demo import seed_demo_feature_diagnostics
    from app.feature_diagnostics.store import run_demo_key_id as fd_id
    seed_demo_feature_diagnostics()
    seed_demo_lineage()
    vid = version_demo_key_id("demo:dsv:kopep-features:v1")
    fid = fd_id("demo:fd:heldout-permutation")
    run = client.post(f"{BASE}/runs", json=_payload(
        dataset_version_id=vid, feature_diagnostics_run_id=fid)).json()
    done = client.post(f"{BASE}/runs/{run['id']}/execute",
                       json={"create_experiment": True}).json()
    assert done["dataset_name"] and done["feature_run_integrity"] == "verified_held_out"
    assert done["experiment_id"] is not None
    exp = client.get(f"/experiment-registry/experiments/{done['experiment_id']}").json()
    assert exp["module"] == "overfitting_diagnostics"
    assert "pbo_estimate" in exp["metrics"]
    again = client.post(f"{BASE}/runs/{run['id']}/execute",
                        json={"create_experiment": True}).json()
    assert again["experiment_id"] == done["experiment_id"]  # no duplicate


def test_migration_idempotent_and_registries_preserved(client):
    run = client.post(f"{BASE}/runs", json=_payload()).json()
    db_module.init_db()
    assert client.get(f"{BASE}/runs/{run['id']}").status_code == 200
    for path in ("/experiment-registry/summary", "/model-validation/summary",
                 "/meta-labeling/summary", "/feature-diagnostics/summary"):
        assert client.get(path).status_code == 200


def test_export_privacy(client):
    run = client.post(f"{BASE}/runs", json=_payload()).json()
    client.post(f"{BASE}/runs/{run['id']}/execute", json={})
    export = client.get(f"{BASE}/export").json()
    assert export["schema_version"] == "overfitting_diagnostics_export_v1"
    blob = json.dumps(export)
    for banned in ("C:\\\\", "/Users/", "/home/", "api_key", "API_KEY",
                   "password", "secret", "pickle", "joblib"):
        assert banned not in blob
    assert "NaN" not in blob and "Infinity" not in blob
    assert str(run["id"]) in export["pbo_splits"]


def test_demo_seed_idempotent_and_expected_shapes(client):
    first = client.post(f"{BASE}/demo-seed", json={}).json()
    assert first["created_runs"] == 4
    second = client.post(f"{BASE}/demo-seed", json={}).json()
    assert second["created_runs"] == 0 and second["skipped_existing"] == 4
    runs = client.get(f"{BASE}/runs", params={"page_size": 50}).json()["items"]
    by_key = {r["name"]: r for r in runs}
    noise = next(r for r in runs if "14 noise candidates" in r["name"])
    signal = next(r for r in runs if "persistent drift" in r["name"].lower()
                  or "Persistent drift" in r["name"] or "lower PBO" in r["name"])
    assert noise["status"] == "completed" and signal["status"] == "completed"
    assert noise["pbo_estimate"] > signal["pbo_estimate"]
    assert signal["is_baseline"] is True
    # many-trial deflation: DSR clearly below PSR on the noise run
    assert noise["dsr"] < noise["psr"]
    # no raw p survives Holm/BH at alpha 0.05 in the noise run
    mt = client.get(f"{BASE}/runs/{noise['id']}/multiple-testing").json()["items"]
    with_p = [m for m in mt if m["raw_p_value"] is not None]
    assert any(m["state_raw"] == "below_threshold" for m in with_p)
    assert all(m["state_holm"] == "above_threshold" for m in with_p)
    assert all(m["state_bh"] == "above_threshold" for m in with_p)
    # correlated pair visible in dependence
    dep = client.get(f"{BASE}/runs/{noise['id']}/dependence").json()
    assert any({p["candidate_a"], p["candidate_b"]} == {"corr-a", "corr-b"}
               for p in dep["high_correlation_pairs"])
    # constant + one-trial run: DSR unavailable with note, warnings visible
    short = next(r for r in runs if "Short record" in r["name"])
    sd = client.get(f"{BASE}/runs/{short['id']}/sharpe-diagnostics").json()
    assert sd["dsr"]["dsr"] is None and "one effective trial" in sd["dsr"]["note"]
    full = client.get(f"{BASE}/runs/{short['id']}").json()
    assert any("only 28 observations" in w for w in full["warnings"])
    cands = client.get(f"{BASE}/runs/{short['id']}/candidates").json()["items"]
    flat = next(c for c in cands if c["candidate_id"] == "flat-fee")
    assert flat["raw_sharpe"] is None and flat["sharpe_status"] == "unavailable"
    # honest failure run
    failed = next(r for r in runs if "Invalid configuration" in r["name"])
    assert failed["status"] == "failed" and failed["error_message"]
    assert by_key  # sanity
    summary = client.get(f"{BASE}/summary").json()
    assert summary["runs"] == 4 and summary["baselines"] == 1
