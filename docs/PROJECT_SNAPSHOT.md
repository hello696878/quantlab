# QuantLab — Project Snapshot (Phase 56.0)

A one-page handoff doc. Facts verified against the repo when written
(version label `4.74.0-dev`); counts drift as phases land — re-verify before
public use.

## Summary

QuantLab is a local-first, deterministic, **educational** quant research
platform: ~40 interactive workspaces behind one shell (grouped sidebar,
dashboard, command palette), a FastAPI + Pydantic v2 backend with a
consistent `sample`/`analyze` API pattern, and a Next.js 14 + TypeScript
frontend with shared charts, local KaTeX formulas, and copy-friendly report
exports. Not investment advice; no live trading; not production
trading/risk/compliance infrastructure.

## Module inventory (by sidebar group)

- **Start Here:** Home, Demo Center, Portfolio Showcase, Developer
  Onboarding, Global Markets Globe.
- **Product Workflow:** Scenario Studio, Research Workspace, Experiment
  Registry, Dataset Lineage, Model Validation Lab, Meta-Labeling Lab,
  Feature Diagnostics, Overfitting Diagnostics, Regime Diagnostics,
  Cost & Capacity, Portfolio Diagnostics, Data Reliability Center,
  QA Command Center, Release Notes Center, Public Release Candidate.
- **Backtesting:** Backtest, Strategy Comparison, Portfolio Backtest, CSV
  Backtest, Strategy Builder, Parameter Sweep, Train/Test, Walk-Forward.
- **Strategy Knowledge:** Strategy Library, Paper Replications, Quant
  Disasters.
- **Portfolio & Macro:** Portfolio Risk Lab, Macro Regime Lab.
- **Crypto & DeFi:** Crypto Derivatives, DeFi Risk, Tokenomics, On-Chain
  Analytics.
- **Market Structure & Alt Data:** Market Microstructure, Alternative Data,
  Event Lab.
- **Derivatives & Volatility:** Options, Volatility, Futures & Commodities.
- **Rates, Credit & Real Assets:** Yield Curve, FX, Credit Risk, Real Estate
  (+ MBS).
- **Methodology & Scanning:** Cross-Sectional Scanner, AFML Methodology.
- **Saved Work:** Saved Backtests, Saved Reports, Settings.

## Primary demo path

Portfolio Showcase → Demo Center → Scenario Studio → Research Workspace →
Data Reliability Center → QA Command Center
(guides: `LOCAL_DEMO_GUIDE.md`, `DEMO_SCRIPT.md`, `DEMO_VIDEO_SCRIPT.md`).

## Architecture

Monorepo: `backend/` (FastAPI; per-lab packages of strict `models.py` +
deterministic `sample.py` + pure `service.py`, exposed as
`GET /<lab>/sample` + `POST /<lab>/analyze`; SQLite for saved work) and
`frontend/` (Next.js 14 single-page shell; typed per-lab clients; shared
chart/formula/state primitives; app-router error/loading/not-found safety
pages). Docker Compose; GitHub Actions CI (backend tests + frontend build).
Full map: `PROJECT_OVERVIEW.md`.

## Data modes

Deterministic static samples in most labs; user-configured inputs in the
backtest engines; local calculation in Options/Credit/Export Report; the
only external providers (yfinance historical, opt-in FRED macro, opt-in
delayed globe quotes) are disabled by default, fail closed, and are never
relied on in tests (KO/PEP pairs demo has a network-free fixture). Registry:
the in-app Data Reliability Center.

## Testing

~2,900+ deterministic backend tests (2,968 green at the v4.60 freeze — see
the ROADMAP entry per phase for each milestone's count); strict finiteness
guarantees at the API boundary; wording contracts as tests;
`npx tsc --noEmit` for the frontend; a Playwright browser E2E guard covering
the frozen demo path, the Experiment Registry, Dataset Lineage, Model
Validation Lab, Meta-Labeling Lab, Feature Diagnostics, Overfitting
Diagnostics, Regime Diagnostics, Cost & Capacity, and Portfolio Diagnostics views (local-first, plus a manually triggered CI workflow —
`CI_BROWSER_E2E.md`); **no frontend unit-test framework yet**.
Verification is run locally by the user (helper wrappers in
`scripts\*.ps1`).

## Documentation inventory

`README.md` (public-facing) · `CHANGELOG.md` · `VERSION` ·
`docs/ROADMAP.md` (per-phase log) · `docs/LIMITATIONS.md` (honest ledger) ·
`docs/PROJECT_OVERVIEW.md` · version/release docs (`VERSION_MANIFEST`,
`RELEASE_CHECKLIST`, `RELEASE_NOTES_TEMPLATE`, `MILESTONE_HISTORY`, this
snapshot) · launch docs (`PORTFOLIO_LAUNCH_PACK`, `PUBLIC_PROJECT_SUMMARY`,
`SCREENSHOT_CHECKLIST`/`SCREENSHOT_PLAN`, `DEMO_VIDEO_SCRIPT`,
`LINKEDIN_POST_DRAFTS`, `INTERVIEW_TALKING_POINTS`, `DEPLOYMENT_READINESS`)
· onboarding docs (`LOCAL_DEMO_GUIDE`, `DEVELOPER_ONBOARDING`,
`TROUBLESHOOTING`, `COMMAND_REFERENCE`, `ENVIRONMENT_DOCTOR`) ·
contribution/hygiene docs (`CONTRIBUTING`, `CI`, `REPOSITORY_HYGIENE`,
`SECURITY_AND_SECRETS`) · public-readiness docs (`PUBLIC_RELEASE_CANDIDATE`,
`FINAL_SMOKE_TEST_RUNBOOK`, `DEMO_FREEZE_CHECKLIST`,
`PUBLIC_LAUNCH_READINESS`, `KNOWN_LIMITATIONS_PUBLIC`, `FINAL_DEMO_SCRIPT`)
· futures-path docs (`INSTRUMENTS_LAYER`, `FUTURES_DATA_INGESTION_PLAN`).

## Public portfolio readiness

README, launch pack, pitches, demo scripts, and the in-app Showcase are
ready, and the release-candidate layer (`PUBLIC_RELEASE_CANDIDATE.md` +
smoke runbook + demo freeze + launch decision table) defines the final
manual pass — its status table starts at "Not yet run" and only fills in
with user-run evidence. Screenshots for the newer labs are the main
outstanding capture work (`SCREENSHOT_CHECKLIST.md`); hosted deployment is
deliberately not claimed (`DEPLOYMENT_READINESS.md` lists what it would
need).

## Known limitations (headlines)

Educational simplifications on hand-written samples (nothing calibrated; no
alpha claims); hand-maintained registries can drift until re-reviewed; no
frontend tests; single-user local-first (no auth/hosting); full ledger in
`LIMITATIONS.md`.

## Next recommended improvements

1. Frontend test framework (shared primitives first).
2. Registry-vs-route drift tests so stale metadata fails CI.
3. Pre-configured deep links between product layers.
4. Screenshot captures for the newer labs (real runs).
5. Read-only hosted demo once the deployment gaps are addressed.
