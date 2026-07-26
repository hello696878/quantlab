"""
Commission, spread and slippage models (v1).

Semantics (documented, no hidden assumptions):

* Commission — ``fixed_per_order`` charges its value once per order with
  explicit entry/exit order counts; ``fixed_per_trade`` charges once per
  round-trip trade; ``per_contract`` / ``per_unit`` charge per contract or
  unit **per side** (entry and exit executions each pay); ``bps_of_notional``
  is a per-side rate applied to each side's notional (equivalently to the
  round-trip traded notional).  An optional minimum is applied first (floor),
  then an optional maximum (cap); ``maximum >= minimum`` is enforced.
  Negative fees are rejected; zero is allowed.
* Spread — the configured ``fraction`` of the quoted spread (in [0, 1]) is
  assumed paid per marketable execution; there is no silent half-spread or
  full-spread default — the fraction must be configured explicitly.  Sides
  are explicit (``round_trip`` / ``entry_only`` / ``exit_only``).
* Slippage — deterministic fixed per-side assumptions or supplied realized
  slippage.  The stress multiplier (>= 1) applies to modelled slippage only,
  never to supplied realized values, and cannot generate favourable slippage.
  Favourable (negative) slippage exists only when supplied and labelled
  ``supplied_realized``.

Period-level observations support only notional-proportional models
(basis points on turnover); monetary-unit models are rejected for period runs
because period observations carry no capital base.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional, Tuple

from app.cost_diagnostics.core import CostInputError
from app.cost_diagnostics.units import BASIS_POINT

COMMISSION_MODELS = ("none", "fixed_per_order", "fixed_per_trade",
                     "per_contract", "per_unit", "bps_of_notional")
SPREAD_MODELS = ("none", "fixed_bps", "fixed_price", "fixed_ticks", "supplied")
SLIPPAGE_MODELS = ("none", "fixed_bps_per_side", "fixed_ticks_per_side",
                   "fixed_price_per_side", "supplied_realized")
SPREAD_SIDES = ("round_trip", "entry_only", "exit_only")

PERIOD_COMMISSION_MODELS = ("none", "bps_of_notional")
PERIOD_SPREAD_MODELS = ("none", "fixed_bps", "supplied")
PERIOD_SLIPPAGE_MODELS = ("none", "fixed_bps_per_side")

MAX_ORDERS_PER_SIDE = 10
MAX_STRESS_MULTIPLIER = 10.0

_NOT_CONFIGURED = {"status": "not_configured", "amount": None, "reason": None}


def _finite_value(cfg: Dict[str, Any], field: str, *, required: bool,
                  non_negative: bool = True) -> Optional[float]:
    v = cfg.get(field)
    if v is None:
        if required:
            raise CostInputError(f"cost model field {field!r} is required")
        return None
    if isinstance(v, bool):
        raise CostInputError(f"cost model field {field!r} must be a number")
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise CostInputError(f"cost model field {field!r} must be a number")
    if not math.isfinite(f):
        raise CostInputError(f"cost model field {field!r} must be finite")
    if non_negative and f < 0:
        raise CostInputError(f"cost model field {field!r} must be >= 0 "
                             "(negative fees are rejected)")
    return f


def _config_dict(raw: Any, component: str) -> Dict[str, Any]:
    if raw is None:
        return {"model": "none"}
    if not isinstance(raw, dict):
        raise CostInputError(f"{component} configuration must be an object")
    return dict(raw)


def validate_commission_config(raw: Any, observation_type: str) -> Dict[str, Any]:
    cfg = _config_dict(raw, "commission")
    model = cfg.get("model", "none")
    if model not in COMMISSION_MODELS:
        raise CostInputError(
            f"commission model must be one of {', '.join(COMMISSION_MODELS)}")
    if observation_type == "period" and model not in PERIOD_COMMISSION_MODELS:
        raise CostInputError(
            "period observations support only commission models "
            f"{', '.join(PERIOD_COMMISSION_MODELS)}; monetary units need a "
            "capital base that period observations do not carry")
    if observation_type == "period":
        for field in ("minimum", "maximum", "entry_orders", "exit_orders"):
            if cfg.get(field) is not None:
                raise CostInputError(
                    f"commission {field} is a monetary/order-level setting and "
                    "is not supported for period observations (no capital "
                    "base); it would otherwise be silently ignored")
    out: Dict[str, Any] = {"model": model}
    if model != "none":
        out["value"] = _finite_value(cfg, "value", required=True)
        if observation_type == "trade":
            minimum = _finite_value(cfg, "minimum", required=False)
            maximum = _finite_value(cfg, "maximum", required=False)
            if minimum is not None and maximum is not None and maximum < minimum:
                raise CostInputError("commission maximum must be >= minimum")
            out["minimum"] = minimum
            out["maximum"] = maximum
            for field in ("entry_orders", "exit_orders"):
                v = cfg.get(field, 1)
                if isinstance(v, bool) or not isinstance(v, int) or not (
                        1 <= v <= MAX_ORDERS_PER_SIDE):
                    raise CostInputError(
                        f"{field} must be an integer in [1, {MAX_ORDERS_PER_SIDE}]")
                out[field] = v
    return out


def validate_spread_config(raw: Any, observation_type: str) -> Dict[str, Any]:
    cfg = _config_dict(raw, "spread")
    model = cfg.get("model", "none")
    if model not in SPREAD_MODELS:
        raise CostInputError(
            f"spread model must be one of {', '.join(SPREAD_MODELS)}")
    if observation_type == "period" and model not in PERIOD_SPREAD_MODELS:
        raise CostInputError(
            "period observations support only spread models "
            f"{', '.join(PERIOD_SPREAD_MODELS)}")
    if observation_type == "period" and cfg.get("sides") not in (None, "round_trip"):
        raise CostInputError(
            "period turnover carries no entry/exit decomposition; spread "
            "sides must be 'round_trip' for period observations")
    out: Dict[str, Any] = {"model": model}
    if model != "none":
        fraction = cfg.get("fraction")
        if fraction is None:
            raise CostInputError(
                "spread fraction must be configured explicitly (no silent "
                "half-spread or full-spread assumption)")
        f = _finite_value({"fraction": fraction}, "fraction", required=True)
        if f > 1.0:
            raise CostInputError("spread fraction must be in [0, 1]")
        out["fraction"] = f
        sides = cfg.get("sides", "round_trip")
        if sides not in SPREAD_SIDES:
            raise CostInputError(
                f"spread sides must be one of {', '.join(SPREAD_SIDES)}")
        out["sides"] = sides
        if model in ("fixed_bps", "fixed_price", "fixed_ticks"):
            out["value"] = _finite_value(cfg, "value", required=True)
    return out


def validate_slippage_config(raw: Any, observation_type: str) -> Dict[str, Any]:
    cfg = _config_dict(raw, "slippage")
    model = cfg.get("model", "none")
    if model not in SLIPPAGE_MODELS:
        raise CostInputError(
            f"slippage model must be one of {', '.join(SLIPPAGE_MODELS)}")
    if observation_type == "period" and model not in PERIOD_SLIPPAGE_MODELS:
        raise CostInputError(
            "period observations support only slippage models "
            f"{', '.join(PERIOD_SLIPPAGE_MODELS)}")
    out: Dict[str, Any] = {"model": model}
    if model != "none":
        stress = cfg.get("stress_multiplier", 1.0)
        s = _finite_value({"stress_multiplier": stress}, "stress_multiplier",
                          required=True)
        if not (1.0 <= s <= MAX_STRESS_MULTIPLIER):
            raise CostInputError(
                f"stress_multiplier must be in [1, {MAX_STRESS_MULTIPLIER:g}] "
                "(stress must not generate favourable slippage)")
        out["stress_multiplier"] = s
        if model.startswith("fixed_"):
            out["value"] = _finite_value(cfg, "value", required=True)
    return out


# --------------------------------------------------------------------------
# per-observation computation — trades (monetary) and periods (return space)
# --------------------------------------------------------------------------

def compute_commission(obs: Dict[str, Any], cfg: Dict[str, Any],
                       observation_type: str) -> Dict[str, Any]:
    model = cfg.get("model", "none")
    if model == "none":
        return dict(_NOT_CONFIGURED)
    value = cfg["value"]
    if observation_type == "period":
        # bps_of_notional on per-period turnover (fraction of capital traded)
        if obs.get("turnover") is None:
            return {"status": "unavailable", "amount": None,
                    "reason": "commission on turnover requires turnover"}
        return {"status": "available",
                "amount": value * BASIS_POINT * obs["turnover"], "reason": None}
    q = obs["quantity"]
    if model == "fixed_per_order":
        amount = value * (cfg["entry_orders"] + cfg["exit_orders"])
    elif model == "fixed_per_trade":
        amount = value
    elif model == "per_contract":
        amount = value * q * 2  # entry and exit executions each pay per side
    elif model == "per_unit":
        # per underlying unit (contracts x multiplier), each side pays
        amount = value * q * obs["contract_multiplier"] * 2
    else:  # bps_of_notional — per-side rate on each side's notional
        amount = value * BASIS_POINT * obs["traded_notional"]
    if cfg.get("minimum") is not None:
        amount = max(amount, cfg["minimum"])   # floor first
    if cfg.get("maximum") is not None:
        amount = min(amount, cfg["maximum"])   # then cap
    return {"status": "available", "amount": amount, "reason": None}


def _supplied_spread_price(obs: Dict[str, Any], side_price: float,
                           tick_size: Optional[float]
                           ) -> Tuple[Optional[float], Optional[str]]:
    """Returns ``(spread_in_price_units, unavailable_reason)``."""
    spec = obs.get("cost_inputs", {}).get("spread")
    if spec is None:
        return None, "supplied spread missing for this observation"
    v, unit = spec["value"], spec["unit"]
    if unit == "price":
        return v, None
    if unit == "ticks":
        if tick_size is None or tick_size <= 0:
            return None, "supplied tick spread requires a configured tick_size"
        return v * tick_size, None
    return v * BASIS_POINT * side_price, None  # bps of the side's price


def compute_spread_cost(obs: Dict[str, Any], cfg: Dict[str, Any],
                        observation_type: str,
                        tick_size: Optional[float]) -> Dict[str, Any]:
    model = cfg.get("model", "none")
    if model == "none":
        return dict(_NOT_CONFIGURED)
    fraction = cfg["fraction"]
    if observation_type == "period":
        if obs.get("turnover") is None:
            return {"status": "unavailable", "amount": None,
                    "reason": "spread cost on turnover requires turnover"}
        if model == "fixed_bps":
            bps = cfg["value"]
        else:  # supplied — bps input required for period observations
            spec = obs.get("cost_inputs", {}).get("spread")
            if spec is None or spec["unit"] != "bps":
                return {"status": "unavailable", "amount": None,
                        "reason": "supplied spread (bps) missing for this "
                                  "observation"}
            bps = spec["value"]
        return {"status": "available",
                "amount": fraction * bps * BASIS_POINT * obs["turnover"],
                "reason": None}
    q_units = obs["quantity"] * obs["contract_multiplier"]
    per_side = []
    for side, price in (("entry", obs["entry_price"]), ("exit", obs["exit_price"])):
        if cfg["sides"] == "entry_only" and side != "entry":
            continue
        if cfg["sides"] == "exit_only" and side != "exit":
            continue
        if model == "fixed_price":
            s_price = cfg["value"]
        elif model == "fixed_ticks":
            if tick_size is None or tick_size <= 0:
                return {"status": "unavailable", "amount": None,
                        "reason": "tick spread requires a configured tick_size"}
            s_price = cfg["value"] * tick_size
        elif model == "fixed_bps":
            s_price = cfg["value"] * BASIS_POINT * price
        else:  # supplied
            s_price, reason = _supplied_spread_price(obs, price, tick_size)
            if s_price is None:
                return {"status": "unavailable", "amount": None,
                        "reason": reason}
        per_side.append(fraction * s_price * q_units)
    return {"status": "available", "amount": float(sum(per_side)), "reason": None}


def compute_slippage(obs: Dict[str, Any], cfg: Dict[str, Any],
                     observation_type: str,
                     tick_size: Optional[float]) -> Dict[str, Any]:
    model = cfg.get("model", "none")
    if model == "none":
        return dict(_NOT_CONFIGURED)
    if model == "supplied_realized":
        spec = obs.get("cost_inputs", {}).get("realized_slippage")
        if spec is None:
            return {"status": "unavailable", "amount": None, "modelled_amount": None,
                    "source": "supplied_realized",
                    "reason": "realized slippage missing for this observation"}
        # supplied realized values are used as-is (may be favourable/negative);
        # the stress multiplier never applies to realized fills.
        return {"status": "available", "amount": spec["value"],
                "modelled_amount": None, "source": "supplied_realized",
                "reason": None}
    stress = cfg["stress_multiplier"]
    if observation_type == "period":
        if obs.get("turnover") is None:
            return {"status": "unavailable", "amount": None, "modelled_amount": None,
                    "source": "modelled",
                    "reason": "slippage on turnover requires turnover"}
        modelled = cfg["value"] * BASIS_POINT * obs["turnover"]
        return {"status": "available", "amount": modelled * stress,
                "modelled_amount": modelled, "source": "modelled", "reason": None}
    q_units = obs["quantity"] * obs["contract_multiplier"]
    if model == "fixed_bps_per_side":
        modelled = cfg["value"] * BASIS_POINT * obs["traded_notional"]
    elif model == "fixed_ticks_per_side":
        if tick_size is None or tick_size <= 0:
            return {"status": "unavailable", "amount": None, "modelled_amount": None,
                    "source": "modelled",
                    "reason": "tick slippage requires a configured tick_size"}
        modelled = cfg["value"] * tick_size * q_units * 2
    else:  # fixed_price_per_side
        modelled = cfg["value"] * q_units * 2
    return {"status": "available", "amount": modelled * stress,
            "modelled_amount": modelled, "source": "modelled", "reason": None}
