"""
Pydantic request / response schemas for the QuantLab backtesting API.
"""

import math
from datetime import date
from typing import Annotated, Dict, List, Literal, Optional, Union

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


# Strategy direction modes.  Long-only (the default, original behaviour),
# short-only, or long/short.  Supported by SMA Crossover, Momentum and
# Volatility Breakout.
PositionMode = Literal["long_only", "short_only", "long_short"]

_POSITION_MODE_FIELD = Field(
    default="long_only",
    description=(
        "Strategy direction: 'long_only' (default — bullish→long, else cash), "
        "'short_only' (bearish→short, else cash), or 'long_short' "
        "(bullish→long, bearish→short).  No leverage; |position| ≤ 1."
    ),
)


# ---------------------------------------------------------------------------
# Transaction-cost / slippage model (research v1)
# ---------------------------------------------------------------------------

# All costs are basis points charged on trade *turnover* (|Δposition|), so a
# long↔short flip (turnover 2) costs twice a single open.  The model only
# resolves to an effective per-side bps value; the backtest engine's turnover
# math is unchanged.
CostModelType = Literal["simple_bps", "commission_slippage", "conservative"]


class CostModel(BaseModel):
    """
    Optional transaction-cost / slippage assumptions for a backtest.

    * ``simple_bps``          — one ``transaction_cost_bps`` value (default;
      falls back to the request's top-level ``transaction_cost_bps`` when
      omitted, so existing requests are unchanged).
    * ``commission_slippage`` — ``commission_bps + slippage_bps + spread_bps``
      (``spread_bps`` optional, defaults to 0).
    * ``conservative``        — preset 10 + 10 + 5 = 25 bps/side
      ("higher assumed execution friction").
    """

    type: CostModelType = "simple_bps"
    transaction_cost_bps: Optional[float] = Field(
        default=None,
        ge=0.0,
        lt=10_000.0,
        description="simple_bps: one-way cost in bps (falls back to the request's transaction_cost_bps).",
    )
    commission_bps: Optional[float] = Field(
        default=None, ge=0.0, lt=10_000.0, description="commission_slippage: commission in bps."
    )
    slippage_bps: Optional[float] = Field(
        default=None, ge=0.0, lt=10_000.0, description="commission_slippage: slippage in bps."
    )
    spread_bps: Optional[float] = Field(
        default=None, ge=0.0, lt=10_000.0, description="commission_slippage: optional half-spread in bps."
    )

    @model_validator(mode="after")
    def check_effective_cost(self) -> "CostModel":
        """Ensure resolved commission/slippage totals stay inside engine bounds."""
        if self.type == "commission_slippage":
            effective = (
                (self.commission_bps or 0.0)
                + (self.slippage_bps or 0.0)
                + (self.spread_bps or 0.0)
            )
            if effective >= 10_000.0:
                raise ValueError(
                    "commission_bps + slippage_bps + spread_bps must be less than 10,000 bps."
                )
        return self


class CostModelResolved(BaseModel):
    """The cost model after resolution, echoed on the response for display."""

    type: CostModelType
    label: str
    commission_bps: float
    slippage_bps: float
    spread_bps: float
    effective_bps_per_side: float = Field(
        description="Total per-side cost in bps applied on turnover (|Δposition|)."
    )


_COST_MODEL_FIELD = Field(
    default=None,
    description=(
        "Optional transaction-cost / slippage model. When omitted, the simple "
        "transaction_cost_bps is used (backward-compatible default)."
    ),
)


# ---------------------------------------------------------------------------
# Position sizing (research v1)
# ---------------------------------------------------------------------------

# Position sizing scales the *magnitude* of a strategy's position after signals
# are generated — it never changes signal timing or direction.  All modes keep
# |exposure| ≤ 1 (no leverage by default).
PositionSizingType = Literal[
    "full_allocation", "fixed_fraction", "volatility_target", "max_exposure"
]
PositionSizingInputType = Literal[
    "full", "full_allocation", "fixed_fraction", "volatility_target", "max_exposure"
]


class PositionSizing(BaseModel):
    """
    Optional position-sizing model for a single-asset backtest.

    * ``full_allocation``    — full allocation (default; ±100% on a signal,
      identical to the original behaviour).  Legacy ``"full"`` is still
      accepted and normalized.
    * ``fixed_fraction``     — allocate a fixed ``fraction`` (0–1) of capital on
      each signal; the rest stays in cash.
    * ``volatility_target``  — scale exposure toward an annualized
      ``target_volatility`` using a rolling realized-vol estimate
      (``lookback_days`` days, default 20).  Capped by ``max_exposure`` (default
      1.0) — it only de-levers in high-vol regimes (no leverage).
    * ``max_exposure``       — cash reserve: cap ``|exposure|`` at
      ``max_exposure`` (0–1); the remainder is always held in cash.
    """

    type: PositionSizingInputType = "full_allocation"
    fraction: Optional[float] = Field(
        default=None, gt=0.0, le=1.0, description="fixed_fraction: capital fraction (0–1]."
    )
    target_volatility: Optional[float] = Field(
        default=None,
        gt=0.0,
        le=2.0,
        description="volatility_target: annualized target volatility (e.g. 0.15 = 15%).",
    )
    lookback_days: Optional[int] = Field(
        default=None,
        ge=5,
        le=2520,
        validation_alias=AliasChoices("lookback_days", "vol_lookback"),
        description="volatility_target: realized-vol lookback in trading days (default 20).",
    )
    max_exposure: Optional[float] = Field(
        default=None,
        gt=0.0,
        le=1.0,
        description=(
            "max_exposure / volatility_target: cap on |exposure| (0–1]; "
            "the remainder stays in cash."
        ),
    )

    @model_validator(mode="after")
    def normalize_and_check(self) -> "PositionSizing":
        if self.type == "full":
            self.type = "full_allocation"
        if self.type == "fixed_fraction" and self.fraction is None:
            raise ValueError("fixed_fraction position sizing requires fraction.")
        if self.type == "max_exposure" and self.max_exposure is None:
            raise ValueError("max_exposure position sizing requires max_exposure.")
        return self


class PositionSizingResolved(BaseModel):
    """The position-sizing config after resolution, echoed on the response."""

    type: PositionSizingType
    label: str
    fraction: Optional[float] = None
    target_volatility: Optional[float] = None
    lookback_days: Optional[int] = None
    max_exposure: Optional[float] = None


_POSITION_SIZING_FIELD = Field(
    default=None,
    description=(
        "Optional position-sizing model. When omitted, full_allocation is used "
        "(backward-compatible default). Sizing scales exposure magnitude only — "
        "signal timing / direction are unchanged, and |exposure| ≤ 1."
    ),
)


# ---------------------------------------------------------------------------
# Risk management (research v1)
# ---------------------------------------------------------------------------

# Risk-management rules run *after* a strategy signal generates a position.
# They only ever **close a position to cash** (never reverse it); a later new
# signal can re-enter.  Rules are evaluated on daily closes with the same
# one-bar-delay convention as the signal layer (no lookahead).
RiskManagementType = Literal[
    "none",
    "fixed_stop_take_profit",
    "trailing_stop",
    "max_holding_days",
    "combined",
]


class RiskManagement(BaseModel):
    """
    Optional risk-management exits for a single-asset backtest.

    * ``none``                  — no risk exits (default; signal-based exits only,
      identical to the original behaviour).
    * ``fixed_stop_take_profit``— ``stop_loss_pct`` and/or ``take_profit_pct``
      relative to the entry price.
    * ``trailing_stop``         — ``trailing_stop_pct`` from the peak (long) /
      trough (short) since entry.
    * ``max_holding_days``      — exit after ``max_holding_days`` bars.
    * ``combined``              — any combination of the above (at least one).

    All percentages are decimals (0.10 = 10%).  Exits close to cash only — they
    never reverse a position.
    """

    type: RiskManagementType = "none"
    stop_loss_pct: Optional[float] = Field(
        default=None, gt=0.0, le=1.0, description="Stop loss as a decimal (0.10 = 10%)."
    )
    take_profit_pct: Optional[float] = Field(
        default=None, gt=0.0, le=5.0, description="Take profit as a decimal (0.20 = 20%)."
    )
    trailing_stop_pct: Optional[float] = Field(
        default=None, gt=0.0, le=1.0, description="Trailing stop as a decimal (0.10 = 10%)."
    )
    max_holding_days: Optional[int] = Field(
        default=None, ge=1, le=10_000, description="Max bars to hold before exiting to cash."
    )

    @model_validator(mode="after")
    def check_active_rules(self) -> "RiskManagement":
        if self.type == "fixed_stop_take_profit":
            if self.stop_loss_pct is None and self.take_profit_pct is None:
                raise ValueError(
                    "fixed_stop_take_profit requires stop_loss_pct and/or take_profit_pct."
                )
        elif self.type == "trailing_stop":
            if self.trailing_stop_pct is None:
                raise ValueError("trailing_stop requires trailing_stop_pct.")
        elif self.type == "max_holding_days":
            if self.max_holding_days is None:
                raise ValueError("max_holding_days requires max_holding_days.")
        elif self.type == "combined":
            if not any(
                v is not None
                for v in (
                    self.stop_loss_pct,
                    self.take_profit_pct,
                    self.trailing_stop_pct,
                    self.max_holding_days,
                )
            ):
                raise ValueError("combined risk management requires at least one active rule.")
        return self


class RiskManagementResolved(BaseModel):
    """The risk-management config after resolution, echoed on the response."""

    type: RiskManagementType
    label: str
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    trailing_stop_pct: Optional[float] = None
    max_holding_days: Optional[int] = None


class RiskDiagnostics(BaseModel):
    """Counts of risk-exit events (present only when risk rules are active)."""

    risk_exit_count: int
    stop_loss_count: int
    take_profit_count: int
    trailing_stop_count: int
    max_holding_exit_count: int
    risk_exit_rate: float = Field(
        description="Fraction of position entries that ended via a risk exit (0–1)."
    )


_RISK_MANAGEMENT_FIELD = Field(
    default=None,
    description=(
        "Optional risk-management rules. When omitted, no risk exits are applied "
        "(backward-compatible default). Rules close positions to cash only — they "
        "never reverse a position, and a later new signal can re-enter."
    ),
)


# ---------------------------------------------------------------------------
# Annualization convention (research v1)
# ---------------------------------------------------------------------------

# Annualized metrics (CAGR, volatility, Sharpe, Sortino, Calmar) depend on how
# many return periods make up a year.  This only rescales metrics — it never
# changes trades, the equity curve, or total return.
AnnualizationMode = Literal["trading_days_252", "crypto_365", "auto"]

_ANNUALIZATION_FIELD = Field(
    default=None,
    description=(
        "Optional annualization convention for risk metrics: 'trading_days_252' "
        "(default, equities/ETFs), 'crypto_365' (24/7 crypto daily data), or "
        "'auto' (infer from the ticker). When omitted, 252 is used "
        "(backward-compatible). Affects CAGR / Calmar / volatility / Sharpe / "
        "Sortino scaling only — trades and total return are unchanged."
    ),
)


# ---------------------------------------------------------------------------
# Robustness Lab (research v1)
# ---------------------------------------------------------------------------

class RobustnessConfig(BaseModel):
    """
    Optional bootstrap robustness analysis for a single-asset backtest.

    Disabled by default — normal backtests run exactly as before.  When
    enabled, daily strategy returns are block-bootstrap resampled (blocks
    preserve short-term autocorrelation; ``block_size=1`` degenerates to an
    i.i.d. bootstrap) to estimate how sensitive the result is to the ordering
    and sampling of historical returns.  Deterministic for a given seed.
    """

    enabled: bool = False
    method: Literal["block_bootstrap_returns"] = "block_bootstrap_returns"
    n_simulations: int = Field(default=1000, ge=100, le=5000)
    block_size: int = Field(default=5, ge=1, le=60)
    seed: int = Field(default=42, ge=0, le=2**31 - 1)


_ROBUSTNESS_FIELD = Field(
    default=None,
    description=(
        "Optional bootstrap robustness analysis. When omitted or disabled, the "
        "backtest runs exactly as before with no extra computation. Robustness "
        "diagnostics are research tools, not guarantees."
    ),
)


class RobustnessSummary(BaseModel):
    """Percentile summary of the bootstrap simulation distribution."""

    median_final_return: float
    p05_final_return: float
    p95_final_return: float
    probability_of_loss: float = Field(ge=0.0, le=1.0)
    probability_of_outperforming_benchmark: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Fraction of simulations whose final return beats the configured "
            "benchmark's actual total return (absent when benchmark mode is none "
            "or benchmark data was unavailable)."
        ),
    )
    median_max_drawdown: float
    p95_max_drawdown: float = Field(
        description="95th-percentile drawdown *severity* (the bad tail; more negative than the median)."
    )
    median_sharpe: float
    p05_sharpe: float
    p95_sharpe: float


class RobustnessHistogramBin(BaseModel):
    """One bin of the simulated final-return histogram (compact chart payload)."""

    lower: float
    upper: float
    count: int


class RobustnessResult(BaseModel):
    """Bootstrap robustness block (present only when analysis was requested)."""

    enabled: bool = True
    method: str = "block_bootstrap_returns"
    n_simulations: int
    block_size: int
    seed: int
    summary: Optional[RobustnessSummary] = Field(
        default=None, description="Null when there was not enough data to simulate."
    )
    final_return_histogram: List[RobustnessHistogramBin] = Field(
        default_factory=list,
        description="~20-bin histogram of simulated final returns (chart payload).",
    )
    grade: Optional[Literal["A", "B", "C", "D", "F"]] = Field(
        default=None,
        description=(
            "Heuristic robustness grade — a transparent rule-of-thumb summary, "
            "not a trading recommendation (null when not computable)."
        ),
    )
    deflated_sharpe: Optional[float] = Field(
        default=None,
        description=(
            "Always null in v1: a deflated Sharpe needs the number of tried "
            "configurations and distributional assumptions. Planned for v2."
        ),
    )
    warnings: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Reproducibility / config hash (research v1)
