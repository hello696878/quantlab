"""
Robustness Lab v1 — bootstrap Monte Carlo on daily strategy returns.

Resamples the realized daily return series with a **block bootstrap** (blocks
of consecutive returns preserve short-term autocorrelation; ``block_size=1``
degenerates to a plain i.i.d. bootstrap), rebuilds simulated equity paths of
the same length, and summarizes the distribution of final returns, max
drawdowns, and Sharpe ratios.

Honesty rules (enforced here, restated in the UI/docs):

* Deterministic for a given seed; changing the seed changes the simulation but
  never the core backtest result.
* Bootstrap resamples *history* — it estimates sensitivity to return ordering
  and sampling, not future performance.  Regime shifts, liquidity shocks, and
  structural breaks are outside its assumptions.
* The A–F grade is a transparent heuristic rule-of-thumb, not a recommendation.
* No NaN/inf ever reaches JSON; insufficient data → warning, never a crash.
* Deflated Sharpe is **null in v1**: it requires the number of tried
  configurations (unknowable here) and distributional assumptions — planned
  for Robustness Lab v2 rather than faked.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

import numpy as np

from app.schemas import (
    RobustnessConfig,
    RobustnessHistogramBin,
    RobustnessResult,
    RobustnessSummary,
)

# Below this many daily returns a bootstrap distribution is too unstable to be
# meaningful — return a warning instead of numbers.
MIN_RETURNS = 30

_HIST_BINS = 20


def bootstrap_returns(
    returns: np.ndarray,
    n_simulations: int,
    block_size: int,
    seed: int,
) -> np.ndarray:
    """Block-bootstrap resample: (n_simulations, len(returns)) matrix.

    Contiguous blocks are sampled with replacement and concatenated, then
    truncated to the original length (so each simulated path has exactly as
    many periods as the realized one).
    """
    n = len(returns)
    rng = np.random.default_rng(seed)
    block = max(1, min(block_size, n))
    n_blocks = math.ceil(n / block)
    starts = rng.integers(0, n - block + 1, size=(n_simulations, n_blocks))
    offsets = np.arange(block)
    idx = (starts[:, :, None] + offsets[None, None, :]).reshape(n_simulations, -1)[:, :n]
    return returns[idx]


def _simulate_stats(
    sims: np.ndarray, periods_per_year: int
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-simulation (final_return, max_drawdown, annualized sharpe)."""
    equity = np.cumprod(1.0 + sims, axis=1)
    final_returns = equity[:, -1] - 1.0
    running_peak = np.maximum.accumulate(equity, axis=1)
    drawdowns = equity / running_peak - 1.0
    max_drawdowns = drawdowns.min(axis=1)
    means = sims.mean(axis=1)
    stds = sims.std(axis=1, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        sharpes = np.where(stds > 1e-12, means / stds * math.sqrt(periods_per_year), 0.0)
    return final_returns, max_drawdowns, sharpes


def _clean(value: float, digits: int = 6) -> float:
    f = float(value)
    return round(f, digits) if math.isfinite(f) else 0.0


def _histogram(final_returns: np.ndarray) -> List[RobustnessHistogramBin]:
    lo = float(final_returns.min())
    hi = float(final_returns.max())
    if not (math.isfinite(lo) and math.isfinite(hi)):
        return []
    if hi - lo < 1e-12:  # degenerate (e.g. flat returns) — single bin
        return [RobustnessHistogramBin(lower=_clean(lo), upper=_clean(hi), count=len(final_returns))]
    counts, edges = np.histogram(final_returns, bins=_HIST_BINS)
    return [
        RobustnessHistogramBin(
            lower=_clean(edges[i]), upper=_clean(edges[i + 1]), count=int(counts[i])
        )
        for i in range(len(counts))
    ]


def compute_robustness_grade(summary: RobustnessSummary) -> str:
    """Transparent heuristic grade (rule-of-thumb, not a recommendation).

    F: p(loss) > 60%, or median final return < 0, or extreme tail drawdown.
    A: p(loss) < 10%, 5th-pct final return > 0, tail drawdown better than −25%,
       median Sharpe > 1.
    B: p(loss) < 25%, 5th-pct final return > −15%, median Sharpe > 0.5.
    C: p(loss) < 40%.   D: p(loss) ≤ 60%.   Otherwise F.
    """
    p_loss = summary.probability_of_loss
    if (
        p_loss > 0.60
        or summary.median_final_return < 0
        or summary.p95_max_drawdown < -0.60
    ):
        return "F"
    if (
        p_loss < 0.10
        and summary.p05_final_return > 0
        and summary.p95_max_drawdown > -0.25
        and summary.median_sharpe > 1.0
    ):
        return "A"
    if p_loss < 0.25 and summary.p05_final_return > -0.15 and summary.median_sharpe > 0.5:
        return "B"
    if p_loss < 0.40:
        return "C"
    return "D"


def build_robustness_report(
    daily_returns: np.ndarray,
    config: RobustnessConfig,
    periods_per_year: int,
    benchmark_total_return: Optional[float] = None,
    extra_warnings: Optional[List[str]] = None,
) -> RobustnessResult:
    """Run the bootstrap and assemble the response block (never raises)."""
    warnings: List[str] = list(extra_warnings or [])

    returns = np.asarray(daily_returns, dtype=float)
    returns = returns[np.isfinite(returns)]
    if len(returns) < MIN_RETURNS:
        warnings.append(
            f"Only {len(returns)} valid daily return(s) available — at least "
            f"{MIN_RETURNS} are needed for a meaningful bootstrap. Analysis skipped."
        )
        return RobustnessResult(
            n_simulations=config.n_simulations,
            block_size=config.block_size,
            seed=config.seed,
            summary=None,
            grade=None,
            warnings=warnings,
        )

    if config.block_size > len(returns):
        warnings.append(
            f"block_size {config.block_size} exceeds the sample length; clamped."
        )

    sims = bootstrap_returns(returns, config.n_simulations, config.block_size, config.seed)
    final_returns, max_drawdowns, sharpes = _simulate_stats(sims, periods_per_year)

    prob_outperform = None
    if benchmark_total_return is not None and math.isfinite(benchmark_total_return):
        prob_outperform = _clean(float((final_returns > benchmark_total_return).mean()), 4)

    summary = RobustnessSummary(
        median_final_return=_clean(np.percentile(final_returns, 50)),
        p05_final_return=_clean(np.percentile(final_returns, 5)),
        p95_final_return=_clean(np.percentile(final_returns, 95)),
        probability_of_loss=_clean(float((final_returns < 0).mean()), 4),
        probability_of_outperforming_benchmark=prob_outperform,
        median_max_drawdown=_clean(np.percentile(max_drawdowns, 50)),
        # The bad tail: 95th percentile of drawdown *severity* = 5th percentile
        # of the signed values (more negative than the median).
        p95_max_drawdown=_clean(np.percentile(max_drawdowns, 5)),
        median_sharpe=_clean(np.percentile(sharpes, 50), 4),
        p05_sharpe=_clean(np.percentile(sharpes, 5), 4),
        p95_sharpe=_clean(np.percentile(sharpes, 95), 4),
    )

    return RobustnessResult(
        n_simulations=config.n_simulations,
        block_size=config.block_size,
        seed=config.seed,
        summary=summary,
        final_return_histogram=_histogram(final_returns),
        grade=compute_robustness_grade(summary),
        deflated_sharpe=None,  # v1: see module docstring — never faked
        warnings=warnings
        + [
            "Bootstrap resamples historical returns to estimate outcome "
            "uncertainty; it does not model regime shifts, liquidity shocks, or "
            "structural breaks, and it is not a guarantee."
        ],
    )
