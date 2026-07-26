# QuantLab — Manual CI Browser E2E Workflow (Phase 45.0)

The manually triggered GitHub Actions workflow that runs the Playwright
frozen-demo regression suite in an isolated CI runner and uploads evidence
artifacts. Companions: [`CI.md`](CI.md) (the main preflight) ·
[`BROWSER_E2E_RUNBOOK.md`](BROWSER_E2E_RUNBOOK.md) (the local harness) ·
[`FROZEN_DEMO_REGRESSION_GUARD.md`](FROZEN_DEMO_REGRESSION_GUARD.md).

> **Remote workflow status: GREEN — observed run
> [29185725247](https://github.com/hello696878/quantlab/actions/runs/29185725247)
> on commit `47bfec0` (the `v4.63.0-manual-ci-browser-e2e-evidence-v1` tag
> target), `workflow_dispatch`, conclusion `success`.** Every step succeeded
> — backend tests, typecheck, production build, both readiness waits, the
> Playwright suite, and the evidence upload
> (`browser-e2e-evidence-29185725247`, ~212 KB, 14-day retention, expires
> 2026-07-26). Observed via read-only API inspection during Phase 46.0.
> A green run is evidence about that commit only — update this line per run.

## 1. Purpose

Run the existing browser regression guard (frozen demo route, Scenario
Studio severe combo, KO/PEP pairs fixture, responsive geometry, and the
Phase 48.0 Experiment Registry + Phase 49.0 Dataset Lineage + Phase 50.0
Model Validation Lab + Phase 51.0 Meta-Labeling Lab + Phase 52.0 Feature
Diagnostics + Phase 53.0 Overfitting Diagnostics + Phase 54.0 Regime
Diagnostics + Phase 55.0 Cost Diagnostics + Phase 56.0 Portfolio
Diagnostics + Phase 57.0 Portfolio Stress specs) against a
**freshly built, isolated** QuantLab instance — proving the guard doesn't
secretly depend on anything on the maintainer's machine, and producing
downloadable evidence (logs, traces, HTML report) per run. The registry specs
seed only the idempotent, clearly-marked demo records and otherwise read —
they never mutate real data.

## 2. Workflow identity

- **Name:** `Browser E2E Preflight`
- **File:** `.github/workflows/browser-e2e.yml`
- **Trigger:** `workflow_dispatch` **only** — started by a human from the
  Actions tab. No push/PR/schedule/release triggers, **no inputs** (nothing
  user-typed ever reaches a shell).
- **Permissions:** `contents: read` (nothing else). No secrets used or
  available to it; no deployment; no release/tag creation; no GitHub API
  mutations. Concurrency-guarded per ref; 30-minute job timeout.

## 3. Why manual and non-blocking in v1

The harness is new (v4.61). Keeping it out of the push/PR gate avoids
slowing or flaking the main pipeline while a stability record accumulates;
the frozen-demo guard is most valuable run deliberately before
releases/reviews. Main CI (`ci.yml`) is unchanged: backend tests + frontend
typecheck/build on every push/PR.

## 4. Environment

Ubuntu (`ubuntu-latest`) · Python 3.11 · Node 20 (npm cache keyed to
`frontend/package-lock.json`) · Playwright **Chromium only**, installed via
`npx playwright install --with-deps chromium` **inside the disposable
runner** (locally the harness drives the OS-installed Edge instead — no
download; `docs/PLAYWRIGHT_SETUP.md`).

## 5. Pipeline (exact logical order)

1. Checkout + runtimes (same pinned official actions as main CI).
2. `pip install -r backend/requirements.txt` · `npm ci` (lockfile-exact).
3. Playwright Chromium install.
4. **Static validation first:** backend `python -m pytest -q`, frontend
   `npx tsc --noEmit` — the E2E environment must be valid before any
   browser starts (deliberate duplication of main CI, isolated here).
5. `npm run build` with `BACKEND_URL=http://127.0.0.1:8000` — the repo's
   real build-time variable: `next.config.js` bakes it into the `/api/*`
   rewrite used by `next start`.
6. Background services, logs captured: uvicorn on `127.0.0.1:8000`
   (`artifacts/e2e-ci/backend.log`), `npx next start --hostname 127.0.0.1
   --port 3100` (`artifacts/e2e-ci/frontend.log`).
7. **Deterministic readiness** (no fixed sleeps):
   `python scripts/wait_for_http.py http://127.0.0.1:8000/health --timeout 90`
   then `…:3100/ --timeout 120` — a stdlib-only, localhost-only poller
   (exit 0 ready / 1 timeout / 2 bad args; unit-tested in
   `backend/tests/test_wait_for_http_script.py`).
8. `npx playwright test --project=chromium` with
   `E2E_BASE_URL=http://127.0.0.1:3100` and `E2E_BROWSER_CHANNEL=""`
   (bundled Chromium on the runner). The workflow fails iff Playwright
   exits non-zero — zero retries; a red test is information, never noise to
   retry away. The suite size evolves with the guard; no count is
   hardcoded.
9. Evidence upload (**`if: always()`**) + narrow failure diagnostics.

## 6. Deterministic data policy

The suite runs entirely on QuantLab's built-in fixtures (the KO/PEP demo
pair short-circuits before any fetch; Scenario Studio is static sample
data). **No live market data, no yfinance calls, no FRED** — no provider
credential exists in the workflow, and optional adapters stay disabled /
fail-closed by default.