# ---------------------------------------------------------------------------

class Reproducibility(BaseModel):
    """Deterministic fingerprint of the normalized, result-changing inputs.

    Same normalized config → same hash.  The hash identifies *input
    assumptions* only — external data providers can revise history, so exact
    output reproducibility additionally needs the data-quality metadata (and,
    in future, dataset version hashes).
    """

    schema_version: str = Field(description="Canonical-config schema version.")
    config_hash: str = Field(description="Short display hash (first 12 hex chars).")
    config_hash_full: str = Field(description="Full SHA-256 hex of the canonical config.")
    canonical_config_json: str = Field(
        description="Compact canonical JSON the hash was computed over (for audit)."
    )


# ---------------------------------------------------------------------------
# Benchmark / active performance analytics (research v1)
# ---------------------------------------------------------------------------

# Benchmark comparison never changes strategy trades — it only compares the
# strategy's performance against a reference asset on date-aligned returns.
BenchmarkMode = Literal["none", "buy_and_hold_same_asset", "custom_ticker"]


class BenchmarkConfig(BaseModel):
    """
    Optional benchmark configuration for a backtest / comparison.

    * ``buy_and_hold_same_asset`` — hold the strategy's own asset over the same
      period (default; no transaction costs on the benchmark).
    * ``custom_ticker``           — buy-and-hold of another ticker (e.g. SPY),
      fetched via the same data provider and aligned by date (inner join).
    * ``none``                    — no benchmark analytics.
    """

    mode: BenchmarkMode = "buy_and_hold_same_asset"
    ticker: Optional[str] = Field(
        default=None, description="Benchmark ticker — required for custom_ticker."
    )

    @model_validator(mode="after")
    def check_ticker(self) -> "BenchmarkConfig":
        if self.mode == "custom_ticker":
            if self.ticker is None or not self.ticker.strip():
                raise ValueError("custom_ticker benchmark requires a non-empty ticker.")
            self.ticker = self.ticker.strip().upper()
        else:
            self.ticker = None  # ignored for none / buy_and_hold_same_asset
        return self


_BENCHMARK_FIELD = Field(
    default=None,
    description=(
        "Optional benchmark configuration. When omitted, buy-and-hold of the "
        "same asset is used (matches the engine's built-in benchmark). "
        "Benchmark analytics never change strategy trades or results."
    ),
)


class BenchmarkMetricsBlock(BaseModel):
    """Benchmark performance over the aligned comparison window."""

    total_return: float
    cagr: float
    volatility: float
    sharpe: float
    max_drawdown: float


class ActiveMetrics(BaseModel):
    """Strategy-vs-benchmark metrics on date-aligned returns (risk-free rate 0).

    Any metric that is not computable (zero variance, zero tracking error,
    insufficient overlap) is null, with an explanatory warning on the parent
    block — never NaN/inf.
    """

    excess_total_return: Optional[float] = None
    excess_cagr: Optional[float] = None
    alpha: Optional[float] = Field(
        default=None,
        description="Annualized: mean(strategy) − beta × mean(benchmark), rf = 0.",
    )
    beta: Optional[float] = None
    correlation: Optional[float] = None
    tracking_error: Optional[float] = Field(
        default=None, description="std(strategy − benchmark returns) × √periods_per_year."
    )
    information_ratio: Optional[float] = None
    aligned_points: Optional[int] = Field(
        default=None, description="Number of aligned return observations used."
    )


class BenchmarkEquityPoint(BaseModel):
    """One point on a custom benchmark's normalized equity curve."""

    date: str
    equity: float


class BenchmarkAnalytics(BaseModel):
    """Benchmark + active-performance block (absent when mode is 'none')."""

    mode: BenchmarkMode
    ticker: Optional[str] = Field(
        default=None, description="Benchmark ticker (the asset itself for buy-and-hold)."
    )
    display_name: str
    metrics: Optional[BenchmarkMetricsBlock] = Field(
        default=None, description="Null when benchmark data could not be used."
    )
    active_metrics: Optional[ActiveMetrics] = None
    equity_curve: Optional[List[BenchmarkEquityPoint]] = Field(
        default=None,
        description=(
            "Normalized benchmark equity (custom_ticker only — the same-asset "
            "benchmark curve is already on the response equity_curve)."
        ),
    )
    data_provider: Optional[str] = Field(
        default=None, description="Provider used for a custom benchmark fetch."
    )
    data_quality: Optional["DataQuality"] = Field(
        default=None, description="Diagnostics for a custom benchmark's data."
    )
    warnings: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Market data quality (research v1)
# ---------------------------------------------------------------------------

class DataQuality(BaseModel):
    """Diagnostics for the price series actually fed to the backtest engine.

    Purely informational — warnings never block a run, and computing the
    diagnostics never modifies prices or results.
    """

    provider: str = Field(description="Data provider: 'yfinance', 'csv_upload', or 'synthetic'.")
    ticker: str = Field(description="Ticker / dataset label the data belongs to.")
    requested_start_date: str = Field(description="Start date the user requested.")
    requested_end_date: str = Field(description="End date the user requested.")
    actual_start_date: Optional[str] = Field(
        default=None, description="First date present in the data (None when empty)."
    )
    actual_end_date: Optional[str] = Field(
        default=None, description="Last date present in the data (None when empty)."
    )
    row_count: int = Field(description="Number of price rows used.")
    missing_value_count: int = Field(description="NaN close values found.")
    duplicate_date_count: int = Field(description="Duplicate index dates found.")
    inferred_frequency: str = Field(
        description="Lightweight frequency guess: business_day / calendar_day / weekly / monthly / unknown."
    )
    calendar_gap_count: int = Field(description="Gaps longer than 5 calendar days.")
    first_price: Optional[float] = Field(default=None, description="First close price.")
    last_price: Optional[float] = Field(default=None, description="Last close price.")
    price_column_used: str = Field(description="Which price column fed the engine.")
    adjusted: bool = Field(
        description="True when prices are split/dividend-adjusted (yfinance auto_adjust)."
    )
    warnings: List[str] = Field(
        default_factory=list, description="Informational data warnings (never blocking)."
    )


class AnnualizationResolved(BaseModel):
    """Resolved annualization echo (present on backtest / comparison responses)."""

    mode: AnnualizationMode = Field(description="Requested annualization mode.")
    mode_used: Literal["trading_days_252", "crypto_365"] = Field(
        description="Concrete convention applied after resolution."
    )
    periods_per_year: int = Field(description="Return periods per year used (252 or 365).")
    warning: Optional[str] = Field(
        default=None, description="Set when 'auto' could not confirm the asset class."
    )


# ===========================================================================
# Requests
# ===========================================================================

class BacktestRequest(BaseModel):
    """Parameters for the SMA crossover backtest endpoint."""

    cost_model: Optional[CostModel] = _COST_MODEL_FIELD
    position_sizing: Optional[PositionSizing] = _POSITION_SIZING_FIELD
    risk_management: Optional[RiskManagement] = _RISK_MANAGEMENT_FIELD
    annualization_mode: Optional[AnnualizationMode] = _ANNUALIZATION_FIELD
    benchmark: Optional[BenchmarkConfig] = _BENCHMARK_FIELD
    robustness: Optional[RobustnessConfig] = _ROBUSTNESS_FIELD

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
        default=20,
        ge=2,
        description=(
            "Fast SMA look-back window in trading days "
            "(demo-friendly default: 20; use 50 for the classic long-term trend)."
        ),
    )
    slow_window: int = Field(
        default=100,
        ge=2,
        description=(
            "Slow SMA look-back window in trading days "
            "(demo-friendly default: 100; use 200 for the classic golden-cross)."
        ),
    )
    transaction_cost_bps: float = Field(
        default=10.0,
        ge=0.0,
        lt=10_000.0,
        description="One-way transaction cost in basis points (10 bps = 0.10%).",
    )
    initial_capital: float = Field(
        default=100_000.0,
        gt=0,
        description="Starting capital in USD.",
    )
    position_mode: PositionMode = _POSITION_MODE_FIELD


class RsiBacktestRequest(BaseModel):
    """Parameters for the RSI mean-reversion backtest endpoint."""

    cost_model: Optional[CostModel] = _COST_MODEL_FIELD
    position_sizing: Optional[PositionSizing] = _POSITION_SIZING_FIELD
    risk_management: Optional[RiskManagement] = _RISK_MANAGEMENT_FIELD
    annualization_mode: Optional[AnnualizationMode] = _ANNUALIZATION_FIELD
    benchmark: Optional[BenchmarkConfig] = _BENCHMARK_FIELD
    robustness: Optional[RobustnessConfig] = _ROBUSTNESS_FIELD

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
    rsi_window: int = Field(
        default=14,
        ge=2,
        le=500,
        description="RSI look-back window in trading days.",
    )
    oversold_threshold: float = Field(
        default=35.0,
        ge=1.0,
        lt=100.0,
        description=(
            "Enter long when RSI falls strictly below this level "
            "(demo-friendly default: 35; use 30 for a stricter, classic oversold)."
        ),
    )
    exit_threshold: float = Field(
        default=55.0,
        gt=1.0,
        le=100.0,
        description="Exit long when RSI rises above this level (default: 55).",
    )
    transaction_cost_bps: float = Field(
        default=10.0,
        ge=0.0,
        lt=10_000.0,
        description="One-way transaction cost in basis points.",
    )
    initial_capital: float = Field(
        default=100_000.0,
        gt=0,
        description="Starting capital in USD.",
    )

    @model_validator(mode="after")
    def check_thresholds(self) -> "RsiBacktestRequest":
        if self.oversold_threshold >= self.exit_threshold:
            raise ValueError(
                f"oversold_threshold ({self.oversold_threshold}) must be less than "
                f"exit_threshold ({self.exit_threshold})."
            )
        return self


class BbBacktestRequest(BaseModel):
    """Parameters for the Bollinger Band mean-reversion backtest endpoint."""

    cost_model: Optional[CostModel] = _COST_MODEL_FIELD
    position_sizing: Optional[PositionSizing] = _POSITION_SIZING_FIELD
    risk_management: Optional[RiskManagement] = _RISK_MANAGEMENT_FIELD
    annualization_mode: Optional[AnnualizationMode] = _ANNUALIZATION_FIELD
    benchmark: Optional[BenchmarkConfig] = _BENCHMARK_FIELD
    robustness: Optional[RobustnessConfig] = _ROBUSTNESS_FIELD

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
    bb_window: int = Field(
        default=20,
        ge=2,
        le=500,
        description="Bollinger Band rolling look-back window in trading days.",
    )
    num_std: float = Field(
        default=1.8,
        gt=0.0,
        le=10.0,
        description=(
            "Width of the bands in standard deviations "
            "(demo-friendly default: 1.8; classic Bollinger uses 2.0)."
        ),
    )
    exit_band: Literal["middle", "upper"] = Field(
        default="middle",
        description=(
            "Which band to target for exit: "
            "'middle' exits when price recovers to the SMA (default); "
            "'upper' holds until price reaches the upper band."
        ),
    )
    transaction_cost_bps: float = Field(
        default=10.0,
        ge=0.0,
        lt=10_000.0,
        description="One-way transaction cost in basis points.",
    )
    initial_capital: float = Field(
        default=100_000.0,
        gt=0,
        description="Starting capital in USD.",
    )


class MomentumBacktestRequest(BaseModel):
    """Parameters for the time-series momentum backtest endpoint."""

    cost_model: Optional[CostModel] = _COST_MODEL_FIELD
    position_sizing: Optional[PositionSizing] = _POSITION_SIZING_FIELD
    risk_management: Optional[RiskManagement] = _RISK_MANAGEMENT_FIELD
    annualization_mode: Optional[AnnualizationMode] = _ANNUALIZATION_FIELD
    benchmark: Optional[BenchmarkConfig] = _BENCHMARK_FIELD
    robustness: Optional[RobustnessConfig] = _ROBUSTNESS_FIELD

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
    momentum_window: int = Field(
        default=63,
        ge=1,
        le=1000,
        description=(
            "Trailing return look-back period in trading days "
            "(demo-friendly default: 63 ≈ 3 months; 126 ≈ 6 months, 252 ≈ 12)."
        ),
    )
    entry_threshold: float = Field(
        default=0.0,
        ge=-1.0,
        le=1.0,
        description=(
            "Enter long when the trailing return strictly exceeds this value "
            "(decimal, e.g. 0.05 = 5 %).  Default 0.0 → any positive momentum."
        ),
    )
    exit_threshold: float = Field(
        default=0.0,
        ge=-1.0,
        le=1.0,
        description=(
            "Exit long when the trailing return falls to or below this value "
            "(decimal, e.g. -0.02 = −2 %).  Must be ≤ entry_threshold."
        ),
    )
    transaction_cost_bps: float = Field(
        default=10.0,
        ge=0.0,
        lt=10_000.0,
        description="One-way transaction cost in basis points.",
    )
    initial_capital: float = Field(
        default=100_000.0,
        gt=0,
        description="Starting capital in USD.",
    )

    position_mode: PositionMode = _POSITION_MODE_FIELD

    @model_validator(mode="after")
    def check_thresholds(self) -> "MomentumBacktestRequest":
        if self.entry_threshold < self.exit_threshold:
            raise ValueError(
                f"entry_threshold ({self.entry_threshold}) must be >= "
                f"exit_threshold ({self.exit_threshold})."
            )
        return self


