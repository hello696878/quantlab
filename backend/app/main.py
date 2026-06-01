"""
QuantLab FastAPI application.

Endpoints
---------
GET  /health                            — liveness check
POST /backtest/sma-crossover            — run an SMA crossover backtest
POST /backtest/rsi-mean-reversion       — run an RSI mean-reversion backtest
POST /backtest/bollinger-band           — run a Bollinger Band mean-reversion backtest
POST /backtest/momentum                 — run a time-series momentum backtest
POST /backtest/volatility-breakout      — run a volatility breakout backtest
POST /backtest/pairs                    — run a pairs trading backtest
POST /portfolio/backtest                — equal-weight multi-asset portfolio backtest
POST /backtest/csv                      — run a single-asset backtest on an uploaded CSV
POST /backtest/custom                   — run a no-code custom rule-based strategy
POST /custom-strategies                 — save a reusable custom strategy template
GET  /custom-strategies                 — list saved custom strategy templates
GET  /custom-strategies/{id}            — get a full custom strategy template
PUT  /custom-strategies/{id}            — update a custom strategy template
DELETE /custom-strategies/{id}          — delete a custom strategy template
GET  /custom-strategies/{id}/export     — export a template as portable JSON
POST /custom-strategies/import          — import a template from portable JSON
GET  /custom-strategy-gallery           — list built-in gallery templates
GET  /custom-strategy-gallery/{template_id} — get one built-in gallery template
POST /research/sma-parameter-sweep     — sweep fast/slow SMA window combinations
POST /research/sma-train-test          — SMA train/test out-of-sample validation
POST /research/sma-walk-forward        — SMA walk-forward optimization
POST /research/strategy-comparison     — compare five single-asset strategies
"""

