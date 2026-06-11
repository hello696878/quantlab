"""
Stability Lab v1 — parameter-sensitivity sweep for SMA Crossover.

Re-runs the strategy over a small fast×slow window grid using the **same
pipeline as the main backtest** (signal → direction mode → risk management →
position sizing → engine → metrics, with the same effective costs and
annualization convention), and summarizes whether the selected parameters sit
in a stable neighborhood or an isolated spike.

Honesty rules:

* A research diagnostic, not an optimization recommendation — choosing the
  best-performing cell after viewing the heatmap can itself create overfitting.
* Invalid combinations (fast ≥ slow, or not enough bars) are marked invalid,
  never faked or silently dropped from the grid shape.
* Summary metrics only — no equity curves per cell (payload stays compact).
* The stability score is a transparent heuristic (0–1) and is labelled as such.
"""

from __future__ import annotations

import math
import statistics
from typing import Dict, List, Optional, Tuple

import pandas as pd

from app.backtest import run_backtest
from app.metrics import compute_metrics
from app.position_sizing import apply_sizing
from app.risk_management import apply_risk_management
from app.schemas import (
    PositionSizing,
    RiskManagement,
    SensitivityConfig,
    SensitivityPoint,
    SensitivityResult,
    SensitivityRun,
    SensitivityRunMetrics,
    SensitivitySummary,
)
from app.strategies import sma_crossover_signals

DEFAULT_FAST_GRID = [10, 15, 20, 25, 30, 40, 50]
DEFAULT_SLOW_GRID = [60, 80, 100, 120, 150, 200]

HARD_MAX_RUNS = 200

# Metrics where a *higher* value is better.  max_drawdown is negative, so
# "higher" (closer to zero, i.e. a shallower drawdown) is still better.
_METRIC_KEYS = ("sharpe", "total_return", "cagr", "max_drawdown", "calmar")

# Below this score the selected parameters are flagged as fragile.
_FRAGILITY_THRESHOLD = 0.5


def build_parameter_grid(
    config: SensitivityConfig, current_fast: int, current_slow: int
) -> Tuple[List[int], List[int]]:
    """Resolve the grid and make sure the selected parameters are included."""
    xs = sorted(set(config.x_values or DEFAULT_FAST_GRID) | {current_fast})
    ys = sorted(set(config.y_values or DEFAULT_SLOW_GRID) | {current_slow})
    return xs, ys


def _metric_value(metrics: Optional[SensitivityRunMetrics], metric: str) -> Optional[float]:
    if metrics is None:
        return None
    value = getattr(metrics, metric, None)
    return float(value) if value is not None and math.isfinite(float(value)) else None


def run_sensitivity_grid(
    close: pd.Series,
    config: SensitivityConfig,
    *,
    current_fast: int,
    current_slow: int,
    position_mode: str,
    risk_management: Optional[RiskManagement],
    position_sizing: Optional[PositionSizing],
    effective_cost_bps: float,
    initial_capital: float,
    periods_per_year: int,
) -> SensitivityResult:
    """Run the SMA fast×slow sweep with the full simulation pipeline per cell."""
    warnings: List[str] = []
    xs, ys = build_parameter_grid(config, current_fast, current_slow)

    total = len(xs) * len(ys)
    cap = min(config.max_runs, HARD_MAX_RUNS)
    if total > cap:
        raise ValueError(
            f"Sensitivity grid has {total} combinations, exceeding the limit of "
            f"{cap}. Reduce x_values/y_values or raise max_runs (hard cap "
            f"{HARD_MAX_RUNS})."
        )

    n_bars = len(close)
    runs: List[SensitivityRun] = []
    value_by_cell: Dict[Tuple[int, int], Optional[float]] = {}

    for slow in ys:
        for fast in xs:
            if fast >= slow:
                runs.append(SensitivityRun(
                    fast_window=fast, slow_window=slow, valid=False,
                    warning="fast_window must be less than slow_window.",
                ))
                value_by_cell[(fast, slow)] = None
                continue
            if n_bars < slow + 2:
                runs.append(SensitivityRun(
                    fast_window=fast, slow_window=slow, valid=False,
                    warning=f"Only {n_bars} bars; need at least {slow + 2}.",
                ))
                value_by_cell[(fast, slow)] = None
                continue

            position = sma_crossover_signals(
                close, fast_window=fast, slow_window=slow, position_mode=position_mode
            )
            risk_result = apply_risk_management(position, close, risk_management)
            sized = apply_sizing(risk_result.position, close, position_sizing)
            equity, _bench, trades = run_backtest(
                close=close,
                position=sized,
                transaction_cost_bps=effective_cost_bps,
                initial_capital=initial_capital,
            )
            m = compute_metrics(equity, periods_per_year=periods_per_year)
            metrics = SensitivityRunMetrics(
                sharpe=float(m["sharpe_ratio"]),
                total_return=float(m["total_return"]),
                cagr=float(m["cagr"]),
                max_drawdown=float(m["max_drawdown"]),
                calmar=float(m["calmar_ratio"]),
            )
            runs.append(SensitivityRun(
                fast_window=fast, slow_window=slow, valid=True,
                metrics=metrics, num_trades=len(trades),
            ))
            value_by_cell[(fast, slow)] = _metric_value(metrics, config.metric)

    matrix = [[value_by_cell[(fast, slow)] for fast in xs] for slow in ys]

    selected_value = value_by_cell.get((current_fast, current_slow))
    selected_point = SensitivityPoint(
        fast_window=current_fast, slow_window=current_slow, value=selected_value
    )
    if selected_value is None:
        warnings.append(
            "The selected parameters did not produce a valid sweep run; the "
            "stability summary is unavailable."
        )

    summary = summarize_sensitivity(
        xs, ys, value_by_cell, current_fast, current_slow, config.metric
    )

    warnings.append(
        "Parameter sensitivity is a research diagnostic. Choosing the "
        "best-performing cell after viewing the heatmap can itself create "
        "overfitting."
    )

    return SensitivityResult(
        supported=True,
        strategy="sma_crossover",
        metric=config.metric,
        x_values=xs,
        y_values=ys,
        selected_point=selected_point,
        matrix=matrix,
        runs=runs,
        summary=summary,
        warnings=warnings,
    )


