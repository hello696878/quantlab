"""
Futures-aware vectorized backtest adapter (Phase 3 — commit 4).

Named ``futures_backtest`` (a package) to avoid colliding with the existing
``app.backtest`` module.  This adapter **reuses ``app.backtest.run_backtest``**
for the core return/cost/equity math and the trade log, and wraps it with the
futures specifics: the ``t+1`` execution shift, ratio-adjusted (seam-safe)
strategy returns, a roll-day cost overlay, and tick/commission-derived costs.

Key correctness rules (Phase 3 plan §D.6/§D.8):

* **Timing:** a signal at ``t`` executes at ``t+1`` — ``effective_position =
  target_position.shift(1).fillna(0)``.  The first row is flat; no same-bar fill.
* **Returns:** computed from ``close_adjusted`` (ratio) — seam-safe, so a roll's
  raw inter-contract gap can never create fake strategy PnL.  Raw prices are
  **execution/reference only** (fill price, tick rounding, dollar-cost notional).
* **Costs:** charged only when ``effective_position`` changes; an extra roll cost
  is charged when a non-zero position is held across a ``roll_flag`` bar (if
  ``include_roll_cost``).  Cost assumptions are recorded in ``cost_metadata`` —
  never a silent zero.
* Inputs are never mutated; output is deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from app.backtest import run_backtest

_KEY_COLUMNS = ["timestamp", "root_symbol", "active_contract"]


class FuturesBacktestError(ValueError):
    """Raised on invalid or mismatched futures-backtest inputs."""


@dataclass
class FuturesBacktestResult:
    """Per-bar backtest frame plus the trade log, benchmark, and metadata."""

    frame: pd.DataFrame
    trades: list
    benchmark_equity: pd.Series
    cost_metadata: dict
    metrics: dict


def _require_columns(df: pd.DataFrame, columns: list[str], which: str) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise FuturesBacktestError(f"{which} is missing required columns: {missing}")


def _resolve_cost_bps(
    transaction_cost_bps: Optional[float],
    commission_per_contract: Optional[float],
    slippage_ticks_per_side: Optional[float],
    spec,
    reference_price: float,
) -> tuple[float, dict]:
    """Resolve an effective per-side cost in bps, with documented metadata."""
    if transaction_cost_bps is not None:
        bps = float(transaction_cost_bps)
        return bps, {
            "effective_cost_bps": bps,
            "source": "explicit_bps",
            "is_placeholder": False,
            "zero_cost": bps == 0.0,
        }

    commission = (
        float(commission_per_contract)
        if commission_per_contract is not None
        else float(spec.costs.commission_per_contract_per_side)
    )
    slippage = (
        float(slippage_ticks_per_side)
        if slippage_ticks_per_side is not None
        else float(spec.costs.slippage_ticks_per_side)
    )
    cost_per_side_usd = commission + slippage * float(spec.tick_value)
    notional = reference_price * float(spec.contract_multiplier)
    bps = (cost_per_side_usd / notional) * 10_000.0 if notional > 0 else 0.0
    return bps, {
        "effective_cost_bps": bps,
        "source": "derived_from_commission_slippage",
        "commission_per_contract_per_side": commission,
        "slippage_ticks_per_side": slippage,
        "tick_value": float(spec.tick_value),
        "contract_multiplier": float(spec.contract_multiplier),
        "notional_reference_price": reference_price,
        "is_placeholder": bool(spec.costs.is_placeholder),
        "zero_cost": bps == 0.0,
    }


def run_futures_backtest(
    continuous_df: pd.DataFrame,
    signal_df: pd.DataFrame,
    spec,
    *,
    position_col: str = "target_position",
    price_col: str = "close_adjusted",
    raw_execution_price_col: str = "open_raw",
    transaction_cost_bps: Optional[float] = None,
    commission_per_contract: Optional[float] = None,
    slippage_ticks_per_side: Optional[float] = None,
    initial_capital: float = 10_000.0,
    include_roll_cost: bool = True,
) -> FuturesBacktestResult:
    """Run a futures-aware vectorized backtest. Inputs are never mutated."""
    _require_columns(
        continuous_df,
        _KEY_COLUMNS + [price_col, raw_execution_price_col, "close_raw", "roll_flag", "adjustment_method"],
        "continuous_df",
    )
    _require_columns(signal_df, _KEY_COLUMNS + [position_col], "signal_df")
    if len(continuous_df) < 2:
        raise FuturesBacktestError("need at least 2 continuous rows to backtest")

    # Strategy returns must be seam-safe -> require ratio-adjusted continuous data.
    adjustments = {str(a) for a in continuous_df["adjustment_method"].unique()}
    if adjustments != {"ratio"}:
        raise FuturesBacktestError(
            f"strategy returns require ratio-adjusted continuous data, got {sorted(adjustments)}"
        )

    cont = continuous_df.sort_values("timestamp", kind="stable").reset_index(drop=True)
    sig = signal_df[_KEY_COLUMNS + [position_col]].copy()

    # Align target to continuous rows by key (flat where no signal is provided).
    merged = cont.merge(sig, on=_KEY_COLUMNS, how="left")
    target = merged[position_col].fillna(0.0).astype(float)

    # Timing: signal at t executes at t+1.
    effective_position = target.shift(1).fillna(0.0)

    # Cost resolution (documented; never a silent zero).
    reference_price = float(np.median(cont["close_raw"].astype(float)))
    cost_bps, cost_metadata = _resolve_cost_bps(
        transaction_cost_bps, commission_per_contract, slippage_ticks_per_side, spec, reference_price
    )
    cost_metadata["include_roll_cost"] = bool(include_roll_cost)

    # --- reuse app.backtest.run_backtest for the base (seam-safe) engine ---
    close_adjusted = cont[price_col].astype(float)
    close_adjusted.index = cont["timestamp"]
    engine_position = effective_position.copy()
    engine_position.index = cont["timestamp"]
    engine_equity, benchmark_equity, trades = run_backtest(
        close=close_adjusted,
        position=engine_position,
        transaction_cost_bps=cost_bps,
        initial_capital=initial_capital,
    )
    engine_equity = engine_equity.reset_index(drop=True)
    benchmark_equity = benchmark_equity.reset_index(drop=True)

    # Per-bar engine net return (market return + position-change cost; no roll cost).
    engine_return = engine_equity / engine_equity.shift(1) - 1.0
    engine_return.iloc[0] = engine_equity.iloc[0] / initial_capital - 1.0

    # --- roll-cost overlay (the futures-specific detail run_backtest can't model) ---
    cost_rate = cost_bps / 10_000.0
    roll_flag = cont["roll_flag"].fillna(False).astype(bool)
    if include_roll_cost:
        held_across_roll = roll_flag & (effective_position.abs() > 0)
        roll_cost_fraction = held_across_roll.astype(float) * cost_rate * effective_position.abs()
    else:
        roll_cost_fraction = pd.Series(0.0, index=cont.index)

    net_return = (1.0 + engine_return) * (1.0 - roll_cost_fraction) - 1.0
    equity = initial_capital * (1.0 + net_return).cumprod()

    # Decomposed output columns.
    market_return = close_adjusted.reset_index(drop=True).pct_change().fillna(0.0)
    strategy_return = effective_position * market_return  # gross, from close_adjusted
    transaction_cost = strategy_return - net_return       # exact: position-change + roll cost

    frame = pd.DataFrame(
        {
            "timestamp": cont["timestamp"].to_numpy(),
            "root_symbol": cont["root_symbol"].to_numpy(),
            "active_contract": cont["active_contract"].to_numpy(),
            "target_position": target.to_numpy(),
            "effective_position": effective_position.to_numpy(),
            "close_adjusted": close_adjusted.reset_index(drop=True).to_numpy(),
            "raw_execution_price": cont[raw_execution_price_col].astype(float).to_numpy(),
            "roll_flag": roll_flag.to_numpy(),
            "strategy_return": strategy_return.to_numpy(),
            "transaction_cost": transaction_cost.to_numpy(),
            "net_strategy_return": net_return.to_numpy(),
            "equity": equity.to_numpy(),
        }
    )

    position_changes = effective_position.diff().fillna(effective_position.iloc[0]).abs()
    metrics = {
        "final_equity": float(equity.iloc[-1]),
        "total_return": float(equity.iloc[-1] / initial_capital - 1.0),
        "total_transaction_cost": float(transaction_cost.sum()),
        "num_trades": len(trades),
        "n_position_changes": int((position_changes > 1e-12).sum()),
        "initial_capital": float(initial_capital),
    }
    return FuturesBacktestResult(
        frame=frame,
        trades=trades,
        benchmark_equity=benchmark_equity,
        cost_metadata=cost_metadata,
        metrics=metrics,
    )
