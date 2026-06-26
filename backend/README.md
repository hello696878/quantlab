# QuantLab Backend

A **correct** FastAPI backtesting and research engine for quantitative trading strategies.

---

## Architecture

```
backend/
├── app/
│   ├── __init__.py         package marker
│   ├── main.py             FastAPI app, routes, input validation
│   ├── schemas.py          Pydantic request / response models
│   ├── data.py             yfinance OHLCV download layer
│   ├── strategies.py       signal generation (lookahead-bias-free)
│   ├── backtest.py         vectorised backtest engine + transaction costs
│   ├── metrics.py          Sharpe, Sortino, CAGR, drawdown, Calmar, win-rate, …
│   ├── globe/              typed dossiers + optional FRED/delayed quote adapters
│   ├── globe_routes.py     read-only Global Markets Globe API routes
│   ├── portfolio_risk/     static-sample portfolio analytics (models/sample/service/factors/optimize/simulate)
│   ├── portfolio_risk_routes.py  Portfolio Risk Lab API routes
│   ├── real_estate/        static-sample real-estate analytics (models/sample/service/mbs)
│   ├── real_estate_routes.py     Real Estate Lab API routes
│   ├── futures/            static-sample futures/commodities analytics (models/sample/service)
│   ├── futures_routes.py         Futures & Commodities Lab API routes
│   ├── volatility/         static-sample vol-surface/variance-swap analytics (models/sample/service)
│   ├── volatility_routes.py      Volatility Lab API routes (reuses app/options BS)
│   ├── microstructure/     static-sample order-book/execution analytics (models/sample/service)
│   ├── microstructure_routes.py  Market Microstructure & Execution Lab API routes
│   └── utils.py            shared helpers
├── tests/
│   ├── test_metrics.py           unit tests for metrics
│   ├── test_strategies.py        signal shape / bias / economic behaviour tests
│   ├── test_backtest.py          equity curve, trades, benchmark tests
│   ├── test_api_sma.py           SMA crossover API integration tests
│   ├── test_api_rsi.py           RSI mean reversion API tests
│   ├── test_api_bb.py            Bollinger Band API tests
│   ├── test_api_momentum.py      Momentum API tests
│   ├── test_api_vb.py            Volatility Breakout API tests
│   ├── test_api_pairs.py         Pairs Trading API tests
│   ├── test_sma_sweep.py         SMA Parameter Sweep research tests
│   ├── test_sma_train_test.py    SMA Train/Test Validation research tests
│   ├── test_sma_walk_forward.py  SMA Walk-Forward Optimization research tests
│   ├── test_globe.py             dossier API/schema/FRED/quote adapter tests
│   ├── test_portfolio_risk.py    Portfolio Risk Lab analytics/API/validation tests
│   ├── test_real_estate.py       Real Estate Lab analytics/API/validation tests
│   ├── test_mbs.py               Mortgage & MBS prepayment analytics/API tests
│   ├── test_futures.py           Futures & Commodities Lab analytics/API tests
│   ├── test_volatility.py        Volatility Lab analytics/API/validation tests
│   └── test_microstructure.py    Market Microstructure & Execution Lab analytics/API/validation tests
├── pyproject.toml          pytest config (pythonpath, testpaths)
└── requirements.txt
```

---

## Setup

> **Prerequisite:** Python 3.11+ and a virtual environment activated.

```powershell
cd C:\quantlab

# activate the existing venv (Windows PowerShell)
.venv\Scripts\Activate.ps1

# install dependencies
pip install -r backend\requirements.txt
```

---

## Running the server

```powershell
cd C:\quantlab\backend
uvicorn app.main:app --reload --port 8000
```

The interactive API docs are available at:

- Swagger UI → http://localhost:8000/docs  
- ReDoc      → http://localhost:8000/redoc

---

## API Endpoints

### `GET /health`

Liveness check.

```json
{ "status": "ok", "version": "0.1.0" }
```

---

### Global Markets Globe Endpoints

These endpoints return a deterministic static illustrative core. An optional,
disabled-by-default FRED adapter can source selected US macro fields, and a
separate disabled-by-default yfinance adapter can enrich supported primary
index/FX rows with delayed quotes. All unsupported fields remain static. No
real-time market coverage is provided.

