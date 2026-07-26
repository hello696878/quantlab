"""
Deterministic linear estimators for the Factor Diagnostics Lab (v1).

Only the repository's approved numerical stack is used — ``numpy`` for the
linear algebra and ``scipy.stats`` for the Student-t tail.  statsmodels and
scikit-learn are NOT installed and are deliberately not added: everything
here is a closed-form estimator with a documented formula.

Ordinary least squares
----------------------
``beta_hat`` minimises ``||y - X beta||²`` and is obtained from the singular
value decomposition of ``X`` (``numpy.linalg.lstsq``), which is numerically
stable where the normal equations ``(XᵀX)⁻¹Xᵀy`` are not.  Rank is read from
the same decomposition with an explicit tolerance; the condition number is
reported on the CENTRED factor block so an intercept column's scale cannot
mask two near-duplicate factors (the convention already used by the
Portfolio Lab's price-based factor view in ``app/portfolio.py``).

Classical covariance (the only one v1 offers, see
``STANDARD_ERROR_METHOD``):

    sigma² = RSS / (n - p)          p = columns of X, including the intercept
    Var(beta_hat) = sigma² (XᵀX)⁻¹
    se_j = sqrt(Var_jj),  t_j = beta_j / se_j,  p_j = 2 · P(T_{n-p} > |t_j|)

These assume homoskedastic, serially uncorrelated errors.  They are NEVER
labelled robust, and no HC/HAC estimator is implemented or advertised —
adding an untested robust estimator would be worse than saying plainly that
none exists.

Ridge (explicit research reference only)
---------------------------------------
    beta_hat = (XᵀX + lambda·I)⁻¹Xᵀy,  the intercept excluded from I.

Ridge coefficients are labelled ``regularised``; they carry no standard
errors, no t-statistics and no p-values, and no lambda is ever selected
automatically.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy import stats as sp_stats

MIN_DEGREES_OF_FREEDOM = 1
MAX_CONDITION_NUMBER_WARNING = 1e8
RANK_TOLERANCE_SCALE = 1e-12
CONSTANT_TOLERANCE = 1e-12
ZERO_VARIANCE_TOLERANCE = 1e-24

INTERCEPT_POLICIES = ("include", "exclude")
RANK_POLICIES = ("fail", "minimum_norm_descriptive")
REGRESSION_METHODS = ("ols", "ridge")
RIDGE_SCALINGS = ("none", "zscore_fit_sample")
MIN_RIDGE_LAMBDA = 0.0
MAX_RIDGE_LAMBDA = 1e6
MIN_CONFIDENCE = 0.5
MAX_CONFIDENCE = 0.999

STANDARD_ERROR_METHOD = "classical_ols"
STANDARD_ERROR_METHODS = ("classical_ols",)
STANDARD_ERROR_ASSUMPTIONS = (
    "classical OLS covariance sigma^2 (X'X)^-1 — assumes homoskedastic, "
    "serially uncorrelated errors; NOT robust, NOT HAC/Newey-West"
)

RANK_STATUSES = ("full_rank", "rank_deficient_descriptive")


class RegressionError(ValueError):
    """Invalid regression input or an honestly refused fit (HTTP 422)."""


def validate_confidence(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) \
            or not math.isfinite(float(value)) \
            or not (MIN_CONFIDENCE <= float(value) <= MAX_CONFIDENCE):
        raise RegressionError(
            f"confidence must be a finite number in "
            f"[{MIN_CONFIDENCE}, {MAX_CONFIDENCE}]")
    return float(value)


def validate_ridge_lambda(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) \
            or not math.isfinite(float(value)) \
            or not (MIN_RIDGE_LAMBDA <= float(value) <= MAX_RIDGE_LAMBDA):
        raise RegressionError(
            f"ridge_lambda must be a finite number in "
            f"[{MIN_RIDGE_LAMBDA}, {MAX_RIDGE_LAMBDA}]")
    return float(value)


def _design(factor_matrix: np.ndarray, intercept: bool) -> np.ndarray:
    if intercept:
        return np.column_stack([np.ones(factor_matrix.shape[0]),
                                factor_matrix])
    return factor_matrix


def _finite_array(values: Sequence[Sequence[float]] | Sequence[float],
                  label: str) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if not np.isfinite(array).all():
        raise RegressionError(f"{label} contains a non-finite value")
    return array


def column_diagnostics(factor_matrix: np.ndarray,
                       names: Sequence[str]) -> Dict[str, Any]:
    """Constant and exactly duplicated factor columns (never auto-removed)."""
    constant: List[str] = []
    for j, name in enumerate(names):
        column = factor_matrix[:, j]
        if float(np.max(column) - np.min(column)) <= CONSTANT_TOLERANCE:
            constant.append(name)
    duplicates: List[Dict[str, str]] = []
    for j in range(len(names)):
        for i in range(j):
            a, b = factor_matrix[:, i], factor_matrix[:, j]
            scale = max(1.0, float(np.max(np.abs(a))), float(np.max(np.abs(b))))
            if float(np.max(np.abs(a - b))) <= CONSTANT_TOLERANCE * scale:
                duplicates.append({"factor_a": names[i], "factor_b": names[j]})
    return {"constant_columns": constant, "duplicate_columns": duplicates}


def conditioning(factor_matrix: np.ndarray) -> Dict[str, Any]:
    """Rank, singular values and condition number of the CENTRED factors."""
    centred = factor_matrix - factor_matrix.mean(axis=0)
    singular = np.linalg.svd(centred, compute_uv=False)
    singular_list = [float(s) for s in singular]
    largest = singular_list[0] if singular_list else 0.0
    smallest = singular_list[-1] if singular_list else 0.0
    tolerance = max(centred.shape) * RANK_TOLERANCE_SCALE * max(largest, 1e-300)
    factor_rank = int(sum(1 for s in singular_list if s > tolerance))
    condition_number: Optional[float] = None
    condition_state = "unavailable"
    if singular_list and smallest > tolerance and largest > 0.0:
        condition_number = float(largest / smallest)
        condition_state = ("high" if condition_number
                           > MAX_CONDITION_NUMBER_WARNING else "ok")
    elif singular_list:
        condition_state = "singular"
    return {
        "singular_values": singular_list,
        "factor_rank": factor_rank,
        "condition_number": condition_number,
        "condition_state": condition_state,
        "condition_note": (
            "condition number of the centred factor block "
            "(largest / smallest singular value); values above "
            f"{MAX_CONDITION_NUMBER_WARNING:.0e} are flagged, which is a "
            "neutral warning and not a universal rule"),
    }


def ols_fit(y_values: Sequence[float],
            factor_values: Sequence[Sequence[float]],
            names: Sequence[str], *,
            intercept: bool = True,
            rank_policy: str = "fail",
            confidence: float = 0.95) -> Dict[str, Any]:
    """Least-squares fit with honest rank, statistic and availability states."""
    if rank_policy not in RANK_POLICIES:
        raise RegressionError(f"rank_policy must be one of {list(RANK_POLICIES)}")
    y = _finite_array(y_values, "target series")
    factor_matrix = _finite_array(factor_values, "factor matrix")
    if factor_matrix.ndim != 2:
        raise RegressionError("the factor matrix must be two-dimensional")
    n, k = factor_matrix.shape
    if len(names) != k:
        raise RegressionError("factor names must match the factor columns")
    if y.shape[0] != n:
        raise RegressionError(
            f"target has {y.shape[0]} observations but the factor matrix has "
            f"{n}")

    design = _design(factor_matrix, intercept)
    parameters = design.shape[1]
    if n <= parameters:
        raise RegressionError(
            f"{n} observations cannot identify {parameters} parameter(s); at "
            f"least {parameters + MIN_DEGREES_OF_FREEDOM} are required")

    cond = conditioning(factor_matrix)
    columns = column_diagnostics(factor_matrix, names)
    design_singular = np.linalg.svd(design, compute_uv=False)
    design_tolerance = (max(design.shape) * RANK_TOLERANCE_SCALE
                        * max(float(design_singular[0]), 1e-300))
    rank = int(sum(1 for s in design_singular if s > design_tolerance))
    rank_status = "full_rank" if rank == parameters else \
        "rank_deficient_descriptive"
    if rank_status != "full_rank" and rank_policy == "fail":
        raise RegressionError(
            f"the design matrix is rank deficient (rank {rank} of "
            f"{parameters} columns): the coefficients are not identified. "
            f"Constant columns: {columns['constant_columns'] or 'none'}; "
            f"duplicate columns: "
            f"{[d['factor_a'] + '=' + d['factor_b'] for d in columns['duplicate_columns']] or 'none'}. "
            f"Re-run with rank_policy 'minimum_norm_descriptive' to record a "
            f"labelled minimum-norm solution instead.")

    beta, _residual_ss, _lstsq_rank, _sv = np.linalg.lstsq(design, y,
                                                           rcond=None)
    if not np.isfinite(beta).all():
        raise RegressionError("the least-squares solution is not finite")
    fitted = design @ beta
    residuals = y - fitted
    if not (np.isfinite(fitted).all() and np.isfinite(residuals).all()):
        raise RegressionError("the fitted values are not finite")

    rss = float(np.sum(residuals ** 2))
    tss = float(np.sum((y - y.mean()) ** 2))
    dof = int(n - parameters)
    sigma_squared = rss / dof if dof >= MIN_DEGREES_OF_FREEDOM else None

    r_squared: Optional[float] = None
    adjusted: Optional[float] = None
    r_squared_note: Optional[str] = None
    if tss <= ZERO_VARIANCE_TOLERANCE:
        r_squared_note = (
            "the target series has zero variance, so R-squared is undefined "
            "(the total sum of squares is zero) — it is reported as "
            "unavailable rather than 0 or 1")
    else:
        r_squared = float(1.0 - rss / tss)
        denominator = n - parameters
        if denominator >= 1:
            adjusted = float(1.0 - (1.0 - r_squared) * (n - 1) / denominator)

    residual_mean = float(np.mean(residuals))
    residual_std = float(np.std(residuals, ddof=1)) if n >= 2 else None
    rmse = float(math.sqrt(rss / n)) if n > 0 else None

    zero_residual = rss <= ZERO_VARIANCE_TOLERANCE * max(1.0, tss)
    standard_error_state = "available"
    standard_error_note: Optional[str] = None
    if rank_status != "full_rank":
        standard_error_state = "unavailable"
        standard_error_note = (
            "standard errors, t-statistics and p-values are withheld for a "
            "rank-deficient design: the minimum-norm coefficients are not "
            "identified, so their sampling distribution is undefined")
    elif dof < MIN_DEGREES_OF_FREEDOM:
        standard_error_state = "unavailable"
        standard_error_note = (
            f"insufficient degrees of freedom ({dof}) for inferential "
            f"statistics")
    elif zero_residual:
        standard_error_state = "unavailable"
        standard_error_note = (
            "the residual variance is zero (an exact fit), so the classical "
            "standard errors collapse to zero and every t-statistic would be "
            "infinite; they are withheld instead")

    covariance_diagonal: Optional[List[float]] = None
    if standard_error_state == "available" and sigma_squared is not None:
        # (X'X)^-1 from the SVD of X: V diag(1/s^2) V'.
        u, s, vt = np.linalg.svd(design, full_matrices=False)
        inverse = (vt.T * (1.0 / (s ** 2))) @ vt
        diagonal = np.diag(inverse)
        if not np.isfinite(diagonal).all() or float(np.min(diagonal)) < 0.0:
            standard_error_state = "unavailable"
            standard_error_note = (
                "the cross-product matrix could not be inverted stably, so "
                "standard errors are withheld")
        else:
            covariance_diagonal = [float(sigma_squared * d) for d in diagonal]

    t_critical: Optional[float] = None
    if covariance_diagonal is not None and dof >= MIN_DEGREES_OF_FREEDOM:
        t_critical = float(sp_stats.t.ppf(1.0 - (1.0 - confidence) / 2.0, dof))

    offset = 1 if intercept else 0
    coefficients: List[Dict[str, Any]] = []
    for j, name in enumerate(names):
        index = j + offset
        entry: Dict[str, Any] = {
            "factor_id": name,
            "coefficient": float(beta[index]),
            "standard_error": None,
            "t_statistic": None,
            "p_value": None,
            "confidence_lower": None,
            "confidence_upper": None,
            "unavailable_reason": standard_error_note,
        }
        if covariance_diagonal is not None:
            variance = covariance_diagonal[index]
            se = math.sqrt(variance) if variance > 0 else 0.0
            if se > 0.0 and math.isfinite(se):
                t_stat = float(beta[index] / se)
                entry.update({
                    "standard_error": float(se),
                    "t_statistic": t_stat,
                    "p_value": float(2.0 * sp_stats.t.sf(abs(t_stat), dof)),
                    "unavailable_reason": None,
                })
                if t_critical is not None:
                    entry["confidence_lower"] = float(beta[index]
                                                      - t_critical * se)
                    entry["confidence_upper"] = float(beta[index]
                                                      + t_critical * se)
            else:
                entry["unavailable_reason"] = (
                    "the estimated coefficient variance is zero, so no "
                    "t-statistic or p-value is defined")
        coefficients.append(entry)

    intercept_entry: Optional[Dict[str, Any]] = None
    if intercept:
        intercept_entry = {
            "factor_id": "__intercept__",
            "coefficient": float(beta[0]),
            "standard_error": None, "t_statistic": None, "p_value": None,
            "confidence_lower": None, "confidence_upper": None,
            "unavailable_reason": standard_error_note,
        }
        if covariance_diagonal is not None:
            variance = covariance_diagonal[0]
            se = math.sqrt(variance) if variance > 0 else 0.0
            if se > 0.0 and math.isfinite(se):
                t_stat = float(beta[0] / se)
                intercept_entry.update({
                    "standard_error": float(se),
                    "t_statistic": t_stat,
                    "p_value": float(2.0 * sp_stats.t.sf(abs(t_stat), dof)),
                    "unavailable_reason": None,
                })
                if t_critical is not None:
                    intercept_entry["confidence_lower"] = float(
                        beta[0] - t_critical * se)
                    intercept_entry["confidence_upper"] = float(
                        beta[0] + t_critical * se)

    return {
        "method": "ols",
        "intercept_policy": "include" if intercept else "exclude",
        "observations": int(n),
        "factors": int(k),
        "parameters": int(parameters),
        "degrees_of_freedom": dof,
        "intercept": intercept_entry,
        "coefficients": coefficients,
        "fitted": [float(v) for v in fitted],
        "residuals": [float(v) for v in residuals],
        "residual_sum_of_squares": rss,
        "total_sum_of_squares": tss,
        "r_squared": r_squared,
        "adjusted_r_squared": adjusted,
        "r_squared_note": r_squared_note,
        "root_mean_squared_error": rmse,
        "residual_mean": residual_mean,
        "residual_std": residual_std,
        "sigma_squared": sigma_squared,
        "rank": rank,
        "expected_rank": int(parameters),
        "rank_status": rank_status,
        "rank_policy": rank_policy,
        "standard_error_method": STANDARD_ERROR_METHOD,
        "standard_error_assumptions": STANDARD_ERROR_ASSUMPTIONS,
        "standard_error_state": standard_error_state,
        "standard_error_note": standard_error_note,
        "confidence_level": float(confidence),
        **cond,
        **columns,
    }


def ridge_fit(y_values: Sequence[float],
              factor_values: Sequence[Sequence[float]],
              names: Sequence[str], *,
              ridge_lambda: float,
              intercept: bool = True,
              scaling: str = "none") -> Dict[str, Any]:
    """Explicit ridge reference: regularised coefficients, no inference."""
    if scaling not in RIDGE_SCALINGS:
        raise RegressionError(f"ridge scaling must be one of {list(RIDGE_SCALINGS)}")
    lam = validate_ridge_lambda(ridge_lambda)
    y = _finite_array(y_values, "target series")
    factor_matrix = _finite_array(factor_values, "factor matrix")
    n, k = factor_matrix.shape
    if len(names) != k:
        raise RegressionError("factor names must match the factor columns")

    scale_centre = np.zeros(k)
    scale_spread = np.ones(k)
    if scaling == "zscore_fit_sample":
        scale_centre = factor_matrix.mean(axis=0)
        spread = factor_matrix.std(axis=0, ddof=1) if n >= 2 else np.ones(k)
        spread = np.where(spread > CONSTANT_TOLERANCE, spread, 1.0)
        scale_spread = spread
    scaled = (factor_matrix - scale_centre) / scale_spread

    design = _design(scaled, intercept)
    parameters = design.shape[1]
    penalty = np.eye(parameters) * lam
    if intercept:
        penalty[0, 0] = 0.0  # the intercept is never penalised
    gram = design.T @ design + penalty
    try:
        beta = np.linalg.solve(gram, design.T @ y)
    except np.linalg.LinAlgError as exc:  # pragma: no cover - lambda > 0 fixes
        raise RegressionError(
            f"the penalised system could not be solved: {exc}") from exc
    if not np.isfinite(beta).all():
        raise RegressionError("the ridge solution is not finite")

    fitted = design @ beta
    residuals = y - fitted
    rss = float(np.sum(residuals ** 2))
    tss = float(np.sum((y - y.mean()) ** 2))
    r_squared = (float(1.0 - rss / tss)
                 if tss > ZERO_VARIANCE_TOLERANCE else None)
    offset = 1 if intercept else 0

    # Report coefficients in the ORIGINAL factor units when scaling was used.
    coefficients: List[Dict[str, Any]] = []
    for j, name in enumerate(names):
        raw = float(beta[j + offset]) / float(scale_spread[j])
        coefficients.append({
            "factor_id": name,
            "coefficient": raw,
            "standard_error": None, "t_statistic": None, "p_value": None,
            "confidence_lower": None, "confidence_upper": None,
            "unavailable_reason": (
                "ridge coefficients are regularised (biased by construction); "
                "v1 publishes no standard error, t-statistic or p-value for "
                "them and no multiple-testing correction is applied"),
        })
    intercept_entry: Optional[Dict[str, Any]] = None
    if intercept:
        shift = float(np.sum([beta[j + offset] * scale_centre[j]
                              / scale_spread[j] for j in range(k)])) \
            if scaling == "zscore_fit_sample" else 0.0
        intercept_entry = {
            "factor_id": "__intercept__",
            "coefficient": float(beta[0]) - shift,
            "standard_error": None, "t_statistic": None, "p_value": None,
            "confidence_lower": None, "confidence_upper": None,
            "unavailable_reason": (
                "ridge intercept: no inferential statistics are published"),
        }

    cond = conditioning(factor_matrix)
    columns = column_diagnostics(factor_matrix, names)
    return {
        "method": "ridge",
        "intercept_policy": "include" if intercept else "exclude",
        "ridge_lambda": lam,
        "ridge_scaling": scaling,
        "observations": int(n),
        "factors": int(k),
        "parameters": int(parameters),
        "degrees_of_freedom": None,
        "intercept": intercept_entry,
        "coefficients": coefficients,
        "fitted": [float(v) for v in fitted],
        "residuals": [float(v) for v in residuals],
        "residual_sum_of_squares": rss,
        "total_sum_of_squares": tss,
        "r_squared": r_squared,
        "adjusted_r_squared": None,
        "r_squared_note": (
            "R-squared of a penalised fit is descriptive only: it is not "
            "comparable with an OLS R-squared and implies no predictive gain"),
        "root_mean_squared_error": float(math.sqrt(rss / n)) if n else None,
        "residual_mean": float(np.mean(residuals)),
        "residual_std": float(np.std(residuals, ddof=1)) if n >= 2 else None,
        "sigma_squared": None,
        "rank": None,
        "expected_rank": int(parameters),
        "rank_status": "full_rank" if cond["factor_rank"] == k
                       else "rank_deficient_descriptive",
        "rank_policy": "minimum_norm_descriptive",
        "standard_error_method": None,
        "standard_error_assumptions": None,
        "standard_error_state": "unavailable",
        "standard_error_note": (
            "no standard errors are defined for regularised coefficients in "
            "v1"),
        "confidence_level": None,
        **cond,
        **columns,
    }


def predict(factor_values: Sequence[Sequence[float]],
            coefficients: Sequence[float],
            intercept_value: Optional[float]) -> List[float]:
    """Apply FIXED coefficients to new rows (held-out evaluation)."""
    matrix = _finite_array(factor_values, "factor matrix")
    beta = np.asarray(coefficients, dtype=np.float64)
    if matrix.shape[1] != beta.shape[0]:
        raise RegressionError(
            "coefficient count does not match the factor columns")
    base = float(intercept_value or 0.0)
    return [float(base + float(row @ beta)) for row in matrix]


def out_of_sample_r_squared(actual: Sequence[float],
                            predicted: Sequence[float],
                            training_mean: float) -> Optional[float]:
    """Held-out R² against the TRAINING mean benchmark:

        1 - SUM (y_i - yhat_i)^2 / SUM (y_i - mean_train)^2

    Using the training mean (not the held-out mean) keeps the denominator
    free of held-out information; the value can be negative, and a negative
    value is reported as measured.
    """
    y = np.asarray(actual, dtype=np.float64)
    p = np.asarray(predicted, dtype=np.float64)
    if y.shape != p.shape or y.size == 0:
        return None
    denominator = float(np.sum((y - float(training_mean)) ** 2))
    if denominator <= ZERO_VARIANCE_TOLERANCE:
        return None
    return float(1.0 - float(np.sum((y - p) ** 2)) / denominator)


__all__ = [
    "MIN_DEGREES_OF_FREEDOM", "MAX_CONDITION_NUMBER_WARNING",
    "INTERCEPT_POLICIES", "RANK_POLICIES", "REGRESSION_METHODS",
    "RIDGE_SCALINGS", "MIN_RIDGE_LAMBDA", "MAX_RIDGE_LAMBDA",
    "STANDARD_ERROR_METHOD", "STANDARD_ERROR_METHODS",
    "STANDARD_ERROR_ASSUMPTIONS", "RANK_STATUSES", "RegressionError",
    "validate_confidence", "validate_ridge_lambda", "column_diagnostics",
    "conditioning", "ols_fit", "ridge_fit", "predict",
    "out_of_sample_r_squared",
]
