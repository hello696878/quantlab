"""
Deterministic static-sample crypto markets for the Crypto Funding & Basis Lab (26.0).

Four illustrative markets (BTCUSDT perp, ETHUSDT perp, SOLUSDT perp, BTC quarterly
futures), each with a spot / index / perpetual-mark snapshot, a dated futures curve,
a funding rate, and a sample leveraged position. Identical every run and every
test. Not live exchange data, not live crypto prices, not advice.
"""

from __future__ import annotations

from typing import List

from app.crypto_derivatives.models import (
    CryptoDerivativesAnalysisRequest,
    CryptoDerivativesSampleResponse,
    CryptoMarketInput,
    DatedFutureInput,
    PositionInput,
)

DISCLAIMER = (
    "Static illustrative sample data. Crypto derivatives analytics are educational "
    "and not investment, trading, liquidation, legal, tax, or risk-management advice."
)


def _build(
    symbol: str,
    spot: float,
    index: float,
    perp_mark: float,
    funding_8h: float,
    next_funding_hours: float,
    futures: List[tuple],  # (contract, maturity_days, price)
    side: str,
    notional: float,
    entry: float,
    leverage: float,
    init_margin: float,
    maint_margin: float,
) -> CryptoDerivativesAnalysisRequest:
    return CryptoDerivativesAnalysisRequest(
        market=CryptoMarketInput(
            symbol=symbol,
            spot_price=spot,
            perp_mark_price=perp_mark,
            index_price=index,
            funding_rate_8h=funding_8h,
            next_funding_hours=next_funding_hours,
            risk_free_rate=0.04,
        ),
        dated_futures=[
            DatedFutureInput(contract=c, maturity_days=d, futures_price=p) for (c, d, p) in futures
        ],
        position=PositionInput(
            side=side,
            notional=notional,
            entry_price=entry,
            mark_price=perp_mark,
            leverage=leverage,
            initial_margin_rate=init_margin,
            maintenance_margin_rate=maint_margin,
            taker_fee_rate=0.0004,
            maker_fee_rate=0.0001,
        ),
    )


def sample_requests() -> List[CryptoDerivativesAnalysisRequest]:
    return [
        # BTCUSDT perp — mild positive funding, contango curve, long position.
        _build(
            "BTCUSDT_SAMPLE", 65000.0, 64980.0, 65080.0, 0.0001, 4.0,
            [("BTC-30D", 30.0, 65300.0), ("BTC-90D", 90.0, 66100.0), ("BTC-180D", 180.0, 67500.0)],
            "long", 100000.0, 64800.0, 5.0, 0.20, 0.05,
        ),
        # ETHUSDT perp — slightly richer funding, contango, long position.
        _build(
            "ETHUSDT_SAMPLE", 3500.0, 3499.0, 3504.5, 0.00018, 2.0,
            [("ETH-30D", 30.0, 3520.0), ("ETH-90D", 90.0, 3565.0), ("ETH-180D", 180.0, 3640.0)],
            "long", 50000.0, 3470.0, 8.0, 0.125, 0.04,
        ),
        # SOLUSDT perp — hot positive funding + premium (overheated-ish), long.
        _build(
            "SOLUSDT_SAMPLE", 150.0, 149.8, 150.6, 0.00045, 6.0,
            [("SOL-30D", 30.0, 151.5), ("SOL-90D", 90.0, 154.0), ("SOL-180D", 180.0, 158.0)],
            "long", 30000.0, 148.0, 10.0, 0.10, 0.05,
        ),
        # BTC quarterly futures — slight perp discount, rich dated carry, short perp.
        _build(
            "BTC_QUARTERLY_SAMPLE", 64000.0, 64010.0, 63960.0, -0.00008, 1.5,
            [("BTC-Q1", 91.0, 65200.0), ("BTC-Q2", 182.0, 66800.0), ("BTC-Q3", 273.0, 68500.0)],
            "short", 80000.0, 64200.0, 4.0, 0.25, 0.06,
        ),
    ]


def build_sample_response() -> CryptoDerivativesSampleResponse:
    return CryptoDerivativesSampleResponse(
        markets=sample_requests(),
        disclaimer=DISCLAIMER,
        notes=[
            "Four illustrative crypto markets (BTCUSDT perp, ETHUSDT perp, SOLUSDT "
            "perp, BTC quarterly futures) with spot / index / perp-mark snapshots, "
            "dated futures curves, funding rates, and sample leveraged positions.",
            "Select / edit a market in the lab to explore the analytics.",
            "Not live exchange data, not live crypto prices, and not investment, "
            "trading, or liquidation advice.",
        ],
    )
