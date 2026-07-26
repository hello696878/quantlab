# Portfolio Stress Lab Runbook (v1)

Operating the Phase 57.0 Portfolio Stress Testing, Scenario Shock and
Drawdown Attribution Lab locally.

## Prerequisites

- Backend on :8000 (`scripts/run_backend.ps1`), frontend dev server on :3000.
- Interpreter for tests: `backend\venv\Scripts\python.exe`.
- Clear `PYTHONIOENCODING` before backend suites on Windows (cp950 subprocess
  decode noise): `Remove-Item Env:PYTHONIOENCODING`.

## Load the demo

`POST /portfolio-stress/demo-seed`, or the **Load demo runs** button in the
Portfolio Stress Lab view. Seeding is idempotent (unique `demo_key`) and
cascades the Phase 56 / 55 / 54 demo loaders. Only the flagship creates an
Experiment Registry record.

The 16 documented cases:

| # | Case | Shows |
| --- | --- | --- |
| 1 | Flagship combined stress on the ERC book | full execution order; baseline + experiment record |
| 2 | Single-asset shock | explicit `zero` policy for the rest |
| 3 | Shock units side by side | bps / return / percent conversions |
| 4 | Partial scenario (`unavailable` policy) | honest partial + withheld drifted weights |
| 5 | Historical window replay | `verified_historical_window` (ex-ante) |
| 6 | Single stored period replay | smallest verifiable historical scenario |
| 7 | Full-sample window | `full_sample_descriptive` |
| 8 | Invalid future-looking ex-ante claim | `invalid`; baseline refused |
| 9 | Volatility ×2.5 | risk estimate only; zero scenario return |
| 10 | Additive volatility shock | disclosed zero-flooring |
| 11 | Correlations toward one (α 0.7) | changed dependence and risk under an explicit assumption |
| 12 | Supplied non-PSD correlation, repair `none` | honest unavailability |
| 13 | Same matrix, explicit eigenvalue floor | visible repair |
| 14 | Liquidity and cost stress | copied cost model, participation, honest impact |
| 15 | Post-shock constraint breaches | drifted-book breaches, no auto-rebalance |
| 16 | Drawdown episodes | episodes + deepest-episode attribution |

## Verification

```bash
backend/venv/Scripts/python.exe -m pytest backend/tests/test_portfolio_stress.py -q
```

```bash
cd frontend && npx tsc --noEmit
```

```bash
cd frontend && npx playwright test e2e/portfolio-stress.spec.ts --workers=1
```

The Playwright spec targets an already-running dev server (the config never
starts one). If the dev server becomes unresponsive after repeated full
runs, stop it, delete `frontend/.next`, and start it again — a documented
safe reset.

## Isolation

E2E writes are limited to the idempotent demo seeds plus one deliberately
rejected baseline attempt (409). To reset only this lab in a dev database,
delete rows from `portfolio_stress_runs` and its seven child tables plus
`experiment_registry` rows named `Portfolio stress: %` — no other registry
is touched.

## Troubleshooting

| Symptom | Cause / action |
| --- | --- |
| Net scenario return shows "— (withheld)" | shock coverage is partial while a cost leg exists — the two legs are on different bases, so both are reported separately instead of netted (see the attribution policy) |
| An episode's Peak column says "initial capital (before …)" | the episode opened on the first observed period, so the peak is the starting capital rather than an observation |
| Verified historical drawdown stops at the decision cutoff | expected: only observations strictly before the selected decision timestamp enter that causal block; full-series drawdown is descriptive |
| Drawdown cost attribution unavailable | no timestamp-aligned realized cost path is stored; the separate one-way scenario cost estimate is not imputed into episodes |
| 422 "unsupported scenario keys" | a mistyped scenario key — nothing is silently ignored |
| 422 "historical window does not reference actual stored observations" | timestamps are not on the linked portfolio's stored timeline |
| 422 "shock exceeds ±100%" | shock bound in return space |
| 422 "factor shocks are deferred in v1" | no factor-exposure system exists; expected |
| 422 "liquidity/cost stress requires a linked cost-diagnostic run" | pass `cost_diagnostic_run_id` |
| 409 on mark-baseline | integrity is not verified, the result is not complete, the stressed covariance is unavailable, or the linked dataset is invalidated |
| "the stored portfolio weights changed since this stress run was created" | the linked Phase 56 run was re-executed; create a new stress run |
| Stressed covariance unavailable | matrix is below the PSD tolerance under repair policy `none`; an explicit eigenvalue floor is available only when that modelling assumption is intended |

## Scope reminder

Scenarios are explicit assumptions, not predictions. No scenario is a worst
case, no measured loss is a guarantee, and the lab never hedges, rebalances,
trades or recommends an action. Not regulatory stress testing, not
capital-adequacy analysis, not investment advice.
