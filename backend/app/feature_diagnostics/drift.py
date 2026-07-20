"""
Feature distribution drift and importance drift diagnostics.

Distribution drift compares an explicit reference sample set against an
explicit comparison set (v1 modes: ``early_vs_late`` — deterministic halves
of the timestamp-sorted samples — or ``first_vs_last_split`` — the held-out
test members of the first vs last valid linked split).  Numeric diagnostics:
mean/median difference, std ratio, p10/p50/p90 quantile changes, two-sample
KS statistic (scipy), PSI over explicit equal-width bins anchored on the
reference range (smoothing epsilon 1e-6, out-of-range comparison values
counted in the boundary bins and reported separately).

PSI classification thresholds (documented, configurable within safe bounds):
none < 0.02 ≤ low < 0.10 ≤ moderate < 0.25 ≤ high by default.  Drift is a
descriptive diagnostic — it never proves model failure and carries no
financial interpretation.

Importance drift compares per-feature mean importance between the earlier and
later halves of the valid splits (by split order): difference, percentage
difference when the denominator is valid, rank change, sign change — with
neutral wording only (increased / decreased / sign changed / unavailable).
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
from scipy import stats as sp_stats

from app.feature_diagnostics.importance import _rank_desc

DRIFT_MODES = ("early_vs_late", "first_vs_last_split")
MIN_DRIFT_BINS = 4
MAX_DRIFT_BINS = 50
DEFAULT_DRIFT_BINS = 10
PSI_EPSILON = 1e-6
DEFAULT_PSI_THRESHOLDS = {"low": 0.02, "moderate": 0.10, "high": 0.25}
SMALL_SAMPLE_N = 30

IMPORTANCE_DRIFT_PCT = {"low": 10.0, "moderate": 25.0, "high": 50.0}


class DriftError(ValueError):
    """Invalid drift configuration (HTTP 422)."""


def validate_drift_config(config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    config = config or {}
    mode = config.get("mode", "early_vs_late")
    if mode not in DRIFT_MODES:
        raise DriftError(f"drift mode must be one of {DRIFT_MODES}")
    bins = config.get("psi_bins", DEFAULT_DRIFT_BINS)
    if isinstance(bins, bool) or not isinstance(bins, int) \
            or not (MIN_DRIFT_BINS <= bins <= MAX_DRIFT_BINS):
        raise DriftError(f"psi_bins must be an integer in [{MIN_DRIFT_BINS}, {MAX_DRIFT_BINS}]")
    thresholds = dict(DEFAULT_PSI_THRESHOLDS)
    override = config.get("psi_thresholds") or {}
    if not isinstance(override, dict):
        raise DriftError("psi_thresholds must be an object")
    for key in ("low", "moderate", "high"):
        if key in override:
            v = override[key]
            if isinstance(v, bool) or not isinstance(v, (int, float)) \
                    or not math.isfinite(v) or not (0.0 < float(v) <= 10.0):
                raise DriftError(f"psi_thresholds.{key} must be a finite number in (0, 10]")
            thresholds[key] = float(v)
    if not (thresholds["low"] < thresholds["moderate"] < thresholds["high"]):
        raise DriftError("psi_thresholds must satisfy low < moderate < high")
    return {"mode": mode, "psi_bins": bins, "psi_thresholds": thresholds}


def classify_psi(psi: Optional[float], thresholds: Dict[str, float]) -> str:
    if psi is None:
        return "unknown"
    if psi < thresholds["low"]:
        return "none"
    if psi < thresholds["moderate"]:
        return "low"
    if psi < thresholds["high"]:
        return "moderate"
    return "high"


def _psi(ref: np.ndarray, cmp_: np.ndarray, bins: int) -> Optional[Dict[str, Any]]:
    lo, hi = float(ref.min()), float(ref.max())
    if hi <= lo:
        return None  # constant reference — PSI undefined
    edges = np.linspace(lo, hi, bins + 1)
    ref_counts, _ = np.histogram(np.clip(ref, lo, hi), bins=edges)
    cmp_counts, _ = np.histogram(np.clip(cmp_, lo, hi), bins=edges)
    ref_frac = ref_counts / len(ref) + PSI_EPSILON
    cmp_frac = cmp_counts / len(cmp_) + PSI_EPSILON
    psi = float(np.sum((cmp_frac - ref_frac) * np.log(cmp_frac / ref_frac)))
    return {"psi": psi, "bins": bins, "bin_edges": [round(float(e), 8) for e in edges],
            "epsilon": PSI_EPSILON}


def numeric_distribution_drift(
    ref: np.ndarray, cmp_: np.ndarray, bins: int, thresholds: Dict[str, float]
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "reference_count": int(len(ref)), "comparison_count": int(len(cmp_)),
        "small_sample_warning": (
            f"fewer than {SMALL_SAMPLE_N} samples on one side — treat drift "
            "statistics as indicative only"
            if min(len(ref), len(cmp_)) < SMALL_SAMPLE_N else None
        ),
    }
    if len(ref) == 0 or len(cmp_) == 0:
        out.update({"status": "unavailable",
                    "reason": "empty reference or comparison set",
                    "classification": "unknown"})
        return out
    ref_std, cmp_std = float(ref.std()), float(cmp_.std())
    out.update({
        "status": "ok",
        "mean_difference": float(cmp_.mean() - ref.mean()),
        "median_difference": float(np.median(cmp_) - np.median(ref)),
        "std_ratio": (cmp_std / ref_std) if ref_std > 0.0 else None,
        "quantile_changes": {
            f"p{q}": float(np.quantile(cmp_, q / 100.0) - np.quantile(ref, q / 100.0))
            for q in (10, 50, 90)
        },
        "out_of_range_fraction": float(
            np.mean((cmp_ < ref.min()) | (cmp_ > ref.max()))
        ),
    })
    # Asymptotic method: deterministic and defined for tied samples.  The
    # two-sample KS statistic is defined for ANY two non-empty samples —
    # including the degenerate case where both sides are internally constant:
    # two DIFFERENT constants give the maximal statistic 1.0 (the strongest
    # possible distribution shift), two equal constants give 0.0.  Suppressing
    # it there would report maximal drift as "unavailable".
    ks = sp_stats.ks_2samp(ref, cmp_, method="asymp")
    out["ks_statistic"] = float(ks.statistic)
    out["ks_pvalue"] = float(ks.pvalue)
    psi_block = _psi(ref, cmp_, bins)
    if psi_block is None:
        out["psi"] = None
        out["psi_detail"] = None
        out["psi_note"] = "PSI undefined: reference values are constant"
    else:
        out["psi"] = round(psi_block["psi"], 8)
        out["psi_detail"] = {"bins": psi_block["bins"], "epsilon": psi_block["epsilon"]}
        out["psi_note"] = None
    out["classification"] = classify_psi(out["psi"], thresholds)
    out["thresholds"] = thresholds
    return out


def importance_drift(
    split_records: Sequence[Dict[str, Any]], feature_names: Sequence[str]
) -> Dict[str, Any]:
    """Early-half vs late-half importance comparison over valid splits."""
    valid = [s for s in split_records if s["status"] == "valid"]
    if len(valid) < 2:
        return {
            "status": "unavailable",
            "reason": "importance drift requires at least 2 valid splits",
            "features": [],
        }
    mid = len(valid) // 2
    early, late = valid[:mid], valid[mid:]

    def _half_mean(half: List[Dict[str, Any]], name: str) -> Optional[float]:
        vals = [s["features"][name]["mean_importance"] for s in half
                if s["features"][name]["mean_importance"] is not None]
        return float(np.mean(vals)) if vals else None

    early_means = {n: _half_mean(early, n) for n in feature_names}
    late_means = {n: _half_mean(late, n) for n in feature_names}
    early_ranks = dict(zip(feature_names,
                           _rank_desc([early_means[n] for n in feature_names])))
    late_ranks = dict(zip(feature_names,
                          _rank_desc([late_means[n] for n in feature_names])))
    features: List[Dict[str, Any]] = []
    for name in feature_names:
        e, l = early_means[name], late_means[name]
        entry: Dict[str, Any] = {
            "feature_name": name,
            "early_mean_importance": e, "late_mean_importance": l,
            "early_rank": early_ranks[name], "late_rank": late_ranks[name],
        }
        if e is None or l is None:
            entry.update({"difference": None, "abs_difference": None,
                          "pct_difference": None, "rank_change": None,
                          "sign_changed": None, "direction": "unavailable",
                          "classification": "unknown"})
        else:
            diff = l - e
            entry["difference"] = diff
            entry["abs_difference"] = abs(diff)
            entry["pct_difference"] = (diff / abs(e) * 100.0) if abs(e) > 1e-12 else None
            entry["rank_change"] = (
                late_ranks[name] - early_ranks[name]
                if early_ranks[name] is not None and late_ranks[name] is not None
                else None
            )
            entry["sign_changed"] = (e > 0) != (l > 0) if e != 0 and l != 0 else (e == 0) != (l == 0)
            entry["direction"] = (
                "increased" if diff > 0 else ("decreased" if diff < 0 else "unchanged")
            )
            pct = entry["pct_difference"]
            if pct is None:
                entry["classification"] = "unknown"
            elif abs(pct) < IMPORTANCE_DRIFT_PCT["low"]:
                entry["classification"] = "none"
            elif abs(pct) < IMPORTANCE_DRIFT_PCT["moderate"]:
                entry["classification"] = "low"
            elif abs(pct) < IMPORTANCE_DRIFT_PCT["high"]:
                entry["classification"] = "moderate"
            else:
                entry["classification"] = "high"
        features.append(entry)
    return {
        "status": "ok",
        "early_splits": [s["split_id"] for s in early],
        "late_splits": [s["split_id"] for s in late],
        "pct_thresholds": IMPORTANCE_DRIFT_PCT,
        "features": features,
    }


__all__ = [
    "DRIFT_MODES", "MIN_DRIFT_BINS", "MAX_DRIFT_BINS", "DEFAULT_DRIFT_BINS",
    "PSI_EPSILON", "DEFAULT_PSI_THRESHOLDS", "SMALL_SAMPLE_N",
    "IMPORTANCE_DRIFT_PCT", "DriftError", "validate_drift_config",
    "classify_psi", "numeric_distribution_drift", "importance_drift",
]
