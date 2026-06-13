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

QuantLab fetches with `auto_adjust=True`, so the `Close` column used by every backtest is **split/dividend-adjusted**. Always sanity-check results that look unusually good or bad.

### Data provider abstraction is v1 — yfinance and CSV only

Backtest responses now report `data_provider` and `data_quality` diagnostics (actual range, row count, missing values, duplicate dates, inferred frequency, calendar gaps, warnings). These diagnostics are **observational**: they describe the series the engine used; they never repair, fill, or block data. Current limits:

- **No paid/institutional data provider integration yet** (Polygon, Tiingo, Alpaca, Binance, …) — the abstraction is prepared for them, but yfinance and CSV upload are the only live providers.
- **No intraday provider abstraction** — daily bars only.
- **No exchange-native crypto data provider** — crypto goes through Yahoo Finance's `-USD` pairs.
- Data-quality warnings are heuristics (frequency inference, gap detection with a 5-day threshold, 7-day edge tolerance); absence of warnings does not certify the data is correct.
- Portfolio endpoints (multi-ticker) do not yet report per-ticker data quality.

### No survivorship-bias-free database

The strategy library only backtests tickers that exist today. If you backtest an index of stocks that were listed in 2005, you are implicitly selecting survivors — companies that did not go bankrupt or get delisted. This causes in-sample results to look better than they would have been in real time.

A rigorous test would use a point-in-time database with constituent lists at each rebalance date. This is not currently implemented.

### No intraday or tick data

All strategies use daily closing prices only. Intraday patterns, opening gaps, and microstructure effects are not modelled.

---

## Backtest Engine

### Static transaction cost model

Transaction costs are modelled as a static percentage of portfolio value charged on each position change. The single-asset Backtest form and Strategy Comparison support either backward-compatible simple bps or a commission + slippage + spread/conservative preset; CSV upload and SMA research tools use the simple `transaction_cost_bps` path. This is still a rough approximation. In practice, costs depend on:

- Trade size (market impact)
- Bid-ask spread (varies by asset, time, liquidity)
- Broker commissions
- Short-selling borrowing fees (relevant for pairs trading)

The model does not simulate dynamic spreads, size-dependent impact, partial fills, or order book dynamics.

### No execution simulator

Signals are generated from the close and shifted one bar before returns are earned, but the daily-bar simulation still approximates fills from closing-price data. Static slippage bps can be included in the cost model, but QuantLab does not model intraday execution paths, gap fills, market orders walking the book, or adverse selection. For illiquid assets or large position sizes, actual fill prices can be materially worse.

### No tax model

Capital gains taxes, wash-sale rules, and other tax considerations are not modelled.

### No margin, leverage, or short-selling cost model

Pairs trading is dollar-neutral, and SMA Crossover / Momentum / Volatility Breakout offer **short-only** and **long-short** direction modes. All of these assume **no margin requirements and no borrow/funding cost** on short positions — a short simply earns `−1 × asset_return` with `|position| ≤ 1` (no leverage). In practice, short-selling requires a locate, incurs borrow fees, is subject to margin calls and forced buy-in risk, and can be liquidated. **None of that is modelled.** Long/short results are therefore highly sensitive to timing and transaction costs; the UI surfaces a short-selling warning and direction diagnostics, and exported reports add an explicit caveat. `long_only` is always the default.

### Buy-and-hold benchmark

The benchmark is always buy-and-hold of the primary asset with no transaction costs. This is a reasonable baseline for trend-following strategies but may not be the most relevant benchmark for every strategy type (e.g., a market-neutral pairs strategy should be compared to cash or a market-neutral index, not buy-and-hold).

---

## Metrics

### Annualization convention is selectable but still simplified

Single-asset backtests and Strategy Comparison support an **annualization convention** (`annualization_mode`): `trading_days_252` (default, equities/ETFs), `crypto_365` (24/7 crypto daily data), or `auto` (recognized crypto tickers → 365, otherwise 252 with a caveat). The convention rescales **CAGR, Calmar, Sharpe, Sortino, and volatility** only — it never changes trades, the equity curve, total return, or max drawdown. The default (252) is identical to previous behaviour.

This is still a simplified convention:

- It assumes one fixed number of return periods per year; intraday data would require different period assumptions.
- CAGR uses `periods_per_year` (not exact calendar days) for v1.
- `auto` detection is a simple ticker heuristic (`-USD` suffix / a known-crypto list); uncertain tickers default to 252 with a warning.
- Mixed-asset portfolios may need more nuanced calendar handling in future.
- **Pairs trading, the CSV Upload UI's simple workflow, the SMA research tools (sweep / train-test / walk-forward), and all portfolio analytics still annualise with 252** regardless of asset — only the single-asset Backtest and Strategy Comparison flows expose the selected mode in the UI.

Using 252 for crypto assets will understate annual returns and overstate risk metrics compared to a 365-day calculation, which is why `crypto_365` / `auto` exist.

### Risk-free rate is zero

The Sharpe and Sortino ratios are computed with a risk-free rate of 0%. During periods of elevated interest rates, a non-zero risk-free rate would lower the Sharpe ratio of strategies that hold cash during flat periods.

### Robustness Lab is a bootstrap, not a proof

