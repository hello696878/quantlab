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

- **No slippage or market-impact model (yet).** Trades are assumed to fill at the
  signal bar's close; large orders moving the market are not simulated.
- **Simplified transaction costs.** A flat bps charge on turnover (`|Δposition|`
  for single-asset, portfolio rebalancing turnover for baskets) — no spreads,
  commissions tiers, or partial fills.
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

## Metrics

- **Annualization is selectable for single-asset backtests and Strategy
  Comparison only.** Use `trading_days_252`, `crypto_365`, or `auto` depending
  on the asset. Portfolio analytics, CSV upload, pairs trading, and SMA research
  tools still use the existing 252 trading-day convention in this version.
- **Risk-free rate is 0** in Sharpe/Sortino (a portfolio-level `risk_free_rate`
  is used in the efficient frontier / optimization Sharpe objective).

## Persistence & platform

- **Local SQLite only — no multi-user auth or cloud sync.** Saved backtests,
  reports, and templates live in a local `backend/data/quantlab.db`. Anyone with
  access to the running app can read/modify/delete them. Single-user, local use
  is the intended model.
- **Settings are browser-local** (`localStorage`); they never change backend
  computation.

## Reporting

- **PDF export uses the browser print dialog (v1).** Reports are generated as
  Markdown locally and "PDF" is browser **Print → Save as PDF** — there is no
  server-side PDF renderer. PDF/print output is **text + tables only**; embedded
  chart images are future work.

---

For the full, categorized constraint list (data, engine, metrics, research
tools, frontend) see [`LIMITATIONS.md`](LIMITATIONS.md). For what may come next,
see [`ROADMAP.md`](ROADMAP.md).