| Endpoint | Description |
|---|---|
| `GET /globe/markets` | All 15 typed sample market dossiers plus data status and notice |
| `GET /globe/markets/{market_id}` | One dossier; unknown ids return `404 Market not found.` |
| `GET /globe/regions` | Static market counts by region |

The FRED adapter is fail-closed and documents exact field/date provenance. It
never returns its API key. The delayed quote adapter also fails closed, requires
no API key, and never claims real-time data. The news adapter remains an inert
stub. See `docs/GLOBE_DATA.md` for local opt-in configuration and limitations.

---

### Portfolio Risk Lab Endpoints

Deterministic static-sample portfolio analytics (Phase 21.0). No live data, no
network calls, long-only by default, educational only — not investment advice.

| Endpoint | Description |
|---|---|
| `GET /portfolio-risk/sample` | Deterministic 8-asset sample portfolio (fixed-seed monthly return series, default risk-free rate, confidence, and stress scenario) |
| `POST /portfolio-risk/analyze` | Full analytics: normalized weights, expected return, volatility, Sharpe, covariance/correlation, marginal/component/percent risk contributions, historical VaR/CVaR (monthly), optional stress P&L, deterministic efficient frontier, minimum-variance and risk-parity portfolios, **factor exposure & risk decomposition** (9 illustrative factors, beta matrix, portfolio β=Bᵀw, factor + specific risk contributions), **deterministic scenario stress** (5 sample scenarios → asset/factor impact, worst/best asset; optional `custom_scenarios`), **constrained optimization** (`optimization_results`: long-only box-capped candidate search → max-Sharpe / min-variance / target-return / target-volatility / current / equal / risk-parity, optional `optimization_constraints`), **Black-Litterman** (`black_litterman`: implied equilibrium π=δΣw, sample views, posterior returns, BL-optimized portfolio), a **hypothetical rebalance** (`rebalance_analysis`: deltas + ½Σ\|Δ\| turnover), **Monte Carlo + bootstrap** (`monte_carlo` / `bootstrap_robustness`: fixed-seed wealth paths → terminal-wealth stats, probability of loss, drawdown-breach probability, simulated VaR/CVaR, fan chart, sample paths; optional `simulation_config`), **assumption sensitivity** (`assumption_sensitivity`: 8 ±return/vol/correlation/rate shifts), and **optimization robustness** (`optimization_robustness`: base/worst-case Sharpe, range, rank stability) |

Factor betas are deterministic illustrative values (Phase 21.1) — not estimated
from live data; factors are treated as orthogonal in v1. Scenarios are
educational sample shocks. Factor and specific percent risk contributions use the
variance-share convention and sum to 1. The optimizer (Phase 21.2) is a
deterministic long-only candidate search (no production solver); Black-Litterman
views are illustrative, not forecasts; rebalance deltas are hypothetical, not
trade orders. Infeasible target return/volatility returns a friendly note (no
crash). Monte Carlo / bootstrap (Phase 21.3) are **fixed-seed** simulations on
the illustrative sample data — deterministic for a given seed, **not forecasts**;
the bootstrap resamples daily-equivalent returns derived from the short monthly
sample series. Sensitivity/robustness scenarios are deterministic illustrative
assumption shifts.

Inputs are strictly validated (`extra="forbid"`, `FiniteFloat`): weights are
normalized, negative weights are rejected in long-only mode, volatility must be
> 0, confidence must be in `[0.5, 0.999]`, and no NaN/Infinity can enter or
leave. Every response carries `data_status = "static_sample"` and an educational
disclaimer.

---

### Real Estate Lab Endpoints

Deterministic static-sample income-property + REIT analytics (Phase 22.0). No live
property or REIT data, no network calls, educational only — not investment / tax /
legal / lending advice.

| Endpoint | Description |
|---|---|
| `GET /real-estate/sample` | Deterministic sample property + mortgage + REIT inputs |
| `POST /real-estate/analyze` | Full analytics: income statement (EGI/NOI), valuation (cap rate), mortgage amortization, LTV/DSCR, levered returns (cash-on-cash, IRR, equity multiple), six stress scenarios, and a simple REIT NAV discount/premium |
| `GET /real-estate/mbs/sample` | Deterministic sample agency MBS pool + prepayment + valuation inputs |
| `POST /real-estate/mbs/analyze` | Mortgage/MBS analytics: cash flows with CPR/SMM/PSA prepayments, MBS cash-flow decomposition, price, WAL, modified-duration/convexity approximations, and rate / prepayment-speed stress scenarios |

