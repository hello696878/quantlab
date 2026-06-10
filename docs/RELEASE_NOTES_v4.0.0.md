# QuantLab v4.0.0 — Local-First Quant Research Terminal

> **Research only.** QuantLab is an educational/research tool. It does **not**
> place trades, connect to a broker, or provide investment advice.

## Summary

QuantLab v4.0.0 is the first public, portfolio-ready release — a full local-first
quantitative research platform you run on your own machine. A **FastAPI** backend
computes every backtest, optimization, and risk metric on **real historical price
data** (yfinance daily OHLCV, or your own CSV uploads) with no lookahead bias; a
**Next.js / React / TypeScript** frontend gives you an interactive neon "quant
terminal" to explore strategies, build your own with no code, run portfolio
analytics, and export branded research reports. Saved backtests, strategies, and
reports persist in a **local SQLite** database — no account, no cloud, no
telemetry.

## Highlights

- **Command Center** home dashboard with guided demos, a command palette, and global search (`Ctrl/Cmd + K`).
- **Single-asset backtesting** across six strategies, with **long / short / long-short** modes and a lookahead-bias-free engine.
- **Research tools** — Strategy Comparison, Parameter Sweep, Train/Test, and Walk-Forward validation.
- **Custom Strategy Lab** — a no-code rule builder (no `eval`), saved templates with JSON import/export, and a built-in gallery.
- **Portfolio Lab** — equal-weight backtesting, optimization, walk-forward optimization, efficient frontier, risk dashboard, stress testing, and factor analysis.
- **Reporting** — Markdown and PDF/print export with four branded templates, plus a saved-reports gallery.
- **Polished UX** — neon theme & charts, toast notifications, an app-level error boundary, and consistent loading / empty / offline states.
- **Local-first & honest** — local SQLite persistence, clear in-app caveats, and a friendly "Backend offline" recovery experience.

## Demo workflow (≈5–8 min)

1. Open the **Command Center**; note the recents and live system status.
2. Run a **backtest** — `SPY · SMA Crossover 20/100 · 2015-01-01 → 2023-12-31 · 100,000 · 10 bps · long_only` — and view the neon equity/drawdown charts.
3. **Save** the backtest, then **export** a Markdown / PDF report (try the *Quant Tear Sheet* template).
4. Open the **Portfolio Lab** with `SPY, QQQ, GLD, TLT` (2015-01-01 → 2023-12-31); run the **Efficient Frontier** (rf 0.02, 2,000 portfolios) and the **Risk Dashboard**.
5. Press **`Ctrl/Cmd + K`** and search for your saved report.
6. Close on the architecture — local SQLite + FastAPI + Next.js.

The full script is in [`docs/DEMO_SCRIPT.md`](DEMO_SCRIPT.md).

## Quick start

**Docker (recommended)**

```bash
docker compose up --build
# Frontend  http://localhost:3000
# Backend   http://localhost:8000   (docs at /docs)
```

**Local dev**

```bash
# backend
cd backend
python -m uvicorn app.main:app --reload --port 8000

# frontend (second terminal)
cd frontend
npm install
npm run dev
```

## Testing

```bash
# backend — 980+ tests across 48 files, synthetic data (no network)
cd backend
python -m pytest -q

# frontend — type check + production build
cd frontend
npx tsc --noEmit
npm run build
```

A full pre-release checklist is in [`docs/RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md).

## Known limitations

- **Research only — not investment advice.** No live trading, no broker integration.
- **Data:** yfinance daily data (no SLA, possible gaps/anomalies; not survivorship-bias-free; no intraday/tick).
- **Execution realism:** flat-bps turnover cost only — no slippage or market-impact model yet.
- **Short selling is simplified:** no borrow fees, margin, liquidation, or funding modelled (`|position| ≤ 1`, no leverage).
- **Portfolio optimization is historical / in-sample** and can overfit — descriptive, not a forecast.
- **Annualization** defaults to 252 trading days, with selectable `crypto_365` and `auto` conventions for single-asset Backtest and Strategy Comparison runs.
- **Local SQLite only** — single-user, no authentication or cloud sync.
- **PDF export** uses the browser print dialog (text + tables; embedded chart images are future work).

See [`docs/KNOWN_ISSUES.md`](KNOWN_ISSUES.md) and [`docs/LIMITATIONS.md`](LIMITATIONS.md) for the full list.

## Screenshots

A grouped gallery is in the [README](../README.md#screenshots); source images and
capture parameters are in [`docs/screenshots/`](screenshots/README.md). Featured
views:

- Command Center — `docs/screenshots/command-center.png`
- Backtest neon charts — `docs/screenshots/backtest-neon-chart.png`
- Strategy Comparison — `docs/screenshots/strategy-comparison.png`
- Custom Strategy Builder — `docs/screenshots/custom-strategy-builder.png`
- Efficient Frontier — `docs/screenshots/portfolio-efficient-frontier.png`
- Risk Dashboard — `docs/screenshots/portfolio-risk-dashboard.png`
- Stress Test — `docs/screenshots/portfolio-stress-test.png`
- Factor Analysis — `docs/screenshots/factor-analysis.png`
- Saved Reports — `docs/screenshots/saved-reports.png`
- Command Palette — `docs/screenshots/command-palette.png`
- Settings & Theme — `docs/screenshots/settings-theme.png`

## Future roadmap

Candidate next stages (not commitments):

1. **v4.0 → release polish** — hosted demo, image hardening, richer PDF reports with embedded charts.
2. **Quant research depth** — slippage / market-impact modelling, robust crypto (365-day) annualization, more data-provider integrations, and advanced models.
3. **Commercialization foundation** *(only if pursued)* — optional user auth / multi-user. Broker / live-trading remains far-future and out of scope for a research tool.

See [`docs/ROADMAP.md`](ROADMAP.md) and [`CHANGELOG.md`](../CHANGELOG.md).

---

_QuantLab is a learning and research project. Nothing here constitutes investment
advice; past simulated performance does not predict future results._
