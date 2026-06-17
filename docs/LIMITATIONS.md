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

The Options & Volatility Lab prices **European** options with Black–Scholes (continuous dividend yield), computes Greeks, solves implied volatility by bisection, draws expiration payoff diagrams, runs CRR tree / Monte Carlo calculators, and builds a manual/synthetic IV surface with an SVI research fit. It is deterministic and educational. It explicitly does **not** model:

- Live option chains or calibrated market feeds; the Vol Surface tab uses manual or synthetic rows only.
- A guaranteed arbitrage-free surface; the SVI fit is a constrained least-squares research approximation.
- Transaction costs, bid/ask spreads, liquidity, or assignment risk.
- Path-dependent mark-to-market PnL — payoff diagrams are **terminal** payoff at expiration only (a short option can show a small bounded payoff yet carry large interim losses; see Volmageddon in Quant Disasters).
- Real-time Greeks or **any live option-chain data** — all inputs (including premiums in the payoff builder) are manual.

Greeks conventions are labelled: delta/gamma per 1.0 of the underlying; vega/rho raw per 1.0 (100%) move; theta shown per-day and per-year. Breakevens are approximate (interpolated from the sampled payoff curve). It is not a fair value, a recommendation, or a production options risk system.

**Tree pricing is a numerical approximation, not a production American-pricing engine.** The CRR binomial model converges to Black–Scholes for European options as the step count grows, and handles American exercise by taking `max(intrinsic, continuation)` at each node. It models only a **continuous** dividend yield — **not** discrete dividends, corporate actions, or other exotic features — and its price depends on the chosen step count, the volatility input, and the exercise style. The early-exercise diagnostic (detected / first step / approximate boundary) is a teaching aid, not a guaranteed optimal-exercise policy. The full node lattice is rendered only for small trees (≤ 6 steps) for readability; larger trees return the price and diagnostics only. No trinomial tree yet (planned), no volatility surface, no Heston/SABR.

**Monte Carlo pricing is an educational simulation with sampling error, not a production exotic-pricing engine.** The Monte Carlo tab simulates risk-neutral **Geometric Brownian Motion** paths (constant volatility, continuous dividend yield) to price European, arithmetic-average **Asian**, and simple **barrier** (up/down-and-out/in) options. Every price carries Monte Carlo **sampling error** — reported as the standard error and a 95% confidence interval — and depends on the random **seed**, the number of **simulations**, the number of time **steps**, and the volatility input. **Barrier monitoring is discrete** over the simulated steps (it can differ from continuous monitoring and tends to under-count breaches), and Asian averaging is arithmetic with no closed form. The path preview is a small, capped sample (≤ 12 paths) — the engine never returns all simulated paths. It does **not** model stochastic / local volatility, jumps, discrete dividends, early exercise, transaction costs, or live option chains. It is not a fair value or a recommendation.

**The volatility surface is a research tool, not a live vol terminal or an arbitrage-free calibration.** The Vol Surface tab extracts implied volatility from a **manual or synthetic** option chain (there are **no live option chains**) using the existing bisection solver, then summarises the smile, ATM term structure, and skew, and fits a per-expiry **SVI** smile. Surface quality depends entirely on the input option prices, bid/ask quality, strike/expiry coverage, dividends, rates, and solver stability; deep out-of-the-money / short-dated quotes have little vega, so their recovered IVs are unreliable. The **SVI fit is a least-squares research approximation** — it enforces the basic parameter constraints (b ≥ 0, |ρ| < 1, σ > 0) but does **not** guarantee a static-arbitrage-free surface, and a slice with too few valid points is reported as unfitted rather than forced. A row that fails to solve is kept with a null IV and a warning. The surface is **not** produced by a stochastic-volatility model — the separate Heston tab is a path simulator, not a surface calibrator. No SABR, no local volatility, no production calibration.

**Heston is an educational stochastic-volatility simulator, not a calibrated model.** The Heston tab prices European options under risk-neutral Heston dynamics (variance mean-reverts to a long-run level with its own vol-of-vol and a price/variance correlation) using a **full-truncation Euler Monte Carlo** scheme. The Euler discretization is **biased** (finer steps reduce the bias), every price carries Monte Carlo **sampling error** (reported as the standard error and a 95% CI), and results depend on the parameters, the seed, the step/simulation counts, and the variance-process handling. The **Feller condition** (2κθ ≥ ξ²) is reported and **warned** when violated (variance then spends more time near zero, increasing Euler bias) but is **not** rejected. The Black-Scholes reference (using √long-run-variance) is shown only for orientation — it is **not** a correctness benchmark when volatility is stochastic. The model is **not calibrated to any market surface** (calibration is planned), and there is no SABR, local, or rough volatility.

**Options Lab scenario presets and the Model Comparison are educational.** The unified scenario presets are **educational scenarios / model demonstrations**, not trading recommendations; they only seed inputs. The Model Comparison prices the same option across Black–Scholes, binomial, Monte Carlo, and Heston on demand — the models disagree because **their assumptions differ**, and none is automatically "correct"; differences vs Black–Scholes are expected, and the simulation rows carry Monte Carlo sampling error.

