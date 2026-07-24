"""
Constraint model (v1).

All constraint units are portfolio-weight fractions (1.0 = 100% of the
portfolio).  Checked feasibility BEFORE optimization where possible;
infeasible configurations are rejected with explicit reasons; solver
output is ALWAYS re-checked independently after the solve with the
documented tolerance — there is no silent relaxation and no automatic
removal of constraints.  ``max_active_assets`` is a validation-only check
(never a cardinality optimizer), and gross exposure doubles as the v1
leverage bound (documented).
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

CONSTRAINT_TOLERANCE = 1e-6
MAX_GROSS_EXPOSURE = 5.0
MAX_TURNOVER_CAP = 2.0


class ConstraintError(ValueError):
    """Raised for invalid or infeasible constraint configuration."""


def _num(cfg: Dict[str, Any], field: str, default=None,
         lo=None, hi=None) -> Optional[float]:
    v = cfg.get(field, default)
    if v is None:
        return None
    if isinstance(v, bool):
        raise ConstraintError(f"{field} must be a number")
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise ConstraintError(f"{field} must be a number")
    if not math.isfinite(f):
        raise ConstraintError(f"{field} must be finite")
    if lo is not None and f < lo:
        raise ConstraintError(f"{field} must be >= {lo:g}")
    if hi is not None and f > hi:
        raise ConstraintError(f"{field} must be <= {hi:g}")
    return f


def validate_constraints(raw: Any, assets: List[Dict[str, Any]]) -> Dict[str, Any]:
    cfg = dict(raw or {})
    if not isinstance(cfg, dict):
        raise ConstraintError("constraints must be an object")
    out: Dict[str, Any] = {
        "long_only": bool(cfg.get("long_only", True)),
        "tolerance": CONSTRAINT_TOLERANCE,
        "units": "portfolio-weight fractions (1.0 = 100%)",
    }
    min_w = _num(cfg, "min_weight", 0.0 if out["long_only"] else -1.0,
                 lo=-MAX_GROSS_EXPOSURE, hi=MAX_GROSS_EXPOSURE)
    max_w = _num(cfg, "max_weight", 1.0, lo=-MAX_GROSS_EXPOSURE,
                 hi=MAX_GROSS_EXPOSURE)
    if min_w > max_w:
        raise ConstraintError("min_weight must be <= max_weight")
    if out["long_only"] and min_w < 0:
        raise ConstraintError("long_only portfolios require min_weight >= 0")
    out["min_weight"], out["max_weight"] = min_w, max_w
    out["gross_exposure_limit"] = _num(cfg, "gross_exposure_limit", None,
                                       lo=0.0, hi=MAX_GROSS_EXPOSURE)
    out["net_exposure_target"] = _num(cfg, "net_exposure_target", None,
                                      lo=-MAX_GROSS_EXPOSURE,
                                      hi=MAX_GROSS_EXPOSURE)
    out["turnover_cap"] = _num(cfg, "turnover_cap", None, lo=0.0,
                               hi=MAX_TURNOVER_CAP)
    out["cash_residual_allowed"] = bool(cfg.get("cash_residual_allowed", False))

    known = {a["asset_id"] for a in assets}
    groups_present: Dict[str, int] = {}
    for a in assets:
        if a.get("group"):
            groups_present[a["group"]] = groups_present.get(a["group"], 0) + 1

    group_caps: Dict[str, float] = {}
    for g, cap in dict(cfg.get("group_caps") or {}).items():
        if g not in groups_present:
            raise ConstraintError(f"group cap references unknown group {g!r}")
        group_caps[g] = _num({"cap": cap}, "cap", lo=0.0, hi=MAX_GROSS_EXPOSURE)
    out["group_caps"] = group_caps
    group_minimums: Dict[str, float] = {}
    for g, mn in dict(cfg.get("group_minimums") or {}).items():
        if g not in groups_present:
            raise ConstraintError(f"group minimum references unknown group {g!r}")
        group_minimums[g] = _num({"min": mn}, "min", lo=0.0, hi=MAX_GROSS_EXPOSURE)
        if g in group_caps and group_minimums[g] > group_caps[g]:
            raise ConstraintError(
                f"group {g!r}: minimum exceeds its cap (lower bound must be "
                "<= upper bound)")
    out["group_minimums"] = group_minimums

    excluded = list(cfg.get("excluded_assets") or [])
    for asset_id in excluded:
        if asset_id not in known:
            raise ConstraintError(f"excluded asset {asset_id!r} is unknown")
    out["excluded_assets"] = sorted(set(excluded))

    frozen: Dict[str, float] = {}
    for asset_id, w in dict(cfg.get("frozen_weights") or {}).items():
        if asset_id not in known:
            raise ConstraintError(f"frozen asset {asset_id!r} is unknown")
        if asset_id in out["excluded_assets"]:
            raise ConstraintError(
                f"asset {asset_id!r} cannot be both frozen and excluded")
        fw = _num({"w": w}, "w", lo=-MAX_GROSS_EXPOSURE, hi=MAX_GROSS_EXPOSURE)
        if not (min_w - CONSTRAINT_TOLERANCE <= fw <= max_w + CONSTRAINT_TOLERANCE):
            raise ConstraintError(
                f"frozen weight for {asset_id!r} violates the weight bounds")
        frozen[asset_id] = fw
    out["frozen_weights"] = frozen

    max_active = cfg.get("max_active_assets")
    if max_active is not None:
        if isinstance(max_active, bool) or not isinstance(max_active, int) \
                or max_active < 1:
            raise ConstraintError("max_active_assets must be a positive integer")
        out["max_active_assets"] = max_active
    else:
        out["max_active_assets"] = None

    # ---- feasibility pre-checks (documented; infeasible => explicit) ----
    eligible = [a for a in assets if a["asset_id"] not in out["excluded_assets"]]
    n_eligible = len(eligible)
    if n_eligible < 1:
        raise ConstraintError("all assets are excluded; nothing to construct")
    target_sum = out["net_exposure_target"]
    if target_sum is None:
        target_sum = 1.0
    if out["long_only"]:
        frozen_sum = sum(frozen.values())
        free = [a for a in eligible if a["asset_id"] not in frozen]
        if len(free) * max_w + frozen_sum < target_sum - CONSTRAINT_TOLERANCE \
                and not out["cash_residual_allowed"]:
            raise ConstraintError(
                f"infeasible: {len(free)} free assets at max_weight "
                f"{max_w:g} plus frozen weights cannot reach the required "
                f"exposure {target_sum:g}")
        if len(free) * min_w + frozen_sum > target_sum + CONSTRAINT_TOLERANCE:
            raise ConstraintError(
                "infeasible: minimum weights alone exceed the required "
                "exposure")
        for g, mn in group_minimums.items():
            members = groups_present.get(g, 0)
            if members * max_w < mn - CONSTRAINT_TOLERANCE:
                raise ConstraintError(
                    f"infeasible: group {g!r} cannot reach its minimum "
                    f"{mn:g} under max_weight {max_w:g}")
        capped_total = 0.0
        all_capped = True
        for a in eligible:
            g = a.get("group")
            if g and g in group_caps:
                continue
            all_capped = False
            break
        if all_capped and eligible:
            capped_total = sum(group_caps[g] for g in
                               {a["group"] for a in eligible})
            if capped_total < target_sum - CONSTRAINT_TOLERANCE \
                    and not out["cash_residual_allowed"]:
                raise ConstraintError(
                    "infeasible: the group caps sum to "
                    f"{capped_total:g}, below the required exposure "
                    f"{target_sum:g}")
    return out


def check_weights(weights: Dict[str, float], constraints: Dict[str, Any],
                  assets: List[Dict[str, Any]],
                  turnover: Optional[float] = None) -> List[Dict[str, Any]]:
    """Independent post-solve constraint check (violations list)."""
    tol = constraints["tolerance"]
    violations: List[Dict[str, Any]] = []

    def violate(name: str, detail: str, amount: float,
                asset_id: Optional[str] = None) -> None:
        violations.append({"constraint": name, "detail": detail,
                           "amount": amount, "asset_id": asset_id})

    for a in assets:
        w = weights.get(a["asset_id"], 0.0)
        if constraints["long_only"] and w < -tol:
            violate("long_only", f"{a['asset_id']} weight {w:.6f} is negative",
                    -w, a["asset_id"])
        if w < constraints["min_weight"] - tol \
                and a["asset_id"] not in constraints["excluded_assets"]:
            violate("min_weight",
                    f"{a['asset_id']} weight {w:.6f} below "
                    f"{constraints['min_weight']:g}",
                    constraints["min_weight"] - w, a["asset_id"])
        if w > constraints["max_weight"] + tol:
            violate("max_weight",
                    f"{a['asset_id']} weight {w:.6f} above "
                    f"{constraints['max_weight']:g}",
                    w - constraints["max_weight"], a["asset_id"])
    for asset_id in constraints["excluded_assets"]:
        if abs(weights.get(asset_id, 0.0)) > tol:
            violate("excluded_assets",
                    f"excluded asset {asset_id} has weight",
                    abs(weights.get(asset_id, 0.0)), asset_id)
    for asset_id, fw in constraints["frozen_weights"].items():
        if abs(weights.get(asset_id, 0.0) - fw) > tol:
            violate("frozen_weights",
                    f"frozen asset {asset_id} moved from {fw:g}",
                    abs(weights.get(asset_id, 0.0) - fw), asset_id)
    gross = sum(abs(w) for w in weights.values())
    if constraints["gross_exposure_limit"] is not None \
            and gross > constraints["gross_exposure_limit"] + tol:
        violate("gross_exposure_limit",
                f"gross exposure {gross:.6f} above limit",
                gross - constraints["gross_exposure_limit"])
    net = sum(weights.values())
    if constraints["net_exposure_target"] is not None \
            and abs(net - constraints["net_exposure_target"]) > tol \
            and not constraints["cash_residual_allowed"]:
        violate("net_exposure_target",
                f"net exposure {net:.6f} differs from target",
                abs(net - constraints["net_exposure_target"]))
    by_group: Dict[str, float] = {}
    for a in assets:
        if a.get("group"):
            by_group[a["group"]] = by_group.get(a["group"], 0.0) + \
                abs(weights.get(a["asset_id"], 0.0))
    for g, cap in constraints["group_caps"].items():
        if by_group.get(g, 0.0) > cap + tol:
            violate("group_caps", f"group {g} exposure {by_group[g]:.6f} "
                    f"above cap {cap:g}", by_group[g] - cap)
    for g, mn in constraints["group_minimums"].items():
        if by_group.get(g, 0.0) < mn - tol:
            violate("group_minimums", f"group {g} exposure "
                    f"{by_group.get(g, 0.0):.6f} below minimum {mn:g}",
                    mn - by_group.get(g, 0.0))
    if constraints["turnover_cap"] is not None and turnover is not None \
            and turnover > constraints["turnover_cap"] + tol:
        violate("turnover_cap",
                f"one-way turnover {turnover:.6f} above cap",
                turnover - constraints["turnover_cap"])
    if constraints["max_active_assets"] is not None:
        active = sum(1 for w in weights.values() if abs(w) > tol)
        if active > constraints["max_active_assets"]:
            violate("max_active_assets",
                    f"{active} active assets above the configured maximum "
                    "(validation-only check, never a cardinality optimizer)",
                    active - constraints["max_active_assets"])
    return violations
