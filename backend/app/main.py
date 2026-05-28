"""
QuantLab FastAPI application.

Endpoints
---------
GET  /health                          — liveness check
POST /backtest/sma-crossover          — run an SMA crossover backtest
POST /backtest/rsi-mean-reversion     — run an RSI mean-reversion backtest
POST /backtest/bollinger-band         — run a Bollinger Band mean-reversion backtest
POST /backtest/momentum               — run a time-series momentum backtest
POST /backtest/volatility-breakout    — run a volatility breakout backtest
POST /backtest/pairs                  — run a pairs trading backtest
POST /research/sma-parameter-sweep   — sweep fast/slow SMA window combinations
POST /research/sma-train-test        — SMA train/test out-of-sample validation
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.backtest import run_backtest, run_pairs_backtest
from app.data import fetch_ohlcv, fetch_pairs_close
from app.metrics import compute_metrics
from app.schemas import (
    BacktestRequest,
    BacktestResponse,
    BbBacktestRequest,
    EquityPoint,
    MomentumBacktestRequest,
    PairsBacktestRequest,
    PerformanceMetrics,
    RsiBacktestRequest,
    SmaSweepRequest,
    SmaSweepResponse,
    SmaSweepRow,
    SmaTrainTestRequest,
    SmaTrainTestResponse,
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

app = FastAPI(
    title="QuantLab API",
    description=(
        "Quantitative backtesting engine.\n\n"
        "Strategies: SMA Crossover, RSI Mean Reversion, "
        "Bollinger Band Mean Reversion, Time-Series Momentum, "
        "Volatility Breakout, Pairs Trading.\n"
        "All strategies use a one-day signal shift to prevent lookahead bias."
    ),
    version="0.7.0",
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
