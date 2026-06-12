# QuantLab — Demo Script (8–12 minutes)

A polished walkthrough for a portfolio showcase or screen recording. It moves
from the Command Center → a real backtest with the Trust Layer → reporting →
strategy comparison → the Content Engine, and closes on the roadmap. Every
number shown is a **real backend run** — nothing is faked, and nothing planned
is presented as built.

**Before you start**
- Run the stack (`docker compose up --build`, or `uvicorn` + `npm run dev`).
- Have **at least one saved backtest and one saved report** already stored so the
  Command Center recents and global search have content. (Tip: run steps 3–6
  once beforehand.)
- Optional: set the accent theme you like in **Settings** (the **cyan** default
  or the **Risk** red read well on camera).

**Reusable parameters**

| Backtest | Portfolio |
|---|---|
| ticker **SPY** | tickers **SPY, QQQ, GLD, TLT** |
| strategy **SMA Crossover** | range **2015-01-01 → 2023-12-31** |
| range **2015-01-01 → 2023-12-31** | risk-free **0.02** |
| fast **20** / slow **100** | num portfolios **2000** |
| capital **100,000** · cost **10 bps** | |
| position mode **long_only** | |

---

## The flow

### Demo 1 · Command Center (~60s)
Load <http://localhost:3000>. Point out the four pillars on the hub: **research
workflows** (hero CTAs + quick actions), the **Trust Layer** grid, the
**Content Engine** cards (Strategy Library · Paper Replications · Quant
Disasters, with live counts), and **saved research** (recents + system status
from local SQLite). Scroll to the **Platform Direction** panel.
> "QuantLab opens on a research hub. Everything is local-first, and the
> direction panel is honest — only items marked Built exist."

### Demo 2 · Backtest Studio (~90s)
Go to **Backtest**. Set: **SMA Crossover · SPY · 2016-01-01 → present · cost
model Simple 10 bps · position sizing Full Allocation · risk management None ·
annualization trading_days_252 · benchmark Buy & Hold Same Asset**. Click
**Run**.
Walk the result top-down: **metrics grid**, the **neon equity curve vs the
labelled benchmark**, the **drawdown overlay**, the **cumulative excess return**
chart, the **Benchmark Comparison** card (alpha/beta/correlation/tracking
error/information ratio), the **Data Source** card, and the **Reproducibility**
card.
> "Real yfinance data, one-day signal shift — no lookahead. Every result
> carries its data quality and a SHA-256 config hash: same normalized config,
> same hash."

### Demo 3 · Trust Layer (~90s)
Re-run the same backtest with **Run robustness analysis** and **Run Stability
Lab** enabled (defaults: 1,000 sims · block 5 · seed 42).
Show the **Robustness Lab** card — probability of loss, percentile ranges, the
final-return histogram, and the **heuristic grade** — then the **Stability
Lab** heatmap with the selected 20/100 cell ring-highlighted.
> "Robustness resamples *returns*; stability varies *parameters*. Broad stable
> regions beat isolated spikes — and both cards say plainly they're
> diagnostics, not guarantees."

### Demo 4 · Report Export (~45s)
**Save** the backtest (toast confirms), then **Export Report** → PDF
print-preview. Scroll the structured sections: Metadata, Simulation Settings,
Data Quality, Benchmark Comparison, Robustness Lab, Stability Lab,
Reproducibility, Risk/Caveats.
> "The report carries the assumptions and the caveats — including the config
> hash — so the research is auditable. No raw JSON anywhere."

### Demo 5 · Strategy Comparison (~60s)
Open **Strategy Comparison**. Point at the **Simulation Settings** (cost,
sizing, risk, annualization, benchmark applied to all five strategies), run on
SPY, and show the ranked table plus the **"vs Benchmark"** toggle
(excess/alpha/beta/IR columns).
> "Five strategies under identical assumptions — and mean-reversion strategies
> that can't short are labelled, not silently skipped."

### Demo 6 · Content Engine (~90s)
Open **Strategy Library** → SMA Crossover (hypothesis, parameters, failure
modes, trust checklist, related papers/disasters). Open **Paper Replications**
→ Jegadeesh–Titman (point at the **Inspired Demo** badge and the "not a full
replication" caveats). Open **Quant Disasters** → LTCM (the "what a naive
backtest might miss" section and the honest "cannot model yet" list).
> "The platform teaches how strategies work, where the ideas came from, and how
> they fail — with the same honesty rules as the engine."

### Demo 7 · Portfolio Studio (~60s, optional)
Open **Portfolio Lab**: run the **Efficient Frontier** (SPY/QQQ/GLD/TLT · rf
0.02 · 2,000 portfolios) and glance at the **Risk Dashboard** heatmap.
> "Multi-asset analytics with the same in-sample honesty caveats."

### Demo Close · Roadmap (~30s)
Return to the Command Center's **Platform Direction** panel (or open
`docs/ROADMAP.md`).
> "Next up per the blueprint: an Options & Volatility Lab, event-driven and
> arbitrage modules, an ensemble builder, a microstructure/HFT teaching lab,
> an explainer copilot, and 3D visualization — all clearly marked planned or
> future, none claimed as built. Under the hood it's FastAPI + Next.js +
> local SQLite: research software, not a trading system."

---

## Optional add-ons (if you have extra time)
- **Guided demos / onboarding** — show a preset chip prefilling the form
  (never auto-runs); run the BTC-USD crypto momentum demo with **auto**
  annualization resolving to crypto 365.
- **Command palette** — Ctrl/Cmd+K, search `LTCM`, `robustness`, or a saved
  report name; everything is reachable from the keyboard.
- **Custom Strategy Builder** — load the *Momentum + Trend* gallery template and run it (no-code rules, no `eval`).
- **Stress Test** — run COVID Crash + 2022 Rate-Hike on the basket.
- **Offline UX** — stop the backend and open Saved Reports to show the friendly **Backend offline** panel with **Retry** (graceful, not a crash).
- **Theme** — switch the accent in Settings to show the whole app re-skin instantly.

## Tips
- Keep the window at ~1440×900 for clean charts.
- Pre-run steps 3–6 so recents/search have content on camera.
- If a run shows few/zero trades, that's expected for long-only in a downtrend —
  mention it rather than hiding it; it's an honest behavior, not a bug.