Inputs are strictly validated (`extra="forbid"`, `FiniteFloat`): purchase price
> 0, rent ≥ 0, vacancy ∈ [0,1], cap rate > 0, holding period > 0, no NaN/Infinity.
IRR is solved deterministically (sign-change bracketing + bisection) and returns
`null` with a note when it cannot be bracketed. The Mortgage & MBS endpoints
(Phase 22.1) use a simplified educational CPR→SMM and 100-PSA ramp; WAL,
duration, and convexity are educational approximations (duration/convexity hold
the projected cash flows fixed). No live mortgage rates or MBS prices.

---

### Futures & Commodities Lab Endpoints

Deterministic static-sample futures / commodities analytics (Phase 23.0). No live
futures or commodity prices, no network calls, educational only — not investment,
trading, legal, tax, or risk-management advice.

| Endpoint | Description |
|---|---|
| `GET /futures/sample` | Four deterministic sample commodities (crude oil, gold, natural gas, wheat) with futures curves + a sample position |
| `POST /futures/analyze` | Full analytics: cost-of-carry pricing, implied convenience yield, curve shape (contango/backwardation/mixed), basis, roll yield, calendar spread, notional / margin / leverage P&L, and eight commodity stress scenarios |

Inputs are strictly validated (`extra="forbid"`, `FiniteFloat`): spot > 0, futures
> 0, maturity > 0, multiplier > 0, margin rates ∈ [0,1] with initial ≥ maintenance,
no NaN/Infinity. Curve shape is classified deterministically from consecutive
observed futures.

---

### Volatility Surface & Variance Swap Lab Endpoints

Deterministic static-sample derivatives-volatility analytics (Phase 24.0). No live
option chains or market data, no network calls, educational only — not investment,
trading, legal, tax, or risk-management advice, and not official VIX / exchange
methodology.

| Endpoint | Description |
|---|---|
| `GET /volatility/sample` | Deterministic SPX-like sample option chain (Black-Scholes-generated mid prices) + sample positions |
| `POST /volatility/analyze` | Implied-vol inversion, smile / skew / term structure, 2-D surface, realized-vol comparison, simplified variance-swap fair strike, vega exposure, and eight volatility scenarios |

Reuses the Options Lab Black-Scholes (price / greeks / bisection IV solver). Inputs
are strictly validated (`extra="forbid"`, `FiniteFloat`): spot > 0, strike > 0,
maturity > 0, mid price > 0, no NaN/Infinity. The variance-swap fair strike is a
simplified educational option-strip approximation, **not** official VIX methodology;
an impossible/out-of-bounds price returns a null IV with a note (no crash).

---

### Market Microstructure & Execution Lab Endpoints

Deterministic static-sample market-microstructure / execution analytics (Phase 25.0).
No live order books or trades, no broker / exchange integration, no network calls,
educational only — not investment, trading, order-routing, legal, tax, or
risk-management advice, and not a production execution / TCA system.

| Endpoint | Description |
|---|---|
| `GET /microstructure/sample` | Four deterministic sample instruments (BTCUSDT, SPY, CL futures, TSM equity), each with a limit order book, trade tape, parent order, sample fills, and an intraday volume curve |
| `POST /microstructure/analyze` | Order-book summary (spread, depth ladder, top-of-book & 5-level imbalance, microprice), trade-tape VWAP / TWAP / trade imbalance, execution analytics (implementation shortfall, slippage, participation, square-root market impact), a four-schedule execution comparison (Immediate / TWAP / VWAP-style / participation-of-volume), eight liquidity stress scenarios, and **TCA / execution-cost attribution** (arrival/VWAP/TWAP benchmark shortfalls + spread / impact / timing / fees / residual decomposition reconciling to the realised arrival shortfall; optional `commission_per_unit`) |

Inputs are strictly validated (`extra="forbid"`, `FiniteFloat`): prices and sizes
> 0, no NaN/Infinity, a **crossed/locked book is rejected** (best_bid must be <
best_ask), and the trade side must be `buy`/`sell`. Implementation shortfall and
slippage are signed by side (a positive value is an execution cost); market impact
uses a square-root model with educational parameters. The schedule comparison and
liquidity scenarios are hypothetical educational examples — no schedule is
recommended, and nothing is order-routing advice. The **TCA attribution** splits
the realised arrival shortfall into spread / impact / timing / fees / residual
components that sum to the total by construction (deterministic, educational — not
execution, routing, or trading advice). Every division is guarded so all outputs
are finite.

