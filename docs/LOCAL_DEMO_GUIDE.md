# QuantLab — Local Demo Guide (Phase 39.0)

How to run QuantLab locally and give a clean demo. Companion docs:
[`COMMAND_REFERENCE.md`](COMMAND_REFERENCE.md) ·
[`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) ·
[`DEMO_SCRIPT.md`](DEMO_SCRIPT.md) (detailed live script) ·
[`DEMO_VIDEO_SCRIPT.md`](DEMO_VIDEO_SCRIPT.md) (recorded versions).

## What QuantLab is

A local-first, deterministic, **educational** quant research platform: ~40
interactive labs (portfolio risk, derivatives, crypto/DeFi, macro,
microstructure) plus a product workflow layer (guided demos, scenario
reports, research journal, reliability/QA dashboards). Static sample data
throughout — not investment advice, not a trading system, not production
compliance infrastructure.

## Local demo goal

Both services running on your machine, every screen deterministic, zero
network dependencies — so the demo cannot be broken by a provider outage.

## Prerequisites

- Windows with PowerShell (paths below assume the repo at `C:\quantlab`)
- Python 3.11 with the repo venv at `backend\venv` (see
  [`DEVELOPER_ONBOARDING.md`](DEVELOPER_ONBOARDING.md) if missing)
- Node 18+ and npm; `frontend\node_modules` installed (`npm install`)
- Quick check: `.\scripts\check_environment.ps1` (read-only)

## Start the backend

```powershell
cd C:\quantlab\backend
venv\Scripts\uvicorn app.main:app --reload --port 8000
```

(or `.\scripts\run_backend.ps1` from the repo root — it prints the exact
command before running it). Verify: <http://localhost:8000/docs>.

## Start the frontend (user-run)

```powershell
cd C:\quantlab\frontend
npm run dev
```

Open <http://localhost:3000>. Helper scripts never run this for you.

## Recommended demo route

1. **Portfolio Showcase** — what the platform demonstrates, in one screen.
2. **Demo Center** — pick a guided tour; show module health.
3. **Scenario Studio** — Soft Landing → Severe Combo; copy the report.
4. **Research Workspace** — stage runs, show the reproducibility checklist.
5. **Data Reliability Center** — the deterministic-data story.
6. **QA Command Center** — smoke matrix + the command checklist.

## The 3-minute demo

Dashboard (Starting Paths strip, 15s) → Scenario Studio severe-combo heatmap
+ one slider + Copy Markdown (75s) → Demo Center tour + module health (45s) →
one deep lab, e.g. Crypto Derivatives funding slider (30s) → close on the
QA Command Center release gauge with the line "and the score itself says it
doesn't prove tests were run" (15s).

## The 8-minute demo

Use the timed table in [`DEMO_VIDEO_SCRIPT.md`](DEMO_VIDEO_SCRIPT.md) — it
adds Research Workspace, Data Reliability, Options/Macro depth, and the
KO/PEP offline pairs demo in Backtest Studio.

## What not to overclaim

- No performance/alpha/returns claims — samples are hand-written teaching sets.
- No "live", "real-time", or "production-ready" language.
- No users/customers/revenue (there are none to claim).
- Don't say tests/build passed unless you ran them in front of the audience.

## Safety wording (say it once, early)

> "Everything you'll see runs locally on deterministic educational sample
> data — no live feeds, no trading, not investment advice, and not
> production risk or compliance infrastructure."
