"""
Input model: feature definitions + samples, validated and normalized.

Policies (explicit, recorded in run configuration):
* missing values — rejected at input (v1 has no imputation; callers must
  supply complete rows);
* categorical features — not supported in v1; callers must pre-encode to
  numeric columns upstream and document the encoding;
* target — always supplied explicitly, never inferred from a column;
* ordering — samples sort deterministically by (timestamp, sample_id);
  features keep the caller's declared order.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np

MIN_SAMPLES = 16
MAX_SAMPLES = 2000
MIN_FEATURES = 1
MAX_FEATURES = 32
MAX_NAME_LEN = 64
MIN_TRAIN_SIZE = 8
MAX_DECLARED_SPLITS = 12

TARGET_TYPES = ("binary_classification", "regression")

MISSING_VALUE_POLICY = "reject (v1 accepts complete numeric rows only; no imputation)"
CATEGORICAL_POLICY = (
    "not supported in v1 — categorical features must be pre-encoded to numeric "
    "columns by the caller"
)


class FeatureInputError(ValueError):
    """Invalid feature/sample input (HTTP 422)."""


def _parse_time(value: Any, field: str) -> Tuple[datetime, bool]:
    if not isinstance(value, str) or not value:
        raise FeatureInputError(f"{field} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise FeatureInputError(f"{field} {value!r} is not valid ISO-8601")
    return parsed, parsed.tzinfo is not None


def normalize_feature_definitions(defs: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(defs, (list, tuple)):
        raise FeatureInputError("features must be a list of feature definitions")
    if not (MIN_FEATURES <= len(defs) <= MAX_FEATURES):
        raise FeatureInputError(
            f"feature count must be between {MIN_FEATURES} and {MAX_FEATURES} "
            f"(got {len(defs)})"
        )
    seen: set[str] = set()
    normalized: List[Dict[str, Any]] = []
    for d in defs:
        name = d.get("feature_name")
        if not isinstance(name, str) or not name.strip():
            raise FeatureInputError("every feature needs a non-empty feature_name")
        name = name.strip()
        if len(name) > MAX_NAME_LEN:
            raise FeatureInputError(f"feature_name {name[:20]!r}… exceeds {MAX_NAME_LEN} chars")
        if name.lower() == "target":
            raise FeatureInputError("a feature may not be named 'target'")
        if name in seen:
            raise FeatureInputError(f"duplicate feature_name {name!r}")
        seen.add(name)
        data_type = d.get("data_type", "numeric")
        if data_type != "numeric":
            raise FeatureInputError(
                f"feature {name!r}: data_type must be 'numeric' ({CATEGORICAL_POLICY})"
            )
        for opt in ("display_name", "source_column", "feature_group", "description",
                    "dataset_schema_reference"):
            v = d.get(opt)
            if v is not None and (not isinstance(v, str) or len(v) > 200):
                raise FeatureInputError(f"feature {name!r}: {opt} must be a string ≤ 200 chars")
        normalized.append({
            "feature_name": name,
            "display_name": d.get("display_name"),
            "data_type": "numeric",
            "source_column": d.get("source_column"),
            "feature_group": d.get("feature_group"),
            "description": d.get("description"),
            "dataset_schema_reference": d.get("dataset_schema_reference"),
        })
    return normalized


def normalize_samples(
    samples: Sequence[Dict[str, Any]],
    feature_names: Sequence[str],
    target_type: str,
) -> List[Dict[str, Any]]:
    if target_type not in TARGET_TYPES:
        raise FeatureInputError(f"target_type must be one of {TARGET_TYPES}")
    if not isinstance(samples, (list, tuple)):
        raise FeatureInputError("samples must be a list")
    if not (MIN_SAMPLES <= len(samples) <= MAX_SAMPLES):
        raise FeatureInputError(
            f"sample count must be between {MIN_SAMPLES} and {MAX_SAMPLES} "
            f"(got {len(samples)})"
        )
    seen: set[str] = set()
    tz_flags: set[bool] = set()
    normalized: List[Dict[str, Any]] = []
    for s in samples:
        sid = s.get("sample_id")
        if not isinstance(sid, str) or not sid.strip():
            raise FeatureInputError("every sample needs a non-empty sample_id")
        sid = sid.strip()
        if len(sid) > MAX_NAME_LEN:
            raise FeatureInputError(f"sample_id {sid[:20]!r}… exceeds {MAX_NAME_LEN} chars")
        if sid in seen:
            raise FeatureInputError(f"duplicate sample_id {sid!r}")
        seen.add(sid)
        parsed, aware = _parse_time(s.get("timestamp"), f"sample {sid} timestamp")
        tz_flags.add(aware)
        if len(tz_flags) > 1:
            raise FeatureInputError(
                "timestamps mix timezone-aware and naive values — use one convention"
            )
        raw_features = s.get("features")
        if not isinstance(raw_features, dict):
            raise FeatureInputError(f"sample {sid}: features must be an object")
        extra = set(raw_features) - set(feature_names)
        if extra:
            raise FeatureInputError(
                f"sample {sid}: unknown feature(s) {sorted(extra)[:3]} not declared"
            )
        values: Dict[str, float] = {}
        for name in feature_names:
            if name not in raw_features:
                raise FeatureInputError(
                    f"sample {sid}: missing value for feature {name!r} "
                    f"(missing-value policy: {MISSING_VALUE_POLICY})"
                )
            v = raw_features[name]
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                raise FeatureInputError(
                    f"sample {sid}: feature {name!r} must be a finite number"
                )
            values[name] = float(v)
        target = s.get("target")
        if isinstance(target, bool) or not isinstance(target, (int, float)) \
                or not math.isfinite(target):
            raise FeatureInputError(f"sample {sid}: target must be a finite number")
        target = float(target)
        if target_type == "binary_classification" and target not in (0.0, 1.0):
            raise FeatureInputError(
                f"sample {sid}: binary_classification targets must be 0 or 1"
            )
        # Persist a CANONICAL timestamp, not the caller's raw string: samples
        # are read back with a lexicographic TEXT sort, and only a canonical
        # form makes that text order equal the chronological order this list is
        # sorted (and fingerprinted) in.  Aware timestamps normalize to UTC so
        # differing offsets cannot reorder; naive ones normalize the separator.
        canonical_ts = (
            parsed.astimezone(timezone.utc).isoformat() if aware else parsed.isoformat()
        )
        normalized.append({
            "sample_id": sid,
            "timestamp": canonical_ts,
            "_sort_key": (parsed, sid),
            "features": values,
            "target": target,
        })
    normalized.sort(key=lambda s: s["_sort_key"])
    for s in normalized:
        del s["_sort_key"]
    return normalized


def build_matrix(
    samples: Sequence[Dict[str, Any]], feature_names: Sequence[str]
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """Deterministic (X, y, sample_ids) in normalized sample order."""
    X = np.array(
        [[s["features"][name] for name in feature_names] for s in samples],
        dtype=np.float64,
    )
    y = np.array([s["target"] for s in samples], dtype=np.float64)
    ids = [s["sample_id"] for s in samples]
    return X, y, ids


def check_target_leakage(X: np.ndarray, y: np.ndarray, feature_names: Sequence[str]) -> None:
    """Reject features that are the target (or an exact affine transform of it).

    A |correlation| of exactly 1.0 (within float tolerance) between a feature
    and the target means the feature is a deterministic affine copy of the
    target — the clearest form of target leakage.  Near-perfect correlations
    are surfaced by the correlation diagnostics instead of being rejected.
    """
    y_std = float(np.std(y))
    for j, name in enumerate(feature_names):
        col = X[:, j]
        if np.array_equal(col, y):
            raise FeatureInputError(
                f"feature {name!r} is identical to the target — target leakage"
            )
        if y_std > 0.0 and float(np.std(col)) > 0.0:
            corr = float(np.corrcoef(col, y)[0, 1])
            if abs(corr) >= 1.0 - 1e-12:
                raise FeatureInputError(
                    f"feature {name!r} is an exact affine transform of the target "
                    "(|correlation| = 1) — target leakage"
                )


def constant_features(X: np.ndarray, feature_names: Sequence[str]) -> List[str]:
    return [name for j, name in enumerate(feature_names)
            if float(np.std(X[:, j])) == 0.0]


def validate_declared_splits(
    declared: Sequence[Dict[str, Any]], sample_ids: Sequence[str]
) -> List[Dict[str, Any]]:
    """Caller-declared held-out splits: validated for structure, never verified."""
    if not isinstance(declared, (list, tuple)) or not declared:
        raise FeatureInputError("declared_splits must be a non-empty list")
    if len(declared) > MAX_DECLARED_SPLITS:
        raise FeatureInputError(f"at most {MAX_DECLARED_SPLITS} declared splits are allowed")
    known = set(sample_ids)
    seen_ids: set[str] = set()
    out: List[Dict[str, Any]] = []
    for d in declared:
        split_id = d.get("split_id")
        if not isinstance(split_id, str) or not split_id.strip():
            raise FeatureInputError("every declared split needs a non-empty split_id")
        split_id = split_id.strip()
        if split_id in seen_ids:
            raise FeatureInputError(f"duplicate declared split_id {split_id!r}")
        seen_ids.add(split_id)
        train = d.get("train_sample_ids")
        test = d.get("test_sample_ids")
        if not isinstance(train, (list, tuple)) or not isinstance(test, (list, tuple)):
            raise FeatureInputError(
                f"split {split_id}: train_sample_ids and test_sample_ids must be lists"
            )
        train, test = list(dict.fromkeys(train)), list(dict.fromkeys(test))
        unknown = [sid for sid in [*train, *test] if sid not in known]
        if unknown:
            raise FeatureInputError(
                f"split {split_id}: unknown sample id(s) {unknown[:3]}"
            )
        overlap = set(train) & set(test)
        if overlap:
            raise FeatureInputError(
                f"split {split_id}: train/test overlap ({sorted(overlap)[:3]})"
            )
        if len(train) < MIN_TRAIN_SIZE:
            raise FeatureInputError(
                f"split {split_id}: at least {MIN_TRAIN_SIZE} training samples required"
            )
        if not test:
            raise FeatureInputError(f"split {split_id}: test set is empty")
        out.append({"split_id": split_id, "train_sample_ids": train,
                    "test_sample_ids": test})
    return out


__all__ = [
    "MIN_SAMPLES", "MAX_SAMPLES", "MIN_FEATURES", "MAX_FEATURES",
    "MIN_TRAIN_SIZE", "MAX_DECLARED_SPLITS", "TARGET_TYPES",
    "MISSING_VALUE_POLICY", "CATEGORICAL_POLICY", "FeatureInputError",
    "normalize_feature_definitions", "normalize_samples", "build_matrix",
    "check_target_leakage", "constant_features", "validate_declared_splits",
]
