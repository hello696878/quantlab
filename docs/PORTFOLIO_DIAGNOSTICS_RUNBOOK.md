# Portfolio Diagnostics Runbook (Phase 56.0)

Operations for the Portfolio Construction, Risk Budgeting,
Diversification & Constraint Diagnostics Lab. Local-first: SQLite only,
no cloud, no provider calls, no order submission; generated weights are
never applied anywhere.

## Start

```powershell
cd C:\quantlab\backend
venv\Scripts\uvicorn.exe app.main:app --reload --port 8000
```

Open the **Portfolio Diagnostics** sidebar view (the frontend is
user-controlled and proxies `/api/portfolio-diagnostics/*`).

## Demo

`POST /portfolio-diagnostics/demo-seed` (or "Load demo runs") —
idempotent via `demo:pd:*` keys; cascades the Phase 55 cost demo (which
cascades every earlier registry demo). Eleven runs cover the fifteen
documented cases: equal-weight reference, inverse-volatility with a
visible floor, ERC baseline, capped minimum variance, a highly
correlated universe, a degenerate-covariance honest failure, an
explicit eigenvalue-floor repair, a turnover-capped cost-linked
rebalancing run, a regime-linked run, a full-sample descriptive warning,
and an invalid future-looking provenance run. Loading twice creates
nothing. (Structurally infeasible constraints are a 422 at create — by
design not a stored run.)

## Typical API flow

1. `POST /portfolio-diagnostics/runs` — universe + method + estimation +
   covariance + constraints (+ budgets/rebalance/solver/sensitivity/
   links). Eager validation returns 422s with exact reasons.
2. `POST /runs/{id}/execute` — deterministic; re-execution atomically replaces
   the parent execution snapshot plus all child rows and reproduces the result
   fingerprint. Failures are recorded as `failed` (clearing any baseline flag)
   — never left running with a partially committed replacement.
3. Inspect `/runs/{id}` plus `/assets`, `/weights`,
   `/risk-contributions`, `/rebalances`, `/sensitivity`, `/regimes`.
4. `POST /runs/{id}/mark-baseline` — completed + acceptable integrity +
   successful solve + zero violations + every rebalance completed (409
   otherwise).
5. `GET /compare?a=&b=`, `GET /export` (with a truncation flag).

## E2E isolation

`frontend/e2e/portfolio-diagnostics.spec.ts` (18 tests) writes only the
idempotent demo seeds plus one deliberately rejected baseline attempt
(the expected 409 is filtered in that test). No real user data; no
external network; full Playwright only when backend + frontend already
run.

## Restoring a clean dev DB

The session restore script empties all registry demo tables — including
the six `portfolio_*` tables — after an abort-on-non-demo safety check;
`saved_backtests` / `saved_reports` / `custom_strategy_templates` are
never touched. The experiment-name allowlist includes
`"Portfolio diagnostics: "`.

## Troubleshooting

- **422 at create** — the message names the violated rule (alignment,
  bounds, infeasible constraints, ERC structural conflicts, inapplicable
  sensitivity dimensions, oversized schedules…). Nothing is coerced.
- **Solver `failed`** — degenerate/singular covariance under repair
  policy `none`, an unbounded ERC problem (zero-variance asset), or
  SLSQP non-convergence; the reason is stored per rebalance. Fix the
  input or choose an explicit repair policy.
- **Constraint violations** — the independent post-solve check found the
  solver output outside a configured bound. Turnover compares each target to
  the prior target after it has drifted through intervening returns; in v1 a
  minimum-variance turnover cap is diagnostic rather than solver-enforced.
  Violations are listed per rebalance and block baselines.
- **`unavailable` rebalances** — insufficient history before the
  estimation cutoff; expected for early fixed timestamps.
- **Regime rows missing** — portfolio timestamps must exactly match the
  linked regime run's timeline (no interpolation).

## Verification commands

```powershell
cd C:\quantlab\backend
venv\Scripts\python.exe -m pytest tests\test_portfolio_diagnostics.py -q
```

```powershell
cd C:\quantlab\frontend
npx tsc --noEmit
npx playwright test portfolio-diagnostics --project=chromium
```
