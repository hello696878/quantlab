"""
AFML labeling-demo orchestrator: synthetic path → CUSUM events → triple-barrier
labels → concurrency → uniqueness weights → JSON-ready, downsampled payload.
"""

from __future__ import annotations

import math
from typing import List, Optional

import numpy as np

from app.finml.cusum import THRESHOLD_MODES, cusum_events
from app.finml.labeling import triple_barrier_labels
from app.finml.metrics import label_summary
from app.finml.sample_data import generate_synthetic_path
from app.finml.uniqueness import average_uniqueness, compute_concurrency, sample_weights

_MIN_DAYS = 50
_MAX_DAYS = 5000
_SERIES_CAP = 1200  # downsample price / concurrency series for charts
_EVENT_CAP = 1000


class FinmlInputError(ValueError):
    """Raised when AFML methodology inputs are logically invalid."""


def _clean(value: float, digits: int = 6) -> float:
    f = float(value)
    return round(f, digits) if math.isfinite(f) else 0.0


def validate_finml_inputs(
    n_days: int,
    start_price: float,
    drift: float,
    volatility: float,
    seed: Optional[int],
    cusum_threshold: float,
    threshold_mode: str,
    volatility_window: int,
    profit_take_multiple: float,
    stop_loss_multiple: float,
    vertical_barrier_days: int,
) -> None:
    if not isinstance(n_days, int) or isinstance(n_days, bool) or n_days < _MIN_DAYS or n_days > _MAX_DAYS:
        raise FinmlInputError(f"n_days must be an integer between {_MIN_DAYS} and {_MAX_DAYS}.")
    if not math.isfinite(start_price) or start_price <= 0:
        raise FinmlInputError("start_price must be positive.")
    if not math.isfinite(drift) or abs(drift) > 1.0:
        raise FinmlInputError("drift must be finite and within ±1.0.")
    if not math.isfinite(volatility) or volatility <= 0 or volatility > 1.0:
        raise FinmlInputError("volatility must be between 0 and 1.0.")
    if cusum_threshold is None or not math.isfinite(cusum_threshold) or cusum_threshold <= 0:
        raise FinmlInputError("cusum_threshold must be positive.")
    if threshold_mode not in THRESHOLD_MODES:
        raise FinmlInputError(f"threshold_mode must be one of {THRESHOLD_MODES}.")
    if not isinstance(volatility_window, int) or isinstance(volatility_window, bool) or volatility_window < 2:
        raise FinmlInputError("volatility_window must be an integer >= 2.")
    if volatility_window >= n_days:
        raise FinmlInputError("volatility_window must be smaller than n_days.")
    if not math.isfinite(profit_take_multiple) or profit_take_multiple <= 0:
        raise FinmlInputError("profit_take_multiple must be positive.")
    if not math.isfinite(stop_loss_multiple) or stop_loss_multiple <= 0:
        raise FinmlInputError("stop_loss_multiple must be positive.")
    if not isinstance(vertical_barrier_days, int) or isinstance(vertical_barrier_days, bool) or vertical_barrier_days < 1:
        raise FinmlInputError("vertical_barrier_days must be an integer >= 1.")
    if vertical_barrier_days >= n_days:
        raise FinmlInputError("vertical_barrier_days must be smaller than n_days.")
    if seed is not None and (not isinstance(seed, int) or isinstance(seed, bool) or seed < 0):
        raise FinmlInputError("seed must be a non-negative integer.")


def _downsample(n: int, cap: int) -> List[int]:
    if n <= cap:
        return list(range(n))
    return sorted({round(i * (n - 1) / (cap - 1)) for i in range(cap)})


