"""
Deterministic fingerprint tests for the Research Experiment Registry (Phase 48.0).

Covers canonicalization (key order independence, whole-float normalization),
non-finite rejection, and the config / result / dataset fingerprints reacting to
the inputs that should change them and ignoring the ones that should not.
"""

from __future__ import annotations

import math

import pytest

fp = pytest.importorskip("app.experiment_registry.fingerprints")


# ---------------------------------------------------------------------------
# Canonical JSON
# ---------------------------------------------------------------------------


def test_key_order_does_not_affect_hash():
    a = fp.sha256_hex({"a": 1, "b": 2, "c": 3})
    b = fp.sha256_hex({"c": 3, "b": 2, "a": 1})
    assert a == b


def test_nested_key_order_does_not_affect_hash():
    a = fp.sha256_hex({"outer": {"x": 1, "y": 2}, "list": [{"m": 1, "n": 2}]})
    b = fp.sha256_hex({"list": [{"n": 2, "m": 1}], "outer": {"y": 2, "x": 1}})
    assert a == b


def test_whole_float_normalizes_to_int():
    assert fp.sha256_hex({"x": 10.0}) == fp.sha256_hex({"x": 10})
    assert fp.sha256_hex({"x": 10.5}) != fp.sha256_hex({"x": 10})


def test_identical_input_identical_hash_across_calls():
    payload = {"module": "m", "params": {"a": [1, 2, 3], "b": "s"}}
    assert fp.sha256_hex(payload) == fp.sha256_hex(payload)


def test_nan_rejected():
    with pytest.raises(fp.FingerprintError):
        fp.canonical_json({"x": float("nan")})


def test_infinity_rejected():
    with pytest.raises(fp.FingerprintError):
        fp.canonical_json({"x": float("inf")})
    with pytest.raises(fp.FingerprintError):
        fp.canonical_json({"x": float("-inf")})


def test_unsupported_type_rejected():
    with pytest.raises(fp.FingerprintError):
        fp.canonical_json({"x": {1, 2, 3}})  # a set is not JSON-safe


def test_bool_preserved_distinct_from_int():
    # True is not treated as 1 for hashing purposes.
    assert fp.sha256_hex({"x": True}) != fp.sha256_hex({"x": 1})


def test_short_hash_length():
    full = fp.sha256_hex({"a": 1})
    assert len(fp.short_hash(full)) == fp.SHORT_HASH_LEN
    assert full.startswith(fp.short_hash(full))


# ---------------------------------------------------------------------------
# Configuration fingerprint
# ---------------------------------------------------------------------------


def _base_config(**over):
    kwargs = dict(
        module="scenario_studio",
        experiment_type="stress",
        parameters={"a": 1, "b": 2},
        random_seed=7,
        dataset_name="fx",
        dataset_version="v1",
        dataset_fingerprint=None,
    )
    kwargs.update(over)
    return fp.configuration_fingerprint(**kwargs)


def test_config_hash_stable_and_order_independent():
    h1 = fp.configuration_fingerprint(
        module="m", experiment_type="t", parameters={"a": 1, "b": 2}, random_seed=1
    )
    h2 = fp.configuration_fingerprint(
        module="m", experiment_type="t", parameters={"b": 2, "a": 1}, random_seed=1
    )
    assert h1 == h2


def test_changed_parameter_changes_hash():
    assert _base_config(parameters={"a": 1, "b": 2}) != _base_config(parameters={"a": 1, "b": 3})


def test_changed_seed_changes_hash():
    assert _base_config(random_seed=7) != _base_config(random_seed=8)


def test_missing_vs_zero_seed_differ():
    assert _base_config(random_seed=None) != _base_config(random_seed=0)


def test_changed_dataset_fingerprint_changes_hash():
    fp_a = "a" * 64
    fp_b = "b" * 64
    assert _base_config(dataset_fingerprint=fp_a) != _base_config(dataset_fingerprint=fp_b)


def test_changed_module_or_type_changes_hash():
    assert _base_config(module="a") != _base_config(module="b")
    assert _base_config(experiment_type="a") != _base_config(experiment_type="b")


# ---------------------------------------------------------------------------
# Result fingerprint
# ---------------------------------------------------------------------------


def test_result_hash_binds_to_config_and_metrics():
    cfg = _base_config()
    r1 = fp.result_fingerprint(metrics={"sharpe": 1.0}, configuration_fingerprint=cfg)
    r2 = fp.result_fingerprint(metrics={"sharpe": 1.0}, configuration_fingerprint=cfg)
    r3 = fp.result_fingerprint(metrics={"sharpe": 2.0}, configuration_fingerprint=cfg)
    r4 = fp.result_fingerprint(metrics={"sharpe": 1.0}, configuration_fingerprint="different")
    assert r1 == r2
    assert r1 != r3
    assert r1 != r4


def test_result_hash_rejects_non_finite_metric():
    cfg = _base_config()
    with pytest.raises(fp.FingerprintError):
        fp.result_fingerprint(metrics={"x": math.inf}, configuration_fingerprint=cfg)


# ---------------------------------------------------------------------------
# Dataset fingerprint helpers
# ---------------------------------------------------------------------------


def test_dataset_fingerprint_from_identity_is_deterministic():
    a = fp.dataset_fingerprint_from_identity(name="ds", version="v1", identity={"rows": 10})
    b = fp.dataset_fingerprint_from_identity(name="ds", version="v1", identity={"rows": 10})
    c = fp.dataset_fingerprint_from_identity(name="ds", version="v1", identity={"rows": 11})
    assert a == b
    assert a != c
    assert fp.is_valid_sha256(a)


def test_normalize_supplied_fingerprint():
    assert fp.normalize_supplied_fingerprint(None) is None
    assert fp.normalize_supplied_fingerprint("  ") is None
    good = "A" * 64
    assert fp.normalize_supplied_fingerprint(good) == "a" * 64
    with pytest.raises(fp.FingerprintError):
        fp.normalize_supplied_fingerprint("nothex")


def test_is_valid_sha256():
    assert fp.is_valid_sha256("f" * 64)
    assert not fp.is_valid_sha256("f" * 63)
    assert not fp.is_valid_sha256("g" * 64)
    assert not fp.is_valid_sha256(123)  # type: ignore[arg-type]
