"""
Bounded deterministic sensitivity scenarios (v1).

One-at-a-time variations around the base configuration (documented — no
cross-product grid in v1): each dimension carries an explicit bounded
value list, scenarios are deduplicated and deterministically ordered by
(dimension, value), and the base scenario appears exactly once.  No
scenario is ever selected, preferred, or marked optimal.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List

from app.portfolio_diagnostics.core import PortfolioInputError

# cost_notional_scale is deliberately NOT a v1 dimension: every cost
# component applicable to weight turnover is notional-invariant in return
# space, so the scenario could never produce an observable difference —
# a vacuous dimension would misleadingly suggest measured insensitivity.
SENSITIVITY_DIMENSIONS = ("lookback", "shrinkage_alpha", "max_weight",
                          "correlation_multiplier", "volatility_multiplier")
MAX_VALUES_PER_DIMENSION = 5
MAX_SCENARIOS = 40

_BOUNDS = {
    "lookback": (3, 500, int),
    "shrinkage_alpha": (0.0, 1.0, float),
    "max_weight": (0.0, 5.0, float),
    "correlation_multiplier": (0.0, 2.0, float),
    "volatility_multiplier": (0.01, 10.0, float),
}


def validate_sensitivity_config(raw: Any) -> Dict[str, List[float]]:
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise PortfolioInputError("sensitivity configuration must be an object")
    cfg = dict(raw)
    unknown = set(cfg) - set(SENSITIVITY_DIMENSIONS)
    if unknown:
        raise PortfolioInputError(
            f"unsupported sensitivity dimensions: {', '.join(sorted(unknown))}")
    out: Dict[str, List[float]] = {}
    total = 0
    for dim, values in cfg.items():
        if not isinstance(values, list) or not values:
            raise PortfolioInputError(f"{dim} must be a non-empty list")
        if len(values) > MAX_VALUES_PER_DIMENSION:
            raise PortfolioInputError(
                f"{dim} supports at most {MAX_VALUES_PER_DIMENSION} values")
        lo, hi, kind = _BOUNDS[dim]
        clean = []
        for v in values:
            if isinstance(v, bool):
                raise PortfolioInputError(f"{dim} values must be numbers")
            if kind is int:
                if not isinstance(v, int) or not (lo <= v <= hi):
                    raise PortfolioInputError(
                        f"{dim} values must be integers in [{lo}, {hi}]")
                clean.append(v)
            else:
                try:
                    f = float(v)
                except (TypeError, ValueError):
                    raise PortfolioInputError(f"{dim} values must be numbers")
                if not math.isfinite(f) or not (lo <= f <= hi):
                    raise PortfolioInputError(
                        f"{dim} values must be in [{lo:g}, {hi:g}]")
                clean.append(f)
        out[dim] = sorted(set(clean))
        total += len(out[dim])
    if total + 1 > MAX_SCENARIOS:
        raise PortfolioInputError(
            f"sensitivity produces {total + 1} scenarios; at most "
            f"{MAX_SCENARIOS} are supported")
    return out


def build_scenarios(config: Dict[str, List[float]]) -> List[Dict[str, Any]]:
    """Base scenario first, then one-at-a-time variations, deterministic."""
    scenarios: List[Dict[str, Any]] = [
        {"dimension": "base", "value": None, "is_base": True}]
    for dim in sorted(config):
        for v in config[dim]:
            scenarios.append({"dimension": dim, "value": v, "is_base": False})
    return scenarios
