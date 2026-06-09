"""
Risk-management engine (research v1).

Risk rules run **after** a strategy signal + position mode have produced a
desired ±1 / 0 position, and **before** position sizing scales the magnitude.
They only ever **close a position to cash** — they never reverse a position.
A later, genuinely new signal can re-enter.

Execution convention (documented, lookahead-free)
-------------------------------------------------
The desired position series is already shifted by one bar (position[t] is the
exposure for the close[t-1]→close[t] interval, decided from data through
close[t-1]).  Risk rules follow the *same* convention: the decision to hold or
close on bar ``t`` uses only prices through ``close[t-1]``.  Entry price and the
trailing peak/trough are tracked on those same closes.  This means stops are
**daily-close based**: intraday breaches, gaps and order priority are not
modelled.

Rules (all percentages are decimals, 0.10 = 10%)
------------------------------------------------
* stop_loss      — long: close ≤ entry·(1-sl);  short: close ≥ entry·(1+sl)
* take_profit    — long: close ≥ entry·(1+tp);  short: close ≤ entry·(1-tp)
* trailing_stop  — long: close ≤ peak·(1-ts);   short: close ≥ trough·(1+ts)
* max_holding    — exit after the position has been held ``max_holding_days`` bars
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
import pandas as pd

from app.schemas import RiskDiagnostics, RiskManagement, RiskManagementResolved

_REASON_KEYS = ("stop_loss", "take_profit", "trailing_stop", "max_holding_days")
_COUNT_KEY = {
    "stop_loss": "stop_loss_count",
    "take_profit": "take_profit_count",
    "trailing_stop": "trailing_stop_count",
    "max_holding_days": "max_holding_exit_count",
}


@dataclass
class RiskResult:
    """Output of :func:`apply_risk_management`."""

    position: pd.Series  # risk-adjusted ±1 / 0 position
    exit_reasons: Dict[int, str]  # change-bar index -> risk reason
    counts: Dict[str, int]  # per-rule exit counts
    num_entries: int


def is_active(risk: Optional[RiskManagement]) -> bool:
    """True when risk management should change behaviour."""
    return risk is not None and risk.type != "none"


def _active_rules(risk: RiskManagement) -> tuple:
    """Return (stop_loss, take_profit, trailing_stop, max_holding) for the type."""
    t = risk.type
    sl = tp = ts = None
    mh = None
    if t == "fixed_stop_take_profit":
        sl = risk.stop_loss_pct
        tp = risk.take_profit_pct
    elif t == "trailing_stop":
        ts = risk.trailing_stop_pct
    elif t == "max_holding_days":
        mh = risk.max_holding_days
    elif t == "combined":
        sl = risk.stop_loss_pct
        tp = risk.take_profit_pct
        ts = risk.trailing_stop_pct
        mh = risk.max_holding_days
    return sl, tp, ts, mh


def _triggered(
    held_sign: int,
    entry_price: float,
    extreme: float,
    price: float,
    bars_held: int,
    sl: Optional[float],
    tp: Optional[float],
    ts: Optional[float],
    mh: Optional[int],
) -> Optional[str]:
    if sl is not None:
        if held_sign > 0 and price <= entry_price * (1.0 - sl):
            return "stop_loss"
        if held_sign < 0 and price >= entry_price * (1.0 + sl):
            return "stop_loss"
    if tp is not None:
        if held_sign > 0 and price >= entry_price * (1.0 + tp):
            return "take_profit"
        if held_sign < 0 and price <= entry_price * (1.0 - tp):
            return "take_profit"
    if ts is not None:
        if held_sign > 0 and price <= extreme * (1.0 - ts):
            return "trailing_stop"
        if held_sign < 0 and price >= extreme * (1.0 + ts):
            return "trailing_stop"
    if mh is not None and bars_held >= mh:
        return "max_holding_days"
    return None


def apply_risk_management(
    position: pd.Series,
    close: pd.Series,
    risk: Optional[RiskManagement],
) -> RiskResult:
    """Apply risk rules to a desired ±1/0 position series (see module docstring)."""
    counts = {_COUNT_KEY[k]: 0 for k in _REASON_KEYS}

    if not is_active(risk):
        # Identity: returns the original position untouched (backward-compatible).
        return RiskResult(position=position, exit_reasons={}, counts=counts, num_entries=0)

    sl, tp, ts, mh = _active_rules(risk)

    pos = position.reindex(close.index).ffill().fillna(0.0)
    prices = close.to_numpy(dtype=float)
    desired = np.sign(pos.to_numpy(dtype=float)).astype(int)
    n = len(prices)
    adj = np.zeros(n, dtype=float)
    exit_reasons: Dict[int, str] = {}

    held_sign = 0
    entry_idx = -1
    entry_price = 0.0
    extreme = 0.0
    blocked_dir = 0
    num_entries = 0

    for t in range(n):
        d = int(desired[t])
        # Decide bar t's exposure using only prices through close[t-1].
        cur_price = prices[t - 1] if t > 0 else prices[0]

        if held_sign == 0:
            if d == 0:
                blocked_dir = 0  # signal reset — next non-zero is a fresh entry
                adj[t] = 0.0
            elif blocked_dir != 0 and d == blocked_dir:
                adj[t] = 0.0  # block re-entry into the same persistent signal
            else:
                held_sign = d
                entry_idx = t
                entry_price = cur_price
                extreme = cur_price
                blocked_dir = 0
                num_entries += 1
                adj[t] = float(d)
        elif d != held_sign:
            # Signal-driven exit or flip (never blocked).
            if d == 0:
                held_sign = 0
                adj[t] = 0.0
            else:
                held_sign = d
                entry_idx = t
                entry_price = cur_price
                extreme = cur_price
                num_entries += 1
                adj[t] = float(d)
            blocked_dir = 0
        else:
            # Still holding the same direction — update extreme then test rules.
            if held_sign > 0:
                extreme = max(extreme, cur_price)
            else:
                extreme = min(extreme, cur_price)
            bars_held = t - entry_idx  # bars held through close[t-1]
            reason = _triggered(
                held_sign, entry_price, extreme, cur_price, bars_held, sl, tp, ts, mh
            )
            if reason is not None:
                adj[t] = 0.0
                held_sign = 0
                blocked_dir = d  # block same-direction re-entry until signal resets
                exit_reasons[t] = reason
                counts[_COUNT_KEY[reason]] += 1
            else:
                adj[t] = float(held_sign)

    adj_series = pd.Series(adj, index=close.index, name="position")
    return RiskResult(
        position=adj_series,
        exit_reasons=exit_reasons,
        counts=counts,
        num_entries=num_entries,
    )


def _fmt_pct(value: Optional[float]) -> Optional[str]:
    return None if value is None else f"{value:.0%}"


def resolve(risk: Optional[RiskManagement]) -> Optional[RiskManagementResolved]:
    """Resolve risk config into a display echo (None when inactive)."""
    if not is_active(risk):
        return None
    assert risk is not None
    parts: list[str] = []
    if risk.type in ("fixed_stop_take_profit", "combined"):
        if risk.stop_loss_pct is not None:
            parts.append(f"stop {_fmt_pct(risk.stop_loss_pct)}")
        if risk.take_profit_pct is not None:
            parts.append(f"take {_fmt_pct(risk.take_profit_pct)}")
    if risk.type in ("trailing_stop", "combined") and risk.trailing_stop_pct is not None:
        parts.append(f"trailing {_fmt_pct(risk.trailing_stop_pct)}")
    if risk.type in ("max_holding_days", "combined") and risk.max_holding_days is not None:
        parts.append(f"max {risk.max_holding_days} bars")
    label = "Risk rules: " + (", ".join(parts) if parts else "none") + "."
    return RiskManagementResolved(
        type=risk.type,
        label=label,
        stop_loss_pct=risk.stop_loss_pct,
        take_profit_pct=risk.take_profit_pct,
        trailing_stop_pct=risk.trailing_stop_pct,
        max_holding_days=risk.max_holding_days,
    )


def diagnostics(result: RiskResult) -> RiskDiagnostics:
    """Build the risk-exit diagnostics from a :class:`RiskResult`."""
    risk_exit_count = int(sum(result.counts.values()))
    rate = risk_exit_count / result.num_entries if result.num_entries > 0 else 0.0
    return RiskDiagnostics(
        risk_exit_count=risk_exit_count,
        stop_loss_count=int(result.counts["stop_loss_count"]),
        take_profit_count=int(result.counts["take_profit_count"]),
        trailing_stop_count=int(result.counts["trailing_stop_count"]),
        max_holding_exit_count=int(result.counts["max_holding_exit_count"]),
        risk_exit_rate=round(rate, 6),
    )
