# QuantLab — CI (Phase 41.0)

What the GitHub Actions workflow ([`.github/workflows/ci.yml`](../.github/workflows/ci.yml),
named **CI**) checks, what it deliberately does not, and how to run the same
checks locally. The workflow predates this phase (backend tests + frontend
build); Phase 41.0 added `permissions: contents: read` and a fast-fail
TypeScript check, and wrote this document.

> A green CI run is a **preflight signal** — the deterministic suite passed
> and the frontend compiled on a clean runner. It is not a production,
> compliance, security, or trading certification, and it never publishes or
> deploys anything.

## What CI checks

**Job 1 — Backend Tests** (`ubuntu-latest`, Python 3.11):
installs `backend/requirements.txt`, runs `python -m pytest -q` from
`backend/`. The suite (~2,900 tests) is deterministic and offline by design —
no live provider is ever contacted (yfinance is monkeypatched in the backtest
API tests; every lab runs on static samples).

**Job 2 — Frontend Build** (`ubuntu-latest`, Node 20):
`npm ci` (lockfile-exact), then `npx tsc --noEmit` (fast-fail typecheck,
added in 41.0), then `npm run build`. The build job predates Phase 41 and is
kept because the project has always expected CI to verify the production
build compiles — **on the runner**; your local `npm run build` remains a
separate, user-run step.

## What CI intentionally does NOT do

- No deployment of any kind.
- No GitHub release creation or publishing.
- No tags, no pushes — `permissions: contents: read`.
- No secrets: the workflow uses none, caches none, and needs none.
- No live external provider checks (no yfinance/FRED network tests).
- No trading/broker/exchange/wallet anything (none exists in the repo).
- No telemetry or coverage-upload services.

## Equivalent local checks (run by you)

```powershell
# Backend tests (repo venv at backend\venv)
cd C:\quantlab
if (Test-Path .\artifacts) {
    Remove-Item -Recurse -Force .\artifacts
}
backend\venv\Scripts\python.exe -m pytest backend\tests -q

# Frontend typecheck
cd C:\quantlab\frontend
npx tsc --noEmit

# Production build — user-run, always (never run by Claude sessions)
cd C:\quantlab\frontend
if (Test-Path .next) {
    Remove-Item -Recurse -Force .next
}
npm run build
```

Wrappers: `scripts\run_backend_tests.ps1`, `scripts\run_frontend_typecheck.ps1`.

## Known limitations

- No frontend *unit* tests exist yet. A local browser E2E harness exists
  (Phase 43.0 — [`BROWSER_E2E_RUNBOOK.md`](BROWSER_E2E_RUNBOOK.md)) but is
  **deliberately not a CI job in v1**: it needs live local servers, and
  keeping it out of CI avoids making the pipeline slower/flakier while the
  harness stabilizes. CI keeps covering backend tests + typecheck + build;
  the frozen-demo E2E guard is run locally before releases/reviews.
- CI proves the suite passes on a clean Linux runner — local-environment
  issues (venv drift, node_modules staleness) are covered by
  `scripts\check_environment.ps1` instead.
- CI status is only meaningful per-commit: "CI passed" claims must reference
  an actual run on an actual commit — never assume or assert it in docs
  without checking the Actions tab.
- No dependency-update automation (no bots) — dependency bumps are manual
  and deliberate.

## Troubleshooting CI failures

1. **Backend job fails** — reproduce locally with the commands above; the
   suite is deterministic, so a runner failure almost always reproduces
   locally. Check for accidentally committed environment-dependent paths.
2. **`npm ci` fails** — `package-lock.json` is out of sync with
   `package.json`; run `npm install` locally and commit the updated lockfile.
3. **Typecheck fails** — run `npx tsc --noEmit` locally; fix types honestly
   (no `any` escapes).
4. **Build fails but typecheck passed** — usually an app-router or import
   issue; clear `frontend\.next` locally
   (`scripts\clean_frontend_build_cache.ps1`) and rebuild yourself.

## Safety wording

CI runs deterministic educational code on sample data. Nothing in CI or in a
green badge is investment, trading, allocation, legal, tax, compliance, or
risk-management advice — and QuantLab remains not production trading, risk,
or compliance infrastructure regardless of CI status.
