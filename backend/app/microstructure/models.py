"""
Typed Pydantic models for the Market Microstructure & Execution Lab (25.0).

Strict, JSON-safe schemas (``extra="forbid"``, ``FiniteFloat`` everywhere) so no
NaN/Infinity can enter or leave the API. All data is static illustrative sample
data — educational only, not investment / trading / order-routing advice.
"""

from __future__ import annotations

from typing import Annotated, List, Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    StringConstraints,
    model_validator,
)

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
PositiveFloat = Annotated[FiniteFloat, Field(gt=0)]
NonNegFloat = Annotated[FiniteFloat, Field(ge=0)]
PositiveMult = Annotated[FiniteFloat, Field(gt=0, le=100)]
Side = Literal["buy", "sell"]
LiquidityFlag = Literal["maker", "taker"]


class MsModel(BaseModel):
    """Strict base model for stable, JSON-safe microstructure payloads."""

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- #
# Input
# --------------------------------------------------------------------------- #
class OrderBookLevelInput(MsModel):
    price: PositiveFloat
    size: PositiveFloat


class OrderBookSnapshotInput(MsModel):
    symbol: NonEmptyStr
    timestamp: NonEmptyStr
    bids: List[OrderBookLevelInput] = Field(min_length=1)
    asks: List[OrderBookLevelInput] = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> "OrderBookSnapshotInput":
        best_bid = max(b.price for b in self.bids)
        best_ask = min(a.price for a in self.asks)
        if best_bid >= best_ask:
            raise ValueError(
                f"crossed/locked book: best_bid {best_bid} must be < best_ask {best_ask}"
            )
        return self


class TradePrintInput(MsModel):
    timestamp: NonEmptyStr
    price: PositiveFloat
    size: PositiveFloat
    side: Side


class ExecutionOrderInput(MsModel):
    symbol: NonEmptyStr
    side: Side
    quantity: PositiveFloat
    arrival_price: PositiveFloat
    decision_price: Optional[PositiveFloat] = None
    benchmark_price: Optional[PositiveFloat] = None
    risk_aversion: Optional[NonNegFloat] = None
    participation_limit: Optional[Annotated[FiniteFloat, Field(gt=0, le=1)]] = None


class ExecutionFillInput(MsModel):
    timestamp: NonEmptyStr
    price: PositiveFloat
    quantity: PositiveFloat
    venue: Optional[NonEmptyStr] = None
    liquidity_flag: Optional[LiquidityFlag] = None


class MarketMicrostructureAnalysisRequest(MsModel):
    order_book: OrderBookSnapshotInput
    trades: List[TradePrintInput] = Field(min_length=1)
    execution_order: ExecutionOrderInput
    fills: List[ExecutionFillInput] = Field(min_length=1)
    volume_curve: List[PositiveFloat] = Field(min_length=2)
    average_daily_volume: PositiveFloat
    volatility_bps: NonNegFloat = 100.0
    impact_coefficient: NonNegFloat = 0.1


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
class InstrumentSummary(MsModel):
    symbol: NonEmptyStr
    timestamp: NonEmptyStr
    best_bid: FiniteFloat
    best_ask: FiniteFloat
    mid_price: FiniteFloat


class OrderBookSummary(MsModel):
    best_bid: FiniteFloat
    best_ask: FiniteFloat
    mid_price: FiniteFloat
    spread: FiniteFloat
    spread_bps: FiniteFloat
    top_of_book_imbalance: FiniteFloat
    depth_imbalance_5: FiniteFloat
    microprice: FiniteFloat
    microprice_vs_mid_bps: FiniteFloat


class DepthLevel(MsModel):
    level: int
    bid_price: FiniteFloat
    bid_size: FiniteFloat
    cumulative_bid_size: FiniteFloat
    ask_price: FiniteFloat
    ask_size: FiniteFloat
    cumulative_ask_size: FiniteFloat


class TradeTapeSummary(MsModel):
    trade_count: int
    total_volume: FiniteFloat
    vwap: FiniteFloat
    twap: FiniteFloat
    trade_imbalance: FiniteFloat
    buy_volume: FiniteFloat
    sell_volume: FiniteFloat


class ExecutionSummary(MsModel):
    side: Side
    parent_quantity: FiniteFloat
    arrival_price: FiniteFloat
    average_execution_price: FiniteFloat
    filled_quantity: FiniteFloat
    fill_ratio: FiniteFloat
    implementation_shortfall: FiniteFloat
    shortfall_bps: FiniteFloat
    slippage_bps: FiniteFloat
    participation_rate: FiniteFloat
    market_impact_bps: FiniteFloat


class ScheduleComparisonResult(MsModel):
    schedule_name: NonEmptyStr
    child_orders: int
    expected_avg_price: FiniteFloat
    expected_shortfall_bps: FiniteFloat
    expected_spread_cost_bps: FiniteFloat
    expected_impact_bps: FiniteFloat
    participation_rate: FiniteFloat
    completion_rate: FiniteFloat
    notes: List[NonEmptyStr]


class LiquidityScenarioResult(MsModel):
    id: NonEmptyStr
    name: NonEmptyStr
    description: NonEmptyStr
    spread_bps: FiniteFloat
    total_depth: FiniteFloat
    depth_imbalance: FiniteFloat
    microprice: FiniteFloat
    immediate_shortfall_bps: FiniteFloat
    twap_shortfall_bps: FiniteFloat
    vwap_shortfall_bps: FiniteFloat
    pov_shortfall_bps: FiniteFloat
    notes: List[NonEmptyStr]


class MarketMicrostructureAnalysisResponse(MsModel):
    data_status: Literal["static_sample"] = "static_sample"
    instrument_summary: InstrumentSummary
    order_book_summary: OrderBookSummary
    depth_table: List[DepthLevel]
    trade_tape_summary: TradeTapeSummary
    execution_summary: ExecutionSummary
    schedule_comparison: List[ScheduleComparisonResult]
    liquidity_scenarios: List[LiquidityScenarioResult]
    notes: List[NonEmptyStr]
    disclaimer: NonEmptyStr


class MicrostructureSampleResponse(MsModel):
    instruments: List[MarketMicrostructureAnalysisRequest]
    data_status: Literal["static_sample"] = "static_sample"
    disclaimer: NonEmptyStr
    notes: List[NonEmptyStr]
