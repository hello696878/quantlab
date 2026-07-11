# QuantLab — Browser E2E Runbook (Phase 43.0)

How to run the Playwright regression harness that guards the frozen public
demo path. Companions: [`PLAYWRIGHT_SETUP.md`](PLAYWRIGHT_SETUP.md) (setup) ·
[`FROZEN_DEMO_REGRESSION_GUARD.md`](FROZEN_DEMO_REGRESSION_GUARD.md) (what is
protected and why).

> **What green means:** the frozen demo path still behaves as it did at tag
> `v4.60.0-public-release-candidate-demo-freeze-v1` — a regression signal
> only. It is **not** a production certification, not trading/compliance
> readiness, and not proof of anything beyond the checks listed below.
> Everything runs on deterministic fixtures; **no live data is required or
> used**.

## 1. What the harness checks

- The landing page loads with the frozen hero, dashboard, and (when the
  backend is up) an **API ONLINE** health chip.
- The frozen product-workflow pages open: Portfolio Showcase, Public Release
  Candidate, Demo Center, Release Notes Center, Developer Onboarding, Saved
  Reports (controlled empty state).
- The command palette opens with Ctrl+K and navigates.
- **Scenario Studio**: "Severe Cross-Asset Stress Combo" analyzes via a 200
  POST and reaches severity **100.0/100**, **8 / 8** modules, the "Severe
  systemic stress" regime, with heatmap and charts rendered.
- **KO/PEP pairs fixture**: the deterministic demo pair over the pinned
  frozen date range (2016-07-11 → 2026-07-11) reproduces **119 trades**,
  **−23.0%** vs **+112.7%** B&H, 4 charts, and a trade log — with no live
  provider involved.
- **Responsive geometry** at 1440/1024/768: no horizontal document overflow,
  dashboard badges stay inside their cards (Phase 42.1 defect D1), the
  TopBar title block stays readable (D2), Global Markets chips don't clip
  their values (D3).
- Page-safety invariants everywhere: no rendered `NaN`/`Infinity` (checklist
  *wording* on the QA/RC pages is a documented exception), no raw stack
  traces, no failed local `/api/*` requests (dev-mode StrictMode
  `ERR_ABORTED` duplicate-mount fetches are a documented, ignored exception —
  each is followed by a 200).

## 2. What it does NOT check

Quant correctness (that's the backend suite's job — ~2,900+ deterministic
tests), visual pixel fidelity (no snapshot baselines in v1), the other ~30
sidebar views (manual runbook: [`FINAL_SMOKE_TEST_RUNBOOK.md`](FINAL_SMOKE_TEST_RUNBOOK.md)),
copy-to-clipboard behavior, accessibility conformance, cross-browser
rendering (Chromium-engine only in v1), or anything about production
hosting.

## 3. Required servers (started by YOU — the harness never starts servers)

| Server | URL | Start command |
|---|---|---|
| Backend | http://localhost:8000 | `cd C:\quantlab\backend; venv\Scripts\uvicorn app.main:app --reload --port 8000` |
| Frontend dev | http://localhost:3000 | `cd C:\quantlab\frontend; npm run dev` |
| Frontend production (optional) | http://localhost:3100 | `npm run build` then `npx next start --port 3100` (both user-run) |

## 4. Running

From `C:\quantlab\frontend`:

```powershell
npm run e2e              # all specs
npm run e2e:frozen       # frozen demo + Scenario Studio + KO/PEP pairs
npm run e2e:responsive   # 1440 / 1024 / 768 geometry guards
npm run e2e:report       # open the last HTML report
```

Against the production server:

```powershell
$env:E2E_BASE_URL = "http://localhost:3100"
npm run e2e
```

Wrapper scripts (they refuse to run if the servers aren't up, and never
start anything): `scripts\run_e2e_frozen_demo.ps1`,
`scripts\run_e2e_responsive.ps1`, cheat sheet `scripts\print_e2e_commands.ps1`.

## 5. Where artifacts go

Everything generated lands under **`C:\quantlab\artifacts\e2e\`**
(`test-results\` for traces/failure screenshots, `playwright-report\` for the
HTML report) — covered by the repo's `artifacts/` gitignore rule and safe to
delete at any time. The harness **never writes to
`docs\screenshots\release_*.png`** — those are frozen release evidence.

## 6. Interpreting failures

1. Open the report (`npm run e2e:report`) or the failure trace
   (`npx playwright show-trace <trace.zip>` path printed on failure).
2. A frozen-metric mismatch (severity ≠ 100.0, trades ≠ 119, returns
   changed) means the deterministic demo changed — either an intentional
   post-freeze decision (then update the guard *and*
   `FROZEN_DEMO_REGRESSION_GUARD.md` deliberately) or a genuine regression.
3. Geometry failures name the offending badge/chip and the overflow in px.
4. "BLOCKED" from the wrapper scripts means a server isn't running — that is
   a precondition failure, not a regression.

## 7. Known limitations (v1)

- Local/manual only — deliberately **not a CI job yet** (see
  [`CI.md`](CI.md)); run it before releases/reviews.
- Chromium-engine only, via the OS-installed Edge (`channel: "msedge"`).
- Failure videos are off (they'd require Playwright's downloadable ffmpeg;
  traces + screenshots are the evidence).
- The KO/PEP guard pins the frozen date range explicitly because the app's
  default dates are relative to "today" — this is a feature of the guard,
  not a bug in the app.
- The suite mutates nothing persistent: each test runs in a fresh browser
  context; localStorage-based prefs never leave the test profile.

## Ground rules (unchanged by this doc)

Deterministic educational sample data; no live trading; no telemetry; not
investment advice; not production trading, risk, or compliance
infrastructure.
