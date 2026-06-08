# Changelog

All notable changes to QuantLab are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project aims
to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Research only.** QuantLab is an educational/research tool — it does not place
> trades, connect to a broker, or provide investment advice.

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