class PairsBacktestRequest(BaseModel):
    """Parameters for the pairs trading / statistical arbitrage endpoint."""

    cost_model: Optional[CostModel] = _COST_MODEL_FIELD

    asset_y: str = Field(
        default="KO",
        description=(
            "Yahoo Finance ticker for asset Y (the 'dependent' leg, e.g. KO). "
            "A positive spread means Y is expensive relative to X."
        ),
    )
    asset_x: str = Field(
        default="PEP",
        description=(
            "Yahoo Finance ticker for asset X (the 'independent' leg, e.g. PEP)."
        ),
    )
    start_date: str = Field(
        default="2015-01-01",
        description="Backtest start date in YYYY-MM-DD format.",
    )
    end_date: str = Field(
        default="2023-12-31",
        description="Backtest end date in YYYY-MM-DD format.",
    )
    lookback_window: int = Field(
        default=60,
        ge=10,
        le=500,
        description=(
            "Rolling window for the z-score of the log-ratio spread "
            "(default: 60 trading days ~ 3 months)."
        ),
    )
    entry_z_score: float = Field(
        default=1.5,
        gt=0.0,
        le=5.0,
        description=(
            "Enter a position when |z-score| exceeds this threshold "
            "(demo-friendly default: 1.5; 2.0 is stricter/classic).  "
            "Must be > exit_z_score."
        ),
    )
    exit_z_score: float = Field(
        default=0.5,
        ge=0.0,
        lt=5.0,
        description=(
            "Mean-reversion exit threshold around zero: long-spread exits when "
            "z-score > -exit_z_score; short-spread exits when z-score < "
            "+exit_z_score (default: 0.5).  Must be < entry_z_score."
        ),
    )
    transaction_cost_bps: float = Field(
        default=10.0,
        ge=0.0,
        lt=10_000.0,
        description="One-way transaction cost per leg in basis points.",
    )
    initial_capital: float = Field(
        default=100_000.0,
        gt=0,
        description="Starting capital in USD.",
    )

    @model_validator(mode="after")
    def check_z_scores(self) -> "PairsBacktestRequest":
        if self.entry_z_score <= self.exit_z_score:
            raise ValueError(
                f"entry_z_score ({self.entry_z_score}) must be strictly greater "
                f"than exit_z_score ({self.exit_z_score})."
            )
        return self

    @model_validator(mode="after")
    def check_assets_differ(self) -> "PairsBacktestRequest":
        if self.asset_y.strip().upper() == self.asset_x.strip().upper():
            raise ValueError("asset_y and asset_x must be different tickers.")
        return self


class VbBacktestRequest(BaseModel):
    """Parameters for the volatility breakout backtest endpoint."""

    cost_model: Optional[CostModel] = _COST_MODEL_FIELD
    position_sizing: Optional[PositionSizing] = _POSITION_SIZING_FIELD
    risk_management: Optional[RiskManagement] = _RISK_MANAGEMENT_FIELD
    annualization_mode: Optional[AnnualizationMode] = _ANNUALIZATION_FIELD
    benchmark: Optional[BenchmarkConfig] = _BENCHMARK_FIELD
    robustness: Optional[RobustnessConfig] = _ROBUSTNESS_FIELD

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
    lookback_window: int = Field(
        default=20,
        ge=2,
        le=500,
        description=(
            "Rolling high/low lookback window in trading days (default: 20). "
            "Must be ≥ 2."
        ),
    )
    breakout_multiplier: float = Field(
        default=0.3,
        gt=0.0,
        le=10.0,
        description=(
            "Entry threshold: prior rolling high plus this multiple of the "
            "prior rolling high-low range (demo-friendly default: 0.3; raise "
            "toward 1.0+ for a stricter breakout buffer)."
        ),
    )
    exit_window: int = Field(
        default=10,
        ge=1,
        le=500,
        description=(
            "Rolling mean window for the exit level (default: 10)."
        ),
    )
    transaction_cost_bps: float = Field(
        default=10.0,
        ge=0.0,
        lt=10_000.0,
        description="One-way transaction cost in basis points.",
    )
    initial_capital: float = Field(
        default=100_000.0,
        gt=0,
        description="Starting capital in USD.",
    )
    position_mode: PositionMode = _POSITION_MODE_FIELD


# ===========================================================================
# Response building blocks
# ===========================================================================

class PerformanceMetrics(BaseModel):
    """Annualised and total performance statistics for one equity curve."""

    total_return: float = Field(description="Total return as a decimal (0.25 = 25%).")
    cagr: float = Field(description="Compound annual growth rate as a decimal.")
    sharpe_ratio: float = Field(description="Annualised Sharpe ratio (rf = 0%).")
    sortino_ratio: float = Field(description="Annualised Sortino ratio (rf = 0%).")
    max_drawdown: float = Field(description="Maximum peak-to-trough drawdown as a decimal (negative).")
    volatility: float = Field(description="Annualised volatility as a decimal.")
    calmar_ratio: float = Field(
        description="Calmar ratio (CAGR / |max_drawdown|).  0.0 when max_drawdown is zero."
    )
    win_rate: float = Field(description="Fraction of trading days with a positive return.")
    num_days: int = Field(description="Number of trading days in the period.")


class TradeRecord(BaseModel):
    """A single trade event."""

    date: str = Field(description="Trade date in YYYY-MM-DD format.")
    action: str = Field(description="'BUY', 'SELL', 'LONG SPREAD', 'SHORT SPREAD', or 'EXIT'.")
    price: float = Field(description="Execution price (adjusted close).")
    shares: float = Field(description="Approximate number of shares traded.")
    cost: float = Field(description="Estimated transaction cost in USD.")
    reason: Optional[str] = Field(
        default=None,
        description=(
            "Why the trade happened (only when risk management is active): "
            "signal_entry / signal_exit / signal_flip / stop_loss / take_profit / "
            "trailing_stop / max_holding_days."
        ),
    )


class EquityPoint(BaseModel):
    """One daily data point on the equity curve."""

    date: str
    strategy: float = Field(description="Strategy portfolio value in USD.")
    benchmark: float = Field(description="Buy-and-hold portfolio value in USD.")


# ===========================================================================
# Full response  (shared by all six strategy endpoints)
# ===========================================================================

class BacktestDiagnostics(BaseModel):
    """
    Direction / exposure diagnostics for a single-asset backtest.

    Long/short gross returns are pre-cost and decompose multiplicatively
    (cash bars contribute a factor of 1).  Borrow costs, margin and funding are
    **not** modelled.
    """

    long_trade_count: int = Field(description="Entries into a long position (BUY + FLIP_TO_LONG).")
    short_trade_count: int = Field(description="Entries into a short position (SHORT + FLIP_TO_SHORT).")
    percent_time_long: float = Field(description="Fraction of bars held long (0–1).")
    percent_time_short: float = Field(description="Fraction of bars held short (0–1).")
    percent_time_cash: float = Field(description="Fraction of bars in cash (0–1).")
    gross_long_return: float = Field(description="Pre-cost compounded return earned while long.")
    gross_short_return: float = Field(description="Pre-cost compounded return earned while short.")
    short_return_contribution: float = Field(
        description="Incremental compound effect of the short legs on total gross return."
    )
    turnover_estimate: float = Field(description="Total |Δposition| over the period.")


class BacktestResponse(BaseModel):
    """
    Universal backtest response.

    Strategy identification
    -----------------------
    ``strategy`` identifies which strategy produced this result:
    ``"sma_crossover"``, ``"rsi_mean_reversion"``, ``"bollinger_band"``,
    ``"momentum"``, ``"volatility_breakout"``, ``"pairs"``, or ``"custom"``.

    Strategy-specific fields
    ------------------------
    * SMA      : ``fast_window``, ``slow_window`` (0 for other strategies).
    * RSI      : ``rsi_window``, ``oversold_threshold``, ``exit_threshold``
                 (None otherwise).
    * BB       : ``bb_window``, ``bb_num_std``, ``bb_exit_band`` (None otherwise).
    * Momentum : ``momentum_window``, ``momentum_entry_threshold``,
                 ``momentum_exit_threshold`` (None otherwise).
    * VB       : ``vb_lookback_window``, ``vb_breakout_multiplier``,
                 ``vb_exit_window`` (None otherwise).
    * Pairs    : ``pairs_asset_y``, ``pairs_asset_x``,
                 ``pairs_lookback_window``, ``pairs_entry_z_score``,
                 ``pairs_exit_z_score`` (None otherwise).

    Backward compatibility
    ----------------------
    All strategy-specific fields carry safe defaults so existing clients that
    read only the fields they care about continue to work without changes.
    """

    ticker: str
    start_date: str
    end_date: str

    # Which strategy produced this result.
    strategy: str = Field(
        default="sma_crossover",
        description=(
            "Strategy identifier: 'sma_crossover', 'rsi_mean_reversion', "
            "'bollinger_band', 'momentum', 'volatility_breakout', 'pairs', "
            "or 'custom'."
        ),
    )

    # SMA params — set to 0 when strategy is not SMA.
    fast_window: int = Field(default=0)
    slow_window: int = Field(default=0)

    # RSI params — None when strategy is not RSI.
    rsi_window: Optional[int] = Field(default=None)
    oversold_threshold: Optional[float] = Field(default=None)
    exit_threshold: Optional[float] = Field(default=None)

    # Bollinger Band params — None when strategy is not bollinger_band.
    bb_window: Optional[int] = Field(default=None)
    bb_num_std: Optional[float] = Field(default=None)
    bb_exit_band: Optional[str] = Field(default=None)

    # Momentum params — None when strategy is not momentum.
    momentum_window: Optional[int] = Field(default=None)
    momentum_entry_threshold: Optional[float] = Field(default=None)
    momentum_exit_threshold: Optional[float] = Field(default=None)

    # Volatility Breakout params — None when strategy is not volatility_breakout.
    vb_lookback_window: Optional[int] = Field(default=None)
    vb_breakout_multiplier: Optional[float] = Field(default=None)
    vb_exit_window: Optional[int] = Field(default=None)

    # Pairs Trading params — None when strategy is not pairs.
    pairs_asset_y: Optional[str] = Field(default=None)
    pairs_asset_x: Optional[str] = Field(default=None)
    pairs_lookback_window: Optional[int] = Field(default=None)
    pairs_entry_z_score: Optional[float] = Field(default=None)
    pairs_exit_z_score: Optional[float] = Field(default=None)

    transaction_cost_bps: float = Field(
        description="Effective per-side transaction cost in bps applied (resolved from cost_model when provided).",
    )
    initial_capital: float
    cost_model: Optional[CostModelResolved] = Field(
        default=None,
        description="Resolved cost model echo (present only when a cost_model was supplied).",
    )
    effective_cost_bps: Optional[float] = Field(
        default=None,
        description="Effective per-side cost in bps applied on turnover (|Δposition|).",
    )
    total_transaction_cost: Optional[float] = Field(
        default=None,
        description="Sum of all per-trade dollar transaction costs over the backtest.",
    )
    cost_drag_return: Optional[float] = Field(
        default=None,
        description="Total return given up to transaction costs (gross-of-cost minus net).",
    )
    position_sizing: Optional[PositionSizingResolved] = Field(
        default=None,
        description="Resolved position-sizing echo (full_allocation when omitted).",
    )
    average_exposure: Optional[float] = Field(
        default=None,
        description="Mean absolute exposure (|position|) over the backtest period.",
    )
    risk_management: Optional[RiskManagementResolved] = Field(
        default=None,
        description="Resolved risk-management echo (present only when risk rules are active).",
    )
    risk_diagnostics: Optional[RiskDiagnostics] = Field(
        default=None,
        description="Risk-exit counts (present only when risk rules are active).",
    )
    annualization_mode: Optional[AnnualizationMode] = Field(
        default=None, description="Requested annualization mode (defaults to trading_days_252)."
    )
    annualization_mode_used: Optional[str] = Field(
        default=None, description="Concrete annualization convention applied (trading_days_252 / crypto_365)."
    )
    periods_per_year: Optional[int] = Field(
        default=None, description="Return periods per year used for annualized metrics (252 or 365)."
    )
    annualization_warning: Optional[str] = Field(
        default=None, description="Set when 'auto' could not confirm the asset class."
    )
    data_provider: Optional[str] = Field(
        default=None, description="Market-data provider used ('yfinance' / 'csv_upload')."
    )
    data_quality: Optional[DataQuality] = Field(
        default=None, description="Diagnostics for the price series fed to the engine."
    )
    benchmark_analytics: Optional[BenchmarkAnalytics] = Field(
        default=None,
        description=(
            "Benchmark + active-performance block (absent when benchmark mode is "
            "'none'). The legacy benchmark_metrics / equity_curve benchmark values "
            "always remain the same-asset buy-and-hold for backward compatibility."
        ),
    )
    reproducibility: Optional[Reproducibility] = Field(
        default=None,
        description="Deterministic config hash of the normalized result-changing inputs.",
    )
    robustness: Optional[RobustnessResult] = Field(
        default=None,
        description=(
            "Bootstrap robustness block (present only when requested via the "
            "robustness config; never changes core backtest results)."
        ),
    )
    position_mode: str = Field(
        default="long_only",
        description="Strategy direction mode used (long_only / short_only / long_short).",
    )
    strategy_metrics: PerformanceMetrics
    benchmark_metrics: PerformanceMetrics
    equity_curve: List[EquityPoint]
    trades: List[TradeRecord]
    num_trades: int = Field(description="Total number of trade events.")
    diagnostics: Optional[BacktestDiagnostics] = Field(
        default=None,
        description="Direction / exposure diagnostics (long/short trade counts, time-in-state, gross contributions, turnover).",
    )


