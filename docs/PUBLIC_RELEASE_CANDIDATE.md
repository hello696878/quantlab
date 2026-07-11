# QuantLab Public Release Candidate v1 (Phase 42.0)

The manual verification layer between "the repo looks done" and "I shared it
publicly." Work through this document — with
[`FINAL_SMOKE_TEST_RUNBOOK.md`](FINAL_SMOKE_TEST_RUNBOOK.md) for the hands-on
pass and [`DEMO_FREEZE_CHECKLIST.md`](DEMO_FREEZE_CHECKLIST.md) before
recording anything — and QuantLab is ready for public portfolio, GitHub, and
LinkedIn sharing.

> **What "release candidate" means here:** a milestone of the local project
> that the user intends to verify manually and then share as a portfolio
> project. It is **public portfolio readiness only** — not a production
> certification, not a package publication, not a claim that any check below
> has already passed. Every status in this document starts at *Not yet run*
> and only the user changes it, with evidence.

## 1. Purpose

Before QuantLab is shown publicly (GitHub repo made public, LinkedIn post,
portfolio link, live interview demo), one person — the user — performs a final
manual verification pass. This document defines that pass: what the candidate
includes, what it deliberately does not include, which checks are required,
and a status table to fill in with real evidence.

## 2. What the release candidate includes

- **Portfolio Showcase** — the public-presentation page (pitches, demo path).
- **Demo Center** — guided walkthroughs + the module health dashboard.
- **Scenario Studio** — cross-lab scenario impacts and the report builder.
- **Research Workspace** — presets, experiment journal, exports.
- **Data Reliability Center** — data modes, offline fixtures, provider caveats.
- **QA Command Center** — smoke matrix, release readiness, command checklist.
- **Release Notes Center** — version manifest, changelog areas, release flow.
- **Developer Onboarding** — environment checklist, commands, troubleshooting.
- **CI preflight** — backend tests + frontend typecheck/build on push
  ([`CI.md`](CI.md)).
- **Repository hygiene & security/secrets docs** —
  [`REPOSITORY_HYGIENE.md`](REPOSITORY_HYGIENE.md),
  [`SECURITY_AND_SECRETS.md`](SECURITY_AND_SECRETS.md).
- **The core research labs** — portfolio/macro, backtesting & strategy
  comparison, derivatives & volatility, crypto/DeFi/tokenomics/on-chain,
  microstructure & alternative data, futures & commodities, real estate/MBS,
  credit, rates/FX — all on deterministic sample data.

## 3. What the release candidate does NOT include

- Live trading of any kind (QuantLab has no trading capability at all).
- Broker, exchange, or wallet integrations.
- Production compliance or risk certification — none is claimed anywhere.
- Investment, trading, allocation, legal, tax, or risk-management advice.
- Guaranteed live data — the few optional providers are disabled by default
  and fail closed to static data; their availability is never guaranteed.
- Automated deployment or hosting —
  [`DEPLOYMENT_READINESS.md`](DEPLOYMENT_READINESS.md) lists what a hosted
  demo would still need.

## 4. Required checks before public sharing

All are **user-run**; none are claimed to have passed by this document.

1. **Backend tests** — from `C:\quantlab`:
   `backend\venv\Scripts\python.exe -m pytest backend\tests -q`
   (delete `artifacts\` first if present; it must be absent after).
2. **Frontend typecheck** — from `frontend\`: `npx tsc --noEmit`.
3. **Frontend production build** — from `frontend\`: `npm run build`
   (always user-run; no tooling in this repo runs it for you).
4. **Manual route smoke test** — the full pass in
   [`FINAL_SMOKE_TEST_RUNBOOK.md`](FINAL_SMOKE_TEST_RUNBOOK.md).
5. **Docs link check** — click through the README "Project docs" list and the
   links inside the six Phase 42 docs; no 404s / wrong paths.
6. **Safety wording check** — the overclaim search in
   [`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md) §6 comes back clean
   (no production-trading / advice / guarantee language outside negations).
7. **Secret check** — the publishing-time search in
   [`SECURITY_AND_SECRETS.md`](SECURITY_AND_SECRETS.md) comes back clean.
8. **Screenshot checklist** — captures done per
   [`SCREENSHOT_CHECKLIST.md`](SCREENSHOT_CHECKLIST.md).
9. **Demo script rehearsal** — at least one timed run-through of
   [`FINAL_DEMO_SCRIPT.md`](FINAL_DEMO_SCRIPT.md).

## 5. Release candidate status table

Fill this in by hand as checks are completed. Evidence means something you
could show someone: a terminal line with the test count, a commit hash, a
screenshot filename, a date. **Do not mark Pass without evidence.**

| Area | Check | Owner | Status | Evidence |
|---|---|---|---|---|
| Backend | Full pytest suite green, `artifacts\` absent after | User | Not yet run | — |
| Frontend | `npx tsc --noEmit` exit 0 | User | Not yet run | — |
| Frontend | `npm run build` succeeds | User (user-run) | Not yet run | — |
| Routes | Smoke runbook full pass (all pages) | User | Manual verification required | — |
| Responsive | Desktop / tablet / mobile widths pass | User | Manual verification required | — |
| Docs | README + docs links all resolve | User | Manual verification required | — |
| Wording | Safety/overclaim search clean | User | Manual verification required | — |
| Secrets | Secret search clean; no `.env` committed | User | Manual verification required | — |
| CI | Latest push green on GitHub Actions | User (observe the run) | Not yet observed | — |
| Screenshots | SCREENSHOT_CHECKLIST captures complete | User | Manual verification required | — |
| Demo | FINAL_DEMO_SCRIPT rehearsed once end to end | User | Not yet run | — |
| Freeze | DEMO_FREEZE_CHECKLIST completed and dated | User | Not yet run | — |

Status vocabulary: `Not yet run` · `Not yet observed` · `Manual verification
required` · `User-run — passed on <date>` · `Failed — see notes`. There is no
"assumed passed."

## 6. When the table is complete

- Record the freeze in [`DEMO_FREEZE_CHECKLIST.md`](DEMO_FREEZE_CHECKLIST.md)
  (date, commit hash, tag).
- Make the launch decision in
  [`PUBLIC_LAUNCH_READINESS.md`](PUBLIC_LAUNCH_READINESS.md).
- Public-facing caveats live in
  [`KNOWN_LIMITATIONS_PUBLIC.md`](KNOWN_LIMITATIONS_PUBLIC.md) — link it from
  anywhere the project is shared.

## Ground rules (unchanged by this doc)

Deterministic educational sample data; no live trading; no telemetry; not
investment advice; not production trading, risk, or compliance
infrastructure. The frontend production build is always run locally by the
user.
