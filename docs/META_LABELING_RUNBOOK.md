# Meta-Labeling Lab Runbook (Phase 51.0)

## 1. Start services

```powershell
cd C:\quantlab\backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
# separate terminal:
cd C:\quantlab\frontend
npm run dev
```

`init_db()` idempotently adds the four Phase 51 tables; existing data is
untouched.

## 2. Open the lab and load the demo

http://localhost:3000 → sidebar **Meta-Labeling Lab** (or Ctrl/Cmd+K →
"Meta-Labeling"). Click **Load demo runs** — seven deterministic runs plus
three threshold policies (one baseline); idempotent, cascades to the other
registries' idempotent demo loaders. Equivalent:
`curl.exe -X POST http://localhost:8000/meta-labeling/demo-seed`.

## 3. Create a run (API in v1)

```powershell
curl.exe -X POST http://localhost:8000/meta-labeling/runs -H "Content-Type: application/json" -d '{
  "name": "My meta run", "calibration_method": "sigmoid",
  "outcome_threshold": 0.0, "validation_run_id": 12,
  "observations": [{"sample_id": "s1", "prediction_time": "2025-01-01T00:00:00",
    "evaluation_time": "2025-01-06T00:00:00", "primary_side": 1,
    "raw_probability": 0.62, "realized_outcome": 0.013}, ...]}'
curl.exe -X POST http://localhost:8000/meta-labeling/runs/<id>/execute `
  -H "Content-Type: application/json" -d '{"create_experiment": true}'
```

Link `validation_run_id` (a completed, leakage-clean Model Validation run
whose sample ids match) for **verified OOF** calibration; link
`dataset_version_id` for lineage context. Sides: −1/0/1; side 0 abstains.

## 4. Inspect reliability and thresholds

The detail shows raw-vs-calibrated Brier / log loss / ROC AUC / PR AUC /
ECE / MCE (unavailable metrics say why), the reliability chart with its bin
table, and the threshold chart/table — click any threshold to update
coverage and confusion counts. **Save threshold policy** records *your*
selection; the lab never recommends one.

## 5. Baselines, comparison, export

Mark a saved policy as the run's baseline (one per run, transactional;
rejected on failed or not-out-of-fold runs). Tick two runs → **Compare
selected** for a neutral diff. **Export JSON** downloads runs, bins, and
policies — never paths, credentials, or model files.

## 6. Testing

```powershell
cd C:\quantlab\backend
.\venv\Scripts\python.exe -m pytest tests\test_meta_labeling.py -q
cd C:\quantlab\frontend
npx tsc --noEmit
npx playwright test meta-labeling --project=chromium   # servers must be running
```

## 7. Safe demo/test reset

Demo rows carry `demo_key` on `meta_label_runs` (their observations, bins,
and policies reference those run ids). Leave them (inert, idempotent) or
remove exactly those rows with the backend stopped and the DB backed up.

## 8. Troubleshooting

- **404** — restart the backend (predates Phase 51).
- **Failed: "requires a completed, leakage-clean validation run"** — the
  linked validation run has invalid splits or isn't executed.
- **Failed: "not members of the linked validation run"** — observation
  sample_ids must match the validation run's samples exactly.
- **Failed: "both classes"** — one-class meta-labels; calibration is
  unavailable by policy.
- **Baseline 409** — the run is failed or `not_out_of_fold`.
- **422 on grid/band** — thresholds within [0,1], ≤101 points; band lower ≤
  upper.
