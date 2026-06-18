"""
Cross-sectional portfolio engine: rebalance scheduling, lookahead-safe P&L,
turnover-based transaction costs, exposures, diagnostics, and a latest-date
ranking preview.
"""

from __future__ import annotations

import math
from datetime import date
from typing import List, Optional, Tuple

import numpy as np

from app.scanner.metrics import portfolio_metrics
from app.scanner.neutralize import dollar_neutral_weights
from app.scanner.sample_data import generate_sample_universe
from app.scanner.signals import momentum_score, reversal_score

STRATEGIES = ("cross_sectional_reversal", "cross_sectional_momentum")
REBALANCE_FREQUENCIES = ("daily", "weekly", "monthly")

_MIN_ASSETS = 5
_MAX_ASSETS = 500
_MAX_DATES = 6000
_RANKING_CAP = 100  # never return the full N×A matrix; cap the ranking preview
_SERIES_CAP = 1500  # downsample chart series beyond this many points


class ScannerInputError(ValueError):
    """Raised when scanner inputs are logically invalid."""


def _clean(value: float, digits: int = 6) -> float:
    f = float(value)
    return round(f, digits) if math.isfinite(f) else 0.0


def validate_scanner_inputs(
    strategy: str,
    n_assets: int,
    start_date: str,
    end_date: str,
    lookback_days: int,
    long_quantile: float,
    short_quantile: float,
    rebalance_frequency: str,
    gross_exposure: float,
    cost_bps: float,
    min_liquidity: float,
    seed: Optional[int],
) -> None:
    if strategy not in STRATEGIES:
        raise ScannerInputError(f"strategy must be one of {STRATEGIES}.")
    if not isinstance(n_assets, int) or isinstance(n_assets, bool):
        raise ScannerInputError("n_assets must be an integer.")
    if n_assets < _MIN_ASSETS or n_assets > _MAX_ASSETS:
        raise ScannerInputError(f"n_assets must be between {_MIN_ASSETS} and {_MAX_ASSETS}.")
    if not isinstance(lookback_days, int) or isinstance(lookback_days, bool) or lookback_days < 1:
        raise ScannerInputError("lookback_days must be an integer >= 1.")
    if lookback_days > 252:
        raise ScannerInputError("lookback_days must be no greater than 252.")
    if not (0.0 < long_quantile < 0.5):
        raise ScannerInputError("long_quantile must be between 0 and 0.5 (exclusive).")
    if not (0.0 < short_quantile < 0.5):
        raise ScannerInputError("short_quantile must be between 0 and 0.5 (exclusive).")
    if not math.isfinite(gross_exposure) or gross_exposure <= 0 or gross_exposure > 10:
        raise ScannerInputError("gross_exposure must be between 0 and 10.")
    if not math.isfinite(cost_bps) or cost_bps < 0 or cost_bps > 1000:
        raise ScannerInputError("cost_bps must be between 0 and 1000.")
    if rebalance_frequency not in REBALANCE_FREQUENCIES:
        raise ScannerInputError(f"rebalance_frequency must be one of {REBALANCE_FREQUENCIES}.")
    if not math.isfinite(min_liquidity) or min_liquidity < 0 or min_liquidity > 1:
        raise ScannerInputError("min_liquidity must be between 0 and 1.")
    if seed is not None and (not isinstance(seed, int) or isinstance(seed, bool) or seed < 0):
        raise ScannerInputError("seed must be a non-negative integer.")
    try:
        d0 = date.fromisoformat(start_date)
        d1 = date.fromisoformat(end_date)
    except (ValueError, TypeError):
        raise ScannerInputError("start_date and end_date must be YYYY-MM-DD.")
    if d0 >= d1:
        raise ScannerInputError("start_date must be before end_date.")


def compute_rebalance_indices(date_index, first_valid: int, frequency: str) -> List[int]:
    """Indices (from ``first_valid``) on which to rebalance, by calendar group."""
    valid = range(first_valid, len(date_index))
    if frequency == "daily":
        return list(valid)
    seen = set()
    result: List[int] = []
    for t in valid:
        d = date_index[t]
        if frequency == "weekly":
            iso = d.isocalendar()
            key = (iso[0], iso[1])
        else:  # monthly
            key = (d.year, d.month)
        if key not in seen:
            seen.add(key)
            result.append(t)
    return result


def gross_returns_from_weights(weights: np.ndarray, returns: np.ndarray) -> np.ndarray:
    """Lookahead-safe portfolio gross returns: ``g[k] = weights[k-1] · returns[k]``.

    Weights decided at *k-1* (from information through *k-1*) earn the return
    realized from *k-1* to *k*. ``g[0] = 0`` (no prior weights).
    """
    g = np.zeros(returns.shape[0])
    g[1:] = np.sum(weights[:-1] * returns[1:], axis=1)
    return g


