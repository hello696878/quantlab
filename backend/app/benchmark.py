"""
Benchmark / active-performance analytics engine (research v1).

Compares a strategy's equity curve against a reference asset on **date-aligned
returns** (inner join).  Modes:

* ``buy_and_hold_same_asset`` — the engine's built-in costless benchmark of the
  strategy's own asset (default; no extra fetch, perfectly aligned).
* ``custom_ticker``           — buy-and-hold of another ticker, fetched through
  the same provider seam, normalized to the strategy's starting capital on the
  shared dates.
* ``none``                    — no analytics block.

Definitions (risk-free rate = 0 for v1; ``ppy`` = periods/year from the
annualization engine):

* active return     = strategy_return − benchmark_return (per aligned period)
* tracking error    = std(active) × √ppy
* information ratio = mean(active) × ppy ÷ tracking error
* beta              = cov(strategy, benchmark) ÷ var(benchmark)
* alpha             = (mean(strategy) − beta × mean(benchmark)) × ppy
* correlation       = Pearson on aligned returns

Anything not computable (zero variance, zero tracking error, too little
overlap) is **null plus a warning** — never NaN/inf, never a crash.  Benchmark
analytics never change strategy trades, equity, or metrics.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

import pandas as pd

from app.metrics import compute_metrics
from app.schemas import (
    ActiveMetrics,
    BenchmarkAnalytics,
    BenchmarkConfig,
    BenchmarkEquityPoint,
    BenchmarkMetricsBlock,
    DataQuality,
)

# Below this many aligned return observations, active metrics are unreliable
# enough that we return nulls + a warning instead.
_MIN_ALIGNED_POINTS = 10

# Warn when the benchmark covers less than this fraction of strategy dates.
_OVERLAP_WARN_FRACTION = 0.8

_VAR_EPS = 1e-18
_TE_EPS = 1e-12


def _clean(value: float, digits: int = 6) -> Optional[float]:
    """Round for JSON; null out NaN/inf."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return round(f, digits) if math.isfinite(f) else None


def normalize_config(config: Optional[BenchmarkConfig]) -> BenchmarkConfig:
    """Missing benchmark config → buy-and-hold same asset (matches the engine)."""
    return config if config is not None else BenchmarkConfig(mode="buy_and_hold_same_asset")


def compute_active_metrics(
    strategy_equity: pd.Series,
    benchmark_equity: pd.Series,
    periods_per_year: int,
) -> Tuple[ActiveMetrics, List[str]]:
    """Active metrics on the date-aligned intersection of the two curves."""
    warnings: List[str] = []
    common = strategy_equity.index.intersection(benchmark_equity.index)

    if len(common) < _MIN_ALIGNED_POINTS:
        warnings.append(
            f"Only {len(common)} aligned data point(s) between strategy and "
            "benchmark — active metrics are not computable."
        )
        return ActiveMetrics(aligned_points=int(len(common))), warnings

    strat_eq = strategy_equity.loc[common]
    bench_eq = benchmark_equity.loc[common]

    strat_ret = strat_eq.pct_change().dropna()
    bench_ret = bench_eq.pct_change().dropna()
    active = strat_ret - bench_ret

    strat_total = float(strat_eq.iloc[-1] / strat_eq.iloc[0]) - 1.0
    bench_total = float(bench_eq.iloc[-1] / bench_eq.iloc[0]) - 1.0
    n_years = len(strat_ret) / periods_per_year
    excess_cagr = None
    if n_years > 0 and strat_eq.iloc[0] > 0 and bench_eq.iloc[0] > 0:
        strat_cagr = float(strat_eq.iloc[-1] / strat_eq.iloc[0]) ** (1.0 / n_years) - 1.0
        bench_cagr = float(bench_eq.iloc[-1] / bench_eq.iloc[0]) ** (1.0 / n_years) - 1.0
        excess_cagr = strat_cagr - bench_cagr

    bench_var = float(bench_ret.var())
    strat_var = float(strat_ret.var())

    beta = None
    alpha = None
    correlation = None
    if not math.isfinite(bench_var) or bench_var < _VAR_EPS:
        warnings.append("Benchmark returns have zero variance; beta, alpha, and correlation are not computable.")
    else:
        beta_val = float(strat_ret.cov(bench_ret)) / bench_var
        beta = beta_val
        alpha = (float(strat_ret.mean()) - beta_val * float(bench_ret.mean())) * periods_per_year
        if strat_var < _VAR_EPS:
            warnings.append("Strategy returns have zero variance; correlation is not computable.")
        else:
            correlation = float(strat_ret.corr(bench_ret))

    te = float(active.std()) * math.sqrt(periods_per_year)
    information_ratio = None
    if not math.isfinite(te) or te < _TE_EPS:
        te = 0.0
        warnings.append("Tracking error is zero; the information ratio is not computable.")
    else:
        information_ratio = float(active.mean()) * periods_per_year / te

    return (
        ActiveMetrics(
            excess_total_return=_clean(strat_total - bench_total),
            excess_cagr=_clean(excess_cagr) if excess_cagr is not None else None,
            alpha=_clean(alpha) if alpha is not None else None,
            beta=_clean(beta, 4) if beta is not None else None,
            correlation=_clean(correlation, 4) if correlation is not None else None,
            tracking_error=_clean(te),
            information_ratio=_clean(information_ratio, 4)
            if information_ratio is not None
            else None,
            aligned_points=int(len(common)),
        ),
        warnings,
    )