# ===========================================================================
# Research — SMA Parameter Sweep
# ===========================================================================


class SmaSweepRequest(BaseModel):
    """Parameters for the SMA crossover parameter-sweep endpoint."""

    ticker: str = Field(
        default="SPY",
        description="Yahoo Finance ticker symbol.",
    )
    start_date: str = Field(
        default="2015-01-01",
        description="Backtest start date in YYYY-MM-DD format.",
    )
    end_date: str = Field(
        default="2023-12-31",
        description="Backtest end date in YYYY-MM-DD format.",
    )
    fast_windows: List[int] = Field(
        default=[10, 20, 30, 50],
        min_length=1,
        max_length=10,
        description=(
            "Fast SMA window lengths to test.  Each value must be >= 2.  "
            "Maximum 10 values."
        ),
    )
    slow_windows: List[int] = Field(
        default=[50, 100, 150, 200],
        min_length=1,
        max_length=10,
        description=(
            "Slow SMA window lengths to test.  Each value must be >= 2.  "
            "Maximum 10 values."
        ),
    )
    transaction_cost_bps: float = Field(
        default=10.0,
        ge=0.0,
        lt=10_000.0,
        description="One-way transaction cost in basis points.",
    )
    initial_capital: float = Field(
        default=100_000.0,
        gt=0,
        description="Starting capital in USD.",
    )

    @model_validator(mode="after")
    def check_windows(self) -> "SmaSweepRequest":
        for fw in self.fast_windows:
            if fw < 2:
                raise ValueError(
                    f"All fast_windows must be >= 2; got {fw}."
                )
        for sw in self.slow_windows:
            if sw < 2:
                raise ValueError(
                    f"All slow_windows must be >= 2; got {sw}."
                )
        total = len(self.fast_windows) * len(self.slow_windows)
        if total > 100:
            raise ValueError(
                f"Total combinations (len(fast_windows) × len(slow_windows)) "
                f"must be ≤ 100; got {total}."
            )
        return self


class SmaSweepRow(BaseModel):
    """One row in the SMA parameter-sweep result table."""

    fast_window: int = Field(description="Fast SMA window (days).")
    slow_window: int = Field(description="Slow SMA window (days).")
    total_return: float = Field(description="Total return as a decimal.")
    cagr: float = Field(description="Compound annual growth rate as a decimal.")
    sharpe_ratio: float = Field(description="Annualised Sharpe ratio.")
    sortino_ratio: float = Field(description="Annualised Sortino ratio.")
    calmar_ratio: float = Field(description="CAGR divided by absolute max drawdown.")
    max_drawdown: float = Field(description="Maximum drawdown (negative decimal).")
    volatility: float = Field(description="Annualised volatility as a decimal.")
    num_trades: int = Field(description="Total BUY + SELL trade events.")


class SmaSweepResponse(BaseModel):
    """Full response for an SMA parameter-sweep request."""

    ticker: str
    start_date: str
    end_date: str
    transaction_cost_bps: float
    initial_capital: float
    num_combinations: int = Field(
        description=(
            "Number of valid (fast < slow) combinations actually run.  "
            "Pairs where fast >= slow are silently skipped."
        )
    )
    results: List[SmaSweepRow] = Field(
        description=(
            "One row per valid (fast, slow) combination, "
            "ordered by fast_window then slow_window."
        )
    )


# ===========================================================================
# Research — SMA Train/Test Out-of-Sample Validation
# ===========================================================================

_DATE_RE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"


class SmaTrainTestRequest(BaseModel):
    """Parameters for the SMA crossover train/test validation endpoint."""

    ticker: str = Field(
        default="SPY",
        description="Yahoo Finance ticker symbol.",
    )
    start_date: str = Field(
        default="2010-01-01",
        description="Start of the in-sample period (YYYY-MM-DD).",
    )
    split_date: str = Field(
        default="2018-01-01",
        description=(
            "Split point: dates before this are in-sample; "
            "dates from this point onward are out-of-sample (YYYY-MM-DD)."
        ),
    )
    end_date: str = Field(
        default="2023-12-31",
        description="End of the out-of-sample period (YYYY-MM-DD).",
    )
    fast_windows: List[int] = Field(
        default=[10, 20, 30, 50],
        min_length=1,
        max_length=10,
        description="Fast SMA window lengths to sweep (each >= 2, max 10 values).",
    )
    slow_windows: List[int] = Field(
        default=[100, 150, 200],
        min_length=1,
        max_length=10,
        description="Slow SMA window lengths to sweep (each >= 2, max 10 values).",
    )
    transaction_cost_bps: float = Field(
        default=10.0,
        ge=0.0,
        lt=10_000.0,
        description="One-way transaction cost in basis points.",
    )
    initial_capital: float = Field(
        default=100_000.0,
        gt=0,
        description="Starting capital in USD.",
    )
    selection_metric: Literal["sharpe_ratio", "cagr", "calmar_ratio"] = Field(
        default="sharpe_ratio",
        description=(
            "Metric used to pick the best in-sample parameter pair.  "
            "One of: 'sharpe_ratio', 'cagr', 'calmar_ratio'."
        ),
    )

    @model_validator(mode="after")
    def check_dates(self) -> "SmaTrainTestRequest":
        import re
        for name, val in [
            ("start_date", self.start_date),
            ("split_date", self.split_date),
            ("end_date", self.end_date),
        ]:
            if not re.match(_DATE_RE_PATTERN, val):
                raise ValueError(f"{name} must be in YYYY-MM-DD format.")
        if self.start_date >= self.split_date:
            raise ValueError("start_date must be strictly before split_date.")
        if self.split_date >= self.end_date:
            raise ValueError("split_date must be strictly before end_date.")
        return self

    @model_validator(mode="after")
    def check_windows(self) -> "SmaTrainTestRequest":
        for fw in self.fast_windows:
            if fw < 2:
                raise ValueError(f"All fast_windows must be >= 2; got {fw}.")
        for sw in self.slow_windows:
            if sw < 2:
                raise ValueError(f"All slow_windows must be >= 2; got {sw}.")
        total = len(self.fast_windows) * len(self.slow_windows)
        if total > 100:
            raise ValueError(
                f"Total combinations (len(fast_windows) × len(slow_windows)) "
                f"must be ≤ 100; got {total}."
            )
        return self


class SmaTrainTestResponse(BaseModel):
    """Full response for the SMA train/test out-of-sample validation endpoint."""

    # Identity
    ticker: str
    start_date: str
    split_date: str
    end_date: str
    transaction_cost_bps: float
    initial_capital: float
    selection_metric: str

    # Period lengths
    in_sample_days: int = Field(description="Number of in-sample trading days.")
    out_of_sample_days: int = Field(description="Number of out-of-sample trading days.")

    # Best parameters (selected on in-sample data only)
    best_fast_window: int
    best_slow_window: int

    # Metrics for the best-param pair on each period
    in_sample_metrics: PerformanceMetrics
    out_of_sample_metrics: PerformanceMetrics
    out_of_sample_benchmark_metrics: PerformanceMetrics = Field(
        description="Buy-and-hold benchmark over the out-of-sample period."
    )

    # Out-of-sample equity curve
    out_of_sample_equity_curve: List[EquityPoint]

    # Out-of-sample trades
    out_of_sample_trades: List[TradeRecord]
    out_of_sample_num_trades: int

    # Degradation  (OOS value − IS value; negative = deteriorated)
    sharpe_degradation: float = Field(
        description="out_of_sample_sharpe − in_sample_sharpe.  Negative = OOS is worse."
    )
    cagr_degradation: float = Field(
        description="out_of_sample_cagr − in_sample_cagr.  Negative = OOS is worse."
    )
    calmar_degradation: float = Field(
        description="out_of_sample_calmar − in_sample_calmar.  Negative = OOS is worse."
    )
    max_drawdown_worsening: float = Field(
        description=(
            "abs(out_of_sample_max_drawdown) − abs(in_sample_max_drawdown).  "
            "Positive = OOS drawdown is deeper."
        )
    )

    # Warning flag
    oos_collapsed: bool = Field(
        description=(
            "True when OOS Sharpe < 0, or when OOS Sharpe is less than half "
            "of the in-sample Sharpe (large degradation signal)."
        )
    )

    # All in-sample sweep rows (for reference / display)
    all_in_sample_results: List[SmaSweepRow]


# ===========================================================================
# Research — SMA Walk-Forward Optimization
# ===========================================================================


class SmaWalkForwardRequest(BaseModel):
    """Parameters for the SMA walk-forward optimization endpoint."""

    ticker: str = Field(
        default="SPY",
        description="Yahoo Finance ticker symbol.",
    )
    start_date: str = Field(
        default="2010-01-01",
        description="Start of the full data range (YYYY-MM-DD).",
    )
    end_date: str = Field(
        default="2023-12-31",
        description="End of the full data range (YYYY-MM-DD).",
    )
    train_window_days: int = Field(
        default=756,
        ge=10,
        description=(
            "Number of trading days in each rolling training (in-sample) window. "
            "Default 756 ≈ 3 years."
        ),
    )
    test_window_days: int = Field(
        default=126,
        ge=5,
        description=(
            "Number of trading days in each out-of-sample test window. "
            "Default 126 ≈ 6 months."
        ),
    )
    step_days: int = Field(
        default=126,
        ge=1,
        description=(
            "Number of trading days to advance the window each step. "
            "When step_days == test_window_days the test windows are non-overlapping. "
            "Default 126."
        ),
    )
    fast_windows: List[int] = Field(
        default=[10, 20, 30, 40, 50],
        min_length=1,
        max_length=10,
        description="Fast SMA window lengths to sweep (each >= 2, max 10 values).",
    )
    slow_windows: List[int] = Field(
        default=[100, 150, 200, 250],
        min_length=1,
        max_length=10,
        description="Slow SMA window lengths to sweep (each >= 2, max 10 values).",
    )
    selection_metric: Literal["sharpe_ratio", "cagr", "calmar_ratio"] = Field(
        default="sharpe_ratio",
        description="Metric used to select best parameters on each training window.",
    )
    initial_capital: float = Field(
        default=100_000.0,
        gt=0,
        description="Starting capital in USD.",
    )
    transaction_cost_bps: float = Field(
        default=10.0,
        ge=0.0,
        lt=10_000.0,
        description="One-way transaction cost in basis points.",
    )

    @model_validator(mode="after")
    def check_dates(self) -> "SmaWalkForwardRequest":
        import re
        for name, val in [("start_date", self.start_date), ("end_date", self.end_date)]:
            if not re.match(_DATE_RE_PATTERN, val):
                raise ValueError(f"{name} must be in YYYY-MM-DD format.")
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be strictly before end_date.")
        return self

    @model_validator(mode="after")
    def check_windows(self) -> "SmaWalkForwardRequest":
        for fw in self.fast_windows:
            if fw < 2:
                raise ValueError(f"All fast_windows must be >= 2; got {fw}.")
        for sw in self.slow_windows:
            if sw < 2:
                raise ValueError(f"All slow_windows must be >= 2; got {sw}.")
        total = len(self.fast_windows) * len(self.slow_windows)
        if total > 100:
            raise ValueError(
                f"Total combinations (len(fast_windows) × len(slow_windows)) "
                f"must be ≤ 100; got {total}."
            )
        return self


class SmaWalkForwardBestParams(BaseModel):
    """The (fast, slow) parameter pair selected for one walk-forward window."""

    fast_window: int = Field(description="Selected fast SMA window (days).")
    slow_window: int = Field(description="Selected slow SMA window (days).")


class SmaWalkForwardWindow(BaseModel):
    """Results for one walk-forward train/test window."""

    window_index: int = Field(description="0-based window index.")
    train_start_date: str = Field(description="First date of the training period.")
    train_end_date: str = Field(description="Last date of the training period.")
    test_start_date: str = Field(description="First date of the test period.")
    test_end_date: str = Field(description="Last date of the test period.")
    train_days: int = Field(description="Number of training-period trading days.")
    test_days: int = Field(description="Number of test-period trading days.")
    best_fast_window: int = Field(description="Fast window selected on training data.")
    best_slow_window: int = Field(description="Slow window selected on training data.")
    train_metrics: PerformanceMetrics = Field(
        description="Performance of the best params on the training window."
    )
    test_metrics: PerformanceMetrics = Field(
        description="Performance of the selected params on the test window."
    )
    test_benchmark_metrics: PerformanceMetrics = Field(
        description="Buy-and-hold performance on the test window."
    )
    num_trades: int = Field(description="Trade events in the test window.")


class SmaWalkForwardParamStability(BaseModel):
    """Summary of how stable the parameter selection is across windows."""

    num_windows: int = Field(description="Total number of completed walk-forward windows.")
    unique_parameter_sets: int = Field(
        description="Number of distinct (fast, slow) pairs selected across windows."
    )
    most_common_fast_window: int = Field(
        description="Most frequently selected fast window across all windows."
    )
    most_common_slow_window: int = Field(
        description="Most frequently selected slow window across all windows."
    )
    most_common_count: int = Field(
        description="How many windows chose the most common parameter set."
    )
    all_selected_params: List[SmaWalkForwardBestParams] = Field(
        description="The (fast, slow) pair chosen in each window, in order."
    )
    parameters_unstable: bool = Field(
        description=(
            "True when no single parameter set was chosen in more than 50% "
            "of windows — a sign that the strategy is sensitive to the "
            "optimisation window."
        )
    )


