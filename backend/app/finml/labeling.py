"""
Triple-barrier labeling (López de Prado, AFML ch. 3).

For each event, set a profit-take barrier above and a stop-loss barrier below
(both scaled by a per-event volatility target), plus a vertical (time) barrier.
The label is determined by **which barrier is touched first**.

Event *formation* uses no future information; future prices are only consulted to
**assign the label** after the event exists, exactly as labeling requires.
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np


def triple_barrier_labels(
    close: np.ndarray,
    event_indices: List[int],
    rolling_vol: np.ndarray,
    profit_take_multiple: float,
    stop_loss_multiple: float,
    vertical_barrier_days: int,
    fixed_target: Optional[float] = None,
) -> List[dict]:
    """Label each event by the first barrier touched.

    Returns dicts with start/end, barriers, ``label`` (+1 / −1 / 0),
    ``touched_barrier`` (profit_take / stop_loss / vertical), realized return, and
    holding period (in observations). Events with no forward window are skipped.
    """
    n = close.shape[0]
    out: List[dict] = []
    eid = 0
    for t0 in event_indices:
        if t0 >= n - 1:
            continue  # no forward window → cannot form a label
        start_price = float(close[t0])
        target = float(fixed_target) if fixed_target is not None else float(rolling_vol[t0])
        if not (target > 0):
            continue

        upper = start_price * (1.0 + profit_take_multiple * target)
        lower = start_price * (1.0 - stop_loss_multiple * target)
        vbar = min(t0 + vertical_barrier_days, n - 1)

        label = 0
        touched = "vertical"
        end = vbar
        for u in range(t0 + 1, vbar + 1):
            price = float(close[u])
            if price >= upper:
                label, touched, end = 1, "profit_take", u
                break
            if price <= lower:
                label, touched, end = -1, "stop_loss", u
                break
        else:
            realized = close[vbar] / start_price - 1.0
            label = int(np.sign(realized))
            touched = "vertical"
            end = vbar

        end_price = float(close[end])
        realized_return = end_price / start_price - 1.0
        out.append(
            {
                "event_id": eid,
                "start_index": int(t0),
                "end_index": int(end),
                "start_price": start_price,
                "end_price": end_price,
                "target_return": target,
                "upper_barrier": upper,
                "lower_barrier": lower,
                "label": int(label),
                "touched_barrier": touched,
                "realized_return": float(realized_return),
                "holding_period_days": int(end - t0),
            }
        )
        eid += 1
    return out
