# QuantLab — Project Overview

## Purpose

QuantLab is a **local-first** interactive quantitative research and backtesting platform, built for education and research — not live trading and not investment advice.

The goal is to let users explore trading strategies, understand their mathematical logic, tune parameters, and evaluate performance on real historical data — all through a clean web interface with no lookahead bias.

This document describes the system architecture, module responsibilities, and the flow of data from a browser request through to a backtest result.

> **Direction:** future development follows [Master Blueprint v3](MASTER_BLUEPRINT_V3.md) (long-term model catalog + platform trust features) via the phased plan in [ROADMAP.md](ROADMAP.md). The blueprint is a direction, not a feature list — only items labelled "built" exist today.

---

## System Architecture

```
Browser
  │
  │  http://localhost:3000
  ▼
Next.js Frontend (App Router)
  │  Command Center · Backtest · Strategy Library · Paper Replications
  │  Quant Disasters · CSV · Strategy Builder · Portfolio Lab · Research tools
  │  Saved Backtests/Reports · Settings
  │  Command palette (Ctrl/Cmd+K) · global search · toasts · error boundary
  │  EquityCurveChart · DrawdownChart · MetricsGrid · TradeTable (neon charts)
  │
  │  /api/*  (proxied via next.config.js rewrites → internal Docker DNS)
  ▼
FastAPI Backend
  │
  ├── main.py                       Route handlers, validation, response assembly
  ├── data.py                       yfinance OHLCV fetch and alignment
  ├── strategies.py                 Signal generation (all strategies, all shift by 1 day)
  ├── backtest.py                   Vectorised P&L engine, trade log, benchmark, long/short
  ├── custom_strategy.py            No-code rule evaluation (whitelisted operands, no eval)
  ├── portfolio.py                  Equal-weight, optimization, walk-forward, frontier, risk, stress, factor
  ├── metrics.py                    Performance statistics from an equity curve
  ├── cost_model.py                 Transaction-cost model resolution (simple/commission/conservative)
  ├── position_sizing.py            Exposure scaling (full/fraction/vol-target/cap, no leverage)
  ├── risk_management.py            Stop/take/trailing/max-holding exits (close-to-cash overlay)
  ├── annualization.py              252/365/auto metric-scaling convention
  ├── market_data.py                Provider abstraction + data-quality diagnostics
  ├── benchmark.py                  Benchmark + active metrics (alpha/beta/TE/IR) on aligned returns
  ├── reproducibility.py            Canonical config normalization + SHA-256 config hash
  ├── robustness.py                 Robustness Lab v1: block-bootstrap Monte Carlo + heuristic grade
  ├── sensitivity.py                Stability Lab v1: SMA parameter-sensitivity sweep + stability score
  ├── db.py                         SQLite connection + schema initialisation
  ├── saved_backtests.py            Saved-backtest CRUD
  ├── saved_reports.py              Saved-report CRUD
  ├── custom_strategy_templates.py  Saved custom-strategy CRUD + import/export
  ├── strategy_gallery.py           Built-in template gallery (static, validated)
  ├── schemas.py                    Pydantic v2 request / response models
  └── utils.py                      Date format validation helpers
```

---

## Backend Modules

### `data.py` — Data Layer

Downloads OHLCV data via yfinance and returns a cleaned DataFrame.

- `fetch_ohlcv(ticker, start, end)` — single-asset daily close
- `fetch_pairs_close(asset_y, asset_x, start, end)` — two-asset close series, inner-joined on shared trading days

Returns adjusted close prices. Raises `ValueError` when the ticker is invalid or no data is returned.

---

### `strategies.py` — Signal Generation

Each function takes a `pd.Series` of closing prices and returns a `pd.Series` of integer positions.

**Lookahead-bias rule:** every signal series is shifted forward by one bar with `.shift(1).fillna(0)` before being returned. This means the position on day T is determined by day T−1's signal — the strategy never "sees" today's close before deciding today's position.

| Function | Position values | Logic |
|---|---|---|
| `sma_crossover_signals` | 0 / 1 (or -1 / 0 / 1 with direction modes) | Long when fast SMA > slow SMA |
| `rsi_mean_reversion_signals` | 0 or 1 | Enter when RSI < oversold; exit when RSI > exit threshold |
| `bollinger_band_signals` | 0 or 1 | Enter when close < lower band; exit at middle or upper band |
| `momentum_signals` | 0 / 1 (or -1 / 0 / 1 with direction modes) | Enter when trailing N-day return > entry threshold |
| `volatility_breakout_signals` | 0 / 1 (or -1 / 0 / 1 with direction modes) | Enter when close > rolling high + multiplier × range |
| `pairs_signals` | −1, 0, or +1 | Long/short spread based on z-score of log-price spread |

