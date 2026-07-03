"""
Synthetic futures mini trade report (foundation demo, NOT a backtest engine).

One deliberately tiny calculation: go long ``contracts`` at the first bar's
close, exit at the last bar's close, and compute the P&L two independent ways
from the instrument spec:

* direct:      ``price_move * contract_multiplier * contracts``
* tick-based:  ``(price_move / tick_size) * tick_value * contracts``

The two agree exactly when the spec's tick-value invariant
(``tick_value == contract_multiplier * tick_size``) holds, so the match flag
doubles as an end-to-end consistency check across bars, registry, and
economics.  No positions over time, no costs, no slippage — the real engine
lives elsewhere and is out of scope here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from app.datastore import FuturesDailyBar
from app.instruments import get_instrument


@dataclass(frozen=True)
class LongTradeReport:
    """Result of one synthetic long trade over a sequence of daily bars."""

    root_symbol: str
    contract_symbol: str
    name: str
    exchange: str
    currency: str
    contract_multiplier: float
    tick_size: float
    tick_value: float
    entry_price: float
    exit_price: float
    price_move: float
    tick_move: float
    contracts: int
    pnl_usd: float
    tick_pnl_usd: float
    pnl_matches: bool
    # Spec-level warnings; the instrument yamls ask these to be surfaced in
    # every report (tuple keeps the frozen dataclass immutable).
    warnings: tuple[str, ...]


def long_trade_report(
    bars: Sequence[FuturesDailyBar], contracts: int = 1
) -> LongTradeReport:
    """Long ``contracts`` from the first bar's close to the last bar's close.

    ``bars`` must be non-empty and all for the same contract; they are sorted
    by timestamp before entry/exit are taken.  Raises :class:`ValueError` on
    bad input.
    """
    if not bars:
        raise ValueError("bars must be non-empty")
    if not isinstance(contracts, int) or isinstance(contracts, bool) or contracts < 1:
        raise ValueError(f"contracts must be an int >= 1 (got {contracts!r})")
    roots = sorted({b.root_symbol for b in bars})
    symbols = sorted({b.contract_symbol for b in bars})
    if len(roots) != 1 or len(symbols) != 1:
        raise ValueError(
            f"bars must all be for one contract (got roots={roots}, "
            f"contracts={symbols})"
        )
    if len({b.timestamp for b in bars}) != len(bars):
        raise ValueError("bars must have unique timestamps")

    spec = get_instrument(roots[0])
    ordered = sorted(bars, key=lambda b: b.timestamp)
    entry = ordered[0].close
    exit_ = ordered[-1].close
    move = exit_ - entry
    pnl = move * spec.contract_multiplier * contracts
    tick_move = move / spec.tick_size
    tick_pnl = tick_move * spec.tick_value * contracts

    return LongTradeReport(
        root_symbol=spec.root_symbol,
        contract_symbol=symbols[0],
        name=spec.name,
        exchange=spec.exchange,
        currency=spec.currency,
        contract_multiplier=spec.contract_multiplier,
        tick_size=spec.tick_size,
        tick_value=spec.tick_value,
        entry_price=entry,
        exit_price=exit_,
        price_move=move,
        tick_move=tick_move,
        contracts=contracts,
        pnl_usd=pnl,
        tick_pnl_usd=tick_pnl,
        pnl_matches=math.isclose(pnl, tick_pnl, rel_tol=1e-9, abs_tol=1e-9),
        warnings=tuple(spec.warnings),
    )