def metrics_block(equity: pd.Series, periods_per_year: int) -> BenchmarkMetricsBlock:
    """Benchmark metrics via the shared metrics engine + annualization convention."""
    m = compute_metrics(equity, periods_per_year=periods_per_year)
    return BenchmarkMetricsBlock(
        total_return=float(m["total_return"]),
        cagr=float(m["cagr"]),
        volatility=float(m["volatility"]),
        sharpe=float(m["sharpe_ratio"]),
        max_drawdown=float(m["max_drawdown"]),
    )


def build_benchmark_analytics(
    *,
    config: BenchmarkConfig,
    strategy_ticker: str,
    strategy_equity: pd.Series,
    same_asset_benchmark_equity: pd.Series,
    periods_per_year: int,
    initial_capital: float,
    custom_close: Optional[pd.Series] = None,
    custom_fetch_error: Optional[str] = None,
    custom_data_provider: Optional[str] = None,
    custom_data_quality: Optional[DataQuality] = None,
) -> Optional[BenchmarkAnalytics]:
    """Assemble the benchmark block for a single-asset backtest (None for 'none')."""
    if config.mode == "none":
        return None

    if config.mode == "buy_and_hold_same_asset":
        active, warnings = compute_active_metrics(
            strategy_equity, same_asset_benchmark_equity, periods_per_year
        )
        return BenchmarkAnalytics(
            mode=config.mode,
            ticker=strategy_ticker.upper(),
            display_name=f"Buy & Hold {strategy_ticker.upper()}",
            metrics=metrics_block(same_asset_benchmark_equity, periods_per_year),
            active_metrics=active,
            equity_curve=None,  # already on the response equity_curve
            warnings=warnings,
        )

    # custom_ticker
    ticker = (config.ticker or "").upper()
    if custom_close is None or len(custom_close) == 0:
        return BenchmarkAnalytics(
            mode=config.mode,
            ticker=ticker,
            display_name=f"Buy & Hold {ticker}",
            metrics=None,
            active_metrics=None,
            data_provider=custom_data_provider,
            data_quality=custom_data_quality,
            warnings=[
                custom_fetch_error
                or f"Benchmark data for '{ticker}' is unavailable; benchmark analytics were skipped."
            ],
        )

    warnings: List[str] = []
    common = strategy_equity.index.intersection(custom_close.index)
    if len(common) < 2:
        return BenchmarkAnalytics(
            mode=config.mode,
            ticker=ticker,
            display_name=f"Buy & Hold {ticker}",
            metrics=None,
            active_metrics=None,
            data_provider=custom_data_provider,
            data_quality=custom_data_quality,
            warnings=[
                f"Benchmark '{ticker}' has no overlapping dates with the strategy "
                "period; benchmark analytics are not computable."
            ],
        )
    if len(common) < _OVERLAP_WARN_FRACTION * len(strategy_equity):
        warnings.append(
            f"Benchmark '{ticker}' overlaps only {len(common)} of "
            f"{len(strategy_equity)} strategy dates — active metrics use the "
            "aligned subset only."
        )

    bench_close = custom_close.loc[common]
    bench_equity = bench_close / float(bench_close.iloc[0]) * float(initial_capital)
    active, active_warnings = compute_active_metrics(
        strategy_equity, bench_equity, periods_per_year
    )
    warnings.extend(active_warnings)

    curve = [
        BenchmarkEquityPoint(
            date=str(d.date()) if hasattr(d, "date") else str(d),
            equity=round(float(v), 2),
        )
        for d, v in zip(bench_equity.index, bench_equity)
    ]

    return BenchmarkAnalytics(
        mode=config.mode,
        ticker=ticker,
        display_name=f"Buy & Hold {ticker}",
        metrics=metrics_block(bench_equity, periods_per_year),
        active_metrics=active,
        equity_curve=curve,
        data_provider=custom_data_provider,
        data_quality=custom_data_quality,
        warnings=warnings,
    )
