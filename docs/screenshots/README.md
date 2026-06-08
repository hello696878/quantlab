# Screenshots

UI screenshots for the README, captured on the dark neon theme (PNG, ~1440 × 900). Every image is a **real backend run** on real historical data — no mock data.

The **README showcase set** below is embedded in the main [README](../../README.md#screenshots), grouped by workflow. The **additional captures** (research tools + API docs) are kept here for reference.

> Reproduce a capture by running the stack and using the listed demo parameters. Have a few saved backtests/reports/templates stored first so the Command Center, Saved Reports, and Command Palette show real content.

---

## README showcase set

| Filename | Page / workflow | Demo parameters | Demonstrates |
|---|---|---|---|
| `command-center.png` | Command Center (Home) | — (≥2 saved backtests, ≥1 saved report) | Local-first home dashboard: hero + badges, welcome/guided demos, quick-start checklist, recent saved work, system status, quick actions |
| `backtest-neon-chart.png` | Backtest results | SPY · SMA Crossover 20/100 · 2015-01-01 → 2023-12-31 · 100,000 · 10 bps · long_only | Neon equity curve (strategy vs dashed benchmark) + semantic-red drawdown chart |
| `strategy-comparison.png` | Strategy Comparison | SPY · 2015-01-01 → 2023-12-31 · long-only | Built-in single-asset strategies compared and ranked on one ticker |
| `custom-strategy-builder.png` | Custom Strategy Builder | Load gallery template *Momentum + Trend*, then Run | No-code entry/exit rule builder (whitelisted indicators, no `eval`) with a result |
| `portfolio-efficient-frontier.png` | Portfolio Lab → Efficient Frontier | SPY, QQQ, GLD, TLT · 2015-01-01 → 2023-12-31 · rf 0.02 · 2,000 portfolios | Risk–return scatter coloured by Sharpe with min-vol / max-Sharpe / equal-weight portfolios + weights |
| `portfolio-risk-dashboard.png` | Portfolio Lab → Risk Dashboard | SPY, QQQ, GLD, TLT · 2015-01-01 → 2023-12-31 | Correlation heatmap, diversification ratio, per-asset risk contribution |
| `portfolio-stress-test.png` | Portfolio Lab → Stress Test | Basket + COVID Crash + 2022 Rate-Hike scenarios | Historical stress-window behaviour vs benchmark, scenario table + correlation heatmap |
| `factor-analysis.png` | Portfolio Lab → Factor Analysis | Basket vs Core ETF Factors (SPY/QQQ/IWM/TLT/GLD) | OLS factor-exposure regression: betas, alpha, R², actual-vs-fitted curve |
| `saved-reports.png` | Saved Reports gallery | — (≥2 saved reports) | Local report gallery — Markdown reports stored in SQLite, reopen / download / print |
| `command-palette.png` | Command Palette (Ctrl/Cmd + K) | Query e.g. `momentum` or `risk` | Global palette/search across navigation, demos, and real saved resources |
| `settings-theme.png` | Settings → Appearance | Pick an accent (e.g. **Blue** / **Risk**) | Local preferences + CSS-variable neon accent theme (six accents) |

---

## Additional captures (reference)

Earlier captures of the research tools and API docs, retained for reference:

| Filename | Page / workflow | Demo parameters | Demonstrates |
|---|---|---|---|
| `main-backtest-dashboard.png` | Backtest results (earlier) | AAPL · SMA 50/200 · 2015-01-01 → 2024-01-01 | Full backtest dashboard (metrics + charts + trade log) |
| `sma-parameter-sweep.png` | Research → SMA Parameter Sweep | AAPL · fast 10–50 · slow 50–200 | Grid search over fast/slow windows ranked by Sharpe/CAGR/Calmar |
| `train-test-validation.png` | Research → Train/Test Validation | AAPL · 2010-01-01 → 2024-01-01 · split 2020-01-01 | In-sample vs out-of-sample metrics + degradation |
| `walk-forward-optimization.png` | Research → Walk-Forward | SPY · 2010-01-01 → 2024-01-01 · train 504 / test 126 / step 63 | Stitched out-of-sample equity + parameter stability |
| `fastapi-docs.png` | Swagger UI (`:8000/docs`) | — | Auto-generated API docs grouped by tag |

---

## How to capture

1. Start the stack: `docker compose up --build` (or `uvicorn` + `npm run dev`).
2. Set the browser/device toolbar to ~1440 × 900.
3. Run the listed parameters, wait for the real result, and capture.
4. Save into this folder with the listed filename and reference it from the README, e.g.:

```markdown
### Command Center
![Command Center](docs/screenshots/command-center.png)
```

See [`../SCREENSHOT_PLAN.md`](../SCREENSHOT_PLAN.md) for the per-shot capture plan.
