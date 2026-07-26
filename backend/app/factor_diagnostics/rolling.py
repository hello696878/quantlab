"""
Trailing rolling estimates (v1).

A window that ends at aligned observation ``i`` uses observations
``i - window + 1 .. i`` and NOTHING else.  Centred windows do not exist in
this lab, and because a window never reads an observation after its own end
index, an outlier that arrives later cannot change an earlier estimate — an
invariance the test-suite asserts directly rather than assuming.

Each window records:

* ``window_start`` / ``window_end`` — the first and last period it covers
* ``decision_timestamp``           — when the window's data is complete
                                     (the end of its last period)
* ``effective_timestamp``          — the start of the first period the
                                     estimate could govern, i.e. the NEXT
                                     observation; ``null`` for the final
                                     window, which governs nothing yet
* ``status``                       — ``estimated``, ``rank_deficient``,
                                     ``insufficient_observations`` or
                                     ``failed`` (with a reason)

Failed and rank-deficient windows stay visible; a missing coefficient is
never interpolated from its neighbours.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

from app.experiment_registry.fingerprints import sha256_hex
from app.factor_diagnostics.regression import (RegressionError, ols_fit)

MIN_ROLLING_WINDOW = 4
MAX_ROLLING_WINDOW = 500
MIN_ROLLING_STEP = 1
MAX_ROLLING_STEP = 50
MAX_ROLLING_WINDOWS = 400

ROLLING_STATUSES = ("estimated", "rank_deficient", "insufficient_observations",
                    "failed")


class RollingError(ValueError):
    """Invalid rolling configuration (HTTP 422)."""


def validate_rolling(raw: Any) -> Optional[Dict[str, Any]]:
    """Validate the optional rolling block; ``None`` disables rolling."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise RollingError("rolling must be an object or null")
    unknown = sorted(set(raw) - {"window", "step", "enabled"})
    if unknown:
        raise RollingError(f"unknown rolling keys: {unknown}")
    if raw.get("enabled") is False:
        return None
    window = raw.get("window")
    if isinstance(window, bool) or not isinstance(window, int):
        raise RollingError("rolling window must be an integer")
    if not (MIN_ROLLING_WINDOW <= window <= MAX_ROLLING_WINDOW):
        raise RollingError(
            f"rolling window must be between {MIN_ROLLING_WINDOW} and "
            f"{MAX_ROLLING_WINDOW} observations")
    step = raw.get("step", 1)
    if isinstance(step, bool) or not isinstance(step, int):
        raise RollingError("rolling step must be an integer")
    if not (MIN_ROLLING_STEP <= step <= MAX_ROLLING_STEP):
        raise RollingError(
            f"rolling step must be between {MIN_ROLLING_STEP} and "
            f"{MAX_ROLLING_STEP}")
    return {"window": window, "step": step}


def rolling_estimates(design_rows: Sequence[Dict[str, Any]],
                      factor_ids: Sequence[str], *,
                      window: int, step: int,
                      intercept: bool = True,
                      rank_policy: str = "minimum_norm_descriptive",
                      confidence: float = 0.95) -> List[Dict[str, Any]]:
    """Trailing windows over the aligned observations, oldest window first."""
    n = len(design_rows)
    parameters = len(factor_ids) + (1 if intercept else 0)
    if window <= parameters:
        raise RollingError(
            f"a rolling window of {window} observation(s) cannot identify "
            f"{parameters} parameter(s)")
    end_indices = list(range(window - 1, n, step))
    if len(end_indices) > MAX_ROLLING_WINDOWS:
        raise RollingError(
            f"{len(end_indices)} rolling windows exceed the bound of "
            f"{MAX_ROLLING_WINDOWS}; increase the step or shorten the sample")

    rows: List[Dict[str, Any]] = []
    for window_id, end in enumerate(end_indices):
        start = end - window + 1
        slice_rows = design_rows[start:end + 1]
        y = [float(r["target_return"]) for r in slice_rows]
        x = [[float(v) for v in r["factor_values"]] for r in slice_rows]
        entry: Dict[str, Any] = {
            "window_id": window_id,
            "window_index_start": start,
            "window_index_end": end,
            "window_start": slice_rows[0]["period_start"],
            "window_end": slice_rows[-1]["period_end"],
            "decision_timestamp": slice_rows[-1]["period_end"],
            "effective_timestamp": (design_rows[end + 1]["period_start"]
                                    if end + 1 < n else None),
            "observations": len(slice_rows),
            "coefficients": {},
            "intercept": None,
            "r_squared": None,
            "condition_number": None,
            "rank": None,
            "rank_status": None,
            "status": "estimated",
            "reason": None,
            "fingerprint": None,
        }
        try:
            fit = ols_fit(y, x, factor_ids, intercept=intercept,
                          rank_policy=rank_policy, confidence=confidence)
        except RegressionError as exc:
            entry["status"] = "failed"
            entry["reason"] = str(exc)
            rows.append(entry)
            continue
        entry["coefficients"] = {c["factor_id"]: float(c["coefficient"])
                                 for c in fit["coefficients"]}
        entry["intercept"] = (float(fit["intercept"]["coefficient"])
                              if fit.get("intercept") else None)
        entry["r_squared"] = fit["r_squared"]
        entry["condition_number"] = fit["condition_number"]
        entry["rank"] = fit["rank"]
        entry["rank_status"] = fit["rank_status"]
        if fit["rank_status"] != "full_rank":
            entry["status"] = "rank_deficient"
            entry["reason"] = (
                f"the window design matrix has rank {fit['rank']} of "
                f"{fit['expected_rank']} columns; the coefficients shown are "
                f"the labelled minimum-norm solution")
        entry["fingerprint"] = sha256_hex({
            "kind": "factor_rolling_window_v1",
            "window_start": entry["window_start"],
            "window_end": entry["window_end"],
            "observations": entry["observations"],
            "coefficients": {k: round(v, 12)
                             for k, v in sorted(entry["coefficients"].items())},
            "intercept": (None if entry["intercept"] is None
                          else round(entry["intercept"], 12)),
            "status": entry["status"],
        })
        rows.append(entry)
    return rows


def rolling_summary(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Counts that make window quality visible without a verdict."""
    total = len(rows)
    estimated = sum(1 for r in rows if r["status"] == "estimated")
    rank_deficient = sum(1 for r in rows if r["status"] == "rank_deficient")
    failed = sum(1 for r in rows if r["status"] == "failed")
    condition_warnings = sum(
        1 for r in rows
        if r.get("condition_number") is not None
        and math.isfinite(float(r["condition_number"]))
        and float(r["condition_number"]) > 1e8)
    return {
        "windows": total,
        "estimated": estimated,
        "rank_deficient": rank_deficient,
        "failed": failed,
        "condition_warnings": condition_warnings,
        "convention": ("trailing windows only; a window never reads an "
                       "observation after its own end index"),
    }


__all__ = [
    "MIN_ROLLING_WINDOW", "MAX_ROLLING_WINDOW", "MIN_ROLLING_STEP",
    "MAX_ROLLING_STEP", "MAX_ROLLING_WINDOWS", "ROLLING_STATUSES",
    "RollingError", "validate_rolling", "rolling_estimates", "rolling_summary",
]
