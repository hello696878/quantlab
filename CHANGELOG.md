# Changelog

All notable changes to QuantLab are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project aims
to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Research only.** QuantLab is an educational/research tool — it does not place
> trades, connect to a broker, or provide investment advice.

---

## Unreleased — Options & Volatility Lab v1

### Added

- **Options Lab** workspace with European Black–Scholes pricing, Greeks,
  bisection implied-volatility solving, and single/multi-leg expiration payoff
  diagrams.
- Deterministic backend endpoints: `POST /options/black-scholes`,
  `POST /options/implied-volatility`, and `POST /options/payoff`.
- CRR binomial tree endpoints for European/American exercise:
  `POST /options/binomial` and `POST /options/tree-convergence`, with small
  lattice visualization capped for readability.
- Monte Carlo GBM endpoint `POST /options/monte-carlo` for European,
  arithmetic-average Asian, and simple discretely monitored barrier payoffs,
  with seed reproducibility, standard error, 95% confidence interval, and capped
  path preview.
- Volatility surface endpoints `POST /options/surface` and
  `POST /options/surface/sample` for manual/synthetic option chains, per-row IV
  extraction, smile/skew/ATM term structure, moneyness × expiry heatmap, and SVI
  research fit.
- Heston stochastic-volatility endpoint `POST /options/heston` for educational
  full-truncation Euler Monte Carlo European pricing with standard error, 95%
  confidence interval, Feller-condition warning, Black-Scholes reference, and
  capped price/volatility path preview.
- Strategy payoff presets for long call/put, covered call, protective put,
  bull/bear spreads, straddles, and strangles.
- Dashboard, sidebar, command-palette/search, Black–Scholes paper, and
  Volmageddon cross-links.

### Fixed

- Strategy Comparison is now placed beside Backtest and Strategy Library in
  the sidebar; the fixed desktop rail scrolls vertically on shorter screens.
- Global Markets Globe API payloads reject non-finite values and the frontend
  validates the complete static dossier schema before using backend data.

### Limitations

- Educational calculator only: American exercise is limited to the simplified
  CRR tree model, GBM Monte Carlo is constant-volatility with sampling error,
  and Heston is an uncalibrated Euler simulator; no live option chains, broker
  integration, assignment, discrete-dividend/corporate-action modelling,
  transaction-cost/liquidity modelling, or arbitrage-free production volatility
  calibration.

---

## v4.7.0 — Showcase Candidate — 2026-06-13

This candidate packages QuantLab as a portfolio-ready local research showcase:
the core backtesting/research stack is stable, the Trust Layer is visible in
results and reports, and the Content Engine explains strategies, papers, and
failure modes without pretending planned work is already built.

### Added

**Trust Layer v1**
- Data-quality diagnostics, benchmark analytics/visualization, reproducible
  SHA-256 config hashes, Robustness Lab bootstrap diagnostics, and Stability
  Lab SMA parameter-sensitivity heatmaps.
- Report/export integration for trust diagnostics and caveats, so saved and
  downloaded research remains auditable.

**Content Engine v1**
- Strategy Library pages for live strategies plus honest planned/research
  catalog entries with no run buttons until the backend exists.
- Paper Replications pages with clearly labelled inspired demos, not full
  academic replications.
- Quant Disasters case studies that connect backtest limitations to real risk
  mechanisms and explicit "cannot model yet" lists.
- Command Center content hub, global-search access, and release screenshot/demo
  plans for the showcase flow.

### Changed

- README, release checklist, demo script, screenshot plan, limitations, and
  known-issues docs refreshed for v4.7 showcase readiness.
- Command Palette search now opens all existing educational registry pages
  (including planned Strategy Library / Paper Replication entries) while keeping
  runnable commands limited to implemented strategies and safe demo presets.
- Test-count references updated to the current 1,060+ backend tests across 53
  files.

### Limitations

- Still **research only**: no live trading, broker connection, account system,
  cloud sync, billing, or AI copilot.
- yfinance/CSV daily data only; no survivorship-bias-free institutional data,
  intraday/tick data, or live feeds.
