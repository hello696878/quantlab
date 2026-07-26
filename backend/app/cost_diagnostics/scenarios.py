"""
Cost-sensitivity grid and capacity scaling (v1).

Sensitivity: a bounded deterministic grid of component multipliers
(commission / spread / slippage / impact).  Multipliers scale the computed
base component amounts; for the square-root impact model this is exactly a
coefficient multiplier because the model is linear in its coefficient.
Duplicate scenarios are removed, ordering is deterministic, the base
scenario (all multipliers 1) is always present and marked, and no scenario
is ever labelled optimal or automatically selected.

Capacity: bounded notional/capital scale factors applied to observation
size, never to historical prices.  Fixed fees remain fixed, per-unit fees
scale with quantity, notional-proportional costs scale with notional and
square-root impact responds superlinearly through participation.  Results
are estimates under configured assumptions — not executable capacity, and
no assumption is made that fills remain available at scale.
"""

from __future__ import annotations

import math
from itertools import product
from typing import Any, Dict, List, Optional, Tuple

from app.cost_diagnostics.core import CostInputError
from app.cost_diagnostics.reconcile import COMPONENT_NAMES

MAX_MULTIPLIERS_PER_COMPONENT = 5
MAX_SCENARIOS = 60
MIN_MULTIPLIER = 0.0
MAX_MULTIPLIER = 100.0

MAX_CAPACITY_SCALES = 8
MIN_CAPACITY_SCALE = 0.001
MAX_CAPACITY_SCALE = 100.0
DEFAULT_CAPACITY_SCALES = (0.25, 0.5, 1.0, 2.0, 5.0)

_GRID_KEYS = ("commission_multipliers", "spread_multipliers",
              "slippage_multipliers", "impact_multipliers")


def _clean_multipliers(raw: Any, field: str) -> List[float]:
    if raw is None:
        return [1.0]
    if not isinstance(raw, list) or not raw:
        raise CostInputError(f"{field} must be a non-empty list of numbers")
    if len(raw) > MAX_MULTIPLIERS_PER_COMPONENT:
        raise CostInputError(
            f"{field} supports at most {MAX_MULTIPLIERS_PER_COMPONENT} values")
    out = []
    for v in raw:
        if isinstance(v, bool):
            raise CostInputError(f"{field} entries must be numbers")
        try:
            f = float(v)
        except (TypeError, ValueError):
            raise CostInputError(f"{field} entries must be numbers")
        if not math.isfinite(f) or not (MIN_MULTIPLIER <= f <= MAX_MULTIPLIER):
            raise CostInputError(
                f"{field} entries must be in [{MIN_MULTIPLIER:g}, "
                f"{MAX_MULTIPLIER:g}]")
        out.append(f)
    return sorted(set(out))


def validate_sensitivity_grid(raw: Any) -> Dict[str, List[float]]:
    cfg = dict(raw or {})
    unknown = set(cfg) - set(_GRID_KEYS)
    if unknown:
        raise CostInputError(
            f"unsupported sensitivity grid keys: {', '.join(sorted(unknown))}")
    grid = {k: _clean_multipliers(cfg.get(k), k) for k in _GRID_KEYS}
    count = 1
    for v in grid.values():
        count *= len(v)
    # the base scenario is injected if absent, so allow for one extra row
    if count + 1 > MAX_SCENARIOS + 1:
        raise CostInputError(
            f"sensitivity grid produces {count} scenarios; at most "
            f"{MAX_SCENARIOS} are supported")
    return grid


def build_scenarios(grid: Dict[str, List[float]]) -> List[Dict[str, float]]:
    """Deterministic, de-duplicated scenario list with the base marked."""
    combos = sorted(set(product(grid["commission_multipliers"],
                                grid["spread_multipliers"],
                                grid["slippage_multipliers"],
                                grid["impact_multipliers"])))
    base = (1.0, 1.0, 1.0, 1.0)
    if base not in combos:
        combos = sorted(set(combos) | {base})
    return [{
        "commission_multiplier": c, "spread_multiplier": s,
        "slippage_multiplier": sl, "impact_multiplier": i,
        "is_base": (c, s, sl, i) == base,
    } for c, s, sl, i in combos]


