# QuantLab — Known Limitations

This document lists known constraints, simplifications, and caveats in the current implementation. Being explicit about limitations is important for honest backtesting and responsible use.

---

## Data

### yfinance data quality

Price data is sourced from yfinance (Yahoo Finance). This data:

- May contain gaps, errors, or anomalies around corporate actions
- Depends on Yahoo Finance's continued free availability — no SLA
- Is not suitable for production trading systems
- May return adjusted or unadjusted prices depending on the ticker and date range

Always sanity-check results that look unusually good or bad.

### No survivorship-bias-free database

The strategy library only backtests tickers that exist today. If you backtest an index of stocks that were listed in 2005, you are implicitly selecting survivors — companies that did not go bankrupt or get delisted. This causes in-sample results to look better than they would have been in real time.

A rigorous test would use a point-in-time database with constituent lists at each rebalance date. This is not currently implemented.

### No intraday or tick data

All strategies use daily closing prices only. Intraday patterns, opening gaps, and microstructure effects are not modelled.

---

## Backtest Engine

### Simplified transaction cost model

Transaction costs are modelled as a flat percentage of portfolio value (`transaction_cost_bps / 10000`) charged on each position change. This is a rough approximation. In practice, costs depend on:

- Trade size (market impact)
- Bid-ask spread (varies by asset, time, liquidity)
- Broker commissions
- Short-selling borrowing fees (relevant for pairs trading)

The model does not simulate partial fills, slippage, or order book dynamics.

### No slippage model

Trades are executed at the closing price of the signal bar (i.e., the open of the next bar conceptually). In reality, large orders move the market. For illiquid assets or large position sizes, actual fill prices will be worse.

### No tax model

Capital gains taxes, wash-sale rules, and other tax considerations are not modelled.

### No margin, leverage, or short-selling cost model

Pairs trading is dollar-neutral, and SMA Crossover / Momentum / Volatility Breakout offer **short-only** and **long-short** direction modes. All of these assume **no margin requirements and no borrow/funding cost** on short positions — a short simply earns `−1 × asset_return` with `|position| ≤ 1` (no leverage). In practice, short-selling requires a locate, incurs borrow fees, is subject to margin calls and forced buy-in risk, and can be liquidated. **None of that is modelled.** Long/short results are therefore highly sensitive to timing and transaction costs; the UI surfaces a short-selling warning and direction diagnostics, and exported reports add an explicit caveat. `long_only` is always the default.

### Buy-and-hold benchmark

The benchmark is always buy-and-hold of the primary asset with no transaction costs. This is a reasonable baseline for trend-following strategies but may not be the most relevant benchmark for every strategy type (e.g., a market-neutral pairs strategy should be compared to cash or a market-neutral index, not buy-and-hold).

---

## Metrics

### Annualization convention is selectable but still simplified

Single-asset backtests and Strategy Comparison support an **annualization convention** (`annualization_mode`): `trading_days_252` (default, equities/ETFs), `crypto_365` (24/7 crypto daily data), or `auto` (recognized crypto tickers → 365, otherwise 252 with a caveat). The convention rescales **CAGR, Sharpe, Sortino, and volatility** only — it never changes trades, the equity curve, total return, or max drawdown. The default (252) is identical to previous behaviour.

This is still a simplified convention:

- It assumes one fixed number of return periods per year; intraday data would require different period assumptions.
- CAGR uses `periods_per_year` (not exact calendar days) for v1.
- `auto` detection is a simple ticker heuristic (`-USD` suffix / a known-crypto list); uncertain tickers default to 252 with a warning.
- Mixed-asset portfolios may need more nuanced calendar handling in future.
- **Pairs trading, CSV-upload backtests, the SMA research tools (sweep / train-test / walk-forward), and all portfolio analytics still annualise with 252** regardless of asset — only the single-asset Backtest and Strategy Comparison flows honour the selected mode.

Using 252 for crypto assets will understate annual returns and overstate risk metrics compared to a 365-day calculation, which is why `crypto_365` / `auto` exist.

### Risk-free rate is zero

The Sharpe and Sortino ratios are computed with a risk-free rate of 0%. During periods of elevated interest rates, a non-zero risk-free rate would lower the Sharpe ratio of strategies that hold cash during flat periods.

### Calmar ratio edge cases

The Calmar ratio is defined as `CAGR / |max_drawdown|`. If max drawdown is zero (impossible in real markets but possible in tests with synthetic constant prices), it is reported as 0.0 rather than infinity.

---

## Research Tools

### Parameter sweeps can overfit

The SMA Parameter Sweep and the in-sample phase of Train/Test and Walk-Forward tools select parameters that performed best on historical data. This does not mean those parameters will perform well out-of-sample. The out-of-sample and walk-forward tools exist precisely to help diagnose this — but degradation is common and expected.

A parameter that ranks first in a grid search may do so by chance. Treat in-sample results with scepticism.

### Walk-forward stitching ignores overlap gaps

When `step_days < test_window_days`, consecutive test windows overlap. The stitching logic deduplicates overlapping dates by keeping only the first occurrence. This means a date may be evaluated using parameters selected from an earlier training window, not the most recent one. The aggregate metrics reflect this stitched curve, which is an approximation of true walk-forward performance.

### Strategy Comparison uses fixed default parameters

The Strategy Comparison tool runs each strategy with fixed demo-friendly default parameters (SMA 20/100, RSI 14 with 35/55 thresholds, Bollinger 20 with 1.8σ, momentum 63, Volatility Breakout 20 with 0.3× range). These defaults are starting points, not recommendations, and may still produce few or zero trades for some assets or periods. A strategy that ranks last with its defaults might rank first with tuned parameters.

Strategy Comparison **does** let you adjust the shared market-simulation assumptions — cost model, position sizing, risk management, and direction mode — which are applied globally to all five strategies. The **strategy-specific** parameters above remain fixed (per-strategy parameter customization is not implemented). Direction modes apply only to SMA Crossover, Momentum, and Volatility Breakout; RSI and Bollinger run long-only and are labelled as unsupported under short modes. Risk exits use the same daily-bar approximation, costs/slippage are simplified, and position sizing does not model margin or financing — none of these are guaranteed to improve performance.

---

## Persistence & Portfolio Analytics

### In-sample portfolio optimization

Static Portfolio Optimization and the Efficient Frontier estimate expected returns and the covariance matrix from the **same** historical window they then analyse (252-day annualisation). This is in-sample by construction: it will look good, can overfit, and **does not predict future performance**. Walk-Forward Optimization provides an out-of-sample variant but still relies on historical assumptions. Risk-dashboard, stress-test, and factor-analysis figures are likewise **historical estimates** that may not persist out-of-sample.

### Local SQLite — single-user, no auth

Saved backtests, saved reports, and saved custom-strategy templates persist in a **local SQLite** file (`backend/data/quantlab.db`). There is **no authentication, no multi-user support, and no cloud sync** — anyone with access to the running app can read/modify/delete local records. It is intended for single-user, local research, not a shared or hosted deployment.

## Frontend

### No real-time data

The frontend does not update automatically. Each run requires a manual click. There is no streaming or live feed.

---

## General

### Not investment advice

**Nothing in QuantLab constitutes investment advice.** Backtests show historical simulated performance only. Past performance does not predict future results. Real trading involves execution risk, market impact, regulatory constraints, and other factors not modelled here.

### Strategy results are sensitive to the period chosen

All strategies are sensitive to the start date, end date, and the specific market regime in that period. A strategy that looks excellent on SPY from 2010–2020 may look very different on SPY from 2000–2010, or on a different asset. Do not draw conclusions from a single backtest window.
