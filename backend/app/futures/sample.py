"""
Deterministic static-sample commodities for the Futures & Commodities Lab.

Four illustrative commodities (crude oil, gold, natural gas, wheat) with hand-
authored spot prices, carry parameters, margin rates, futures curves, and a
sample position. Identical every run and every test. Not live data, not advice.
"""

from __future__ import annotations

from typing import List

from app.futures.models import (
    FuturesAnalysisRequest,
    FuturesContractInput,
    FuturesCurvePoint,
    FuturesPositionInput,
    FuturesSampleResponse,
)

DISCLAIMER = (
    "Static illustrative sample data. Futures and commodities analytics are "
    "educational and not investment, trading, legal, tax, or risk-management advice."
)


def _curve(points) -> List[FuturesCurvePoint]:
    return [
        FuturesCurvePoint(contract=c, maturity_months=m, futures_price=p)
        for c, m, p in points
    ]


def _crude() -> FuturesAnalysisRequest:
    return FuturesAnalysisRequest(
        contract=FuturesContractInput(
            commodity_name="Crude Oil Sample",
            symbol="CL_SAMPLE",
            spot_price=75.00,
            risk_free_rate=0.045,
            storage_cost_rate=0.015,
            convenience_yield=0.020,
            contract_multiplier=1000,
            initial_margin_rate=0.10,
            maintenance_margin_rate=0.075,
        ),
        curve=_curve([
            ("1M", 1, 75.20), ("3M", 3, 75.80), ("6M", 6, 76.40),
            ("9M", 9, 77.00), ("12M", 12, 77.60), ("18M", 18, 78.80),
        ]),
        position=FuturesPositionInput(
            position_type="long", contracts=5, entry_price=75.80,
            exit_price=77.60, contract_multiplier=1000,
        ),
    )


def _gold() -> FuturesAnalysisRequest:
    return FuturesAnalysisRequest(
        contract=FuturesContractInput(
            commodity_name="Gold Sample",
            symbol="GC_SAMPLE",
            spot_price=2000.00,
            risk_free_rate=0.045,
            storage_cost_rate=0.005,
            convenience_yield=0.000,
            contract_multiplier=100,
            initial_margin_rate=0.06,
            maintenance_margin_rate=0.045,
        ),
        curve=_curve([
            ("1M", 1, 2008.0), ("3M", 3, 2024.0), ("6M", 6, 2048.0),
            ("9M", 9, 2072.0), ("12M", 12, 2096.0), ("18M", 18, 2145.0),
        ]),
        position=FuturesPositionInput(
            position_type="long", contracts=2, entry_price=2024.0,
            exit_price=2096.0, contract_multiplier=100,
        ),
    )


def _natgas() -> FuturesAnalysisRequest:
    # Backwardated curve (near above far) — high seasonal convenience yield.
    return FuturesAnalysisRequest(
        contract=FuturesContractInput(
            commodity_name="Natural Gas Sample",
            symbol="NG_SAMPLE",
            spot_price=3.50,
            risk_free_rate=0.045,
            storage_cost_rate=0.050,
            convenience_yield=0.180,
            contract_multiplier=10000,
            initial_margin_rate=0.12,
            maintenance_margin_rate=0.090,
        ),
        curve=_curve([
            ("1M", 1, 3.55), ("3M", 3, 3.45), ("6M", 6, 3.30),
            ("9M", 9, 3.20), ("12M", 12, 3.10), ("18M", 18, 2.95),
        ]),
        position=FuturesPositionInput(
            position_type="short", contracts=3, entry_price=3.45,
            exit_price=3.20, contract_multiplier=10000,
        ),
    )


def _wheat() -> FuturesAnalysisRequest:
    # Mixed (non-monotone) curve.
    return FuturesAnalysisRequest(
        contract=FuturesContractInput(
            commodity_name="Wheat Sample",
            symbol="ZW_SAMPLE",
            spot_price=6.00,
            risk_free_rate=0.045,
            storage_cost_rate=0.040,
            convenience_yield=0.030,
            contract_multiplier=5000,
            initial_margin_rate=0.08,
            maintenance_margin_rate=0.060,
        ),
        curve=_curve([
            ("1M", 1, 6.05), ("3M", 3, 6.15), ("6M", 6, 6.10),
            ("9M", 9, 6.20), ("12M", 12, 6.18), ("18M", 18, 6.30),
        ]),
        position=FuturesPositionInput(
            position_type="long", contracts=4, entry_price=6.10,
            exit_price=6.20, contract_multiplier=5000,
        ),
    )


def sample_requests() -> List[FuturesAnalysisRequest]:
    return [_crude(), _gold(), _natgas(), _wheat()]


def build_sample_response() -> FuturesSampleResponse:
    return FuturesSampleResponse(
        commodities=sample_requests(),
        disclaimer=DISCLAIMER,
        notes=[
            "Four illustrative commodities (crude oil, gold, natural gas, wheat) "
            "with hand-authored spot, carry, margin, and futures-curve values.",
            "Edit the assumptions in the lab to explore the analytics.",
            "Not live futures or commodity prices, and not investment or trading advice.",
        ],
    )
