"""
Exposure aggregation, return decomposition and reconciliation (v1).

Two analysis modes ship in v1:

``time_series_regression``
    The exposure of the target to factor k is the ESTIMATED coefficient
    beta_k, constant over the estimation sample.  Period contributions are

        factor_contribution_k,t = beta_k * f_k,t
        modelled_return_t       = intercept + SUM_k factor_contribution_k,t
        residual_t              = measured_t - modelled_return_t

    which reconciles exactly by construction of the least-squares residual.
    The reconciliation column proves that identity numerically instead of
    assuming it.

``supplied_exposure_aggregation``
    Asset-level exposures are SUPPLIED, never inferred, and aggregated with
    the beginning-of-period weights of a stored Phase 56 book:

        portfolio_exposure_k,t = SUM_i weight_i,t * asset_exposure_i,k
        factor_contribution_k,t = portfolio_exposure_k,t * factor_return_k,t
        modelled_return_t       = SUM_k factor_contribution_k,t
        residual_t              = measured_t - modelled_return_t

    A missing asset exposure leaves that factor's contribution UNAVAILABLE
    for that period — it is never treated as a zero exposure.  Weights are
    used exactly as the book holds them: nothing is normalised, and long or
    short weights both aggregate under the same signed formula.

``cross_sectional_decomposition`` is DEFERRED in v1 — see
``DEFERRED_MODES``.  No stored record in the repository holds per-period
asset exposures with aligned per-period asset returns, and a
cross-sectional factor-return estimate built from anything less would be a
placeholder.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.factor_diagnostics.definitions import contribution_scale

ANALYSIS_MODES = ("time_series_regression", "supplied_exposure_aggregation")

DEFERRED_MODES = {
    "cross_sectional_decomposition": (
        "DEFERRED in v1: a cross-sectional factor-return estimate needs "
        "per-period asset exposures aligned with per-period asset returns. "
        "No stored QuantLab record holds that pair (Phase 58 stores per-asset "
        "contributions aggregated over the window), and estimating factor "
        "returns from anything less would be a placeholder rather than a "
        "measurement."),
}

MIN_TOLERANCE = 1e-12
MAX_TOLERANCE = 1e-2
DEFAULT_TOLERANCE = 1e-9

EXPOSURE_STATES = ("supplied", "estimated", "unavailable")
RECONCILIATION_STATES = ("reconciled", "mismatch", "unavailable")


class DecompositionError(ValueError):
    """Invalid exposure input or decomposition request (HTTP 422)."""


def validate_mode(value: Any) -> str:
    if value in DEFERRED_MODES:
        raise DecompositionError(DEFERRED_MODES[value])
    if value not in ANALYSIS_MODES:
        raise DecompositionError(
            f"analysis_mode must be one of {list(ANALYSIS_MODES)}")
    return value


def validate_tolerance(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) \
            or not math.isfinite(float(value)) \
            or not (MIN_TOLERANCE <= float(value) <= MAX_TOLERANCE):
        raise DecompositionError(
            f"reconciliation_tolerance must be a finite number in "
            f"[{MIN_TOLERANCE}, {MAX_TOLERANCE}]")
    return float(value)


def validate_asset_exposures(raw: Any, *, factor_ids: Sequence[str]
                             ) -> Dict[str, Dict[str, float]]:
    """Supplied asset-level exposures: {asset_id: {factor_id: exposure}}.

    Exposures are dimensionless loadings.  A factor missing for an asset is
    kept missing; it is never defaulted to zero.
    """
    if not isinstance(raw, dict) or not raw:
        raise DecompositionError(
            "supplied_exposure_aggregation requires an asset_exposures object "
            "{asset_id: {factor_id: exposure}}")
    if len(raw) > 40:
        raise DecompositionError("at most 40 assets are supported")
    out: Dict[str, Dict[str, float]] = {}
    for asset_id, values in raw.items():
        if not isinstance(asset_id, str) or not asset_id:
            raise DecompositionError("asset ids must be non-empty strings")
        if not isinstance(values, dict):
            raise DecompositionError(
                f"exposures for asset '{asset_id}' must be an object")
        unknown = sorted(set(values) - set(factor_ids))
        if unknown:
            raise DecompositionError(
                f"asset '{asset_id}' declares exposures to unknown factors: "
                f"{unknown}")
        entry: Dict[str, float] = {}
        for factor_id, value in values.items():
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)) \
                    or not math.isfinite(float(value)):
                raise DecompositionError(
                    f"exposure of '{asset_id}' to '{factor_id}' must be a "
                    f"finite number")
            if abs(float(value)) > 100.0:
                raise DecompositionError(
                    f"exposure of '{asset_id}' to '{factor_id}' exceeds the "
                    f"supported magnitude of 100")
            entry[factor_id] = float(value)
        out[asset_id] = entry
    return out


def aggregate_exposures(weights_by_period: Sequence[Optional[Dict[str, float]]],
                        asset_exposures: Dict[str, Dict[str, float]],
                        factor_ids: Sequence[str]) -> List[Dict[str, Any]]:
    """portfolio_exposure_k,t = SUM_i weight_i,t * asset_exposure_i,k."""
    rows: List[Dict[str, Any]] = []
    for index, weights in enumerate(weights_by_period):
        entry: Dict[str, Any] = {
            "period_index": index, "exposures": {}, "states": {},
            "missing_assets": {},
        }
        for factor_id in factor_ids:
            if weights is None:
                entry["exposures"][factor_id] = None
                entry["states"][factor_id] = "unavailable"
                entry["missing_assets"][factor_id] = []
                continue
            total = 0.0
            missing: List[str] = []
            for asset_id, weight in weights.items():
                exposure = asset_exposures.get(asset_id, {}).get(factor_id)
                if exposure is None:
                    if abs(weight) > 0.0:
                        missing.append(asset_id)
                    continue
                total += float(weight) * float(exposure)
            if missing:
                entry["exposures"][factor_id] = None
                entry["states"][factor_id] = "unavailable"
            else:
                entry["exposures"][factor_id] = float(total)
                entry["states"][factor_id] = "supplied"
            entry["missing_assets"][factor_id] = missing
        rows.append(entry)
    return rows


def _scaled_factor_value(value: float, transformed_unit: str) -> Optional[float]:
    scale = contribution_scale(transformed_unit)
    if scale is None:
        return None
    return float(value) * scale


def regression_period_rows(design_rows: Sequence[Dict[str, Any]],
                           fit: Dict[str, Any],
                           factor_ids: Sequence[str],
                           tolerance: float, *,
                           fit_residuals: Optional[Sequence[float]] = None
                           ) -> List[Dict[str, Any]]:
    """Per-period decomposition under an estimated (constant) exposure.

    ``residual_t = measured_t - modelled_t`` by definition, so the identity
    closes exactly.  When the estimator's own residual vector covers the
    same rows (a full-sample fit), it is compared against the decomposition
    row by row — an independent numerical proof that the reported
    contributions really are the least-squares fit and that nothing was
    redistributed.  Under a training-only fit the estimator's residuals
    cover the training rows only, so that cross-check is skipped rather
    than mis-aligned.
    """
    betas = {c["factor_id"]: float(c["coefficient"])
             for c in fit["coefficients"]}
    intercept = (float(fit["intercept"]["coefficient"])
                 if fit.get("intercept") else 0.0)
    residual_check = (list(fit_residuals)
                      if fit_residuals is not None
                      and len(fit_residuals) == len(design_rows) else None)
    rows: List[Dict[str, Any]] = []
    for position, design in enumerate(design_rows):
        measured = float(design["target_return"])
        contributions: Dict[str, Optional[float]] = {}
        modelled = intercept
        for index, factor_id in enumerate(factor_ids):
            value = float(design["factor_values"][index])
            contribution = betas[factor_id] * value
            contributions[factor_id] = float(contribution)
            modelled += contribution
        residual = measured - modelled
        difference = measured - (modelled + residual)
        if residual_check is not None:
            difference = residual - float(residual_check[position])
        rows.append({
            "period_index": design["period_index"],
            "period_start": design["period_start"],
            "period_end": design["period_end"],
            "information_available_at": design["information_available_at"],
            "measured_return": measured,
            "intercept_contribution": float(intercept),
            "factor_contributions": contributions,
            "factor_values": {factor_id: float(design["factor_values"][i])
                              for i, factor_id in enumerate(factor_ids)},
            "exposures": {factor_id: betas[factor_id]
                          for factor_id in factor_ids},
            "exposure_state": "estimated",
            "modelled_return": float(modelled),
            "residual": float(residual),
            "least_squares_residual": (None if residual_check is None
                                       else float(residual_check[position])),
            "reconciliation_difference": float(difference),
            "reconciliation_state": ("reconciled" if abs(difference) <= tolerance
                                     else "mismatch"),
        })
    return rows


def supplied_period_rows(design_rows: Sequence[Dict[str, Any]],
                         exposure_rows: Sequence[Dict[str, Any]],
                         definitions: Sequence[Dict[str, Any]],
                         tolerance: float) -> Tuple[List[Dict[str, Any]],
                                                    List[str]]:
    """Per-period decomposition under supplied, aggregated exposures."""
    warnings: List[str] = []
    units = {d["factor_id"]: d["transformed_unit"] for d in definitions}
    non_return = sorted({fid for fid, unit in units.items()
                         if contribution_scale(unit) is None})
    if non_return:
        raise DecompositionError(
            f"supplied_exposure_aggregation multiplies an exposure by a factor "
            f"RETURN, so every factor must carry a return-like unit "
            f"(return_fraction, return_percent or basis_points). These do not: "
            f"{non_return}")
    exposures_by_period = {row["period_index"]: row for row in exposure_rows}
    rows: List[Dict[str, Any]] = []
    unavailable_periods = 0
    for design in design_rows:
        measured = float(design["target_return"])
        exposure_row = exposures_by_period.get(design["period_index"])
        contributions: Dict[str, Optional[float]] = {}
        exposures: Dict[str, Optional[float]] = {}
        modelled: Optional[float] = 0.0
        state = "supplied"
        for index, definition in enumerate(definitions):
            factor_id = definition["factor_id"]
            exposure = (exposure_row or {}).get("exposures", {}).get(factor_id)
            exposures[factor_id] = exposure
            raw_value = float(design["factor_values"][index])
            scaled = _scaled_factor_value(raw_value, units[factor_id])
            if exposure is None or scaled is None:
                contributions[factor_id] = None
                modelled = None
                state = "unavailable"
                continue
            contribution = float(exposure) * float(scaled)
            contributions[factor_id] = contribution
            if modelled is not None:
                modelled += contribution
        if modelled is None:
            unavailable_periods += 1
            rows.append({
                "period_index": design["period_index"],
                "period_start": design["period_start"],
                "period_end": design["period_end"],
                "information_available_at": design["information_available_at"],
                "measured_return": measured,
                "intercept_contribution": None,
                "factor_contributions": contributions,
                "factor_values": {d["factor_id"]:
                                  float(design["factor_values"][i])
                                  for i, d in enumerate(definitions)},
                "exposures": exposures,
                "exposure_state": "unavailable",
                "modelled_return": None,
                "residual": None,
                "reconciliation_difference": None,
                "reconciliation_state": "unavailable",
            })
            continue
        residual = measured - modelled
        difference = measured - (modelled + residual)
        rows.append({
            "period_index": design["period_index"],
            "period_start": design["period_start"],
            "period_end": design["period_end"],
            "information_available_at": design["information_available_at"],
            "measured_return": measured,
            "intercept_contribution": 0.0,
            "factor_contributions": contributions,
            "factor_values": {d["factor_id"]: float(design["factor_values"][i])
                              for i, d in enumerate(definitions)},
            "exposures": exposures,
            "exposure_state": state,
            "modelled_return": float(modelled),
            "residual": float(residual),
            "reconciliation_difference": float(difference),
            "reconciliation_state": ("reconciled" if abs(difference) <= tolerance
                                     else "mismatch"),
        })
    if unavailable_periods:
        warnings.append(
            f"{unavailable_periods} period(s) have no modelled return because "
            f"at least one asset exposure is missing; the gap is reported "
            f"rather than filled with a zero exposure.")
    return rows, warnings


def summarise_periods(period_rows: Sequence[Dict[str, Any]],
                      factor_ids: Sequence[str],
                      tolerance: float) -> Dict[str, Any]:
    """Window totals: measured, intercept, per-factor, residual, difference."""
    measured = 0.0
    intercept_total = 0.0
    residual_total = 0.0
    modelled_total = 0.0
    counted = 0
    unavailable = 0
    totals: Dict[str, Optional[float]] = {fid: 0.0 for fid in factor_ids}
    for row in period_rows:
        if row["modelled_return"] is None:
            unavailable += 1
            continue
        counted += 1
        measured += row["measured_return"]
        intercept_total += float(row["intercept_contribution"] or 0.0)
        modelled_total += row["modelled_return"]
        residual_total += float(row["residual"] or 0.0)
        for fid in factor_ids:
            value = row["factor_contributions"].get(fid)
            if value is None or totals[fid] is None:
                totals[fid] = None
            else:
                totals[fid] = float(totals[fid]) + float(value)
    difference = measured - (modelled_total + residual_total)
    state = "unavailable" if counted == 0 else (
        "reconciled" if abs(difference) <= tolerance * max(1, counted)
        else "mismatch")
    return {
        "periods_decomposed": counted,
        "periods_unavailable": unavailable,
        "measured_return_sum": float(measured) if counted else None,
        "intercept_contribution_sum": float(intercept_total) if counted else None,
        "factor_contribution_sums": totals,
        "modelled_return_sum": float(modelled_total) if counted else None,
        "residual_sum": float(residual_total) if counted else None,
        "reconciliation_difference": float(difference) if counted else None,
        "reconciliation_state": state,
        "convention": (
            "arithmetic period sums: contributions are added across periods "
            "and are NOT compounded, so the sums do not equal a compounded "
            "return over the window"),
    }


def benchmark_comparison(portfolio: Dict[str, Optional[float]],
                         benchmark: Dict[str, Optional[float]],
                         factor_ids: Sequence[str],
                         *, portfolio_contributions: Dict[str, Optional[float]],
                         benchmark_contributions: Dict[str, Optional[float]]
                         ) -> List[Dict[str, Any]]:
    """active_exposure_k = portfolio_exposure_k - benchmark_exposure_k."""
    rows: List[Dict[str, Any]] = []
    for factor_id in factor_ids:
        p_exposure = portfolio.get(factor_id)
        b_exposure = benchmark.get(factor_id)
        p_contribution = portfolio_contributions.get(factor_id)
        b_contribution = benchmark_contributions.get(factor_id)
        active_exposure = (None if p_exposure is None or b_exposure is None
                           else float(p_exposure) - float(b_exposure))
        active_contribution = (
            None if p_contribution is None or b_contribution is None
            else float(p_contribution) - float(b_contribution))
        rows.append({
            "factor_id": factor_id,
            "portfolio_exposure": (None if p_exposure is None
                                   else float(p_exposure)),
            "benchmark_exposure": (None if b_exposure is None
                                   else float(b_exposure)),
            "active_exposure": active_exposure,
            "portfolio_contribution": (None if p_contribution is None
                                       else float(p_contribution)),
            "benchmark_contribution": (None if b_contribution is None
                                       else float(b_contribution)),
            "active_contribution": active_contribution,
            "note": ("an active exposure is a measured difference; it is "
                     "neither desirable nor undesirable here"),
        })
    return rows


__all__ = [
    "ANALYSIS_MODES", "DEFERRED_MODES", "MIN_TOLERANCE", "MAX_TOLERANCE",
    "DEFAULT_TOLERANCE", "EXPOSURE_STATES", "RECONCILIATION_STATES",
    "DecompositionError", "validate_mode", "validate_tolerance",
    "validate_asset_exposures", "aggregate_exposures",
    "regression_period_rows", "supplied_period_rows", "summarise_periods",
    "benchmark_comparison",
]
