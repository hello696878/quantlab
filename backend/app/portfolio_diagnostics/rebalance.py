"""
No-look-ahead estimation windows, rebalance schedules and turnover (v1).

At a rebalance with decision index i, the estimation window is:

* ``rolling``:   returns[i-lag-lookback+1 .. i-lag]  (trailing only)
* ``expanding``: returns[0 .. i-lag] requiring at least ``min_history``
* ``full_sample``: the whole sample — descriptive only, never leakage-safe

with ``lag >= 1`` enforced: weights effective FOR period i use returns
through i-lag at most, so the period being traded never informs its own
weights.  Centered windows and negative lags are rejected outright.
Early rebalances with insufficient history are honestly unavailable.

Turnover convention (documented): ``one_way_turnover = 0.5 × Σ_i
|w_new_i − w_old_i|`` — the half-L1 convention also used by the Phase 21
optimizer.  The initial-rebalance turnover policy is explicit:
``none`` (no prior book → turnover unavailable), ``zero_book`` (a
documented all-cash start → turnover = 0.5 × Σ|w|), or ``supplied``
(the universe's prior weights).
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from app.portfolio_diagnostics.core import PortfolioInputError

ESTIMATION_MODES = ("rolling", "expanding", "full_sample")
REBALANCE_KINDS = ("one_time", "every_n", "fixed_timestamps")
INITIAL_TURNOVER_POLICIES = ("none", "zero_book", "supplied")

MIN_LOOKBACK = 3
MAX_LOOKBACK = 500
MIN_LAG = 1
MAX_LAG = 30
MIN_HISTORY_DEFAULT = 12
MAX_REBALANCES = 60


def validate_estimation_config(raw: Any) -> Dict[str, Any]:
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise PortfolioInputError("estimation configuration must be an object")
    cfg = dict(raw)
    if cfg.get("window") == "centered" or cfg.get("centered") is True:
        raise PortfolioInputError(
            "centered estimation windows are prohibited (no look-ahead)")
    mode = cfg.get("mode", "rolling")
    if mode not in ESTIMATION_MODES:
        raise PortfolioInputError(
            f"estimation mode must be one of {', '.join(ESTIMATION_MODES)}")
    out: Dict[str, Any] = {"mode": mode}
    lag = cfg.get("lag", 1)
    if isinstance(lag, bool) or not isinstance(lag, int) or not (
            MIN_LAG <= lag <= MAX_LAG):
        raise PortfolioInputError(
            f"lag must be an integer in [{MIN_LAG}, {MAX_LAG}] — negative or "
            "zero lags would leak the traded period into its own weights")
    out["lag"] = lag
    if mode == "rolling":
        lookback = cfg.get("lookback")
        if isinstance(lookback, bool) or not isinstance(lookback, int) or not (
                MIN_LOOKBACK <= lookback <= MAX_LOOKBACK):
            raise PortfolioInputError(
                f"rolling estimation requires an integer lookback in "
                f"[{MIN_LOOKBACK}, {MAX_LOOKBACK}]")
        out["lookback"] = lookback
    else:
        min_history = cfg.get("min_history", MIN_HISTORY_DEFAULT)
        if isinstance(min_history, bool) or not isinstance(min_history, int) \
                or min_history < MIN_LOOKBACK:
            raise PortfolioInputError(
                f"min_history must be an integer >= {MIN_LOOKBACK}")
        out["min_history"] = min_history
    return out


def validate_rebalance_policy(raw: Any, timestamps: List[str]) -> Dict[str, Any]:
    if raw is None:
        raw = {"kind": "one_time"}
    if not isinstance(raw, dict):
        raise PortfolioInputError("rebalance policy must be an object")
    cfg = dict(raw)
    kind = cfg.get("kind", "one_time")
    if kind not in REBALANCE_KINDS:
        raise PortfolioInputError(
            f"rebalance kind must be one of {', '.join(REBALANCE_KINDS)}")
    out: Dict[str, Any] = {"kind": kind}
    if kind == "every_n":
        n = cfg.get("every_n")
        if isinstance(n, bool) or not isinstance(n, int) or n < 1:
            raise PortfolioInputError("every_n must be a positive integer")
        out["every_n"] = n
    if kind == "fixed_timestamps":
        stamps = cfg.get("timestamps")
        if not isinstance(stamps, list) or not stamps:
            raise PortfolioInputError(
                "fixed_timestamps requires a non-empty timestamps list")
        index = {ts: i for i, ts in enumerate(timestamps)}
        indices = []
        for s in stamps:
            if not isinstance(s, str):
                raise PortfolioInputError(
                    "rebalance timestamps must be strings")
            if s not in index:
                raise PortfolioInputError(
                    f"rebalance timestamp {s!r} is not on the shared "
                    "timeline (no fabricated timestamps)")
            indices.append(index[s])
        out["indices"] = sorted(set(indices))
    policy = cfg.get("initial_turnover_policy", "none")
    if policy not in INITIAL_TURNOVER_POLICIES:
        raise PortfolioInputError(
            "initial_turnover_policy must be one of "
            f"{', '.join(INITIAL_TURNOVER_POLICIES)}")
    out["initial_turnover_policy"] = policy
    return out


def estimation_window(i: int, estimation: Dict[str, Any],
                      n_periods: int) -> Optional[Tuple[int, int]]:
    """Permitted (start, end) inclusive window for decision index i, or None."""
    lag = estimation["lag"]
    end = i - lag
    if estimation["mode"] == "rolling":
        start = end - estimation["lookback"] + 1
        if start < 0 or end < start:
            return None
        return (start, end)
    if estimation["mode"] == "expanding":
        if end + 1 < estimation["min_history"]:
            return None
        return (0, end)
    # full_sample — descriptive only, labelled by the integrity state
    return (0, n_periods - 1)


def first_feasible_index(estimation: Dict[str, Any], n_periods: int) -> Optional[int]:
    for i in range(n_periods):
        if estimation_window(i, estimation, n_periods) is not None:
            if estimation["mode"] == "full_sample":
                return 0
            return i
    return None


def rebalance_indices(policy: Dict[str, Any], estimation: Dict[str, Any],
                      n_periods: int) -> List[int]:
    """Deterministic decision indices (bounded; infeasible ones excluded
    later per-rebalance rather than silently shifted)."""
    first = first_feasible_index(estimation, n_periods)
    if policy["kind"] == "fixed_timestamps":
        indices = policy["indices"]
    elif policy["kind"] == "every_n":
        if first is None:
            return []
        indices = list(range(first, n_periods, policy["every_n"]))
    else:  # one_time
        indices = [] if first is None else [first]
    if len(indices) > MAX_REBALANCES:
        raise PortfolioInputError(
            f"at most {MAX_REBALANCES} rebalances are supported "
            f"({len(indices)} scheduled)")
    return indices


def one_way_turnover(prev: Optional[Dict[str, float]],
                     new: Dict[str, float],
                     policy: str) -> Optional[float]:
    """0.5 × Σ|Δw|; None when no prior book exists under policy 'none'."""
    if prev is None:
        if policy == "zero_book":
            return 0.5 * sum(abs(v) for v in new.values())
        return None
    keys = set(prev) | set(new)
    return 0.5 * sum(abs(new.get(k, 0.0) - prev.get(k, 0.0)) for k in keys)


def drift_weights(weights: Dict[str, float],
                  asset_ids: List[str],
                  returns_matrix: List[List[float]],
                  start: int,
                  end: int) -> Optional[Dict[str, float]]:
    """Drift target weights through periods ``start .. end-1``.

    Cash is the explicit residual ``1 - sum(weights)`` and earns zero in
    v1. A non-positive or non-finite portfolio value makes the pre-trade
    book unavailable rather than fabricating normalized weights.
    """
    current = {a: float(weights.get(a, 0.0)) for a in asset_ids}
    for t in range(start, end):
        period_return = sum(
            current[a] * returns_matrix[i][t]
            for i, a in enumerate(asset_ids)
        )
        next_value = 1.0 + period_return
        if not math.isfinite(next_value) or next_value <= 0:
            return None
        current = {
            a: current[a] * (1.0 + returns_matrix[i][t]) / next_value
            for i, a in enumerate(asset_ids)
        }
        if any(not math.isfinite(v) for v in current.values()):
            return None
    return current


def portfolio_returns(rebalances: List[Dict[str, Any]],
                      asset_ids: List[str],
                      returns_matrix: List[List[float]],
                      n_periods: int) -> List[Optional[float]]:
    """Realized portfolio return series under the recorded weights.

    Weights effective at decision index i govern periods i .. next-1 (the
    weights were estimated from data through i-lag <= i-1, so period i is
    never used in its own weights).  Periods before the first effective
    rebalance are None (honestly unavailable, never zero-filled).
    """
    out: List[Optional[float]] = [None] * n_periods
    targets = {
        r["decision_index"]: r["weights"] for r in rebalances
        if r.get("weights") is not None
    }
    current: Optional[Dict[str, float]] = None
    for t in range(n_periods):
        if t in targets:
            current = {a: float(targets[t].get(a, 0.0)) for a in asset_ids}
        if current is None:
            continue
        total = sum(
            current[a] * returns_matrix[k][t]
            for k, a in enumerate(asset_ids)
        )
        if not math.isfinite(total) or 1.0 + total <= 0:
            current = None
            continue
        out[t] = total
        current = {
            a: current[a] * (1.0 + returns_matrix[k][t]) / (1.0 + total)
            for k, a in enumerate(asset_ids)
        }
    return out