def evaluate_scenario(obs_results: List[Dict[str, Any]],
                      scenario: Dict[str, float]) -> Dict[str, Any]:
    """Evaluate one multiplier scenario over base per-observation results.

    Unavailable components stay unavailable — a multiplier never fabricates
    a missing input, so incomplete-input counts are unchanged by design.
    Supplied realized slippage is a historical fact, not a modelled
    assumption: the slippage multiplier is pinned to 1 for observations
    whose slippage source is ``supplied_realized`` (scaling a favourable
    realized fill would fabricate favourable slippage).
    """
    mults = {"commission": scenario["commission_multiplier"],
             "spread": scenario["spread_multiplier"],
             "slippage": scenario["slippage_multiplier"],
             "impact": scenario["impact_multiplier"]}
    total_cost = 0.0
    net_values: List[float] = []
    gp_nn = 0
    any_cost = False
    for r in obs_results:
        comp = r["component_values"]
        available = {n: v for n, v in comp.items() if v is not None}
        if not available:
            continue
        any_cost = True
        realized_slippage = r.get("slippage_source") == "supplied_realized"
        cost = sum(
            v * (1.0 if n == "slippage" and realized_slippage else mults[n])
            for n, v in available.items())
        total_cost += cost
        net = r["gross_value"] - cost
        net_values.append(net)
        if r["gross_value"] > 0 and net <= 0:
            gp_nn += 1
    n_net = len(net_values)
    return {
        **{k: scenario[k] for k in ("commission_multiplier", "spread_multiplier",
                                    "slippage_multiplier", "impact_multiplier")},
        "is_base": scenario["is_base"],
        "total_cost": total_cost if any_cost else None,
        "net_total": float(sum(net_values)) if net_values else None,
        "net_positive_rate": (float(sum(1 for v in net_values if v > 0) / n_net)
                              if n_net else None),
        "gross_positive_net_nonpositive_count": gp_nn,
        "unavailable_cost_count": sum(
            1 for r in obs_results if r.get("unavailable_components")),
    }


def validate_capacity_scales(raw: Any) -> List[float]:
    if raw is None:
        return list(DEFAULT_CAPACITY_SCALES)
    if not isinstance(raw, list) or not raw:
        raise CostInputError("capacity scales must be a non-empty list")
    if len(raw) > MAX_CAPACITY_SCALES:
        raise CostInputError(
            f"at most {MAX_CAPACITY_SCALES} capacity scales are supported")
    out = []
    for v in raw:
        if isinstance(v, bool):
            raise CostInputError("capacity scales must be numbers")
        try:
            f = float(v)
        except (TypeError, ValueError):
            raise CostInputError("capacity scales must be numbers")
        if not math.isfinite(f) or not (MIN_CAPACITY_SCALE <= f <= MAX_CAPACITY_SCALE):
            raise CostInputError(
                f"capacity scales must be in [{MIN_CAPACITY_SCALE:g}, "
                f"{MAX_CAPACITY_SCALE:g}]")
        out.append(f)
    scales = sorted(set(out))
    if 1.0 not in scales:
        scales = sorted(set(scales) | {1.0})
    if len(scales) > MAX_CAPACITY_SCALES + 1:
        raise CostInputError(
            f"at most {MAX_CAPACITY_SCALES} capacity scales are supported")
    return scales


def scale_observation(obs: Dict[str, Any], scale: float, observation_type: str,
                      integer_contracts: bool
                      ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Scale one observation's size (never its historical prices).

    Returns ``(scaled_obs, exclusion_reason)``.  With ``integer_contracts``
    the scaled quantity is floored to a whole number of contracts; a floor of
    zero excludes the observation at that scale (reported, never silently
    dropped).  Gross results scale proportionally with size under the
    documented assumption that the historical per-unit result is unchanged.
    """
    scaled = dict(obs)
    if observation_type == "period":
        for key in ("turnover", "traded_notional"):
            if obs.get(key) is not None:
                scaled[key] = obs[key] * scale
        scaled["gross_return"] = obs["gross_return"] * scale
        scaled["gross_value"] = scaled["gross_return"]
        return scaled, None
    q = obs["quantity"] * scale
    if integer_contracts:
        q = float(math.floor(q))
        if q < 1.0:
            return None, ("integer contract policy: scaled quantity below "
                          "one contract")
    ratio = q / obs["quantity"]
    scaled["quantity"] = q
    scaled["entry_notional"] = obs["entry_price"] * q * obs["contract_multiplier"]
    scaled["exit_notional"] = obs["exit_price"] * q * obs["contract_multiplier"]
    scaled["traded_notional"] = scaled["entry_notional"] + scaled["exit_notional"]
    scaled["gross_pnl"] = obs["gross_pnl"] * ratio
    scaled["gross_value"] = scaled["gross_pnl"]
    return scaled, None
