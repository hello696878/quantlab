"""
Covariance estimation, validation, repair and stress (v1).

Estimation methods (all deterministic, per-period — never annualized):

* ``sample`` — sample covariance with ddof=1 over the permitted window
  (documented frequency, sample count, no missing values by construction).
* ``diagonal`` — sample variances with off-diagonals set to zero; clearly
  labelled a reference assumption, not an estimate of dependence.
* ``fixed_shrinkage`` — ``(1 - alpha) * sample + alpha * target`` with
  alpha in [0, 1] declared by the caller (never data-driven in v1) and
  the target explicitly one of ``diagonal`` (diagonal of the sample) or
  ``scaled_identity`` (identity times the average sample variance).
  Ledoit-Wolf is deferred: scikit-learn is not an approved dependency of
  this repository and no in-repo implementation exists.

Validation reports symmetry, finiteness, diagonal sign, the minimum
eigenvalue (``numpy.linalg.eigvalsh``), positive-semidefinite status
against a documented tolerance, and the condition number with a
near-singular warning.  Repair is NEVER silent: policy ``none`` leaves an
invalid matrix invalid; policy ``eigenvalue_floor`` clamps eigenvalues at
an explicit visible threshold and retains both original and repaired
eigenvalues plus a repair status, all fingerprinted.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import numpy as np

COVARIANCE_METHODS = ("sample", "diagonal", "fixed_shrinkage")
SHRINKAGE_TARGETS = ("diagonal", "scaled_identity")
REPAIR_POLICIES = ("none", "eigenvalue_floor")

PSD_TOLERANCE = -1e-10          # minimum eigenvalue below this => not PSD
NEAR_SINGULAR_CONDITION = 1e12  # condition number warning threshold
DEFAULT_EIGENVALUE_FLOOR = 1e-10
MIN_COVARIANCE_SAMPLES = 3


class CovarianceError(ValueError):
    """Raised for invalid covariance configuration or inputs."""


def validate_covariance_config(raw: Any) -> Dict[str, Any]:
    if raw is None:
        raw = {"method": "sample"}
    if not isinstance(raw, dict):
        raise CovarianceError("covariance configuration must be an object")
    cfg = dict(raw)
    method = cfg.get("method", "sample")
    if method not in COVARIANCE_METHODS:
        raise CovarianceError(
            f"covariance method must be one of {', '.join(COVARIANCE_METHODS)}")
    out: Dict[str, Any] = {"method": method, "ddof": 1}
    if method == "fixed_shrinkage":
        alpha = cfg.get("alpha")
        if alpha is None or isinstance(alpha, bool):
            raise CovarianceError("fixed_shrinkage requires an explicit alpha")
        try:
            af = float(alpha)
        except (TypeError, ValueError):
            raise CovarianceError("shrinkage alpha must be a number")
        if not math.isfinite(af) or not (0.0 <= af <= 1.0):
            raise CovarianceError("shrinkage alpha must be in [0, 1]")
        out["alpha"] = af
        target = cfg.get("target", "diagonal")
        if target not in SHRINKAGE_TARGETS:
            raise CovarianceError(
                f"shrinkage target must be one of {', '.join(SHRINKAGE_TARGETS)}")
        out["target"] = target
    repair = cfg.get("repair", "none")
    if repair not in REPAIR_POLICIES:
        raise CovarianceError(
            f"covariance repair must be one of {', '.join(REPAIR_POLICIES)}")
    out["repair"] = repair
    if repair == "eigenvalue_floor":
        floor = cfg.get("eigenvalue_floor", DEFAULT_EIGENVALUE_FLOOR)
        try:
            ff = float(floor)
        except (TypeError, ValueError):
            raise CovarianceError("eigenvalue_floor must be a number")
        if not math.isfinite(ff) or not (0.0 < ff <= 1.0):
            raise CovarianceError("eigenvalue_floor must be in (0, 1]")
        out["eigenvalue_floor"] = ff
    return out


def estimate_covariance(window: np.ndarray, cfg: Dict[str, Any]) -> np.ndarray:
    """Estimate the per-period covariance of ``window`` (obs × assets)."""
    if window.ndim != 2 or window.shape[0] < MIN_COVARIANCE_SAMPLES:
        raise CovarianceError(
            f"covariance estimation needs at least {MIN_COVARIANCE_SAMPLES} "
            "observations")
    sample = np.cov(window, rowvar=False, ddof=cfg.get("ddof", 1))
    sample = np.atleast_2d(sample)
    sample = 0.5 * (sample + sample.T)  # symmetrize numeric noise
    method = cfg["method"]
    if method == "sample":
        return sample
    if method == "diagonal":
        return np.diag(np.diag(sample))
    # fixed_shrinkage
    alpha = cfg["alpha"]
    if cfg["target"] == "diagonal":
        target = np.diag(np.diag(sample))
    else:  # scaled_identity
        target = np.eye(sample.shape[0]) * float(np.mean(np.diag(sample)))
    return (1.0 - alpha) * sample + alpha * target


def validate_matrix(cov: np.ndarray) -> Dict[str, Any]:
    """Structural validation of a covariance matrix (never repairs)."""
    report: Dict[str, Any] = {"valid": True, "warnings": []}

    def invalid(reason: str) -> Dict[str, Any]:
        return {"valid": False, "warnings": [reason], "psd": False,
                "min_eigenvalue": None, "max_eigenvalue": None,
                "condition_number": None}

    if cov.ndim != 2 or cov.shape[0] != cov.shape[1]:
        return invalid("covariance must be square")
    if not np.all(np.isfinite(cov)):
        return invalid("covariance contains non-finite values")
    if not np.allclose(cov, cov.T, atol=1e-10):
        return invalid("covariance is not symmetric")
    diag = np.diag(cov)
    if np.any(diag < 0):
        return invalid("covariance has a negative diagonal")
    eigenvalues = np.linalg.eigvalsh(cov)
    min_eig = float(eigenvalues[0])
    max_eig = float(eigenvalues[-1])
    report["min_eigenvalue"] = min_eig
    report["max_eigenvalue"] = max_eig
    report["psd"] = min_eig >= PSD_TOLERANCE
    if not report["psd"]:
        report["warnings"].append(
            f"covariance is not positive semidefinite (min eigenvalue "
            f"{min_eig:.3e})")
    if min_eig > 0 and math.isfinite(max_eig / min_eig):
        report["condition_number"] = max_eig / min_eig
        if max_eig / min_eig > NEAR_SINGULAR_CONDITION:
            report["warnings"].append(
                "covariance is near-singular (condition number above "
                f"{NEAR_SINGULAR_CONDITION:.0e})")
    else:
        report["condition_number"] = None
        if min_eig < 0:
            report["warnings"].append(
                "condition number not reported for a non-PSD covariance")
        elif min_eig == 0:
            report["warnings"].append(
                "covariance is singular (zero minimum eigenvalue); "
                "condition number undefined")
        else:
            report["warnings"].append(
                "covariance is effectively singular (condition number "
                "overflows); treat estimates with caution")
    return report


def repair_matrix(cov: np.ndarray, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Apply the EXPLICIT repair policy; never silent.

    Returns ``{"matrix", "repaired", "policy", "original_eigenvalues",
    "repaired_eigenvalues", "floor"}`` — with policy ``none`` the matrix is
    returned unchanged and ``repaired`` is False even when invalid.
    """
    policy = cfg.get("repair", "none")
    if not np.all(np.isfinite(cov)):
        return {"matrix": cov, "repaired": False, "policy": policy,
                "original_eigenvalues": None, "repaired_eigenvalues": None,
                "floor": None}
    eigenvalues = np.linalg.eigvalsh(0.5 * (cov + cov.T))
    if policy == "none":
        return {"matrix": cov, "repaired": False, "policy": "none",
                "original_eigenvalues": [float(v) for v in eigenvalues],
                "repaired_eigenvalues": None, "floor": None}
    floor = cfg.get("eigenvalue_floor", DEFAULT_EIGENVALUE_FLOOR)
    if float(eigenvalues[0]) >= floor:
        return {"matrix": cov, "repaired": False, "policy": "eigenvalue_floor",
                "original_eigenvalues": [float(v) for v in eigenvalues],
                "repaired_eigenvalues": None, "floor": floor}
    sym = 0.5 * (cov + cov.T)
    vals, vecs = np.linalg.eigh(sym)
    clamped = np.maximum(vals, floor)
    repaired = vecs @ np.diag(clamped) @ vecs.T
    repaired = 0.5 * (repaired + repaired.T)
    return {"matrix": repaired, "repaired": True, "policy": "eigenvalue_floor",
            "original_eigenvalues": [float(v) for v in vals],
            "repaired_eigenvalues": [float(v) for v in clamped],
            "floor": floor}