def summarize_sensitivity(
    xs: List[int],
    ys: List[int],
    value_by_cell: Dict[Tuple[int, int], Optional[float]],
    current_fast: int,
    current_slow: int,
    metric: str,
) -> SensitivitySummary:
    """Best point + heuristic neighborhood stability around the selection."""
    valid_items = [(k, v) for k, v in value_by_cell.items() if v is not None]
    best_value = None
    best_params = None
    if valid_items:
        # Higher is better for every supported metric (max_drawdown is negative,
        # so "higher" = shallower drawdown).
        (bf, bs), bv = max(valid_items, key=lambda kv: kv[1])
        best_value = round(bv, 6)
        best_params = SensitivityPoint(fast_window=bf, slow_window=bs, value=best_value)

    selected = value_by_cell.get((current_fast, current_slow))
    score, fragile, neighbor_median, neighbor_min, explanation = compute_stability_score(
        xs, ys, value_by_cell, current_fast, current_slow, selected
    )

    return SensitivitySummary(
        best_value=best_value,
        best_params=best_params,
        selected_value=round(selected, 6) if selected is not None else None,
        neighbor_median=neighbor_median,
        neighbor_min=neighbor_min,
        stability_score=score,
        fragility_flag=fragile,
        explanation=explanation,
    )


def compute_stability_score(
    xs: List[int],
    ys: List[int],
    value_by_cell: Dict[Tuple[int, int], Optional[float]],
    current_fast: int,
    current_slow: int,
    selected: Optional[float],
) -> Tuple[Optional[float], bool, Optional[float], Optional[float], str]:
    """Transparent heuristic: compare the selected cell to its grid neighbors.

    Neighbors are the up-to-8 cells within one grid step in each direction.
    ``closeness`` penalizes a selected value far above the neighbor median
    (an isolated spike); the valid-neighbor fraction penalizes neighborhoods
    full of invalid/missing cells.  Score = closeness × (0.5 + 0.5 ×
    valid_fraction), clamped to [0, 1]; fragile when < 0.5.
    """
    if selected is None:
        return None, False, None, None, (
            "Stability is unavailable because the selected parameters have no "
            "valid sweep result."
        )

    xi = xs.index(current_fast) if current_fast in xs else -1
    yi = ys.index(current_slow) if current_slow in ys else -1
    if xi < 0 or yi < 0:
        return None, False, None, None, "Selected parameters are outside the grid."

    neighbor_cells: List[Optional[float]] = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = xi + dx, yi + dy
            if 0 <= nx < len(xs) and 0 <= ny < len(ys):
                neighbor_cells.append(value_by_cell.get((xs[nx], ys[ny])))

    valid_neighbors = [v for v in neighbor_cells if v is not None]
    if len(valid_neighbors) < 2:
        return None, False, None, None, (
            "Too few valid neighboring parameter combinations to assess "
            "stability."
        )

    neighbor_median = float(statistics.median(valid_neighbors))
    neighbor_min = float(min(valid_neighbors))
    valid_frac = len(valid_neighbors) / len(neighbor_cells)

    drop_vs_median = max(0.0, selected - neighbor_median)
    scale = max(abs(selected), abs(neighbor_median), 0.1)
    closeness = max(0.0, min(1.0, 1.0 - drop_vs_median / scale))
    score = round(max(0.0, min(1.0, closeness * (0.5 + 0.5 * valid_frac))), 4)
    fragile = score < _FRAGILITY_THRESHOLD

    if fragile:
        explanation = (
            "The selected parameters appear sensitive: nearby parameter choices "
            "produce much weaker results."
        )
    else:
        explanation = "Nearby parameter choices produce broadly similar results."

    return score, fragile, round(neighbor_median, 6), round(neighbor_min, 6), explanation


def unsupported_sensitivity(strategy: str, config: SensitivityConfig) -> SensitivityResult:
    """Clear unsupported-strategy block (no crash, no fake sweep)."""
    return SensitivityResult(
        supported=False,
        strategy=strategy,
        metric=config.metric,
        warnings=[
            "Stability Lab v1 currently supports SMA Crossover only; "
            f"'{strategy}' sweeps are planned."
        ],
    )
