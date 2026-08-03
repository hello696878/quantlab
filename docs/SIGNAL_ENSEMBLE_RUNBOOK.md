# Signal Ensemble Lab Runbook (Phase 61, v1)

## 1. Start the services

```powershell
cd C:\quantlab\backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

```powershell
cd C:\quantlab\frontend
npm run dev
```

Open http://localhost:3000 → sidebar → **Signal Ensemble Lab**. The
`signal_ensemble_*` tables and indexes are created idempotently on
backend start by `app/db.py`.

## 2. Load the deterministic demo

Click **Load demo runs**. The seed is idempotent (unique `demo:sen:*`
keys — loading twice creates nothing) and cascades the Phase 54 regime,
Phase 52 validation, Phase 55 cost and Phase 59 factor demo loaders (the
factor loader cascades attribution and portfolio) so linked-record cases
work on a cold database. 24 cases with hand-computable expectations,
including: pairwise correlations exactly ±1, a constant signal and a
thin-overlap pair honestly unavailable, strict-intersection (18 keys)
versus pairwise-complete (30 keys) on the same pair, a redundant trio
with effective signal count exactly 1 and one cluster, a rank-deficient
matrix with the condition number unavailable rather than infinite,
equal-weight / user-weight / negative-weight combinations whose
contributions reconcile to 1e-9, require-all versus renormalise-available
missing policies, churn that cancels versus churn that is created by
combining, training-versus-held-out separation, regime-flipping
similarity, horizon-shifting response, a raw-versus-factor-residual
comparison, a cost-linked reference and one eligible baseline.

## 3. API quick reference

```
GET  /signal-ensembles/summary                 lab summary
GET  /signal-ensembles/runs?query=&status=...  list (filters + paging)
POST /signal-ensembles/runs                    create (validates first)
GET  /signal-ensembles/runs/{id}               full run
POST /signal-ensembles/runs/{id}/execute       execute (pins links)
POST /signal-ensembles/runs/{id}/invalidate    append-only audit
POST /signal-ensembles/runs/{id}/mark-baseline integrity-gated baseline
GET  /signal-ensembles/runs/{id}/pairwise|matrix|components|horizons|
     leave-one-out|regimes|bootstrap|sensitivity
GET  /signal-ensembles/compare?a=&b=           neutral comparison
GET  /signal-ensembles/export                  schema-versioned JSON (≤25)
POST /signal-ensembles/demo-seed               idempotent demo
```

Error mapping: 404 unknown id · 409 conflict (pin mismatch, baseline
refusal, wrong status) · 422 validation/engine refusal · 500 internal
(stale results cleared, honest message stored).

## 4. Tests

Backend (uses the project venv — global Python lacks pytest):

```powershell
cd C:\quantlab\backend
.\venv\Scripts\python.exe -m pytest tests/test_signal_ensemble.py -q
```

E2E (services from §1 must already be running against an **isolated
test database**; the spec only adds idempotent demo rows and never
clears anything):

```powershell
cd C:\quantlab\frontend
npx playwright test e2e/signal-ensemble.spec.ts --project=chromium --workers=1
```

## 5. Interpreting states

* **Integrity** — were all components knowable at each combined
  observation's timestamp, and did the horizon evaluation stay
  violation-free. `invalid` means at least one violation; the numbers
  stay visible for forensics but the run can never be a baseline.
* **Completeness** — full combination coverage + complete matrix +
  (when linked) complete costs; anything less is `partial`, nothing is
  `unavailable` unless no combined score exists at all.
* **Reconciliation** — `reconciled` (linear modes, 1e-9),
  `not_applicable` (majority sign), or `failed` (run-level error, never
  redistributed).
* **unavailable — reason** anywhere means the input could not support
  the statistic. It is never rendered as 0 and never hidden.

## 6. Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| 422 on create | bounds, duplicate ids, mixed frequencies, unknown policy, weights that break the declared normalisation | the message names the field and the rule |
| 409 on execute | a pinned link's fingerprint changed since creation | re-create the run against the current upstream record |
| pairwise rows unavailable | constants, heavy ties or overlap below the minimum | expected conservative behaviour; the overlap count is on the row |
| matrix diagnostics unavailable | at least one correlation cell unavailable, or a non-PSD matrix beyond tolerance | expected: nothing is imputed and nothing is repaired |
| combined scores unavailable | require_all with missing components, or rank normalisation without enough entities per timestamp | expected; missing ids and reasons are per row |
| baseline rejected | integrity not verified, completeness failed, or reconciliation failed | expected: baselines are integrity-gated, never performance-gated |
| demo seed slow on first run | upstream demo cascade (regime, validation, cost, factor → attribution → portfolio) | one-time cost per database; the seed itself is idempotent |

## 7. What not to do

Do not read a low correlation as independent information or a high one
as duplication, do not treat the effective signal count as the true
number of independent signals, do not read a leave-one-out delta as an
instruction to drop a signal, do not compare gross with cost-adjusted
numbers as one series, do not treat any combination here as a strategy,
and do not read any of it as investment advice.