def run_labeling_demo(
    n_days: int = 500,
    start_price: float = 100.0,
    drift: float = 0.0002,
    volatility: float = 0.015,
    seed: Optional[int] = 42,
    cusum_threshold: float = 0.02,
    threshold_mode: str = "fixed",
    volatility_window: int = 20,
    profit_take_multiple: float = 1.5,
    stop_loss_multiple: float = 1.0,
    vertical_barrier_days: int = 10,
) -> dict:
    """Run the full CUSUM → triple-barrier → uniqueness demo as a JSON-ready dict."""
    validate_finml_inputs(
        n_days, start_price, drift, volatility, seed, cusum_threshold, threshold_mode,
        volatility_window, profit_take_multiple, stop_loss_multiple, vertical_barrier_days,
    )

    path = generate_synthetic_path(
        n_days, start_price, drift, volatility, seed if seed is not None else 42, volatility_window
    )
    dates = path["dates"]
    close = path["close"]
    returns = path["returns"]
    rolling_vol = path["rolling_vol"]

    raw_events = cusum_events(returns, cusum_threshold, threshold_mode, rolling_vol)
    labels = triple_barrier_labels(
        close, [e["index"] for e in raw_events], rolling_vol,
        profit_take_multiple, stop_loss_multiple, vertical_barrier_days,
    )

    intervals = [(l["start_index"], l["end_index"]) for l in labels]
    concurrency = compute_concurrency(n_days, intervals)
    uniqueness = average_uniqueness(intervals, concurrency)
    weights = sample_weights(uniqueness)

    summary = label_summary(labels, uniqueness, n_days)

    warnings: List[str] = [
        "Synthetic path for methodology demonstration — not live market data.",
        "This is a labeling pipeline, not a trained model: no features, no model, no out-of-sample "
        "validation. Event formation uses no future information; future prices are only used to "
        "assign labels (as labeling requires). The separate Purged CV demo provides overlap-aware "
        "split diagnostics; CPCV, meta-labeling, sequential bootstrap, and fractional "
        "differentiation are planned, not implemented.",
    ]
    if summary["n_events"] == 0:
        warnings.append(
            "No events were sampled: the CUSUM threshold may be too high for this path. Lower the "
            "threshold or increase volatility / n_days."
        )
    dropped_unlabeled = len(raw_events) - len(labels)
    if dropped_unlabeled > 0:
        warnings.append(
            f"{dropped_unlabeled} final-bar event(s) were dropped because no forward price window "
            "was available for triple-barrier labeling."
        )
    truncated = sum(1 for l in labels if l["start_index"] + vertical_barrier_days >= n_days)
    if truncated > 0:
        warnings.append(
            f"{truncated} event(s) near the end of the synthetic path used a shortened vertical "
            "barrier at the data boundary."
        )
    if len(labels) > _EVENT_CAP:
        warnings.append(
            f"Label, event, and weight tables are capped at {_EVENT_CAP} rows in the response; "
            "summary counts are computed from all labeled events."
        )
    if threshold_mode == "vol_scaled":
        warnings.append(
            "Vol-scaled CUSUM mode interprets cusum_threshold as a multiplier of the rolling "
            "volatility estimate, not as a fixed percentage return."
        )

    # ── Chart-ready, downsampled / capped payloads ────────────────────────────
    pidx = _downsample(n_days, _SERIES_CAP)
    price_series = [
        {"date": dates[i], "close": _clean(float(close[i]), 4), "volatility": _clean(float(rolling_vol[i]))}
        for i in pidx
    ]
    concurrency_series = [
        {"date": dates[i], "concurrency": int(concurrency[i])} for i in pidx
    ]

    # Align the events list to labeled events (a final-bar CUSUM event with no
    # forward window cannot be labeled and is dropped) so all counts agree.
    event_by_index = {e["index"]: e for e in raw_events}
    events_out = [
        {
            "event_id": l["event_id"],
            "date": dates[l["start_index"]],
            "side_hint": event_by_index[l["start_index"]]["side"],
            "threshold_used": _clean(event_by_index[l["start_index"]]["threshold_used"]),
            "return_at_event": _clean(event_by_index[l["start_index"]]["return_at_event"]),
            "price_at_event": _clean(l["start_price"], 4),
        }
        for l in labels[:_EVENT_CAP]
    ]
    labels_out = [
        {
            "event_id": l["event_id"],
            "start_date": dates[l["start_index"]],
            "end_date": dates[l["end_index"]],
            "start_price": _clean(l["start_price"], 4),
            "end_price": _clean(l["end_price"], 4),
            "target_return": _clean(l["target_return"]),
            "upper_barrier": _clean(l["upper_barrier"], 4),
            "lower_barrier": _clean(l["lower_barrier"], 4),
            "label": l["label"],
            "touched_barrier": l["touched_barrier"],
            "realized_return": _clean(l["realized_return"]),
            "holding_period_days": l["holding_period_days"],
        }
        for l in labels[:_EVENT_CAP]
    ]
    weights_out = [
        {
            "event_id": labels[i]["event_id"],
            "label": labels[i]["label"],
            "average_uniqueness": _clean(uniqueness[i]),
            "sample_weight": _clean(weights[i]),
        }
        for i in range(min(len(labels), _EVENT_CAP))
    ]

    return {
        "summary": summary,
        "parameters": {
            "n_days": n_days,
            "cusum_threshold": _clean(cusum_threshold),
            "threshold_mode": threshold_mode,
            "volatility_window": volatility_window,
            "profit_take_multiple": _clean(profit_take_multiple),
            "stop_loss_multiple": _clean(stop_loss_multiple),
            "vertical_barrier_days": vertical_barrier_days,
        },
        "price_series": price_series,
        "events": events_out,
        "labels": labels_out,
        "concurrency": concurrency_series,
        "weights": weights_out,
        "warnings": warnings,
    }
