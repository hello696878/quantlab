"""
QuantLab FastAPI application.

Endpoints
---------
GET  /health                            — liveness check
GET  /globe/markets                     — list static sample market dossiers
GET  /globe/markets/{market_id}         — get one static sample market dossier
GET  /globe/regions                     — static sample market counts by region
POST /backtest/sma-crossover            — run an SMA crossover backtest
POST /backtest/rsi-mean-reversion       — run an RSI mean-reversion backtest
POST /backtest/bollinger-band           — run a Bollinger Band mean-reversion backtest
POST /backtest/momentum                 — run a time-series momentum backtest
POST /backtest/volatility-breakout      — run a volatility breakout backtest
POST /backtest/pairs                    — run a pairs trading backtest
POST /portfolio/backtest                — equal-weight multi-asset portfolio backtest
POST /portfolio/optimize                — optimize portfolio weights (min-vol / max-Sharpe)
POST /portfolio/walk-forward-optimize   — rolling out-of-sample portfolio optimization
POST /portfolio/efficient-frontier      — risk-return space of long-only portfolios
POST /portfolio/risk-dashboard          — asset/portfolio risk diagnostics
POST /portfolio/stress-test             — historical scenario / stress analysis
POST /portfolio/factor-analysis         — OLS factor-exposure regression
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

import hashlib
import json
from contextlib import asynccontextmanager
from datetime import date, timedelta
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from app.backtest import (
    compute_position_diagnostics,
    run_backtest,
    run_pairs_backtest,
)
from app.cost_model import resolve as resolve_cost_model
from app.position_sizing import (
    apply_sizing,
    average_exposure,
    resolve as resolve_position_sizing,
)
from app.risk_management import (
    apply_risk_management,
    diagnostics as risk_diagnostics,
    is_active as is_risk_active,
    resolve as resolve_risk_management,
)
from app.annualization import resolve_annualization
from app.market_data import assess_data_quality
from app.globe_routes import router as globe_router
from app.portfolio_risk_routes import router as portfolio_risk_router
from app.real_estate_routes import router as real_estate_router
from app.futures_routes import router as futures_router
from app.volatility_routes import router as volatility_router
from app.microstructure_routes import router as microstructure_router
from app.crypto_derivatives_routes import router as crypto_derivatives_router
from app.benchmark import (
    build_benchmark_analytics,
    compute_active_metrics,
    metrics_block as benchmark_metrics_block,
    normalize_config as normalize_benchmark_config,
)
from app.reproducibility import (
    build_reproducibility,
    normalize_backtest_config,
    normalize_comparison_config,
)
from app.robustness import build_robustness_report
from app.sensitivity import run_sensitivity_grid, unsupported_sensitivity
from app.options import (
    black_scholes_greeks,
    implied_volatility,
    strategy_payoff,
)
from app.options_tree import (
    TreeInputError,
    binomial_tree_price,
    compare_tree_to_black_scholes,
)
from app.options_monte_carlo import (
    MonteCarloInputError,
    price_monte_carlo,
)
from app.options_surface import (
    SurfaceInputError,
    build_sample_surface,
    build_surface,
)
from app.options_heston import (
    HestonInputError,
    price_heston_european_mc,
)
from app.event_study import (
    SAMPLE_EVENTS,
    EventInputError,
    compute_merger_arb_metrics,
    run_multi_event_study,
    run_single_event_study,
)
from app.yield_curve import (
    CurveInputError,
    bond_analytics,
    build_curve_analytics,
    generate_sample_yield_curve,
    shock_analytics,
)
from app.short_rates import (
    ShortRateInputError,
    run_short_rate_model,
)
from app.fx import (
    FxInputError,
    compute_currency_exposure,
    compute_fx_carry,
    compute_fx_forward,
    compute_ppp_deviation,
    price_garman_kohlhagen,
)
from app.credit import (
    CreditInputError,
    compute_cds_spread,
    compute_hazard_survival_curve,
    price_merton_credit,
    price_risky_bond,
)
from app.scanner import (
    ScannerInputError,
    run_scanner_backtest,
)
from app.finml import (
    FinmlInputError,
    run_labeling_demo,
    run_purged_cv_demo,
    run_sequential_bootstrap_demo,
    run_fractional_diff_demo,
)
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
    annualized_stats,
    buy_and_hold_equity,
    drawdown_series,
    efficient_frontier_points,
    factor_analysis,
    optimize_weights,
    portfolio_point,
    portfolio_stats,
    random_portfolios,
    risk_dashboard,
    run_equal_weight_portfolio,
    run_walk_forward_optimization,
    stress_test,
)
from app.strategy_gallery import get_gallery_template, list_gallery
from app.metrics import compute_metrics
from app.saved_backtests import (
    create_saved_backtest as db_create,
    delete_saved_backtest as db_delete,
    get_saved_backtest as db_get,
    list_saved_backtests as db_list,
)
from app.saved_reports import (
    create_saved_report as report_create,
    delete_saved_report as report_delete,
    get_saved_report as report_get,
    list_saved_reports as report_list,
    update_saved_report as report_update,
)
from app.schemas import (
    BacktestRequest,
    BacktestResponse,
    BbBacktestRequest,
    BenchmarkAnalytics,
    BenchmarkConfig,
    BlackScholesRequest,
    BlackScholesResponse,
    BinomialTreeRequest,
    BinomialTreeResponse,
    ImpliedVolRequest,
    ImpliedVolResponse,
    EventStudyRequest,
    EventStudyResponse,
    HestonRequest,
    HestonResponse,
    MergerArbRequest,
    MergerArbResponse,
    MonteCarloRequest,
    MonteCarloResponse,
    MultiEventStudyRequest,
    MultiEventStudyResponse,
    SampleEventsResponse,
    BondRequest,
    BondResponse,
    CurveRequest,
    CurveResponse,
    SampleCurveResponse,
    ShockRequest,
    ShockResponse,
    ShortRateRequest,
    ShortRateResponse,
    FxForwardRequest,
    FxForwardResponse,
    FxCarryRequest,
    FxCarryResponse,
    FxPppRequest,
    FxPppResponse,
    FxExposureRequest,
    FxExposureResponse,
    FxOptionRequest,
    FxOptionResponse,
    MertonRequest,
    MertonResponse,
    HazardRequest,
    HazardResponse,
    CdsRequest,
    CdsResponse,
    RiskyBondRequest,
    RiskyBondResponse,
    ScannerRequest,
    ScannerResponse,
    LabelingDemoRequest,
    LabelingDemoResponse,
    PurgedCvRequest,
    PurgedCvResponse,
    SequentialBootstrapRequest,
    SequentialBootstrapResponse,
    FractionalDiffRequest,
    FractionalDiffResponse,
    PayoffRequest,
    PayoffResponse,
    SampleSurfaceRequest,
    SurfaceRequest,
    SurfaceResponse,
    TreeConvergenceRequest,
    TreeConvergenceResponse,
    CostModel,
    PositionSizing,
    RiskManagement,
    RobustnessConfig,
    SensitivityConfig,
    CustomStrategyRequest,
    CustomStrategyTemplateCreate,
    CustomStrategyTemplateExport,
    CustomStrategyTemplateFull,
    CustomStrategyTemplateImport,
    CustomStrategyTemplateSummary,
    CustomStrategyTemplateUpdate,
    DeleteResponse,
    EfficientFrontierRequest,
    EfficientFrontierResponse,
    EquityPoint,
    FactorAnalysisRequest,
    FactorAnalysisResponse,
    FactorDiagnostics,
    FactorRegressionPoint,
    FrontierCurvePoint,
    FrontierPortfolioPoint,
    GalleryTemplate,
    PortfolioBacktestRequest,
    PortfolioBacktestResponse,
    PortfolioDrawdownPoint,
    PortfolioEquityPoint,
    PortfolioOptDrawdownPoint,
    PortfolioOptEquityPoint,
    PortfolioOptimizeRequest,
    PortfolioOptimizeResponse,
    PortfolioRebalanceEvent,
    PortfolioWalkForwardRequest,
    PortfolioWalkForwardResponse,
    PortfolioWalkForwardWindow,
    PortfolioWeightPoint,
    PortfolioWeightStability,
    CorrelationDiagnostics,
    EqualWeightRiskSummary,
    RiskDashboardRequest,
    RiskDashboardResponse,
    StressScenarioResult,
    StressTestRequest,
    StressTestResponse,
    MomentumBacktestRequest,
    PairsBacktestRequest,
    PerformanceMetrics,
    RsiBacktestRequest,
    SavedBacktestCreate,
    SavedBacktestFull,
    SavedBacktestSummary,
    SavedReportCreate,
    SavedReportFull,
    SavedReportSummary,
    SavedReportUpdate,
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

# Global Markets Globe data layer (Phase 20.2) — static sample dossier API.
app.include_router(globe_router)

# Portfolio Risk Lab (Phase 21.0) — static sample portfolio analytics API.
app.include_router(portfolio_risk_router)

# Real Estate Lab (Phase 22.0) — static sample property/REIT analytics API.
app.include_router(real_estate_router)

# Futures & Commodities Lab (Phase 23.0) — static sample futures analytics API.
app.include_router(futures_router)

# Volatility Surface & Variance Swap Lab (Phase 24.0) — static sample vol API.
app.include_router(volatility_router)

# Market Microstructure & Execution Lab (Phase 25.0) — static sample exec API.
app.include_router(microstructure_router)

# Crypto Perpetual Futures Funding & Basis Lab (Phase 26.0) — static sample API.
app.include_router(crypto_derivatives_router)


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
    position_mode: str = "long_only",
    cost_model: Optional[CostModel] = None,
    position_sizing: Optional[PositionSizing] = None,
    risk_management: Optional[RiskManagement] = None,
    annualization_mode: Optional[str] = None,
    data_provider: str = "yfinance",
    benchmark: Optional[BenchmarkConfig] = None,
    robustness: Optional[RobustnessConfig] = None,
    sensitivity: Optional[SensitivityConfig] = None,
) -> BacktestResponse:
    """Run backtest + metrics and assemble the unified response.

    When a ``cost_model`` is supplied it is resolved to an effective per-side
    bps value that feeds the engine and is reported as ``transaction_cost_bps``;
    the resolved breakdown is echoed on ``cost_model``.  With no ``cost_model``
    the behaviour is identical to before (``transaction_cost_bps`` is used).

    When ``position_sizing`` is supplied the position magnitude is scaled
    (signal timing / direction unchanged) before the engine runs; with no
    sizing (``full_allocation``) the position is used as-is.
    """
    cost_model_echo = None
    effective_cost_bps = transaction_cost_bps
    if cost_model is not None:
        resolved = resolve_cost_model(cost_model, transaction_cost_bps)
        effective_cost_bps = resolved.effective_bps_per_side
        cost_model_echo = resolved

    # Risk management runs first (signal → mode → risk → sizing → engine).  It
    # closes positions to cash on a stop/take/trailing/max-holding trigger; with
    # no rules (none/None) the position is returned untouched.
    risk_result = apply_risk_management(position, close, risk_management)
    risk_active = is_risk_active(risk_management)
    risk_management_echo = resolve_risk_management(risk_management)
    risk_diagnostics_obj = (
        risk_diagnostics(risk_result) if risk_active else None
    )

    # Position sizing scales exposure magnitude only.  Full / None is identity.
    sized_position = apply_sizing(risk_result.position, close, position_sizing)
    position_sizing_echo = resolve_position_sizing(position_sizing)
    avg_exposure = average_exposure(sized_position)

    # Attach trade reasons only when risk rules are active (preserves the old
    # trade shape — no `reason` key — for every existing backtest).
    change_reasons = risk_result.exit_reasons if risk_active else None
    strategy_equity, benchmark_equity, trades = run_backtest(
        close=close,
        position=sized_position,
        transaction_cost_bps=effective_cost_bps,
        initial_capital=initial_capital,
        position_change_reasons=change_reasons,
    )

    # Annualization convention — affects metric *scaling* only (252 = identical
    # to the historical default); never changes trades / equity / total return.
    annualization = resolve_annualization(request_ticker, annualization_mode)
    ppy = annualization.periods_per_year

    # Data-quality diagnostics observe the close series the engine actually
    # uses — informational only, results are unchanged.  yfinance Close is
    # auto-adjusted (splits/dividends) in data.fetch_ohlcv; CSV is as-uploaded.
    data_quality = assess_data_quality(
        close,
        ticker=request_ticker.upper(),
        requested_start_date=start_date,
        requested_end_date=end_date,
        provider=data_provider,
        adjusted=(data_provider == "yfinance"),
    )

    strategy_metrics_dict = compute_metrics(strategy_equity, periods_per_year=ppy)
    benchmark_metrics_dict = compute_metrics(benchmark_equity, periods_per_year=ppy)
    diagnostics = compute_position_diagnostics(close, sized_position, trades)

    # Cost transparency: total dollar cost paid, and the return given up to costs
    # (gross-of-cost minus net) via a cost-free run of the *same* position series.
    total_transaction_cost = round(
        float(sum(float(t.get("cost", 0.0)) for t in trades)), 2
    )
    gross_equity, _gross_bench, _gross_trades = run_backtest(
        close=close,
        position=sized_position,
        transaction_cost_bps=0.0,
        initial_capital=initial_capital,
    )
    gross_total_return = float(gross_equity.iloc[-1]) / float(initial_capital) - 1.0
    cost_drag_return = round(
        gross_total_return - float(strategy_metrics_dict["total_return"]), 6
    )

    # Benchmark / active analytics — observational only (never changes trades,
    # equity, or metrics).  Missing config normalizes to buy-and-hold same asset,
    # which reuses the engine's built-in costless benchmark (no refetch).
    bench_config = normalize_benchmark_config(benchmark)
    custom_close = None
    custom_fetch_error = None
    custom_provider = None
    custom_quality = None
    if bench_config.mode == "custom_ticker":
        bench_ticker = bench_config.ticker or ""
        if data_provider == "csv_upload":
            custom_fetch_error = (
                "Custom benchmark tickers are not supported for CSV backtests; "
                "use buy-and-hold of the uploaded series or no benchmark."
            )
        elif bench_ticker == request_ticker.upper():
            custom_close = close  # same asset — reuse, don't refetch
            custom_provider = data_provider
        else:
            try:
                custom_close = _fetch(bench_ticker, start_date, end_date)["Close"]
                custom_provider = "yfinance"
            except HTTPException as exc:
                custom_fetch_error = (
                    f"Benchmark '{bench_ticker}' could not be fetched: {exc.detail}"
                )
        if custom_close is not None:
            custom_quality = assess_data_quality(
                custom_close,
                ticker=bench_ticker,
                requested_start_date=start_date,
                requested_end_date=end_date,
                provider=custom_provider or "yfinance",
                adjusted=(custom_provider == "yfinance"),
            )
    benchmark_analytics = build_benchmark_analytics(
        config=bench_config,
        strategy_ticker=request_ticker,
        strategy_equity=strategy_equity,
        same_asset_benchmark_equity=benchmark_equity,
        periods_per_year=ppy,
        initial_capital=initial_capital,
        custom_close=custom_close,
        custom_fetch_error=custom_fetch_error,
        custom_data_provider=custom_provider,
        custom_data_quality=custom_quality,
    )

    # Robustness Lab — opt-in bootstrap on the realized daily strategy returns.
    # Never changes core results; disabled/missing config costs nothing.
    robustness_result = None
    if robustness is not None and robustness.enabled:
        bench_total_for_robustness = (
            benchmark_analytics.metrics.total_return
            if benchmark_analytics is not None and benchmark_analytics.metrics is not None
            else None
        )
        dq_warnings = (
            [
                "Data quality warnings exist; robustness analysis assumes the "
                "input return series is valid."
            ]
            if data_quality.warnings
            else []
        )
        robustness_result = build_robustness_report(
            strategy_equity.pct_change().dropna().to_numpy(),
            config=robustness,
            periods_per_year=ppy,
            benchmark_total_return=bench_total_for_robustness,
            extra_warnings=dq_warnings,
        )

    # Stability Lab — opt-in parameter-sensitivity sweep (SMA v1).  Re-runs the
    # same pipeline per grid cell; never changes the core backtest results.
    sensitivity_result = None
    if sensitivity is not None and sensitivity.enabled:
        if strategy == "sma_crossover" and fast_window and slow_window:
            try:
                sensitivity_result = run_sensitivity_grid(
                    close,
                    sensitivity,
                    current_fast=fast_window,
                    current_slow=slow_window,
                    position_mode=position_mode,
                    risk_management=risk_management,
                    position_sizing=position_sizing,
                    effective_cost_bps=effective_cost_bps,
                    initial_capital=initial_capital,
                    periods_per_year=ppy,
                )
            except ValueError as exc:  # oversized grid — reject safely
                raise HTTPException(status_code=422, detail=str(exc)) from exc
        else:
            sensitivity_result = unsupported_sensitivity(strategy, sensitivity)

    # Reproducible config hash — normalized, result-changing inputs only.
    # SMA windows use a 0 sentinel when not applicable; everything else is None.
    strategy_params = {
        k: v
        for k, v in {
            "fast_window": fast_window if fast_window else None,
            "slow_window": slow_window if slow_window else None,
            "rsi_window": rsi_window,
            "oversold_threshold": oversold_threshold,
            "exit_threshold": exit_threshold,
            "bb_window": bb_window,
            "bb_num_std": bb_num_std,
            "bb_exit_band": bb_exit_band,
            "momentum_window": momentum_window,
            "momentum_entry_threshold": momentum_entry_threshold,
            "momentum_exit_threshold": momentum_exit_threshold,
            "vb_lookback_window": vb_lookback_window,
            "vb_breakout_multiplier": vb_breakout_multiplier,
            "vb_exit_window": vb_exit_window,
        }.items()
        if v is not None
    }
    reproducibility = build_reproducibility(
        normalize_backtest_config(
            strategy=strategy,
            ticker=request_ticker,
            start_date=start_date,
            end_date=end_date,
            initial_capital=initial_capital,
            strategy_params=strategy_params,
            effective_cost_bps=effective_cost_bps,
            position_sizing=position_sizing,
            risk_management=risk_management,
            annualization_mode_used=annualization.mode_used,
            benchmark=benchmark,
            position_mode=position_mode,
            data_provider=data_provider,
            dataset_fingerprint=close.attrs.get("csv_content_sha256"),
        )
    )

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
        transaction_cost_bps=effective_cost_bps,
        initial_capital=initial_capital,
        cost_model=cost_model_echo,
        effective_cost_bps=effective_cost_bps,
        total_transaction_cost=total_transaction_cost,
        cost_drag_return=cost_drag_return,
        position_sizing=position_sizing_echo,
        average_exposure=avg_exposure,
        risk_management=risk_management_echo,
        risk_diagnostics=risk_diagnostics_obj,
        annualization_mode=annualization.mode,
        annualization_mode_used=annualization.mode_used,
        periods_per_year=annualization.periods_per_year,
        annualization_warning=annualization.warning,
        data_provider=data_provider,
        data_quality=data_quality,
        benchmark_analytics=benchmark_analytics,
        reproducibility=reproducibility,
        robustness=robustness_result,
        sensitivity=sensitivity_result,
        position_mode=position_mode,
        strategy_metrics=PerformanceMetrics(**strategy_metrics_dict),
        benchmark_metrics=PerformanceMetrics(**benchmark_metrics_dict),
        equity_curve=equity_curve,
        trades=[TradeRecord(**t) for t in trades],
        num_trades=len(trades),
        diagnostics=diagnostics,
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
        position_mode=request.position_mode,
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
        cost_model=request.cost_model,
        position_sizing=request.position_sizing,
        risk_management=request.risk_management,
        annualization_mode=request.annualization_mode,
        benchmark=request.benchmark,
        robustness=request.robustness,
        sensitivity=request.sensitivity,
        fast_window=request.fast_window,
        slow_window=request.slow_window,
        position_mode=request.position_mode,
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
        cost_model=request.cost_model,
        position_sizing=request.position_sizing,
        risk_management=request.risk_management,
        annualization_mode=request.annualization_mode,
        benchmark=request.benchmark,
        robustness=request.robustness,
        sensitivity=request.sensitivity,
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
        cost_model=request.cost_model,
        position_sizing=request.position_sizing,
        risk_management=request.risk_management,
        annualization_mode=request.annualization_mode,
        benchmark=request.benchmark,
        robustness=request.robustness,
        sensitivity=request.sensitivity,
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
        position_mode=request.position_mode,
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
        cost_model=request.cost_model,
        position_sizing=request.position_sizing,
        risk_management=request.risk_management,
        annualization_mode=request.annualization_mode,
        benchmark=request.benchmark,
        robustness=request.robustness,
        sensitivity=request.sensitivity,
        momentum_window=request.momentum_window,
        momentum_entry_threshold=request.entry_threshold,
        momentum_exit_threshold=request.exit_threshold,
        position_mode=request.position_mode,
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
        position_mode=request.position_mode,
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
        cost_model=request.cost_model,
        position_sizing=request.position_sizing,
        risk_management=request.risk_management,
        annualization_mode=request.annualization_mode,
        benchmark=request.benchmark,
        robustness=request.robustness,
        sensitivity=request.sensitivity,
        vb_lookback_window=request.lookback_window,
        vb_breakout_multiplier=request.breakout_multiplier,
        vb_exit_window=request.exit_window,
        position_mode=request.position_mode,
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

    # Resolve the cost model to an effective per-side bps (backward-compatible
    # when no cost_model is supplied).
    resolved_cost = resolve_cost_model(request.cost_model, request.transaction_cost_bps)
    effective_cost_bps = resolved_cost.effective_bps_per_side
    cost_model_echo = resolved_cost if request.cost_model is not None else None

    # Run the pairs-specific backtest engine.
    strategy_equity, benchmark_equity, trades = run_pairs_backtest(
        close_y=close_y,
        close_x=close_x,
        signal=signal,
        transaction_cost_bps=effective_cost_bps,
        initial_capital=request.initial_capital,
    )

    strategy_metrics_dict = compute_metrics(strategy_equity)
    benchmark_metrics_dict = compute_metrics(benchmark_equity)

    # Cost transparency (same as single-asset): total dollar cost + cost drag via
    # a cost-free run of the same signal.
    total_transaction_cost = round(
        float(sum(float(t.get("cost", 0.0)) for t in trades)), 2
    )
    gross_equity, _gb, _gt = run_pairs_backtest(
        close_y=close_y,
        close_x=close_x,
        signal=signal,
        transaction_cost_bps=0.0,
        initial_capital=request.initial_capital,
    )
    gross_total_return = (
        float(gross_equity.iloc[-1]) / float(request.initial_capital) - 1.0
    )
    cost_drag_return = round(
        gross_total_return - float(strategy_metrics_dict["total_return"]), 6
    )

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
        transaction_cost_bps=effective_cost_bps,
        initial_capital=request.initial_capital,
        cost_model=cost_model_echo,
        effective_cost_bps=effective_cost_bps,
        total_transaction_cost=total_transaction_cost,
        cost_drag_return=cost_drag_return,
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


@app.post(
    "/portfolio/optimize",
    response_model=PortfolioOptimizeResponse,
    tags=["portfolio"],
    summary="Optimize long-only portfolio weights (in-sample)",
    description=(
        "Optimize long-only, fully-invested weights (w_i >= 0, sum = 1) across "
        "the requested assets using historical returns, then backtest the "
        "optimized buy-and-hold portfolio against an equal-weight benchmark "
        "over the same period.\n\n"
        "Objectives: equal_weight, min_volatility (minimise w'Σw), max_sharpe "
        "(maximise (w'μ − rf)/√(w'Σw)).  Annualised with 252 trading days.\n\n"
        "**In-sample caveat:** weights are optimized AND backtested on the same "
        "date range.  This can overfit and does not predict future performance. "
        "Transaction costs are accepted for interface consistency, but v1 static "
        "optimization does not deduct one-time allocation or ongoing turnover "
        "costs. Not investment advice."
    ),
)
def portfolio_optimize(request: PortfolioOptimizeRequest) -> PortfolioOptimizeResponse:
    tickers = request.tickers  # cleaned/uppercased/deduped by the schema

    frames = {}
    for ticker in tickers:
        df = _fetch(ticker, request.start_date, request.end_date)
        frames[ticker] = df["Close"]

    prices = align_prices(frames)
    if len(prices) < 3:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Only {len(prices)} common trading day(s) across "
                f"{', '.join(tickers)}; need at least 3 to estimate returns and "
                "covariance.  Try a wider date range or assets with overlapping "
                "history."
            ),
        )

    try:
        expected_returns, covariance = annualized_stats(prices)
        weights = optimize_weights(
            expected_returns,
            covariance,
            objective=request.objective,
            risk_free_rate=request.risk_free_rate,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    equal_weights = {t: 1.0 / len(tickers) for t in tickers}

    # In-sample buy-and-hold backtests over the same period.
    try:
        optimized_equity = buy_and_hold_equity(prices, weights, request.initial_capital)
        equal_equity = buy_and_hold_equity(prices, equal_weights, request.initial_capital)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    opt_ret, opt_vol, opt_sharpe = portfolio_stats(
        weights, expected_returns, covariance, risk_free_rate=request.risk_free_rate
    )

    opt_dd = drawdown_series(optimized_equity)
    eq_dd = drawdown_series(equal_equity)

    def _d(ts) -> str:
        return str(ts.date()) if hasattr(ts, "date") else str(ts)

    equity_curve = [
        PortfolioOptEquityPoint(date=_d(d), value=round(float(v), 2))
        for d, v in zip(optimized_equity.index, optimized_equity)
    ]
    equal_weight_equity_curve = [
        PortfolioOptEquityPoint(date=_d(d), value=round(float(v), 2))
        for d, v in zip(equal_equity.index, equal_equity)
    ]
    drawdown = [
        PortfolioOptDrawdownPoint(
            date=_d(d), portfolio=round(float(p), 6), equal_weight=round(float(e), 6)
        )
        for d, p, e in zip(opt_dd.index, opt_dd, eq_dd)
    ]

    expected_returns_dict = {t: round(float(expected_returns[t]), 6) for t in tickers}
    covariance_dict = {
        ti: {tj: round(float(covariance.loc[ti, tj]), 8) for tj in tickers}
        for ti in tickers
    }

    return PortfolioOptimizeResponse(
        tickers=tickers,
        objective=request.objective,
        start_date=request.start_date,
        end_date=request.end_date,
        initial_capital=request.initial_capital,
        risk_free_rate=request.risk_free_rate,
        transaction_cost_bps=request.transaction_cost_bps,
        weights=weights,
        expected_returns=expected_returns_dict,
        covariance_matrix=covariance_dict,
        portfolio_expected_return=round(opt_ret, 6),
        portfolio_volatility=round(opt_vol, 6),
        portfolio_sharpe=round(opt_sharpe, 4),
        metrics=PerformanceMetrics(**compute_metrics(optimized_equity)),
        equal_weight_metrics=PerformanceMetrics(**compute_metrics(equal_equity)),
        equity_curve=equity_curve,
        equal_weight_equity_curve=equal_weight_equity_curve,
        drawdown=drawdown,
    )


@app.post(
    "/portfolio/walk-forward-optimize",
    response_model=PortfolioWalkForwardResponse,
    tags=["portfolio"],
    summary="Walk-forward (rolling, out-of-sample) portfolio optimization",
    description=(
        "Roll a training window forward, optimize long-only weights on each "
        "training slice, then apply those fixed weights to the following "
        "out-of-sample test window.  Test windows are stitched into one OOS "
        "equity curve and compared to an equal-weight benchmark rebalanced on "
        "the same boundaries.\n\n"
        "The optimizer only ever sees training data — no future test data leaks "
        "in.  Transaction cost is turnover-based at each window boundary "
        "(prev → new weights; entry turnover from cash for the first window) "
        "and is deducted from equity at the start of that test window.\n\n"
        "This reduces — but does not eliminate — overfitting versus the static "
        "in-sample optimizer.  Results still rely on historical assumptions and "
        "do not predict future performance.  Not investment advice."
    ),
)
def portfolio_walk_forward_optimize(
    request: PortfolioWalkForwardRequest,
) -> PortfolioWalkForwardResponse:
    tickers = request.tickers  # cleaned/uppercased/deduped by the schema

    frames = {}
    for ticker in tickers:
        df = _fetch(ticker, request.start_date, request.end_date)
        frames[ticker] = df["Close"]

    prices = align_prices(frames)

    try:
        result = run_walk_forward_optimization(
            prices,
            train_window_days=request.train_window_days,
            test_window_days=request.test_window_days,
            step_days=request.step_days,
            objective=request.objective,
            risk_free_rate=request.risk_free_rate,
            initial_capital=request.initial_capital,
            transaction_cost_bps=request.transaction_cost_bps,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    stitched = result.stitched_equity
    bench = result.benchmark_equity
    opt_dd = drawdown_series(stitched)
    bench_dd = drawdown_series(bench)

    def _d(ts) -> str:
        return str(ts.date()) if hasattr(ts, "date") else str(ts)

    windows = [
        PortfolioWalkForwardWindow(
            train_start_date=w["train_start_date"],
            train_end_date=w["train_end_date"],
            test_start_date=w["test_start_date"],
            test_end_date=w["test_end_date"],
            weights={t: round(float(v), 6) for t, v in w["weights"].items()},
            train_expected_return=round(w["train_expected_return"], 6),
            train_volatility=round(w["train_volatility"], 6),
            train_sharpe=round(w["train_sharpe"], 4),
            test_metrics=PerformanceMetrics(**w["test_metrics"]),
            turnover=round(w["turnover"], 6),
            transaction_cost=round(w["transaction_cost"], 2),
        )
        for w in result.windows
    ]

    stitched_equity_curve = [
        PortfolioOptEquityPoint(date=_d(d), value=round(float(v), 2))
        for d, v in zip(stitched.index, stitched)
    ]
    benchmark_equity_curve = [
        PortfolioOptEquityPoint(date=_d(d), value=round(float(v), 2))
        for d, v in zip(bench.index, bench)
    ]
    drawdown = [
        PortfolioDrawdownPoint(
            date=_d(d), portfolio=round(float(p), 6), benchmark=round(float(b), 6)
        )
        for d, p, b in zip(opt_dd.index, opt_dd, bench_dd)
    ]

    stab = result.weight_stability
    weight_stability = PortfolioWeightStability(
        average_turnover=round(stab["average_turnover"], 6),
        max_turnover=round(stab["max_turnover"], 6),
        average_weight_by_asset={t: round(v, 6) for t, v in stab["average_weight_by_asset"].items()},
        min_weight_by_asset={t: round(v, 6) for t, v in stab["min_weight_by_asset"].items()},
        max_weight_by_asset={t: round(v, 6) for t, v in stab["max_weight_by_asset"].items()},
    )

    return PortfolioWalkForwardResponse(
        tickers=tickers,
        objective=request.objective,
        start_date=request.start_date,
        end_date=request.end_date,
        train_window_days=request.train_window_days,
        test_window_days=request.test_window_days,
        step_days=request.step_days,
        risk_free_rate=request.risk_free_rate,
        initial_capital=request.initial_capital,
        transaction_cost_bps=request.transaction_cost_bps,
        num_windows=len(windows),
        windows=windows,
        stitched_equity_curve=stitched_equity_curve,
        benchmark_equity_curve=benchmark_equity_curve,
        drawdown=drawdown,
        metrics=PerformanceMetrics(**compute_metrics(stitched)),
        benchmark_metrics=PerformanceMetrics(**compute_metrics(bench)),
        weight_stability=weight_stability,
    )


@app.post(
    "/portfolio/efficient-frontier",
    response_model=EfficientFrontierResponse,
    tags=["portfolio"],
    summary="Efficient frontier — risk/return space of long-only portfolios",
    description=(
        "Estimate annualised expected returns and covariance from historical "
        "daily returns, then sample many random long-only portfolios "
        "(w_i >= 0, sum = 1) and locate the equal-weight, minimum-volatility, "
        "and maximum-Sharpe portfolios.  A long-only efficient-frontier curve "
        "(minimise volatility per target return) is also returned.\n\n"
        "**Historical / in-sample caveat:** expected returns and covariance are "
        "estimated from the selected window and may not persist.  This is "
        "descriptive analysis, not a forecast or investment advice."
    ),
)
def portfolio_efficient_frontier(
    request: EfficientFrontierRequest,
) -> EfficientFrontierResponse:
    tickers = request.tickers  # cleaned/uppercased/deduped by the schema

    frames = {}
    for ticker in tickers:
        df = _fetch(ticker, request.start_date, request.end_date)
        frames[ticker] = df["Close"]

    prices = align_prices(frames)
    if len(prices) < 3:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Only {len(prices)} common trading day(s) across "
                f"{', '.join(tickers)}; need at least 3 to estimate returns and "
                "covariance.  Try a wider date range or assets with overlapping "
                "history."
            ),
        )

    try:
        expected_returns, covariance = annualized_stats(prices)
        randoms = random_portfolios(
            expected_returns,
            covariance,
            request.num_portfolios,
            risk_free_rate=request.risk_free_rate,
            seed=42,
        )
        equal_w = optimize_weights(expected_returns, covariance, "equal_weight")
        min_vol_w = optimize_weights(expected_returns, covariance, "min_volatility")
        max_sharpe_w = optimize_weights(
            expected_returns, covariance, "max_sharpe", request.risk_free_rate
        )
        frontier = efficient_frontier_points(expected_returns, covariance, num_points=50)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    def _round_point(p: dict) -> FrontierPortfolioPoint:
        return FrontierPortfolioPoint(
            expected_return=round(p["expected_return"], 6),
            volatility=round(p["volatility"], 6),
            sharpe=round(p["sharpe"], 4),
            weights={t: round(float(v), 6) for t, v in p["weights"].items()},
        )

    rf = request.risk_free_rate
    return EfficientFrontierResponse(
        tickers=tickers,
        start_date=request.start_date,
        end_date=request.end_date,
        risk_free_rate=rf,
        num_portfolios=request.num_portfolios,
        expected_returns={t: round(float(expected_returns[t]), 6) for t in tickers},
        covariance_matrix={
            ti: {tj: round(float(covariance.loc[ti, tj]), 8) for tj in tickers}
            for ti in tickers
        },
        random_portfolios=[_round_point(p) for p in randoms],
        equal_weight=_round_point(portfolio_point(equal_w, expected_returns, covariance, rf)),
        min_volatility=_round_point(portfolio_point(min_vol_w, expected_returns, covariance, rf)),
        max_sharpe=_round_point(portfolio_point(max_sharpe_w, expected_returns, covariance, rf)),
        frontier_points=[
            FrontierCurvePoint(
                expected_return=round(p["expected_return"], 6),
                volatility=round(p["volatility"], 6),
            )
            for p in frontier
        ],
    )


@app.post(
    "/portfolio/risk-dashboard",
    response_model=RiskDashboardResponse,
    tags=["portfolio"],
    summary="Portfolio risk dashboard — correlations, diversification, risk contribution",
    description=(
        "Compute asset- and portfolio-level risk diagnostics from historical "
        "daily returns (252-day annualisation): per-asset annual return and "
        "volatility, the correlation and covariance matrices, equal-weight "
        "portfolio return/volatility and diversification ratio, correlation "
        "diagnostics (average / most / least correlated pairs), and the "
        "equal-weight percent risk contribution per asset.\n\n"
        "All statistics are historical estimates and may not persist "
        "out-of-sample.  Not investment advice."
    ),
)
def portfolio_risk_dashboard(request: RiskDashboardRequest) -> RiskDashboardResponse:
    tickers = request.tickers  # cleaned/uppercased/deduped by the schema

    frames = {}
    for ticker in tickers:
        df = _fetch(ticker, request.start_date, request.end_date)
        frames[ticker] = df["Close"]

    prices = align_prices(frames)
    if len(prices) < 3:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Only {len(prices)} common trading day(s) across "
                f"{', '.join(tickers)}; need at least 3 to estimate risk "
                "statistics.  Try a wider date range or assets with overlapping "
                "history."
            ),
        )

    try:
        d = risk_dashboard(prices)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    def _round_matrix(m: dict, ndigits: int) -> dict:
        return {ti: {tj: round(v, ndigits) for tj, v in row.items()} for ti, row in m.items()}

    return RiskDashboardResponse(
        tickers=tickers,
        start_date=request.start_date,
        end_date=request.end_date,
        asset_annual_returns={t: round(v, 6) for t, v in d["asset_annual_returns"].items()},
        asset_annual_volatilities={t: round(v, 6) for t, v in d["asset_annual_volatilities"].items()},
        correlation_matrix=_round_matrix(d["correlation_matrix"], 6),
        covariance_matrix=_round_matrix(d["covariance_matrix"], 8),
        equal_weight_portfolio=EqualWeightRiskSummary(
            expected_return=round(d["equal_weight_portfolio"]["expected_return"], 6),
            volatility=round(d["equal_weight_portfolio"]["volatility"], 6),
            diversification_ratio=round(d["equal_weight_portfolio"]["diversification_ratio"], 4),
            weights={t: round(v, 6) for t, v in d["equal_weight_portfolio"]["weights"].items()},
        ),
        correlation_diagnostics=CorrelationDiagnostics(
            average_pairwise_correlation=round(d["correlation_diagnostics"]["average_pairwise_correlation"], 6),
            max_pairwise_correlation=round(d["correlation_diagnostics"]["max_pairwise_correlation"], 6),
            min_pairwise_correlation=round(d["correlation_diagnostics"]["min_pairwise_correlation"], 6),
            most_correlated_pair=d["correlation_diagnostics"]["most_correlated_pair"],
            least_correlated_pair=d["correlation_diagnostics"]["least_correlated_pair"],
        ),
        risk_contribution={t: round(v, 6) for t, v in d["risk_contribution"].items()},
    )


@app.post(
    "/portfolio/stress-test",
    response_model=StressTestResponse,
    tags=["portfolio"],
    summary="Portfolio stress testing / historical scenario analysis",
    description=(
        "Evaluate how a static long-only portfolio (given or equal weights) "
        "would have moved through historical stress windows.  For each scenario "
        "the portfolio and benchmark returns are sliced, rebased to the initial "
        "capital, and summarised (total return, max drawdown, annualised "
        "volatility, worst/best day, excess vs benchmark, and the asset "
        "correlation matrix during the window).\n\n"
        "v1 uses static weights with no rebalancing or leverage.  Results are "
        "historical and do not guarantee or predict future behaviour.  Not "
        "investment advice."
    ),
)
def portfolio_stress_test(request: StressTestRequest) -> StressTestResponse:
    tickers = request.tickers  # cleaned/uppercased/deduped by the schema
    benchmark_ticker = request.benchmark_ticker

    # Fetch assets + benchmark and align everything on common dates.
    combined = {}
    for ticker in tickers:
        combined[ticker] = _fetch(ticker, request.start_date, request.end_date)["Close"]
    if benchmark_ticker not in combined:
        combined[benchmark_ticker] = _fetch(
            benchmark_ticker, request.start_date, request.end_date
        )["Close"]

    aligned = align_prices(combined)
    if len(aligned) < 3:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Only {len(aligned)} common trading day(s) across the assets "
                f"and benchmark; need at least 3.  Try a wider date range or "
                "assets with overlapping history."
            ),
        )

    prices = aligned[tickers]
    bench_close = aligned[benchmark_ticker]

    weights = request.weights or {t: 1.0 / len(tickers) for t in tickers}

    try:
        result = stress_test(
            prices,
            bench_close,
            weights,
            [s.model_dump() for s in request.scenarios],
            initial_capital=request.initial_capital,
            transaction_cost_bps=request.transaction_cost_bps,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    def _to_points(curve: list) -> list[PortfolioOptEquityPoint]:
        return [PortfolioOptEquityPoint(**p) for p in curve]

    scenarios = [
        StressScenarioResult(
            name=s["name"],
            start_date=s["start_date"],
            end_date=s["end_date"],
            total_return=round(s["total_return"], 6),
            max_drawdown=round(s["max_drawdown"], 6),
            annualized_volatility=round(s["annualized_volatility"], 6),
            worst_day_return=round(s["worst_day_return"], 6),
            best_day_return=round(s["best_day_return"], 6),
            benchmark_total_return=round(s["benchmark_total_return"], 6),
            benchmark_max_drawdown=round(s["benchmark_max_drawdown"], 6),
            benchmark_worst_day_return=round(s["benchmark_worst_day_return"], 6),
            benchmark_best_day_return=round(s["benchmark_best_day_return"], 6),
            excess_return=round(s["excess_return"], 6),
            correlation_matrix={
                ti: {tj: round(v, 6) for tj, v in row.items()}
                for ti, row in s["correlation_matrix"].items()
            },
            portfolio_equity_curve=_to_points(s["portfolio_equity_curve"]),
            benchmark_equity_curve=_to_points(s["benchmark_equity_curve"]),
        )
        for s in result["scenarios"]
    ]

    return StressTestResponse(
        tickers=tickers,
        weights={t: round(float(weights[t]), 6) for t in tickers},
        start_date=request.start_date,
        end_date=request.end_date,
        benchmark_ticker=benchmark_ticker,
        full_period_metrics=PerformanceMetrics(**result["full_period_metrics"]),
        benchmark_full_period_metrics=PerformanceMetrics(**result["benchmark_full_period_metrics"]),
        full_equity_curve=_to_points(result["full_equity_curve"]),
        benchmark_equity_curve=_to_points(result["benchmark_equity_curve"]),
        scenarios=scenarios,
    )


@app.post(
    "/portfolio/factor-analysis",
    response_model=FactorAnalysisResponse,
    tags=["portfolio"],
    summary="Factor exposure / OLS regression analysis",
    description=(
        "Regress a portfolio's daily returns on a set of factor ETF-proxy "
        "returns by ordinary least squares (intercept included):\n\n"
        "    r_p = alpha + Σ_k beta_k · r_factor_k + residual\n\n"
        "Returns alpha (daily + annualised), per-factor betas, R², annualised "
        "residual volatility, the factor correlation matrix, the actual-vs-"
        "fitted return series + equity curves, and diagnostics (strongest ± "
        "exposures, multicollinearity warning).\n\n"
        "Uses ETF proxies (not external Fama-French data) and is computed with "
        "NumPy least squares.  Exposures are historical and depend on the chosen "
        "proxies; collinear factors can make betas unstable.  Not investment "
        "advice."
    ),
)
def portfolio_factor_analysis(request: FactorAnalysisRequest) -> FactorAnalysisResponse:
    import pandas as pd

    tickers = request.tickers
    factor_names = list(request.factor_tickers.keys())
    factor_symbols = request.factor_tickers  # name → uppercased ticker

    # Fetch every distinct symbol (portfolio + factor proxies) once, then align.
    needed = set(tickers) | set(factor_symbols.values())
    closes: dict = {}
    for sym in needed:
        closes[sym] = _fetch(sym, request.start_date, request.end_date)["Close"]

    aligned = align_prices(closes)
    if len(aligned) < len(factor_names) + 3:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Only {len(aligned)} common trading day(s) across the portfolio "
                f"and factor proxies; need more than {len(factor_names) + 2} to "
                "fit the regression.  Widen the date range or reduce factors."
            ),
        )

    portfolio_prices = aligned[tickers]
    # Factor price columns in factor-name order (a proxy may equal a holding).
    factor_prices = pd.DataFrame(
        {name: aligned[factor_symbols[name]] for name in factor_names}
    )

    weights = request.weights or {t: 1.0 / len(tickers) for t in tickers}

    try:
        d = factor_analysis(
            portfolio_prices,
            factor_prices,
            weights,
            factor_names,
            initial_capital=request.initial_capital,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    def _pts(curve: list) -> list[PortfolioOptEquityPoint]:
        return [
            PortfolioOptEquityPoint(date=p["date"], value=round(float(p["value"]), 2))
            for p in curve
        ]

    return FactorAnalysisResponse(
        tickers=tickers,
        weights={t: round(float(weights[t]), 6) for t in tickers},
        start_date=request.start_date,
        end_date=request.end_date,
        factor_tickers=factor_symbols,
        alpha_daily=round(d["alpha_daily"], 8),
        alpha_annualized=round(d["alpha_annualized"], 6),
        betas={name: round(b, 6) for name, b in d["betas"].items()},
        r_squared=round(d["r_squared"], 6),
        residual_volatility=round(d["residual_volatility"], 6),
        factor_correlation_matrix={
            a: {b: round(v, 6) for b, v in row.items()}
            for a, row in d["factor_correlation_matrix"].items()
        },
        diagnostics=FactorDiagnostics(**d["diagnostics"]),
        regression_points=[
            FactorRegressionPoint(
                date=p["date"],
                actual_return=round(p["actual_return"], 8),
                fitted_return=round(p["fitted_return"], 8),
                residual=round(p["residual"], 8),
            )
            for p in d["regression_points"]
        ],
        actual_equity_curve=_pts(d["actual_equity_curve"]),
        fitted_equity_curve=_pts(d["fitted_equity_curve"]),
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
        "metrics.  Strategies: SMA Crossover (fast=20, slow=100), "
        "RSI Mean Reversion (window=14, OB=35, exit=55), "
        "Bollinger Band (window=20, 1.8σ, exit=middle), "
        "Momentum (window=63, thresholds=0), "
        "Volatility Breakout (lookback=20, mult=0.3, exit=10).  "
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

    # SMA 20/100 is the most restrictive demo default: needs slow + 2 = 102 bars.
    min_bars = 102
    if len(close) < min_bars:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Only {len(close)} trading days available; need at least "
                f"{min_bars} for strategy comparison "
                f"(SMA Crossover with slow=100 requires {min_bars} trading days)."
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
    warnings_global: list = []

    # Direction mode applies only to strategies that support it (SMA, Momentum,
    # Volatility Breakout); RSI and Bollinger always run long-only.
    cmp_mode = request.position_mode

    # Resolve the shared simulation controls once; they apply to *every* strategy
    # (signal → mode → risk → sizing → engine), exactly like a single backtest.
    resolved_cost = resolve_cost_model(request.cost_model, request.transaction_cost_bps)
    effective_cost_bps = resolved_cost.effective_bps_per_side
    risk_active = is_risk_active(request.risk_management)
    position_sizing_echo = resolve_position_sizing(request.position_sizing)
    risk_management_echo = resolve_risk_management(request.risk_management)

    # One annualization convention for the whole comparison (single ticker).
    annualization = resolve_annualization(request.ticker, request.annualization_mode)
    ppy = annualization.periods_per_year

    # One shared data fetch → one data-quality assessment for all strategies.
    data_quality = assess_data_quality(
        close,
        ticker=request.ticker.strip().upper(),
        requested_start_date=request.start_date,
        requested_end_date=request.end_date,
        provider="yfinance",
    )

    # Shared benchmark for the whole comparison (one reference for all five
    # strategies).  buy_and_hold_same_asset reuses the engine benchmark; a
    # custom ticker is fetched once and aligned to the shared close index.
    bench_config = normalize_benchmark_config(request.benchmark)
    custom_bench_equity = None
    custom_bench_error = None
    custom_bench_quality = None
    if bench_config.mode == "custom_ticker":
        bench_ticker = bench_config.ticker or ""
        custom_bench_close = None
        if bench_ticker == request.ticker.strip().upper():
            custom_bench_close = close
        else:
            try:
                raw_bench = _fetch(bench_ticker, request.start_date, request.end_date)["Close"]
                custom_bench_close = raw_bench[
                    (raw_bench.index >= start_ts) & (raw_bench.index <= end_ts)
                ]
            except HTTPException as exc:
                custom_bench_error = (
                    f"Benchmark '{bench_ticker}' could not be fetched: {exc.detail}"
                )
        if custom_bench_close is not None and len(custom_bench_close) > 0:
            custom_bench_quality = assess_data_quality(
                custom_bench_close,
                ticker=bench_ticker,
                requested_start_date=request.start_date,
                requested_end_date=request.end_date,
                provider="yfinance",
            )
            common_idx = close.index.intersection(custom_bench_close.index)
            if len(common_idx) >= 2:
                cb = custom_bench_close.loc[common_idx]
                custom_bench_equity = cb / float(cb.iloc[0]) * request.initial_capital
            else:
                custom_bench_error = (
                    f"Benchmark '{bench_ticker}' has no overlapping dates with the "
                    "comparison period; benchmark analytics are not computable."
                )

    def _run_strategy(raw_position):
        """Apply risk → sizing → engine to a raw signal (shared assumptions)."""
        nonlocal bench_eq
        risk_result = apply_risk_management(raw_position, close, request.risk_management)
        sized = apply_sizing(risk_result.position, close, request.position_sizing)
        eq, bench, trades = run_backtest(
            close=close,
            position=sized,
            transaction_cost_bps=effective_cost_bps,
            initial_capital=request.initial_capital,
            position_change_reasons=(risk_result.exit_reasons if risk_active else None),
        )
        if bench_eq is None:
            bench_eq = bench
        risk_exits = sum(risk_result.counts.values()) if risk_active else None
        return eq, trades, round(average_exposure(sized), 6), risk_exits

    def _reference_benchmark_equity():
        """The shared benchmark equity each strategy is measured against."""
        if bench_config.mode == "none":
            return None
        if bench_config.mode == "custom_ticker":
            return custom_bench_equity  # None when fetch/alignment failed
        return bench_eq  # buy-and-hold same asset (set by the first run)

    def _item(strategy, display_name, params, eq, trades, avg_exp, risk_exits,
              mode_used, unsupported):
        item_warnings = []
        if "position_mode" in unsupported:
            item_warnings.append("Does not support short modes — ran long-only.")
        ref_eq = _reference_benchmark_equity()
        active = (
            compute_active_metrics(eq, ref_eq, ppy)[0] if ref_eq is not None else None
        )
        return StrategyResultItem(
            strategy=strategy,
            display_name=display_name,
            params=params,
            position_mode=mode_used,
            metrics=PerformanceMetrics(**compute_metrics(eq, periods_per_year=ppy)),
            equity_curve=_curve(eq, bench_eq),
            num_trades=len(trades),
            average_exposure=avg_exp,
            risk_exit_count=risk_exits,
            effective_cost_bps=effective_cost_bps,
            unsupported_features=unsupported,
            warnings=item_warnings,
            active_metrics=active,
        )

    mode_unsupported = ["position_mode"] if cmp_mode != "long_only" else []

    # ── 1. SMA Crossover (fast=20, slow=100) ─────────────────────────────
    sma_pos = sma_crossover_signals(
        close, fast_window=20, slow_window=100, position_mode=cmp_mode
    )
    sma_eq, sma_trades, sma_exp, sma_risk = _run_strategy(sma_pos)
    results.append(_item(
        "sma_crossover", "SMA Crossover", {"fast_window": 20, "slow_window": 100},
        sma_eq, sma_trades, sma_exp, sma_risk, cmp_mode, [],
    ))

    # ── 2. RSI Mean Reversion (window=14, oversold=35, exit=55) — long-only ──
    rsi_pos = rsi_mean_reversion_signals(
        close, rsi_window=14, oversold_threshold=35.0, exit_threshold=55.0
    )
    rsi_eq, rsi_trades, rsi_exp, rsi_risk = _run_strategy(rsi_pos)
    results.append(_item(
        "rsi_mean_reversion", "RSI Mean Reversion",
        {"rsi_window": 14, "oversold_threshold": 35.0, "exit_threshold": 55.0},
        rsi_eq, rsi_trades, rsi_exp, rsi_risk, "long_only", mode_unsupported,
    ))

    # ── 3. Bollinger Band (window=20, 1.8σ, exit=middle) — long-only ─────
    bb_pos = bollinger_band_signals(
        close, bb_window=20, num_std=1.8, exit_band="middle"
    )
    bb_eq, bb_trades, bb_exp, bb_risk = _run_strategy(bb_pos)
    results.append(_item(
        "bollinger_band", "Bollinger Band",
        {"bb_window": 20, "num_std": 1.8, "exit_band": "middle"},
        bb_eq, bb_trades, bb_exp, bb_risk, "long_only", mode_unsupported,
    ))

    # ── 4. Momentum (window=63, entry=0, exit=0) ──────────────────────────
    mom_pos = momentum_signals(
        close, momentum_window=63, entry_threshold=0.0, exit_threshold=0.0,
        position_mode=cmp_mode,
    )
    mom_eq, mom_trades, mom_exp, mom_risk = _run_strategy(mom_pos)
    results.append(_item(
        "momentum", "Momentum",
        {"momentum_window": 63, "entry_threshold": 0.0, "exit_threshold": 0.0},
        mom_eq, mom_trades, mom_exp, mom_risk, cmp_mode, [],
    ))

    # ── 5. Volatility Breakout (lookback=20, mult=0.3, exit=10) ──────────
    vb_pos = volatility_breakout_signals(
        close, lookback_window=20, breakout_multiplier=0.3, exit_window=10,
        position_mode=cmp_mode,
    )
    vb_eq, vb_trades, vb_exp, vb_risk = _run_strategy(vb_pos)
    results.append(_item(
        "volatility_breakout", "Volatility Breakout",
        {"lookback_window": 20, "breakout_multiplier": 0.3, "exit_window": 10},
        vb_eq, vb_trades, vb_exp, vb_risk, cmp_mode, [],
    ))

    if cmp_mode != "long_only":
        warnings_global.append(
            "RSI Mean Reversion and Bollinger Band do not support short modes "
            "and ran long-only."
        )

    # ── Shared benchmark-analytics block (per-strategy active metrics live
    #    on each StrategyResultItem; this echoes the reference itself). ──────
    benchmark_analytics = None
    if bench_config.mode == "buy_and_hold_same_asset":
        benchmark_analytics = BenchmarkAnalytics(
            mode=bench_config.mode,
            ticker=request.ticker.strip().upper(),
            display_name=f"Buy & Hold {request.ticker.strip().upper()}",
            metrics=benchmark_metrics_block(bench_eq, ppy),
            warnings=[],
        )
    elif bench_config.mode == "custom_ticker":
        bench_ticker = bench_config.ticker or ""
        benchmark_analytics = BenchmarkAnalytics(
            mode=bench_config.mode,
            ticker=bench_ticker,
            display_name=f"Buy & Hold {bench_ticker}",
            metrics=(
                benchmark_metrics_block(custom_bench_equity, ppy)
                if custom_bench_equity is not None
                else None
            ),
            data_provider="yfinance" if custom_bench_equity is not None else None,
            data_quality=custom_bench_quality,
            warnings=[custom_bench_error] if custom_bench_error else [],
        )

    # Reproducible config hash for the whole comparison (shared settings; the
    # five strategies' demo-default parameters are fixed by the endpoint).
    comparison_reproducibility = build_reproducibility(
        normalize_comparison_config(
            ticker=request.ticker,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
            effective_cost_bps=effective_cost_bps,
            position_sizing=request.position_sizing,
            risk_management=request.risk_management,
            annualization_mode_used=annualization.mode_used,
            benchmark=request.benchmark,
            position_mode=request.position_mode,
            strategies=[item.strategy for item in results],
        )
    )

    # ── Benchmark metrics + curve ─────────────────────────────────────────
    bench_m = compute_metrics(bench_eq, periods_per_year=ppy)
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
        transaction_cost_bps=effective_cost_bps,
        position_mode=request.position_mode,
        cost_model=resolved_cost,
        effective_cost_bps=effective_cost_bps,
        position_sizing=position_sizing_echo,
        risk_management=risk_management_echo,
        warnings=warnings_global,
        annualization_mode=annualization.mode,
        annualization_mode_used=annualization.mode_used,
        periods_per_year=annualization.periods_per_year,
        annualization_warning=annualization.warning,
        data_provider="yfinance",
        data_quality=data_quality,
        benchmark_analytics=benchmark_analytics,
        reproducibility=comparison_reproducibility,
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
# Saved Reports (Report Gallery) endpoints
# ---------------------------------------------------------------------------


@app.post(
    "/saved-reports",
    response_model=SavedReportFull,
    tags=["saved-reports"],
    summary="Save a research report",
    description=(
        "Persist a generated research report (Markdown text + structured "
        "metadata) to the local SQLite database.  PDF binaries are never "
        "stored — PDF export remains a client-side browser-print operation.  "
        "Returns the saved record with its assigned ``id`` and timestamps."
    ),
)
def create_saved_report_endpoint(request: SavedReportCreate) -> SavedReportFull:
    record = report_create(request.model_dump())
    return SavedReportFull(**record)


@app.get(
    "/saved-reports",
    response_model=list[SavedReportSummary],
    tags=["saved-reports"],
    summary="List saved reports",
    description=(
        "Return all saved reports as lightweight summary rows (no Markdown "
        "content blob).  Ordered newest-first by creation timestamp."
    ),
)
def list_saved_reports_endpoint() -> list[SavedReportSummary]:
    return [SavedReportSummary(**row) for row in report_list()]


@app.get(
    "/saved-reports/{id}",
    response_model=SavedReportFull,
    tags=["saved-reports"],
    summary="Get a saved report",
    description="Return the full saved report including the Markdown content.",
)
def get_saved_report_endpoint(id: int) -> SavedReportFull:
    record = report_get(id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Saved report {id} not found.")
    return SavedReportFull(**record)


@app.put(
    "/saved-reports/{id}",
    response_model=SavedReportFull,
    tags=["saved-reports"],
    summary="Update a saved report",
    description=(
        "Update a saved report's mutable metadata (title, notes, metadata).  "
        "The Markdown content and source provenance are preserved; "
        "``updated_at`` is refreshed."
    ),
)
def update_saved_report_endpoint(
    id: int, request: SavedReportUpdate
) -> SavedReportFull:
    record = report_update(id, request.model_dump())
    if record is None:
        raise HTTPException(status_code=404, detail=f"Saved report {id} not found.")
    return SavedReportFull(**record)


@app.delete(
    "/saved-reports/{id}",
    response_model=DeleteResponse,
    tags=["saved-reports"],
    summary="Delete a saved report",
    description="Permanently delete a saved report by id.",
)
def delete_saved_report_endpoint(id: int) -> DeleteResponse:
    if not report_delete(id):
        raise HTTPException(status_code=404, detail=f"Saved report {id} not found.")
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
        cost_model=req.cost_model,
        position_sizing=req.position_sizing,
        risk_management=req.risk_management,
        annualization_mode=req.annualization_mode,
        data_provider="csv_upload",
        benchmark=req.benchmark,
        robustness=req.robustness,
        sensitivity=req.sensitivity,
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
            close,
            fast_window=req.fast_window,
            slow_window=req.slow_window,
            position_mode=req.position_mode,
        )
        return _build_response(
            **common,
            position=position,
            strategy="sma_crossover",
            fast_window=req.fast_window,
            slow_window=req.slow_window,
            position_mode=req.position_mode,
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
            position_mode=req.position_mode,
        )
        return _build_response(
            **common,
            position=position,
            strategy="momentum",
            momentum_window=req.momentum_window,
            momentum_entry_threshold=req.entry_threshold,
            momentum_exit_threshold=req.exit_threshold,
            position_mode=req.position_mode,
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
        position_mode=req.position_mode,
    )
    return _build_response(
        **common,
        position=position,
        strategy="volatility_breakout",
        vb_lookback_window=req.lookback_window,
        vb_breakout_multiplier=req.breakout_multiplier,
        vb_exit_window=req.exit_window,
        position_mode=req.position_mode,
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

    # Dataset fingerprint for the reproducibility hash: same CSV content →
    # same fingerprint; a different file with identical label/params changes
    # the config hash (config alone can't identify uploaded data).
    close.attrs["csv_content_sha256"] = hashlib.sha256(raw).hexdigest()

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


# ---------------------------------------------------------------------------
# Options & Volatility Lab endpoints (research v1 — deterministic, no chains)
# ---------------------------------------------------------------------------


@app.post(
    "/options/black-scholes",
    response_model=BlackScholesResponse,
    tags=["options"],
    summary="Price a European option (Black–Scholes) + Greeks",
    description=(
        "Educational European Black–Scholes pricing with continuous dividend "
        "yield. Returns price, delta, gamma, vega, annual + daily theta, rho, "
        "d1, d2. Simplified model — no American exercise, discrete dividends, "
        "smile/term-structure, costs, or liquidity."
    ),
)
def options_black_scholes(request: BlackScholesRequest) -> BlackScholesResponse:
    g = black_scholes_greeks(
        request.option_type,
        request.underlying_price,
        request.strike,
        request.time_to_expiry,
        request.risk_free_rate,
        request.volatility,
        request.dividend_yield,
    )
    return BlackScholesResponse(option_type=request.option_type, **g)


@app.post(
    "/options/implied-volatility",
    response_model=ImpliedVolResponse,
    tags=["options"],
    summary="Solve implied volatility (bisection)",
    description=(
        "Robust bisection solver for the Black–Scholes implied volatility. "
        "Prices outside the no-arbitrage bounds return a warning and "
        "converged=false rather than crashing."
    ),
)
def options_implied_volatility(request: ImpliedVolRequest) -> ImpliedVolResponse:
    iv, converged, iterations, warning = implied_volatility(
        request.option_type,
        request.market_price,
        request.underlying_price,
        request.strike,
        request.time_to_expiry,
        request.risk_free_rate,
        request.dividend_yield,
    )
    return ImpliedVolResponse(
        implied_volatility=iv,
        converged=converged,
        iterations=iterations,
        warning=warning,
    )


@app.post(
    "/options/payoff",
    response_model=PayoffResponse,
    tags=["options"],
    summary="Expiration payoff for a multi-leg options strategy",
    description=(
        "Expiration payoff curve for manually-entered legs (no live option "
        "chains). Returns bounded max profit / max loss (null when unbounded) "
        "and approximate breakevens interpolated from the sampled curve. "
        "Expiration payoff only — not path-dependent mark-to-market PnL."
    ),
)
def options_payoff(request: PayoffRequest) -> PayoffResponse:
    result = strategy_payoff(
        [leg.model_dump() for leg in request.legs],
        request.price_min,
        request.price_max,
        request.points,
    )
    return PayoffResponse(**result)


@app.post(
    "/options/binomial",
    response_model=BinomialTreeResponse,
    tags=["options"],
    summary="Price a European/American option on a CRR binomial tree",
    description=(
        "Cox-Ross-Rubinstein binomial lattice pricing for European and American "
        "options, with early-exercise diagnostics and Black-Scholes convergence. "
        "Educational numerical approximation — not a production options risk "
        "engine. European prices converge to Black-Scholes as steps grow; "
        "American exercise is handled by max(intrinsic, continuation) at each "
        "node. No discrete dividends, corporate actions, costs, or liquidity. "
        "The full node lattice is returned only for small trees (steps <= 6)."
    ),
)
def options_binomial(request: BinomialTreeRequest) -> BinomialTreeResponse:
    try:
        result = binomial_tree_price(
            request.option_type,
            request.exercise_style,
            request.underlying_price,
            request.strike,
            request.time_to_expiry,
            request.risk_free_rate,
            request.volatility,
            request.dividend_yield,
            request.steps,
            include_lattice=request.include_lattice,
        )
    except TreeInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return BinomialTreeResponse(**result)


@app.post(
    "/options/tree-convergence",
    response_model=TreeConvergenceResponse,
    tags=["options"],
    summary="Tree price vs Black-Scholes across step counts (convergence)",
    description=(
        "Prices the option on CRR binomial trees of several step counts and "
        "reports each price and its difference from Black-Scholes. For European "
        "options this shows convergence to Black-Scholes; for American options "
        "Black-Scholes is only a European reference (no early-exercise value)."
    ),
)
def options_tree_convergence(
    request: TreeConvergenceRequest,
) -> TreeConvergenceResponse:
    try:
        result = compare_tree_to_black_scholes(
            request.option_type,
            request.exercise_style,
            request.underlying_price,
            request.strike,
            request.time_to_expiry,
            request.risk_free_rate,
            request.volatility,
            request.dividend_yield,
            request.step_values,
        )
    except TreeInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return TreeConvergenceResponse(**result)


@app.post(
    "/options/monte-carlo",
    response_model=MonteCarloResponse,
    tags=["options"],
    summary="Monte Carlo option pricing (GBM; European / Asian / barrier)",
    description=(
        "Risk-neutral Geometric Brownian Motion Monte Carlo pricing for European, "
        "arithmetic-average Asian, and simple (discretely-monitored) barrier "
        "options. Reproducible via the seed; returns the price, standard error, a "
        "95% confidence interval, a European Black-Scholes reference where "
        "applicable, and a small capped path preview. Educational simulation with "
        "sampling error — not a fair value, not a production exotic-pricing engine. "
        "Constant-volatility GBM only; barrier monitoring is discrete."
    ),
)
def options_monte_carlo(request: MonteCarloRequest) -> MonteCarloResponse:
    try:
        result = price_monte_carlo(
            request.payoff_type,
            request.underlying_price,
            request.strike,
            request.time_to_expiry,
            request.risk_free_rate,
            request.volatility,
            request.dividend_yield,
            request.steps,
            request.simulations,
            request.seed,
            request.antithetic,
            request.barrier_price,
        )
    except MonteCarloInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return MonteCarloResponse(**result)


@app.post(
    "/options/surface",
    response_model=SurfaceResponse,
    tags=["options"],
    summary="Build an implied-volatility surface from a manual option chain",
    description=(
        "Extracts implied volatility per option row (reusing the bisection "
        "solver), builds a moneyness × expiry surface grid, smile / ATM term "
        "structure / skew summaries, and an optional per-expiry SVI research "
        "fit. Educational research tool — no live chains, not an arbitrage-free "
        "calibration. A row that fails to solve is kept with null IV and a "
        "warning rather than crashing the surface."
    ),
)
def options_surface(request: SurfaceRequest) -> SurfaceResponse:
    try:
        result = build_surface(
            request.underlying_price,
            request.risk_free_rate,
            request.dividend_yield,
            [row.model_dump() for row in request.rows],
            request.fit_svi,
        )
    except SurfaceInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return SurfaceResponse(**result)


@app.post(
    "/options/surface/sample",
    response_model=SurfaceResponse,
    tags=["options"],
    summary="Generate a synthetic option chain and build its IV surface",
    description=(
        "Generates a synthetic option chain from Black-Scholes plus a parametric "
        "skew/smile (no live data), then runs the same surface pipeline. Useful "
        "for exploring the smile, term structure, and SVI fit without supplying "
        "a chain."
    ),
)
def options_surface_sample(request: SampleSurfaceRequest) -> SurfaceResponse:
    try:
        result = build_sample_surface(
            request.underlying_price,
            request.risk_free_rate,
            request.dividend_yield,
            request.base_vol,
            request.skew,
            request.smile,
            request.term,
            request.fit_svi,
        )
    except SurfaceInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return SurfaceResponse(**result)


@app.post(
    "/options/heston",
    response_model=HestonResponse,
    tags=["options"],
    summary="Heston stochastic-volatility Monte Carlo pricing (European)",
    description=(
        "Prices European options under the Heston stochastic-volatility model via "
        "a full-truncation Euler Monte Carlo simulation. Returns the price, "
        "standard error, 95% confidence interval, a constant-volatility "
        "Black-Scholes reference (sqrt of long-run variance), variance/volatility "
        "path previews, and a Feller-condition diagnostic. Educational research "
        "model — Euler discretization is biased, results carry Monte Carlo error, "
        "and the model is not calibrated to any market surface."
    ),
)
def options_heston(request: HestonRequest) -> HestonResponse:
    try:
        result = price_heston_european_mc(
            request.option_type,
            request.underlying_price,
            request.strike,
            request.time_to_expiry,
            request.risk_free_rate,
            request.dividend_yield,
            request.initial_variance,
            request.long_run_variance,
            request.kappa,
            request.vol_of_vol,
            request.rho,
            request.steps,
            request.simulations,
            request.seed,
        )
    except HestonInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return HestonResponse(**result)


# ---------------------------------------------------------------------------
# Event-Driven / Arbitrage Lab endpoints (research v1)
# ---------------------------------------------------------------------------


def _event_close_series(
    ticker: str,
    event_date: str,
    estimation_window_days: int,
    pre_event_days: int,
    post_event_days: int,
):
    """Fetch a close-price series wide enough for the estimation + event window.

    Trading days are ~0.69 of calendar days, so we over-fetch with a buffer.
    """
    ev = date.fromisoformat(event_date)
    before_days = int((estimation_window_days + pre_event_days) * 1.7) + 45
    after_days = int(post_event_days * 1.7) + 15
    start = (ev - timedelta(days=before_days)).isoformat()
    end = (ev + timedelta(days=after_days + 1)).isoformat()  # yfinance end is exclusive
    return _fetch(ticker, start, end)["Close"].rename(ticker.upper())


@app.post(
    "/events/study",
    response_model=EventStudyResponse,
    tags=["events"],
    summary="Event study — benchmark-adjusted abnormal returns and CAR",
    description=(
        "Computes abnormal returns and the cumulative abnormal return (CAR) "
        "around an event date, using market-adjusted, mean-adjusted, or "
        "market-model baselines. Educational research diagnostic — results depend "
        "on the event date, benchmark choice, window size, leakage, confounding "
        "events, liquidity, and costs. Not a live event scanner or investment advice."
    ),
)
def events_study(request: EventStudyRequest) -> EventStudyResponse:
    asset_close = _event_close_series(
        request.ticker,
        request.event_date,
        request.estimation_window_days,
        request.pre_event_days,
        request.post_event_days,
    )
    benchmark_close = None
    bench_warning: Optional[str] = None
    try:
        benchmark_close = _event_close_series(
            request.benchmark_ticker,
            request.event_date,
            request.estimation_window_days,
            request.pre_event_days,
            request.post_event_days,
        )
    except HTTPException as exc:
        bench_warning = (
            f"Benchmark '{request.benchmark_ticker}' could not be fetched: {exc.detail}"
        )

    try:
        result = run_single_event_study(
            asset_close,
            benchmark_close,
            request.event_date,
            request.estimation_window_days,
            request.pre_event_days,
            request.post_event_days,
            request.model,
            request.event_name,
        )
    except EventInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    if bench_warning:
        result["warnings"].insert(0, bench_warning)
        result["summary"]["warnings"].insert(0, bench_warning)
    result["benchmark_ticker"] = request.benchmark_ticker.upper()
    return EventStudyResponse(**result)


@app.post(
    "/events/multi-study",
    response_model=MultiEventStudyResponse,
    tags=["events"],
    summary="Multi-event study — average abnormal return (AAR) and CAAR",
    description=(
        "Runs an event study for each event and averages abnormal returns by "
        "relative day (AAR / CAAR). A single failing event is recorded rather than "
        "aborting the batch. Educational research diagnostic."
    ),
)
def events_multi_study(request: MultiEventStudyRequest) -> MultiEventStudyResponse:
    results = []
    errors = []
    for ev in request.events:
        bench_ticker = ev.benchmark_ticker or request.benchmark_ticker
        try:
            asset_close = _event_close_series(
                ev.ticker, ev.event_date, request.estimation_window_days,
                request.pre_event_days, request.post_event_days,
            )
            try:
                bench_close = _event_close_series(
                    bench_ticker, ev.event_date, request.estimation_window_days,
                    request.pre_event_days, request.post_event_days,
                )
            except HTTPException:
                bench_close = None
            results.append(
                run_single_event_study(
                    asset_close, bench_close, ev.event_date,
                    request.estimation_window_days, request.pre_event_days,
                    request.post_event_days, request.model,
                    ev.event_name or ev.ticker,
                )
            )
        except (EventInputError, HTTPException) as exc:
            detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
            errors.append(
                {
                    "event_name": ev.event_name or ev.ticker,
                    "ticker": ev.ticker.upper(),
                    "actual_event_date": None,
                    "total_car": None,
                    "error": str(detail),
                }
            )

    if not results:
        raise HTTPException(
            status_code=422,
            detail="No events could be processed; check the tickers and dates.",
        )

    agg = run_multi_event_study(results)
    return MultiEventStudyResponse(
        event_count=len(request.events),
        per_event=agg["per_event"] + errors,
        aar_curve=agg["aar_curve"],
        average_total_car=agg["average_total_car"],
        warnings=(
            [f"{len(errors)} event(s) could not be processed; see per-event errors."]
            if errors
            else []
        ),
    )


@app.post(
    "/events/merger-arb",
    response_model=MergerArbResponse,
    tags=["events"],
    summary="Simplified merger-arbitrage calculator",
    description=(
        "Simplified expected-value merger-arb economics (spread, expected/annualized "
        "return, breakeven probability). Ignores borrow/financing costs, regulatory "
        "timing, competing bids, taxes, liquidity, and detailed deal terms — not a "
        "full merger-arbitrage model and not investment advice."
    ),
)
def events_merger_arb(request: MergerArbRequest) -> MergerArbResponse:
    try:
        result = compute_merger_arb_metrics(
            request.current_price,
            request.offer_price,
            request.downside_price,
            request.probability_close,
            request.expected_days_to_close,
        )
    except EventInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return MergerArbResponse(**result)


@app.get(
    "/events/sample",
    response_model=SampleEventsResponse,
    tags=["events"],
    summary="Sample (demo) events for the Event Lab",
)
def events_sample() -> SampleEventsResponse:
    return SampleEventsResponse(
        events=list(SAMPLE_EVENTS),
        note="Sample events are for demo workflow only. Verify event dates before research use.",
    )


# ---------------------------------------------------------------------------
# Yield Curve Lab endpoints (research v1)
# ---------------------------------------------------------------------------


@app.post(
    "/rates/curve",
    response_model=CurveResponse,
    tags=["rates"],
    summary="Yield curve analytics — discount factors and forward rates",
    description=(
        "Builds discount factors and (continuously-compounded) forward rates from "
        "a manual/synthetic zero curve under the chosen compounding convention. "
        "Educational fixed-income research — no live rates feed, no swap-curve "
        "bootstrapping. Results depend on curve construction, compounding, "
        "interpolation, and data quality."
    ),
)
def rates_curve(request: CurveRequest) -> CurveResponse:
    try:
        result = build_curve_analytics(
            [p.model_dump() for p in request.curve_points],
            request.compounding,
            request.interpolation,
        )
    except CurveInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return CurveResponse(**result)


@app.post(
    "/rates/shock",
    response_model=ShockResponse,
    tags=["rates"],
    summary="Educational yield-curve shocks (parallel / steepener / flattener / butterfly)",
    description=(
        "Applies a simple educational curve shock and returns the original vs "
        "shocked curve. Not a realistic scenario-generation model."
    ),
)
def rates_shock(request: ShockRequest) -> ShockResponse:
    try:
        result = shock_analytics(
            [p.model_dump() for p in request.curve_points],
            request.shock_type,
            request.shock_bps,
            request.compounding,
        )
    except CurveInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return ShockResponse(**result)


@app.post(
    "/rates/bond",
    response_model=BondResponse,
    tags=["rates"],
    summary="Simplified fixed-rate bond pricing + duration / convexity / DV01",
    description=(
        "Prices a fixed-rate bond from a yield to maturity or by discounting cash "
        "flows on a zero curve, with Macaulay/modified duration, DV01, and "
        "convexity. Simplified clean-price approximation — no accrued interest, "
        "day-count, or settlement conventions. Educational only, not a quote."
    ),
)
def rates_bond(request: BondRequest) -> BondResponse:
    try:
        result = bond_analytics(
            request.face_value,
            request.coupon_rate,
            request.maturity_years,
            request.coupon_frequency,
            request.pricing_mode,
            request.yield_to_maturity,
            [p.model_dump() for p in request.curve_points] if request.curve_points else None,
            request.compounding,
            request.interpolation,
        )
    except CurveInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return BondResponse(**result)


@app.get(
    "/rates/sample",
    response_model=SampleCurveResponse,
    tags=["rates"],
    summary="Synthetic sample yield curve for the Yield Curve Lab",
)
def rates_sample() -> SampleCurveResponse:
    return SampleCurveResponse(
        curve_points=generate_sample_yield_curve(),
        note="Synthetic sample curve for education — not current market data.",
    )


@app.post(
    "/rates/short-rate",
    response_model=ShortRateResponse,
    tags=["rates"],
    summary="Short-rate model simulation (Vasicek / CIR) + analytic zero-coupon price",
    description=(
        "Simulates a one-factor Vasicek or CIR short-rate model (risk-neutral, "
        "Euler scheme; CIR uses full truncation), returning summary diagnostics, a "
        "capped path preview, a terminal-rate distribution, and the closed-form "
        "zero-coupon bond price. Educational research only — simplified models, "
        "no live rates feed, no market calibration, no Hull-White. Results depend "
        "on the parameters, discretization, simulation count, and random seed."
    ),
)
def rates_short_rate(request: ShortRateRequest) -> ShortRateResponse:
    try:
        result = run_short_rate_model(
            request.model,
            request.initial_rate,
            request.long_run_rate,
            request.kappa,
            request.sigma,
            request.horizon_years,
            request.steps,
            request.simulations,
            request.seed,
        )
    except ShortRateInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return ShortRateResponse(**result)


# ---------------------------------------------------------------------------
# FX Lab endpoints (research v1)
# ---------------------------------------------------------------------------


@app.post(
    "/fx/forward",
    response_model=FxForwardResponse,
    tags=["fx"],
    summary="FX forward via covered interest rate parity",
    description=(
        "Theoretical forward rate from spot and the domestic/foreign interest "
        "differential (continuous or annual compounding). Quote convention: "
        "domestic currency per 1 unit of foreign. Educational — no live FX rates, "
        "ignores bid/ask, funding/transaction costs, and capital controls."
    ),
)
def fx_forward(request: FxForwardRequest) -> FxForwardResponse:
    try:
        result = compute_fx_forward(
            request.spot_rate,
            request.domestic_rate,
            request.foreign_rate,
            request.time_to_maturity,
            request.compounding,
        )
    except FxInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return FxForwardResponse(**result)


@app.post(
    "/fx/carry",
    response_model=FxCarryResponse,
    tags=["fx"],
    summary="Simplified FX carry decomposition",
    description=(
        "Decomposes an FX carry position into the interest differential and the "
        "expected spot move. Educational — carry is not free money; ignores "
        "funding/transaction costs and uses an assumed expected spot, not a forecast."
    ),
)
def fx_carry(request: FxCarryRequest) -> FxCarryResponse:
    try:
        result = compute_fx_carry(
            request.spot_rate,
            request.domestic_rate,
            request.foreign_rate,
            request.expected_spot,
            request.horizon_years,
            request.notional,
            request.direction,
        )
    except FxInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return FxCarryResponse(**result)


@app.post(
    "/fx/ppp",
    response_model=FxPppResponse,
    tags=["fx"],
    summary="Purchasing-power-parity (PPP) deviation",
    description=(
        "Relative PPP-implied spot and the deviation of the current spot from it. "
        "Educational — suggests relative valuation under simplified inputs, not a "
        "timing signal; sensitive to base period, basket, and data quality."
    ),
)
def fx_ppp(request: FxPppRequest) -> FxPppResponse:
    try:
        result = compute_ppp_deviation(
            request.current_spot,
            request.base_spot,
            request.domestic_price_index,
            request.foreign_price_index,
        )
    except FxInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return FxPppResponse(**result)


@app.post(
    "/fx/exposure",
    response_model=FxExposureResponse,
    tags=["fx"],
    summary="Currency exposure translation + symmetric stress",
    description=(
        "Translates currency exposures into a base currency and applies a uniform "
        "symmetric FX shock. Educational translation, not a covariance-based risk "
        "model; no live FX rates."
    ),
)
def fx_exposure(request: FxExposureRequest) -> FxExposureResponse:
    try:
        result = compute_currency_exposure(
            [e.model_dump() for e in request.exposures],
            request.base_currency,
            request.shock_pct,
        )
    except FxInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return FxExposureResponse(**result)


@app.post(
    "/fx/option",
    response_model=FxOptionResponse,
    tags=["fx"],
    summary="Garman-Kohlhagen FX option pricing + Greeks",
    description=(
        "Prices a European FX option with the Garman-Kohlhagen model "
        "(Black-Scholes with a foreign risk-free rate as the dividend yield), "
        "returning d1/d2, delta, gamma, vega, theta, and domestic/foreign rho. "
        "Constant volatility — no FX volatility surface. Educational only."
    ),
)
def fx_option(request: FxOptionRequest) -> FxOptionResponse:
    try:
        result = price_garman_kohlhagen(
            request.option_type,
            request.spot_rate,
            request.strike,
            request.domestic_rate,
            request.foreign_rate,
            request.volatility,
            request.time_to_expiry,
        )
    except FxInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return FxOptionResponse(**result)


# ---------------------------------------------------------------------------
# Credit Risk Lab endpoints (research v1)
# ---------------------------------------------------------------------------


@app.post(
    "/credit/merton",
    response_model=MertonResponse,
    tags=["credit"],
    summary="Merton structural credit model (equity as a call on assets)",
    description=(
        "Merton structural model: equity as a call on firm assets, implied debt "
        "value, distance to default, risk-neutral default probability, and credit "
        "spread. Educational — stylized single-debt structure, constant asset "
        "volatility, no live data, not investment advice."
    ),
)
def credit_merton(request: MertonRequest) -> MertonResponse:
    try:
        result = price_merton_credit(
            request.asset_value,
            request.debt_face_value,
            request.asset_volatility,
            request.risk_free_rate,
            request.time_to_maturity,
            request.recovery_rate,
            request.expected_asset_return,
        )
    except CreditInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return MertonResponse(**result)


@app.post(
    "/credit/hazard",
    response_model=HazardResponse,
    tags=["credit"],
    summary="Reduced-form constant-hazard survival / default curve",
    description=(
        "Constant-hazard reduced-form model: survival, cumulative default, "
        "expected loss, and risky discount factor over time, plus the credit-"
        "triangle CDS approximation. Educational — flat hazard, not calibrated."
    ),
)
def credit_hazard(request: HazardRequest) -> HazardResponse:
    try:
        result = compute_hazard_survival_curve(
            request.hazard_rate,
            request.recovery_rate,
            request.maturity_years,
            request.risk_free_rate,
        )
    except CreditInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return HazardResponse(**result)


@app.post(
    "/credit/cds",
    response_model=CdsResponse,
    tags=["credit"],
    summary="Simplified CDS par-spread calculator",
    description=(
        "Discrete protection-leg / premium-leg fair CDS par spread under a flat "
        "hazard rate. Educational approximation — no ISDA conventions, no "
        "accrual-on-default, no calibrated hazard term structure. Not a quote."
    ),
)
def credit_cds(request: CdsRequest) -> CdsResponse:
    try:
        result = compute_cds_spread(
            request.hazard_rate,
            request.recovery_rate,
            request.maturity_years,
            request.risk_free_rate,
            request.payment_frequency,
            request.notional,
        )
    except CreditInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return CdsResponse(**result)


@app.post(
    "/credit/risky-bond",
    response_model=RiskyBondResponse,
    tags=["credit"],
    summary="Reduced-form risky (defaultable) bond pricing + credit spread",
    description=(
        "Prices a fixed-coupon risky bond as survival-weighted promised cash "
        "flows plus a recovery leg under a flat hazard rate, with the risk-free "
        "price and a flat-yield credit spread. Educational — no liquidity/tax/"
        "optionality, not an OAS or a market quote."
    ),
)
def credit_risky_bond(request: RiskyBondRequest) -> RiskyBondResponse:
    try:
        result = price_risky_bond(
            request.face_value,
            request.coupon_rate,
            request.maturity_years,
            request.coupon_frequency,
            request.risk_free_rate,
            request.hazard_rate,
            request.recovery_rate,
        )
    except CreditInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return RiskyBondResponse(**result)


# ---------------------------------------------------------------------------
# Cross-Sectional Scanner Engine endpoints (research v1)
# ---------------------------------------------------------------------------


@app.post(
    "/scanner/backtest",
    response_model=ScannerResponse,
    tags=["scanner"],
    summary="Cross-sectional scanner backtest (rank → long/short baskets → P&L)",
    description=(
        "Portfolio-level cross-sectional engine: ranks a synthetic universe each "
        "rebalance date, forms dollar-neutral long/short baskets, and runs a "
        "lookahead-safe vectorized backtest net of turnover costs. Educational — "
        "synthetic sample universe, no live market data, no real-time scanning, "
        "not investment advice."
    ),
)
def scanner_backtest(request: ScannerRequest) -> ScannerResponse:
    try:
        result = run_scanner_backtest(
            request.strategy,
            request.n_assets,
            request.start_date,
            request.end_date,
            request.lookback_days,
            request.long_quantile,
            request.short_quantile,
            request.rebalance_frequency,
            request.gross_exposure,
            request.cost_bps,
            request.min_liquidity,
            request.seed,
        )
    except ScannerInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return ScannerResponse(**result)


# ---------------------------------------------------------------------------
# AFML Methodology Layer endpoints (research v1)
# ---------------------------------------------------------------------------


@app.post(
    "/finml/labeling-demo",
    response_model=LabelingDemoResponse,
    tags=["finml"],
    summary="AFML labeling demo (CUSUM events → triple-barrier labels → uniqueness)",
    description=(
        "Educational financial-ML labeling pipeline on a synthetic path: symmetric "
        "CUSUM event sampling, triple-barrier labeling, sample concurrency, and "
        "uniqueness weights. The separate Purged CV endpoint provides purged K-fold "
        "and embargo diagnostics. Not a trained model, no live data, no "
        "meta-labeling. Not investment advice."
    ),
)
def finml_labeling_demo(request: LabelingDemoRequest) -> LabelingDemoResponse:
    try:
        result = run_labeling_demo(
            request.n_days,
            request.start_price,
            request.drift,
            request.volatility,
            request.seed,
            request.cusum_threshold,
            request.threshold_mode,
            request.volatility_window,
            request.profit_take_multiple,
            request.stop_loss_multiple,
            request.vertical_barrier_days,
        )
    except FinmlInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return LabelingDemoResponse(**result)


@app.post(
    "/finml/purged-cv-demo",
    response_model=PurgedCvResponse,
    tags=["finml"],
    summary="Purged K-Fold + embargo cross-validation demo (leakage diagnostics)",
    description=(
        "Builds triple-barrier labels on a synthetic path, then forms purged "
        "K-fold splits with an embargo and reports per-fold leakage diagnostics "
        "(overlap before vs after purging). Educational methodology — not CPCV, "
        "not model training, no live data. Purged CV reduces overlap leakage but "
        "does not guarantee a good model. Not investment advice."
    ),
)
def finml_purged_cv_demo(request: PurgedCvRequest) -> PurgedCvResponse:
    try:
        result = run_purged_cv_demo(
            request.n_days,
            request.start_price,
            request.drift,
            request.volatility,
            request.seed,
            request.cusum_threshold,
            request.threshold_mode,
            request.volatility_window,
            request.profit_take_multiple,
            request.stop_loss_multiple,
            request.vertical_barrier_days,
            request.n_splits,
            request.embargo_pct,
        )
    except FinmlInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return PurgedCvResponse(**result)


@app.post(
    "/finml/sequential-bootstrap-demo",
    response_model=SequentialBootstrapResponse,
    tags=["finml"],
    summary="Sequential bootstrap demo (uniqueness-aware sampling vs random)",
    description=(
        "Builds triple-barrier labels on a synthetic path, then draws a sequential "
        "bootstrap sample (events chosen with probability proportional to marginal "
        "average uniqueness) and compares its uniqueness to a random-bootstrap "
        "baseline. Educational methodology — reduces sample dependence but does not "
        "guarantee a better model. No live data, not investment advice."
    ),
)
def finml_sequential_bootstrap_demo(request: SequentialBootstrapRequest) -> SequentialBootstrapResponse:
    try:
        result = run_sequential_bootstrap_demo(
            request.n_days,
            request.start_price,
            request.drift,
            request.volatility,
            request.seed,
            request.cusum_threshold,
            request.threshold_mode,
            request.volatility_window,
            request.profit_take_multiple,
            request.stop_loss_multiple,
            request.vertical_barrier_days,
            request.sample_size,
            request.random_trials,
            request.with_replacement,
        )
    except FinmlInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return SequentialBootstrapResponse(**result)


@app.post(
    "/finml/fractional-diff-demo",
    response_model=FractionalDiffResponse,
    tags=["finml"],
    summary="Fractional differentiation demo (memory and persistence diagnostics)",
    description=(
        "Fixed-width fractional differentiation of a synthetic price path: recursive "
        "weights, the transformed series vs the ordinary first difference, memory-"
        "retention correlations, and heuristic persistence/stability diagnostics. "
        "Educational preprocessing — not a trading signal, not a formal stationarity "
        "test, no live data, not investment advice."
    ),
)
def finml_fractional_diff_demo(request: FractionalDiffRequest) -> FractionalDiffResponse:
    try:
        result = run_fractional_diff_demo(
            request.n_days,
            request.start_price,
            request.drift,
            request.volatility,
            request.seed,
            request.d,
            request.weight_threshold,
            request.max_weights,
        )
    except FinmlInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return FractionalDiffResponse(**result)
