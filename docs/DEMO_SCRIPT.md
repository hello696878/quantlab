# QuantLab — Demo Script (5–8 minutes)

A polished walkthrough for a portfolio showcase or screen recording. It moves
from the landing dashboard → a real backtest → reporting → portfolio analytics →
the command palette, and closes on the architecture. Every number shown is a
**real backend run** — nothing is faked.

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

### 1 · Open the Command Center (~30s)
Load <http://localhost:3000>. Point out the **Command Center**: quick actions,
**recent saved backtests/reports** (real, from local SQLite), **system status**
(API **ONLINE**, local mode, live counts), and the **feature map**.
> "QuantLab opens on a command center — everything here is local-first; the
> recents and counts come straight from a local SQLite database."

### 2 · Show guided demo mode (~30s)
Point to the **Welcome / guided demos**. Hover a preset and note it **prefills,
never auto-runs**.
> "First-time users get guided demos. They load real parameters into the form —
> but nothing runs until you click Run, so there's no fake data."

### 3 · Run an SPY SMA backtest (~60s)
Go to **Backtest**. Enter the backtest parameters above and click **Run**.
> "Real historical data via yfinance, one-day signal shift so there's no
> lookahead bias."

### 4 · Show the neon equity curve (~45s)
Walk through the results: **metrics grid** (CAGR, Sharpe, Sortino, max drawdown),
the **neon equity curve** (glowing strategy line vs dashed buy-&-hold benchmark),
the **drawdown** chart, and the **trade log**.
> "The whole UI is a neon quant-terminal theme; the charts pick up the accent
> color, while semantic colors — green/red — stay fixed for readability."

### 5 · Save the backtest (~20s)
Click **Save backtest**, give it a name → a **toast** confirms it's stored. Note
it now appears under Saved Backtests and on the Command Center recents.

### 6 · Export a Markdown / PDF report (~45s)
On the result, pick a **report template** (e.g. *Quant Tear Sheet*), click
**Export Report** (Markdown downloads), then **Export PDF** → the print-preview
opens (browser **Print → Save as PDF**). Optionally **Save Report**.
> "Reports are generated locally in the browser from the result on screen —
> four branded templates, Markdown or print-to-PDF, nothing uploaded."

### 7 · Open the Portfolio Lab (~30s)
Go to **Portfolio Backtest**. Enter the portfolio basket and run the
**Equal-Weight Backtest** (monthly rebalance).
> "Same engine, multi-asset: equal-weight with turnover-based rebalancing costs."

### 8 · Run the Efficient Frontier (~45s)
Switch to the **Efficient Frontier** tab; run with rf **0.02**, **2000**
portfolios. Show the scatter with **min-vol / max-Sharpe / equal-weight**
highlighted and the weight cards.
> "Random long-only portfolios plus the efficient frontier — and we're explicit
> that this is in-sample, historical, not a forecast."

### 9 · Show the Risk Dashboard (~40s)
Switch to the **Risk Dashboard** tab. Highlight the **correlation heatmap**, the
**diversification ratio**, and the **risk-contribution** table.
> "This shows when one volatile, correlated asset dominates portfolio risk even
> at equal dollar weight."

### 10 · Open the Command Palette (Ctrl/Cmd + K) (~30s)
Press **Ctrl/Cmd + K**. Show how it navigates anywhere and runs demos.
> "A command palette wires up every workspace — the same handlers as the
> sidebar, no separate router."

### 11 · Search a saved report (~30s)
In the palette, type a term from your saved report (e.g. `SPY` or `momentum`).
Show it surfaces the **saved report** (and saved backtests, templates, gallery);
press Enter to open it.
> "It's also a global search across your real local resources."

### 12 · Mention the architecture (~30s)
Close on the stack.
> "Under the hood: a **FastAPI** backend computes every backtest and risk metric;
> a **Next.js / React / TypeScript** frontend; **local SQLite** persistence — no
> account, no cloud, no telemetry. It's a research tool: no live trading, and
> it's honest about its limitations."

---

## Optional add-ons (if you have extra time)
- **Content Hub tour** — from the Command Center hero, click through the four
  workflows: Run Backtest → back → Open Strategy Library (open SMA Crossover,
  show hypothesis/failure modes) → Open Paper Replications (Jegadeesh–Titman,
  point out the "inspired demo, not full replication" labelling) → Open Quant
  Disasters (LTCM, show "what a naive backtest might miss"). Then scroll the
  dashboard's Trust Layer grid and the Built/Planned/Future direction panel —
  emphasize nothing planned is claimed as live.
- **Trust Layer on one result** — run SPY SMA with benchmark + robustness +
  stability enabled; walk the result page top to bottom (data quality, config
  hash, robustness grade, stability heatmap) and export the report.
- **Strategy Comparison** — five strategies on SPY, side by side, ranked.
- **Custom Strategy Builder** — load the *Momentum + Trend* gallery template and run it (no-code rules, no `eval`).
- **Stress Test** — run COVID Crash + 2022 Rate-Hike on the basket.
- **Offline UX** — stop the backend and open Saved Reports to show the friendly **Backend offline** panel with **Retry** (graceful, not a crash).
- **Theme** — switch the accent in Settings to show the whole app re-skin instantly.

## Tips
- Keep the window at ~1440×900 for clean charts.
- Pre-run steps 3–6 so recents/search have content on camera.
- If a run shows few/zero trades, that's expected for long-only in a downtrend —
  mention it rather than hiding it; it's an honest behavior, not a bug.
