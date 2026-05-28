"""
Pydantic request / response schemas for the QuantLab backtesting API.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


# ===========================================================================
# Requests
# ===========================================================================

class BacktestRequest(BaseModel):
    """Parameters for the SMA crossover backtest endpoint."""

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
        lt=10_000.0,
        description="One-way transaction cost in basis points (10 bps = 0.10%).",
    )
    initial_capital: float = Field(
        default=100_000.0,
        gt=0,
        description="Starting capital in USD.",
    )


class RsiBacktestRequest(BaseModel):
    """Parameters for the RSI mean-reversion backtest endpoint."""

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
        default=30.0,
        ge=1.0,
        lt=100.0,
        description="Enter long when RSI falls strictly below this level.",
    )
    exit_threshold: float = Field(
        default=50.0,
        gt=1.0,
        le=100.0,
        description="Exit long when RSI rises above this level.",
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
        default=2.0,
        gt=0.0,
        le=10.0,
        description="Width of the bands in standard deviations (typical: 2.0).",
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
        default=126,
        ge=1,
        le=1000,
        description=(
            "Trailing return look-back period in trading days "
            "(default: 126 ≈ 6 months)."
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
        default=2.0,
        gt=0.0,
        le=5.0,
        description=(
            "Enter a position when |z-score| exceeds this threshold "
            "(default: 2.0).  Must be > exit_z_score."
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
        default=1.0,
        gt=0.0,
        le=10.0,
        description=(
            "Entry threshold: prior rolling high plus this multiple of the "
            "prior rolling high-low range."
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


class EquityPoint(BaseModel):
    """One daily data point on the equity curve."""

    date: str
    strategy: float = Field(description="Strategy portfolio value in USD.")
    benchmark: float = Field(description="Buy-and-hold portfolio value in USD.")


# ===========================================================================
# Full response  (shared by all six strategy endpoints)
# ===========================================================================

class BacktestResponse(BaseModel):
    """
    Universal backtest response.

    Strategy identification
    -----------------------
    ``strategy`` identifies which strategy produced this result:
    ``"sma_crossover"``, ``"rsi_mean_reversion"``, ``"bollinger_band"``,
    ``"momentum"``, ``"volatility_breakout"``, or ``"pairs"``.

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
            "'bollinger_band', 'momentum', 'volatility_breakout', or 'pairs'."
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

    transaction_cost_bps: float
    initial_capital: float
    strategy_metrics: PerformanceMetrics
    benchmark_metrics: PerformanceMetrics
    equity_curve: List[EquityPoint]
    trades: List[TradeRecord]
    num_trades: int = Field(description="Total number of trade events.")


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
