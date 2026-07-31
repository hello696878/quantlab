"""
Deterministic bootstrap diagnostics (v1).

A bounded, seeded resampling of the MEASURED sample.  Outputs are quantiles
of the resampled statistic distribution — a description of sampling
variability under the chosen resampling scheme, **not** a validation, not a
p-value (none is produced: a bootstrap p-value needs a null-model
construction v1 does not implement, so it is not offered rather than
approximated), and not a fix for overlapping observations (the moving-block
scheme preserves short-range dependence but its block length is an
assumption the caller declares).

Methods
-------
* ``iid``            — resample pairs with replacement
* ``moving_block``   — resample contiguous blocks of the time-ordered
                       pairs (block length declared, wrap-free)
* ``timestamp``      — resample whole cross-sectional timestamps with
                       replacement (for cross-sectional IC)

Determinism: ``numpy.random.default_rng(seed)`` with a caller-declared
integer seed; identical inputs and seed reproduce identical quantiles.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
from scipy import stats as sp_stats

MAX_RESAMPLES = 2000
MIN_RESAMPLES = 50
MAX_BLOCK_LENGTH = 250

BOOTSTRAP_METHODS = ("iid", "moving_block", "timestamp")
BOOTSTRAP_STATISTICS = ("pearson", "spearman", "top_minus_bottom")
DEFAULT_QUANTILES = (0.025, 0.5, 0.975)


class BootstrapError(ValueError):
    """Invalid bootstrap configuration (HTTP 422)."""


def validate_bootstrap_config(raw: Any) -> Optional[Dict[str, Any]]:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise BootstrapError("bootstrap must be an object or null")
    unknown = sorted(set(raw) - {"method", "seed", "resamples",
                                 "block_length", "quantiles", "statistic",
                                 "enabled"})
    if unknown:
        raise BootstrapError(f"unknown bootstrap keys: {unknown}")
    if raw.get("enabled") is False:
        return None
    method = raw.get("method", "iid")
    if method not in BOOTSTRAP_METHODS:
        raise BootstrapError(
            f"bootstrap method must be one of {list(BOOTSTRAP_METHODS)}")
    seed = raw.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise BootstrapError(
            "bootstrap requires an explicit non-negative integer seed")
    resamples = raw.get("resamples", 500)
    if isinstance(resamples, bool) or not isinstance(resamples, int) \
            or not (MIN_RESAMPLES <= resamples <= MAX_RESAMPLES):
        raise BootstrapError(
            f"resamples must be an integer in [{MIN_RESAMPLES}, "
            f"{MAX_RESAMPLES}]")
    block_length = raw.get("block_length")
    if method == "moving_block":
        if isinstance(block_length, bool) or not isinstance(block_length, int) \
                or not (2 <= block_length <= MAX_BLOCK_LENGTH):
            raise BootstrapError(
                f"moving_block requires an integer block_length in "
                f"[2, {MAX_BLOCK_LENGTH}] — the block length is a declared "
                f"assumption, never inferred")
    elif block_length is not None:
        raise BootstrapError("block_length only applies to moving_block")
    quantiles = raw.get("quantiles") or list(DEFAULT_QUANTILES)
    if not isinstance(quantiles, list) or not quantiles \
            or len(quantiles) > 9:
        raise BootstrapError("quantiles must be a list of at most 9 values")
    for q in quantiles:
        if isinstance(q, bool) or not isinstance(q, (int, float)) \
                or not (0.0 < float(q) < 1.0):
            raise BootstrapError("each quantile must be in (0, 1)")
    statistic = raw.get("statistic", "spearman")
    if statistic not in BOOTSTRAP_STATISTICS:
        raise BootstrapError(
            f"bootstrap statistic must be one of {list(BOOTSTRAP_STATISTICS)}")
    return {"method": method, "seed": seed, "resamples": resamples,
            "block_length": block_length,
            "quantiles": sorted(float(q) for q in quantiles),
            "statistic": statistic}


def _statistic(x: np.ndarray, y: np.ndarray, statistic: str,
               *, bucket_count: int) -> Optional[float]:
    if x.size < 3 or np.unique(x).size < 2 or np.unique(y).size < 2:
        return None
    if statistic == "pearson":
        value = float(sp_stats.pearsonr(x, y).statistic)
    elif statistic == "spearman":
        value = float(sp_stats.spearmanr(x, y).statistic)
    else:
        order = np.argsort(x, kind="stable")
        k = max(1, min(x.size // bucket_count, x.size // 2))
        bottom = y[order[:k]]
        top = y[order[-k:]]
        value = float(np.mean(top) - np.mean(bottom))
    return value if math.isfinite(value) else None


def run_bootstrap(pairs: List[Dict[str, Any]], config: Dict[str, Any],
                  *, bucket_count: int) -> Dict[str, Any]:
    ordered = sorted(pairs, key=lambda p: (p["signal_timestamp"],
                                           p["entity_id"]))
    x = np.asarray([p["signal_value"] for p in ordered], dtype=np.float64)
    y = np.asarray([p["outcome_value"] for p in ordered], dtype=np.float64)
    n = x.size
    out: Dict[str, Any] = {
        "method": config["method"], "seed": config["seed"],
        "resamples": config["resamples"],
        "block_length": config.get("block_length"),
        "statistic": config["statistic"],
        "observed": None, "quantiles": {}, "valid_resamples": 0,
        "state": "unavailable", "reason": None,
        "note": ("quantiles of the resampled statistic under the declared "
                 "scheme — a descriptive spread, not a validation and not a "
                 "p-value; overlapping observations remain a stated "
                 "limitation of any resampling scheme here"),
    }
    if n < 8:
        out["reason"] = "fewer than 8 pairs"
        return out
    if config["method"] == "moving_block" and len({
            pair["entity_id"] for pair in ordered}) > 1:
        out["reason"] = (
            "moving_block is unavailable for multiple entities because a "
            "single flattened order would create blocks across entity "
            "boundaries; use timestamp bootstrap for cross-sections")
        return out
    observed = _statistic(
        x, y, config["statistic"], bucket_count=bucket_count)
    if observed is None:
        out["reason"] = ("the observed statistic is unavailable (constant or "
                         "too-small sample)")
        return out
    out["observed"] = observed

    rng = np.random.default_rng(config["seed"])
    values: List[float] = []
    if config["method"] == "timestamp":
        stamps = sorted({p["signal_timestamp"] for p in ordered})
        by_stamp: Dict[str, List[int]] = {}
        for i, p in enumerate(ordered):
            by_stamp.setdefault(p["signal_timestamp"], []).append(i)
        for _ in range(config["resamples"]):
            chosen = rng.integers(0, len(stamps), size=len(stamps))
            index = [i for c in chosen for i in by_stamp[stamps[int(c)]]]
            value = _statistic(x[index], y[index], config["statistic"],
                               bucket_count=bucket_count)
            if value is not None:
                values.append(value)
    elif config["method"] == "moving_block":
        block = int(config["block_length"])
        if block >= n:
            out["reason"] = (f"block_length {block} is not below the sample "
                             f"size {n}")
            return out
        starts_available = n - block + 1
        blocks_needed = math.ceil(n / block)
        for _ in range(config["resamples"]):
            starts = rng.integers(0, starts_available, size=blocks_needed)
            index = [s + offset for s in starts for offset in range(block)]
            index = index[:n]
            value = _statistic(x[index], y[index], config["statistic"],
                               bucket_count=bucket_count)
            if value is not None:
                values.append(value)
    else:
        for _ in range(config["resamples"]):
            index = rng.integers(0, n, size=n)
            value = _statistic(x[index], y[index], config["statistic"],
                               bucket_count=bucket_count)
            if value is not None:
                values.append(value)

    if len(values) < config["resamples"] // 2:
        out["reason"] = (f"only {len(values)} of {config['resamples']} "
                         f"resamples produced a defined statistic")
        return out
    array = np.asarray(values, dtype=np.float64)
    out["quantiles"] = {f"{q:g}": float(np.quantile(array, q))
                        for q in config["quantiles"]}
    out["valid_resamples"] = len(values)
    out["state"] = "available"
    return out


__all__ = [
    "MAX_RESAMPLES", "MIN_RESAMPLES", "MAX_BLOCK_LENGTH", "BOOTSTRAP_METHODS",
    "BOOTSTRAP_STATISTICS", "DEFAULT_QUANTILES", "BootstrapError",
    "validate_bootstrap_config", "run_bootstrap",
]
