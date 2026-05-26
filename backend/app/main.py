"""
QuantLab FastAPI application.

Endpoints
---------
GET  /health                          — liveness check
POST /backtest/sma-crossover          — run an SMA crossover backtest
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.backtest import run_backtest
from app.data import fetch_ohlcv
from app.metrics import compute_metrics
from app.schemas import (
    BacktestRequest,
    BacktestResponse,
    EquityPoint,
    PerformanceMetrics,
    TradeRecord,
)
from app.strategies import sma_crossover_signals
from app.utils import validate_date_format

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="QuantLab API",
    description=(
        "Quantitative backtesting engine — Phase 1 MVP.\n\n"
        "Implements a long-only SMA crossover strategy with transaction costs, "
        "a buy-and-hold benchmark, performance metrics, and a full trade log."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health", tags=["ops"])
def health_check():
    """Return a simple 200 OK to confirm the server is running."""
    return {"status": "ok", "version": "0.1.0"}


@app.post(
    "/backtest/sma-crossover",
    response_model=BacktestResponse,
    tags=["backtest"],
    summary="Run an SMA crossover backtest",
    description=(
        "Runs a long-only, fully-invested SMA crossover strategy on daily "
        "adjusted close prices from Yahoo Finance.  "
        "The signal is shifted by one day to prevent lookahead bias: "
        "the position for day T is determined by prices up to day T-1."
    ),
)
def backtest_sma_crossover(request: BacktestRequest) -> BacktestResponse:
    # ---- input validation --------------------------------------------------
    if not validate_date_format(request.start_date):
        raise HTTPException(status_code=422, detail="start_date must be YYYY-MM-DD.")
    if not validate_date_format(request.end_date):
        raise HTTPException(status_code=422, detail="end_date must be YYYY-MM-DD.")
    if request.start_date >= request.end_date:
        raise HTTPException(status_code=422, detail="start_date must be before end_date.")
    if request.fast_window >= request.slow_window:
        raise HTTPException(
            status_code=422,
            detail=f"fast_window ({request.fast_window}) must be less than "
                   f"slow_window ({request.slow_window}).",
        )

    # ---- fetch data --------------------------------------------------------
    try:
        df = fetch_ohlcv(request.ticker, request.start_date, request.end_date)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Data fetch failed: {exc}"
        ) from exc

    min_bars_needed = request.slow_window + 2  # +2 for the shift + one valid return
    if len(df) < min_bars_needed:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Only {len(df)} trading days available; need at least "
                f"{min_bars_needed} for a {request.slow_window}-day slow SMA."
            ),
        )

    close = df["Close"]

    # ---- strategy signals --------------------------------------------------
    position = sma_crossover_signals(
        close,
        fast_window=request.fast_window,
        slow_window=request.slow_window,
    )

    # ---- backtest ----------------------------------------------------------
    strategy_equity, benchmark_equity, trades = run_backtest(
        close=close,
        position=position,
        transaction_cost_bps=request.transaction_cost_bps,
        initial_capital=request.initial_capital,
    )

    # ---- metrics -----------------------------------------------------------
    strategy_metrics_dict = compute_metrics(strategy_equity)
    benchmark_metrics_dict = compute_metrics(benchmark_equity)

    # ---- build response ----------------------------------------------------
    equity_curve = [
        EquityPoint(
            date=str(d.date()) if hasattr(d, "date") else str(d),
            strategy=round(float(s), 2),
            benchmark=round(float(b), 2),
        )
        for d, s, b in zip(strategy_equity.index, strategy_equity, benchmark_equity)
    ]

    return BacktestResponse(
        ticker=request.ticker.upper(),
        start_date=request.start_date,
        end_date=request.end_date,
        fast_window=request.fast_window,
        slow_window=request.slow_window,
        transaction_cost_bps=request.transaction_cost_bps,
        initial_capital=request.initial_capital,
        strategy_metrics=PerformanceMetrics(**strategy_metrics_dict),
        benchmark_metrics=PerformanceMetrics(**benchmark_metrics_dict),
        equity_curve=equity_curve,
        trades=[TradeRecord(**t) for t in trades],
        num_trades=len(trades),
    )