---

### `backtest.py` — Backtest Engine

`run_backtest(close, position, transaction_cost_bps, initial_capital)` produces:

- **Strategy equity curve** — daily portfolio value after applying position and transaction costs
- **Benchmark equity curve** — buy-and-hold with no transaction costs
- **Trade log** — list of position-change records (BUY / SELL / SHORT / COVER / FLIP_TO_LONG / FLIP_TO_SHORT, plus spread actions for pairs) with date, price context, shares/exposure, and dollar transaction cost

Transaction cost model:

```
equity[t] = equity[t-1]
            × (1 − |Δposition[t]| × cost_rate)
            × (1 + position[t] × asset_return[t])
```

For a long-only strategy (`position ∈ {0, 1}`), this charges `cost_rate` of NAV on each entry and exit.

`run_pairs_backtest` handles the dollar-neutral two-leg case: long Y / short X or short Y / long X, with each leg receiving 50% of capital.

---

### `metrics.py` — Performance Statistics

`compute_metrics(equity_curve, periods_per_year=252)` returns:

| Metric | Formula notes |
|---|---|
| Total return | `(final / initial) − 1` |
| CAGR | `(final / initial)^(1/years) − 1`, using the selected/default periods-per-year convention |
| Annualised volatility | `std(daily_returns) × √periods_per_year` |
| Sharpe ratio | `mean(excess) / std(excess) × √periods_per_year`, risk-free = 0 |
| Sortino ratio | `mean(excess) / downside_std × √periods_per_year` |
| Max drawdown | Peak-to-trough on the equity curve (`≤ 0`) |
| Calmar ratio | `CAGR / |max_drawdown|` |
| Win rate | Fraction of positive-return days |

The default convention is **252 trading days/year** (US equity convention). Single-asset Backtest and Strategy Comparison can request 252 / crypto 365 / auto; portfolio analytics, pairs trading, and SMA research tools retain the 252 convention.

---

### `schemas.py` — API Contracts

Pydantic v2 models for every endpoint. Separate request models per strategy (`BacktestRequest`, `RsiBacktestRequest`, `BbBacktestRequest`, …) share common fields (`ticker`, `start_date`, `end_date`, `transaction_cost_bps`, `initial_capital`) and add strategy-specific parameters.

`BacktestResponse` is the unified response for all backtest endpoints. Research endpoints have their own response models (`SmaSweepResponse`, `SmaTrainTestResponse`, `SmaWalkForwardResponse`, `StrategyComparisonResponse`).

---

### `main.py` — Route Layer

FastAPI application with two groups of endpoints:

**Backtest endpoints** (`/backtest/*`):
- Validate common fields (date format, ticker, ordering)
- Fetch price data via `data.py`
- Generate signals via `strategies.py`
- Run the backtest engine via `backtest.py`
- Compute metrics via `metrics.py`
- Assemble and return a `BacktestResponse`

**Research endpoints** (`/research/*`):
- Reuse the same `run_backtest` + `compute_metrics` stack
- Add higher-order logic: parameter grids, train/test splits, rolling windows, multi-strategy ranking
- Return richer response models with degradation statistics, parameter stability, and stitched equity curves

---

## Frontend Modules

### `src/lib/api.ts`

Typed fetch wrappers for every backend endpoint. All calls use relative `/api/*` URLs, which Next.js proxies to the backend. No hardcoded backend URL in client-side code.

### `src/lib/types.ts`

TypeScript interfaces mirroring the Pydantic response models: `BacktestResponse`, `PerformanceMetrics`, `EquityPoint`, `TradeRecord`, `SmaSweepResponse`, etc.

### `src/lib/format.ts`

Display formatters: percentages, dollar amounts, ratios, dates.

### `src/app/page.tsx`

Root page component. Owns all strategy and research parameter state. Renders `BacktestForm` on the left and the appropriate result panels on the right. Tabs switch between Backtest and each research tool.

### `src/components/BacktestForm.tsx`

Strategy and parameter selection form. Renders different parameter fields per strategy. All numeric inputs use `string` state internally (to support partial editing states like `""`, `"0."`, `"-"`) and sync valid parsed values to the parent via prop setters. Validation and the Run button disabled state are derived from parsed values, not raw strings.

### Research panel components

`SmaSweepPanel`, `SmaTrainTestPanel`, `SmaWalkForwardPanel`, `StrategyComparisonPanel` — self-contained panels each managing their own parameter state, API call lifecycle, and result display.

### Visualisation components

- `EquityCurveChart` — strategy vs. benchmark line chart (Recharts)
- `DrawdownChart` — drawdown area chart
- `MetricsGrid` — performance metrics table
- `TradeTable` — sortable trade log

---

