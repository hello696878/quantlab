# QuantLab — Demo Video Script (Phase 38.0)

Scripts for recorded demos (60s / 3min / 8min). Companion to the live-demo
[`DEMO_SCRIPT.md`](DEMO_SCRIPT.md). Record at ~1440×900, dark theme, backend
running, ≥2 saved backtests so recents have content.

> **Every version must say, on camera or on screen:** deterministic
> educational sample data · not investment advice · not a live trading
> system · not production compliance infrastructure.

---

## 60-second version

**Screens (in order):** Dashboard → Scenario Studio → Demo Center → close on
the Scenario Studio report.

**Say:**
> "This is QuantLab — a full-stack quant research platform I built. About
> forty interactive labs — options, rates, credit, futures, microstructure,
> and a full crypto suite — all running locally on deterministic sample
> data. [Open Scenario Studio; select Severe Combo] One scenario maps into
> every module's documented impact score — here's the heatmap, the regime
> read, and a copyable report. [Open Demo Center] There's a product layer
> too: guided tours, module health, QA dashboards. FastAPI and Pydantic on
> the back, Next.js and TypeScript on the front, about 2,900 deterministic
> tests. It's educational — sample data, not investment advice, not a
> trading system — and every model states its limitations right in the UI."

**Avoid saying:** "production", "live", "alpha", "returns", anything about
performance.

## 3-minute version

**Screens:** Dashboard (Starting Paths) → Demo Center (Founder tour, module
health) → Scenario Studio (Soft Landing → Severe Combo, drag one slider, copy
report) → Crypto Derivatives Lab (funding slider, liquidation chart) →
Research Workspace (journal + reproducibility) → QA Command Center (smoke
matrix + command checklist).

**Beats to hit:**
1. *Shell* (20s): "One shell — grouped sidebar, command palette, dashboard
   starting paths. Everything you'll see is deterministic sample data."
2. *Demo Center* (30s): "The platform explains itself: guided walkthroughs
   per audience, and a hand-maintained module health dashboard."
3. *Scenario Studio* (45s): "The connective tissue. Ten stress templates,
   documented weight tables — watch the heatmap and regime flip when I go
   from Soft Landing to the Severe Combo. One click copies a Markdown
   report."
4. *One deep lab* (40s): "Each lab is a real model with the formulas rendered
   next to the numbers. Here's perp funding and basis — the liquidation
   distance is labeled as the educational estimate it is."
5. *Research Workspace* (25s): "Runs get journaled into research packs with
   severity ranking and a reproducibility checklist."
6. *QA close* (20s): "And the quality story is a product surface: smoke-test
   matrix, release readiness, and the exact local verification commands —
   which the page lists but never claims to have run."

**Closing statement:**
> "QuantLab is educational and local-first: static sample data, no live
> feeds, no trading, not investment advice, and not production risk or
> compliance software. The code, tests, and honest limitations ledger are all
> in the repo."

## 8-minute version

Extend the 3-minute skeleton; suggested timing:

| Min | Screen | What to click | What to say (theme) |
|---|---|---|---|
| 0:00 | Dashboard | Starting Paths strip | What QuantLab is; ground rules (sample data, educational) |
| 0:45 | Demo Center | Founder tour → a step's "Open module →" | Product layer; audiences; module health + capability matrix |
| 1:45 | Scenario Studio | Severe Combo; one slider; formula panel; Copy Markdown | Cross-lab impact scoring; documented formulas; report export |
| 3:00 | Crypto Derivatives → DeFi Risk | Funding slider; depeg slider past the kink | Interactive labs; deterministic what-ifs; honest labels |
| 4:15 | Options Lab or Macro Regime | Price an option / flip macro states | Classic quant depth; LaTeX beside numbers |
| 5:00 | Research Workspace | Stage runs; note; Export → Copy JSON | Journal, reproducibility checks, local drafts |
| 5:45 | Data Reliability Center | Filter to Backtesting; provider table | The yfinance story: optional, fail-closed, test-safe fixtures |
| 6:30 | QA Command Center | Smoke matrix; command checklist | QA as product; verification stays local |
| 7:15 | Backtest Studio | Run the KO/PEP pairs demo | The offline deterministic demo fallback, end on charts |
| 7:45 | Dashboard | — | Closing statement (below) |

**What to avoid saying (all versions):**
- Any performance, alpha, or return claim ("this strategy makes…").
- "Live", "real-time", "production-ready", "institutional-grade".
- User/customer/revenue numbers (there are none).
- That tests/builds passed in this recording unless you show them running.

**Closing statement (8-min):**
> "Everything you saw ran locally on deterministic sample data — that's the
> design: reproducible demos, tests that never touch a live provider, and
> models that state their simplifications. QuantLab is an educational
> research platform and an engineering portfolio piece — not investment
> advice, not a live trading system, not production compliance
> infrastructure. Thanks for watching."