def correlation_from_covariance(cov: np.ndarray) -> Optional[np.ndarray]:
    """Correlation matrix; None when any variance is zero (no fabrication)."""
    diag = np.diag(cov)
    if np.any(diag <= 0):
        return None
    std = np.sqrt(diag)
    corr = cov / np.outer(std, std)
    corr = np.clip(0.5 * (corr + corr.T), -1.0, 1.0)
    np.fill_diagonal(corr, 1.0)
    return corr


def stress_covariance(cov: np.ndarray, *,
                      correlation_multiplier: Optional[float] = None,
                      volatility_multipliers: Optional[List[float]] = None
                      ) -> Dict[str, Any]:
    """Research stress: scale off-diagonal correlations and/or volatilities.

    Off-diagonal correlations are multiplied and clamped to [-1, 1]; the
    stressed covariance is rebuilt and must pass its own PSD validation
    (the caller applies the explicit repair policy — never automatic).
    """
    corr = correlation_from_covariance(cov)
    if corr is None:
        return {"matrix": None,
                "note": "stress unavailable: a zero-variance asset leaves "
                        "correlation undefined"}
    std = np.sqrt(np.diag(cov))
    if correlation_multiplier is not None:
        m = float(correlation_multiplier)
        if not math.isfinite(m) or m < 0:
            raise CovarianceError("correlation multiplier must be finite and >= 0")
        off = corr * m
        np.fill_diagonal(off, 1.0)
        corr = np.clip(off, -1.0, 1.0)
    if volatility_multipliers is not None:
        mult = np.asarray(volatility_multipliers, dtype=float)
        if mult.shape != std.shape or np.any(~np.isfinite(mult)) or np.any(mult <= 0):
            raise CovarianceError(
                "volatility multipliers must be finite positive values, one "
                "per asset")
        std = std * mult
    stressed = corr * np.outer(std, std)
    return {"matrix": 0.5 * (stressed + stressed.T), "note": None}
