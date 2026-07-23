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
- **Meta-Labeling Lab** (Phase 51.0, `meta-labeling.spec.ts`): the lab opens
  with its calibration disclaimer, the 7-run demo seeds idempotently, method
  filters work, the verified-OOF run shows its validation/dataset links and
  raw-vs-calibrated metrics with the reliability chart + bin-table fallback,
  manual threshold selection updates coverage with no "optimal" wording
  anywhere, comparison stays neutral, the one-class failure and
  invalidated-dataset warning render honestly, dark-theme controls and column
  geometry hold, and 1024/768 have no page overflow (list AND detail). Only
  writes: the idempotent demo seeds.
- **Regime Diagnostics** (Phase 54.0, `regime-diagnostics.spec.ts`): the lab
  opens with its no-look-ahead disclaimer, the 5-run demo seeds idempotently,
  integrity filters work, the training-verified run shows its
  verified-from-validation-split pill with lookback/lag/threshold detail and
  the validation link, the full-sample run is warned and never called
  verified while its drawdown definition stays verified-causal, coverage
  with unassigned counts and the rare-regime "low sample" withholding
  render, the rank-reversal matrix and its no-winner note render, the
  concentration/robustness classifications stay neutral (no best/
  recommended/profitable-regime wording — asserted), the per-definition
  regime timeline strips render with combined labels and the transitions
  table with measured (never causal) differences, the invalid
  centered-labels definition shows its honest state next to a valid causal
  one, the invalid-definition run's baseline attempt is rejected with a 409
  (asserted as the only failed request), comparison warns that universes
  differ, export is path/credential-free, dark-theme controls and column
  geometry hold, and 1024/768 have no page overflow. Only writes: the
  idempotent demo seeds.
- **Cost & Capacity** (Phase 55.0, `cost-diagnostics.spec.ts`): the lab
  opens with its explicit-assumptions and no-execution disclaimers, the
  6-run demo seeds idempotently, completeness filters work, the flagship
  run's waterfall reconciles exactly (component sum = total cost and
  net = gross − total, asserted numerically through the same API the page
  uses), the partial-input run keeps missing spread/ADV unavailable —
  never zero — with the missing components named per observation, the
  high-turnover run reports its gross-positive→net-nonpositive count with
  no "failed trades" wording, the sensitivity grid marks the base scenario
  with no optimal-scenario wording (banned-wording regex asserted), the
  capacity results show participation rising monotonically with scale and
  fixed per-order fees constant while per-contract slippage scales 5× at
  5× (asserted numerically), the participation-threshold warning renders,
  the regime-linked run's cost table joins stored assignments with
  never-recomputed wording, the invalid future-looking run's baseline
  attempt is rejected with a 409 (asserted as the only failed request),
  an eligible run marks baseline as a comparison reference, comparison
  stays neutral, export is path/credential/NaN-free, dark-theme controls
  and explicit units hold, and 1024/768 have no page overflow. Only
  writes: the idempotent demo seeds plus the deliberate baseline marking
  on a demo run.
- **Overfitting Diagnostics** (Phase 53.0, `overfitting-diagnostics.spec.ts`):
  the lab opens with its selection-bias disclaimer, the 4-run demo seeds
  idempotently, metric/status filters work, the high-PBO noise demo shows
  the PBO estimate, the λ histogram with its labelled zero boundary and the
  block/combination counts, selection frequency and IS/OOS degradation
  render neutrally (no best/winning/recommended/optimal/safe strategy
  wording — asserted), the Sharpe diagnostics show observed Sharpe /
  non-excess kurtosis / trial counts / E[maxSR] / DSR with the
  no-future-profit disclaimer, the multiple-testing table separates
  Bonferroni/Holm/BH with the FWER-vs-FDR explanation and declared
  provenance, the dependence section shows the correlated pair and the
  approximate effective trials, the constant/one-trial demo shows honest
  unavailability and small-sample warnings, the invalid-config demo fails
  honestly with no baseline action, comparison warns that universes differ
  and stays neutral, export is path/credential-free, dark-theme controls
  and column geometry hold, and 1024/768 have no page overflow.  Only
  writes: the idempotent demo seeds.
- **Feature Diagnostics** (Phase 52.0, `feature-diagnostics.spec.ts`): the
  lab opens with its held-out / non-causality disclaimer, the 4-run demo
  seeds idempotently, method/integrity filters work, the verified held-out
  permutation run shows its validation/dataset links, the importance chart
  with honest negative values and its accessible full table, the
  rank-stability matrix + pairwise correlations + transparent score formula,
  the correlated pair group (with no deletion suggestion), distribution
  drift (high for the drifting feature) and importance drift
  (importance-drift-without-data-drift rendered honestly), the
  leakage-failed link fails honestly, the flagship baseline star renders and
  a not-held-out run's baseline attempt is rejected with a 409 (the one
  deliberate non-2xx in the suite — asserted as the only failed request),
  comparison stays neutral, the export JSON is path/credential/sample-free,
  no "causal"/"best"/"recommended" wording, dark-theme controls and column
  geometry hold, and 1024/768 have no page overflow (list AND detail). Only
  writes: the idempotent demo seeds (plus that rejected baseline attempt,
  which writes nothing).
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
  each is followed by a 200; the feature-diagnostics baseline-rejection test
  deliberately provokes exactly one 409 and asserts nothing else failed).

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
