# QuantLab — Screenshot Plan (v4.0 RC)

The capture list for release/portfolio screenshots. Capture as **PNG** on the
dark neon theme at **~1440 × 900**, using the parameters below so each shot is
representative and reproducible. Save into `docs/screenshots/`.

> Every chart/metric shown must come from a **real backend run** — no fabricated
> data. The existing committed captures are listed in
> [`screenshots/README.md`](screenshots/README.md); this plan is the target set
> for the release.

**Setup:** run the stack and pre-create a few saved backtests/reports/templates
so the Command Center, Saved Reports, and Command Palette have real content.

---

| # | Page / view | Parameters | What should be visible | Filename |
|---|---|---|---|---|
| 1 | **Command Center** (Home) | — (have ≥2 saved backtests + ≥1 saved report) | Quick actions, recent saved backtests/reports, system status (API **ONLINE**), feature map | `command-center.png` |
| 2 | **Backtest** results | SPY · SMA Crossover 20/100 · 2015-01-01 → 2023-12-31 · 100,000 · 10 bps · long_only | Metrics grid + neon equity curve (glow line vs dashed benchmark) + drawdown chart | `backtest-neon-chart.png` |
| 3 | **Strategy Comparison** | SPY · 2015-01-01 → 2023-12-31 · long-only | All five strategies side by side with the ranking summary; mode badge | `strategy-comparison.png` |
| 4 | **CSV Backtest** | Upload a `date,close` CSV · SMA Crossover | Upload dropzone with a parsed file + a real result (metrics + equity curve); "CSV backtest complete" toast if timed | `csv-upload.png` |
| 5 | **Custom Strategy Builder** | Load gallery template *Momentum + Trend*, then Run | Entry/exit rule rows, ALL/ANY logic, and a result below | `custom-strategy-builder.png` |
| 6 | **Portfolio Lab → Efficient Frontier** | SPY, QQQ, GLD, TLT · 2015-01-01 → 2023-12-31 · rf 0.02 · 2,000 portfolios | Scatter (x=vol, y=return) with min-vol / max-Sharpe / equal-weight highlighted + weight cards | `portfolio-efficient-frontier.png` |
| 7 | **Portfolio Lab → Risk Dashboard** | SPY, QQQ, GLD, TLT · 2015-01-01 → 2023-12-31 | Correlation heatmap (neon tiles), diversification ratio, risk-contribution table | `portfolio-risk-dashboard.png` |
| 8 | **Portfolio Lab → Stress Test** | Basket + COVID Crash + 2022 Rate-Hike scenarios | Scenario-comparison table, selected scenario equity vs benchmark, per-scenario correlation heatmap | `portfolio-stress-test.png` |
| 9 | **Portfolio Lab → Factor Analysis** | Basket vs Core ETF Factors (SPY/QQQ/IWM/TLT/GLD) | R²/alpha/residual-vol/largest-exposure cards, beta table, actual-vs-fitted curve | `factor-analysis.png` |
| 10 | **Saved Reports** gallery | — (have ≥2 saved reports) | The saved-reports list; optionally a report opened in the reader | `saved-reports.png` |
| 11 | **Command Palette** (Ctrl/Cmd + K) | Query `momentum` or `risk` | Palette open showing commands + grouped saved resources (backtests/reports/templates) | `command-palette.png` |
| 12 | **Settings → Appearance** | Select an accent (e.g. **Risk** red or **violet**) | Theme controls with the whole app re-skinned to the chosen accent | `settings-theme.png` |

---

## How to capture

1. Start the stack: `docker compose up --build` (or `uvicorn` + `npm run dev`).
2. Set the browser/device toolbar to 1440×900.
3. Run each view with the parameters above, wait for the real result, capture.
4. Save into `docs/screenshots/` with the suggested filename and reference it in
   the README Screenshots section, e.g.:

```markdown
### Command Center
![Command Center](docs/screenshots/command-center.png)
```

**Optional extras:** a guided-demo/onboarding card shot and an **offline UX**
shot (stop the backend, open Saved Reports to show the friendly *Backend offline*
panel) make good "honest engineering" additions.