class SmaWalkForwardResponse(BaseModel):
    """Full response for the SMA walk-forward optimization endpoint."""

    # Identity
    ticker: str
    start_date: str
    end_date: str
    train_window_days: int
    test_window_days: int
    step_days: int
    selection_metric: str
    initial_capital: float
    transaction_cost_bps: float

    # Window-level results
    num_windows: int = Field(description="Number of completed walk-forward windows.")
    windows: List[SmaWalkForwardWindow] = Field(
        description="Per-window results, ordered by window_index."
    )

    # Stitched out-of-sample equity curve (strategy chained across test windows)
    stitched_equity_curve: List[EquityPoint] = Field(
        description=(
            "Stitched out-of-sample equity curve: strategy and benchmark "
            "equity compounded across all test windows. For overlapping test "
            "windows, each date is included once using the earliest completed "
            "window that covers it. If step_days is larger than test_window_days, "
            "calendar gaps between test windows are intentionally left out of "
            "the stitched curve."
        )
    )

    # Aggregate metrics on the full stitched OOS performance
    aggregate_metrics: PerformanceMetrics = Field(
        description="Performance metrics computed on the full stitched OOS equity curve."
    )
    aggregate_benchmark_metrics: PerformanceMetrics = Field(
        description="Buy-and-hold metrics on the full stitched OOS period."
    )

    # Parameter stability
    parameter_stability: SmaWalkForwardParamStability


# ===========================================================================
# Research — Strategy Comparison
# ===========================================================================


class StrategyComparisonRequest(BaseModel):
    """
    Parameters for the multi-strategy comparison endpoint.

    All five single-asset strategies (SMA Crossover, RSI Mean Reversion,
    Bollinger Band, Momentum, Volatility Breakout) are run with fixed default
    parameters on the same ticker and date range.  Pairs Trading is excluded
    because it requires two assets.
    """

    ticker: str = Field(
        default="SPY",
        description="Yahoo Finance ticker symbol.",
    )
    start_date: str = Field(
        default="2015-01-01",
        description="Backtest start date in YYYY-MM-DD format.",
    )
    end_date: str = Field(
        default="2023-12-31",
        description="Backtest end date in YYYY-MM-DD format.",
    )
    initial_capital: float = Field(
        default=100_000.0,
        gt=0,
        description="Starting capital in USD.",
    )
    transaction_cost_bps: float = Field(
        default=10.0,
        ge=0.0,
        lt=10_000.0,
        description="One-way transaction cost in basis points, applied to all strategies.",
    )
    position_mode: PositionMode = Field(
        default="long_only",
        description=(
            "Direction mode applied to strategies that support it (SMA Crossover, "
            "Momentum, Volatility Breakout).  RSI and Bollinger remain long-only "
            "regardless.  Defaults to 'long_only'."
        ),
    )
    cost_model: Optional[CostModel] = _COST_MODEL_FIELD
    position_sizing: Optional[PositionSizing] = _POSITION_SIZING_FIELD
    risk_management: Optional[RiskManagement] = _RISK_MANAGEMENT_FIELD
    annualization_mode: Optional[AnnualizationMode] = _ANNUALIZATION_FIELD
    benchmark: Optional[BenchmarkConfig] = _BENCHMARK_FIELD

    @model_validator(mode="after")
    def check_dates(self) -> "StrategyComparisonRequest":
        import re
        for name, val in [("start_date", self.start_date), ("end_date", self.end_date)]:
            if not re.match(_DATE_RE_PATTERN, val):
                raise ValueError(f"{name} must be in YYYY-MM-DD format.")
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be strictly before end_date.")
        return self


class StrategyResultItem(BaseModel):
    """Results for one strategy within a multi-strategy comparison."""

    strategy: str = Field(
        description=(
            "Strategy identifier: 'sma_crossover', 'rsi_mean_reversion', "
            "'bollinger_band', 'momentum', or 'volatility_breakout'."
        )
    )
    display_name: str = Field(description="Human-readable strategy name.")
    params: dict = Field(description="Default parameter values used for this strategy run.")
    position_mode: str = Field(
        default="long_only",
        description=(
            "Direction mode actually applied to this strategy.  Equals the "
            "comparison mode for strategies that support it; 'long_only' for "
            "strategies (RSI, Bollinger) that do not."
        ),
    )
    metrics: PerformanceMetrics = Field(description="Performance metrics over the full period.")
    equity_curve: List[EquityPoint] = Field(description="Daily portfolio value.")
    num_trades: int = Field(description="Number of trade events.")
    average_exposure: Optional[float] = Field(
        default=None,
        description="Mean absolute exposure (|position|) after position sizing.",
    )
    risk_exit_count: Optional[int] = Field(
        default=None,
        description="Number of risk-management exits (present only when risk rules are active).",
    )
    effective_cost_bps: Optional[float] = Field(
        default=None,
        description="Effective per-side cost in bps applied to this strategy.",
    )
    unsupported_features: List[str] = Field(
        default_factory=list,
        description="Selected simulation features this strategy could not apply (e.g. 'position_mode').",
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Human-readable notes for this strategy row (e.g. 'ran long-only').",
    )
    active_metrics: Optional[ActiveMetrics] = Field(
        default=None,
        description=(
            "Strategy-vs-benchmark metrics against the comparison's configured "
            "benchmark (absent when benchmark mode is 'none')."
        ),
    )


class StrategyComparisonRanking(BaseModel):
    """Identifies the best-performing strategy for each ranking criterion."""

    best_by_sharpe: str = Field(
        description="Display name of the strategy with the highest Sharpe ratio."
    )
    best_by_cagr: str = Field(
        description="Display name of the strategy with the highest CAGR."
    )
    best_by_calmar: str = Field(
        description="Display name of the strategy with the highest Calmar ratio."
    )
    lowest_drawdown: str = Field(
        description=(
            "Display name of the strategy with the smallest absolute max drawdown "
            "(i.e. the least negative max_drawdown value)."
        )
    )


class StrategyComparisonResponse(BaseModel):
    """Full response for the strategy comparison endpoint."""

    ticker: str
    start_date: str
    end_date: str
    initial_capital: float
    transaction_cost_bps: float = Field(
        description="Effective per-side cost in bps applied to all strategies.",
    )
    position_mode: str = Field(
        default="long_only",
        description="Direction mode requested for the comparison.",
    )
    cost_model: Optional[CostModelResolved] = Field(
        default=None,
        description=(
            "Resolved cost model echo. When cost_model is omitted, this is the "
            "backward-compatible simple_bps model derived from transaction_cost_bps."
        ),
    )
    effective_cost_bps: Optional[float] = Field(
        default=None,
        description="Effective per-side cost in bps applied to all strategies.",
    )
    position_sizing: Optional[PositionSizingResolved] = Field(
        default=None,
        description=(
            "Resolved position-sizing echo. When omitted, this is full_allocation."
        ),
    )
    risk_management: Optional[RiskManagementResolved] = Field(
        default=None,
        description="Resolved risk-management echo (present only when risk rules are active).",
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Comparison-level notes (e.g. strategies that could not apply a mode).",
    )
    annualization_mode: Optional[AnnualizationMode] = Field(
        default=None, description="Requested annualization mode (defaults to trading_days_252)."
    )
    annualization_mode_used: Optional[str] = Field(
        default=None, description="Concrete annualization convention applied to all strategies."
    )
    periods_per_year: Optional[int] = Field(
        default=None, description="Return periods per year used (252 or 365)."
    )
    annualization_warning: Optional[str] = Field(
        default=None, description="Set when 'auto' could not confirm the asset class."
    )
    data_provider: Optional[str] = Field(
        default=None, description="Market-data provider used (one shared fetch for all strategies)."
    )
    data_quality: Optional[DataQuality] = Field(
        default=None, description="Diagnostics for the shared price series (computed once)."
    )
    benchmark_analytics: Optional[BenchmarkAnalytics] = Field(
        default=None,
        description=(
            "Shared benchmark block for the comparison (absent when benchmark "
            "mode is 'none'). The legacy `benchmark` curve / `benchmark_metrics` "
            "always remain the same-asset buy-and-hold."
        ),
    )
    reproducibility: Optional[Reproducibility] = Field(
        default=None,
        description="Deterministic config hash of the normalized comparison inputs.",
    )

    strategies: List[StrategyResultItem] = Field(
        description=(
            "Results for each of the five compared strategies, in a fixed order: "
            "SMA Crossover, RSI Mean Reversion, Bollinger Band, Momentum, "
            "Volatility Breakout."
        )
    )

    benchmark: List[EquityPoint] = Field(
        description=(
            "Buy-and-hold benchmark equity curve.  Both the 'strategy' and "
            "'benchmark' fields of each point carry the benchmark value."
        )
    )
    benchmark_metrics: PerformanceMetrics = Field(
        description="Performance metrics for the buy-and-hold benchmark."
    )

    ranking: StrategyComparisonRanking


# ===========================================================================
# Saved Backtests
# ===========================================================================


class SavedBacktestCreate(BaseModel):
    """Request body for POST /saved-backtests."""

    name: str = Field(
        min_length=1,
        description="Display name for the saved backtest (non-empty).",
    )
    ticker: str = Field(
        min_length=1,
        description="Ticker symbol, e.g. SPY (non-empty).",
    )
    strategy: str = Field(
        min_length=1,
        description="Strategy identifier, e.g. sma_crossover (non-empty).",
    )
    start_date: str = Field(description="Backtest start date (YYYY-MM-DD).")
    end_date: str = Field(description="Backtest end date (YYYY-MM-DD).")
    initial_capital: float = Field(gt=0, description="Starting capital in USD.")
    transaction_cost_bps: float = Field(
        ge=0.0, description="One-way transaction cost in basis points."
    )
    params: dict = Field(
        default_factory=dict,
        description="Strategy parameters used for this run.",
    )
    metrics: dict = Field(
        default_factory=dict,
        description="Performance metrics dict (keys match PerformanceMetrics).",
    )
    equity_curve: list = Field(
        default_factory=list,
        description="List of EquityPoint dicts {date, strategy, benchmark}.",
    )
    trades: list = Field(
        default_factory=list,
        description="List of TradeRecord dicts.",
    )
    notes: str = Field(default="", description="Optional free-text notes.")

    @field_validator("name", "ticker", "strategy")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @model_validator(mode="after")
    def check_dates(self) -> "SavedBacktestCreate":
        try:
            start = date.fromisoformat(self.start_date)
            end = date.fromisoformat(self.end_date)
        except ValueError as exc:
            raise ValueError(
                "start_date and end_date must be valid YYYY-MM-DD dates."
            ) from exc

        if start >= end:
            raise ValueError("start_date must be before end_date.")
        return self


class SavedBacktestSummary(BaseModel):
    """
    Lightweight summary row returned by GET /saved-backtests.

    Omits the large JSON blobs (equity_curve, trades, params, metrics) so
    list responses are cheap to serialise and transfer.  The four headline
    metrics are extracted from the stored metrics JSON.
    """

    id: int
    created_at: str = Field(description="ISO-8601 UTC timestamp of creation.")
    name: str
    ticker: str
    strategy: str
    start_date: str
    end_date: str
    total_return: Optional[float] = Field(
        default=None, description="Total return as a decimal (from stored metrics)."
    )
    cagr: Optional[float] = Field(
        default=None, description="CAGR as a decimal (from stored metrics)."
    )
    sharpe_ratio: Optional[float] = Field(
        default=None, description="Annualised Sharpe ratio (from stored metrics)."
    )
    max_drawdown: Optional[float] = Field(
        default=None, description="Max drawdown as a decimal ≤ 0 (from stored metrics)."
    )
    notes: str


class SavedBacktestFull(SavedBacktestSummary):
    """
    Full record returned by GET /saved-backtests/{id} and
    POST /saved-backtests.

    Extends SavedBacktestSummary with the four large JSON fields and the
    common parameters.
    """

    initial_capital: float
    transaction_cost_bps: float
    params: dict = Field(description="Strategy parameters.")
    metrics: dict = Field(description="Full performance metrics dict.")
    equity_curve: list = Field(description="Daily equity curve data points.")
    trades: list = Field(description="Trade log.")


class DeleteResponse(BaseModel):
    """Response body for DELETE /saved-backtests/{id}."""

    deleted: bool = Field(description="True if the record existed and was deleted.")
    id: int = Field(description="ID of the deleted record.")


# ===========================================================================
# Saved Reports (Report Gallery)
# ===========================================================================

# The analysis that produced a report.  Constrained so list/filter UIs and the
# DB stay consistent; "manual" covers ad-hoc / hand-written reports.
SavedReportSourceType = Literal[
    "backtest",
    "csv_backtest",
    "custom_strategy",
    "portfolio_backtest",
    "portfolio_optimization",
    "risk_dashboard",
    "stress_test",
    "factor_analysis",
    "manual",
]