## How a Backtest Request Flows Through the System

```
1. User fills in BacktestForm (ticker, dates, strategy, parameters)
2. Clicks Run → page.tsx calls api.ts with the typed request body
3. Next.js server proxies POST /api/backtest/sma-crossover
   → backend POST /backtest/sma-crossover
4. main.py validates dates, ticker, parameter ranges
5. data.py fetches OHLCV from yfinance
6. strategies.py computes signal, shifts by 1 day (no lookahead)
7. backtest.py runs vectorised P&L, builds trade log and benchmark
8. metrics.py computes all statistics from equity curves
9. main.py assembles BacktestResponse (Pydantic serialises to JSON)
10. Frontend receives JSON, updates React state
11. MetricsGrid, EquityCurveChart, DrawdownChart, TradeTable re-render
```

---

## How Research Tools Reuse the Backtest Engine

The research tools do not have separate engines. They call the same `run_backtest` and `compute_metrics` functions:

- **Parameter sweep**: loops over a (fast, slow) grid, calls `run_backtest` once per pair
- **Train/test validation**: splits the date range, runs sweep on IS data, calls `run_backtest` once on OOS data with the selected parameters
- **Walk-forward**: rolls a training window, calls sweep + `run_backtest` on each fold, stitches OOS equity curves using daily return compounding
- **Strategy comparison**: calls `run_backtest` once per strategy with fixed default parameters

---

## How Lookahead Bias is Prevented

All signal functions in `strategies.py` end with:

```python
return raw_signal.shift(1).fillna(0).astype(int).rename("position")
```

This means: today's position is determined by yesterday's closing prices. The backtest engine then uses `position[t]` to compute the return from `close[t-1]` to `close[t]`. The strategy earns the return of day T only if it was long at the start of day T, using information available at the end of day T−1.

For the walk-forward tool, signal context uses only data up to and including the training window's last date:

```python
signal_context = close_all.iloc[train_start_idx:test_end_idx]
```

The shift-by-1 inside `sma_crossover_signals` ensures the signal for the first OOS bar is still based on the last training bar.

---

## Post-MVP Modules (current platform)

The sections above describe the original MVP backtest path. The platform has since grown; these modules reuse the same lookahead-bias-free engine and SQLite layer:

### Backend

- **`custom_strategy.py`** — evaluates no-code strategies as whitelisted rule trees (operands: `close`, constant, or `sma`/`rsi`/`bb_*`/`momentum`; operators `>`, `>=`, `<`, `<=`; ALL/ANY logic). Rules are validated against a strict schema and evaluated with vectorised pandas — **no `eval`, no user code is executed**. Position is shifted one bar forward like every other strategy.
- **`portfolio.py`** — multi-asset analytics: equal-weight backtest (turnover-cost rebalancing), long-only optimization (min-vol / max-Sharpe via SciPy SLSQP), walk-forward optimization (out-of-sample, no leakage), efficient frontier, risk dashboard (correlation/covariance, diversification ratio, risk contribution), historical stress testing, and OLS factor-exposure analysis.
- **`strategy_gallery.py`** — a static, pre-validated catalogue of built-in custom-strategy templates served read-only.
- **`db.py` / `saved_backtests.py` / `saved_reports.py` / `custom_strategy_templates.py`** — SQLite persistence + CRUD for saved results, reports (Markdown + metadata only), and reusable strategy templates (with portable JSON import/export).

### Frontend

- **Command Center** (`HomeDashboard`) — default landing view with quick actions, live recent saved backtests/reports, system status, and a feature map.
- **Onboarding / guided demos** (`lib/demoPresets.ts`, `lib/onboarding.ts`) — first-run welcome card, dismissible, with prefilled (never auto-run) demo presets and a local quick-start checklist.
- **Command palette + global search** (`CommandPalette`, `lib/search.ts`) — Ctrl/Cmd+K to navigate and search commands plus real local resources (saved backtests/reports, templates, gallery).
- **Reporting** (`lib/reportExport.ts`, `ExportReportButton`, `PrintableReportModal`) — local Markdown generation, browser print-to-PDF, four branded templates, and a saved-reports gallery.
- **State & feedback primitives** (`components/ui/`, `lib/toast.ts`, `hooks/useToasts.ts`, `AppErrorBoundary`) — shared loading skeletons, empty/offline/error states, a global toast store, and an app-level error boundary.
- **Theme & charts** (`lib/settings.ts`, `lib/useAccentColors.ts`, `components/charts/`) — CSS-variable neon accent theme and accent-aware neon chart styling.

---

## Limitations and Next Steps

See [`LIMITATIONS.md`](LIMITATIONS.md) for known constraints.

See [`ROADMAP.md`](ROADMAP.md) for planned future work.
