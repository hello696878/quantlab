"""
Cost-unit policy (v1).

Every cost input declares its unit; conversion to a normalized monetary amount
is explicit and reversible.  1 basis point = 0.0001 of notional; percent =
0.01 of notional.  Tick inputs require a valid tick size; per-contract and
price-unit inputs require quantity (and multiplier for price units).  There
is no silent FX conversion and no ambiguous "percent" handling — the unit
string is always stored beside the original value.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional

BASIS_POINT = 0.0001
PERCENT = 0.01

COST_UNITS = (
    "currency_per_order",
    "currency_per_trade",
    "currency_per_contract",
    "currency_per_unit",
    "bps_of_notional",
    "percent_of_notional",
    "ticks",
    "price_units",
)


def _unavailable(reason: str) -> Dict[str, Any]:
    return {"status": "unavailable", "amount": None, "reason": reason}


def normalize_cost_amount(
    value: float,
    unit: str,
    *,
    quantity: Optional[float] = None,
    contract_multiplier: Optional[float] = None,
    tick_size: Optional[float] = None,
    notional: Optional[float] = None,
    order_count: int = 1,
) -> Dict[str, Any]:
    """Convert ``value`` in ``unit`` to a monetary amount for ONE execution
    context (one order / one side / one round-trip trade as the unit implies).

    Per-side composition (charging both entry and exit) is the caller's
    responsibility and lives in ``components.py``.  Returns ``{"status":
    "available", "amount": float}`` or an unavailable record with an explicit
    reason.  Missing or invalid context never silently becomes zero, and
    negative cost values are rejected here (favourable amounts exist only as
    supplied realized slippage, which does not pass through this function).
    """
    if unit not in COST_UNITS:
        return _unavailable(f"unsupported cost unit {unit!r}")
    try:
        v = float(value)
    except (TypeError, ValueError):
        return _unavailable("cost value is not a number")
    if not math.isfinite(v):
        return _unavailable("cost value is not finite")
    if v < 0:
        return _unavailable("negative cost values are rejected")
    if unit == "currency_per_order":
        if isinstance(order_count, bool) or not isinstance(order_count, int) \
                or order_count < 1:
            return _unavailable(
                "currency_per_order requires a positive integer order count")
        return {"status": "available", "amount": v * order_count}
    if unit == "currency_per_trade":
        return {"status": "available", "amount": v}
    if unit == "currency_per_contract":
        if quantity is None or quantity <= 0:
            return _unavailable(f"{unit} requires a positive quantity")
        return {"status": "available", "amount": v * quantity}
    if unit == "currency_per_unit":
        # per underlying unit: contracts x multiplier
        if quantity is None or quantity <= 0:
            return _unavailable(f"{unit} requires a positive quantity")
        if contract_multiplier is None or contract_multiplier <= 0:
            return _unavailable(f"{unit} requires a positive contract_multiplier")
        return {"status": "available", "amount": v * quantity * contract_multiplier}
    if unit == "bps_of_notional":
        if notional is None or notional < 0:
            return _unavailable("bps_of_notional requires a non-negative notional")
        return {"status": "available", "amount": v * BASIS_POINT * notional}
    if unit == "percent_of_notional":
        if notional is None or notional < 0:
            return _unavailable("percent_of_notional requires a non-negative notional")
        return {"status": "available", "amount": v * PERCENT * notional}
    if unit == "ticks":
        if tick_size is None or tick_size <= 0:
            return _unavailable("ticks require a positive tick_size")
        if quantity is None or quantity <= 0:
            return _unavailable("ticks require a positive quantity")
        mult = contract_multiplier if contract_multiplier and contract_multiplier > 0 else None
        if mult is None:
            return _unavailable("ticks require a positive contract_multiplier")
        return {"status": "available", "amount": v * tick_size * quantity * mult}
    # price_units
    if quantity is None or quantity <= 0:
        return _unavailable("price_units require a positive quantity")
    mult = contract_multiplier if contract_multiplier and contract_multiplier > 0 else None
    if mult is None:
        return _unavailable("price_units require a positive contract_multiplier")
    return {"status": "available", "amount": v * quantity * mult}


def spread_to_price(value: float, unit: str, *, mid_price: Optional[float] = None,
                    tick_size: Optional[float] = None) -> Dict[str, Any]:
    """Convert a quoted spread in ``bps`` / ``price`` / ``ticks`` to price units.

    ``bps`` spreads are relative to ``mid_price``.  Negative spreads are
    rejected upstream; here a negative result is reported unavailable.
    """
    if not math.isfinite(float(value)) or float(value) < 0:
        return _unavailable("spread must be a finite non-negative value")
    v = float(value)
    if unit == "price":
        return {"status": "available", "amount": v}
    if unit == "ticks":
        if tick_size is None or tick_size <= 0:
            return _unavailable("tick spread requires a positive tick_size")
        return {"status": "available", "amount": v * tick_size}
    if unit == "bps":
        if mid_price is None or mid_price <= 0:
            return _unavailable("bps spread requires a positive reference price")
        return {"status": "available", "amount": v * BASIS_POINT * mid_price}
    return _unavailable(f"unsupported spread unit {unit!r}")