class SavedReportCreate(BaseModel):
    """Request body for POST /saved-reports."""

    title: str = Field(min_length=1, description="Report title (non-empty).")
    report_type: str = Field(
        min_length=1,
        description="Report content format, e.g. 'markdown' (non-empty).",
    )
    source_type: SavedReportSourceType = Field(
        description="The analysis type that produced the report."
    )
    source_id: Optional[int] = Field(
        default=None,
        description="Optional id of a related record (e.g. a saved backtest).",
    )
    tickers: List[str] = Field(
        default_factory=list,
        description="Tickers referenced by the report, if any.",
    )
    strategy: Optional[str] = Field(
        default=None, description="Strategy / objective identifier, if applicable."
    )
    date_range_start: Optional[str] = Field(
        default=None, description="Analysis start date (YYYY-MM-DD), if applicable."
    )
    date_range_end: Optional[str] = Field(
        default=None, description="Analysis end date (YYYY-MM-DD), if applicable."
    )
    markdown_content: str = Field(
        min_length=1, description="Full Markdown report text (non-empty)."
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Structured report metadata (free-form JSON object).",
    )
    notes: str = Field(default="", description="Optional free-text notes.")

    @field_validator("title", "report_type")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("field must not be blank.")
        return stripped

    @field_validator("markdown_content")
    @classmethod
    def _check_markdown_non_empty(cls, value: str) -> str:
        # Preserve the original content (whitespace/formatting), but reject
        # content that is blank once stripped.
        if not value.strip():
            raise ValueError("markdown_content must not be blank.")
        return value

    @field_validator("date_range_start", "date_range_end", mode="before")
    @classmethod
    def _blank_date_to_none(cls, value: object) -> object:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @model_validator(mode="after")
    def _check_dates(self) -> "SavedReportCreate":
        parsed: dict = {}
        for field_name in ("date_range_start", "date_range_end"):
            raw = getattr(self, field_name)
            if raw is None or raw == "":
                continue
            try:
                parsed[field_name] = date.fromisoformat(raw)
            except ValueError as exc:
                raise ValueError(
                    f"{field_name} must be a valid YYYY-MM-DD date."
                ) from exc

        if "date_range_start" in parsed and "date_range_end" in parsed:
            if parsed["date_range_start"] >= parsed["date_range_end"]:
                raise ValueError("date_range_start must be before date_range_end.")
        return self


class SavedReportUpdate(BaseModel):
    """Request body for PUT /saved-reports/{id} — mutable metadata only."""

    title: str = Field(min_length=1, description="Report title (non-empty).")
    notes: str = Field(default="", description="Optional free-text notes.")
    metadata: dict = Field(
        default_factory=dict, description="Structured report metadata."
    )

    @field_validator("title")
    @classmethod
    def _strip_title(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("title must not be blank.")
        return stripped


class SavedReportSummary(BaseModel):
    """Lightweight list-view row returned by GET /saved-reports (no Markdown)."""

    id: int
    created_at: str = Field(description="ISO-8601 UTC timestamp of creation.")
    updated_at: str = Field(description="ISO-8601 UTC timestamp of last update.")
    title: str
    report_type: str
    source_type: SavedReportSourceType
    source_id: Optional[int] = None
    tickers: List[str] = Field(default_factory=list)
    strategy: Optional[str] = None
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    notes: str


class SavedReportFull(SavedReportSummary):
    """Full record returned by GET /saved-reports/{id} and POST /saved-reports."""

    markdown_content: str = Field(description="Full Markdown report text.")
    metadata: dict = Field(
        default_factory=dict, description="Structured report metadata."
    )


# ===========================================================================
# Custom Strategy Builder (v1) — no-code rule builder
# ===========================================================================

# Indicator operand names.  bb_upper / bb_lower additionally require num_std.
CustomIndicatorName = Literal[
    "sma", "rsi", "bb_upper", "bb_middle", "bb_lower", "momentum"
]
CustomOperator = Literal[">", ">=", "<", "<="]


class CustomCloseOperand(BaseModel):
    """The adjusted close price at each bar."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["close"] = "close"


class CustomConstantOperand(BaseModel):
    """A fixed numeric constant compared against an indicator/price."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["constant"] = "constant"
    value: float = Field(allow_inf_nan=False, description="The constant value.")


class CustomIndicatorParams(BaseModel):
    """Parameters for an indicator operand."""

    model_config = ConfigDict(extra="forbid")

    window: int = Field(
        ge=1, le=1000, description="Look-back window in trading days."
    )
    num_std: Optional[float] = Field(
        default=None,
        gt=0.0,
        le=10.0,
        description="Standard-deviation multiplier (Bollinger bands only).",
    )


class CustomIndicatorOperand(BaseModel):
    """A technical-indicator operand evaluated from the close price series."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["indicator"] = "indicator"
    name: CustomIndicatorName
    params: CustomIndicatorParams

    @model_validator(mode="after")
    def _check_indicator_params(self) -> "CustomIndicatorOperand":
        if self.name in ("rsi", "bb_upper", "bb_middle", "bb_lower"):
            if self.params.window < 2:
                raise ValueError(
                    f"Indicator '{self.name}' requires params.window >= 2."
                )
        if self.name in ("bb_upper", "bb_lower") and self.params.num_std is None:
            raise ValueError(
                f"Indicator '{self.name}' requires params.num_std."
            )
        return self


# Discriminated union on the "type" field.
CustomOperand = Annotated[
    Union[CustomCloseOperand, CustomConstantOperand, CustomIndicatorOperand],
    Field(discriminator="type"),
]


class CustomRule(BaseModel):
    """A single comparison: ``left <operator> right``."""

    model_config = ConfigDict(extra="forbid")

    left: CustomOperand
    operator: CustomOperator
    right: CustomOperand


class CustomStrategyRequest(BaseModel):
    """
    Request body for the Custom Strategy Builder backtest.

    Long-only, single-asset.  The position enters when the entry rules are
    satisfied (combined by ``entry_logic``) and exits when the exit rules are
    satisfied (combined by ``exit_logic``).  All comparisons use values known
    at bar close; the resulting position is shifted one bar forward to prevent
    lookahead bias.
    """

    model_config = ConfigDict(extra="forbid")

    ticker: str = Field(default="SPY", description="Yahoo Finance ticker symbol.")
    start_date: str = Field(
        default="2015-01-01", description="Backtest start date (YYYY-MM-DD)."
    )
    end_date: str = Field(
        default="2023-12-31", description="Backtest end date (YYYY-MM-DD)."
    )
    transaction_cost_bps: float = Field(
        default=10.0, ge=0.0, lt=10_000.0,
        description="One-way transaction cost in basis points.",
    )
    initial_capital: float = Field(
        default=100_000.0, gt=0, description="Starting capital in USD."
    )
    entry_rules: List[CustomRule] = Field(
        min_length=1,
        max_length=10,
        description="Rules that trigger entry into a long position.",
    )
    entry_logic: Literal["all", "any"] = Field(
        default="all",
        description="'all' = every entry rule must hold (AND); 'any' = at least one (OR).",
    )
    exit_rules: List[CustomRule] = Field(
        default_factory=list,
        max_length=10,
        description="Rules that trigger exit to cash. Empty = hold once entered.",
    )
    exit_logic: Literal["all", "any"] = Field(
        default="any",
        description="'all' = every exit rule must hold (AND); 'any' = at least one (OR).",
    )


# ===========================================================================
# Saved Custom Strategy Templates
# ===========================================================================
#
# A *template* is a reusable strategy definition (rules + logic + metadata).
# It deliberately stores NO backtest results — see saved_backtests.py for those.
# Rules reuse the exact same validated CustomRule schema as the live builder,
# so only whitelisted indicators/operators are ever accepted (no eval, no
# arbitrary code).  Logic is expressed as "AND"/"OR" at the template layer.

CustomTemplateLogic = Literal["AND", "OR"]


class CustomStrategyTemplateBase(BaseModel):
    """Shared fields for creating / updating a custom strategy template."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        min_length=1,
        max_length=120,
        description="Template display name (non-empty).",
    )
    description: str = Field(
        default="", max_length=1000, description="Free-text description."
    )
    entry_logic: CustomTemplateLogic = Field(
        default="AND", description="How entry rules combine: 'AND' or 'OR'."
    )
    exit_logic: CustomTemplateLogic = Field(
        default="OR", description="How exit rules combine: 'AND' or 'OR'."
    )
    entry_rules: List[CustomRule] = Field(
        default_factory=list,
        max_length=10,
        description="Entry rules (0–10). Reuses the Custom Strategy Builder schema.",
    )
    exit_rules: List[CustomRule] = Field(
        default_factory=list,
        max_length=10,
        description="Exit rules (0–10). Reuses the Custom Strategy Builder schema.",
    )
    tags: List[str] = Field(
        default_factory=list,
        max_length=20,
        description="Optional free-text tags for organising templates.",
    )

    @field_validator("name")
    @classmethod
    def strip_template_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("name must not be blank.")
        return stripped

    @field_validator("description")
    @classmethod
    def strip_template_description(cls, value: str) -> str:
        return value.strip()

    @field_validator("tags")
    @classmethod
    def strip_template_tags(cls, value: List[str]) -> List[str]:
        cleaned: List[str] = []
        for tag in value:
            stripped = tag.strip()
            if not stripped:
                continue
            if len(stripped) > 40:
                raise ValueError("each tag must be 40 characters or fewer.")
            cleaned.append(stripped)
        return cleaned


class CustomStrategyTemplateCreate(CustomStrategyTemplateBase):
    """Request body for POST /custom-strategies."""


class CustomStrategyTemplateUpdate(CustomStrategyTemplateBase):
    """Request body for PUT /custom-strategies/{id} (full replace)."""


class CustomStrategyTemplateSummary(BaseModel):
    """Lightweight list row — omits the full rule arrays."""

    id: int
    created_at: str
    updated_at: str
    name: str
    description: str
    entry_logic: CustomTemplateLogic
    exit_logic: CustomTemplateLogic
    num_entry_rules: int = Field(description="Number of entry rules.")
    num_exit_rules: int = Field(description="Number of exit rules.")
    tags: List[str]


class CustomStrategyTemplateFull(BaseModel):
    """Full template record including the rule definitions."""

    id: int
    created_at: str
    updated_at: str
    name: str
    description: str
    entry_logic: CustomTemplateLogic
    exit_logic: CustomTemplateLogic
    entry_rules: List[CustomRule]
    exit_rules: List[CustomRule]
    tags: List[str]


# ---------------------------------------------------------------------------
# Import / Export — portable strategy definitions
# ---------------------------------------------------------------------------

# Marker fields make exported files self-describing and let import reject
# unrelated JSON.  Local-only fields (id, created_at, updated_at) are never
# exported.
CUSTOM_TEMPLATE_EXPORT_TYPE = "quantlab_custom_strategy_template"
CUSTOM_TEMPLATE_SCHEMA_VERSION = "1.0"


class CustomStrategyTemplateExport(BaseModel):
    """
    Portable export shape for a custom strategy template.

    Deliberately omits id / created_at / updated_at and any local database
    detail — only the reusable definition plus self-describing markers.
    """

    schema_version: Literal["1.0"] = Field(default=CUSTOM_TEMPLATE_SCHEMA_VERSION)
    type: Literal["quantlab_custom_strategy_template"] = Field(
        default=CUSTOM_TEMPLATE_EXPORT_TYPE
    )
    name: str
    description: str
    entry_logic: CustomTemplateLogic
    exit_logic: CustomTemplateLogic
    entry_rules: List[CustomRule]
    exit_rules: List[CustomRule]
    tags: List[str]


class CustomStrategyTemplateImport(CustomStrategyTemplateBase):
    """
    Request body for POST /custom-strategies/import.

    Validates the portable envelope (schema_version present, correct type) and
    reuses the exact same whitelisted CustomRule schema as the live builder, so
    no arbitrary code / non-whitelisted indicator or operator can ever be
    imported.  Unknown envelope keys are ignored for forward compatibility;
    rule objects remain strictly validated (extra fields forbidden).
    """

    model_config = ConfigDict(extra="ignore")

    schema_version: Literal["1.0"] = Field(
        description="Export schema version. Currently only '1.0' is supported."
    )
    type: Literal["quantlab_custom_strategy_template"] = Field(
        description="Must be 'quantlab_custom_strategy_template'."
    )


# ===========================================================================
# Strategy Template Gallery (built-in, read-only)
# ===========================================================================
#
# Gallery templates are curated, built-in custom strategy definitions.  They
# are static data — NOT stored in SQLite — and reuse the same validated
# CustomRule schema as the live builder, so only whitelisted indicators /
# operators are ever expressible (no eval, no executable formula strings).

GalleryDifficulty = Literal["beginner", "intermediate", "advanced"]
GalleryCategory = Literal["trend", "mean_reversion", "momentum"]


