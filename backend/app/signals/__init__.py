"""Futures signal layer (Phase 3).

Commit 3 ships the deterministic non-ML momentum baseline:
``BaselineSignalConfig``, ``SignalMode``, and ``momentum_baseline_signal``. The
backtest adapter (which applies the t+1 execution shift and computes PnL) lands
in a later commit.
"""

from app.signals.baseline import (
    BaselineSignalConfig,
    SignalError,
    SignalMode,
    momentum_baseline_signal,
)

__all__ = [
    "BaselineSignalConfig",
    "SignalMode",
    "SignalError",
    "momentum_baseline_signal",
]
