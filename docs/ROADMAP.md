# QuantLab — Roadmap

This document tracks what has been built and what is planned.

The guiding principle: **build in small, usable phases**. Each phase produces something that works before moving to the next.

---

## Completed Phases

### Phase 0 — Project Setup ✅

- Clean repository structure
- FastAPI skeleton with `/health` endpoint
- pytest test infrastructure
- `requirements.txt` and local run instructions
- README with setup guide

### Phase 1 — Backend MVP ✅

Core backtesting engine:

- `data.py`: yfinance OHLCV download layer
- `strategies.py`: SMA Crossover signal generation with lookahead-bias prevention (shift by 1)
- `backtest.py`: vectorised P&L engine, transaction cost model, buy-and-hold benchmark, trade log
- `metrics.py`: Total Return, CAGR, Sharpe ratio, Sortino ratio, Calmar ratio, Max Drawdown, Volatility, Win Rate
- `schemas.py`: Pydantic request/response models
- Full test suite for all backend modules

### Phase 2 — Frontend Dashboard ✅

- Next.js 14 + React 18 + TypeScript + Tailwind CSS
- `BacktestForm` component: strategy/parameter selection
- `EquityCurveChart`: strategy vs. buy-and-hold comparison (Recharts)
- `DrawdownChart`: drawdown visualisation
- `MetricsGrid`: performance metrics display
- `TradeTable`: trade log table
- `api.ts`: typed fetch wrappers for all backend endpoints
- Next.js rewrites: `/api/*` proxy to backend

### Phase 3 — Strategy Expansion ✅

Additional strategies added to the backend and frontend:

- RSI Mean Reversion (long-only, oversold entry / exit threshold)
- Bollinger Band Mean Reversion (lower band entry, middle or upper band exit)
- Time-Series Momentum (trailing return threshold, configurable entry/exit)
- Volatility Breakout (rolling high + range multiplier, rolling mean exit)
- Pairs Trading / Statistical Arbitrage (z-score of log-price spread, dollar-neutral two-leg)

Full test coverage for each strategy (signals + API endpoint).

### Phase 4 — Research Tools ✅

Advanced analysis tools built on top of the core backtest engine:

- **SMA Parameter Sweep**: grid search over fast/slow window combinations, ranked results table
- **SMA Train/Test Out-of-Sample Validation**: IS parameter selection → OOS evaluation, degradation metrics, `oos_collapsed` flag
- **SMA Walk-Forward Optimization**: rolling window optimisation, stitched OOS equity curve, parameter stability summary
- **Strategy Comparison**: run all five single-asset strategies on the same ticker, ranked by Sharpe/CAGR/Calmar/drawdown

All research tools reuse `run_backtest` and `compute_metrics` — no separate engine.

### Phase 5 — Engineering Infrastructure ✅

- **Numeric input UX fix**: all form fields store raw string state, validate on submit, support empty fields and partial decimals (`"0."`, `"-"`, `""`) without auto-reset
- **GitHub Actions CI**: `backend-tests` (pytest) and `frontend-build` (next build) on every push/PR to `main`
- **Docker Compose**: `docker compose up --build` starts both services; `BACKEND_URL` baked at frontend build time for correct internal Docker DNS routing
- **Comprehensive README and portfolio documentation**

### Phase 6 — CSV Upload Backtesting ✅

- `POST /backtest/csv` — upload a price CSV and run any single-asset strategy
  (SMA Crossover, RSI, Bollinger Band, Momentum, Volatility Breakout)
- Flexible column detection: date (`date` / `datetime` / `timestamp`) and
  close (`close` / `adj_close` / `adjusted_close`); optional OHLCV ignored
- Reuses the existing strategy + backtest + metrics stack unchanged; Pairs
  Trading excluded (needs two assets)
- New **CSV Backtest** workspace in the dashboard with drag-and-drop upload
- Full parser + API test coverage

### Phase 6 — Custom Strategy Builder v1 ✅

- `POST /backtest/custom` — no-code, long-only, single-asset rule builder
- Operands: `close`, numeric constant, and indicators `sma` / `rsi` /
  `bb_upper` / `bb_middle` / `bb_lower` / `momentum`; operators `> >= < <=`
- Entry/exit rule lists combined with ALL (AND) or ANY (OR) logic; stateful
  long/flat machine with a one-bar forward shift (no lookahead)
- **Safe by construction**: operands resolved through a fixed dispatch table
  and evaluated with vectorised pandas — no `eval`/`exec`, no user code run
- Indicators reuse the built-in `compute_rsi` / `compute_bollinger_bands` math
- New **Strategy Builder** dashboard workspace; full evaluator + API tests

---

## Future Phases

The items below are planned but not yet started. Order and scope may change.

### Phase 6 — Saved Backtests and Database

- Persist backtest results to a lightweight database (SQLite or PostgreSQL)
- Save, name, and reload previous backtest runs
- Compare saved runs side by side

### Phase 7 — User Accounts

- Authentication (email/password or OAuth)
- Per-user saved strategies and backtests
- User dashboard

### Phase 8 — CSV Upload (extensions)

- Single-asset CSV upload backtesting shipped — see "Phase 6 — CSV Upload
  Backtesting" above.
- Remaining: run the research tools (sweep, train/test, walk-forward,
  comparison) on uploaded data, and two-asset CSV upload for Pairs Trading.

### Phase 9 — Multi-Asset Portfolio Backtesting

- Portfolio of assets with configurable weights
- Rebalancing schedule (monthly, quarterly, annual)
- Portfolio-level metrics (portfolio Sharpe, diversification ratio)
- Mean-variance optimisation (Markowitz efficient frontier)
- Risk parity

### Phase 10 — Better Visualisation

- Monthly return heatmap (calendar chart)
- Rolling Sharpe / rolling beta charts
- Trade distribution histogram
- Underwater plot (time spent in drawdown)
- Interactive parameter sensitivity charts

### Phase 11 — Live Data Integration

- Real-time or end-of-day price feed
- Paper trading mode (no real orders, just simulated fills)
- Alert when a live signal triggers

### Phase 12 — Deployment

- Hosted public demo (Railway, Render, Fly.io, or AWS)
- Environment-specific configuration
- Rate limiting and basic abuse protection
- Custom domain

### Phase 13 — Advanced Models

Items from the long-term vision, ordered by complexity:

- Kalman filter pairs trading (dynamic hedge ratio)
- Rolling-beta pairs trading v2 (vs. fixed lookback z-score)
- Hidden Markov Model regime detection
- Factor model exposure analysis (Fama-French)
- Black-Scholes options pricing module
- Heston model and volatility surface

### Phase 14 — Data Quality Improvements

- Crypto calendar support (365-day annualisation, 24/7 trading)
- Survivorship-bias awareness flag
- Dividend-adjusted vs. unadjusted price toggle
- Data quality warnings (gaps, splits, anomalies)

---

## Non-Goals (deliberate omissions)

These items will not be built in the foreseeable future:

- Real-money order execution / brokerage API integration
- Intraday data or tick-level backtesting
- High-frequency or market-making strategies
- Tax modelling
- Options order management
- Proprietary data subscriptions