def _downsample(values: List, cap: int) -> List[int]:
    n = len(values)
    if n <= cap:
        return list(range(n))
    return sorted({round(i * (n - 1) / (cap - 1)) for i in range(cap)})


def run_scanner_backtest(
    strategy: str,
    n_assets: int = 50,
    start_date: str = "2022-01-01",
    end_date: str = "2024-12-31",
    lookback_days: int = 5,
    long_quantile: float = 0.2,
    short_quantile: float = 0.2,
    rebalance_frequency: str = "daily",
    gross_exposure: float = 1.0,
    cost_bps: float = 5.0,
    min_liquidity: float = 0.0,
    seed: Optional[int] = 42,
) -> dict:
    """Run the cross-sectional scanner backtest and return a JSON-ready dict."""
    validate_scanner_inputs(
        strategy, n_assets, start_date, end_date, lookback_days, long_quantile,
        short_quantile, rebalance_frequency, gross_exposure, cost_bps, min_liquidity, seed,
    )

    uni = generate_sample_universe(n_assets, start_date, end_date, seed if seed is not None else 42)
    prices = uni["prices"]
    returns = uni["returns"]
    dates = uni["dates"]
    date_index = uni["date_index"]
    tickers = uni["tickers"]
    sectors = uni["sectors"]
    liquidity = uni["liquidity"]
    n_dates, n_cols = prices.shape

    if n_dates > _MAX_DATES:
        raise ScannerInputError("date range is too long; choose a shorter window.")
    if lookback_days >= n_dates:
        raise ScannerInputError("lookback_days is too long for the chosen date range.")

    scores = reversal_score(prices, lookback_days) if strategy == "cross_sectional_reversal" else momentum_score(prices, lookback_days)

    liq_mask_asset = liquidity >= min_liquidity if min_liquidity > 0 else np.ones(n_cols, dtype=bool)

    first_valid = lookback_days
    reb_indices = set(compute_rebalance_indices(date_index, first_valid, rebalance_frequency))

    weights = np.zeros((n_dates, n_cols))
    prev_w = np.zeros(n_cols)
    skipped = 0
    n_long_hist: List[int] = []
    n_short_hist: List[int] = []
    reb_used: List[int] = []
    warnings: List[str] = []

    for t in range(n_dates):
        if t in reb_indices:
            row = scores[t]
            eligible = np.isfinite(row) & liq_mask_asset
            w, n_long, n_short, ok = dollar_neutral_weights(
                row, eligible, long_quantile, short_quantile, gross_exposure
            )
            if ok:
                prev_w = w
                n_long_hist.append(n_long)
                n_short_hist.append(n_short)
                reb_used.append(t)
            else:
                skipped += 1
        weights[t] = prev_w

    if not reb_used:
        warnings.append(
            "No valid rebalance dates: the eligible universe was too small (after the lookback "
            "and liquidity filter) to form long/short baskets. Try more assets, a smaller "
            "lookback, or a lower minimum liquidity."
        )

    # Turnover (trade at date t to move into weights[t]); weights[-1] = 0 (from cash).
    turnover = np.zeros(n_dates)
    turnover[0] = float(np.sum(np.abs(weights[0])))
    turnover[1:] = np.sum(np.abs(weights[1:] - weights[:-1]), axis=1)
    cost = turnover * (cost_bps / 1e4)

    gross_ret = gross_returns_from_weights(weights, returns)
    net_ret = np.zeros(n_dates)
    # The position weights[k-1] earns gross_ret[k]; its establishment cost was paid at k-1.
    net_ret[1:] = gross_ret[1:] - cost[:-1]

    # Series aligned to the return days (dates[1:]).
    series_dates = dates[1:]
    net_series = net_ret[1:]
    gross_series = gross_ret[1:]
    equity = np.cumprod(1.0 + net_series) if net_series.size else np.array([])
    peak = np.maximum.accumulate(equity) if equity.size else np.array([])
    drawdown = (equity / peak - 1.0) if equity.size else np.array([])

    metrics = portfolio_metrics(net_series)

    # Exposures over time (from the held weights at each date).
    gross_exp = np.sum(np.abs(weights), axis=1)
    net_exp = np.sum(weights, axis=1)
    long_exp = np.sum(np.where(weights > 0, weights, 0.0), axis=1)
    short_exp = np.sum(np.where(weights < 0, weights, 0.0), axis=1)

    # Averages over the dates a basket was actually held.
    held = np.array(sorted(reb_used)) if reb_used else np.array([], dtype=int)
    avg_turnover = float(np.mean([turnover[t] for t in reb_used])) if reb_used else 0.0
    avg_gross = float(np.mean(gross_exp[held])) if held.size else 0.0
    avg_net = float(np.mean(net_exp[held])) if held.size else 0.0
    avg_longs = float(np.mean(n_long_hist)) if n_long_hist else 0.0
    avg_shorts = float(np.mean(n_short_hist)) if n_short_hist else 0.0

    # Chart-ready series (downsampled if very long).
    idx = _downsample(series_dates, _SERIES_CAP)
    equity_curve = [
        {"date": series_dates[i], "equity": _clean(float(equity[i])), "drawdown": _clean(float(drawdown[i]))}
        for i in idx
    ] if equity.size else []
    returns_series = [
        {"date": series_dates[i], "gross": _clean(float(gross_series[i])), "net": _clean(float(net_series[i]))}
        for i in idx
    ]
    # Exposure / turnover aligned to the same return days (weights/turnover at t+1).
    exposures = [
        {
            "date": series_dates[i],
            "gross": _clean(float(gross_exp[i + 1])),
            "net": _clean(float(net_exp[i + 1])),
            "long": _clean(float(long_exp[i + 1])),
            "short": _clean(float(short_exp[i + 1])),
        }
        for i in idx
    ]
    turnover_series = [
        {"date": series_dates[i], "turnover": _clean(float(turnover[i + 1]))}
        for i in idx
    ]

    latest_ranking, latest_date = _build_latest_ranking(
        reb_used, scores, weights, tickers, sectors, dates
    )

    if skipped > 0:
        warnings.append(
            f"{skipped} rebalance date(s) were skipped (insufficient eligible names or no "
            "cross-sectional signal); the previous basket was carried forward."
        )
    warnings.append(
        "Synthetic sample universe for workflow demonstration — not live market data. The "
        "synthetic returns include a mild short-term reversal component for illustration; this "
        "is not evidence the strategy works on real markets."
    )
    warnings.append(
        "Signals are shifted forward one period before P&L is computed (weights at t earn the "
        "return from t to t+1) — no lookahead. Results ignore survivorship bias, point-in-time "
        "data issues, market impact, borrow costs, and capacity."
    )

    return {
        "strategy": strategy,
        "summary": {
            "total_return": _clean(metrics["total_return"]),
            "annualized_return": _clean(metrics["annualized_return"]),
            "annualized_volatility": _clean(metrics["annualized_volatility"]),
            "sharpe": _clean(metrics["sharpe"]),
            "max_drawdown": _clean(metrics["max_drawdown"]),
            "average_turnover": _clean(avg_turnover),
            "average_gross_exposure": _clean(avg_gross),
            "average_net_exposure": _clean(avg_net),
            "average_num_longs": _clean(avg_longs),
            "average_num_shorts": _clean(avg_shorts),
        },
        "equity_curve": equity_curve,
        "returns": returns_series,
        "exposures": exposures,
        "turnover": turnover_series,
        "latest_ranking": latest_ranking,
        "latest_rebalance_date": latest_date,
        "diagnostics": {
            "n_assets": n_assets,
            "n_dates": int(n_dates),
            "valid_rebalance_dates": len(reb_used),
            "skipped_dates": int(skipped),
            "gross_exposure_target": _clean(gross_exposure),
            "cost_bps": _clean(cost_bps),
            "rebalance_frequency": rebalance_frequency,
            "lookback_days": int(lookback_days),
            "warnings": warnings,
        },
    }


def _build_latest_ranking(
    reb_used: List[int],
    scores: np.ndarray,
    weights: np.ndarray,
    tickers: List[str],
    sectors: List[str],
    dates: List[str],
) -> Tuple[List[dict], Optional[str]]:
    """Ranked preview (capped) of the most recent rebalance date."""
    if not reb_used:
        return [], None
    t = max(reb_used)
    row = scores[t]
    w = weights[t]
    order = np.argsort(-np.where(np.isfinite(row), row, -np.inf), kind="stable")
    ranking: List[dict] = []
    for rank, i in enumerate(order, start=1):
        if not np.isfinite(row[i]):
            continue
        wi = float(w[i])
        side = "long" if wi > 0 else "short" if wi < 0 else "neutral"
        ranking.append(
            {
                "rank": rank,
                "ticker": tickers[i],
                "sector": sectors[i],
                "score": _clean(float(row[i])),
                "side": side,
                "weight": _clean(wi),
            }
        )
        if len(ranking) >= _RANKING_CAP:
            break
    return ranking, dates[t]
