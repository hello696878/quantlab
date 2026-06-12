# QuantLab — Screenshot Plan (showcase refresh)

The capture checklist for release/portfolio screenshots. Capture as **PNG** on
the dark neon theme at **~1440 × 900**, save into `docs/screenshots/`, and
reference from the README Screenshots section.

> **Honesty rule:** every chart/metric shown must come from a **real backend
> run** — no fabricated data, no mocked screenshots. If a capture is not done
> yet its status below says **pending**; the README says so too.

**Global setup:** run the stack, pre-create ≥2 saved backtests and ≥1 saved
report so recents/search have content. For every shot, avoid: loading
spinners, error toasts, personal local paths, raw JSON, and empty states
(unless the shot is *about* an empty/offline state).

---

## Capture checklist

| # | Filename | View | Setup | Must show | Avoid | Status |
|---|---|---|---|---|---|---|
| 1 | `command-center.png` | Command Center | ≥2 saved backtests, ≥1 report | Hero CTAs, Trust Layer grid, Content Engine cards, Platform Direction chips, recents, API **ONLINE** | stale counts | **recapture** (pre-13.3 version committed) |
| 2 | `backtest-simulation-settings.png` | Backtest form | SMA · SPY · scroll to controls | Cost Model, Position Sizing, Risk Management, Annualization, Benchmark, Robustness + Stability toggles | validation errors | pending |
| 3 | `backtest-neon-chart.png` | Backtest result | SPY · SMA 20/100 · 2015→2023 · 10 bps · long_only | Metrics grid + neon equity vs labelled benchmark + drawdown | — | captured (v4.0) |
| 4 | `benchmark-visualization.png` | Backtest result | Same run, benchmark Buy & Hold; scroll to benchmark cards | Benchmark Comparison card (alpha/beta/TE/IR) + cumulative excess return chart | — | pending |
| 5 | `robustness-lab.png` | Backtest result | Same run + robustness ON (1,000 sims · seed 42) | P(loss), percentile stats, final-return histogram, heuristic grade chip | — | pending |
| 6 | `stability-heatmap.png` | Backtest result | Same run + Stability Lab ON (Sharpe metric) | Heatmap with 20/100 ring-highlighted, ★ best cell, stability score, fragility/stable note | — | pending |
| 7 | `strategy-comparison.png` | Strategy Comparison | SPY · 2015→2023 · simulation settings visible | Ranked table + applied-assumptions summary + "vs Benchmark" toggle | — | **recapture** (pre-12.3.1 version committed) |
| 8 | `strategy-library.png` | Strategy Library | Open SMA Crossover detail | Hypothesis/Signal Logic/Failure Modes sections + Live badge + related papers/disasters | — | pending |
| 9 | `paper-replications.png` | Paper Replications | Index or Jegadeesh–Titman detail | Status + **Inspired Demo** badges, "not a full replication" caveat | implying full replication | pending |
| 10 | `quant-disasters.png` | Quant Disasters | Open LTCM detail | "What a naive backtest might miss" + Trust-Layer checklist with **Not yet** badges | sensational framing | pending |
| 11 | `report-pdf.png` | Report print preview | Saved SPY run with benchmark+robustness+stability · Export PDF | Structured sections (Simulation Settings, Data Quality, Benchmark, Robustness, Stability, Reproducibility) | raw JSON, letter-wrapped labels | pending |
| 12 | `saved-backtests.png` | Saved Backtests detail | Open the saved SPY run | Config-hash pill, benchmark charts, robustness/stability cards persisted | — | pending |
| 13 | `portfolio-efficient-frontier.png` | Portfolio Lab | SPY/QQQ/GLD/TLT · rf 0.02 · 2,000 portfolios | Frontier scatter + highlighted portfolios + weight cards | — | captured (v4.0) |
| 14 | `portfolio-risk-dashboard.png` | Portfolio Lab | Same basket | Correlation heatmap, diversification ratio, risk contributions | — | captured (v4.0) |
| 15 | `command-palette.png` | Palette (Ctrl/Cmd+K) | Query `ltcm` or `robustness` | Content-engine + trust-layer commands grouped with saved resources | — | **recapture** (new command groups) |
| 16 | `settings-theme.png` | Settings | Pick an accent | Theme re-skin | — | captured (v4.0) |

Legacy v4.0 captures not listed above (CSV upload, builder, stress test, factor
analysis, sweep/validation, FastAPI docs, saved reports) remain valid and
committed.

---

## How to capture

1. Start the stack: `docker compose up --build` (or `uvicorn` + `npm run dev`).
2. Set the browser/device toolbar to 1440×900.
3. Run each view with the parameters above, wait for the real result, capture.
4. Save into `docs/screenshots/`, update `docs/screenshots/README.md` with the
   capture parameters, and reference the file from the README:

```markdown
### Robustness Lab
![Robustness Lab](docs/screenshots/robustness-lab.png)
```

**Optional extras:** an offline-UX shot (backend stopped → friendly offline
panel) and a fragility-warning Stability shot make good "honest engineering"
additions.
