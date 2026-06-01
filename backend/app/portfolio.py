"""
Multi-asset portfolio backtesting (v1).

Equal-weight, long-only, fully-invested portfolio with optional periodic
rebalancing.  Pure computation only — price fetching and HTTP concerns live in
the API layer (``main.py``); metrics reuse ``app.metrics.compute_metrics``.

This is intentionally simple: no optimisation, no shorting, no leverage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from app.metrics import compute_metrics

REBALANCE_FREQUENCIES = ("none", "monthly", "quarterly", "yearly")
OPTIMIZATION_OBJECTIVES = ("equal_weight", "min_volatility", "max_sharpe")
TRADING_DAYS_PER_YEAR = 252
_MIN_VOL = 1e-12


def _date_str(ts) -> str:
    return str(ts.date()) if hasattr(ts, "date") else str(ts)


def _period_key(ts: pd.Timestamp, freq: str):
    """Calendar bucket for a timestamp; rebalancing fires when this changes."""
    if freq == "monthly":
        return (ts.year, ts.month)
    if freq == "quarterly":
        return (ts.year, (ts.month - 1) // 3)
    if freq == "yearly":
        return (ts.year,)
    return None  # "none" → never rebalance


def align_prices(frames: Dict[str, pd.Series]) -> pd.DataFrame:
    """
    Combine per-ticker close series into one frame on their COMMON dates.

    Columns preserve the insertion order of *frames* (i.e. request ticker
    order).  Any date where at least one asset is missing is dropped.
    """
    cleaned = {}
    for ticker, series in frames.items():
        # Keep the last observation for duplicate dates and enforce chronological
        # order before return calculation.
        s = series.copy()
        s.index = pd.to_datetime(s.index)
        s = s.sort_index()
        s = s.groupby(level=0).last()
        cleaned[ticker] = s

    df = pd.DataFrame(cleaned)  # union index, NaN where an asset is missing
    df = df.dropna(how="any")   # keep only fully-populated (common) dates
    return df


def drawdown_series(equity: pd.Series) -> pd.Series:
    """Running peak-to-trough drawdown as a fraction (≤ 0)."""
    peak = equity.cummax()
    return (equity - peak) / peak


def _validate_price_frame(prices: pd.DataFrame) -> None:
    if len(prices.columns) == 0:
        raise ValueError("prices must contain at least one ticker column.")
    if len(prices) < 2:
        raise ValueError("prices must contain at least two common dates.")
    if prices.isna().any().any():
        raise ValueError("prices must not contain missing values.")
    if not np.isfinite(prices.to_numpy(dtype=float)).all():
        raise ValueError("prices must be finite.")
    if (prices <= 0).any().any():
        raise ValueError("prices must be strictly positive.")


@dataclass
class PortfolioResult:
    equity: pd.Series                       # portfolio value per date
    weights: List[dict] = field(default_factory=list)            # [{date, weights}]
    rebalance_events: List[dict] = field(default_factory=list)   # [{date, turnover, cost}]


def run_equal_weight_portfolio(
    prices: pd.DataFrame,
    *,
    initial_capital: float = 100_000.0,
    rebalance_frequency: str = "none",
    transaction_cost_bps: float = 10.0,
) -> PortfolioResult:
    """
    Simulate an equal-weight, long-only, fully-invested portfolio.

    Convention
    ----------
    * Day 0: capital is split equally across the N assets (``equity[0] ==
      initial_capital``; no initial transaction cost is charged).
    * Each subsequent day, holdings drift with each asset's daily return.
    * ``rebalance_frequency`` of monthly/quarterly/yearly resets the holdings to
      equal weight on the FIRST trading day of each new period.  The cost of a
      rebalance is turnover-based:

          turnover = sum_i | target_weight_i - drifted_weight_i |
          cost     = equity_before * turnover * (transaction_cost_bps / 10000)

      and is deducted from portfolio value that day.
    * ``"none"`` never rebalances — weights drift for the whole period.

    Returns daily equity, per-day weights, and the list of rebalance events.
    """
    tickers = list(prices.columns)
    n = len(tickers)
    _validate_price_frame(prices)

    dates = prices.index
    returns = prices.pct_change(fill_method=None)
    cost_rate = transaction_cost_bps / 10_000.0
    target_w = 1.0 / n

    # Dollar holdings per asset — drift naturally captures weight changes.
    holdings: Dict[str, float] = {t: initial_capital / n for t in tickers}

    equity_vals: List[float] = [float(sum(holdings.values()))]  # == initial_capital
    weights: List[dict] = [
        {"date": _date_str(dates[0]), "weights": {t: round(target_w, 6) for t in tickers}}
    ]
    rebalance_events: List[dict] = []

    last_key = _period_key(dates[0], rebalance_frequency)

    for i in range(1, len(dates)):
        ts = dates[i]

        # 1) Drift holdings by today's asset returns.
        for t in tickers:
            r = returns[t].iloc[i]
            holdings[t] *= 1.0 + (0.0 if pd.isna(r) else float(r))

        equity_before = float(sum(holdings.values()))

        # 2) Rebalance on the first trading day of a new period.
        do_rebalance = False
        if rebalance_frequency != "none":
            key = _period_key(ts, rebalance_frequency)
            if key != last_key:
                do_rebalance = True
                last_key = key

        if do_rebalance and equity_before > 0:
            old_w = {t: holdings[t] / equity_before for t in tickers}
            turnover = float(sum(abs(target_w - old_w[t]) for t in tickers))
            cost = equity_before * turnover * cost_rate
            equity_after = equity_before - cost
            for t in tickers:
                holdings[t] = equity_after / n
            rebalance_events.append(
                {
                    "date": _date_str(ts),
                    "turnover": round(turnover, 6),
                    "cost": round(cost, 2),
                }
            )
            equity_vals.append(equity_after)
            weights.append(
                {"date": _date_str(ts), "weights": {t: round(target_w, 6) for t in tickers}}
            )
        else:
            equity_vals.append(equity_before)
            if equity_before > 0:
                wdict = {t: round(holdings[t] / equity_before, 6) for t in tickers}
            else:
                wdict = {t: 0.0 for t in tickers}
            weights.append({"date": _date_str(ts), "weights": wdict})

    equity = pd.Series(equity_vals, index=dates, name="portfolio")
    return PortfolioResult(
        equity=equity, weights=weights, rebalance_events=rebalance_events
    )


# ===========================================================================
# Portfolio optimization (v1, in-sample, long-only)
# ===========================================================================


def annualized_stats(prices: pd.DataFrame):
    """
    Compute annualised expected returns and the annualised covariance matrix
    from daily simple returns.

    Returns
    -------
    (expected_returns, covariance) : (pd.Series, pd.DataFrame)
        Both annualised with a 252-trading-day convention.
    """
    _validate_price_frame(prices)
    daily = prices.pct_change(fill_method=None).dropna(how="any")
    if len(daily) < 2:
        raise ValueError(
            "Need at least 2 daily returns (3 common dates) to estimate "
            "covariance."
        )
    if not np.isfinite(daily.to_numpy(dtype=float)).all():
        raise ValueError("daily returns must be finite.")
    expected_returns = daily.mean() * TRADING_DAYS_PER_YEAR
    covariance = daily.cov() * TRADING_DAYS_PER_YEAR
    if not np.isfinite(expected_returns.to_numpy(dtype=float)).all():
        raise ValueError("expected returns must be finite.")
    if not np.isfinite(covariance.to_numpy(dtype=float)).all():
        raise ValueError("covariance matrix must be finite.")
    return expected_returns, covariance


def portfolio_stats(weights: Dict[str, float], expected_returns: pd.Series, covariance: pd.DataFrame, risk_free_rate: float = 0.0):
    """Return (annual_return, annual_volatility, sharpe) for a weight vector."""
    tickers = list(expected_returns.index)
    w = np.array([weights[t] for t in tickers], dtype=float)
    mu = expected_returns.to_numpy()
    sigma = covariance.to_numpy()
    annual_return = float(w @ mu)
    annual_vol = float(np.sqrt(max(w @ sigma @ w, 0.0)))
    sharpe = (annual_return - risk_free_rate) / annual_vol if annual_vol > _MIN_VOL else 0.0
    return annual_return, annual_vol, float(sharpe)


def optimize_weights(
    expected_returns: pd.Series,
    covariance: pd.DataFrame,
    objective: str,
    risk_free_rate: float = 0.0,
) -> Dict[str, float]:
    """
    Solve for long-only weights (w_i >= 0, sum(w) = 1) under one objective.

    * ``equal_weight``    — 1/N (closed form).
    * ``min_volatility``  — minimise w'Σw (convex QP on the simplex).
    * ``max_sharpe``      — maximise (w'μ − rf) / sqrt(w'Σw).

    Uses SLSQP from an equal-weight start.  Tiny negative artefacts are clipped
    and the result is renormalised to sum to exactly 1.
    """
    if objective not in OPTIMIZATION_OBJECTIVES:
        raise ValueError(f"Unsupported objective: {objective!r}.")

    tickers = list(expected_returns.index)
    n = len(tickers)
    mu = expected_returns.to_numpy()
    sigma = covariance.to_numpy()
    if n == 0:
        raise ValueError("expected_returns must contain at least one asset.")
    if list(covariance.index) != tickers or list(covariance.columns) != tickers:
        raise ValueError("covariance matrix must align with expected_returns.")
    if not np.isfinite(mu).all() or not np.isfinite(sigma).all():
        raise ValueError("expected returns and covariance must be finite.")

    # Equal weight (and the trivial single-asset case) is closed-form.
    if objective == "equal_weight" or n == 1:
        return {t: 1.0 / n for t in tickers}

    equal_w = np.full(n, 1.0 / n)
    equal_vol = float(np.sqrt(max(equal_w @ sigma @ equal_w, 0.0)))
    if objective == "max_sharpe" and equal_vol <= _MIN_VOL:
        return {t: 1.0 / n for t in tickers}

    x0 = equal_w
    bounds = [(0.0, 1.0)] * n
    constraints = ({"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0)},)

    if objective == "min_volatility":
        def cost(w):
            return float(w @ sigma @ w)  # variance is monotonic in volatility
    else:  # max_sharpe → minimise the negative Sharpe ratio
        def cost(w):
            vol = float(np.sqrt(max(w @ sigma @ w, 0.0)))
            if vol <= _MIN_VOL:
                return 1e6
            return -((w @ mu - risk_free_rate) / vol)

    result = minimize(
        cost,
        x0,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 1000, "ftol": 1e-10},
    )
    if not result.success:
        raise ValueError(f"Portfolio optimization failed: {result.message}")
    if not np.isfinite(result.x).all():
        raise ValueError("Portfolio optimization produced non-finite weights.")

    w = np.clip(np.asarray(result.x, dtype=float), 0.0, None)
    total = w.sum()
    if total <= _MIN_VOL:
        raise ValueError("Portfolio optimization produced zero total weight.")
    w = w / total
    # Full precision so the weights sum to 1 (rounding for display happens at
    # the API serialization boundary).
    return {t: float(wi) for t, wi in zip(tickers, w)}


def buy_and_hold_equity(
    prices: pd.DataFrame, weights: Dict[str, float], initial_capital: float
) -> pd.Series:
    """
    Buy-and-hold equity curve for a fixed starting weight vector.

    Capital is allocated to the target weights on day 0 and then left to drift
    (no rebalancing).  ``equity[0] == initial_capital`` because the weights sum
    to 1.
    """
    _validate_price_frame(prices)
    w = np.array([weights[t] for t in prices.columns], dtype=float)
    if not np.isfinite(w).all():
        raise ValueError("weights must be finite.")
    if (w < -1e-12).any():
        raise ValueError("weights must be non-negative.")
    if abs(float(w.sum()) - 1.0) > 1e-6:
        raise ValueError("weights must sum to 1.")
    normalized = prices.to_numpy() / prices.to_numpy()[0]
    equity = initial_capital * (normalized @ w)
    return pd.Series(equity, index=prices.index, name="portfolio")


# ===========================================================================
# Walk-forward portfolio optimization (rolling, out-of-sample)
# ===========================================================================


@dataclass
class WalkForwardResult:
    windows: List[dict]               # per-window train/test detail
    stitched_equity: pd.Series        # optimized OOS equity (anchored at capital)
    benchmark_equity: pd.Series       # equal-weight OOS equity (same dates)
    weight_stability: dict            # turnover + per-asset weight summary


def run_walk_forward_optimization(
    prices: pd.DataFrame,
    *,
    train_window_days: int,
    test_window_days: int,
    step_days: int,
    objective: str,
    risk_free_rate: float = 0.0,
    initial_capital: float = 100_000.0,
    transaction_cost_bps: float = 10.0,
) -> WalkForwardResult:
    """
    Rolling walk-forward optimization with strict train/test separation.

    For each window the optimizer sees ONLY the training slice; the resulting
    weights are then applied (held fixed) across the following out-of-sample
    test slice.  Test windows are stitched into one continuous OOS equity curve.

    No leakage
    ----------
    Weights for window *k* are estimated from ``prices[train_start:train_end]``
    and applied to returns dated strictly after ``train_end`` — future test
    data never enters the optimizer.

    Transaction cost convention
    ---------------------------
    At each test-window boundary the portfolio moves from the previous window's
    weights to the new weights:

        turnover = sum_i |new_w_i - prev_w_i|     (prev = 0 for the first window)
        cost     = turnover * transaction_cost_bps / 10000

    The cost is deducted from portfolio equity at the start of that test window
    (a one-off multiplicative drag), before that window's returns compound.
    The equal-weight benchmark is treated identically (its target never changes,
    so it only pays the initial entry turnover).

    When ``step_days < test_window_days``, test windows overlap.  For the
    stitched equity curve each window contributes only the non-overlapping
    step slice, with the final window contributing its remaining full test
    horizon.  The per-window ``test_metrics`` still describe the full requested
    test horizon and include that window's boundary transaction cost.
    """
    for name, value in (
        ("train_window_days", train_window_days),
        ("test_window_days", test_window_days),
        ("step_days", step_days),
    ):
        if not isinstance(value, (int, np.integer)) or int(value) <= 0:
            raise ValueError(f"{name} must be a positive integer.")
    if not np.isfinite(initial_capital) or initial_capital <= 0:
        raise ValueError("initial_capital must be greater than 0.")
    if not np.isfinite(risk_free_rate):
        raise ValueError("risk_free_rate must be finite.")
    if (
        not np.isfinite(transaction_cost_bps)
        or transaction_cost_bps < 0
        or transaction_cost_bps >= 10_000
    ):
        raise ValueError("transaction_cost_bps must be >= 0 and less than 10000.")

    _validate_price_frame(prices)
    n = len(prices)
    tickers = list(prices.columns)
    n_assets = len(tickers)

    if n < train_window_days + test_window_days:
        raise ValueError(
            f"Only {n} common trading days available; need at least "
            f"train_window_days + test_window_days = "
            f"{train_window_days + test_window_days}."
        )

    returns = prices.pct_change(fill_method=None)  # row 0 is NaN (unused)
    cost_rate = transaction_cost_bps / 10_000.0
    equal_w = np.full(n_assets, 1.0 / n_assets)

    # Anchor the stitched curves at the last training day of the first window
    # so both start exactly at initial_capital on a shared date.
    first_test_start = train_window_days
    anchor_date = prices.index[first_test_start - 1]

    opt_equity = float(initial_capital)
    bench_equity = float(initial_capital)
    prev_opt_w = np.zeros(n_assets)
    prev_bench_w = np.zeros(n_assets)

    stitched_dates: List = [anchor_date]
    stitched_opt: List[float] = [opt_equity]
    stitched_bench: List[float] = [bench_equity]
    last_date = anchor_date

    windows: List[dict] = []
    all_weights: List[np.ndarray] = []
    rebalance_turnovers: List[float] = []  # window-to-window (excludes entry)

    train_start = 0
    _SAFETY_CAP = 1000

    while True:
        train_end = train_start + train_window_days
        test_start = train_end
        test_end = test_start + test_window_days
        if test_end > n or len(windows) >= _SAFETY_CAP:
            break

        # ── Estimate + optimize on TRAINING data only ────────────────────────
        train_slice = prices.iloc[train_start:train_end]
        mu, cov = annualized_stats(train_slice)
        w_dict = optimize_weights(mu, cov, objective, risk_free_rate)
        w_vec = np.array([w_dict[t] for t in tickers], dtype=float)
        tr_ret, tr_vol, tr_sharpe = portfolio_stats(w_dict, mu, cov, risk_free_rate)

        # ── Turnover / cost at the boundary ─────────────────────────────────
        turnover = float(np.sum(np.abs(w_vec - prev_opt_w)))
        cost_fraction = turnover * cost_rate
        if cost_fraction >= 1.0:
            raise ValueError(
                "transaction_cost_bps is too high for the optimized turnover; "
                "the boundary cost would deplete portfolio equity."
            )
        cost_dollars = opt_equity * cost_fraction

        bench_turnover = float(np.sum(np.abs(equal_w - prev_bench_w)))
        bench_cost_fraction = bench_turnover * cost_rate
        if bench_cost_fraction >= 1.0:
            raise ValueError(
                "transaction_cost_bps is too high for the benchmark entry "
                "turnover; the boundary cost would deplete benchmark equity."
            )

        # ── OOS daily portfolio returns for this test window ────────────────
        win_returns = returns.iloc[test_start:test_end].to_numpy()
        opt_daily = win_returns @ w_vec
        bench_daily = win_returns @ equal_w

        # Per-window standalone OOS equity for test_metrics (anchored and
        # charged the same one-off boundary cost as the stitched curve).
        running = float(initial_capital)
        win_equity_vals = [running]
        running *= 1.0 - cost_fraction
        for r in opt_daily:
            running *= 1.0 + float(r)
            win_equity_vals.append(running)
        test_metrics = compute_metrics(pd.Series(win_equity_vals))

        # ── Apply boundary cost, then stitch the OOS days ───────────────────
        next_train_start = train_start + step_days
        has_next_full_window = (
            next_train_start + train_window_days + test_window_days <= n
        )
        contribution_end = (
            min(test_end, test_start + step_days) if has_next_full_window else test_end
        )
        contrib_returns = returns.iloc[test_start:contribution_end].to_numpy()
        contrib_opt_daily = contrib_returns @ w_vec
        contrib_bench_daily = contrib_returns @ equal_w
        contrib_dates = prices.index[test_start:contribution_end]

        opt_equity *= 1.0 - cost_fraction
        bench_equity *= 1.0 - bench_cost_fraction
        for dt, r_opt, r_bench in zip(contrib_dates, contrib_opt_daily, contrib_bench_daily):
            if dt <= last_date:
                continue  # defensive deduplication if callers pass odd indexes
            opt_equity *= 1.0 + float(r_opt)
            bench_equity *= 1.0 + float(r_bench)
            stitched_dates.append(dt)
            stitched_opt.append(opt_equity)
            stitched_bench.append(bench_equity)
            last_date = dt

        windows.append(
            {
                "train_start_date": _date_str(prices.index[train_start]),
                "train_end_date": _date_str(prices.index[train_end - 1]),
                "test_start_date": _date_str(prices.index[test_start]),
                "test_end_date": _date_str(prices.index[test_end - 1]),
                "weights": w_dict,
                "train_expected_return": tr_ret,
                "train_volatility": tr_vol,
                "train_sharpe": tr_sharpe,
                "test_metrics": test_metrics,
                "turnover": turnover,
                "transaction_cost": cost_dollars,
            }
        )
        all_weights.append(w_vec)
        if len(windows) > 1:
            rebalance_turnovers.append(turnover)

        prev_opt_w = w_vec
        prev_bench_w = equal_w
        train_start += step_days

    if not windows:
        raise ValueError(
            "No walk-forward windows could be formed; widen the date range or "
            "reduce the window sizes."
        )

    stitched_equity = pd.Series(stitched_opt, index=stitched_dates, name="portfolio")
    benchmark_equity = pd.Series(stitched_bench, index=stitched_dates, name="benchmark")

    weight_matrix = np.array(all_weights)  # (num_windows, n_assets)
    weight_stability = {
        "average_turnover": float(np.mean(rebalance_turnovers)) if rebalance_turnovers else 0.0,
        "max_turnover": float(np.max(rebalance_turnovers)) if rebalance_turnovers else 0.0,
        "average_weight_by_asset": {
            t: float(weight_matrix[:, j].mean()) for j, t in enumerate(tickers)
        },
        "min_weight_by_asset": {
            t: float(weight_matrix[:, j].min()) for j, t in enumerate(tickers)
        },
        "max_weight_by_asset": {
            t: float(weight_matrix[:, j].max()) for j, t in enumerate(tickers)
        },
    }

    return WalkForwardResult(
        windows=windows,
        stitched_equity=stitched_equity,
        benchmark_equity=benchmark_equity,
        weight_stability=weight_stability,
    )


# ===========================================================================
# Efficient frontier (risk–return space, long-only, in-sample)
# ===========================================================================


def portfolio_point(
    weights: Dict[str, float],
    expected_returns: pd.Series,
    covariance: pd.DataFrame,
    risk_free_rate: float = 0.0,
) -> dict:
    """A single risk/return/Sharpe point with its weights (for the frontier)."""
    ret, vol, sharpe = portfolio_stats(weights, expected_returns, covariance, risk_free_rate)
    return {
        "expected_return": ret,
        "volatility": vol,
        "sharpe": sharpe,
        "weights": {t: float(weights[t]) for t in expected_returns.index},
    }


def _moment_arrays(expected_returns: pd.Series, covariance: pd.DataFrame):
    """Validate and return aligned moment arrays for frontier calculations."""
    tickers = list(expected_returns.index)
    if not tickers:
        raise ValueError("expected_returns must contain at least one asset.")
    if list(covariance.index) != tickers or list(covariance.columns) != tickers:
        raise ValueError("covariance matrix must align with expected_returns.")
    mu = expected_returns.to_numpy(dtype=float)
    sigma = covariance.to_numpy(dtype=float)
    if not np.isfinite(mu).all() or not np.isfinite(sigma).all():
        raise ValueError("expected returns and covariance must be finite.")
    if not np.allclose(sigma, sigma.T, rtol=1e-10, atol=1e-12):
        raise ValueError("covariance matrix must be symmetric.")
    return tickers, mu, sigma


def random_portfolios(
    expected_returns: pd.Series,
    covariance: pd.DataFrame,
    num_portfolios: int,
    risk_free_rate: float = 0.0,
    seed: int = 42,
) -> List[dict]:
    """
    Sample ``num_portfolios`` long-only portfolios uniformly from the simplex
    (Dirichlet(1,…,1)) and compute their annualised return / volatility /
    Sharpe.  Deterministic for a fixed ``seed``.
    """
    if not isinstance(num_portfolios, (int, np.integer)) or int(num_portfolios) <= 0:
        raise ValueError("num_portfolios must be a positive integer.")
    if not np.isfinite(risk_free_rate):
        raise ValueError("risk_free_rate must be finite.")

    tickers, mu, sigma = _moment_arrays(expected_returns, covariance)
    n = len(tickers)

    rng = np.random.default_rng(seed)
    weights = rng.dirichlet(np.ones(n), size=num_portfolios)  # (num, n), rows sum to 1

    rets = weights @ mu
    variances = np.einsum("ij,jk,ik->i", weights, sigma, weights).clip(min=0.0)
    vols = np.sqrt(variances)
    sharpes = np.zeros_like(rets, dtype=float)
    nonzero_vol = vols > _MIN_VOL
    sharpes[nonzero_vol] = (rets[nonzero_vol] - risk_free_rate) / vols[nonzero_vol]

    portfolios: List[dict] = []
    for i in range(num_portfolios):
        portfolios.append(
            {
                "expected_return": float(rets[i]),
                "volatility": float(vols[i]),
                "sharpe": float(sharpes[i]),
                "weights": {t: float(weights[i, j]) for j, t in enumerate(tickers)},
            }
        )
    return portfolios


def efficient_frontier_points(
    expected_returns: pd.Series,
    covariance: pd.DataFrame,
    num_points: int = 50,
) -> List[dict]:
    """
    Trace the long-only efficient frontier: for a grid of target returns,
    minimise volatility subject to ``w'μ >= target``, ``sum(w) = 1``, ``w >= 0``.

    The plotted frontier starts at the global minimum-volatility portfolio and
    moves toward the highest-return long-only portfolio.  Points where the
    optimizer fails to converge are skipped.
    """
    if not isinstance(num_points, (int, np.integer)) or int(num_points) <= 0:
        raise ValueError("num_points must be a positive integer.")

    _, mu, sigma = _moment_arrays(expected_returns, covariance)
    n = len(mu)

    if n == 1:
        return [
            {
                "expected_return": float(mu[0]),
                "volatility": float(np.sqrt(max(sigma[0, 0], 0.0))),
            }
        ]

    # Degenerate case: all expected returns equal → frontier is a single point.
    if float(mu.max() - mu.min()) <= _MIN_VOL:
        w = optimize_weights(expected_returns, covariance, "min_volatility")
        ret, vol, _ = portfolio_stats(w, expected_returns, covariance)
        return [{"expected_return": ret, "volatility": vol}]

    min_vol_weights = optimize_weights(expected_returns, covariance, "min_volatility")
    min_ret, min_vol, _ = portfolio_stats(
        min_vol_weights, expected_returns, covariance
    )
    hi = float(mu.max())
    if hi - min_ret <= _MIN_VOL:
        return [{"expected_return": min_ret, "volatility": min_vol}]

    bounds = [(0.0, 1.0)] * n
    points: List[dict] = []
    seen: set[tuple[float, float]] = set()
    for target in np.linspace(min_ret, hi, num_points):
        constraints = (
            {"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0)},
            {"type": "ineq", "fun": lambda w, t=target: float(w @ mu - t)},  # w'μ >= t
        )
        result = minimize(
            lambda w: float(w @ sigma @ w),
            np.full(n, 1.0 / n),
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 500, "ftol": 1e-10},
        )
        if not result.success or not np.isfinite(result.x).all():
            continue
        w = np.clip(np.asarray(result.x, dtype=float), 0.0, None)
        total = w.sum()
        if total <= _MIN_VOL:
            continue
        w = w / total
        ret = float(w @ mu)
        vol = float(np.sqrt(max(w @ sigma @ w, 0.0)))
        if not np.isfinite(ret) or not np.isfinite(vol):
            continue
        if ret + 1e-8 < float(target):
            continue
        key = (round(ret, 12), round(vol, 12))
        if key in seen:
            continue
        seen.add(key)
        points.append({"expected_return": ret, "volatility": vol})

    points.sort(key=lambda p: p["volatility"])
    return points


# ===========================================================================
# Portfolio risk dashboard (asset- and portfolio-level diagnostics)
# ===========================================================================


def risk_dashboard(prices: pd.DataFrame) -> dict:
    """
    Compute asset- and portfolio-level risk diagnostics from a price frame.

    Returns a dict with annualised per-asset returns/volatilities, the
    correlation and (annualised) covariance matrices, equal-weight portfolio
    risk, correlation diagnostics, and the equal-weight percent risk
    contributions.  All annualisation uses 252 trading days.

    Raises ``ValueError`` for an invalid / too-short price frame.
    """
    _validate_price_frame(prices)
    tickers = list(prices.columns)
    n = len(tickers)

    daily = prices.pct_change(fill_method=None).dropna(how="any")
    if len(daily) < 2:
        raise ValueError(
            "Need at least 2 daily returns (3 common dates) to estimate risk "
            "statistics."
        )
    if not np.isfinite(daily.to_numpy(dtype=float)).all():
        raise ValueError("daily returns must be finite.")

    annual_returns = daily.mean() * TRADING_DAYS_PER_YEAR
    annual_vols = daily.std() * np.sqrt(TRADING_DAYS_PER_YEAR)
    correlation = daily.corr()
    covariance = daily.cov() * TRADING_DAYS_PER_YEAR
    if not np.isfinite(annual_returns.to_numpy(dtype=float)).all():
        raise ValueError("annualized returns must be finite.")
    if not np.isfinite(annual_vols.to_numpy(dtype=float)).all():
        raise ValueError("annualized volatilities must be finite.")
    if not np.isfinite(covariance.to_numpy(dtype=float)).all():
        raise ValueError("covariance matrix must be finite.")

    # Zero-variance assets make pairwise correlations mathematically undefined
    # in pandas (NaN).  For display diagnostics, keep diagonal self-correlation
    # at 1 and treat undefined off-diagonal correlations as 0 rather than
    # leaking non-JSON values into the API response.
    corr_arr = correlation.to_numpy(dtype=float)
    corr_arr = np.where(np.isfinite(corr_arr), corr_arr, 0.0)
    np.fill_diagonal(corr_arr, 1.0)
    corr_arr = np.clip((corr_arr + corr_arr.T) / 2.0, -1.0, 1.0)
    correlation = pd.DataFrame(corr_arr, index=tickers, columns=tickers)

    cov_arr = covariance.to_numpy(dtype=float)
    covariance = pd.DataFrame((cov_arr + cov_arr.T) / 2.0, index=tickers, columns=tickers)

    # ── Equal-weight portfolio risk ──────────────────────────────────────
    w = np.full(n, 1.0 / n)
    sigma = covariance.to_numpy(dtype=float)
    vols_vec = annual_vols.to_numpy(dtype=float)

    port_return = float(w @ annual_returns.to_numpy(dtype=float))
    port_var = float(w @ sigma @ w)
    port_vol = float(np.sqrt(max(port_var, 0.0)))

    weighted_avg_vol = float(w @ vols_vec)
    diversification_ratio = (
        weighted_avg_vol / port_vol if port_vol > _MIN_VOL else 0.0
    )

    # ── Risk contribution (equal weight) ─────────────────────────────────
    if port_vol > _MIN_VOL:
        marginal = sigma @ w / port_vol          # ∂σ_p/∂w_i
        component = w * marginal                  # component risk (sums to σ_p)
        percent = component / port_vol            # fraction of total risk (sums to 1)
        risk_contribution = {
            t: float(percent[i]) for i, t in enumerate(tickers)
        }
    else:
        risk_contribution = {t: float(w[i]) for i, t in enumerate(tickers)}

    # ── Correlation diagnostics (off-diagonal pairs) ─────────────────────
    diagnostics: dict = {
        "average_pairwise_correlation": 0.0,
        "max_pairwise_correlation": 0.0,
        "min_pairwise_correlation": 0.0,
        "most_correlated_pair": None,
        "least_correlated_pair": None,
    }
    if n >= 2:
        corr = correlation.to_numpy(dtype=float)
        pair_values: List[float] = []
        most_pair = (tickers[0], tickers[1])
        least_pair = (tickers[0], tickers[1])
        most_val = -np.inf
        least_val = np.inf
        for i in range(n):
            for j in range(i + 1, n):
                c = float(corr[i, j])
                pair_values.append(c)
                if c > most_val:
                    most_val = c
                    most_pair = (tickers[i], tickers[j])
                if c < least_val:
                    least_val = c
                    least_pair = (tickers[i], tickers[j])
        diagnostics = {
            "average_pairwise_correlation": float(np.mean(pair_values)),
            "max_pairwise_correlation": most_val,
            "min_pairwise_correlation": least_val,
            "most_correlated_pair": [most_pair[0], most_pair[1]],
            "least_correlated_pair": [least_pair[0], least_pair[1]],
        }

    return {
        "tickers": tickers,
        "asset_annual_returns": {t: float(annual_returns[t]) for t in tickers},
        "asset_annual_volatilities": {t: float(annual_vols[t]) for t in tickers},
        "correlation_matrix": {
            ti: {tj: float(correlation.loc[ti, tj]) for tj in tickers}
            for ti in tickers
        },
        "covariance_matrix": {
            ti: {tj: float(covariance.loc[ti, tj]) for tj in tickers}
            for ti in tickers
        },
        "equal_weight_portfolio": {
            "expected_return": port_return,
            "volatility": port_vol,
            "diversification_ratio": float(diversification_ratio),
            "weights": {t: float(w[i]) for i, t in enumerate(tickers)},
        },
        "correlation_diagnostics": diagnostics,
        "risk_contribution": risk_contribution,
    }


# ===========================================================================
# Stress testing / historical scenario analysis
# ===========================================================================


def _scenario_stats(daily_returns: pd.Series, initial_capital: float, anchor_date):
    """
    Build a rebased equity curve + summary stats from a slice of daily returns.

    The curve is anchored at ``initial_capital`` on ``anchor_date`` (the trading
    day before the first counted return), then compounds each daily return.
    Returns ``(equity_series, total_return, max_drawdown, ann_vol, worst, best)``.
    """
    dates = [anchor_date]
    vals = [float(initial_capital)]
    running = float(initial_capital)
    for d, r in daily_returns.items():
        running *= 1.0 + float(r)
        dates.append(d)
        vals.append(running)
    equity = pd.Series(vals, index=dates)

    total_return = float(equity.iloc[-1] / initial_capital - 1.0)
    max_drawdown = float(drawdown_series(equity).min())
    ann_vol = (
        float(daily_returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR))
        if len(daily_returns) >= 2
        else 0.0
    )
    worst = float(daily_returns.min()) if len(daily_returns) else 0.0
    best = float(daily_returns.max()) if len(daily_returns) else 0.0
    return equity, total_return, max_drawdown, ann_vol, worst, best


def _curve_points(equity: pd.Series) -> List[dict]:
    return [
        {"date": _date_str(d), "value": round(float(v), 2)}
        for d, v in zip(equity.index, equity)
    ]


def stress_test(
    prices: pd.DataFrame,
    benchmark_close: pd.Series,
    weights: Dict[str, float],
    scenarios: List[dict],
    initial_capital: float = 100_000.0,
    transaction_cost_bps: float = 0.0,
) -> dict:
    """
    Static-weight, long-only stress test over historical scenario windows.

    The portfolio holds fixed target weights (``portfolio_return[t] = Σ wᵢ·rᵢ``);
    each scenario is sliced from the full daily-return series and rebased to
    ``initial_capital`` for comparison against the benchmark.  No rebalancing or
    leverage; ``transaction_cost_bps`` is accepted for API symmetry but does not
    affect the buy-and-hold curves in v1.

    ``prices`` (aligned, columns = tickers) and ``benchmark_close`` must share
    the same DatetimeIndex.  Raises ``ValueError`` for a scenario that does not
    overlap the data.
    """
    _validate_price_frame(prices)
    tickers = list(prices.columns)
    if set(weights) != set(tickers):
        raise ValueError("weights must include exactly the price frame tickers.")
    w = np.array([weights[t] for t in tickers], dtype=float)
    if not np.isfinite(w).all():
        raise ValueError("weights must be finite.")
    if (w < 0).any():
        raise ValueError("weights must be non-negative (long-only).")
    if abs(float(w.sum()) - 1.0) > 1e-6:
        raise ValueError("weights must sum to 1.")
    if not np.isfinite(initial_capital) or initial_capital <= 0:
        raise ValueError("initial_capital must be greater than 0.")
    if (
        not np.isfinite(transaction_cost_bps)
        or transaction_cost_bps < 0
        or transaction_cost_bps >= 10_000
    ):
        raise ValueError("transaction_cost_bps must be >= 0 and less than 10000.")

    benchmark_close = benchmark_close.copy()
    benchmark_close.index = pd.to_datetime(benchmark_close.index)
    if not benchmark_close.index.equals(prices.index):
        raise ValueError("benchmark_close must share the same index as prices.")
    if benchmark_close.isna().any():
        raise ValueError("benchmark_close must not contain missing values.")
    if not np.isfinite(benchmark_close.to_numpy(dtype=float)).all():
        raise ValueError("benchmark_close must be finite.")
    if (benchmark_close <= 0).any():
        raise ValueError("benchmark_close must be strictly positive.")
    if not scenarios:
        raise ValueError("at least one stress scenario is required.")

    asset_ret = prices.pct_change(fill_method=None)
    port_ret_full = pd.Series(asset_ret.to_numpy() @ w, index=prices.index)
    bench_ret_full = benchmark_close.pct_change(fill_method=None)

    # ── Full-period curves + metrics ─────────────────────────────────────
    full_equity, *_ = _scenario_stats(
        port_ret_full.iloc[1:], initial_capital, prices.index[0]
    )
    bench_equity = initial_capital * (benchmark_close / float(benchmark_close.iloc[0]))
    full_metrics = compute_metrics(full_equity)
    bench_metrics = compute_metrics(bench_equity)

    idx = prices.index
    scenario_results: List[dict] = []

    for scn in scenarios:
        name = scn["name"]
        s = pd.Timestamp(scn["start_date"])
        e = pd.Timestamp(scn["end_date"])
        positions = np.where((idx >= s) & (idx <= e))[0]
        if len(positions) == 0:
            raise ValueError(
                f"Scenario '{name}' ({scn['start_date']} to {scn['end_date']}) "
                f"does not overlap the available data "
                f"({_date_str(idx[0])} to {_date_str(idx[-1])})."
            )
        i0, i1 = int(positions[0]), int(positions[-1])
        ret_start = i0 + 1
        if ret_start > i1:
            raise ValueError(
                f"Scenario '{name}' is too short — no return days inside the window."
            )
        sel = slice(ret_start, i1 + 1)
        anchor_date = idx[i0]

        scn_port = port_ret_full.iloc[sel]
        scn_bench = bench_ret_full.iloc[sel]

        p_eq, p_tr, p_dd, p_vol, p_worst, p_best = _scenario_stats(
            scn_port, initial_capital, anchor_date
        )
        b_eq, b_tr, b_dd, b_vol, b_worst, b_best = _scenario_stats(
            scn_bench, initial_capital, anchor_date
        )

        win_corr = asset_ret.iloc[sel].corr()
        corr_arr = win_corr.to_numpy(dtype=float)
        corr_arr = np.where(np.isfinite(corr_arr), corr_arr, 0.0)
        np.fill_diagonal(corr_arr, 1.0)
        corr_arr = np.clip((corr_arr + corr_arr.T) / 2.0, -1.0, 1.0)
        win_corr = pd.DataFrame(corr_arr, index=tickers, columns=tickers)
        corr_dict = {
            ti: {tj: float(win_corr.loc[ti, tj]) for tj in tickers} for ti in tickers
        }

        scenario_results.append(
            {
                "name": name,
                "start_date": scn["start_date"],
                "end_date": scn["end_date"],
                "total_return": p_tr,
                "max_drawdown": p_dd,
                "annualized_volatility": p_vol,
                "worst_day_return": p_worst,
                "best_day_return": p_best,
                "benchmark_total_return": b_tr,
                "benchmark_max_drawdown": b_dd,
                "benchmark_worst_day_return": b_worst,
                "benchmark_best_day_return": b_best,
                "excess_return": p_tr - b_tr,
                "correlation_matrix": corr_dict,
                "portfolio_equity_curve": _curve_points(p_eq),
                "benchmark_equity_curve": _curve_points(b_eq),
            }
        )

    return {
        "tickers": tickers,
        "full_period_metrics": full_metrics,
        "benchmark_full_period_metrics": bench_metrics,
        "full_equity_curve": _curve_points(full_equity),
        "benchmark_equity_curve": _curve_points(bench_equity),
        "scenarios": scenario_results,
    }


# ===========================================================================
# Factor exposure / OLS regression analysis
# ===========================================================================


def factor_analysis(
    portfolio_prices: pd.DataFrame,
    factor_prices: pd.DataFrame,
    weights: Dict[str, float],
    factor_names: List[str],
    initial_capital: float = 100_000.0,
) -> dict:
    """
    Regress portfolio daily returns on factor (ETF proxy) daily returns by OLS.

        r_p[t] = alpha + Σ_k beta_k · r_factor_k[t] + residual[t]

    Uses ``numpy.linalg.lstsq`` (intercept included) — no statsmodels.  Returns
    alpha (daily + annualised), betas per factor, R², annualised residual
    volatility, fitted/residual series, actual & fitted equity curves, the
    factor correlation matrix, and diagnostics (strongest ± exposures,
    multicollinearity warning).

    ``portfolio_prices`` (columns = tickers) and ``factor_prices`` (columns in
    ``factor_names`` order) must share the same DatetimeIndex.  Raises
    ``ValueError`` for degenerate inputs.
    """
    _validate_price_frame(portfolio_prices)
    tickers = list(portfolio_prices.columns)
    w = np.array([weights[t] for t in tickers], dtype=float)

    # Daily returns (drop the first NaN row jointly).
    asset_ret = portfolio_prices.pct_change(fill_method=None)
    factor_ret_full = factor_prices[factor_names].pct_change(fill_method=None)
    port_ret = pd.Series(asset_ret.to_numpy() @ w, index=portfolio_prices.index)

    combined = pd.concat([port_ret.rename("__port__"), factor_ret_full], axis=1).dropna(how="any")
    if len(combined) < len(factor_names) + 2:
        raise ValueError(
            "Not enough overlapping return observations to fit the regression "
            f"({len(combined)} rows for {len(factor_names)} factors)."
        )

    y = combined["__port__"].to_numpy(dtype=float)
    factor_matrix = combined[factor_names].to_numpy(dtype=float)
    n_obs = len(y)
    k = len(factor_names)

    # Design matrix with an intercept column.
    X = np.column_stack([np.ones(n_obs), factor_matrix])

    # Guard against a singular / collinear design.
    rank = int(np.linalg.matrix_rank(X))
    multicollinearity_warning = rank < X.shape[1]

    coef, _residual_ss, _rank, _sv = np.linalg.lstsq(X, y, rcond=None)
    alpha_daily = float(coef[0])
    betas = {name: float(coef[i + 1]) for i, name in enumerate(factor_names)}

    fitted = X @ coef
    residuals = y - fitted

    # R² = 1 − SS_res / SS_tot.
    ss_res = float(np.sum(residuals**2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r_squared = float(1.0 - ss_res / ss_tot) if ss_tot > 1e-18 else 0.0

    residual_vol = (
        float(np.std(residuals, ddof=1) * np.sqrt(TRADING_DAYS_PER_YEAR))
        if n_obs >= 2
        else 0.0
    )

    # Factor correlation matrix.
    factor_corr = combined[factor_names].corr().fillna(0.0)
    factor_correlation_matrix = {
        a: {b: float(factor_corr.loc[a, b]) for b in factor_names} for a in factor_names
    }

    # Diagnostics.
    strongest_positive = max(betas, key=lambda nm: betas[nm]) if betas else None
    strongest_negative = min(betas, key=lambda nm: betas[nm]) if betas else None
    abs_largest = max(betas, key=lambda nm: abs(betas[nm])) if betas else None

    # Equity curves (anchored at initial_capital).
    dates = list(combined.index)
    actual_curve = [{"date": _date_str(dates[0]), "value": float(initial_capital)}]
    fitted_curve = [{"date": _date_str(dates[0]), "value": float(initial_capital)}]
    a_run = f_run = float(initial_capital)
    regression_points = []
    for i, d in enumerate(dates):
        a_run *= 1.0 + float(y[i])
        f_run *= 1.0 + float(fitted[i])
        actual_curve.append({"date": _date_str(d), "value": a_run})
        fitted_curve.append({"date": _date_str(d), "value": f_run})
        regression_points.append(
            {
                "date": _date_str(d),
                "actual_return": float(y[i]),
                "fitted_return": float(fitted[i]),
                "residual": float(residuals[i]),
            }
        )

    return {
        "alpha_daily": alpha_daily,
        "alpha_annualized": alpha_daily * TRADING_DAYS_PER_YEAR,
        "betas": betas,
        "r_squared": r_squared,
        "residual_volatility": residual_vol,
        "factor_correlation_matrix": factor_correlation_matrix,
        "diagnostics": {
            "strongest_positive_factor": strongest_positive,
            "strongest_negative_factor": strongest_negative,
            "absolute_largest_exposure": abs_largest,
            "multicollinearity_warning": bool(multicollinearity_warning),
        },
        "regression_points": regression_points,
        "actual_equity_curve": actual_curve,
        "fitted_equity_curve": fitted_curve,
        "num_observations": n_obs,
    }
