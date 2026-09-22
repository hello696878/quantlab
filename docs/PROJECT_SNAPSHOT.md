# QuantLab — Project Snapshot (Phase 64.0)

A one-page handoff doc. Facts verified against the repo when written
(version label `4.82.0-dev`); counts drift as phases land — re-verify before
public use. Status ground truth by area:
[`BLUEPRINT_STATUS_MATRIX.md`](BLUEPRINT_STATUS_MATRIX.md).

## Summary

QuantLab is a local-first, deterministic, **educational** quant research
platform: 58 routed top-level view identifiers behind one shell (grouped sidebar,
dashboard, command palette), a FastAPI + Pydantic v2 backend with a
consistent `sample`/`analyze` API pattern, and a Next.js 15.5.25 + TypeScript
frontend with shared charts, local KaTeX formulas, and copy-friendly report
exports. Not investment advice; no live trading; not production
trading/risk/compliance infrastructure.

## Module inventory (by sidebar group)

- **Start Here:** Home, Demo Center, Portfolio Showcase, Developer
  Onboarding, Global Markets Globe.
- **Product Workflow:** Scenario Studio, Research Workspace, Experiment
  Registry, Dataset Lineage, Model Validation Lab, Meta-Labeling Lab,
  Feature Diagnostics, Overfitting Diagnostics, Regime Diagnostics,
  Cost & Capacity, Portfolio Diagnostics, Portfolio Stress Lab,
  Portfolio Attribution, Factor Diagnostics, Signal Decay Lab,
  Signal Ensemble Lab, Strategy Ensemble Lab, Data Reliability Center, QA Command Center,
  Release Notes Center, Public Release Candidate.
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
`frontend/` (Next.js 15 single-page shell; typed per-lab clients; shared
chart/formula/state primitives; app-router error/loading/not-found safety
pages). Docker Compose; GitHub Actions CI (backend tests + frontend
component tests + typecheck + build).
Full map: `PROJECT_OVERVIEW.md`.

## Data modes

Deterministic static samples in most labs; user-configured inputs in the
backtest engines; local calculation in Options/Credit/Export Report; the external provider paths are yfinance historical prices (default for
market backtests) plus opt-in FRED macro and delayed globe quotes (disabled by
default and fail-closed to static dossiers); none is relied on in tests (KO/PEP pairs demo has a network-free fixture). Registry:
the in-app Data Reliability Center.

## Testing

Phase 64 implementation is committed as `1284b3115977f057f4690f643601dc329aac7797`.
Independent review is committed as `9d169edb4fbb66022d3643b31457fdecee3189e2`;
security patch / verified HEAD and origin/main is
`36f70e6b72800f0ab585afa8c873f4b87c09aeff`.
[Final release evidence (2026-09-20)](PHASE_64_SECURITY_REMEDIATION.md#final-release-verification-2026-09-20):
strict-peer install, 166 frontend tests, TypeScript and user production build
passed on Node 24.20.0/npm 11.17.0; full/production audits reported zero findings
at verification. Actual Microsoft Edge execution passed 21 Strategy Ensemble
and 12 frozen/responsive checks, zero failed/skipped. Exact-patch CI `35064846132`
passed Backend Tests and Frontend Tests & Build; Docker build/runtime/proxy
verification passed using Node 24.21.0. No full 275-test browser run, security/
trading certification or deployment is claimed. The v4.82 tag is pending user
creation after final documentation review, user commit, publication and verification. Phase 65 has
not started; that future docs commit is not covered by the security-patch CI.

Historical implementation evidence: [PHASE_64_IMPLEMENTATION.md](PHASE_64_IMPLEMENTATION.md).
The user's repaired combined implementation/maintenance backend run finished
with **4,359 passed, 3 symlink-platform skips in 3,285.73s**; pytest process exit
0. Source/snapshot/active-DB checks passed. Outer runner final exit was not
recorded. Exact identity and superseded 4,318/4/3 and 4,349/9/3 histories are in
[BACKEND_TEST_MAINTENANCE.md](BACKEND_TEST_MAINTENANCE.md) and the implementation
report. Those executable/configuration bytes matched at evidence finalization;
later revisions have separate evidence, including the final-gate record above.
Overall speedup and parallel execution are not established. That historical
implementation run did not verify production build, browser execution or CI.

Historical evidence below describes prior phases, not the latest run:

The Phase 62 implementation run reported 4,268 passed, four active-database
environment assertion failures and three Windows symlink-permission skips;
the review reproduced and classified those four failures without changing
tests or the active database. Its attempted full rerun exceeded the 65-minute
command timeout, so no green full-suite claim is made. Strict finiteness
guarantees exist at the API boundary; wording contracts are tests;
`npx tsc --noEmit` is clean for the frontend; a Playwright browser E2E guard covering
the frozen demo path, the Experiment Registry, Dataset Lineage, Model
Validation Lab, Meta-Labeling Lab, Feature Diagnostics, Overfitting
Diagnostics, Regime Diagnostics, Cost & Capacity, Portfolio Diagnostics, Portfolio Stress Lab, Portfolio Attribution, Factor Diagnostics, Signal Decay Lab, and Signal Ensemble Lab views (local-first, plus a manually triggered CI workflow —
`CI_BROWSER_E2E.md`). Phase 63.0 added the first frontend component-test
layer: Vitest + React Testing Library + jsdom; the original implementation
had **82 tests in 7 files**. Review strengthened the guards and isolation;
current counts and verification are in `PHASE_63_REVIEW.md`.
Navigation/registry drift guards plus component tests for the sidebar,
command palette, dashboard, formula reference, shared state primitives and
browser-storage safety run one-shot in CI before the typecheck and build
(`FRONTEND_COMPONENT_TESTING.md`).
Phase 63 Playwright discovery reported 254 Chromium tests in 18 spec files; discovery
is not an E2E pass. Verification is run locally by the user (helper wrappers
in `scripts\*.ps1`).

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
alpha claims); hand-maintained registries are now guarded for identity drift
but their content is still hand-maintained; frontend testing covers shared
components, navigation identity and a focused Strategy Ensemble panel slice only
— no visual regression or accessibility certification; single-user
local-first (no auth/hosting); full ledger in `LIMITATIONS.md`.

## Next recommended improvements

1. Final Phase 64 documentation review is complete (2026-09-21). The user then
   commits, publishes and verifies that documentation commit before creating
   the expected v4.82 tag.
2. Extend component tests to further shared primitives as they stabilise.
3. Phase 65/66 (planned, not started): unified ML identity, then replay by hash.
4. Screenshot captures for newer workspaces (real runs).
5. Read-only hosted-demo planning only after the documented gaps are addressed.
