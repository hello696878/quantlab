"""Futures-aware vectorized backtest adapter (Phase 3).

Named ``futures_backtest`` to avoid colliding with the existing ``app.backtest``
module; it reuses ``app.backtest.run_backtest`` internally and wraps it with the
futures specifics (t+1 execution shift, ratio-adjusted returns, roll-day costs).
"""

from app.futures_backtest.futures_vectorized import (
    FuturesBacktestError,
    FuturesBacktestResult,
    run_futures_backtest,
)

__all__ = [
    "run_futures_backtest",
    "FuturesBacktestResult",
    "FuturesBacktestError",
]
