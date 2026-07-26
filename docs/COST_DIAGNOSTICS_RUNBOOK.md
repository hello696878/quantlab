# Cost Diagnostics Runbook (Phase 55.0)

Operations for the Transaction Cost, Slippage, Market Impact & Capacity
Diagnostics Lab. Local-first: SQLite only, no cloud, no broker or
provider calls, no order submission.

## Start

```powershell
cd C:\quantlab\backend
venv\Scripts\uvicorn.exe app.main:app --reload --port 8000
```

The frontend (user-controlled) proxies `/api/cost-diagnostics/*` to the
backend. Open the **Cost & Capacity** sidebar view.

## Demo

`POST /cost-diagnostics/demo-seed` (or the "Load demo runs" button) —
idempotent via unique `demo:cd:*` keys; cascades every upstream registry
demo (regime → overfitting → feature → meta-labeling → validation →
dataset → experiment). Six runs cover the twelve documented cases:
complete gross-to-net with √impact + baseline, high-turnover erosion
(bps commission), partial missing inputs, fixed per-order fee with
integer contracts, regime-linked period costs, and an invalid
future-looking ADV input. Loading twice creates nothing.

## Typical API flow

1. `POST /cost-diagnostics/runs` — observations + cost model + optional
   liquidity series/links (eager validation; 422 on any contract
   violation, including negative fees, missing spread fraction, tick
   units without tick size, ADV-unit/participation-mode mismatch,
   centered windows, non-positive lags, oversized grids).
2. `POST /cost-diagnostics/runs/{id}/execute` — deterministic; re-execution
   replaces child rows and reproduces the result fingerprint. Failures
   are recorded as `failed` with an error message.
3. Inspect `/runs/{id}`, `/runs/{id}/observations`, `/sensitivity`,
   `/capacity`, `/regimes`.
4. `POST /runs/{id}/mark-baseline` — completed + complete +
   acceptable integrity only (409 otherwise).
5. `GET /compare?a=&b=`, `GET /export`.

## E2E isolation

`frontend/e2e/cost-diagnostics.spec.ts` (18 tests) writes only the
idempotent demo seeds plus one deliberate baseline marking on a demo run
and one deliberately rejected baseline attempt (the expected 409 is
filtered in that test). Real user records are never modified; no external
network. Full Playwright runs only when backend + frontend are already
running with the standard dev setup.

## Restoring a clean dev DB

The session restore script (scratchpad `restore_dev_db.py`) empties all
registry demo tables — including the five `cost_*` tables — after an
abort-on-non-demo safety check; `saved_backtests`, `saved_reports` and
`custom_strategy_templates` are never touched. Add
`"Cost diagnostics: Demo"` to its experiment-name allowlist when
restoring after seeding this lab's demo.

## Troubleshooting

- **422 on create** — the error message names the exact violated rule;
  nothing is silently coerced.
- **Component "unavailable"** — by design when an input is missing; the
  per-observation row lists which components and why. Never treated as
  zero.
- **Integrity `invalid`** — an execution input claims a centered window,
  a non-positive lag, or an impossible trailing claim; the run cannot
  become a baseline.
- **Run `failed`** — the error message is stored on the run; re-execute
  after fixing the cause. Runs are never left stuck in `running`.
- **Regime rows missing** — the cost observations' timestamps must
  exactly match the linked regime run's timeline entries (no
  interpolation); unmatched observations appear as `unassigned`.

## Verification commands

```powershell
cd C:\quantlab\backend
venv\Scripts\python.exe -m pytest tests\test_cost_diagnostics.py -q
```

```powershell
cd C:\quantlab\frontend
npx tsc --noEmit
npx playwright test cost-diagnostics --project=chromium
```
