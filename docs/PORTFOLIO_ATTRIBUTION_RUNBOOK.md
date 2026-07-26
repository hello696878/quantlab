# Portfolio Attribution Lab Runbook (v1)

Operating the Phase 58.0 Portfolio Performance Attribution, Benchmark and
Active Risk Lab locally.

## Prerequisites

- Backend on :8000 (`scripts/run_backend.ps1`), frontend dev server on :3000.
- Interpreter for tests: `backend\venv\Scripts\python.exe`.
- Clear `PYTHONIOENCODING` before backend suites on Windows (cp950 subprocess
  decode noise): `Remove-Item Env:PYTHONIOENCODING`.

## Load the demo

`POST /portfolio-attribution/demo-seed`, or the **Load demo runs** button in
the Portfolio Attribution view. Seeding is idempotent (unique `demo_key`),
cascades the Phase 55 demo loader, and creates its **own** hand-computable
Phase 56 books (`demo:pd:attr-*`) through the Phase 56 public service — no
existing record is modified. Only the flagship creates an Experiment Registry
record.

Each demo book repeats an exact two-period return cycle and is restored to
its target weights every period, so the beginning-of-period weights are
exactly the declared targets:

```
type A:  eq-a +2%, eq-b +4%, bd-a +1%, bd-b −1%
type B:  eq-a −1%, eq-b −2%, bd-a  0%, bd-b +2%
```

The 17 documented cases:

| # | Case | Shows |
| --- | --- | --- |
| 1 | Flagship allocation attribution | 1.80% / 1.50% / 0.30% all allocation; baseline + experiment record |
| 2 | Identical benchmark | exactly zero active return, zero TE, IR unavailable |
| 3 | Within-group selection effect | selection isolated from allocation |
| 4 | Non-zero interaction effect | the third term reported separately |
| 5 | Portfolio-only group | benchmark holds no bonds → unavailable terms + visible residual |
| 6 | Benchmark-only group | an explicit commodity sleeve with explicit returns and group |
| 7 | Zero group weight on both sides | no fabricated group return |
| 8 | Arithmetic linking | the compounding gap disclosed |
| 9 | Carinó linking | linked effects reconcile with the geometric active return |
| 10 | Gross versus cost-adjusted | costs separate; impact honestly unavailable |
| 11 | Contribution concentration | 85% in one asset |
| 12 | Long/short book | documented negative-weight group semantics |
| 13 | Contribution-only (no benchmark) | benchmark-relative results unavailable |
| 14 | Buy-and-hold benchmark | drifting benchmark weights |
| 15 | Invalid end-of-period timing | `invalid`; baseline refused |
| 16 | Unspecified frequency | annualized TE withheld |
| 17 | Brinson-Hood-Beebower variant | the alternative allocation convention |

## Verification

```bash
backend/venv/Scripts/python.exe -m pytest backend/tests/test_portfolio_attribution.py -q
```

```bash
cd frontend && npx tsc --noEmit
```

```bash
cd frontend && npx playwright test e2e/portfolio-attribution.spec.ts --workers=1
```

The Playwright spec targets an already-running dev server (the config never
starts one). If the dev server becomes unresponsive after repeated full runs,
stop it, delete `frontend/.next`, and start it again — a documented safe
reset.

## Isolation

E2E writes are limited to the idempotent demo seeds plus one deliberately
rejected baseline attempt (409). To reset only this lab in a dev database,
delete rows from `portfolio_attribution_runs` and its six child tables, the
`demo:pd:attr-*` Phase 56 books, and `experiment_registry` rows named
`Portfolio attribution: %` — no other registry is touched.

## Troubleshooting

| Symptom | Cause / action |
| --- | --- |
| 422 "Brinson attribution requires an explicit benchmark definition" | declare a benchmark, or use `attribution_method: contribution_only` |
| 422 "an equal-weight benchmark must be written out explicitly" | supply the weight vector; there is no implicit fallback |
| 422 "benchmark-only assets need explicit returns" | supply returns for assets the portfolio does not hold |
| 422 "unsupported policy keys" / "unsupported benchmark keys" | a mistyped key — nothing is silently ignored |
| 422 "log-return attribution is deferred" | v1 supports simple returns only |
| Run is `invalid` | end-of-period weight timing, or a linked centered weight basis |
| 409 on mark-baseline | integrity not verified, result not complete, or reconciliation outside tolerance |
| "the linked portfolio run changed since this attribution run was created" | re-create the run against the current Phase 56 record |
| Reconciliation `residual` | expected for one-sided groups or non-unit weight sums; the reason is stored per period |
| Information ratio unavailable | tracking error is zero — never reported as infinite |
| Annualized TE unavailable | the return frequency was declared `unspecified` |

## Scope reminder

Measured contributions and effects under a stated convention. The lab does
not prove alpha, prove manager skill, recommend a benchmark or a portfolio,
guarantee future performance, produce GIPS-compliant reporting, perform tax
accounting, execute trades, or provide investment advice.