---

### Backtest Endpoints

All backtest endpoints accept `POST` and return a unified `BacktestResponse` containing
`strategy_metrics`, `benchmark_metrics`, `equity_curve`, and `trades`.

| Endpoint | Strategy |
|---|---|
| `POST /backtest/sma-crossover` | Long-only SMA crossover |
| `POST /backtest/rsi-mean-reversion` | RSI mean reversion |
| `POST /backtest/bollinger-band` | Bollinger Band mean reversion |
| `POST /backtest/momentum` | Time-series momentum |
| `POST /backtest/volatility-breakout` | Volatility breakout |
| `POST /backtest/pairs` | Pairs trading (dollar-neutral) |

Common fields shared by all backtest requests:

| Field | Type | Default |
|---|---|---|
| `ticker` | string | `"SPY"` |
| `start_date` | string (YYYY-MM-DD) | `"2015-01-01"` |
| `end_date` | string (YYYY-MM-DD) | `"2023-12-31"` |
| `transaction_cost_bps` | float | `10.0` |
| `initial_capital` | float | `100000.0` |

---

### Research Endpoints

#### `POST /research/sma-parameter-sweep`

Runs every valid (fast < slow) combination of SMA windows over a single date range.
Returns a results table sorted by the best Sharpe ratio.

```json
{
  "ticker": "SPY",
  "start_date": "2015-01-01",
  "end_date": "2023-12-31",
  "fast_windows": [10, 20, 50],
  "slow_windows": [100, 150, 200],
  "transaction_cost_bps": 10.0,
  "initial_capital": 100000.0
}
```

Useful for identifying which parameter regions produce robust performance and
which are isolated hot-spots likely caused by overfitting.

---

#### `POST /research/sma-train-test`

Splits the date range at a `split_date` into in-sample (IS) and out-of-sample
(OOS) periods.  Runs a parameter sweep on IS data only, selects the best
(fast, slow) pair by `selection_metric`, then applies it to the OOS period.

```json
{
  "ticker": "SPY",
  "start_date": "2010-01-01",
  "split_date": "2018-01-01",
  "end_date": "2023-12-31",
  "fast_windows": [10, 20, 50],
  "slow_windows": [100, 150, 200],
  "selection_metric": "sharpe_ratio",
  "transaction_cost_bps": 10.0,
  "initial_capital": 100000.0
}
```

Returns IS metrics, OOS metrics, degradation statistics (`sharpe_degradation`,
`cagr_degradation`, `calmar_degradation`, `max_drawdown_worsening`), and a flag
`oos_collapsed` when OOS Sharpe is negative or less than 50 % of IS Sharpe.

---

#### `POST /research/strategy-comparison`

Runs five single-asset strategies on the same ticker and date range using
fixed default parameters, then returns per-strategy metrics, equity curves,
a benchmark, and a ranking.

```json
{
  "ticker": "SPY",
  "start_date": "2015-01-01",
  "end_date": "2023-12-31",
  "initial_capital": 100000.0,
  "transaction_cost_bps": 10.0
}
```

**Strategies included (fixed default parameters):**

| Strategy | Parameters |
|---|---|
| SMA Crossover | fast=20, slow=100 |
| RSI Mean Reversion | window=14, oversold=35, exit=55 |
| Bollinger Band | window=20, 1.8σ, exit=middle band |
| Momentum | window=63, entry/exit threshold=0 |
| Volatility Breakout | lookback=20, multiplier=0.3×, exit_window=10 |

**Pairs Trading is excluded** — it requires two tickers and cannot be compared on a single asset.

**Response includes:**

- `strategies` — per-strategy metrics, equity curve, and params for all five strategies
- `benchmark` — buy-and-hold benchmark equity curve
- `benchmark_metrics` — benchmark performance metrics
- `ranking` — display name of the best strategy by `best_by_sharpe`, `best_by_cagr`, `best_by_calmar`, and `lowest_drawdown`

**Limitations:**

- First version uses fixed default parameters; parameter customisation is not yet supported
- A single in-sample period is used — results are sensitive to the chosen date range
- Rankings should be validated out-of-sample before drawing any conclusions; use the Train/Test or Walk-Forward tools for that

