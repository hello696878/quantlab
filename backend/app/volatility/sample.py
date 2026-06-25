"""
Deterministic static-sample option chain for the Volatility Lab (Phase 24.0).

An illustrative SPX-like surface: a parametric implied-vol pattern (ATM ~18 %,
equity skew, mild upward term structure) is priced with Black-Scholes to produce
coherent sample call/put mid prices, and a fixed-seed daily return series drives
the realized-vol comparison. Identical every run and every test. Not live data.
"""

from __future__ import annotations

from typing import List

import numpy as np

from app.options import black_scholes_price
from app.volatility.models import (
    OptionPositionInput,
    OptionQuoteInput,
    UnderlyingInput,
    VolatilityAnalysisRequest,
    VolatilitySampleResponse,
)

DISCLAIMER = (
    "Static illustrative sample data. Volatility analytics are educational and not "
    "investment, trading, legal, tax, or risk-management advice."
)

_SPOT = 5000.0
_R = 0.045
_Q = 0.015
_MATURITIES = [30, 60, 90, 180, 365]
_MONEYNESS = [0.80, 0.90, 0.95, 1.00, 1.05, 1.10, 1.20]
_SAMPLE_SEED = 24
_RETURN_DAYS = 252


def sample_iv(moneyness: float, t_years: float) -> float:
    """Deterministic illustrative implied-vol surface (equity skew + smile)."""
    atm = 0.18 + 0.02 * (t_years - 30.0 / 365.0)  # mild upward term structure
    skew = 0.30 * (1.0 - moneyness)  # downside puts richer
    smile = 0.25 * (moneyness - 1.0) ** 2  # convex smile
    return max(atm + skew + smile, 0.05)


def _realized_returns() -> List[float]:
    rng = np.random.default_rng(_SAMPLE_SEED)
    # ~17.5% annualised vol with a tiny positive drift.
    rets = rng.normal(0.0003, 0.011, size=_RETURN_DAYS)
    return [round(float(x), 6) for x in rets]


def sample_quotes() -> List[OptionQuoteInput]:
    quotes: List[OptionQuoteInput] = []
    for days in _MATURITIES:
        t = days / 365.0
        for m in _MONEYNESS:
            strike = round(_SPOT * m, 2)
            # OTM convention: puts at/below spot, calls above spot.
            option_type = "put" if m < 1.0 else "call"
            iv = sample_iv(m, t)
            price = black_scholes_price(option_type, _SPOT, strike, t, _R, iv, _Q)
            quotes.append(
                OptionQuoteInput(
                    option_id=f"{option_type[0].upper()}_{int(m * 100)}_{days}d",
                    option_type=option_type,
                    strike=strike,
                    maturity_days=days,
                    mid_price=round(max(price, 0.01), 4),
                )
            )
    return quotes


def sample_positions(quotes: List[OptionQuoteInput]) -> List[OptionPositionInput]:
    # Illustrative net-long-vega book: long 10 of each ATM/OTM-near, fewer wings.
    positions: List[OptionPositionInput] = []
    for q in quotes:
        m = q.strike / _SPOT
        qty = 10.0 if 0.9 <= m <= 1.1 else 4.0
        positions.append(
            OptionPositionInput(option_id=q.option_id, quantity=qty, contract_multiplier=100.0)
        )
    return positions


def sample_request() -> VolatilityAnalysisRequest:
    quotes = sample_quotes()
    return VolatilityAnalysisRequest(
        underlying=UnderlyingInput(
            symbol="SPX_SAMPLE",
            spot_price=_SPOT,
            risk_free_rate=_R,
            dividend_yield=_Q,
            realized_returns=_realized_returns(),
        ),
        option_quotes=quotes,
        positions=sample_positions(quotes),
        variance_swap_maturity_days=30,
    )


def build_sample_response() -> VolatilitySampleResponse:
    return VolatilitySampleResponse(
        request=sample_request(),
        disclaimer=DISCLAIMER,
        notes=[
            "Illustrative SPX-like surface: sample mid prices are generated from a "
            "deterministic implied-vol pattern (ATM ~18%, equity skew, mild term "
            "structure) priced with Black-Scholes, then implied vols are recovered.",
            "Edit the underlying assumptions in the lab to explore the analytics.",
            "Not a live option chain and not investment or trading advice.",
        ],
    )
