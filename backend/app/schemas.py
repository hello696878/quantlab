"""
Pydantic request / response schemas for the QuantLab backtesting API.
"""

from typing import List

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------

class BacktestRequest(BaseModel):
    ticker: str = Field(
        default="SPY",
        description="Yahoo Finance ticker symbol (e.g. SPY, AAPL, BTC-USD).",
    )
    start_date: str = Field(
        default="2015-01-01",
        description="Backtest start date in YYYY-MM-DD format.",
    )
    end_date: str = Field(
        default="2023-12-31",
        description="Backtest end date in YYYY-MM-DD format (exclusive in yfinance).",
    )
    fast_window: int = Field(
        default=50,
        ge=2,
        description="Fast SMA look-back window in trading days.",
    )
    slow_window: int = Field(
        default=200,
        ge=2,
        description="Slow SMA look-back window in trading days.",
    )
    transaction_cost_bps: float = Field(
        default=10.0,
        ge=0.0,
        description="Round-trip transaction cost in basis points (10 bps = 0.10%).",
    )
    initial_capital: float = Field(
        default=100_000.0,
        gt=0,
        description="Starting capital in USD.",
    )


# ---------------------------------------------------------------------------
# Response building blocks
# ---------------------------------------------------------------------------

class PerformanceMetrics(BaseModel):
    """Annualised and total performance statistics for one equity curve."""

    total_return: float = Field(description="Total return as a decimal (0.25 = 25%).")
    cagr: float = Field(description="Compound annual growth rate as a decimal.")
    sharpe_ratio: float = Field(description="Annualised Sharpe ratio (rf = 0%).")
    sortino_ratio: float = Field(description="Annualised Sortino ratio (rf = 0%).")
    max_drawdown: float = Field(description="Maximum peak-to-trough drawdown as a decimal (negative).")
    volatility: float = Field(description="Annualised volatility as a decimal.")
    win_rate: float = Field(description="Fraction of trading days with a positive return.")
    num_days: int = Field(description="Number of trading days in the period.")


class TradeRecord(BaseModel):
    """A single BUY or SELL event."""

    date: str = Field(description="Trade date in YYYY-MM-DD format.")
    action: str = Field(description="'BUY' or 'SELL'.")
    price: float = Field(description="Execution price (adjusted close).")
    shares: float = Field(description="Approximate number of shares traded.")
    cost: float = Field(description="Estimated transaction cost in USD.")


class EquityPoint(BaseModel):
    """One daily data point on the equity curve."""

    date: str
    strategy: float = Field(description="Strategy portfolio value in USD.")
    benchmark: float = Field(description="Buy-and-hold portfolio value in USD.")


# ---------------------------------------------------------------------------
# Full response
# ---------------------------------------------------------------------------

class BacktestResponse(BaseModel):
    ticker: str
    start_date: str
    end_date: str
    fast_window: int
    slow_window: int
    transaction_cost_bps: float
    initial_capital: float
    strategy_metrics: PerformanceMetrics
    benchmark_metrics: PerformanceMetrics
    equity_curve: List[EquityPoint]
    trades: List[TradeRecord]
    num_trades: int = Field(description="Total number of BUY + SELL trade events.")
