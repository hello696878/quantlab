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

### No margin, leverage, or short-selling constraints

Pairs trading is dollar-neutral but assumes no margin requirements and no borrow cost on short positions. In practice, short-selling requires a locate, incurs borrow fees, and may have forced buy-in risk.

### Buy-and-hold benchmark

The benchmark is always buy-and-hold of the primary asset with no transaction costs. This is a reasonable baseline for trend-following strategies but may not be the most relevant benchmark for every strategy type (e.g., a market-neutral pairs strategy should be compared to cash or a market-neutral index, not buy-and-hold).

---

## Metrics

### 252-day annualisation is an equity convention

All annualised metrics (CAGR, Sharpe, Sortino, Volatility) use 252 trading days per year. This is standard for US equity markets but incorrect for:

- Cryptocurrencies (365-day markets)
- Futures calendars
- Assets in markets with different holiday schedules

Using 252 for crypto assets will understate annual returns and overstate risk metrics compared to a 365-day calculation.

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

The Strategy Comparison tool runs each strategy with hard-coded default parameters (e.g., SMA 50/200, RSI window 14). These defaults were chosen as reasonable starting points but may not be optimal for any particular asset or period. A strategy that ranks last with its defaults might rank first with tuned parameters.

---

## Frontend

### No persistent state

Backtest results are not saved. Navigating away or refreshing the page loses all results. Persistence is planned in a future phase (see `ROADMAP.md`).

### No real-time data

The frontend does not update automatically. Each run requires a manual click. There is no streaming or live feed.

---

## General

### Not investment advice

**Nothing in QuantLab constitutes investment advice.** Backtests show historical simulated performance only. Past performance does not predict future results. Real trading involves execution risk, market impact, regulatory constraints, and other factors not modelled here.

### Strategy results are sensitive to the period chosen

All strategies are sensitive to the start date, end date, and the specific market regime in that period. A strategy that looks excellent on SPY from 2010–2020 may look very different on SPY from 2000–2010, or on a different asset. Do not draw conclusions from a single backtest window.
