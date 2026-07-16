"""
Deterministic SHA-256 fingerprints for experiment records.

Three fingerprints are produced from **canonicalized JSON**:

* **configuration fingerprint** — identity of the *result-changing inputs*
  (module, experiment type, parameters, random seed, dataset identity, and any
  explicit provenance inputs).  Never includes timestamps, database ids, or
  display-only state, so two runs with the same inputs fingerprint identically
  regardless of when they ran or field order.
* **result fingerprint** — identity of the *outputs* (metrics + optional result
  metadata) bound to the configuration fingerprint, so the same inputs that
  yield the same outputs fingerprint identically.
* **dataset fingerprint** — an already-verified fingerprint supplied by the
  caller, or one derived from a deterministic fixture's *identity metadata*
  (never by hashing multi-gigabyte data during a request), or ``None``.

Canonical JSON policy: UTF-8, recursively sorted keys, compact separators,
whole-number floats normalized to ints (``10.0`` ≡ ``10``), and **NaN /
Infinity are rejected**.  Unsupported types are rejected too — the input must be
plain JSON-compatible data.

Honest limits (documented, not hidden): a fingerprint identifies *inputs* or
*outputs*; it does not prove scientific validity, and it is not a tamper-proof
security control.  It is an integrity and reproducibility aid.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping, Optional, Sequence

CONFIG_SCHEMA_VERSION = "experiment_registry_config_v1"
RESULT_SCHEMA_VERSION = "experiment_registry_result_v1"
DATASET_IDENTITY_SCHEMA_VERSION = "experiment_registry_dataset_identity_v1"
SHORT_HASH_LEN = 12


class FingerprintError(ValueError):
    """Raised when a value cannot be canonicalized (non-finite number, bad type)."""


def _norm_number(value: float) -> Any:
    """Canonicalize whole-number floats to ints (10.0 and 10 mean the same)."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _canonicalize(obj: Any) -> Any:
    """Recursively coerce *obj* into a strictly JSON-safe, canonical form.

    * ``dict`` keys are stringified and the mapping is rebuilt sorted by key.
    * ``bool`` is preserved (before the ``int`` check — ``bool`` is an ``int``).
    * ``float`` rejects NaN / ±Infinity and normalizes whole numbers to ints.
    * ``list`` / ``tuple`` recurse element-wise.
    * ``str`` / ``int`` / ``None`` pass through.
    * Any other type raises :class:`FingerprintError` (no silent coercion).
    """
    if obj is None or isinstance(obj, str):
        return obj
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise FingerprintError(
                "non-finite number (NaN/Infinity) is not allowed in a fingerprint input"
            )
        return _norm_number(obj)
    if isinstance(obj, Mapping):
        # Sort by string key so field order never affects the hash.
        return {str(k): _canonicalize(v) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))}
    if isinstance(obj, (list, tuple)):
        return [_canonicalize(v) for v in obj]
    raise FingerprintError(f"unsupported type for fingerprint input: {type(obj).__name__}")


def canonical_json(obj: Any) -> str:
    """Compact, key-sorted, deterministic JSON.  Rejects NaN/Infinity/bad types."""
    canonical = _canonicalize(obj)
    return json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def sha256_hex(obj: Any) -> str:
    """Full SHA-256 hex digest of the canonical JSON of *obj*."""
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def short_hash(full_hash: str) -> str:
    """First :data:`SHORT_HASH_LEN` hex chars, for compact display."""
    return full_hash[:SHORT_HASH_LEN]


# ---------------------------------------------------------------------------
# Domain fingerprints
# ---------------------------------------------------------------------------


def configuration_fingerprint(
    *,
    module: str,
    experiment_type: str,
    parameters: Optional[Mapping[str, Any]] = None,
    random_seed: Optional[int] = None,
    dataset_name: Optional[str] = None,
    dataset_version: Optional[str] = None,
    dataset_fingerprint: Optional[str] = None,
    provenance_inputs: Optional[Mapping[str, Any]] = None,
) -> str:
    """Full SHA-256 of the canonical *configuration* (result-changing inputs).

    Deliberately excludes timestamps, database ids, notes, tags, and any
    display-only state.  ``None`` values are dropped by canonicalization only at
    the top level here (we pass an explicit shape), so a missing seed and a seed
    of ``0`` fingerprint differently — that is intentional.
    """
    payload = {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "module": module,
        "experiment_type": experiment_type,
        "parameters": dict(parameters or {}),
        "random_seed": random_seed,
        "dataset": {
            "name": dataset_name,
            "version": dataset_version,
            "fingerprint": dataset_fingerprint,
        },
        "provenance_inputs": dict(provenance_inputs or {}),
    }
    return sha256_hex(payload)


def result_fingerprint(
    *,
    metrics: Optional[Mapping[str, Any]] = None,
    configuration_fingerprint: str,
    result_metadata: Optional[Mapping[str, Any]] = None,
) -> str:
    """Full SHA-256 of the canonical *result* (metrics bound to the config fp)."""
    payload = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "configuration_fingerprint": configuration_fingerprint,
        "metrics": dict(metrics or {}),
        "result_metadata": dict(result_metadata or {}),
    }
    return sha256_hex(payload)


def dataset_fingerprint_from_identity(
    *,
    name: str,
    version: Optional[str] = None,
    identity: Optional[Mapping[str, Any]] = None,
) -> str:
    """Derive a dataset fingerprint from deterministic *identity metadata*.

    This hashes the fixture's declared identity (name, version, small metadata
    such as row counts or a content hash the caller already computed) — **not**
    the raw dataset bytes.  Use this for deterministic offline fixtures whose
    identity is stable and cheap to describe.
    """
    payload = {
        "schema_version": DATASET_IDENTITY_SCHEMA_VERSION,
        "name": name,
        "version": version,
        "identity": dict(identity or {}),
    }
    return sha256_hex(payload)


_SHA256_LEN = 64


def is_valid_sha256(value: str) -> bool:
    """True when *value* is a 64-char lowercase-or-uppercase hex string."""
    if not isinstance(value, str) or len(value) != _SHA256_LEN:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def normalize_supplied_fingerprint(value: Optional[str]) -> Optional[str]:
    """Validate a caller-supplied dataset fingerprint (lowercased) or ``None``.

    Raises :class:`FingerprintError` if a non-empty value is not a valid SHA-256
    hex string, so bad fingerprints fail loudly rather than silently persisting.
    """
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if not is_valid_sha256(value):
        raise FingerprintError("dataset_fingerprint must be a 64-char SHA-256 hex string")
    return value.lower()


def canonicalize_for_hash(obj: Any) -> Any:
    """Public helper: return the canonical (JSON-safe) form used before hashing.

    Useful for tests and for callers that want to inspect exactly what will be
    hashed.  Sequences are returned as lists; mappings as key-sorted dicts.
    """
    return _canonicalize(obj)


__all__ = [
    "CONFIG_SCHEMA_VERSION",
    "RESULT_SCHEMA_VERSION",
    "DATASET_IDENTITY_SCHEMA_VERSION",
    "SHORT_HASH_LEN",
    "FingerprintError",
    "canonical_json",
    "sha256_hex",
    "short_hash",
    "configuration_fingerprint",
    "result_fingerprint",
    "dataset_fingerprint_from_identity",
    "is_valid_sha256",
    "normalize_supplied_fingerprint",
    "canonicalize_for_hash",
]

# Silence unused-import linters for typing-only names kept for clarity.
_ = Sequence
