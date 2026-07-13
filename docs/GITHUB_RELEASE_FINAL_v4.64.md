# GitHub Release FINAL — v4.64.0 (Phase 46.0)

**This is a manual release draft.** The GitHub Release has **not** been
created automatically and never will be by this repo — the user publishes it
by hand (steps in `PUBLIC_GITHUB_LAUNCH_CHECKLIST.md`). Before copying,
re-check every claim against [`RELEASE_EVIDENCE_v4.64.md`](RELEASE_EVIDENCE_v4.64.md).

## Release title

```
QuantLab v4.64.0 — Public Research Platform Release with Browser E2E Evidence
```

## Tag

```
v4.64.0-public-github-release-launch-v1
```

This tag **exists** (verified Phase 47.0): local = remote →
`2d4bcfe` ("Add public GitHub release launch closure v1"). Publish against
this existing tag — never recreate or move it.

---

## Release body (copy below this line)

**QuantLab** is a local-first, **educational** quant research platform:
~40 deterministic research workspaces — backtesting, portfolio risk,
scenario stress, options/volatility, rates/FX, credit, real assets,
crypto/DeFi, market microstructure — behind one shell, built on a FastAPI
backend, a Next.js frontend, SQLite local persistence, and Playwright
browser regression coverage. The few optional data adapters are disabled by
default and fail closed to static data.

> Educational and research-focused only — not investment advice, not a
> trading system, not production trading/risk/compliance infrastructure.
> Deterministic where documented, and honest about everything it isn't.

### Release milestones

- **v4.60 — Frozen public demo.** All 37 views browser smoke-tested; three
  responsive defects found and fixed; five production-build evidence
  screenshots frozen with SHA-256 hashes; demo freeze record.
- **v4.61 — Browser E2E regression guard.** 12 Playwright tests pinning the
  frozen demo route, the Scenario Studio severe-stress result, the KO/PEP
  pairs fixture, and responsive geometry — with hydration-aware
  stabilization for cold dev servers.
- **v4.62 — Public release package.** Release drafts, case study, demo video
  scripts, asset manifest — all manual-publication material.
- **v4.63 — Manual CI browser E2E evidence.** A `workflow_dispatch`-only
  GitHub Actions workflow that builds and starts QuantLab in an isolated
  runner and runs the full browser suite; **first remote run observed
  green** (run 29185725247, every step successful, evidence artifact
  uploaded).
- **v4.64 — This release.** Public repository closure: final release notes,
  evidence ledger, launch checklist, and a SHA-256 checksum manifest with a
  verifier script.

### Main demo workflows

Home / Research Terminal → Public Release Candidate → Portfolio Showcase →
**Scenario Studio** (deterministic Severe Cross-Asset Stress Combo →
severity 100.0/100, 8/8 modules) → **KO/PEP Pairs Trading** (deterministic
fixture: 119 trades, −23.0% vs +112.7% buy-and-hold — the demo strategy
loses on purpose; honest numbers are the feature) → Saved Reports → Command
Palette (Ctrl+K) → responsive at 1440 / 1024 / 768.

### Evidence

**1. Frozen release evidence** (commit `7cf9708`, tag `v4.60.0-…`):
five production-build screenshots (hashes in
`docs/DEMO_FREEZE_CHECKLIST.md`), the 37-view browser smoke report, the
completed freeze record.

**2. Local user-run evidence** (recorded per phase in `docs/ROADMAP.md`):
backend suite 2,968 passed at the freeze and 2,975 passed at Phase 45.0
(exit 0); `npx tsc --noEmit` exit 0; production build exit 0 with no
warnings; production-mode browser smoke PASS; local Playwright 12/12 against
both dev and production base URLs.

**3. Remote CI evidence** (observed runs on specific commits):
- CI run 29141440276 (`c059c4e`) — Backend Tests ✅ Frontend Build ✅
- CI run 29147666495 (`7cf9708`, freeze evidence commit) — ✅ ✅
- CI run 29185696068 (`47bfec0`, v4.63 tag target) — ✅ ✅
- Browser E2E Preflight run 29185725247 (`47bfec0`) — all steps ✅
- **CI run 29188597089 (`2d4bcfe`, this release's tag target)** — ✅ ✅
- **Browser E2E Preflight run 29193708980 (`2d4bcfe`, this release's tag
  target, `workflow_dispatch`)** — all steps ✅ including the full
  Playwright suite; evidence artifact `browser-e2e-evidence-29193708980`
  uploaded (14-day retention).

**4. Re-runnable verification commands** (commands, not results — run them
yourself):

```powershell
backend\venv\Scripts\python.exe -m pytest backend\tests -q     # backend suite
cd frontend; npx tsc --noEmit                                  # typecheck
cd frontend; npx playwright test --list --project=chromium     # E2E discovery
cd frontend; npx playwright test --project=chromium            # local E2E (servers running)
cd frontend; npm run build                                     # production build (user-run)
```

### Screenshots (frozen release evidence)

- `docs/screenshots/release_landing_1440.png`
- `docs/screenshots/release_scenario_studio.png`
- `docs/screenshots/release_home_1024.png`
- `docs/screenshots/release_home_768.png`
- `docs/screenshots/release_pairs_backtest.png`

### Architecture

FastAPI + Pydantic v2 (strict models; NaN/Infinity cannot cross the API
boundary) · Next.js 14 + TypeScript · SQLite local persistence ·
deterministic fixtures (tests never rely on a live provider) · optional
fail-closed adapters · pytest (~2,975 deterministic tests) · Playwright
(12-test frozen-demo guard) · GitHub Actions (CI preflight + manual browser
E2E workflow).

### Quickstart

```powershell
# backend
cd backend
python -m venv venv; venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\uvicorn app.main:app --reload --port 8000

# frontend (new terminal)
cd frontend
npm install
npm run dev   # → http://localhost:3000
```

Guides: `docs/LOCAL_DEMO_GUIDE.md` · `docs/DEVELOPER_ONBOARDING.md` ·
`docs/PLAYWRIGHT_SETUP.md`.

### Limitations (deliberate)

Not investment, trading, allocation, legal, tax, or risk-management advice ·
not production trading and no order execution — no market connectivity at
all · not a compliance system and not a security certification ·
deterministic/sample data where documented · live adapters are optional,
off by default, fail closed · E2E/CI green is a regression signal on a
specific commit only · local-first, single-user — no hosting, no
availability or SLA guarantee. Full ledger:
`docs/KNOWN_LIMITATIONS_PUBLIC.md`.

---
*(end of release body)*

## Manual publication instructions (summary — full runbook in the checklist)

1. Confirm the final review commit and that normal CI **and** Browser E2E
   Preflight are green on it (record both run IDs).
2. Inspect the uploaded CI evidence artifact; confirm no secret-like values
   in `backend.log` / `frontend.log` (none should exist).
3. Run `python scripts/verify_release_checksums.py
   docs/RELEASE_CHECKSUMS_v4.64.sha256` — must exit 0.
4. Confirm the five frozen screenshots and README render at the release
   commit.
5. Create the `v4.64.0-public-github-release-launch-v1` tag per repo
   convention and push it.
6. GitHub → Releases → Draft a new release → select the tag → paste the
   title and body above → confirm the limitations section survived the
   paste → **publish manually**. Consider leaving "Set as latest release"
   unchecked until you've verified the published page.

## Ground rules (unchanged by this doc)

Every evidence line above cites a recorded local run or an observed remote
run ID — nothing is assumed. Publishing is always a manual human action.
