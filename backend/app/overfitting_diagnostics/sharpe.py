"""
Probabilistic Sharpe Ratio, Deflated Sharpe Ratio and Minimum Track Record
Length (after Bailey & López de Prado) — explicit conventions, bounded
outputs, honest unavailability.

Conventions (documented and tested):

* ``SR_hat`` — per-period ``mean/std(ddof=1)`` (see metrics.SHARPE_CONVENTION),
  never annualized inside these formulas; ``T`` = observation count.
* skewness — population moment estimator (scipy ``skew``, ``bias=True``).
* kurtosis — **non-excess** (normal = 3): scipy ``kurtosis(fisher=False,
  bias=True)``.  The PSR variance term uses ``(kurtosis − 1) / 4``.
* PSR(SR*) = Phi( (SR_hat − SR*)·sqrt(T − 1) /
  sqrt(1 − skew·SR_hat + ((kurt − 1)/4)·SR_hat²) ) — the variance expansion
  under the square root must be positive, otherwise PSR is unavailable.
* MinTRL = 1 + (1 − skew·SR_hat + ((kurt − 1)/4)·SR_hat²) ·
  (z_conf / (SR_hat − SR*))², in observations at the stated frequency;
  requires SR_hat > SR*.
* Expected maximum Sharpe across K effectively independent trials (null of
  zero true Sharpe): E[maxSR] ≈ sqrt(V) · ((1 − γ)·Φ⁻¹(1 − 1/K) +
  γ·Φ⁻¹(1 − 1/(K·e))), with γ the Euler–Mascheroni constant and V the
  cross-trial variance of estimated Sharpe ratios.  DSR = PSR(SR* = E[maxSR]).

PSR is a research statistic under the stated assumptions — it is never the
probability that a strategy will be profitable in the future, and DSR is
never proof against overfitting.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional

import numpy as np
from scipy import stats as sp_stats

MIN_SHARPE_OBSERVATIONS = 12
SMALL_SAMPLE_T = 30
MIN_TRIALS_FOR_DSR = 2.0
MAX_EFFECTIVE_TRIALS = 10_000
EULER_MASCHERONI = 0.5772156649015329

MIN_CONFIDENCE = 0.5
MAX_CONFIDENCE = 0.999
MIN_BENCHMARK_SHARPE = -10.0
MAX_BENCHMARK_SHARPE = 10.0

SKEW_CONVENTION = "population moment estimator (scipy skew, bias=True)"
KURTOSIS_CONVENTION = "NON-excess kurtosis (normal = 3; scipy kurtosis, fisher=False, bias=True)"


class SharpeError(ValueError):
    """Invalid Sharpe-diagnostic configuration (HTTP 422)."""


def validate_benchmark_sharpe(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) \
            or not math.isfinite(value) \
            or not (MIN_BENCHMARK_SHARPE <= float(value) <= MAX_BENCHMARK_SHARPE):
        raise SharpeError(
            f"benchmark_sharpe must be a finite number in "
            f"[{MIN_BENCHMARK_SHARPE}, {MAX_BENCHMARK_SHARPE}]"
        )
    return float(value)


def validate_confidence(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) \
            or not math.isfinite(value) \
            or not (MIN_CONFIDENCE < float(value) <= MAX_CONFIDENCE):
        raise SharpeError(
            f"confidence must be a finite number in ({MIN_CONFIDENCE}, {MAX_CONFIDENCE}]"
        )
    return float(value)


def sharpe_moments(returns: np.ndarray) -> Dict[str, Any]:
    """Observed per-period Sharpe + moment estimators, or honest unavailability."""
    r = np.asarray(returns, dtype=np.float64)
    t = int(len(r))
    out: Dict[str, Any] = {"observations": t, "sharpe": None, "skewness": None,
                           "kurtosis": None, "status": "ok", "note": None,
                           "small_sample_warning": None}
    if t < MIN_SHARPE_OBSERVATIONS:
        out["status"] = "unavailable"
        out["note"] = f"needs at least {MIN_SHARPE_OBSERVATIONS} observations"
        return out
    std = float(r.std(ddof=1))
    if std <= 1e-12:
        out["status"] = "unavailable"
        out["note"] = "return standard deviation is zero (constant returns)"
        return out
    out["sharpe"] = float(r.mean() / std)
    out["skewness"] = float(sp_stats.skew(r, bias=True))
    out["kurtosis"] = float(sp_stats.kurtosis(r, fisher=False, bias=True))
    if t < SMALL_SAMPLE_T:
        out["small_sample_warning"] = (
            f"only {t} observations — moment estimates and PSR carry "
            "substantial small-sample uncertainty"
        )
    return out


def _psr_denominator_squared(sharpe: float, skewness: float, kurtosis: float) -> float:
    return 1.0 - skewness * sharpe + ((kurtosis - 1.0) / 4.0) * sharpe * sharpe


def probabilistic_sharpe(
    sharpe: float, benchmark: float, t: int, skewness: float, kurtosis: float
) -> Dict[str, Any]:
    """PSR(SR*) with explicit unavailability when assumptions fail."""
    out: Dict[str, Any] = {"psr": None, "status": "ok", "note": None,
                           "benchmark_sharpe": benchmark}
    if t < MIN_SHARPE_OBSERVATIONS:
        out["status"] = "unavailable"
        out["note"] = f"needs at least {MIN_SHARPE_OBSERVATIONS} observations"
        return out
    for name, v in (("sharpe", sharpe), ("benchmark", benchmark),
                    ("skewness", skewness), ("kurtosis", kurtosis)):
        if not math.isfinite(v):
            out["status"] = "unavailable"
            out["note"] = f"{name} is not finite"
            return out
    denom_sq = _psr_denominator_squared(sharpe, skewness, kurtosis)
    if denom_sq <= 0.0:
        out["status"] = "unavailable"
        out["note"] = (
            "the PSR variance expansion (1 − skew·SR + ((kurt−1)/4)·SR²) is "
            "non-positive — the distributional assumptions are not satisfied"
        )
        return out
    z = (sharpe - benchmark) * math.sqrt(t - 1) / math.sqrt(denom_sq)
    psr = float(sp_stats.norm.cdf(z))
    out["psr"] = min(1.0, max(0.0, psr))
    return out


def expected_max_sharpe(
    trials: float, sharpe_variance: float
) -> Dict[str, Any]:
    """E[max SR] across K effectively independent zero-true-Sharpe trials."""
    out: Dict[str, Any] = {"expected_max_sharpe": None, "status": "ok", "note": None,
                           "trials": trials, "sharpe_variance": sharpe_variance,
                           "euler_mascheroni": EULER_MASCHERONI}
    if not math.isfinite(trials) or trials < MIN_TRIALS_FOR_DSR:
        out["status"] = "unavailable"
        out["note"] = (
            f"the expected-maximum benchmark needs at least "
            f"{MIN_TRIALS_FOR_DSR:g} effectively independent trials"
        )
        return out
    if trials > MAX_EFFECTIVE_TRIALS:
        out["status"] = "unavailable"
        out["note"] = f"trial count exceeds the supported bound of {MAX_EFFECTIVE_TRIALS}"
        return out
    if not math.isfinite(sharpe_variance) or sharpe_variance < 0.0:
        out["status"] = "unavailable"
        out["note"] = "cross-trial Sharpe variance must be finite and non-negative"
        return out
    if sharpe_variance == 0.0:
        out["expected_max_sharpe"] = 0.0
        out["note"] = (
            "zero cross-trial Sharpe variance — under the approximation the "
            "expected maximum equals the zero-Sharpe null"
        )
        return out
    q1 = float(sp_stats.norm.ppf(1.0 - 1.0 / trials))
    q2 = float(sp_stats.norm.ppf(1.0 - 1.0 / (trials * math.e)))
    emax = math.sqrt(sharpe_variance) * (
        (1.0 - EULER_MASCHERONI) * q1 + EULER_MASCHERONI * q2
    )
    out["expected_max_sharpe"] = float(emax)
    return out


def deflated_sharpe(
    sharpe: float, t: int, skewness: float, kurtosis: float,
    trials: float, sharpe_variance: float,
) -> Dict[str, Any]:
    """DSR = PSR against the expected-maximum-Sharpe benchmark."""
    emax = expected_max_sharpe(trials, sharpe_variance)
    out: Dict[str, Any] = {"dsr": None, "status": "ok", "note": None,
                           "expected_max_sharpe": emax["expected_max_sharpe"],
                           "trials": trials, "sharpe_variance": sharpe_variance,
                           "benchmark_note": emax["note"]}
    if emax["status"] != "ok":
        out["status"] = "unavailable"
        out["note"] = emax["note"]
        return out
    psr = probabilistic_sharpe(sharpe, emax["expected_max_sharpe"], t, skewness, kurtosis)
    if psr["status"] != "ok":
        out["status"] = "unavailable"
        out["note"] = psr["note"]
        return out
    out["dsr"] = psr["psr"]
    return out


def minimum_track_record_length(
    sharpe: float, benchmark: float, skewness: float, kurtosis: float,
    confidence: float, periods_per_year: Optional[float] = None,
) -> Dict[str, Any]:
    """Observations needed for PSR(SR*) ≥ confidence, or honest unavailability."""
    out: Dict[str, Any] = {"min_track_record": None, "status": "ok", "note": None,
                           "confidence": confidence, "benchmark_sharpe": benchmark,
                           "unit": "observations at the stated return frequency",
                           "approx_years": None}
    for name, v in (("sharpe", sharpe), ("benchmark", benchmark),
                    ("skewness", skewness), ("kurtosis", kurtosis)):
        if not math.isfinite(v):
            out["status"] = "unavailable"
            out["note"] = f"{name} is not finite"
            return out
    if sharpe <= benchmark:
        out["status"] = "unavailable"
        out["note"] = (
            "the observed Sharpe does not exceed the benchmark — no finite "
            "track record reaches the confidence threshold"
        )
        return out
    denom_sq = _psr_denominator_squared(sharpe, skewness, kurtosis)
    if denom_sq <= 0.0:
        out["status"] = "unavailable"
        out["note"] = "the PSR variance expansion is non-positive"
        return out
    z = float(sp_stats.norm.ppf(confidence))
    mintrl = 1.0 + denom_sq * (z / (sharpe - benchmark)) ** 2
    if not math.isfinite(mintrl) or mintrl <= 0:
        out["status"] = "unavailable"
        out["note"] = "the formula did not produce a finite positive length"
        return out
    out["min_track_record"] = float(mintrl)
    if periods_per_year and periods_per_year > 0:
        out["approx_years"] = float(mintrl / periods_per_year)
    return out


__all__ = [
    "MIN_SHARPE_OBSERVATIONS", "SMALL_SAMPLE_T", "MIN_TRIALS_FOR_DSR",
    "MAX_EFFECTIVE_TRIALS", "EULER_MASCHERONI", "SKEW_CONVENTION",
    "KURTOSIS_CONVENTION", "SharpeError", "validate_benchmark_sharpe",
    "validate_confidence", "sharpe_moments", "probabilistic_sharpe",
    "expected_max_sharpe", "deflated_sharpe", "minimum_track_record_length",
]