**The Event Lab is a research diagnostic, not a live event system.** The event study measures **benchmark-adjusted abnormal returns** and the cumulative abnormal return (CAR / CAAR) around a date. Event windows are measured in trading observations around the event date, and the summary's post-event CAR excludes day 0 because event-day abnormal return is shown separately. Results are highly sensitive to the **event date** (leakage often moves prices before the announcement), the **benchmark/model choice**, the window size, **confounding events** in the window, liquidity, transaction costs, and survivorship/selection bias — a non-trading event date maps to the next session, and insufficient history warns rather than crashing. There are **no live SEC filings, no filing parser, and no curated event database**; the sample events are clearly labelled demo data to be verified before use. The **merger-arbitrage calculator** is a simplified expected-value model (spread, expected/annualized return, breakeven probability) that **ignores** borrow/financing costs, regulatory timing, competing bids, taxes, liquidity, and detailed deal terms. None of it is investment advice.

**The Yield Curve Lab is educational fixed-income research, not a rates desk.** It works on **synthetic or manually-entered** zero curves — there is **no live rates feed and no swap-curve bootstrapping**. Every number is **assumption-driven**: discount factors, implied forward rates, and bond prices change with the **compounding convention** (annual / semiannual / continuous), the **interpolation method** (zero rates vs discount factors), and day-count assumptions (the lab uses simple year fractions — no real day-count or settlement/accrued-interest conventions, so bond prices are a simplified *clean-price approximation*). Forward rates are curve-implied rates, **not guaranteed forecasts**. Interpolation is only valid **inside** the curve's maturity range; cash flows beyond it clamp to the nearest endpoint with a warning. Curve **shocks** (parallel / steepener / flattener / butterfly) are simple educational transforms, not realistic scenario generation. DV01 is shown as a **price-change magnitude** for a 1 bp move; the actual price change for a +1 bp yield move is usually negative. There is **no credit curve**, and nothing here is investment advice.

**The Short Rate Models Lab is an educational simulator, not a calibrated rates model.** The Short Rate Models tab simulates one-factor **Vasicek** (`dr = κ(θ−r)dt + σ dW`) and **CIR** (`dr = κ(θ−r)dt + σ√r dW`) short-rate dynamics under risk-neutral assumptions with an **Euler** scheme (CIR uses **full truncation** so simulated rates stay non-negative). Outputs are **scenarios, not forecasts**: they depend entirely on the chosen parameters (κ, θ, σ, r0), the **discretization** (steps), the **simulation count**, and the **random seed**, and carry Monte Carlo sampling error. **Vasicek is Gaussian and can produce negative rates** — a known feature of the model, flagged with a warning, not a bug. For CIR the **Feller condition** (2κθ ≥ σ²) is reported and **warned** when violated (rates spend more time near zero and Euler bias increases) but is **not** rejected. Zero-coupon bond prices use the standard **closed-form affine** solutions (with a deterministic σ=0 fallback); they are model prices, **not** market quotes. The models are **not calibrated to any market yield curve**, and there is **no Hull-White** (or other multi-factor / time-dependent short-rate model), no swap-curve bootstrapping, and no production curve engine. None of it is investment advice.

**The FX Lab is educational FX analytics, not a live FX desk.** The FX Lab covers spot/forward via **covered interest rate parity** (`F = S·e^((r_d−r_f)T)` or annual), an **FX carry** decomposition (interest differential + an *assumed* expected spot move), **PPP deviation** (relative PPP from inflation indexes), a **currency exposure** translation with a uniform symmetric stress, and **Garman-Kohlhagen** FX option pricing. The quote convention is **domestic currency per 1 unit of foreign currency** throughout. Every result ignores **bid/ask spreads, funding and transaction costs, rollover, liquidity, capital controls, and whether the quoted rates are actually investable** — the parity forward is a no-arbitrage relationship, **not a free profit**, and **carry is not free money** (the differential typically compensates for currency risk). PPP deviation **suggests relative valuation under simplified inputs, not a timing signal** — PPP gaps can persist for years and depend on the base period, the basket, and data quality. The exposure stress is an **educational uniform shock**, not a covariance-based VaR model; FX exposure reports both net exposure and gross absolute exposure, and suppresses net percentage weights when offsetting long/short rows make net exposure near zero. Garman-Kohlhagen assumes **constant volatility and lognormal spot** — there is **no FX volatility surface, smile, or skew**. There are **no live FX rates, no broker integration, no FX arbitrage engine, and no production currency-risk system**, and nothing here is investment advice.

**UI fix (16.1 → 16.2):** Rates / Yield Curve / Short Rate result-card **value text contrast** was poor — the dark theme remaps the Tailwind `slate` ramp to an *inverted* scale (low shades are dark surfaces), so a class like `text-slate-100` rendered as near-invisible dark navy on dark cards. All Rates and FX result cards now use a shared `MetricCard` whose colours come from **explicit CSS design tokens** (`var(--text-hi)` for default values, plus accent / emerald / amber / red tones) rather than Tailwind numeric colour classes, so values stay readable regardless of the ramp. Options Lab and Event Lab cards were not affected.

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
