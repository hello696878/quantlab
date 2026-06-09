"""
Position-sizing engine (research v1).

Position sizing scales the *magnitude* of a strategy's position **after** the
signal is generated — it never changes signal timing or direction.  This keeps
the lookahead-free guarantee of the signal layer intact and composes cleanly
with long / short modes.

All v1 modes keep ``|exposure| ≤ 1`` (no leverage by default):

* ``full_allocation``   — identity (±100% on a signal).
* ``fixed_fraction``    — multiply the position by a fixed fraction (0–1].
* ``volatility_target`` — scale toward an annualized target volatility using a
  *prior* rolling realized-vol estimate (no lookahead), capped at max exposure.
* ``max_exposure``      — clip ``|position|`` to an exposure cap (cash reserve).
"""

from __future__ import annotations

import math
from typing import Optional

import pandas as pd

from app.schemas import PositionSizing, PositionSizingResolved

DEFAULT_VOL_LOOKBACK = 20
DEFAULT_TARGET_VOL = 0.15
TRADING_DAYS = 252


def apply_sizing(
    position: pd.Series,
    close: pd.Series,
    sizing: Optional[PositionSizing],
) -> pd.Series:
    """Return *position* scaled by the sizing model (full allocation if None)."""
    if sizing is None or sizing.type in ("full", "full_allocation"):
        return position

    if sizing.type == "fixed_fraction":
        return position * float(sizing.fraction)

    if sizing.type == "max_exposure":
        return position.clip(lower=-float(sizing.max_exposure), upper=float(sizing.max_exposure))

    if sizing.type == "volatility_target":
        target = (
            sizing.target_volatility
            if sizing.target_volatility is not None
            else DEFAULT_TARGET_VOL
        )
        lookback = int(sizing.lookback_days or DEFAULT_VOL_LOOKBACK)
        max_exposure = float(sizing.max_exposure if sizing.max_exposure is not None else 1.0)
        daily_returns = close.pct_change()
        realized_daily_vol = daily_returns.rolling(lookback).std()
        target_daily_vol = float(target) / math.sqrt(TRADING_DAYS)
        # Use the *prior* day's vol estimate (shift 1) so no lookahead.  The
        # exposure cap keeps v1 non-levered even when realized vol is very low.
        scale = (target_daily_vol / realized_daily_vol).shift(1)
        scale = scale.clip(lower=0.0, upper=max_exposure).fillna(0.0)
        return position * scale

    return position


def resolve(sizing: Optional[PositionSizing]) -> PositionSizingResolved:
    """Resolve *sizing* into a display echo with a human-readable label."""
    if sizing is None or sizing.type in ("full", "full_allocation"):
        return PositionSizingResolved(
            type="full_allocation", label="Full allocation (±100% on signal)."
        )

    if sizing.type == "fixed_fraction":
        frac = float(sizing.fraction)
        return PositionSizingResolved(
            type="fixed_fraction",
            label=f"Fixed fraction: {frac:g}× capital per signal.",
            fraction=frac,
        )

    if sizing.type == "max_exposure":
        cap = float(sizing.max_exposure)
        reserve = round(1.0 - float(cap), 4)
        return PositionSizingResolved(
            type="max_exposure",
            label=f"Max exposure {cap:g} (cash reserve {reserve:g}).",
            max_exposure=float(cap),
        )

    # volatility_target
    target = (
        sizing.target_volatility
        if sizing.target_volatility is not None
        else DEFAULT_TARGET_VOL
    )
    lookback = int(sizing.lookback_days or DEFAULT_VOL_LOOKBACK)
    max_exposure = float(sizing.max_exposure if sizing.max_exposure is not None else 1.0)
    return PositionSizingResolved(
        type="volatility_target",
        label=(
            f"Volatility target: {target:.0%} annualized "
            f"({lookback}-day vol), capped at {max_exposure:.0%}."
        ),
        target_volatility=float(target),
        lookback_days=lookback,
        max_exposure=max_exposure,
    )


def average_exposure(position: pd.Series) -> float:
    """Mean absolute exposure over the period (a time-in-market measure)."""
    if position is None or len(position) == 0:
        return 0.0
    value = float(position.abs().mean())
    return round(value, 6) if math.isfinite(value) else 0.0
