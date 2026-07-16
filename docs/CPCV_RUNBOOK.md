# CPCV / Model Validation Lab Runbook (Phase 50.0)

Operational steps for the Purged CV, Embargo & CPCV Model Validation Lab.
PowerShell-first; the user runs frontend servers, builds, and browser smoke.

## 1. Start the services

```powershell
cd C:\quantlab\backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
# separate terminal:
cd C:\quantlab\frontend
npm run dev
```

`init_db()` idempotently adds `validation_runs` + `validation_splits` on
startup; existing data is untouched.

## 2. Open the lab

http://localhost:3000 → sidebar **Model Validation Lab** (Product Workflow
group), or Ctrl/Cmd+K → "Model Validation". An empty lab shows the empty
state with the demo-loader action.

## 3. Load the demo validation

Click **Load demo validation** — seven deterministic runs are created and
executed (K-fold leakage reference, walk-forward, purged K-fold, purged +
embargo, CPCV, an honest failed configuration, and a linked baseline
candidate). Idempotent; re-clicking duplicates nothing. Equivalent:

```powershell
curl.exe -X POST http://localhost:8000/model-validation/demo-seed
```

## 4. Create a run (API in v1)

```powershell
curl.exe -X POST http://localhost:8000/model-validation/runs -H "Content-Type: application/json" -d '{
  "name": "My purged CV",
  "method": "purged_kfold",
  "configuration": {"n_folds": 5, "embargo": {"mode": "duration_days", "value": 3}},
  "samples": [{"sample_id": "s1", "prediction_time": "2025-01-01T00:00:00",
               "evaluation_time": "2025-01-06T00:00:00", "label": 1, "prediction": 1}, ...]
}'
curl.exe -X POST http://localhost:8000/model-validation/runs/<id>/execute `
  -H "Content-Type: application/json" -d '{"create_experiment": true}'
```

Methods: `standard_kfold` (reference; shuffle needs an explicit seed),
`walk_forward` (`min_train_size`, `test_size`, `step_size`, `window`
expanding/rolling, `rolling_size`, `purge` default true), `purged_kfold`
(`n_folds`, `embargo`), `cpcv` (`n_groups` ≤ 12, `test_groups` < groups,
C(N,k) ≤ 100, `embargo`). Embargo modes: `duration_days` or `fraction`
(≤ 0.2). Invalid configurations are rejected at creation (422).

## 5. Inspect splits

Open a run → the **Leakage audit** stats (valid/invalid splits, purged,
embargoed, remaining overlap), the per-split table (counts, remaining
overlap, status, fingerprint), and the **split timeline** (click a split row
to select it; the membership table is the accessible fallback). For a valid
split the remaining-overlap count is always 0.

## 6. Compare runs

Tick two runs → **Compare selected** — identity, configuration, leakage &
split integrity (shown above metrics), and mean aggregate metrics, all
neutral.

## 7. Link dataset and experiment

Pass `dataset_version_id` at creation to bind a Dataset Lineage version (the
detail shows its fingerprints/provenance/quality and warns if the version was
invalidated). Execute with `{"create_experiment": true}` to record an
Experiment Registry entry once (idempotent on re-execution). Open actions in
the detail jump to the linked registries.

## 8. Mark a baseline

**★ Mark as baseline** on a completed, leakage-clean run — one baseline per
(method, dataset version) scope; the previous same-scope baseline is unmarked
transactionally. Failed, invalidated, or leakage-dirty runs are rejected (409).

## 9. Export

**Export JSON** downloads runs + splits (memberships, diagnostics, metrics,
fingerprints, linked identities) — never absolute paths or credentials.

## 10. Testing

```powershell
cd C:\quantlab\backend
.\venv\Scripts\python.exe -m pytest tests\test_model_validation_engine.py tests\test_model_validation_api.py -q
cd C:\quantlab\frontend
npx tsc --noEmit
npx playwright test model-validation --project=chromium   # servers must be running
```

## 11. Safe demo/test reset

Demo rows are identifiable by `demo_key` on `validation_runs` (their splits
reference those run ids). There is no delete API in v1 — leave demo rows (they
are inert and idempotent) or remove exactly the `demo_key` rows with a
backed-up database and the backend stopped. Never clear tables wholesale.

## 12. Troubleshooting

- **404 on `/model-validation/...`** — restart the backend (predates Phase 50).
- **422 "C(N,k) … exceeds the v1 limit"** — reduce `n_groups`/`test_groups`.
- **422 embargo errors** — one mode only; duration ≥ 0; fraction ≤ 0.2.
- **Run failed with "n_folds cannot exceed…"** — more folds than samples.
- **Standard K-fold shows invalid splits** — expected: it is the leakage
  reference; use purged K-fold or CPCV for clean splits.
- **Baseline rejected (409)** — the run must be completed AND leakage-clean.
