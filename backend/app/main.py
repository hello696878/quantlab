"""
QuantLab FastAPI application.

Endpoints
---------
GET  /health                          — liveness check
POST /backtest/sma-crossover          — run an SMA crossover backtest
POST /backtest/rsi-mean-reversion     — run an RSI mean-reversion backtest
POST /backtest/bollinger-band         — run a Bollinger Band mean-reversion backtest
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.backtest import run_backtest
from app.data import fetch_ohlcv
from app.metrics import compute_metrics
from app.schemas import (
    BacktestRequest,
    BacktestResponse,
    BbBacktestRequest,
    EquityPoint,
    PerformanceMetrics,
    RsiBacktestRequest,
    TradeRecord,
)
from app.strategies import (
    bollinger_band_signals,
    rsi_mean_reversion_signals,
    sma_crossover_signals,
)
from app.utils import validate_date_format

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="QuantLab API",
    description=(
        "Quantitative backtesting engine.\n\n"
        "Strategies: SMA Crossover, RSI Mean Reversion, Bollinger Band Mean Reversion.\n"
        "All strategies use a one-day signal shift to prevent lookahead bias."
    ),
    version="0.3.0",
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
        transaction_cost_bps=transaction_cost_bps,
        initial_capital=initial_capital,
        strategy_metrics=PerformanceMetrics(**strategy_metrics_dict),
        benchmark_metrics=PerformanceMetrics(**benchmark_metrics_dict),
        equity_curve=equity_curve,
        trades=[TradeRecord(**t) for t in trades],
        num_trades=len(trades),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health", tags=["ops"])
def health_check():
    """Return a simple 200 OK to confirm the server is running."""
    return {"status": "ok", "version": "0.3.0"}


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
