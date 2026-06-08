"""
Transaction-cost / slippage model resolution (research v1).

A :class:`~app.schemas.CostModel` only declares *how* to compute the per-side
cost in basis points; the backtest engine's turnover math (cost charged on
``|Δposition|``) is unchanged.  This module turns a cost model into a single
effective per-side bps value plus a human-readable breakdown for display.

Design goals: research realism, backward compatibility, no execution
simulation (no order book, no partial fills, no market impact).
"""

from __future__ import annotations

from typing import Optional

from app.schemas import CostModel, CostModelResolved

# "Conservative" preset — higher assumed execution friction.
CONSERVATIVE_COMMISSION_BPS = 10.0
CONSERVATIVE_SLIPPAGE_BPS = 10.0
CONSERVATIVE_SPREAD_BPS = 5.0
CONSERVATIVE_LABEL = "Conservative: higher assumed execution friction."


def _fmt(bps: float) -> str:
    """Compact bps formatting (no trailing zeros)."""
    return f"{bps:g}"


def resolve(model: Optional[CostModel], fallback_bps: float) -> CostModelResolved:
    """
    Resolve *model* into a :class:`CostModelResolved`.

    ``fallback_bps`` is the request's top-level ``transaction_cost_bps``, used
    when the model is ``None`` or is ``simple_bps`` without its own value — this
    is what preserves the original behaviour for existing requests.

    The returned ``effective_bps_per_side`` is charged on trade turnover, so a
    long↔short flip (turnover 2) costs twice this value.
    """
    if model is None:
        return CostModelResolved(
            type="simple_bps",
            label=f"Simple: {_fmt(fallback_bps)} bps/side.",
            commission_bps=0.0,
            slippage_bps=0.0,
            spread_bps=0.0,
            effective_bps_per_side=float(fallback_bps),
        )

    if model.type == "conservative":
        commission = CONSERVATIVE_COMMISSION_BPS
        slippage = CONSERVATIVE_SLIPPAGE_BPS
        spread = CONSERVATIVE_SPREAD_BPS
        effective = commission + slippage + spread
        label = CONSERVATIVE_LABEL
    elif model.type == "commission_slippage":
        commission = model.commission_bps or 0.0
        slippage = model.slippage_bps or 0.0
        spread = model.spread_bps or 0.0
        effective = commission + slippage + spread
        label = f"Commission + slippage: {_fmt(effective)} bps/side."
    else:  # simple_bps
        effective = (
            model.transaction_cost_bps
            if model.transaction_cost_bps is not None
            else float(fallback_bps)
        )
        commission = slippage = spread = 0.0
        label = f"Simple: {_fmt(effective)} bps/side."

    return CostModelResolved(
        type=model.type,
        label=label,
        commission_bps=commission,
        slippage_bps=slippage,
        spread_bps=spread,
        effective_bps_per_side=float(effective),
    )
