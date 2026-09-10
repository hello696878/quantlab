# Strategy Ensemble Lab Runbook

## Preconditions

Implementation task did not start servers, run a production build, migrate the
active development DB, or run full browser tests. Use a disposable checkout/DB
for manual testing. The existing DB layer uses `_db_path_override` in tests;
there is no new production DB-path environment setting. Do not assume an env
variable isolates the backend when the current DB layer does not read it.
Follow [browser runbook](BROWSER_E2E_RUNBOOK.md) for existing service setup.

## Browser workflow

1. Open Strategy Ensemble Lab from the Product Workflow sidebar or command
   palette, or use `/?view=strategyensemble` on the local frontend.
2. Empty state is normal. Load demo runs only into a database intended for it.
   Seeding is an explicit action, never a startup side effect. It creates ten
   deterministic illustrative return-stream runs plus its own linked regime
   and validation fixtures. These are not market backtests or performance claims.
3. Load twice: second load reports existing runs, not duplicates. Inspect
   Identical, Inverse, Constant, Missing periods, joint-loss and drawdown cases.
4. Inspect Net costs already included: no second deduction; allocation cost and
   fully net performance remain unavailable. Inspect fixed static sensitivity.
5. Inspect Stored regimes and held-out: assignments/memberships and frozen
   weights are visible. Invalid outcome timing is a failed record, not a result.
6. To supply data, use a demo run's **Use inputs for new run**, edit the JSON to
   your explicitly qualified streams, then Create run. Nothing automatically
   executes. Definitions require caller SHA-256 identities and availability;
   copying a demo fingerprint does not establish real-data provenance.
7. Execute explicitly. Mark baseline explicitly only if eligible. Compare two
   completed runs: different inputs are identified as descriptive side-by-side,
   never ranked. Invalidate only your chosen run with a reason.
8. Export JSON and compare with saved run fields. It contains declared inputs,
   pinned source identities, results, warnings and fingerprints, no automatic
   DB/storage paths, environment, credentials, serialized model or file reader.

No weight or number is coerced while editing JSON; backend validation is
authoritative. Loading, unavailable, invalid, empty and retry states are distinct.
Tables paginate at 50 rows; lists at 25. UTC interval labels retain intraday time.
Chart wealth is normalized to 1, not currency. Drawdowns remain negative and
decimal returns are formatted as percentages. Missing values say Not available.

## API

Backend prefix `/strategy-ensembles`; frontend proxy prefix
`/api/strategy-ensembles`. Existing `BACKEND_URL` configuration/default local
backend applies. No separate routing or provider configuration.

| Method | Suffix | Result |
|---|---|---|
| GET | `/runs?page=1&page_size=25` | Bounded summaries; page 1-10,000, size 1-100 |
| POST | `/runs` | Strict `RunCreate`, 201, created without execution |
| GET | `/runs/{id}` | Full stored input/result record |
| POST | `/runs/{id}/execute` | Optional `{ "create_experiment": true }` |
| POST | `/runs/{id}/mark-baseline` | Explicit reference transaction |
| POST | `/runs/{id}/invalidate` | Required nonempty `reason` |
| GET | `/compare?a=1&b=2` | Two different completed runs, no ranking |
| GET | `/export?run_id=1` | JSON snapshot with schema version |
| POST | `/demo-seed` | Explicit idempotent deterministic fixtures |

Not found 404; invalid/stale state 409; malformed or incoherent input 422.
Linked source mutation/invalidation requires a new run, never silent refreshing.
Definitions/observations are immutable after create; use a new run for changes.

## Automated checks

```powershell
cd C:\quantlab
Remove-Item Env:PYTHONIOENCODING -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m pytest backend\tests\test_strategy_ensemble.py -q
.\.venv\Scripts\python.exe -m pytest backend\tests -q

cd C:\quantlab\frontend
npm run test:unit
npm run test:unit
npx tsc --noEmit
npx playwright test --list --project=chromium --reporter=list
```

Temporary SQLite files only in tests. Do not delete active DB or existing
artifacts to conceal the four environment-sensitive full-suite failures.
`--reporter=list` prevents discovery from replacing existing HTML reports.

Only after **already-running** services are confirmed to use a disposable DB:

```powershell
$env:E2E_STRATEGY_ENSEMBLE_ISOLATED = '1'
# Set E2E_BASE_URL to that isolated local frontend before running.
npx playwright test e2e/strategy-ensemble.spec.ts --project=chromium --reporter=list
```

The flag is operator attestation, not automatic DB isolation. New spec refuses
non-local hostnames; no service startup is configured. Do not run against the
active DB. Check 1024/768 layouts, chart/table/API equality, retry, deep-link/back
and no raw stack/NaN. No frozen screenshot files are written.

Frontend build was not run in Codex by instruction. Please run it locally.
No CI, release, deployment or Phase 65 is authorized by this runbook. See
[implementation report](PHASE_64_IMPLEMENTATION.md) for remaining gates and the
user-only commit/push commands.
