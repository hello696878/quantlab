# Signal Decay Lab Runbook (Phase 60, v1)

## 1. Start the services

```powershell
cd C:\quantlab\backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

```powershell
cd C:\quantlab\frontend
npm run dev
```

Open http://localhost:3000 → sidebar → **Signal Decay Lab**. The
`signal_decay_*` tables and indexes are created idempotently on backend
start by `app/db.py`.

## 2. Load the deterministic demo

Click **Load demo runs**. The seed is idempotent (unique `demo:sd:*`
keys — loading twice creates nothing) and cascades the Phase 54 regime,
Phase 52 validation, Phase 55 cost and Phase 59 factor demo loaders (the
factor loader cascades attribution and portfolio) so linked-record cases
work on a cold database. 24 cases with hand-computable expectations,
including: horizon-1 correlations exactly ±1, mean cross-sectional rank
IC exactly 1, a decay curve with a first sign change at horizon 2, an
overlapping vs a deterministically selected non-overlapping pair,
monotone and U-shaped buckets, high vs zero turnover, lag degradation, a
gross-positive/cost-adjusted-non-positive reference, stored-regime and
frozen-threshold held-out views, a deliberately invalid future-looking
run, a raw-vs-factor-residual comparison and one eligible baseline.

## 3. API quick reference

```
GET  /signal-decay/summary                    lab summary
GET  /signal-decay/runs?query=&status=...     list (filters + paging)
POST /signal-decay/runs                       create (validates first)
GET  /signal-decay/runs/{id}                  full run
POST /signal-decay/runs/{id}/execute          execute pinned links + 7 steps
POST /signal-decay/runs/{id}/invalidate       append-only audit invalidation
POST /signal-decay/runs/{id}/mark-baseline    integrity-gated baseline
GET  /signal-decay/runs/{id}/horizons|buckets|turnover|observations|regimes|bootstrap
GET  /signal-decay/compare?run_a=&run_b=      neutral field-state comparison
GET  /signal-decay/export                     schema-versioned JSON (≤ 25 runs)
POST /signal-decay/demo-seed                  idempotent demo
```

Error mapping: 404 unknown id · 409 conflict (pin mismatch, baseline
refusal, wrong status) · 422 validation/engine refusal · 500 internal
(stale results cleared, honest message stored).

## 4. Tests

Backend (uses the project venv — global Python lacks pytest):

```powershell
cd C:\quantlab\backend
.\venv\Scripts\python.exe -m pytest tests/test_signal_decay.py -q
```

E2E (services from §1 must already be running against an **isolated test
database**; the spec only adds idempotent demo rows and never clears
anything):

```powershell
cd C:\quantlab\frontend
npx playwright test e2e/signal-decay.spec.ts --project=chromium --workers=1
```

## 5. Interpreting states

* **Integrity** — was the signal knowable before its outcome began
  ([`SIGNAL_AND_OUTCOME_TIMING_POLICY.md`](SIGNAL_AND_OUTCOME_TIMING_POLICY.md)).
  `invalid` means at least one timing violation; the run's numbers stay
  visible for forensics but it can never be a baseline.
* **Overlap** — are the outcome intervals independent
  ([`FORECAST_HORIZON_AND_OVERLAP_POLICY.md`](FORECAST_HORIZON_AND_OVERLAP_POLICY.md)).
  Overlapping runs keep their real p-values with a limitation note.
* **Completeness** — data gaps only; structural grid-end unavailability
  is disclosed separately and does not degrade completeness.
* **unavailable — reason** anywhere means the input could not support
  the statistic. It is never rendered as 0 and never hidden.

## 6. Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| 422 on create | validation refusal (bounds, unknown policy, clock horizon unit) | read the message — it names the field and the rule |
| 409 on execute | a pinned link's fingerprint changed since creation | re-create the run against the current upstream record |
| run `failed` | engine refusal at execution time | the stored `error_message` is the diagnosis; stale results were cleared |
| every statistic unavailable | constant signal/outcome, too few observations, or unique scores < bucket count | expected conservative behaviour, each row carries its reason |
| baseline rejected | integrity not verified, or completeness failed | expected: baselines are integrity-gated, never performance-gated |
| demo seed slow on first run | upstream demo cascade (regime, validation, cost, factor → attribution → portfolio) | one-time cost per database; the seed itself is idempotent |

## 7. What not to do

Do not read any statistic here as proof of predictability or alpha, do
not pick the largest-|statistic| horizon and call it best, do not treat
the equal-weight reference as a strategy, do not compare gross numbers
with costed numbers as if they were the same series, and do not use the
effective non-overlapping count as a sample size for inference.

## 10. Bootstrap boundary choice

`moving_block` bootstrap is available only for a single entity, where one
chronological order is well defined. Multi-entity panels must use timestamp
bootstrap to resample whole cross-sections; the lab refuses to create blocks
across entity boundaries.