class GalleryTemplate(BaseModel):
    """
    A built-in, read-only strategy template.

    Shares every field with a user-created template (name, logic, rules, tags)
    plus a stable string ``id`` and presentation metadata (difficulty,
    category).  Built-in templates always have at least one entry and one exit
    rule.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Stable slug identifier, e.g. 'sma-trend-filter'.")
    name: str = Field(min_length=1)
    description: str
    entry_logic: CustomTemplateLogic
    exit_logic: CustomTemplateLogic
    entry_rules: List[CustomRule] = Field(min_length=1, max_length=10)
    exit_rules: List[CustomRule] = Field(min_length=1, max_length=10)
    tags: List[str]
    difficulty: GalleryDifficulty
    category: GalleryCategory


# ===========================================================================
# Multi-Asset Portfolio Backtesting (v1)
# ===========================================================================
#
# Equal-weight, long-only, fully-invested portfolio with optional periodic
# rebalancing.  Not portfolio optimisation — every asset targets weight 1/N.

PortfolioRebalanceFrequency = Literal["none", "monthly", "quarterly", "yearly"]


class PortfolioBacktestRequest(BaseModel):
    """Request body for POST /portfolio/backtest."""

    model_config = ConfigDict(extra="forbid")

    tickers: List[str] = Field(
        min_length=1,
        max_length=20,
        description="1–20 Yahoo Finance tickers; held at equal weight.",
    )
    start_date: str = Field(default="2015-01-01", description="Start date (YYYY-MM-DD).")
    end_date: str = Field(default="2023-12-31", description="End date (YYYY-MM-DD).")
    initial_capital: float = Field(
        default=100_000.0, gt=0, description="Starting capital in USD."
    )
    rebalance_frequency: PortfolioRebalanceFrequency = Field(
        default="none",
        description="Rebalance cadence: none / monthly / quarterly / yearly.",
    )
    transaction_cost_bps: float = Field(
        default=10.0,
        ge=0.0,
        lt=10_000.0,
        description="Turnover-based transaction cost in basis points.",
    )

    @field_validator("tickers")
    @classmethod
    def _clean_tickers(cls, value: List[str]) -> List[str]:
        cleaned: List[str] = []
        seen: set[str] = set()
        for raw in value:
            sym = raw.strip().upper()
            if not sym:
                raise ValueError("ticker symbols must not be empty.")
            if sym in seen:
                raise ValueError(f"duplicate ticker after uppercasing: {sym}.")
            seen.add(sym)
            cleaned.append(sym)
        return cleaned

    @model_validator(mode="after")
    def _check_dates(self) -> "PortfolioBacktestRequest":
        import re

        for name, val in [("start_date", self.start_date), ("end_date", self.end_date)]:
            if not re.match(_DATE_RE_PATTERN, val):
                raise ValueError(f"{name} must be in YYYY-MM-DD format.")
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be strictly before end_date.")
        return self


class PortfolioEquityPoint(BaseModel):
    """One daily portfolio + benchmark value."""

    date: str
    portfolio: float
    benchmark: float


class PortfolioDrawdownPoint(BaseModel):
    """Daily peak-to-trough drawdown (fraction ≤ 0) for portfolio + benchmark."""

    date: str
    portfolio: float
    benchmark: float


class PortfolioWeightPoint(BaseModel):
    """Per-asset weights on one date (sum ≈ 1.0)."""

    date: str
    weights: Dict[str, float]


class PortfolioRebalanceEvent(BaseModel):
    """A rebalance back to equal weight, with its turnover and dollar cost."""

    date: str
    turnover: float = Field(description="Sum of absolute weight changes (0–2).")
    cost: float = Field(description="Transaction cost charged in USD.")


class PortfolioBacktestResponse(BaseModel):
    """Full response for POST /portfolio/backtest."""

    tickers: List[str]
    start_date: str
    end_date: str
    strategy: str = "equal_weight_portfolio"
    rebalance_frequency: PortfolioRebalanceFrequency
    initial_capital: float
    transaction_cost_bps: float
    benchmark_ticker: str = Field(
        description="Which series the benchmark uses (SPY when available, else a fallback)."
    )
    metrics: PerformanceMetrics
    benchmark_metrics: PerformanceMetrics
    equity_curve: List[PortfolioEquityPoint]
    drawdown: List[PortfolioDrawdownPoint]
    weights: List[PortfolioWeightPoint]
    rebalance_events: List[PortfolioRebalanceEvent]


# ===========================================================================
# Portfolio Optimization (v1) — in-sample, long-only
# ===========================================================================
#
# Weights are optimised on the FULL requested history and then backtested on
# that SAME period.  This is in-sample optimisation and can overfit — it does
# not predict future performance.

PortfolioObjective = Literal["equal_weight", "min_volatility", "max_sharpe"]


class PortfolioOptimizeRequest(BaseModel):
    """Request body for POST /portfolio/optimize."""

    model_config = ConfigDict(extra="forbid")

    tickers: List[str] = Field(
        min_length=1, max_length=20, description="1–20 Yahoo Finance tickers."
    )
    start_date: str = Field(default="2015-01-01", description="Start date (YYYY-MM-DD).")
    end_date: str = Field(default="2023-12-31", description="End date (YYYY-MM-DD).")
    initial_capital: float = Field(default=100_000.0, gt=0)
    risk_free_rate: float = Field(
        default=0.02,
        ge=0.0,
        le=1.0,
        description="Annual risk-free rate (decimal) used in the Sharpe objective.",
    )
    transaction_cost_bps: float = Field(default=10.0, ge=0.0, lt=10_000.0)
    objective: PortfolioObjective = Field(
        default="max_sharpe",
        description="equal_weight / min_volatility / max_sharpe.",
    )

    @field_validator("tickers")
    @classmethod
    def _clean_tickers(cls, value: List[str]) -> List[str]:
        cleaned: List[str] = []
        seen: set[str] = set()
        for raw in value:
            sym = raw.strip().upper()
            if not sym:
                raise ValueError("ticker symbols must not be empty.")
            if sym in seen:
                raise ValueError(f"duplicate ticker after uppercasing: {sym}.")
            seen.add(sym)
            cleaned.append(sym)
        return cleaned

    @model_validator(mode="after")
    def _check_dates(self) -> "PortfolioOptimizeRequest":
        import re

        for name, val in [("start_date", self.start_date), ("end_date", self.end_date)]:
            if not re.match(_DATE_RE_PATTERN, val):
                raise ValueError(f"{name} must be in YYYY-MM-DD format.")
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be strictly before end_date.")
        return self


class PortfolioOptEquityPoint(BaseModel):
    """One daily value on an optimized/equal-weight equity curve."""

    date: str
    value: float


class PortfolioOptDrawdownPoint(BaseModel):
    """Daily drawdown (fraction ≤ 0) for optimized portfolio + equal weight."""

    date: str
    portfolio: float
    equal_weight: float


class PortfolioOptimizeResponse(BaseModel):
    """Full response for POST /portfolio/optimize."""

    tickers: List[str]
    objective: PortfolioObjective
    start_date: str
    end_date: str
    initial_capital: float
    risk_free_rate: float
    transaction_cost_bps: float

    weights: Dict[str, float] = Field(description="Optimized long-only weights (sum ≈ 1).")
    expected_returns: Dict[str, float] = Field(
        description="Annualised expected return per asset."
    )
    covariance_matrix: Dict[str, Dict[str, float]] = Field(
        description="Annualised covariance matrix (nested by ticker)."
    )

    portfolio_expected_return: float = Field(description="Annualised expected return of the optimized weights.")
    portfolio_volatility: float = Field(description="Annualised volatility of the optimized weights.")
    portfolio_sharpe: float = Field(description="Annualised Sharpe ratio of the optimized weights.")

    metrics: PerformanceMetrics = Field(description="Backtested optimized-portfolio metrics (in-sample).")
    equal_weight_metrics: PerformanceMetrics = Field(description="Backtested equal-weight metrics for comparison.")

    equity_curve: List[PortfolioOptEquityPoint] = Field(description="Optimized buy-and-hold equity curve.")
    equal_weight_equity_curve: List[PortfolioOptEquityPoint] = Field(
        description="Equal-weight buy-and-hold equity curve over the same dates."
    )
    drawdown: List[PortfolioOptDrawdownPoint]

    in_sample_warning: str = Field(
        default=(
            "Weights were optimized and backtested on the same historical "
            "period (in-sample). This can overfit and does not predict future "
            "performance. Portfolio Optimization v1 is a static buy-and-hold "
            "comparison; transaction_cost_bps is not deducted as a one-time "
            "allocation cost or ongoing turnover cost. Not investment advice."
        ),
        description="Explicit in-sample / overfitting caveat.",
    )


# ===========================================================================
# Walk-Forward Portfolio Optimization
# ===========================================================================
#
# Rolling train→test optimization.  Weights are estimated on each training
# window and applied (held fixed) to the following out-of-sample test window;
# the test windows are stitched into one OOS equity curve.  This reduces (but
# does not eliminate) the in-sample overfitting of the static optimizer.


class PortfolioWalkForwardRequest(BaseModel):
    """Request body for POST /portfolio/walk-forward-optimize."""

    model_config = ConfigDict(extra="forbid")

    tickers: List[str] = Field(min_length=1, max_length=20)
    start_date: str = Field(default="2010-01-01", description="Start date (YYYY-MM-DD).")
    end_date: str = Field(default="2023-12-31", description="End date (YYYY-MM-DD).")
    train_window_days: int = Field(
        default=756, ge=1, description="Trading days in each rolling training window."
    )
    test_window_days: int = Field(
        default=126, ge=1, description="Trading days in each out-of-sample test window."
    )
    step_days: int = Field(
        default=126, ge=1, description="Trading days to advance the window each step."
    )
    objective: PortfolioObjective = Field(default="max_sharpe")
    risk_free_rate: float = Field(default=0.02, ge=0.0, le=1.0)
    initial_capital: float = Field(default=100_000.0, gt=0)
    transaction_cost_bps: float = Field(default=10.0, ge=0.0, lt=10_000.0)

    @field_validator("tickers")
    @classmethod
    def _clean_tickers(cls, value: List[str]) -> List[str]:
        cleaned: List[str] = []
        seen: set[str] = set()
        for raw in value:
            sym = raw.strip().upper()
            if not sym:
                raise ValueError("ticker symbols must not be empty.")
            if sym in seen:
                raise ValueError(f"duplicate ticker after uppercasing: {sym}.")
            seen.add(sym)
            cleaned.append(sym)
        return cleaned

    @model_validator(mode="after")
    def _check_dates(self) -> "PortfolioWalkForwardRequest":
        import re

        for name, val in [("start_date", self.start_date), ("end_date", self.end_date)]:
            if not re.match(_DATE_RE_PATTERN, val):
                raise ValueError(f"{name} must be in YYYY-MM-DD format.")
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be strictly before end_date.")
        return self


class PortfolioWalkForwardWindow(BaseModel):
    """One train→test walk-forward window."""

    train_start_date: str
    train_end_date: str
    test_start_date: str
    test_end_date: str
    weights: Dict[str, float] = Field(description="Optimized weights for this window.")
    train_expected_return: float
    train_volatility: float
    train_sharpe: float
    test_metrics: PerformanceMetrics = Field(
        description=(
            "Out-of-sample metrics for this window's full test horizon, "
            "including the one-off boundary transaction cost."
        )
    )
    turnover: float = Field(description="Σ|new_w − prev_w| at the window boundary (prev=0 for window 1).")
    transaction_cost: float = Field(description="Turnover cost charged in USD at the boundary.")


class PortfolioWeightStability(BaseModel):
    """Summary of how stable the optimized weights are across windows."""

    average_turnover: float = Field(description="Mean window-to-window turnover (excludes the entry window).")
    max_turnover: float = Field(description="Max window-to-window turnover.")
    average_weight_by_asset: Dict[str, float]
    min_weight_by_asset: Dict[str, float]
    max_weight_by_asset: Dict[str, float]


class PortfolioWalkForwardResponse(BaseModel):
    """Full response for POST /portfolio/walk-forward-optimize."""

    tickers: List[str]
    objective: PortfolioObjective
    start_date: str
    end_date: str
    train_window_days: int
    test_window_days: int
    step_days: int
    risk_free_rate: float
    initial_capital: float
    transaction_cost_bps: float

    num_windows: int
    windows: List[PortfolioWalkForwardWindow]

    stitched_equity_curve: List[PortfolioOptEquityPoint]
    benchmark_equity_curve: List[PortfolioOptEquityPoint]
    drawdown: List[PortfolioDrawdownPoint]

    metrics: PerformanceMetrics = Field(description="Aggregate out-of-sample metrics (optimized).")
    benchmark_metrics: PerformanceMetrics = Field(description="Aggregate OOS metrics (equal weight).")

    weight_stability: PortfolioWeightStability

    oos_note: str = Field(
        default=(
            "Walk-forward results are out-of-sample (weights estimated only on "
            "past training windows), which reduces in-sample overfitting. They "
            "still rely on historical return/covariance assumptions and do not "
            "predict future performance. Not investment advice."
        ),
        description="Out-of-sample caveat.",
    )


# ===========================================================================
# Efficient Frontier Visualization
# ===========================================================================
#
# Risk–return space of many long-only portfolios estimated from historical
# returns.  In-sample / descriptive — not a forecast.


class EfficientFrontierRequest(BaseModel):
    """Request body for POST /portfolio/efficient-frontier."""

    model_config = ConfigDict(extra="forbid")

    tickers: List[str] = Field(min_length=1, max_length=20)
    start_date: str = Field(default="2015-01-01", description="Start date (YYYY-MM-DD).")
    end_date: str = Field(default="2023-12-31", description="End date (YYYY-MM-DD).")
    risk_free_rate: float = Field(default=0.02, ge=0.0, le=1.0)
    num_portfolios: int = Field(
        default=2000,
        ge=100,
        le=10_000,
        description="Number of random long-only portfolios to sample.",
    )

    @field_validator("tickers")
    @classmethod
    def _clean_tickers(cls, value: List[str]) -> List[str]:
        cleaned: List[str] = []
        seen: set[str] = set()
        for raw in value:
            sym = raw.strip().upper()
            if not sym:
                raise ValueError("ticker symbols must not be empty.")
            if sym in seen:
                raise ValueError(f"duplicate ticker after uppercasing: {sym}.")
            seen.add(sym)
            cleaned.append(sym)
        return cleaned

    @model_validator(mode="after")
    def _check_dates(self) -> "EfficientFrontierRequest":
        import re

        for name, val in [("start_date", self.start_date), ("end_date", self.end_date)]:
            if not re.match(_DATE_RE_PATTERN, val):
                raise ValueError(f"{name} must be in YYYY-MM-DD format.")
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be strictly before end_date.")
        return self


class FrontierPortfolioPoint(BaseModel):
    """A portfolio in risk–return space with its weights."""

    expected_return: float
    volatility: float
    sharpe: float
    weights: Dict[str, float]


class FrontierCurvePoint(BaseModel):
    """A point on the efficient-frontier curve (no weights, for plotting)."""

    expected_return: float
    volatility: float


class EfficientFrontierResponse(BaseModel):
    """Full response for POST /portfolio/efficient-frontier."""

    tickers: List[str]
    start_date: str
    end_date: str
    risk_free_rate: float
    num_portfolios: int

    expected_returns: Dict[str, float] = Field(description="Annualised expected return per asset.")
    covariance_matrix: Dict[str, Dict[str, float]] = Field(
        description="Annualised covariance matrix (nested by ticker)."
    )

    random_portfolios: List[FrontierPortfolioPoint]
    equal_weight: FrontierPortfolioPoint
    min_volatility: FrontierPortfolioPoint
    max_sharpe: FrontierPortfolioPoint
    frontier_points: List[FrontierCurvePoint]

    in_sample_note: str = Field(
        default=(
            "Expected returns and covariance are estimated from historical "
            "data over the selected window (in-sample). They may not persist; "
            "this is descriptive analysis, not a forecast or investment advice."
        ),
        description="Historical / in-sample caveat.",
    )


# ===========================================================================
# Portfolio Risk Dashboard
# ===========================================================================
#
# Asset- and portfolio-level risk diagnostics estimated from historical daily
# returns (252-day annualisation).  Descriptive only.


class RiskDashboardRequest(BaseModel):
    """Request body for POST /portfolio/risk-dashboard."""

    model_config = ConfigDict(extra="forbid")

    tickers: List[str] = Field(min_length=1, max_length=20)
    start_date: str = Field(default="2015-01-01", description="Start date (YYYY-MM-DD).")
    end_date: str = Field(default="2023-12-31", description="End date (YYYY-MM-DD).")

    @field_validator("tickers")
    @classmethod
    def _clean_tickers(cls, value: List[str]) -> List[str]:
        cleaned: List[str] = []
        seen: set[str] = set()
        for raw in value:
            sym = raw.strip().upper()
            if not sym:
                raise ValueError("ticker symbols must not be empty.")
            if sym in seen:
                raise ValueError(f"duplicate ticker after uppercasing: {sym}.")
            seen.add(sym)
            cleaned.append(sym)
        return cleaned

    @model_validator(mode="after")
    def _check_dates(self) -> "RiskDashboardRequest":
        import re

        for name, val in [("start_date", self.start_date), ("end_date", self.end_date)]:
            if not re.match(_DATE_RE_PATTERN, val):
                raise ValueError(f"{name} must be in YYYY-MM-DD format.")
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be strictly before end_date.")
        return self


class EqualWeightRiskSummary(BaseModel):
    """Equal-weight portfolio risk summary."""

    expected_return: float
    volatility: float
    diversification_ratio: float = Field(
        description="Weighted-average asset volatility ÷ portfolio volatility (≥ 1 means diversification benefit)."
    )
    weights: Dict[str, float]


class CorrelationDiagnostics(BaseModel):
    """Summary statistics over the off-diagonal correlation pairs."""

    average_pairwise_correlation: float
    max_pairwise_correlation: float
    min_pairwise_correlation: float
    most_correlated_pair: Optional[List[str]] = Field(
        default=None, description="[ticker_a, ticker_b] with the highest correlation."
    )
    least_correlated_pair: Optional[List[str]] = Field(
        default=None, description="[ticker_a, ticker_b] with the lowest correlation."
    )


class RiskDashboardResponse(BaseModel):
    """Full response for POST /portfolio/risk-dashboard."""

    tickers: List[str]
    start_date: str
    end_date: str

    asset_annual_returns: Dict[str, float]
    asset_annual_volatilities: Dict[str, float]
    correlation_matrix: Dict[str, Dict[str, float]]
    covariance_matrix: Dict[str, Dict[str, float]]
    equal_weight_portfolio: EqualWeightRiskSummary
    correlation_diagnostics: CorrelationDiagnostics
    risk_contribution: Dict[str, float] = Field(
        description="Equal-weight percent risk contribution per asset (≈ sums to 1)."
    )

    historical_note: str = Field(
        default=(
            "All statistics are estimated from historical daily returns over "
            "the selected window. Correlations, volatilities, and risk "
            "contributions may not persist out-of-sample. Not investment advice."
        ),
        description="Historical-estimate caveat.",
    )


# ===========================================================================
# Portfolio Stress Testing / Scenario Analysis
# ===========================================================================


class StressScenarioInput(BaseModel):
    """One historical stress window to evaluate."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, description="Scenario label (non-empty).")
    start_date: str = Field(description="Scenario start date (YYYY-MM-DD).")
    end_date: str = Field(description="Scenario end date (YYYY-MM-DD).")

    @model_validator(mode="after")
    def _check_dates(self) -> "StressScenarioInput":
        import re

        for n, v in [("start_date", self.start_date), ("end_date", self.end_date)]:
            if not re.match(_DATE_RE_PATTERN, v):
                raise ValueError(f"scenario {n} must be in YYYY-MM-DD format.")
        if self.start_date >= self.end_date:
            raise ValueError(
                f"scenario '{self.name}': start_date must be before end_date."
            )
        return self


