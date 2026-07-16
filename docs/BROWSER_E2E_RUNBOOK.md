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
- **Experiment Registry** (Phase 48.0, `experiment-registry.spec.ts`): the
  view opens with its local-first disclaimer, the idempotent demo registry
  loads and the table renders, module filtering works, a detail shows
  fingerprints and a reproducible assessment, two experiments compare with a
  neutral diff, and there is no horizontal overflow at 1024/768. The spec's
  only write is the idempotent demo-seed (clearly-marked records, never
  overwrites or deletes real data); baseline/delete/invalidate transitions are
  covered by the backend tests on isolated databases. The review pass added
  guards for the dark-theme `ql-input` filter controls (rgb & oklch
  serializations) and table-column overlap geometry.
- **Model Validation Lab** (Phase 50.0, `model-validation.spec.ts`): the lab
  opens with its leakage-prevention disclaimer, the seven-run demo seeds
  idempotently, method filters work, the purged K-fold detail shows separate
  purge/embargo counts with zero remaining overlap and the split-timeline SVG,
  the standard K-fold reference shows its leakage warning, the CPCV run lists
  its combinations, run comparison stays neutral, the linked dataset/
  experiment records open, dark-theme controls and column geometry hold, and
  1024/768 have no page overflow. Only writes: the idempotent demo seeds
  (which cascade to the other registries' idempotent demo loaders).
- **Dataset Lineage** (Phase 49.0, `dataset-lineage.spec.ts`): the view opens
  with its provenance disclaimer, the demo lineage seeds idempotently (re-seed
  duplicates nothing), filters narrow the table, a dataset detail shows
  version history, fingerprints, the SVG lineage graph (with its accessible
  tabular fallback) and linked experiments, the alt-data example renders its
  quality warning and invalidated version, version comparison reports neutral
  schema drift, filter controls stay dark, the name column never overlaps its
  neighbour, and there is no page overflow at 1024/768. Same isolation policy:
  the only writes are the idempotent demo seeds.
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

> **Dev and production share `.next`** — never run `next dev` and `next
> start` at the same time, and always rebuild immediately before
> `next start`: the dev server rewrites `.next` under a running production
> server, which then serves stale/missing hashed assets (pages render
> unstyled, hydration never completes, and E2E fails in setup). If prod-mode
> results look corrupted, stop both servers, `npm run build`, start
> `next start` fresh.

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
5. On a **freshly started dev server**, the first run is slower (on-demand
   compile + hydration). The harness waits for real interactivity — the
   header clock rendering (a mount-gated client effect) is its hydration
   witness — so cold starts take longer rather than failing.
6. **Don't run the harness while the backend pytest suite is running** — the
   suite saturates the machine and starves the live backend/frontend,
   producing timeout flakes that look like regressions. Run them
   sequentially.

## 7. Known limitations (v1)

- Deliberately **not part of the push/PR CI gate**. An isolated CI run is
  available on demand via the manually triggered **Browser E2E Preflight**
  workflow ([`CI_BROWSER_E2E.md`](CI_BROWSER_E2E.md)) — it builds and starts
  the app inside the runner and uploads evidence artifacts; the local
  commands in this runbook remain fully supported and are still the primary
  pre-release habit.
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