---

#### `POST /research/sma-walk-forward`

Walk-forward optimization repeatedly advances a rolling training window across
the full date range.  In each step it:

1. Sweeps SMA parameters inside the training window (in-sample).
2. Selects the best (fast, slow) pair by `selection_metric`.
3. Applies that pair to the immediately following test window (out-of-sample).
4. Advances by `step_days` and repeats.

The out-of-sample results from all windows are stitched together (capital
chained) to form a realistic equity curve covering the entire period.

```json
{
  "ticker": "SPY",
  "start_date": "2010-01-01",
  "end_date": "2023-12-31",
  "train_window_days": 756,
  "test_window_days": 126,
  "step_days": 126,
  "fast_windows": [10, 20, 30, 50],
  "slow_windows": [100, 150, 200],
  "selection_metric": "sharpe_ratio",
  "transaction_cost_bps": 10.0,
  "initial_capital": 100000.0
}
```

| Field | Constraint | Default |
|---|---|---|
| `train_window_days` | ≥ 10 trading days | `756` (~3 years) |
| `test_window_days` | ≥ 5 trading days | `126` (~6 months) |
| `step_days` | ≥ 1 trading day | `126` |
| `fast_windows` | 1–10 values, each ≥ 2 | `[10,20,30,40,50]` |
| `slow_windows` | 1–10 values, each ≥ 2 | `[100,150,200,250]` |
| `selection_metric` | `sharpe_ratio` \| `cagr` \| `calmar_ratio` | `"sharpe_ratio"` |

**Response includes:**

- `windows` — per-window details (train/test dates, selected params, IS and OOS metrics)
- `stitched_equity_curve` — compounded OOS equity curve across all windows
- `aggregate_metrics` / `aggregate_benchmark_metrics` — performance over the full stitched period
- `parameter_stability` — how often the same (fast, slow) pair is selected:
  - `parameters_unstable = true` when no single pair wins more than 50 % of windows — a sign that the strategy may not have a stable edge

**Why walk-forward matters:**

A single train/test split can be lucky: the split date might happen to precede
a favourable regime for the selected parameters.  Walk-forward optimization
tests parameters on many non-overlapping OOS windows, reducing the chance that
any single window drives the conclusion.  Consistent OOS performance across
many windows is much stronger evidence of a genuine edge than a single OOS
period.

**Overfitting and unstable parameters:**

If `parameters_unstable` is `true`, the optimizer picks different parameter
pairs in different market regimes.  This is not necessarily wrong — regime
adaptation can be a feature — but it also means the strategy's behaviour is
hard to predict going forward.  Treat stable parameters as a weak positive
signal; treat unstable parameters as a reason for additional scrutiny.

---

## Running the tests

```powershell
cd C:\quantlab\backend
pytest
```

All tests use synthetic price series and make **no network calls**.

```powershell
# Verbose output for a specific test file
pytest tests/test_sma_walk_forward.py -v
pytest tests/test_sma_train_test.py -v
pytest tests/test_sma_sweep.py -v
```

---

## Correctness guarantees

| Risk | Mitigation |
|---|---|
| **Lookahead bias** | Signal from day T is shifted to become the position for day T+1 (`signal.shift(1)`) |
| **Data leakage in walk-forward** | Each test window starts strictly after the corresponding training window ends; test data is never seen during parameter selection |
| **Incorrect benchmark** | Benchmark is always 100 % long from day 1 with no transaction costs; benchmark capital is independently chained in walk-forward |
| **Wrong return calculation** | Uses `pct_change()` on adjusted close; tested against known values |
| **Transaction cost omission** | Costs charged on every position change (both entry and exit) |
| **Overfitting bias** | Walk-forward OOS stitching and parameter stability analysis make overfitting visible |

---

## Phase roadmap

- **Phase 0** ✅ Project scaffold, folder structure, clean repo
- **Phase 1** ✅ SMA crossover backtest engine
- **Phase 2** ✅ Additional strategies (RSI, Bollinger Bands, Momentum, Volatility Breakout, Pairs)
- **Phase 3** ✅ React + Recharts frontend
- **Phase 4** ✅ Research tools: SMA Parameter Sweep, Train/Test Validation, Walk-Forward Optimization, Strategy Comparison
- **Phase 4.5** ✅ Local SQLite saved backtests
- **Phase 5** 🔲 User accounts, CSV upload
