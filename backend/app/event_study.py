"""
Event-Driven / Arbitrage research v1 — event-study abnormal returns (CAR/CAAR)
and a simplified merger-arbitrage calculator.

Educational / research only.  This is **not** a live event scanner, an SEC
filing parser, a complete corporate-action database, or a merger-arbitrage desk:

* Event studies depend on clean, point-in-time **event dates**, the benchmark
  choice, information leakage before the announcement, confounding events,
  liquidity, transaction costs, and survivorship bias.
* The merger-arb calculator is a simplified expected-value model — it ignores
  borrow/financing costs, regulatory timing, competing bids, taxes, liquidity,
  and detailed deal terms.

The functions here are **pure** (they operate on price ``pandas.Series``); the
API route fetches prices through the app's data seam and passes them in, so the
math is fully testable offline.  All outputs are finite — never NaN/inf.
"""

from __future__ import annotations

import math
from datetime import date
from typing import List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

ABNORMAL_RETURN_MODELS = ("market_adjusted", "mean_adjusted", "market_model")
MIN_ESTIMATION_OBS = 20  # below this, mean/market-model baselines are unreliable

# Synthetic sample events — demo workflow only, NOT a curated event database.
SAMPLE_EVENTS = [
    {"event_name": "AAPL earnings (sample)", "ticker": "AAPL", "benchmark_ticker": "SPY", "event_date": "2024-05-02"},
    {"event_name": "MSFT earnings (sample)", "ticker": "MSFT", "benchmark_ticker": "SPY", "event_date": "2024-04-25"},
    {"event_name": "NVDA event (sample)", "ticker": "NVDA", "benchmark_ticker": "SPY", "event_date": "2024-05-22"},
    {"event_name": "SPY macro event (sample)", "ticker": "SPY", "benchmark_ticker": "QQQ", "event_date": "2024-05-01"},
]


class EventInputError(ValueError):
    """Raised when event-study / merger-arb inputs are structurally invalid."""


def _clean(value: Optional[float], digits: int = 6) -> Optional[float]:
    if value is None:
        return None
    f = float(value)
    return round(f, digits) if math.isfinite(f) else None


# ---------------------------------------------------------------------------
# Returns / window alignment
# ---------------------------------------------------------------------------


def compute_returns(close: pd.Series) -> pd.Series:
    """Simple daily returns from a close-price series (first NaN dropped)."""
    returns = close.astype(float).pct_change().dropna()
    return returns


def align_event_window(
    asset_returns: pd.Series,
    event_date: str,
    pre_event_days: int,
    post_event_days: int,
) -> Tuple[int, pd.Timestamp, List[str]]:
    """Locate the event in the return index.

    Returns ``(event_pos, actual_event_date, warnings)``.  If the requested date
    is not a trading day, the next available trading day is used (with a warning).
    """
    warnings: List[str] = []
    idx = asset_returns.index
    target = pd.Timestamp(event_date)

    # First trading day on or after the requested date.
    on_or_after = idx[idx >= target]
    if len(on_or_after) == 0:
        raise EventInputError(
            "The event date is after the available price history; no post-event data."
        )
    actual = on_or_after[0]
    if actual != target:
        warnings.append(
            f"Event date {target.date()} is not a trading day in the data; using the next "
            f"available trading day {actual.date()}."
        )
    event_pos = idx.get_loc(actual)
    if isinstance(event_pos, slice) or not isinstance(event_pos, (int, np.integer)):
        # Defensive: duplicate timestamps shouldn't happen after data cleaning.
        event_pos = int(np.atleast_1d(np.where(idx == actual)[0])[0])

    if event_pos < pre_event_days:
        warnings.append(
            f"Only {event_pos} trading day(s) available before the event; requested "
            f"{pre_event_days}. The pre-event window was truncated."
        )
    if (len(idx) - 1 - event_pos) < post_event_days:
        warnings.append(
            f"Only {len(idx) - 1 - event_pos} trading day(s) available after the event; "
            f"requested {post_event_days}. The post-event window was truncated."
        )
    return int(event_pos), actual, warnings


