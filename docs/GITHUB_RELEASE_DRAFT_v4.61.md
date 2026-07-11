# GitHub Release Draft — v4.61.0 (Phase 44.0)

Copy-ready text for a **manually published** GitHub Release. Nothing in this
repo creates releases automatically or calls the GitHub API — you paste this
into the Release page yourself (checklist at the bottom).

---

## Release title

```
QuantLab v4.61.0 — Public Release Candidate + Browser E2E Regression Guard
```

## Tag

Use the existing tag (verified in local git; **never force-update a tag**):

```
v4.61.0-browser-e2e-regression-guard-v1
```

---

## Release body (copy below this line)

**QuantLab** is a local-first **educational** quant research platform:
~40 deterministic research workspaces (backtesting, portfolio risk, scenario
analysis, derivatives, credit, real assets, crypto/DeFi, market
microstructure) behind one shell, with frozen public-release evidence and a
Playwright browser regression harness protecting the demo path.

> Educational only — not investment advice, not a trading system, not
> production trading/risk/compliance infrastructure. Deterministic sample
> data by design; the few optional data adapters are disabled by default and
> fail closed.

### What's in this release

**v4.60 series — Public Release Candidate & Demo Freeze**
- Six public-readiness docs (release candidate status table, final smoke
  runbook, demo freeze checklist, launch readiness, public limitations,
  final demo script) + the in-app Public Release Candidate page.
- First real end-to-end browser smoke test (all 37 sidebar views) with three
  responsive defects found and fixed (card badges @1024, TopBar @768, market
  chips @768).
- Futures fixture path isolation + YM roll-event continuous-build coverage.
- Frozen release evidence: five production-build screenshots with SHA-256
  hashes recorded in the freeze record.

**v4.61 series — Browser E2E Regression Guard**
- Playwright harness (one devDependency, zero browser downloads — drives
  OS-installed Edge): 12 tests guarding the frozen demo route, the Scenario
  Studio severe-stress result, the KO/PEP pairs fixture, and 1440/1024/768
  responsive geometry.
- Hydration-aware stabilization so the harness is reliable on cold dev
  servers (mount-gated hydration witness, marker-verified navigation,
  palette fallback).

### Verification evidence (user-run, recorded in the project docs)

The following results were observed by the maintainer on the reference
Windows setup and are recorded with context in the repo docs — they are
**records of specific runs**, not guarantees about your machine:

| Check | Recorded result | Where recorded |
|---|---|---|
| Backend suite | 2,968 passed, exit 0 | `docs/DEMO_FREEZE_CHECKLIST.md`, `docs/ROADMAP.md` |
| Frontend typecheck | `npx tsc --noEmit` exit 0 | freeze record |
| Production build | `npm run build` exit 0, no warnings | freeze record |
| Production browser smoke | PASS (all 37 views; prod mode) | `docs/BROWSER_SMOKE_TEST_REPORT.md` |
| Playwright E2E | 12 passed (dev and production base URLs) | `docs/ROADMAP.md` Phase 43.0 |
| CI (freeze evidence commit `7cf9708`) | run 29147666495 — Backend Tests ✅ Frontend Build ✅ | freeze record |

Key commits: application state `c059c4e` · freeze evidence `7cf9708` ·
E2E harness `e1dcdca` · E2E stabilization `4a06c5b`.

### Expected verification commands (re-run these yourself)

```powershell
# backend suite (from the repo root)
backend\venv\Scripts\python.exe -m pytest backend\tests -q

# frontend typecheck
cd frontend; npx tsc --noEmit

# browser E2E guard (start backend + frontend first — see docs/BROWSER_E2E_RUNBOOK.md)
cd frontend; npx playwright test

# production build (user-run)
cd frontend; npm run build
```

### The frozen demo path

Landing → Public Release Candidate → Scenario Studio (Severe Cross-Asset
Stress Combo → severity 100.0/100, 8/8 modules) → KO/PEP Pairs Trading
(deterministic fixture: 119 trades, −23.0% vs +112.7% buy-and-hold) →
Saved Reports → Command Palette (Ctrl+K) → responsive at 1440/1024/768.

### Screenshots (frozen release evidence)

- `docs/screenshots/release_landing_1440.png`
- `docs/screenshots/release_scenario_studio.png`
- `docs/screenshots/release_home_1024.png`
- `docs/screenshots/release_home_768.png`
- `docs/screenshots/release_pairs_backtest.png`

### Limitations (honest, by design)

- Not production trading infrastructure — QuantLab places no orders and has
  no market connectivity.
- Not investment, trading, allocation, legal, tax, or compliance advice.
- Not a compliance/risk certification of anything.
- Deterministic educational sample data; optional external adapters are
  disabled by default and fail closed; never relied on in tests.
- E2E/CI green is a regression signal on a specific commit — not a
  certification.
- Full ledger: `docs/KNOWN_LIMITATIONS_PUBLIC.md`.

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

Full guides: `docs/LOCAL_DEMO_GUIDE.md` · `docs/DEVELOPER_ONBOARDING.md` ·
`docs/PLAYWRIGHT_SETUP.md`.

---
*(end of release body)*

## Manual publication checklist (do these yourself — nothing is automated)

- [ ] Tag `v4.61.0-browser-e2e-regression-guard-v1` exists on the remote and
      points at the reviewed commit (`git ls-remote --tags origin "v4.61*"`).
- [ ] The five frozen screenshots render on GitHub at that tag.
- [ ] The doc links in the body resolve at that tag.
- [ ] No secrets: run the publishing-time search in
      `docs/SECURITY_AND_SECRETS.md` once more.
- [ ] No generated artifacts committed (`artifacts/`, `test-results/`,
      `playwright-report/` absent from the tree).
- [ ] Paste title + body into GitHub → Releases → "Draft a new release" →
      select the existing tag → publish **manually**.

## Ground rules (unchanged by this doc)

This draft records user-run evidence and expected commands — it never claims
a CI run beyond those cited, and publishing the release is always a manual
human action.