## 7. Evidence artifacts

- **Name:** `browser-e2e-evidence-<run id>` · **retention: 14 days**.
- **Contents:** `artifacts/e2e/` (Playwright HTML report; traces + failure
  screenshots when tests fail) and `artifacts/e2e-ci/backend.log` /
  `frontend.log`.
- These are **generated, temporary CI evidence** — never committed, and
  **not** the frozen release screenshots (`docs/screenshots/release_*.png`
  remain separate and untouched) and not production-certification evidence.
- Deliberately excluded: `.env` files (none exist), SQLite user data,
  `node_modules`, the Playwright browser cache, `.next`, secrets.
- `if-no-files-found: warn`: after a fully green run traces/screenshots may
  be absent (only the HTML report + logs exist) — the warning is expected
  noise, not an error.

## 8. Triggering it (GitHub UI — the only way)

Repository → **Actions** → **Browser E2E Preflight** → **Run workflow** →
branch `main` → **Run workflow**. Record the run ID, commit SHA, and each
step's conclusion; download the evidence artifact from the run page.

## 9. Interpreting results

- **Green** — the frozen demo path behaved on that commit in a clean
  environment. A regression signal only: not a production, security,
  compliance, financial, or trading certification.
- **Red at backend tests / typecheck / build** — ordinary code failure;
  reproduce locally with the same commands.
- **Red at readiness** — a service didn't come up; read the uploaded
  `backend.log` / `frontend.log` (the failure step also tails both).
- **Red at Playwright** — open the HTML report / trace in the artifact;
  then [`FROZEN_DEMO_REGRESSION_GUARD.md`](FROZEN_DEMO_REGRESSION_GUARD.md)
  §3 decides whether it's a regression or a deliberate change done wrong.

## 10. Troubleshooting

- **Backend readiness timeout** — `backend.log` usually shows an import
  error or port conflict; the diagnostics step prints listening sockets.
- **Frontend build/start failure** — `frontend.log` + the build step output;
  remember `BACKEND_URL` is read at build time.
- **Playwright browser missing** — the Chromium install step must precede
  the suite; re-run the workflow (fresh runner) rather than debugging cache.
- **Artifact not found** — if the run died before any output existed the
  upload warns and produces nothing; the step logs still exist on the run.

## 11. Difference from the main CI workflow

`ci.yml` (push/PR): backend tests + frontend typecheck/build — no servers,
no browser. `browser-e2e.yml` (manual): everything above **plus** a running
app and the browser suite, in one job, with evidence artifacts. Neither
deploys, publishes, or touches tags/releases.

## 12. Promotion criteria (future, deliberate decision required)

Consider push/PR triggers only after: a run of consistently green manual
executions across multiple phases, runtime comfortably under ~15 minutes,
zero flake-shaped failures, and a documented decision in ROADMAP. Until
then this stays a manual preflight.

## Ground rules (unchanged by this doc)

E2E green is a regression signal only. Deterministic educational sample
data; no live data; no secrets; not investment advice; not production
trading, risk, or compliance infrastructure.