Robustness Lab v1 block-bootstraps the realized daily strategy returns (blocks preserve short-term autocorrelation; `block_size=1` is a plain i.i.d. bootstrap) and summarizes the simulated distribution. Honest limits:

- Bootstrap **resamples history** — it estimates sensitivity to return ordering/sampling, not future performance. Regime shifts, liquidity shocks, and structural breaks violate its assumptions, and small samples limit interpretation.
- A fragile strategy can still look good in one backtest — and a good-looking bootstrap does not prove alpha.
- The **A–F grade is a transparent heuristic** (thresholds on probability of loss, tail return, tail drawdown, median Sharpe) — a rule-of-thumb summary, never a trading recommendation.
- **Deflated Sharpe is null in v1**: it requires the number of tried configurations and distributional assumptions, which the app cannot know. Full deflated Sharpe and PBO (probability of backtest overfitting) are planned for Robustness/Stability v2 — they are **not implemented yet**. The SMA parameter-sensitivity heatmap exists as Stability Lab v1 below.
- Robustness quality inherits data quality: warnings from the data layer are surfaced because the bootstrap assumes the input return series is valid.

### Options Lab is an educational calculator, not an options risk engine

The Options & Volatility Lab v1 prices **European** options with Black–Scholes (continuous dividend yield), computes Greeks, solves implied volatility by bisection, and draws expiration payoff diagrams. It is deterministic and educational. It explicitly does **not** model:

- American / early exercise, or discrete dividends.
- Volatility smile or term structure (a single flat σ per calculation — no surface).
- Transaction costs, bid/ask spreads, liquidity, or assignment risk.
- Path-dependent mark-to-market PnL — payoff diagrams are **terminal** payoff at expiration only (a short option can show a small bounded payoff yet carry large interim losses; see Volmageddon in Quant Disasters).
- Real-time Greeks or **any live option-chain data** — all inputs (including premiums in the payoff builder) are manual.

Greeks conventions are labelled: delta/gamma per 1.0 of the underlying; vega/rho raw per 1.0 (100%) move; theta shown per-day and per-year. Breakevens are approximate (interpolated from the sampled payoff curve). It is not a fair value, a recommendation, or a production options risk system.

### Stability Lab explores parameters; it cannot bless them

Stability Lab v1 sweeps an SMA fast × slow grid with the same simulation settings and summarizes whether the selected parameters sit in a stable neighborhood. Honest limits:

- **Broad stable regions are generally more credible than isolated spikes** — but a stable region in one historical window can still fail out-of-sample.
- **Parameter sweeps can overfit**: choosing the best-performing cell after viewing the heatmap is itself a selection bias. The best cell is shown for context, never as a recommended trading setting.
- The **stability score is a transparent heuristic** (selected value vs. its up-to-8 grid neighbors, penalized for invalid/missing neighbors) — a rule-of-thumb, not a statistical test. PBO (probability of backtest overfitting) is **not implemented**.
- v1 supports **SMA Crossover only**; other strategies return a clear unsupported note. RSI / Bollinger / Momentum sweeps are planned.
- Grid runs share one data fetch and return summary metrics only; benchmark-relative metrics (information ratio) per cell are not computed in v1.

### Config hashes identify inputs, not guaranteed outputs

Every backtest gets a deterministic **config hash**: SHA-256 over the canonical, normalized, result-changing inputs (same normalized config → same hash; defaults are normalized first, so legacy requests hash like their explicit equivalents). Limits to keep in mind:

- The hash fingerprints **input assumptions only**. yfinance can revise historical data, so the same config hash can produce different output later. Exact output reproducibility requires both the config hash **and a stable data snapshot** — v1 hashes configs; future versions will add dataset version hashes (provider snapshot ids / parquet/CSV file hashes). CSV backtests already include a SHA-256 fingerprint of the uploaded file content.
- Settings that resolve to identical engine behaviour hash identically by design (e.g. the conservative cost preset ≡ simple 25 bps; `auto` annualization ≡ its resolved convention).
- The "permalink" is **local-first**: a config fingerprint plus your local saved backtests — not a public or cloud URL. Replay-by-hash (restoring a form from a hash) is future work.
- Old saved backtests created before this feature have no stored hash; they load fine and show "config: —".

### Benchmark / active analytics are simplified research metrics

Benchmark comparison (buy-and-hold same asset, custom ticker, or none) computes alpha, beta, correlation, tracking error, and the information ratio on **date-aligned daily returns** with a **zero risk-free rate** (so "alpha" is a CAPM-style regression intercept against the chosen benchmark, not a risk-free-adjusted alpha). Caveats:

- Benchmark returns are aligned by available dates (inner join); limited overlap shrinks the sample and is flagged with a warning.
- The buy-and-hold benchmark pays **no transaction costs** — a deliberate, documented convention that slightly flatters the benchmark.
- Benchmark data quality depends on the provider (yfinance gaps/revisions apply to benchmarks too).
- Results are sensitive to the **chosen benchmark** — comparing against a weak benchmark can make any strategy look good; choose a benchmark that matches the asset class.
- Non-computable metrics (zero benchmark variance, zero tracking error, too few aligned points) are reported as null with warnings.
- Benchmark analytics never change strategy trades, and they are research metrics — **not investment advice**.

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