# ---------------------------------------------------------------------------
# Abnormal returns
# ---------------------------------------------------------------------------


def _market_model_fit(
    asset_est: np.ndarray, bench_est: np.ndarray
) -> Tuple[float, float]:
    """OLS alpha/beta of asset on benchmark over the estimation window."""
    var = float(np.var(bench_est))
    if var <= 1e-15:
        return float(np.mean(asset_est)), 0.0
    beta = float(np.cov(asset_est, bench_est, ddof=0)[0, 1] / var)
    alpha = float(np.mean(asset_est) - beta * np.mean(bench_est))
    return alpha, beta


def compute_abnormal_returns(
    asset_window: pd.Series,
    benchmark_window: Optional[pd.Series],
    model: str,
    asset_estimation: pd.Series,
    benchmark_estimation: Optional[pd.Series],
) -> Tuple[pd.Series, dict, List[str]]:
    """Abnormal returns over the event window under the chosen model.

    Returns ``(abnormal_returns, model_info, warnings)``.  Falls back gracefully
    to ``mean_adjusted`` when a benchmark is required but unavailable.
    """
    warnings: List[str] = []
    model_info: dict = {"model_used": model, "alpha": None, "beta": None,
                        "estimation_obs": int(len(asset_estimation))}

    has_benchmark = benchmark_window is not None and len(benchmark_window) > 0
    needs_benchmark = model in ("market_adjusted", "market_model")
    if needs_benchmark and not has_benchmark:
        warnings.append(
            f"Benchmark returns are unavailable; falling back from '{model}' to "
            "'mean_adjusted'."
        )
        model = "mean_adjusted"
        model_info["model_used"] = "mean_adjusted"

    if model == "market_adjusted":
        abnormal = asset_window - benchmark_window  # type: ignore[operator]
    elif model == "mean_adjusted":
        if len(asset_estimation) < MIN_ESTIMATION_OBS:
            warnings.append(
                f"Estimation window has {len(asset_estimation)} observations "
                f"(< {MIN_ESTIMATION_OBS}); the mean baseline may be unreliable."
            )
        baseline = float(asset_estimation.mean()) if len(asset_estimation) else 0.0
        abnormal = asset_window - baseline
    elif model == "market_model":
        if (
            len(asset_estimation) < MIN_ESTIMATION_OBS
            or benchmark_estimation is None
            or len(benchmark_estimation) < MIN_ESTIMATION_OBS
        ):
            warnings.append(
                "Insufficient estimation observations for a market-model fit; "
                "falling back to 'market_adjusted'."
            )
            model_info["model_used"] = "market_adjusted"
            abnormal = asset_window - benchmark_window  # type: ignore[operator]
        else:
            alpha, beta = _market_model_fit(
                asset_estimation.to_numpy(), benchmark_estimation.to_numpy()
            )
            model_info["alpha"] = _clean(alpha)
            model_info["beta"] = _clean(beta)
            abnormal = asset_window - (alpha + beta * benchmark_window)  # type: ignore[operator]
    else:
        raise EventInputError(f"Unknown abnormal-return model '{model}'.")

    return abnormal, model_info, warnings


def compute_car(abnormal_returns: Sequence[float]) -> List[float]:
    """Cumulative abnormal return = running sum of abnormal returns."""
    total = 0.0
    out: List[float] = []
    for ar in abnormal_returns:
        total += float(ar)
        out.append(total)
    return out


# ---------------------------------------------------------------------------
# Single-event study
# ---------------------------------------------------------------------------


def validate_event_inputs(
    estimation_window_days: int, pre_event_days: int, post_event_days: int, model: str
) -> None:
    if model not in ABNORMAL_RETURN_MODELS:
        raise EventInputError(f"model must be one of {ABNORMAL_RETURN_MODELS}.")
    if estimation_window_days < 10 or estimation_window_days > 500:
        raise EventInputError("estimation_window_days must be between 10 and 500.")
    if pre_event_days < 1 or pre_event_days > 120:
        raise EventInputError("pre_event_days must be between 1 and 120.")
    if post_event_days < 1 or post_event_days > 120:
        raise EventInputError("post_event_days must be between 1 and 120.")


