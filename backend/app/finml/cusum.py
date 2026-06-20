"""
Symmetric CUSUM filter for event sampling (López de Prado, AFML ch. 2).

Accumulates returns into a positive and a negative running sum; emits an event
and resets the relevant side whenever it breaches the threshold.  Each event uses
only information available up to that bar (no lookahead).
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np

THRESHOLD_MODES = ("fixed", "vol_scaled")


def cusum_events(
    returns: np.ndarray,
    threshold: float,
    threshold_mode: str = "fixed",
    rolling_vol: Optional[np.ndarray] = None,
) -> List[dict]:
    """Return CUSUM events as dicts ``{index, side, threshold_used, return_at_event}``.

    ``fixed``: compare against ``threshold`` (an absolute cumulative-return level).
    ``vol_scaled``: compare against ``threshold · rolling_vol[t]`` at each bar.
    """
    n = returns.shape[0]
    s_pos = 0.0
    s_neg = 0.0
    events: List[dict] = []
    for t in range(1, n):
        r = float(returns[t])
        if not np.isfinite(r):
            s_pos = 0.0
            s_neg = 0.0
            continue
        if threshold_mode == "vol_scaled" and rolling_vol is not None:
            h = float(threshold) * float(rolling_vol[t])
        else:
            h = float(threshold)
        if not np.isfinite(h) or h <= 0:
            continue
        s_pos = max(0.0, s_pos + r)
        s_neg = min(0.0, s_neg + r)
        if s_pos > h:
            events.append({"index": t, "side": "positive", "threshold_used": h, "return_at_event": r})
            s_pos = 0.0
        elif s_neg < -h:
            events.append({"index": t, "side": "negative", "threshold_used": h, "return_at_event": r})
            s_neg = 0.0
    return events