- Cost modelling is static bps/commission/slippage/spread; there is no
  size-dependent market-impact, partial-fill, order-book, borrow, margin, or tax
  simulator.
- Browser print-to-PDF remains the PDF export path; embedded chart images in
  reports are future work.

---

## v4.0.0 — Local-First Quant Research Terminal — 2026-06-08

The first public, portfolio-ready release: a full local-first quantitative
research platform (FastAPI backend · Next.js frontend · local SQLite), with a
neon "quant terminal" UI, single-asset and portfolio analytics, a no-code
strategy builder, branded reporting, and a polished command-center experience.

### Added

**Product experience**
- **Command Center** — local-first home dashboard (quick actions, recent saved work, system status, feature map).
- **Guided Demo Mode** — onboarding card + prefilled demo presets that never auto-run, plus a local quick-start checklist.
- **Command Palette / Global Search** — `Ctrl/Cmd + K` to navigate and search commands plus real saved backtests, reports, and templates.
- **Neon theme & neon chart system** — CSS-variable accent theme (six accents incl. a Risk mode) and accent-aware glowing equity/drawdown/heatmap charts.
- **Toast notifications**, an app-level **error boundary**, and consistent **loading / empty / offline** state primitives.
- **App Settings** — local (browser) defaults for capital, cost, benchmark, date range, accent theme, and report template.

**Strategy research**
- **Single-asset backtesting** with a vectorised, lookahead-bias-free engine (one-day signal shift).
- Strategies: **SMA Crossover, RSI Mean Reversion, Bollinger Band, Time-Series Momentum, Volatility Breakout, Pairs Trading**.
- **Long / short / long-short** direction modes (SMA, Momentum, Volatility Breakout) with diagnostics and a short-selling warning.
- **Strategy Comparison** and **Research tools** — Parameter Sweep, Train/Test validation, Walk-Forward validation.
- **CSV Upload Backtesting** — run strategies on your own daily price CSV.

**Custom strategy lab**
- **Custom Strategy Builder** — no-code entry/exit rule builder over whitelisted indicators (no `eval`).
- **Saved strategy templates** with JSON **import / export**, and a built-in **Strategy Template Gallery**.

**Portfolio lab**
- **Portfolio Backtesting** (equal-weight, turnover-based rebalancing costs).
- **Portfolio Optimization** (min-volatility / max-Sharpe, long-only) and **Walk-Forward Portfolio Optimization** (out-of-sample).
- **Efficient Frontier**, **Risk Dashboard**, **Stress Testing**, and **Factor Analysis**.

**Reporting & persistence**
- **Markdown** and **PDF / print** report export with four **branded report templates**.
- **Saved Reports Gallery** and **Saved Backtests**, persisted in local SQLite.

**Platform**
- **Docker / Docker Compose** one-command stack and **GitHub Actions CI** (backend tests + frontend build).

### Changed
- **README and docs refreshed** — local-first positioning, categorized feature overview, screenshot gallery, and release/QA docs.
- **UI upgraded** to the neon quant-terminal style across every workspace.
- **Default parameters calibrated** for demo usability (clearly not tuned for returns, and not recommendations).
- **Offline UX improved** — friendly "Backend offline" panels with Retry instead of raw HTTP errors, de-duplicated offline notifications.

### Limitations
- **Research only — not investment advice**; **no live trading** and **no broker integration**.
- **yfinance data limitations** (no SLA, possible gaps/anomalies; not survivorship-bias-free; daily only).
- **Local SQLite only** — single-user, no authentication, no cloud sync.
- **Short selling is simplified** — no borrow fees, margin, liquidation, or funding modelled (`|position| ≤ 1`).
- **Portfolio optimization is historical / in-sample** and can overfit; it does not forecast future performance.
- **PDF export** is browser print-to-PDF (text + tables; embedded chart images are future work).

See [`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md) and [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) for the full, categorized list.

---

_Earlier development progressed through phases 0–11 (backend MVP → strategies →
research tools → portfolio lab → reporting → settings/theme → long/short →
Command Center / palette / search → toasts, error boundary, state polish →
release prep). See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the full history._
