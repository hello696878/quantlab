# QuantLab — Known Issues & Honest Limitations

This is the candid, release-facing summary of what QuantLab **does not** do and
where it is intentionally simplified. It complements the deeper
[`LIMITATIONS.md`](LIMITATIONS.md) and exists so the project can be presented
honestly. None of these are bugs to hide — they are documented scope boundaries
of a **research tool**.

> **QuantLab is research/education software. It is not investment advice and not
> a trading system.**

---

## Scope & intent

- **Research-only, not live trading.** There is no broker connection, order
  routing, paper-trading engine, or real-money execution anywhere in the app.
- **No live broker integration.** Out of scope by design; see the roadmap's
  far-future / non-goals.

## Data

- **yfinance data limitations.** Prices come from Yahoo Finance via `yfinance`:
  no SLA, possible gaps/anomalies around corporate actions, and adjusted-vs-raw
  behavior can vary by ticker/range. Sanity-check unusually good/bad results.
- **No production-grade data vendor.** There is no point-in-time / survivorship-
  bias-free database and no intraday or tick data — daily closes only.

## Backtest & execution realism

- **No market-impact or execution simulator.** Daily-bar fills are approximations;
  large orders moving the market, intraday gaps, order-book depth, and partial
  fills are not simulated.
- **Static transaction costs.** Simple bps and commission + slippage + spread
  presets are supported in the main single-asset flows, but costs do not vary by
  size, liquidity, time, broker tier, or stress regime.
- **Short-selling is simplified.** Long/short modes (SMA / Momentum / Volatility
  Breakout) and pairs trading earn `−1 × asset_return` on shorts with **no borrow
  fees, margin requirements, liquidation, or funding costs modelled**, and
  `|position| ≤ 1` (no leverage). Short results are highly sensitive to timing
  and transaction costs; the UI shows a short-selling warning and diagnostics,
  and `long_only` is always the default.

## Portfolio analytics

- **Optimization is based on historical estimates.** Expected returns and
  covariance are estimated from the selected window; static optimization and the
  efficient frontier are **in-sample by construction** (they look good on the
  data they fit). Walk-Forward Optimization is the out-of-sample variant but
  still relies on historical assumptions. None of it forecasts the future.
- Risk-dashboard, stress-test, and factor-exposure figures are likewise
  **historical estimates** that may not persist out-of-sample.

## Options Lab

- **Options Lab is an educational calculator.** It covers European
  Black–Scholes pricing, Greeks, bisection implied volatility, terminal
  payoff diagrams, and (Phase 14.1) **Cox-Ross-Rubinstein binomial tree**
  pricing with **European/American exercise**. It does **not** fetch live
  option chains, simulate transaction costs or liquidity, produce a volatility
  surface, or backtest option strategies through time.
- **Tree pricing is a numerical approximation, not a production risk engine.**
  The binomial lattice converges to Black–Scholes for European options as the
  step count grows; American exercise is handled by `max(intrinsic,
  continuation)` at each node. It models only a **continuous** dividend yield —
  not discrete dividends or corporate actions — and the price depends on the
  step count, volatility input, and exercise style. The early-exercise
  diagnostic and boundary are teaching aids; the full lattice renders only for
  small trees (≤ 6 steps). No trinomial tree yet (planned), no Heston/SABR.
- **Monte Carlo pricing is an educational simulation with sampling error.** The
  Monte Carlo tab simulates risk-neutral **GBM** paths (constant volatility) to
  price European, arithmetic-average **Asian**, and simple **barrier** options.
  Each price carries Monte Carlo error (reported as standard error + 95% CI) and
  depends on the **seed**, simulation count, and step count. **Barrier
  monitoring is discrete** over the simulated steps (it can differ from
  continuous monitoring). The path preview is a small capped sample (≤ 12 paths)
  — never all paths. No stochastic / local volatility, no jumps, no
  live chains, no production exotic pricing.
- **The volatility surface is a research tool, not a live vol terminal.** The
  Vol Surface tab extracts IV from a **manual or synthetic** chain (no live
  chains), then shows the smile, ATM term structure, skew, and a per-expiry
  **SVI** research fit. Surface quality depends on the input prices, strike/
  expiry coverage, dividends, rates, and solver stability (deep-OTM / short-dated
  IVs are unreliable due to tiny vega). The **SVI fit enforces b ≥ 0, |ρ| < 1,
  σ > 0 but is not guaranteed arbitrage-free**; sparse slices are left unfitted.
  Failed rows are kept with null IV + a warning. No stochastic volatility, no
  Heston/SABR, no production calibration.
- **Payoff diagrams are expiration-only.** They ignore mark-to-market path,
  financing, early assignment, and margin. Unbounded short-option risk is
  labelled where applicable; finite payoff summaries assume the underlying
  cannot go below zero.

## Metrics

- **Annualization is selectable in the main single-asset UI flows.** Backtest
  Studio and Strategy Comparison expose `trading_days_252`, `crypto_365`, or
  `auto`. Portfolio analytics, pairs trading, the CSV Upload UI's simple
  workflow, and SMA research tools still use the existing 252 trading-day
  convention in this version.
- **Risk-free rate is 0** in Sharpe/Sortino (a portfolio-level `risk_free_rate`
  is used in the efficient frontier / optimization Sharpe objective).

## Persistence & platform

- **Local SQLite only — no multi-user auth or cloud sync.** Saved backtests,
  reports, and templates live in a local `backend/data/quantlab.db`. Anyone with
  access to the running app can read/modify/delete them. Single-user, local use
  is the intended model.
- **Settings are browser-local** (`localStorage`); they never change backend
  computation.

## Trust Layer

- **Robustness Lab is a bootstrap, not a tail-risk model.** It resamples the
  observed return history; regime shifts, liquidity shocks, and structural
  breaks absent from the sample cannot appear in the simulation. The A–F grade
  is a labelled heuristic.
- **Sensitivity heatmaps can still overfit.** Choosing the best-performing cell
  after viewing the heatmap is selection bias; the best cell is context, not a
  recommended setting. Stability Lab v1 covers SMA Crossover only.
- **Config hashes fingerprint inputs, not outputs.** External data revisions
  (yfinance) can change results under the same hash; exact reproducibility
  needs dataset version hashing (future). The "permalink" is local-first — no
  public URLs, no replay-by-hash route yet.
- **Daily-bar risk exits are approximations.** Stops/takes execute at daily
  closes in simulation; intraday gaps and stop cascades are not modelled.

## Content Engine

- **Paper replications are simplified unless labelled otherwise.** All v1
  entries are *inspired demos* (single-asset approximations); no page claims
  full replication, and planned papers have no run buttons.
- **Quant Disasters are educational summaries, not forensic reports.** Cases
  use neutral phrasing, simplified mechanisms, and explicit "cannot model yet"
  lists; they are risk education, not historical verdicts.

## Reporting

- **PDF export uses the browser print dialog (v1).** Reports are generated as
  Markdown locally and "PDF" is browser **Print → Save as PDF** — there is no
  server-side PDF renderer. PDF/print output is **text + tables only**; embedded
  chart images are future work.

---

For the full, categorized constraint list (data, engine, metrics, research
tools, frontend) see [`LIMITATIONS.md`](LIMITATIONS.md). For what may come next,
see [`ROADMAP.md`](ROADMAP.md).