import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from app.backtest import run_backtest, run_pairs_backtest
from app.csv_data import parse_price_csv
from app.custom_strategy import custom_strategy_signals, required_window
from app.custom_strategy_templates import (
    create_template as tpl_create,
    delete_template as tpl_delete,
    get_template as tpl_get,
    list_templates as tpl_list,
    update_template as tpl_update,
)
from app.data import fetch_ohlcv, fetch_pairs_close
from app.db import init_db
from app.portfolio import (
    align_prices,
    drawdown_series,
    run_equal_weight_portfolio,
)
from app.strategy_gallery import get_gallery_template, list_gallery
from app.metrics import compute_metrics
from app.saved_backtests import (
    create_saved_backtest as db_create,
    delete_saved_backtest as db_delete,
    get_saved_backtest as db_get,
    list_saved_backtests as db_list,
)
from app.schemas import (
    BacktestRequest,
    BacktestResponse,
    BbBacktestRequest,
    CustomStrategyRequest,
    CustomStrategyTemplateCreate,
    CustomStrategyTemplateExport,
    CustomStrategyTemplateFull,
    CustomStrategyTemplateImport,
    CustomStrategyTemplateSummary,
    CustomStrategyTemplateUpdate,
    DeleteResponse,
    EquityPoint,
    GalleryTemplate,
    PortfolioBacktestRequest,
    PortfolioBacktestResponse,
    PortfolioDrawdownPoint,
    PortfolioEquityPoint,
    PortfolioRebalanceEvent,
    PortfolioWeightPoint,
    MomentumBacktestRequest,
    PairsBacktestRequest,
    PerformanceMetrics,
    RsiBacktestRequest,
    SavedBacktestCreate,
    SavedBacktestFull,
    SavedBacktestSummary,
    SmaSweepRequest,
    SmaSweepResponse,
    SmaSweepRow,
    SmaTrainTestRequest,
    SmaTrainTestResponse,
    SmaWalkForwardBestParams,
    SmaWalkForwardParamStability,
    SmaWalkForwardRequest,
    SmaWalkForwardResponse,
    SmaWalkForwardWindow,
    StrategyComparisonRanking,
    StrategyComparisonRequest,
    StrategyComparisonResponse,
    StrategyResultItem,
    TradeRecord,
    VbBacktestRequest,
)
from app.strategies import (
    bollinger_band_signals,
    momentum_signals,
    pairs_signals,
    rsi_mean_reversion_signals,
    sma_crossover_signals,
    volatility_breakout_signals,
)
from app.utils import validate_date_format

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise the SQLite database on startup."""
    init_db()
    yield


app = FastAPI(
    title="QuantLab API",
    description=(
        "Quantitative backtesting engine.\n\n"
        "Strategies: SMA Crossover, RSI Mean Reversion, "
        "Bollinger Band Mean Reversion, Time-Series Momentum, "
        "Volatility Breakout, Pairs Trading.\n"
        "All strategies use a one-day signal shift to prevent lookahead bias."
    ),
    version="0.8.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _validate_common(ticker: str, start_date: str, end_date: str) -> None:
    """Raise HTTPException for invalid common request fields."""
    if not validate_date_format(start_date):
        raise HTTPException(status_code=422, detail="start_date must be YYYY-MM-DD.")
    if not validate_date_format(end_date):
        raise HTTPException(status_code=422, detail="end_date must be YYYY-MM-DD.")
    if start_date >= end_date:
        raise HTTPException(status_code=422, detail="start_date must be before end_date.")
    if not ticker.strip():
        raise HTTPException(status_code=422, detail="ticker must not be empty.")


def _fetch(ticker: str, start_date: str, end_date: str):
    """Download OHLCV data, raising appropriate HTTP errors."""
    try:
        return fetch_ohlcv(ticker, start_date, end_date)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Data fetch failed: {exc}") from exc


def _build_response(
    *,
    request_ticker: str,
    start_date: str,
    end_date: str,
    transaction_cost_bps: float,
    initial_capital: float,
    close,
    position,
    strategy: str,
    # SMA-specific (0 when not applicable)
    fast_window: int = 0,
    slow_window: int = 0,
    # RSI-specific (None when not applicable)
    rsi_window=None,
    oversold_threshold=None,
    exit_threshold=None,
    # Bollinger Band-specific (None when not applicable)
    bb_window=None,
    bb_num_std=None,
    bb_exit_band=None,
    # Momentum-specific (None when not applicable)
    momentum_window=None,
    momentum_entry_threshold=None,
    momentum_exit_threshold=None,
    # Volatility Breakout-specific (None when not applicable)
    vb_lookback_window=None,
    vb_breakout_multiplier=None,
    vb_exit_window=None,
) -> BacktestResponse:
    """Run backtest + metrics and assemble the unified response."""
    strategy_equity, benchmark_equity, trades = run_backtest(
        close=close,
        position=position,
        transaction_cost_bps=transaction_cost_bps,
        initial_capital=initial_capital,
    )

    strategy_metrics_dict = compute_metrics(strategy_equity)
    benchmark_metrics_dict = compute_metrics(benchmark_equity)

    equity_curve = [
        EquityPoint(
            date=str(d.date()) if hasattr(d, "date") else str(d),
            strategy=round(float(s), 2),
            benchmark=round(float(b), 2),
        )
        for d, s, b in zip(strategy_equity.index, strategy_equity, benchmark_equity)
    ]

    return BacktestResponse(
        ticker=request_ticker.upper(),
        start_date=start_date,
        end_date=end_date,
        strategy=strategy,
        fast_window=fast_window,
        slow_window=slow_window,
        rsi_window=rsi_window,
        oversold_threshold=oversold_threshold,
        exit_threshold=exit_threshold,
        bb_window=bb_window,
        bb_num_std=bb_num_std,
        bb_exit_band=bb_exit_band,
        momentum_window=momentum_window,
        momentum_entry_threshold=momentum_entry_threshold,
        momentum_exit_threshold=momentum_exit_threshold,
        vb_lookback_window=vb_lookback_window,
        vb_breakout_multiplier=vb_breakout_multiplier,
        vb_exit_window=vb_exit_window,
        transaction_cost_bps=transaction_cost_bps,
        initial_capital=initial_capital,
        strategy_metrics=PerformanceMetrics(**strategy_metrics_dict),
        benchmark_metrics=PerformanceMetrics(**benchmark_metrics_dict),
        equity_curve=equity_curve,
        trades=[TradeRecord(**t) for t in trades],
        num_trades=len(trades),
    )


# ---------------------------------------------------------------------------
# Private research helpers  (reused by sweep, train-test, walk-forward)
# ---------------------------------------------------------------------------


def _sweep_rows(
    close,
    fast_windows: list,
    slow_windows: list,
    transaction_cost_bps: float,
    initial_capital: float,
) -> tuple:
    """
    Run an SMA parameter sweep on *close* and return (rows, valid_pairs).

    ``rows``        — list of :class:`SmaSweepRow` objects for every
                      (fast < slow) pair that had sufficient bars.
    ``valid_pairs`` — number of (fast < slow) pairs attempted (before the
                      bar-length check).  Used to distinguish "all-invalid
                      grid" from "data too short" in callers.
    """
    rows: list = []
    valid_pairs = 0
    for fast in sorted(set(fast_windows)):
        for slow in sorted(set(slow_windows)):
            if fast >= slow:
                continue
            valid_pairs += 1
            if len(close) < slow + 2:
                continue
            position = sma_crossover_signals(close, fast_window=fast, slow_window=slow)
            strategy_equity, _bench, trades = run_backtest(
                close=close,
                position=position,
                transaction_cost_bps=transaction_cost_bps,
                initial_capital=initial_capital,
            )
            m = compute_metrics(strategy_equity)
            rows.append(
                SmaSweepRow(
                    fast_window=fast,
                    slow_window=slow,
                    total_return=m["total_return"],
                    cagr=m["cagr"],
                    sharpe_ratio=m["sharpe_ratio"],
                    sortino_ratio=m["sortino_ratio"],
                    calmar_ratio=m["calmar_ratio"],
                    max_drawdown=m["max_drawdown"],
                    volatility=m["volatility"],
                    num_trades=len(trades),
                )
            )
    return rows, valid_pairs


def _best_row(rows: list, selection_metric: str) -> "SmaSweepRow":
    """
    Return the best :class:`SmaSweepRow` by *selection_metric*.

    Ties broken deterministically: prefer smaller fast_window, then
    smaller slow_window.
    """
    import math

    def _score(row) -> float:
        if selection_metric == "sharpe_ratio":
            v = row.sharpe_ratio
        elif selection_metric == "cagr":
            v = row.cagr
        else:
            v = row.calmar_ratio
        return float(v) if math.isfinite(float(v)) else float("-inf")

    return max(rows, key=lambda r: (_score(r), -r.fast_window, -r.slow_window))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health", tags=["ops"])
def health_check():
    """Return a simple 200 OK to confirm the server is running."""
    return {"status": "ok", "version": "0.7.0"}


@app.post(
    "/backtest/sma-crossover",
    response_model=BacktestResponse,
    tags=["backtest"],
    summary="Run an SMA crossover backtest",
    description=(
        "Long-only, fully-invested strategy.  "
        "Position = 1 when fast SMA > slow SMA, else 0.  "
        "Signal is shifted one day forward to prevent lookahead bias."
    ),
)
def backtest_sma_crossover(request: BacktestRequest) -> BacktestResponse:
    _validate_common(request.ticker, request.start_date, request.end_date)

    if request.fast_window >= request.slow_window:
        raise HTTPException(
            status_code=422,
            detail=(
                f"fast_window ({request.fast_window}) must be less than "
                f"slow_window ({request.slow_window})."
            ),
        )

    df = _fetch(request.ticker, request.start_date, request.end_date)

    min_bars = request.slow_window + 2
    if len(df) < min_bars:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Only {len(df)} trading days available; need at least "
                f"{min_bars} for a {request.slow_window}-day slow SMA."
            ),
        )

    close = df["Close"]
    position = sma_crossover_signals(
        close,
        fast_window=request.fast_window,
        slow_window=request.slow_window,
    )

    return _build_response(
        request_ticker=request.ticker,
        start_date=request.start_date,
        end_date=request.end_date,
        transaction_cost_bps=request.transaction_cost_bps,
        initial_capital=request.initial_capital,
        close=close,
        position=position,
        strategy="sma_crossover",
        fast_window=request.fast_window,
        slow_window=request.slow_window,
    )


@app.post(
    "/backtest/rsi-mean-reversion",
    response_model=BacktestResponse,
    tags=["backtest"],
    summary="Run an RSI mean-reversion backtest",
    description=(
        "Long-only mean-reversion strategy.  "
        "Enters long when RSI falls below the oversold threshold.  "
        "Exits when RSI rises above the exit threshold.  "
        "Signal is shifted one day forward to prevent lookahead bias."
    ),
)
def backtest_rsi_mean_reversion(request: RsiBacktestRequest) -> BacktestResponse:
    _validate_common(request.ticker, request.start_date, request.end_date)

    df = _fetch(request.ticker, request.start_date, request.end_date)

    # RSI needs rsi_window bars to warm up, +1 for the shift, +1 for first return.
    min_bars = request.rsi_window + 5
    if len(df) < min_bars:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Only {len(df)} trading days available; need at least "
                f"{min_bars} for a {request.rsi_window}-period RSI."
            ),
        )

    close = df["Close"]
    position = rsi_mean_reversion_signals(
        close,
        rsi_window=request.rsi_window,
        oversold_threshold=request.oversold_threshold,
        exit_threshold=request.exit_threshold,
    )

    return _build_response(
        request_ticker=request.ticker,
        start_date=request.start_date,
        end_date=request.end_date,
        transaction_cost_bps=request.transaction_cost_bps,
        initial_capital=request.initial_capital,
        close=close,
        position=position,
        strategy="rsi_mean_reversion",
        rsi_window=request.rsi_window,
        oversold_threshold=request.oversold_threshold,
        exit_threshold=request.exit_threshold,
    )


@app.post(
    "/backtest/bollinger-band",
    response_model=BacktestResponse,
    tags=["backtest"],
    summary="Run a Bollinger Band mean-reversion backtest",
    description=(
        "Long-only mean-reversion strategy.  "
        "Enters long when price falls below the lower Bollinger Band.  "
        "Exits when price recovers to or above the selected exit band "
        "('middle' = SMA, 'upper' = upper band).  "
        "Signal is shifted one day forward to prevent lookahead bias."
    ),
)
def backtest_bollinger_band(request: BbBacktestRequest) -> BacktestResponse:
    _validate_common(request.ticker, request.start_date, request.end_date)

    df = _fetch(request.ticker, request.start_date, request.end_date)

    # BB needs bb_window bars to warm up, +1 for the shift, +1 for first return.
    min_bars = request.bb_window + 5
    if len(df) < min_bars:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Only {len(df)} trading days available; need at least "
                f"{min_bars} for a {request.bb_window}-period Bollinger Band."
            ),
        )

    close = df["Close"]
    position = bollinger_band_signals(
        close,
        bb_window=request.bb_window,
        num_std=request.num_std,
        exit_band=request.exit_band,
    )

    return _build_response(
        request_ticker=request.ticker,
        start_date=request.start_date,
        end_date=request.end_date,
        transaction_cost_bps=request.transaction_cost_bps,
        initial_capital=request.initial_capital,
        close=close,
        position=position,
        strategy="bollinger_band",
        bb_window=request.bb_window,
        bb_num_std=request.num_std,
        bb_exit_band=request.exit_band,
    )


@app.post(
    "/backtest/momentum",
    response_model=BacktestResponse,
    tags=["backtest"],
    summary="Run a time-series momentum backtest",
    description=(
        "Long-only time-series momentum strategy.  "
        "Enters long when the trailing N-day return exceeds the entry threshold.  "
        "Exits when the trailing return falls to or below the exit threshold.  "
        "Default thresholds of 0.0 implement the classical binary momentum rule "
        "(long when past return > 0, flat otherwise).  "
        "Signal is shifted one day forward to prevent lookahead bias."
    ),
)
def backtest_momentum(request: MomentumBacktestRequest) -> BacktestResponse:
    _validate_common(request.ticker, request.start_date, request.end_date)

    df = _fetch(request.ticker, request.start_date, request.end_date)

    # Momentum needs momentum_window bars to compute the first return value,
    # +1 for the shift, +1 for the first equity return.
    min_bars = request.momentum_window + 5
    if len(df) < min_bars:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Only {len(df)} trading days available; need at least "
                f"{min_bars} for a {request.momentum_window}-day momentum window."
            ),
        )

    close = df["Close"]
    position = momentum_signals(
        close,
        momentum_window=request.momentum_window,
        entry_threshold=request.entry_threshold,
        exit_threshold=request.exit_threshold,
    )

    return _build_response(
        request_ticker=request.ticker,
        start_date=request.start_date,
        end_date=request.end_date,
        transaction_cost_bps=request.transaction_cost_bps,
        initial_capital=request.initial_capital,
        close=close,
        position=position,
        strategy="momentum",
        momentum_window=request.momentum_window,
        momentum_entry_threshold=request.entry_threshold,
        momentum_exit_threshold=request.exit_threshold,
    )


@app.post(
    "/backtest/volatility-breakout",
    response_model=BacktestResponse,
    tags=["backtest"],
    summary="Run a volatility breakout backtest",
    description=(
        "Long-only trend-following strategy.  "
        "Enters long when close breaks above the prior rolling high plus a "
        "multiple of the prior rolling high-low range.  "
        "Exits when close falls below the rolling mean exit level.  "
        "Signal is shifted one day forward to prevent lookahead bias."
    ),
)
def backtest_volatility_breakout(request: VbBacktestRequest) -> BacktestResponse:
    _validate_common(request.ticker, request.start_date, request.end_date)

    df = _fetch(request.ticker, request.start_date, request.end_date)

    # Need lookback_window bars for the prior channel, plus one shift bar.
    min_bars = max(request.lookback_window + 2, request.exit_window + 2)
    if len(df) < min_bars:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Only {len(df)} trading days available; need at least "
                f"{min_bars} for a {request.lookback_window}-day lookback and "
                f"{request.exit_window}-day exit mean."
            ),
        )

    close = df["Close"]
    position = volatility_breakout_signals(
        close,
        lookback_window=request.lookback_window,
        breakout_multiplier=request.breakout_multiplier,
        exit_window=request.exit_window,
    )

    return _build_response(
        request_ticker=request.ticker,
        start_date=request.start_date,
        end_date=request.end_date,
        transaction_cost_bps=request.transaction_cost_bps,
        initial_capital=request.initial_capital,
        close=close,
        position=position,
        strategy="volatility_breakout",
        vb_lookback_window=request.lookback_window,
        vb_breakout_multiplier=request.breakout_multiplier,
        vb_exit_window=request.exit_window,
    )


@app.post(
    "/backtest/pairs",
    response_model=BacktestResponse,
    tags=["backtest"],
    summary="Run a pairs trading backtest",
    description=(
        "Dollar-neutral statistical arbitrage strategy on two assets.  "
        "Spread = log(close_y) - log(close_x).  "
        "Enters long-spread (long Y / short X) when the z-score of the spread "
        "falls below -entry_z_score, and short-spread (short Y / long X) when "
        "it rises above +entry_z_score.  "
        "Long-spread exits when z-score > -exit_z_score; short-spread exits "
        "when z-score < +exit_z_score.  "
        "Each leg receives 50% of capital; benchmark is equal-weight buy-and-hold.  "
        "Signal is shifted one day forward to prevent lookahead bias."
    ),
)
def backtest_pairs(request: PairsBacktestRequest) -> BacktestResponse:
    asset_y = request.asset_y.strip()
    asset_x = request.asset_x.strip()

    if not asset_y:
        raise HTTPException(status_code=422, detail="asset_y must not be empty.")
    if not asset_x:
        raise HTTPException(status_code=422, detail="asset_x must not be empty.")

    # Reuse common date/format validation (ticker param is ignored for dates check).
    _validate_common(asset_y, request.start_date, request.end_date)

    # Fetch and align both price series.
    try:
        close_y, close_x = fetch_pairs_close(
            asset_y, asset_x, request.start_date, request.end_date
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Data fetch failed: {exc}"
        ) from exc

    min_bars = request.lookback_window + 5
    if len(close_y) < min_bars:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Only {len(close_y)} common trading days available; need at least "
                f"{min_bars} for a {request.lookback_window}-day lookback window."
            ),
        )

    # Generate signals.
    signal = pairs_signals(
        close_y,
        close_x,
        lookback_window=request.lookback_window,
        entry_z_score=request.entry_z_score,
        exit_z_score=request.exit_z_score,
    )

    # Run the pairs-specific backtest engine.
    strategy_equity, benchmark_equity, trades = run_pairs_backtest(
        close_y=close_y,
        close_x=close_x,
        signal=signal,
        transaction_cost_bps=request.transaction_cost_bps,
        initial_capital=request.initial_capital,
    )

    strategy_metrics_dict = compute_metrics(strategy_equity)
    benchmark_metrics_dict = compute_metrics(benchmark_equity)

    equity_curve = [
        EquityPoint(
            date=str(d.date()) if hasattr(d, "date") else str(d),
            strategy=round(float(s), 2),
            benchmark=round(float(b), 2),
        )
        for d, s, b in zip(strategy_equity.index, strategy_equity, benchmark_equity)
    ]

    ticker_label = f"{asset_y.upper()}/{asset_x.upper()}"

    return BacktestResponse(
        ticker=ticker_label,
        start_date=request.start_date,
        end_date=request.end_date,
        strategy="pairs",
        transaction_cost_bps=request.transaction_cost_bps,
        initial_capital=request.initial_capital,
        pairs_asset_y=asset_y.upper(),
        pairs_asset_x=asset_x.upper(),
        pairs_lookback_window=request.lookback_window,
        pairs_entry_z_score=request.entry_z_score,
        pairs_exit_z_score=request.exit_z_score,
        strategy_metrics=PerformanceMetrics(**strategy_metrics_dict),
        benchmark_metrics=PerformanceMetrics(**benchmark_metrics_dict),
        equity_curve=equity_curve,
        trades=[TradeRecord(**t) for t in trades],
        num_trades=len(trades),
    )


# ---------------------------------------------------------------------------
# Multi-asset portfolio backtesting
# ---------------------------------------------------------------------------


def _resolve_benchmark(prices, start_date: str, end_date: str, tickers: list):
    """
    Choose a benchmark series aligned to the portfolio's dates.

    Preference order:
      1. SPY column already present in the portfolio prices.
      2. SPY fetched separately and reindexed onto the portfolio dates.
      3. Fallback: the first portfolio ticker (documented behaviour).

    Returns ``(benchmark_ticker, benchmark_close_series)``.
    """
    if "SPY" in prices.columns:
        return "SPY", prices["SPY"]

    try:
        spy_close = _fetch("SPY", start_date, end_date)["Close"]
        # Forward-fill only: carrying a future SPY price backward would leak
        # information into earlier benchmark dates. If SPY cannot cover the
        # portfolio's first date, fall back to the first held asset.
        spy_close = spy_close.reindex(prices.index).ffill()
        if spy_close.notna().all() and len(spy_close) >= 2:
            return "SPY", spy_close
    except Exception:
        pass  # fall through to the first-ticker fallback

    first = tickers[0]
    return first, prices[first]


@app.post(
    "/portfolio/backtest",
    response_model=PortfolioBacktestResponse,
    tags=["portfolio"],
    summary="Equal-weight multi-asset portfolio backtest",
    description=(
        "Backtest a simple equal-weight, long-only, fully-invested portfolio "
        "with optional periodic rebalancing (none / monthly / quarterly / "
        "yearly).  Each asset targets weight 1/N; rebalancing costs are "
        "turnover-based.  This is not portfolio optimisation.\n\n"
        "Benchmark: SPY buy-and-hold when available (in the basket or fetched "
        "separately); otherwise the first ticker is used as a documented "
        "fallback."
    ),
)
def portfolio_backtest(request: PortfolioBacktestRequest) -> PortfolioBacktestResponse:
    tickers = request.tickers  # already cleaned/uppercased/deduped by the schema

    # Fetch each asset's close (reuses the single-asset fetch + error mapping).
    frames = {}
    for ticker in tickers:
        df = _fetch(ticker, request.start_date, request.end_date)
        frames[ticker] = df["Close"]

    prices = align_prices(frames)
    if len(prices) < 2:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Only {len(prices)} common trading day(s) across "
                f"{', '.join(tickers)}; need at least 2.  Try a wider date "
                "range or assets with overlapping history."
            ),
        )

    try:
        result = run_equal_weight_portfolio(
            prices,
            initial_capital=request.initial_capital,
            rebalance_frequency=request.rebalance_frequency,
            transaction_cost_bps=request.transaction_cost_bps,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Benchmark aligned to the portfolio's dates.
    benchmark_ticker, bench_close = _resolve_benchmark(
        prices, request.start_date, request.end_date, tickers
    )
    benchmark_equity = request.initial_capital * (bench_close / float(bench_close.iloc[0]))

    portfolio_equity = result.equity
    port_dd = drawdown_series(portfolio_equity)
    bench_dd = drawdown_series(benchmark_equity)

    equity_curve = [
        PortfolioEquityPoint(
            date=str(d.date()) if hasattr(d, "date") else str(d),
            portfolio=round(float(p), 2),
            benchmark=round(float(b), 2),
        )
        for d, p, b in zip(portfolio_equity.index, portfolio_equity, benchmark_equity)
    ]
    drawdown = [
        PortfolioDrawdownPoint(
            date=str(d.date()) if hasattr(d, "date") else str(d),
            portfolio=round(float(p), 6),
            benchmark=round(float(b), 6),
        )
        for d, p, b in zip(port_dd.index, port_dd, bench_dd)
    ]

    metrics = PerformanceMetrics(**compute_metrics(portfolio_equity))
    benchmark_metrics = PerformanceMetrics(**compute_metrics(benchmark_equity))

    return PortfolioBacktestResponse(
        tickers=tickers,
        start_date=request.start_date,
        end_date=request.end_date,
        strategy="equal_weight_portfolio",
        rebalance_frequency=request.rebalance_frequency,
        initial_capital=request.initial_capital,
        transaction_cost_bps=request.transaction_cost_bps,
        benchmark_ticker=benchmark_ticker,
        metrics=metrics,
        benchmark_metrics=benchmark_metrics,
        equity_curve=equity_curve,
        drawdown=drawdown,
        weights=[PortfolioWeightPoint(**w) for w in result.weights],
        rebalance_events=[PortfolioRebalanceEvent(**e) for e in result.rebalance_events],
    )


# ---------------------------------------------------------------------------
# Research endpoints
# ---------------------------------------------------------------------------


@app.post(
    "/research/sma-parameter-sweep",
    response_model=SmaSweepResponse,
    tags=["research"],
    summary="SMA Crossover parameter sweep",
    description=(
        "Run a grid search over all requested (fast, slow) SMA window "
        "combinations for a single asset.  Pairs where fast >= slow are "
        "silently skipped.  Data is fetched once and each combination is "
        "backtested with the same costs and capital.  "
        "Maximum 10 × 10 = 100 combinations per request."
    ),
)
def sma_parameter_sweep(request: SmaSweepRequest) -> SmaSweepResponse:
    _validate_common(request.ticker, request.start_date, request.end_date)

    df = _fetch(request.ticker, request.start_date, request.end_date)
    close = df["Close"]

    rows: list = []
    valid_pairs = 0
    for fast in sorted(set(request.fast_windows)):
        for slow in sorted(set(request.slow_windows)):
            # Skip invalid (fast >= slow) combinations silently.
            if fast >= slow:
                continue
            valid_pairs += 1
            # Skip combinations that need more bars than are available.
            if len(close) < slow + 2:
                continue

            position = sma_crossover_signals(
                close, fast_window=fast, slow_window=slow
            )
            strategy_equity, _bench, trades = run_backtest(
                close=close,
                position=position,
                transaction_cost_bps=request.transaction_cost_bps,
                initial_capital=request.initial_capital,
            )
            m = compute_metrics(strategy_equity)
            rows.append(
                SmaSweepRow(
                    fast_window=fast,
                    slow_window=slow,
                    total_return=m["total_return"],
                    cagr=m["cagr"],
                    sharpe_ratio=m["sharpe_ratio"],
                    sortino_ratio=m["sortino_ratio"],
                    calmar_ratio=m["calmar_ratio"],
                    max_drawdown=m["max_drawdown"],
                    volatility=m["volatility"],
                    num_trades=len(trades),
                )
            )

    if valid_pairs > 0 and not rows:
        max_slow = max(
            slow
            for fast in set(request.fast_windows)
            for slow in set(request.slow_windows)
            if fast < slow
        )
        raise HTTPException(
            status_code=422,
            detail=(
                f"Only {len(close)} trading days available; no valid SMA "
                f"combination can run. Requested slow windows require up to "
                f"{max_slow + 2} trading days."
            ),
        )

    return SmaSweepResponse(
        ticker=request.ticker.strip().upper(),
        start_date=request.start_date,
        end_date=request.end_date,
        transaction_cost_bps=request.transaction_cost_bps,
        initial_capital=request.initial_capital,
        num_combinations=len(rows),
        results=rows,
    )


@app.post(
    "/research/sma-train-test",
    response_model=SmaTrainTestResponse,
    tags=["research"],
    summary="SMA Train/Test Out-of-Sample Validation",
    description=(
        "Split the date range into in-sample (IS) and out-of-sample (OOS) "
        "periods at split_date.  Run a parameter sweep on IS data only, pick "
        "the best (fast, slow) pair by the chosen selection metric, then "
        "evaluate those parameters on OOS data.  Reports IS metrics, OOS "
        "metrics, degradation, and an oos_collapsed warning flag.  "
        "No data leakage: OOS data is never used during parameter selection."
    ),
)
def sma_train_test(request: SmaTrainTestRequest) -> SmaTrainTestResponse:
    import math
    import pandas as pd  # local import keeps top-level clean

    # Pydantic has already validated date ordering and format; call the shared
    # helper only for ticker emptiness and start/end date checks.
    _validate_common(request.ticker, request.start_date, request.end_date)

    # Fetch the full price history once.
    df = _fetch(request.ticker, request.start_date, request.end_date)
    close_all = df["Close"]

    # Trim defensively even when a data provider or test double returns rows
    # outside the requested interval.
    start_ts = pd.Timestamp(request.start_date)
    split_ts = pd.Timestamp(request.split_date)
    end_ts = pd.Timestamp(request.end_date)
    close_all = close_all[(close_all.index >= start_ts) & (close_all.index <= end_ts)]

    # Split: IS = [start_date, split_date)  |  OOS = [split_date, end_date]
    close_is = close_all[close_all.index < split_ts]
    close_oos = close_all[close_all.index >= split_ts]

    if len(close_is) < 3:
        raise HTTPException(
            status_code=422,
            detail=(
                f"In-sample period has only {len(close_is)} trading days "
                "(need at least 3).  Move split_date later."
            ),
        )
    if len(close_oos) < 3:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Out-of-sample period has only {len(close_oos)} trading days "
                "(need at least 3).  Move split_date earlier or extend end_date."
            ),
        )

    # ── In-sample parameter sweep (IS data only — no leakage) ─────────────
    is_rows: list = []
    valid_pairs = 0
    for fast in sorted(set(request.fast_windows)):
        for slow in sorted(set(request.slow_windows)):
            if fast >= slow:
                continue
            valid_pairs += 1
            if len(close_is) < slow + 2:
                continue

            position = sma_crossover_signals(
                close_is, fast_window=fast, slow_window=slow
            )
            strategy_equity, _bench, trades = run_backtest(
                close=close_is,
                position=position,
                transaction_cost_bps=request.transaction_cost_bps,
                initial_capital=request.initial_capital,
            )
            m = compute_metrics(strategy_equity)
            is_rows.append(
                SmaSweepRow(
                    fast_window=fast,
                    slow_window=slow,
                    total_return=m["total_return"],
                    cagr=m["cagr"],
                    sharpe_ratio=m["sharpe_ratio"],
                    sortino_ratio=m["sortino_ratio"],
                    calmar_ratio=m["calmar_ratio"],
                    max_drawdown=m["max_drawdown"],
                    volatility=m["volatility"],
                    num_trades=len(trades),
                )
            )

    if valid_pairs > 0 and not is_rows:
        max_slow = max(
            slow
            for fast in set(request.fast_windows)
            for slow in set(request.slow_windows)
            if fast < slow
        )
        raise HTTPException(
            status_code=422,
            detail=(
                f"In-sample period has only {len(close_is)} trading days; "
                f"no valid SMA combination can run.  Requested slow windows "
                f"require up to {max_slow + 2} trading days.  Move split_date "
                f"later or choose smaller window values."
            ),
        )
    if not is_rows:
        raise HTTPException(
            status_code=422,
            detail="No valid (fast < slow) window combinations found.",
        )

    # ── Select best in-sample parameters ──────────────────────────────────
    def _row_score(row: SmaSweepRow) -> float:
        if request.selection_metric == "sharpe_ratio":
            score = row.sharpe_ratio
        elif request.selection_metric == "cagr":
            score = row.cagr
        else:
            score = row.calmar_ratio
        return float(score) if math.isfinite(float(score)) else float("-inf")

    # Deterministic ties: prefer smaller fast, then smaller slow.
    best_row = max(
        is_rows,
        key=lambda row: (_row_score(row), -row.fast_window, -row.slow_window),
    )
    best_fast = best_row.fast_window
    best_slow = best_row.slow_window

    # ── Verify OOS has enough bars for the selected windows ───────────────
    min_oos_bars = best_slow + 2
    if len(close_oos) < min_oos_bars:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Out-of-sample period has only {len(close_oos)} trading days, "
                f"but the best in-sample parameters (fast={best_fast}, "
                f"slow={best_slow}) require at least {min_oos_bars}.  "
                f"Move split_date earlier or extend end_date."
            ),
        )

    # ── Re-run IS backtest for best params → full PerformanceMetrics ──────
    is_position = sma_crossover_signals(
        close_is, fast_window=best_fast, slow_window=best_slow
    )
    is_strategy_equity, _is_bench, _is_trades = run_backtest(
        close=close_is,
        position=is_position,
        transaction_cost_bps=request.transaction_cost_bps,
        initial_capital=request.initial_capital,
    )
    is_metrics_dict = compute_metrics(is_strategy_equity)
    is_metrics = PerformanceMetrics(**is_metrics_dict)

    # ── OOS backtest with the selected parameters ─────────────────────────
    oos_position = sma_crossover_signals(
        close_oos, fast_window=best_fast, slow_window=best_slow
    )
    oos_strategy_equity, oos_bench_equity, oos_trades = run_backtest(
        close=close_oos,
        position=oos_position,
        transaction_cost_bps=request.transaction_cost_bps,
        initial_capital=request.initial_capital,
    )
    oos_metrics_dict = compute_metrics(oos_strategy_equity)
    oos_bench_metrics_dict = compute_metrics(oos_bench_equity)
    oos_metrics = PerformanceMetrics(**oos_metrics_dict)
    oos_bench_metrics = PerformanceMetrics(**oos_bench_metrics_dict)

    # ── Build OOS equity curve ─────────────────────────────────────────────
    oos_equity_curve = [
        EquityPoint(
            date=str(d.date()) if hasattr(d, "date") else str(d),
            strategy=round(float(s), 2),
            benchmark=round(float(b), 2),
        )
        for d, s, b in zip(
            oos_strategy_equity.index, oos_strategy_equity, oos_bench_equity
        )
    ]

    # ── Degradation (OOS − IS; negative = performance deteriorated) ───────
    sharpe_degradation = round(
        oos_metrics_dict["sharpe_ratio"] - is_metrics_dict["sharpe_ratio"], 4
    )
    cagr_degradation = round(
        oos_metrics_dict["cagr"] - is_metrics_dict["cagr"], 6
    )
    calmar_degradation = round(
        oos_metrics_dict["calmar_ratio"] - is_metrics_dict["calmar_ratio"], 4
    )
    max_drawdown_worsening = round(
        abs(oos_metrics_dict["max_drawdown"]) - abs(is_metrics_dict["max_drawdown"]),
        6,
    )

    # oos_collapsed: OOS Sharpe < 0, or OOS Sharpe < 50 % of IS Sharpe
    # (only triggered when IS Sharpe > 0.1 to avoid noise on flat strategies).
    oos_sharpe = oos_metrics_dict["sharpe_ratio"]
    is_sharpe = is_metrics_dict["sharpe_ratio"]
    oos_collapsed = bool(
        oos_sharpe < 0
        or (is_sharpe > 0.1 and oos_sharpe < is_sharpe * 0.5)
    )

    return SmaTrainTestResponse(
        ticker=request.ticker.strip().upper(),
        start_date=request.start_date,
        split_date=request.split_date,
        end_date=request.end_date,
        transaction_cost_bps=request.transaction_cost_bps,
        initial_capital=request.initial_capital,
        selection_metric=request.selection_metric,
        in_sample_days=int(len(close_is)),
        out_of_sample_days=int(len(close_oos)),
        best_fast_window=best_fast,
        best_slow_window=best_slow,
        in_sample_metrics=is_metrics,
        out_of_sample_metrics=oos_metrics,
        out_of_sample_benchmark_metrics=oos_bench_metrics,
        out_of_sample_equity_curve=oos_equity_curve,
        out_of_sample_trades=[TradeRecord(**t) for t in oos_trades],
        out_of_sample_num_trades=len(oos_trades),
        sharpe_degradation=sharpe_degradation,
        cagr_degradation=cagr_degradation,
        calmar_degradation=calmar_degradation,
        max_drawdown_worsening=max_drawdown_worsening,
        oos_collapsed=oos_collapsed,
        all_in_sample_results=is_rows,
    )


@app.post(
    "/research/sma-walk-forward",
    response_model=SmaWalkForwardResponse,
    tags=["research"],
    summary="SMA Walk-Forward Optimization",
    description=(
        "Repeatedly roll a training window forward, run an SMA parameter sweep "
        "on that window, select the best (fast, slow) pair, then evaluate it on "
        "the following out-of-sample test window.  The test windows are stitched "
        "together into a single OOS equity curve.  Reports per-window metrics, "
        "aggregate statistics, and a parameter-stability summary.  "
        "No future data ever leaks into the training window."
    ),
)
def sma_walk_forward(request: SmaWalkForwardRequest) -> SmaWalkForwardResponse:
    import pandas as pd
    from collections import Counter

    _validate_common(request.ticker, request.start_date, request.end_date)

    df = _fetch(request.ticker, request.start_date, request.end_date)
    close_all = df["Close"]

    # Trim to the requested date range.
    start_ts = pd.Timestamp(request.start_date)
    end_ts = pd.Timestamp(request.end_date)
    close_all = close_all[(close_all.index >= start_ts) & (close_all.index <= end_ts)]

    n = len(close_all)
    train_w = request.train_window_days
    test_w = request.test_window_days
    step = request.step_days

    # Need at least one complete (train + test) window.
    if n < train_w + test_w:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Only {n} trading days available; need at least "
                f"{train_w + test_w} "
                f"(train_window_days={train_w} + test_window_days={test_w})."
            ),
        )

    # Verify at least one valid (fast < slow) pair exists.
    has_valid_pair = any(
        f < s
        for f in request.fast_windows
        for s in request.slow_windows
    )
    if not has_valid_pair:
        raise HTTPException(
            status_code=422,
            detail="No valid (fast < slow) window combinations found.",
        )

    # ── Walk-forward loop ─────────────────────────────────────────────────
    completed_windows: list = []
    stitched_dates: list = []
    stitched_strategy_values: list = []
    stitched_benchmark_values: list = []

    current_capital = request.initial_capital
    current_bench_capital = request.initial_capital
    last_stitched_date = None
    train_start_idx = 0

    while True:
        train_end_idx = train_start_idx + train_w
        test_start_idx = train_end_idx
        test_end_idx = test_start_idx + test_w

        if test_end_idx > n:
            break
        if len(completed_windows) >= 200:   # safety cap
            break

        close_train = close_all.iloc[train_start_idx:train_end_idx]
        close_test = close_all.iloc[test_start_idx:test_end_idx]

        # ── IS sweep on training window ──────────────────────────────────
        sweep, valid_pairs = _sweep_rows(
            close=close_train,
            fast_windows=request.fast_windows,
            slow_windows=request.slow_windows,
            transaction_cost_bps=request.transaction_cost_bps,
            initial_capital=request.initial_capital,
        )

        if not sweep:
            max_slow = max(
                slow
                for fast in set(request.fast_windows)
                for slow in set(request.slow_windows)
                if fast < slow
            )
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Training window has only {len(close_train)} trading days; "
                    f"no valid SMA combination can run. Requested slow windows "
                    f"require up to {max_slow + 2} trading days."
                ),
            )

        chosen = _best_row(sweep, request.selection_metric)
        best_fast = chosen.fast_window
        best_slow = chosen.slow_window

        # ── Re-run train backtest for best params → full train_metrics ───
        train_pos = sma_crossover_signals(
            close_train, fast_window=best_fast, slow_window=best_slow
        )
        train_eq, _train_bench, _train_trades = run_backtest(
            close=close_train,
            position=train_pos,
            transaction_cost_bps=request.transaction_cost_bps,
            initial_capital=request.initial_capital,
        )
        train_metrics_dict = compute_metrics(train_eq)

        # Build the test signal with trailing training history available.
        # This avoids an artificial SMA warm-up inside each OOS slice while
        # still using only data dated before or inside the current test window.
        signal_context = close_all.iloc[train_start_idx:test_end_idx]
        context_pos = sma_crossover_signals(
            signal_context, fast_window=best_fast, slow_window=best_slow
        )
        test_pos = context_pos.reindex(close_test.index).fillna(0).astype(int)

        # ── OOS backtest on test window ──────────────────────────────────
        test_strat_eq, test_bench_eq, test_trades = run_backtest(
            close=close_test,
            position=test_pos,
            transaction_cost_bps=request.transaction_cost_bps,
            initial_capital=request.initial_capital,
        )

        test_metrics_dict = compute_metrics(test_strat_eq)
        test_bench_metrics_dict = compute_metrics(test_bench_eq)

        # ── Store window result ──────────────────────────────────────────
        completed_windows.append(
            SmaWalkForwardWindow(
                window_index=len(completed_windows),
                train_start_date=str(close_train.index[0].date()),
                train_end_date=str(close_train.index[-1].date()),
                test_start_date=str(close_test.index[0].date()),
                test_end_date=str(close_test.index[-1].date()),
                train_days=len(close_train),
                test_days=len(close_test),
                best_fast_window=best_fast,
                best_slow_window=best_slow,
                train_metrics=PerformanceMetrics(**train_metrics_dict),
                test_metrics=PerformanceMetrics(**test_metrics_dict),
                test_benchmark_metrics=PerformanceMetrics(**test_bench_metrics_dict),
                num_trades=len(test_trades),
            )
        )

        # Stitch only dates not already owned by an earlier test window. This
        # keeps overlapping windows from double-counting returns while allowing
        # step_days < test_window_days.
        test_strategy_returns = test_strat_eq.pct_change().fillna(0.0)
        test_benchmark_returns = test_bench_eq.pct_change().fillna(0.0)
        for dt in close_test.index:
            if last_stitched_date is not None and dt <= last_stitched_date:
                continue
            current_capital *= 1.0 + float(test_strategy_returns.loc[dt])
            current_bench_capital *= 1.0 + float(test_benchmark_returns.loc[dt])
            stitched_dates.append(dt)
            stitched_strategy_values.append(current_capital)
            stitched_benchmark_values.append(current_bench_capital)
            last_stitched_date = dt

        train_start_idx += step

    if not completed_windows:
        raise HTTPException(
            status_code=422,
            detail=(
                "No walk-forward windows could be completed.  "
                "The date range may be too short, or all parameter combinations "
                "require more bars than are available in the training window.  "
                "Try a shorter train_window_days or larger date range."
            ),
        )

    # ── Stitch equity curves ──────────────────────────────────────────────
    stitched_strat = pd.Series(stitched_strategy_values, index=stitched_dates)
    stitched_bench = pd.Series(stitched_benchmark_values, index=stitched_dates)

    stitched_equity_curve = [
        EquityPoint(
            date=str(d.date()) if hasattr(d, "date") else str(d),
            strategy=round(float(s), 2),
            benchmark=round(float(b), 2),
        )
        for d, s, b in zip(stitched_strat.index, stitched_strat, stitched_bench)
    ]

    # ── Aggregate metrics on stitched OOS performance ─────────────────────
    agg_metrics_dict = (
        compute_metrics(stitched_strat) if len(stitched_strat) >= 2
        else {k: 0.0 for k in (
            "total_return", "cagr", "sharpe_ratio", "sortino_ratio",
            "max_drawdown", "volatility", "calmar_ratio", "win_rate",
        )} | {"num_days": len(stitched_strat)}
    )
    agg_bench_metrics_dict = (
        compute_metrics(stitched_bench) if len(stitched_bench) >= 2
        else agg_metrics_dict.copy()
    )

    # ── Parameter stability ───────────────────────────────────────────────
    selected_pairs = [
        (w.best_fast_window, w.best_slow_window) for w in completed_windows
    ]
    pair_counter: Counter = Counter(selected_pairs)
    most_common_pair, most_common_count = min(
        pair_counter.items(),
        key=lambda item: (-item[1], item[0][0], item[0][1]),
    )
    unique_count = len(pair_counter)
    n_windows = len(completed_windows)
    parameters_unstable = (most_common_count / n_windows) <= 0.5

    return SmaWalkForwardResponse(
        ticker=request.ticker.strip().upper(),
        start_date=request.start_date,
        end_date=request.end_date,
        train_window_days=request.train_window_days,
        test_window_days=request.test_window_days,
        step_days=request.step_days,
        selection_metric=request.selection_metric,
        initial_capital=request.initial_capital,
        transaction_cost_bps=request.transaction_cost_bps,
        num_windows=n_windows,
        windows=completed_windows,
        stitched_equity_curve=stitched_equity_curve,
        aggregate_metrics=PerformanceMetrics(**agg_metrics_dict),
        aggregate_benchmark_metrics=PerformanceMetrics(**agg_bench_metrics_dict),
        parameter_stability=SmaWalkForwardParamStability(
            num_windows=n_windows,
            unique_parameter_sets=unique_count,
            most_common_fast_window=most_common_pair[0],
            most_common_slow_window=most_common_pair[1],
            most_common_count=most_common_count,
            all_selected_params=[
                SmaWalkForwardBestParams(
                    fast_window=w.best_fast_window,
                    slow_window=w.best_slow_window,
                )
                for w in completed_windows
            ],
            parameters_unstable=parameters_unstable,
        ),
    )


@app.post(
    "/research/strategy-comparison",
    response_model=StrategyComparisonResponse,
    tags=["research"],
    summary="Multi-strategy comparison",
    description=(
        "Run five single-asset strategies on the same ticker and date range "
        "using fixed default parameters, then rank them by key performance "
        "metrics.  Strategies: SMA Crossover (fast=50, slow=200), "
        "RSI Mean Reversion (window=14, OB=30, exit=50), "
        "Bollinger Band (window=20, 2σ, exit=middle), "
        "Momentum (window=126, thresholds=0), "
        "Volatility Breakout (lookback=20, mult=1.0, exit=10).  "
        "Pairs Trading is excluded (two-asset strategy).  "
        "Data is fetched once; all strategies share the same price history.  "
        "All signals use a one-day forward shift to prevent lookahead bias."
    ),
)
def strategy_comparison(request: StrategyComparisonRequest) -> StrategyComparisonResponse:
    import math
    import pandas as pd

    _validate_common(request.ticker, request.start_date, request.end_date)
    df = _fetch(request.ticker, request.start_date, request.end_date)
    close = df["Close"]

    # Defensive trim: data providers and tests may return a superset of the
    # requested range. All strategies and the shared benchmark must compare the
    # exact requested period only.
    start_ts = pd.Timestamp(request.start_date)
    end_ts = pd.Timestamp(request.end_date)
    close = close[(close.index >= start_ts) & (close.index <= end_ts)]

    # SMA 50/200 is the most restrictive default: needs slow + 2 = 202 bars.
    min_bars = 202
    if len(close) < min_bars:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Only {len(close)} trading days available; need at least "
                f"{min_bars} for strategy comparison "
                f"(SMA Crossover with slow=200 requires {min_bars} trading days)."
            ),
        )

    # ── Helper: zip strategy + shared benchmark into EquityPoint list ─────
    def _curve(strat_eq, bench_eq):
        return [
            EquityPoint(
                date=str(d.date()) if hasattr(d, "date") else str(d),
                strategy=round(float(s), 2),
                benchmark=round(float(b), 2),
            )
            for d, s, b in zip(strat_eq.index, strat_eq, bench_eq)
        ]

    results: list = []
    bench_eq = None  # populated on first strategy run; identical for all

    # ── 1. SMA Crossover (fast=50, slow=200) ─────────────────────────────
    sma_pos = sma_crossover_signals(close, fast_window=50, slow_window=200)
    sma_eq, bench_eq, sma_trades = run_backtest(
        close=close,
        position=sma_pos,
        transaction_cost_bps=request.transaction_cost_bps,
        initial_capital=request.initial_capital,
    )
    results.append(StrategyResultItem(
        strategy="sma_crossover",
        display_name="SMA Crossover",
        params={"fast_window": 50, "slow_window": 200},
        metrics=PerformanceMetrics(**compute_metrics(sma_eq)),
        equity_curve=_curve(sma_eq, bench_eq),
        num_trades=len(sma_trades),
    ))

    # ── 2. RSI Mean Reversion (window=14, oversold=30, exit=50) ──────────
    rsi_pos = rsi_mean_reversion_signals(
        close, rsi_window=14, oversold_threshold=30.0, exit_threshold=50.0
    )
    rsi_eq, _, rsi_trades = run_backtest(
        close=close,
        position=rsi_pos,
        transaction_cost_bps=request.transaction_cost_bps,
        initial_capital=request.initial_capital,
    )
    results.append(StrategyResultItem(
        strategy="rsi_mean_reversion",
        display_name="RSI Mean Reversion",
        params={"rsi_window": 14, "oversold_threshold": 30.0, "exit_threshold": 50.0},
        metrics=PerformanceMetrics(**compute_metrics(rsi_eq)),
        equity_curve=_curve(rsi_eq, bench_eq),
        num_trades=len(rsi_trades),
    ))

    # ── 3. Bollinger Band (window=20, 2σ, exit=middle) ───────────────────
    bb_pos = bollinger_band_signals(
        close, bb_window=20, num_std=2.0, exit_band="middle"
    )
    bb_eq, _, bb_trades = run_backtest(
        close=close,
        position=bb_pos,
        transaction_cost_bps=request.transaction_cost_bps,
        initial_capital=request.initial_capital,
    )
    results.append(StrategyResultItem(
        strategy="bollinger_band",
        display_name="Bollinger Band",
        params={"bb_window": 20, "num_std": 2.0, "exit_band": "middle"},
        metrics=PerformanceMetrics(**compute_metrics(bb_eq)),
        equity_curve=_curve(bb_eq, bench_eq),
        num_trades=len(bb_trades),
    ))

    # ── 4. Momentum (window=126, entry=0, exit=0) ─────────────────────────
    mom_pos = momentum_signals(
        close, momentum_window=126, entry_threshold=0.0, exit_threshold=0.0
    )
    mom_eq, _, mom_trades = run_backtest(
        close=close,
        position=mom_pos,
        transaction_cost_bps=request.transaction_cost_bps,
        initial_capital=request.initial_capital,
    )
    results.append(StrategyResultItem(
        strategy="momentum",
        display_name="Momentum",
        params={"momentum_window": 126, "entry_threshold": 0.0, "exit_threshold": 0.0},
        metrics=PerformanceMetrics(**compute_metrics(mom_eq)),
        equity_curve=_curve(mom_eq, bench_eq),
        num_trades=len(mom_trades),
    ))

    # ── 5. Volatility Breakout (lookback=20, mult=1.0, exit=10) ──────────
    vb_pos = volatility_breakout_signals(
        close, lookback_window=20, breakout_multiplier=1.0, exit_window=10
    )
    vb_eq, _, vb_trades = run_backtest(
        close=close,
        position=vb_pos,
        transaction_cost_bps=request.transaction_cost_bps,
        initial_capital=request.initial_capital,
    )
    results.append(StrategyResultItem(
        strategy="volatility_breakout",
        display_name="Volatility Breakout",
        params={"lookback_window": 20, "breakout_multiplier": 1.0, "exit_window": 10},
        metrics=PerformanceMetrics(**compute_metrics(vb_eq)),
        equity_curve=_curve(vb_eq, bench_eq),
        num_trades=len(vb_trades),
    ))

    # ── Benchmark metrics + curve ─────────────────────────────────────────
    bench_m = compute_metrics(bench_eq)
    bench_curve = [
        EquityPoint(
            date=str(d.date()) if hasattr(d, "date") else str(d),
            strategy=round(float(v), 2),
            benchmark=round(float(v), 2),
        )
        for d, v in zip(bench_eq.index, bench_eq)
    ]

    # ── Ranking ───────────────────────────────────────────────────────────
    def _safe(v: float) -> float:
        fv = float(v)
        return fv if math.isfinite(fv) else float("-inf")

    order = {item.display_name: i for i, item in enumerate(results)}

    def _rank(metric_getter):
        return max(
            results,
            key=lambda r: (_safe(metric_getter(r)), -order[r.display_name]),
        ).display_name

    best_sharpe = _rank(lambda r: r.metrics.sharpe_ratio)
    best_cagr = _rank(lambda r: r.metrics.cagr)
    best_calmar = _rank(lambda r: r.metrics.calmar_ratio)
    # max_drawdown is negative; "lowest" = smallest absolute drawdown = closest to 0
    lowest_dd = _rank(lambda r: r.metrics.max_drawdown)

    return StrategyComparisonResponse(
        ticker=request.ticker.strip().upper(),
        start_date=request.start_date,
        end_date=request.end_date,
        initial_capital=request.initial_capital,
        transaction_cost_bps=request.transaction_cost_bps,
        strategies=results,
        benchmark=bench_curve,
        benchmark_metrics=PerformanceMetrics(**bench_m),
        ranking=StrategyComparisonRanking(
            best_by_sharpe=best_sharpe,
            best_by_cagr=best_cagr,
            best_by_calmar=best_calmar,
            lowest_drawdown=lowest_dd,
        ),
    )


# ---------------------------------------------------------------------------
# Saved Backtests endpoints
# ---------------------------------------------------------------------------


@app.post(
    "/saved-backtests",
    response_model=SavedBacktestFull,
    tags=["saved"],
    summary="Save a backtest result",
    description=(
        "Persist a completed backtest result to the local SQLite database.  "
        "Accepts the full result payload (metrics, equity curve, trades) from "
        "any backtest endpoint.  Returns the saved record with its assigned "
        "``id`` and ``created_at`` timestamp."
    ),
)
def create_saved_backtest_endpoint(request: SavedBacktestCreate) -> SavedBacktestFull:
    record = db_create(request.model_dump())
    return SavedBacktestFull(**record)


@app.get(
    "/saved-backtests",
    response_model=list[SavedBacktestSummary],
    tags=["saved"],
    summary="List saved backtests",
    description=(
        "Return all saved backtest records as lightweight summary rows "
        "(no equity curve, trades, or full params blobs).  "
        "Ordered newest-first by creation timestamp."
    ),
)
def list_saved_backtests_endpoint() -> list[SavedBacktestSummary]:
    rows = db_list()
    return [SavedBacktestSummary(**row) for row in rows]


@app.get(
    "/saved-backtests/{id}",
    response_model=SavedBacktestFull,
    tags=["saved"],
    summary="Get a saved backtest",
    description="Return the full saved backtest record including equity curve and trades.",
)
def get_saved_backtest_endpoint(id: int) -> SavedBacktestFull:
    record = db_get(id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Saved backtest {id} not found."
        )
    return SavedBacktestFull(**record)


@app.delete(
    "/saved-backtests/{id}",
    response_model=DeleteResponse,
    tags=["saved"],
    summary="Delete a saved backtest",
    description="Permanently delete a saved backtest record by id.",
)
def delete_saved_backtest_endpoint(id: int) -> DeleteResponse:
    deleted = db_delete(id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Saved backtest {id} not found."
        )
    return DeleteResponse(deleted=True, id=id)


# ---------------------------------------------------------------------------
# CSV upload backtesting
# ---------------------------------------------------------------------------

# Maximum accepted upload size (5 MB ~ decades of daily bars).
_MAX_CSV_BYTES = 5 * 1024 * 1024

# Single-asset strategies supported for CSV upload.  Each maps to the existing
# request model so all field constraints and cross-field validators are reused.
_CSV_PARAM_MODELS = {
    "sma_crossover": BacktestRequest,
    "rsi_mean_reversion": RsiBacktestRequest,
    "bollinger_band": BbBacktestRequest,
    "momentum": MomentumBacktestRequest,
    "volatility_breakout": VbBacktestRequest,
}


def _format_validation_error(exc: ValidationError) -> str:
    """Flatten a Pydantic ValidationError into a single human-readable string."""
    parts = []
    for err in exc.errors():
        loc = err.get("loc", ())
        field = loc[-1] if loc else ""
        msg = err.get("msg", "invalid value")
        parts.append(f"{field}: {msg}" if field else str(msg))
    return "; ".join(parts) or "Invalid parameters."


def _csv_label(filename: str | None) -> str:
    """Derive a short display label from the uploaded filename."""
    if not filename:
        return "UPLOAD"
    base = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if "." in base:
        base = base.rsplit(".", 1)[0]
    base = base.strip()
    return base[:24] if base else "UPLOAD"


def _run_csv_single_asset(close, strategy: str, params: dict, label: str) -> BacktestResponse:
    """
    Validate params, generate signals, and build a unified BacktestResponse
    for an uploaded-CSV single-asset backtest.

    Mirrors the per-strategy yfinance endpoints exactly, but sources ``close``
    from the parsed CSV and derives the date range from its index.
    """
    if strategy == "pairs":
        raise HTTPException(
            status_code=422,
            detail="Pairs Trading is not supported for CSV upload (it requires two assets).",
        )

    model = _CSV_PARAM_MODELS.get(strategy)
    if model is None:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unknown strategy '{strategy}'. Supported CSV strategies: "
                f"{', '.join(_CSV_PARAM_MODELS)}."
            ),
        )

    # Ignore any identity fields a client may send — identity comes from the CSV.
    clean = {k: v for k, v in params.items() if k not in ("ticker", "start_date", "end_date")}
    try:
        req = model(**clean)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=_format_validation_error(exc)) from exc

    start_date = str(close.index[0].date())
    end_date = str(close.index[-1].date())
    n = len(close)

    common = dict(
        request_ticker=label,
        start_date=start_date,
        end_date=end_date,
        transaction_cost_bps=req.transaction_cost_bps,
        initial_capital=req.initial_capital,
        close=close,
    )

    if strategy == "sma_crossover":
        if req.fast_window >= req.slow_window:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"fast_window ({req.fast_window}) must be less than "
                    f"slow_window ({req.slow_window})."
                ),
            )
        min_bars = req.slow_window + 2
        if n < min_bars:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Only {n} rows available; need at least {min_bars} for a "
                    f"{req.slow_window}-day slow SMA."
                ),
            )
        position = sma_crossover_signals(
            close, fast_window=req.fast_window, slow_window=req.slow_window
        )
        return _build_response(
            **common,
            position=position,
            strategy="sma_crossover",
            fast_window=req.fast_window,
            slow_window=req.slow_window,
        )

    if strategy == "rsi_mean_reversion":
        min_bars = req.rsi_window + 5
        if n < min_bars:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Only {n} rows available; need at least {min_bars} for a "
                    f"{req.rsi_window}-period RSI."
                ),
            )
        position = rsi_mean_reversion_signals(
            close,
            rsi_window=req.rsi_window,
            oversold_threshold=req.oversold_threshold,
            exit_threshold=req.exit_threshold,
        )
        return _build_response(
            **common,
            position=position,
            strategy="rsi_mean_reversion",
            rsi_window=req.rsi_window,
            oversold_threshold=req.oversold_threshold,
            exit_threshold=req.exit_threshold,
        )

    if strategy == "bollinger_band":
        min_bars = req.bb_window + 5
        if n < min_bars:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Only {n} rows available; need at least {min_bars} for a "
                    f"{req.bb_window}-period Bollinger Band."
                ),
            )
        position = bollinger_band_signals(
            close,
            bb_window=req.bb_window,
            num_std=req.num_std,
            exit_band=req.exit_band,
        )
        return _build_response(
            **common,
            position=position,
            strategy="bollinger_band",
            bb_window=req.bb_window,
            bb_num_std=req.num_std,
            bb_exit_band=req.exit_band,
        )

    if strategy == "momentum":
        min_bars = req.momentum_window + 5
        if n < min_bars:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Only {n} rows available; need at least {min_bars} for a "
                    f"{req.momentum_window}-day momentum window."
                ),
            )
        position = momentum_signals(
            close,
            momentum_window=req.momentum_window,
            entry_threshold=req.entry_threshold,
            exit_threshold=req.exit_threshold,
        )
        return _build_response(
            **common,
            position=position,
            strategy="momentum",
            momentum_window=req.momentum_window,
            momentum_entry_threshold=req.entry_threshold,
            momentum_exit_threshold=req.exit_threshold,
        )

    # volatility_breakout (only remaining supported strategy)
    min_bars = max(req.lookback_window + 2, req.exit_window + 2)
    if n < min_bars:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Only {n} rows available; need at least {min_bars} for a "
                f"{req.lookback_window}-day lookback and {req.exit_window}-day exit mean."
            ),
        )
    position = volatility_breakout_signals(
        close,
        lookback_window=req.lookback_window,
        breakout_multiplier=req.breakout_multiplier,
        exit_window=req.exit_window,
    )
    return _build_response(
        **common,
        position=position,
        strategy="volatility_breakout",
        vb_lookback_window=req.lookback_window,
        vb_breakout_multiplier=req.breakout_multiplier,
        vb_exit_window=req.exit_window,
    )


@app.post(
    "/backtest/csv",
    response_model=BacktestResponse,
    tags=["backtest"],
    summary="Run a single-asset backtest on an uploaded CSV",
    description=(
        "Upload a historical price CSV and run one of the single-asset "
        "strategies (SMA Crossover, RSI Mean Reversion, Bollinger Band, "
        "Time-Series Momentum, Volatility Breakout) on it.\n\n"
        "The CSV must contain a date column (date / datetime / timestamp) and a "
        "close column (close / adj_close / adjusted_close). Optional OHLCV "
        "columns are ignored.  Strategy parameters are supplied as a JSON object "
        "in the `params` form field.  Pairs Trading is not supported."
    ),
)
async def backtest_csv(
    file: UploadFile = File(..., description="Historical price CSV file."),
    strategy: str = Form(..., description="Single-asset strategy identifier."),
    params: str = Form("{}", description="Strategy parameters as a JSON object."),
) -> BacktestResponse:
    raw = await file.read()
    if len(raw) > _MAX_CSV_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Uploaded file exceeds the {_MAX_CSV_BYTES // (1024 * 1024)} MB limit.",
        )

    try:
        close = parse_price_csv(raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        params_dict = json.loads(params) if params else {}
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=422, detail=f"params must be a valid JSON object: {exc}"
        ) from exc
    if not isinstance(params_dict, dict):
        raise HTTPException(status_code=422, detail="params must be a JSON object.")

    return _run_csv_single_asset(close, strategy, params_dict, _csv_label(file.filename))


# ---------------------------------------------------------------------------
# Custom Strategy Builder
# ---------------------------------------------------------------------------


@app.post(
    "/backtest/custom",
    response_model=BacktestResponse,
    tags=["backtest"],
    summary="Run a no-code custom rule-based strategy",
    description=(
        "Build a long-only, single-asset strategy from predefined technical "
        "indicator rules (SMA, RSI, Bollinger Bands, Momentum, close, and "
        "numeric constants).  The position enters when the entry rules hold "
        "(combined by `entry_logic`) and exits when the exit rules hold "
        "(combined by `exit_logic`).  Rules are evaluated with vectorised "
        "pandas operations — no user code is ever executed.  The position is "
        "shifted one bar forward to prevent lookahead bias."
    ),
)
def backtest_custom(request: CustomStrategyRequest) -> BacktestResponse:
    _validate_common(request.ticker, request.start_date, request.end_date)

    df = _fetch(request.ticker, request.start_date, request.end_date)
    close = df["Close"]

    # Warm-up: enough bars for the longest indicator window, +1 shift, +returns.
    max_window = max(
        required_window(request.entry_rules),
        required_window(request.exit_rules),
    )
    min_bars = max_window + 5
    if len(df) < min_bars:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Only {len(df)} trading days available; need at least "
                f"{min_bars} for the longest indicator window ({max_window})."
            ),
        )

    try:
        position = custom_strategy_signals(
            close,
            entry_rules=request.entry_rules,
            entry_logic=request.entry_logic,
            exit_rules=request.exit_rules,
            exit_logic=request.exit_logic,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return _build_response(
        request_ticker=request.ticker,
        start_date=request.start_date,
        end_date=request.end_date,
        transaction_cost_bps=request.transaction_cost_bps,
        initial_capital=request.initial_capital,
        close=close,
        position=position,
        strategy="custom",
    )


# ---------------------------------------------------------------------------
# Saved Custom Strategy Templates
# ---------------------------------------------------------------------------


@app.post(
    "/custom-strategies",
    response_model=CustomStrategyTemplateFull,
    tags=["custom-strategies"],
    summary="Save a reusable custom strategy template",
    description=(
        "Persist a reusable Custom Strategy Builder definition (entry/exit "
        "rules, combine logic, name, description, tags) to the local SQLite "
        "database.  Stores the definition only — never backtest results.  Rules "
        "are validated against the same whitelisted schema as the live builder; "
        "no user code is ever stored or executed."
    ),
)
def create_custom_strategy(
    request: CustomStrategyTemplateCreate,
) -> CustomStrategyTemplateFull:
    record = tpl_create(request.model_dump())
    return CustomStrategyTemplateFull(**record)


@app.get(
    "/custom-strategies",
    response_model=list[CustomStrategyTemplateSummary],
    tags=["custom-strategies"],
    summary="List saved custom strategy templates",
    description=(
        "Return all saved templates as lightweight summary rows (rule counts "
        "instead of full rule arrays), most recently updated first."
    ),
)
def list_custom_strategies() -> list[CustomStrategyTemplateSummary]:
    return [CustomStrategyTemplateSummary(**row) for row in tpl_list()]


@app.get(
    "/custom-strategies/{id}",
    response_model=CustomStrategyTemplateFull,
    tags=["custom-strategies"],
    summary="Get a full custom strategy template",
    description="Return the full template definition including all rules.",
)
def get_custom_strategy(id: int) -> CustomStrategyTemplateFull:
    record = tpl_get(id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Custom strategy template {id} not found."
        )
    return CustomStrategyTemplateFull(**record)


@app.put(
    "/custom-strategies/{id}",
    response_model=CustomStrategyTemplateFull,
    tags=["custom-strategies"],
    summary="Update a custom strategy template",
    description=(
        "Replace an existing template's rules, logic, and metadata.  Preserves "
        "the original created_at and refreshes updated_at."
    ),
)
def update_custom_strategy(
    id: int, request: CustomStrategyTemplateUpdate
) -> CustomStrategyTemplateFull:
    record = tpl_update(id, request.model_dump())
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Custom strategy template {id} not found."
        )
    return CustomStrategyTemplateFull(**record)


@app.delete(
    "/custom-strategies/{id}",
    response_model=DeleteResponse,
    tags=["custom-strategies"],
    summary="Delete a custom strategy template",
    description="Permanently delete a saved custom strategy template by id.",
)
def delete_custom_strategy(id: int) -> DeleteResponse:
    if not tpl_delete(id):
        raise HTTPException(
            status_code=404, detail=f"Custom strategy template {id} not found."
        )
    return DeleteResponse(deleted=True, id=id)


@app.get(
    "/custom-strategies/{id}/export",
    response_model=CustomStrategyTemplateExport,
    tags=["custom-strategies"],
    summary="Export a template as portable JSON",
    description=(
        "Return a portable, self-describing export of a saved template "
        "(schema_version + type markers + the reusable definition).  Local-only "
        "fields (id, created_at, updated_at) are intentionally excluded so the "
        "file is safe to share and re-import."
    ),
)
def export_custom_strategy(id: int) -> CustomStrategyTemplateExport:
    record = tpl_get(id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Custom strategy template {id} not found."
        )
    return CustomStrategyTemplateExport(
        name=record["name"],
        description=record["description"],
        entry_logic=record["entry_logic"],
        exit_logic=record["exit_logic"],
        entry_rules=record["entry_rules"],
        exit_rules=record["exit_rules"],
        tags=record["tags"],
    )


@app.post(
    "/custom-strategies/import",
    response_model=CustomStrategyTemplateFull,
    tags=["custom-strategies"],
    summary="Import a template from portable JSON",
    description=(
        "Validate a portable export envelope and persist it as a new saved "
        "template.  Reuses the exact whitelisted CustomRule schema as the live "
        "builder, so only known indicators/operators are accepted — no `eval`, "
        "no arbitrary code, max 10 entry / 10 exit rules.  A wrong `type`, "
        "missing `schema_version`, empty `name`, or invalid rule is rejected "
        "with 422."
    ),
)
def import_custom_strategy(
    request: CustomStrategyTemplateImport,
) -> CustomStrategyTemplateFull:
    # model_dump() carries the validated definition; tpl_create reads only the
    # fields it needs (envelope markers are ignored).
    record = tpl_create(request.model_dump())
    return CustomStrategyTemplateFull(**record)


# ---------------------------------------------------------------------------
# Strategy Template Gallery (built-in, read-only)
# ---------------------------------------------------------------------------


@app.get(
    "/custom-strategy-gallery",
    response_model=list[GalleryTemplate],
    tags=["custom-strategies"],
    summary="List built-in strategy gallery templates",
    description=(
        "Return the curated, read-only gallery of built-in custom strategy "
        "templates.  These are static, pre-validated rule definitions (not "
        "stored in SQLite and not backtest results).  Each can be loaded into "
        "the Custom Strategy Builder and optionally saved to local templates."
    ),
)
def get_strategy_gallery() -> list[GalleryTemplate]:
    return list_gallery()


@app.get(
    "/custom-strategy-gallery/{template_id}",
    response_model=GalleryTemplate,
    tags=["custom-strategies"],
    summary="Get one built-in gallery template",
    description="Return a single built-in gallery template by its slug id.",
)
def get_strategy_gallery_template(template_id: str) -> GalleryTemplate:
    template = get_gallery_template(template_id)
    if template is None:
        raise HTTPException(
            status_code=404, detail=f"Gallery template '{template_id}' not found."
        )
    return template