def run_single_event_study(
    asset_close: pd.Series,
    benchmark_close: Optional[pd.Series],
    event_date: str,
    estimation_window_days: int = 120,
    pre_event_days: int = 10,
    post_event_days: int = 10,
    model: str = "market_adjusted",
    event_name: str = "",
) -> dict:
    """Run an event study on pre-fetched price series. Pure (no network)."""
    validate_event_inputs(estimation_window_days, pre_event_days, post_event_days, model)

    asset_returns = compute_returns(asset_close)
    if len(asset_returns) < 2:
        raise EventInputError("Not enough asset price history to compute returns.")

    benchmark_returns: Optional[pd.Series] = None
    warnings: List[str] = []
    if benchmark_close is not None:
        benchmark_returns = compute_returns(benchmark_close)
        # Align asset & benchmark on common trading days.
        asset_returns, benchmark_returns = asset_returns.align(benchmark_returns, join="inner")
        if len(asset_returns) < 2:
            benchmark_returns = None
            warnings.append("Asset and benchmark share too few common dates; benchmark ignored.")

    event_pos, actual_event, win_warnings = align_event_window(
        asset_returns, event_date, pre_event_days, post_event_days
    )
    warnings.extend(win_warnings)

    n = len(asset_returns)
    win_start = max(0, event_pos - pre_event_days)
    win_end = min(n - 1, event_pos + post_event_days)
    est_end = win_start  # estimation window ends just before the event window
    est_start = max(0, est_end - estimation_window_days)

    asset_window = asset_returns.iloc[win_start : win_end + 1]
    asset_estimation = asset_returns.iloc[est_start:est_end]
    bench_window = benchmark_returns.iloc[win_start : win_end + 1] if benchmark_returns is not None else None
    bench_estimation = benchmark_returns.iloc[est_start:est_end] if benchmark_returns is not None else None

    if len(asset_estimation) == 0 and model != "market_adjusted":
        warnings.append("No estimation-window data before the event window; results may be unreliable.")

    abnormal, model_info, ar_warnings = compute_abnormal_returns(
        asset_window, bench_window, model, asset_estimation, bench_estimation
    )
    warnings.extend(ar_warnings)

    car = compute_car(abnormal.to_numpy())

    rows: List[dict] = []
    for i, (ts, ar) in enumerate(abnormal.items()):
        pos = win_start + i
        rel = pos - event_pos
        bench_ret = float(bench_window.iloc[i]) if bench_window is not None else None
        rows.append(
            {
                "relative_day": int(rel),
                "date": ts.date().isoformat(),
                "asset_return": _clean(float(asset_window.iloc[i])),
                "benchmark_return": _clean(bench_ret),
                "abnormal_return": _clean(float(ar)),
                "cumulative_abnormal_return": _clean(car[i]),
            }
        )

    # Summary segments by relative day.
    rel_days = [r["relative_day"] for r in rows]
    ar_by_rel = {r["relative_day"]: (r["abnormal_return"] or 0.0) for r in rows}
    event_day_ar = ar_by_rel.get(0)
    pre_car = sum(ar_by_rel[d] for d in rel_days if d < 0)
    post_car = sum(ar_by_rel[d] for d in rel_days if d > 0)
    total_car = car[-1] if car else 0.0

    return {
        "event_name": event_name,
        "ticker": asset_close.name if asset_close.name else "",
        "model": model,
        "model_used": model_info["model_used"],
        "alpha": model_info["alpha"],
        "beta": model_info["beta"],
        "estimation_obs": model_info["estimation_obs"],
        "rows": rows,
        "summary": {
            "event_day_abnormal_return": _clean(event_day_ar),
            "pre_event_car": _clean(pre_car),
            "post_event_car": _clean(post_car),
            "total_car": _clean(total_car),
            "window_start": rows[0]["date"] if rows else None,
            "window_end": rows[-1]["date"] if rows else None,
            "actual_event_date": actual_event.date().isoformat(),
            "warnings": warnings,
        },
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Multi-event study (CAAR)
# ---------------------------------------------------------------------------


def run_multi_event_study(events_results: Sequence[dict]) -> dict:
    """Aggregate single-event results into average AR (AAR) and CAAR by relative day."""
    # Collect abnormal returns aligned by relative day across events.
    by_rel: dict = {}
    for res in events_results:
        for row in res["rows"]:
            rel = row["relative_day"]
            ar = row["abnormal_return"]
            if ar is None:
                continue
            by_rel.setdefault(rel, []).append(ar)

    rel_days = sorted(by_rel.keys())
    aar_points: List[dict] = []
    running = 0.0
    for rel in rel_days:
        values = by_rel[rel]
        aar = sum(values) / len(values)
        running += aar
        aar_points.append(
            {
                "relative_day": rel,
                "average_abnormal_return": _clean(aar),
                "average_cumulative_abnormal_return": _clean(running),
                "event_count": len(values),
            }
        )

    per_event = [
        {
            "event_name": res["event_name"],
            "ticker": res["ticker"],
            "actual_event_date": res["summary"]["actual_event_date"],
            "total_car": res["summary"]["total_car"],
        }
        for res in events_results
    ]
    cars = [res["summary"]["total_car"] for res in events_results if res["summary"]["total_car"] is not None]
    return {
        "event_count": len(events_results),
        "per_event": per_event,
        "aar_curve": aar_points,
        "average_total_car": _clean(sum(cars) / len(cars)) if cars else None,
    }


# ---------------------------------------------------------------------------
# Merger arbitrage calculator
# ---------------------------------------------------------------------------


def compute_merger_arb_metrics(
    current_price: float,
    offer_price: float,
    downside_price: float,
    probability_close: float,
    expected_days_to_close: float,
) -> dict:
    """Simplified merger-arb expected-value metrics. Pure, no market data."""
    if not all(math.isfinite(float(x)) for x in
               (current_price, offer_price, downside_price, probability_close, expected_days_to_close)):
        raise EventInputError("All merger-arb inputs must be finite.")
    if current_price <= 0:
        raise EventInputError("current_price must be positive.")
    if offer_price <= 0:
        raise EventInputError("offer_price must be positive.")
    if downside_price < 0:
        raise EventInputError("downside_price must be non-negative.")
    if not (0.0 <= probability_close <= 1.0):
        raise EventInputError("probability_close must be between 0 and 1.")
    if expected_days_to_close <= 0:
        raise EventInputError("expected_days_to_close must be positive.")

    spread = offer_price - current_price
    gross_upside_pct = spread / current_price
    downside_pct = (downside_price - current_price) / current_price
    expected_exit = probability_close * offer_price + (1.0 - probability_close) * downside_price
    expected_return = (expected_exit - current_price) / current_price
    years = expected_days_to_close / 365.0
    annualized = (1.0 + expected_return) ** (1.0 / years) - 1.0 if (1.0 + expected_return) > 0 else None

    breakeven = None
    if abs(offer_price - downside_price) > 1e-12:
        breakeven = (current_price - downside_price) / (offer_price - downside_price)

    return {
        "spread": _clean(spread),
        "gross_upside_pct": _clean(gross_upside_pct),
        "downside_pct": _clean(downside_pct),
        "expected_exit_price": _clean(expected_exit),
        "expected_return": _clean(expected_return),
        "annualized_expected_return": _clean(annualized) if annualized is not None else None,
        "downside_loss_pct": _clean(downside_pct),
        "breakeven_probability": _clean(breakeven) if breakeven is not None else None,
        "warnings": [
            "Simplified expected-value model — ignores borrow/financing costs, regulatory "
            "timing, competing bids, taxes, liquidity, and detailed deal terms.",
        ],
    }
