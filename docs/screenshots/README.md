# Screenshots

UI screenshots for the README. Capture as **PNG**, ideally **1440 × 900** (or similar widescreen) on the dark neon theme. Run with the suggested parameters below so the captures are representative and reproducible.

> Screenshots are illustrative of the UI only — every chart/metric shown must come from a **real backend run** (no fabricated data).

---

## Current screenshots (in this folder)

These are already committed and referenced by the README:

| File | View | Suggested run |
|---|---|---|
| `main-backtest-dashboard.png` | Single-asset Backtest results | `AAPL`, SMA Crossover 50/200, 2015-01-01 → 2024-01-01 |
| `strategy-comparison.png` | Strategy Comparison | `SPY`, 2015-01-01 → 2024-01-01, long-only |
| `sma-parameter-sweep.png` | SMA Parameter Sweep | `AAPL`, fast 10–50, slow 50–200 |
| `train-test-validation.png` | SMA Train/Test Validation | `AAPL`, 2010-01-01 → 2024-01-01, split 2020-01-01 |
| `walk-forward-optimization.png` | SMA Walk-Forward | `SPY`, 2010-01-01 → 2024-01-01, train 504 / test 126 / step 63 |
| `fastapi-docs.png` | Swagger UI at `:8000/docs` | endpoints grouped by tag, one expanded |

---

## Recommended additional screenshots (TODO)

The platform has grown well beyond the captures above. Adding the following would make the README fully represent the current product. Filenames are referenced (as TODO) in the README Screenshots section.

| File | View | Suggested run / what to show |
|---|---|---|
| `command-center.png` | Home / Command Center | Default landing view — quick actions, recent saved backtests/reports, system status, feature map (have a couple of saved items so recents are populated) |
| `backtest-neon-chart.png` | Backtest equity + drawdown | `SPY`, SMA 20/100, 2015-01-01 → 2023-12-31 — focus on the neon equity curve, glow line, dashed benchmark, and drawdown chart |
| `custom-strategy-builder.png` | Custom Strategy Builder | Load the *Momentum + Trend* gallery template; show entry/exit rule rows + a result |
| `portfolio-efficient-frontier.png` | Portfolio Lab → Efficient Frontier | `SPY, QQQ, GLD, TLT`, 2015-01-01 → 2023-12-31, rf 0.02, 2,000 portfolios — scatter with min-vol / max-Sharpe / equal-weight highlighted |
| `portfolio-risk-dashboard.png` | Portfolio Lab → Risk Dashboard | `SPY, QQQ, GLD, TLT` — correlation heatmap + risk-contribution table |
| `stress-test.png` | Portfolio Lab → Stress Test | `SPY, QQQ, GLD, TLT` with COVID Crash + 2022 Rate-Hike scenarios |
| `factor-analysis.png` | Portfolio Lab → Factor Analysis | `SPY, QQQ, GLD, TLT` vs Core ETF Factors — beta table + actual-vs-fitted curve |
| `saved-reports.png` | Saved Reports gallery | A few saved reports listed; optionally a report opened in the reader |
| `command-palette.png` | Command palette (Ctrl/Cmd+K) | Open with a query like `momentum` or `risk` showing commands + saved resources grouped |

Optional: a theme-variant capture (e.g. the **Risk** red accent) and a guided-demo/onboarding card shot.

---

## How to capture

### Local dev

1. Start the backend: `cd backend && python -m uvicorn app.main:app --reload --port 8000`
2. Start the frontend: `cd frontend && npm run dev`
3. Open <http://localhost:3000>, run the suggested parameters, capture with your OS tool or browser dev tools (device toolbar at 1440×900).

### Docker

```bash
docker compose up --build
# open http://localhost:3000
```

### Referencing in the README

```markdown
### Command Center
![Command Center](docs/screenshots/command-center.png)
```
