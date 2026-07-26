"""
Market-impact research approximation and participation diagnostics (v1).

Implemented ``square_root`` model (documented exactly):

    participation_side = traded_quantity_or_notional_side / ADV
    impact_fraction_side = impact_coefficient * volatility * sqrt(participation_side)
    impact_cost = sum over executed sides of impact_fraction_side * side_notional

* ``participation_mode`` is explicit: ``quantity`` divides contract/unit
  quantity by ADV in units; ``notional`` divides side notional by ADV in
  currency.  The ADV input's declared unit must match the mode — a mismatch
  is unavailable, never silently converted.
* Volatility is a per-period return fraction (e.g. 0.012 = 1.2%); the
  convention is recorded in the run configuration.
* Impact is a non-negative cost estimate by construction (coefficient >= 0,
  volatility >= 0, sqrt of a non-negative participation); the trade side
  never reverses its sign.  Zero participation gives zero impact.  Missing
  ADV / volume / volatility produces an unavailable status — never a silent
  zero.  ``none`` and ``fixed_bps`` alternatives are supported.

This model does not predict actual market impact; it is a bounded research
approximation consistent with the square-root form used by the
Microstructure Lab.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional

from app.cost_diagnostics.core import CostInputError
from app.cost_diagnostics.units import BASIS_POINT

IMPACT_MODELS = ("none", "fixed_bps", "square_root")
PARTICIPATION_MODES = ("quantity", "notional")
PARTICIPATION_STATUSES = ("within_configured_threshold", "above_configured_threshold",
                          "unavailable", "invalid")

MIN_PARTICIPATION_THRESHOLD = 0.001
MAX_PARTICIPATION_THRESHOLD = 10.0
DEFAULT_PARTICIPATION_THRESHOLD = 0.25
MAX_IMPACT_COEFFICIENT = 10.0

_NOT_CONFIGURED = {"status": "not_configured", "amount": None, "reason": None,
                   "participation": None}


def validate_impact_config(raw: Any, observation_type: str) -> Dict[str, Any]:
    if raw is not None and not isinstance(raw, dict):
        raise CostInputError("impact configuration must be an object")
    cfg = dict(raw or {"model": "none"})
    model = cfg.get("model", "none")
    if model not in IMPACT_MODELS:
        raise CostInputError(
            f"impact model must be one of {', '.join(IMPACT_MODELS)}")
    out: Dict[str, Any] = {"model": model}
    if model == "fixed_bps":
        v = cfg.get("value")
        try:
            fv = float(v) if v is not None and not isinstance(v, bool) else None
        except (TypeError, ValueError):
            fv = None
        if fv is None or not math.isfinite(fv) or fv < 0:
            raise CostInputError("impact fixed_bps requires a finite value >= 0")
        out["value"] = fv
    if model == "square_root":
        c = cfg.get("coefficient")
        try:
            cf = float(c) if c is not None and not isinstance(c, bool) else None
        except (TypeError, ValueError):
            cf = None
        if cf is None:
            raise CostInputError("square_root impact requires an explicit "
                                 "numeric impact coefficient")
        if not math.isfinite(cf) or not (0.0 <= cf <= MAX_IMPACT_COEFFICIENT):
            raise CostInputError(
                f"impact coefficient must be in [0, {MAX_IMPACT_COEFFICIENT:g}]")
        out["coefficient"] = cf
        mode = cfg.get("participation_mode")
        if observation_type == "period":
            if mode not in (None, "notional"):
                raise CostInputError(
                    "period observations support only notional participation")
            mode = "notional"
        if mode not in PARTICIPATION_MODES:
            raise CostInputError(
                "participation_mode must be 'quantity' or 'notional' "
                "(explicit, no default)")
        out["participation_mode"] = mode
    return out


def validate_participation_threshold(raw: Any) -> float:
    if raw is None:
        return DEFAULT_PARTICIPATION_THRESHOLD
    if isinstance(raw, bool):
        raise CostInputError("participation_threshold must be a number")
    try:
        t = float(raw)
    except (TypeError, ValueError):
        raise CostInputError("participation_threshold must be a number")
    if not math.isfinite(t) or not (
            MIN_PARTICIPATION_THRESHOLD <= t <= MAX_PARTICIPATION_THRESHOLD):
        raise CostInputError(
            "participation_threshold must be in "
            f"[{MIN_PARTICIPATION_THRESHOLD:g}, {MAX_PARTICIPATION_THRESHOLD:g}]")
    return t


def _adv_value(obs: Dict[str, Any], resolved_adv: Optional[float],
               required_unit: str, *,
               allow_supplied: bool = True) -> Optional[float]:
    """ADV for one observation.

    When a trailing derivation is configured (``allow_supplied=False``) an
    unresolved trailing value is honestly unavailable — it never silently
    falls back to a per-observation supplied input, whose provenance would
    bypass integrity classification.
    """
    if resolved_adv is not None and resolved_adv > 0:
        return resolved_adv
    if not allow_supplied:
        return None
    spec = obs.get("cost_inputs", {}).get("adv")
    if spec is None:
        spec = obs.get("cost_inputs", {}).get("volume")
    if spec is None:
        return None
    if spec.get("unit") != required_unit:
        return None  # unit mismatch is unavailable, never silently converted
    return spec["value"] if spec["value"] > 0 else None


def compute_impact(obs: Dict[str, Any], cfg: Dict[str, Any],
                   observation_type: str,
                   resolved_adv: Optional[float],
                   resolved_volatility: Optional[float],
                   *, allow_supplied_adv: bool = True,
                   allow_supplied_vol: bool = True) -> Dict[str, Any]:
    model = cfg.get("model", "none")
    if model == "none":
        return dict(_NOT_CONFIGURED)
    if model == "fixed_bps":
        if observation_type == "period":
            if obs.get("turnover") is None:
                return {"status": "unavailable", "amount": None,
                        "participation": None,
                        "reason": "impact on turnover requires turnover"}
            amount = cfg["value"] * BASIS_POINT * obs["turnover"]
        else:
            amount = cfg["value"] * BASIS_POINT * obs["traded_notional"]
        return {"status": "available", "amount": amount,
                "participation": None, "reason": None}

    # square_root
    coefficient = cfg["coefficient"]
    mode = cfg["participation_mode"]
    vol = resolved_volatility
    if vol is None and allow_supplied_vol:
        spec = obs.get("cost_inputs", {}).get("volatility")
        vol = spec["value"] if spec is not None else None
    if vol is None:
        reason = ("trailing volatility unavailable for this observation "
                  "(insufficient history or timestamp not in series)"
                  if not allow_supplied_vol
                  else "volatility input missing; impact not estimated")
        return {"status": "unavailable", "amount": None, "participation": None,
                "reason": reason}

    required_unit = "units" if mode == "quantity" else "currency"
    adv = _adv_value(obs, resolved_adv, required_unit,
                     allow_supplied=allow_supplied_adv)
    if adv is None:
        reason = ("trailing ADV unavailable for this observation "
                  "(insufficient history or timestamp not in series)"
                  if not allow_supplied_adv
                  else f"ADV/volume input in {required_unit!r} missing; "
                       "impact not estimated")
        return {"status": "unavailable", "amount": None, "participation": None,
                "reason": reason}

    if observation_type == "period":
        if obs.get("turnover") is None or obs.get("traded_notional") is None:
            return {"status": "unavailable", "amount": None, "participation": None,
                    "reason": "square-root impact on period observations "
                              "requires turnover and traded_notional"}
        participation = obs["traded_notional"] / adv
        fraction = coefficient * vol * math.sqrt(max(participation, 0.0))
        amount = fraction * obs["turnover"]
        return {"status": "available", "amount": amount,
                "participation": participation, "reason": None}

    sides = []
    for notional in (obs["entry_notional"], obs["exit_notional"]):
        if mode == "quantity":
            participation = obs["quantity"] / adv
        else:
            participation = notional / adv
        fraction = coefficient * vol * math.sqrt(max(participation, 0.0))
        sides.append((participation, fraction * notional))
    participation = max(p for p, _ in sides)
    amount = float(sum(c for _, c in sides))
    return {"status": "available", "amount": amount,
            "participation": participation, "reason": None}


def participation_record(obs: Dict[str, Any], observation_type: str,
                         resolved_adv: Optional[float], mode: Optional[str],
                         threshold: float, *,
                         allow_supplied_adv: bool = True) -> Dict[str, Any]:
    """Participation diagnostics for one observation (§ participation).

    The denominator must be positive; participation above 100% stays visible
    with a warning — nothing is auto-rejected or resized.
    """
    if mode is None:
        return {"participation": None, "status": "unavailable",
                "warning": None}
    required_unit = "units" if mode == "quantity" else "currency"
    adv = _adv_value(obs, resolved_adv, required_unit,
                     allow_supplied=allow_supplied_adv)
    if adv is None or adv <= 0:
        return {"participation": None, "status": "unavailable", "warning": None}
    if observation_type == "period":
        if obs.get("traded_notional") is None:
            return {"participation": None, "status": "unavailable", "warning": None}
        participation = obs["traded_notional"] / adv
    elif mode == "quantity":
        participation = obs["quantity"] / adv
    else:
        participation = max(obs["entry_notional"], obs["exit_notional"]) / adv
    if not math.isfinite(participation) or participation < 0:
        return {"participation": None, "status": "invalid", "warning": None}
    status = ("above_configured_threshold" if participation > threshold
              else "within_configured_threshold")
    warning = None
    if participation > 1.0:
        warning = ("participation above 100% of the configured volume "
                   "denominator")
    return {"participation": participation, "status": status, "warning": warning}
