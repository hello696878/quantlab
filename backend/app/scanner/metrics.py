"""Portfolio metrics for the scanner engine (computed from the net return series)."""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np

_PERIODS_PER_YEAR = 252


def portfolio_metrics(net_returns: Sequence[float], periods_per_year: int = _PERIODS_PER_YEAR) -> dict:
    r = np.asarray(net_returns, dtype=float)
    r = r[np.isfinite(r)]
    if r.size == 0:
        return {
            "total_return": 0.0,
            "annualized_return": 0.0,
            "annualized_volatility": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
        }

    equity = np.cumprod(1.0 + r)
    final = float(equity[-1])
    n = int(r.size)
    total_return = final - 1.0

    if final > 0:
        annualized_return = final ** (periods_per_year / n) - 1.0
    else:
        annualized_return = -1.0  # wiped out

    std = float(np.std(r, ddof=1)) if n > 1 else 0.0
    annualized_volatility = std * math.sqrt(periods_per_year)
    mean = float(np.mean(r))
    sharpe = (mean / std) * math.sqrt(periods_per_year) if std > 0 else 0.0

    peak = np.maximum.accumulate(equity)
    drawdown = equity / peak - 1.0
    max_drawdown = float(drawdown.min())

    def _f(x: float) -> float:
        return float(x) if math.isfinite(x) else 0.0

    return {
        "total_return": _f(total_return),
        "annualized_return": _f(annualized_return),
        "annualized_volatility": _f(annualized_volatility),
        "sharpe": _f(sharpe),
        "max_drawdown": _f(max_drawdown),
    }