class StressTestRequest(BaseModel):
    """Request body for POST /portfolio/stress-test."""

    model_config = ConfigDict(extra="forbid")

    tickers: List[str] = Field(min_length=1, max_length=20)
    weights: Optional[Dict[str, float]] = Field(
        default=None,
        description="Optional long-only weights summing to 1. Equal weight if omitted.",
    )
    start_date: str = Field(default="2007-01-01", description="Full data start (YYYY-MM-DD).")
    end_date: str = Field(default="2023-12-31", description="Full data end (YYYY-MM-DD).")
    initial_capital: float = Field(default=100_000.0, gt=0)
    transaction_cost_bps: float = Field(default=0.0, ge=0.0, lt=10_000.0)
    scenarios: List[StressScenarioInput] = Field(
        min_length=1, max_length=20, description="Stress windows to evaluate."
    )
    benchmark_ticker: str = Field(
        default="SPY", min_length=1, description="Benchmark ticker (non-empty)."
    )

    @field_validator("tickers")
    @classmethod
    def _clean_tickers(cls, value: List[str]) -> List[str]:
        cleaned: List[str] = []
        seen: set[str] = set()
        for raw in value:
            sym = raw.strip().upper()
            if not sym:
                raise ValueError("ticker symbols must not be empty.")
            if sym in seen:
                raise ValueError(f"duplicate ticker after uppercasing: {sym}.")
            seen.add(sym)
            cleaned.append(sym)
        return cleaned

    @field_validator("benchmark_ticker")
    @classmethod
    def _clean_benchmark(cls, value: str) -> str:
        sym = value.strip().upper()
        if not sym:
            raise ValueError("benchmark_ticker must not be empty.")
        return sym

    @model_validator(mode="after")
    def _check(self) -> "StressTestRequest":
        import re

        for n, v in [("start_date", self.start_date), ("end_date", self.end_date)]:
            if not re.match(_DATE_RE_PATTERN, v):
                raise ValueError(f"{n} must be in YYYY-MM-DD format.")
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be strictly before end_date.")

        if self.weights is not None:
            cleaned: Dict[str, float] = {}
            for raw, wt in self.weights.items():
                sym = raw.strip().upper()
                if not sym:
                    raise ValueError("weight ticker symbols must not be empty.")
                if sym in cleaned:
                    raise ValueError(f"duplicate weight ticker after uppercasing: {sym}.")
                cleaned[sym] = float(wt)
            if set(cleaned) != set(self.tickers):
                raise ValueError("weights must include exactly the requested tickers.")
            if any(not math.isfinite(wt) for wt in cleaned.values()):
                raise ValueError("weights must be finite.")
            if any(wt < 0 for wt in cleaned.values()):
                raise ValueError("weights must be non-negative (long-only).")
            if abs(sum(cleaned.values()) - 1.0) > 1e-6:
                raise ValueError("weights must sum to 1.")
            self.weights = cleaned
        return self


class StressScenarioResult(BaseModel):
    """Portfolio + benchmark performance over one stress window."""

    name: str
    start_date: str
    end_date: str
    total_return: float
    max_drawdown: float
    annualized_volatility: float
    worst_day_return: float
    best_day_return: float
    benchmark_total_return: float
    benchmark_max_drawdown: float
    benchmark_worst_day_return: float
    benchmark_best_day_return: float
    excess_return: float = Field(description="Portfolio total return − benchmark total return.")
    correlation_matrix: Dict[str, Dict[str, float]]
    portfolio_equity_curve: List[PortfolioOptEquityPoint]
    benchmark_equity_curve: List[PortfolioOptEquityPoint]


class StressTestResponse(BaseModel):
    """Full response for POST /portfolio/stress-test."""

    tickers: List[str]
    weights: Dict[str, float]
    start_date: str
    end_date: str
    benchmark_ticker: str
    full_period_metrics: PerformanceMetrics
    benchmark_full_period_metrics: PerformanceMetrics
    full_equity_curve: List[PortfolioOptEquityPoint]
    benchmark_equity_curve: List[PortfolioOptEquityPoint]
    scenarios: List[StressScenarioResult]

    historical_note: str = Field(
        default=(
            "Scenario results are historical: they show how this static "
            "portfolio would have moved through past stress windows and do not "
            "guarantee or predict future behaviour. Not investment advice."
        ),
        description="Historical caveat.",
    )


# ===========================================================================
# Factor Exposure / Regression Analysis
# ===========================================================================


class FactorAnalysisRequest(BaseModel):
    """Request body for POST /portfolio/factor-analysis."""

    model_config = ConfigDict(extra="forbid")

    tickers: List[str] = Field(min_length=1, max_length=20)
    weights: Optional[Dict[str, float]] = Field(
        default=None,
        description="Optional long-only weights summing to 1. Equal weight if omitted.",
    )
    start_date: str = Field(default="2015-01-01", description="Start date (YYYY-MM-DD).")
    end_date: str = Field(default="2023-12-31", description="End date (YYYY-MM-DD).")
    initial_capital: float = Field(default=100_000.0, gt=0)
    factor_tickers: Dict[str, str] = Field(
        min_length=1,
        description="Map of factor name → ETF proxy ticker (1–10 factors).",
    )

    @field_validator("tickers")
    @classmethod
    def _clean_tickers(cls, value: List[str]) -> List[str]:
        cleaned: List[str] = []
        seen: set[str] = set()
        for raw in value:
            sym = raw.strip().upper()
            if not sym:
                raise ValueError("ticker symbols must not be empty.")
            if sym in seen:
                raise ValueError(f"duplicate ticker after uppercasing: {sym}.")
            seen.add(sym)
            cleaned.append(sym)
        return cleaned

    @field_validator("factor_tickers")
    @classmethod
    def _clean_factors(cls, value: Dict[str, str]) -> Dict[str, str]:
        if not value:
            raise ValueError("factor_tickers must not be empty.")
        if len(value) > 10:
            raise ValueError("at most 10 factors are allowed.")
        cleaned: Dict[str, str] = {}
        for name, tk in value.items():
            nm = name.strip()
            sym = tk.strip().upper()
            if not nm:
                raise ValueError("factor names must not be empty.")
            if not sym:
                raise ValueError(f"factor '{nm}' has an empty ticker.")
            if nm in cleaned:
                raise ValueError(f"duplicate factor name: {nm}.")
            cleaned[nm] = sym
        return cleaned

    @model_validator(mode="after")
    def _check(self) -> "FactorAnalysisRequest":
        import re

        for n, v in [("start_date", self.start_date), ("end_date", self.end_date)]:
            if not re.match(_DATE_RE_PATTERN, v):
                raise ValueError(f"{n} must be in YYYY-MM-DD format.")
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be strictly before end_date.")

        if self.weights is not None:
            cleaned: Dict[str, float] = {}
            for raw, wt in self.weights.items():
                sym = raw.strip().upper()
                if not sym:
                    raise ValueError("weight ticker symbols must not be empty.")
                if sym in cleaned:
                    raise ValueError(f"duplicate weight ticker after uppercasing: {sym}.")
                cleaned[sym] = float(wt)
            if set(cleaned) != set(self.tickers):
                raise ValueError("weights must include exactly the requested tickers.")
            if any(not math.isfinite(wt) for wt in cleaned.values()):
                raise ValueError("weights must be finite.")
            if any(wt < 0 for wt in cleaned.values()):
                raise ValueError("weights must be non-negative (long-only).")
            if abs(sum(cleaned.values()) - 1.0) > 1e-6:
                raise ValueError("weights must sum to 1.")
            self.weights = cleaned
        return self


class FactorDiagnostics(BaseModel):
    """Headline summary of the regression exposures."""

    strongest_positive_factor: Optional[str] = None
    strongest_negative_factor: Optional[str] = None
    absolute_largest_exposure: Optional[str] = None
    multicollinearity_warning: bool = Field(
        description="True when the factor design matrix is rank-deficient (collinear factors)."
    )


class FactorRegressionPoint(BaseModel):
    """One daily observation: actual vs fitted return and the residual."""

    date: str
    actual_return: float
    fitted_return: float
    residual: float


class FactorAnalysisResponse(BaseModel):
    """Full response for POST /portfolio/factor-analysis."""

    tickers: List[str]
    weights: Dict[str, float]
    start_date: str
    end_date: str
    factor_tickers: Dict[str, str]

    alpha_daily: float
    alpha_annualized: float
    betas: Dict[str, float]
    r_squared: float
    residual_volatility: float = Field(description="Annualised residual (idiosyncratic) volatility.")
    factor_correlation_matrix: Dict[str, Dict[str, float]]
    diagnostics: FactorDiagnostics
    regression_points: List[FactorRegressionPoint]
    actual_equity_curve: List[PortfolioOptEquityPoint]
    fitted_equity_curve: List[PortfolioOptEquityPoint]

    historical_note: str = Field(
        default=(
            "Factor exposures are estimated by historical OLS regression on the "
            "chosen ETF proxies. Betas depend on the proxies selected and the "
            "window, and highly correlated factors can make individual betas "
            "unstable. Historical — not a forecast or investment advice."
        ),
        description="Historical / collinearity caveat.",
    )
