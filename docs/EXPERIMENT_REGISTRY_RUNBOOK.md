# Experiment Registry Runbook (Phase 48.0)

Operational steps for running, demoing, and testing the Research Experiment
Registry. Commands are PowerShell-first (Windows). The user runs the frontend
dev server, production build, and browser E2E manually.

## 1. Start the backend

```powershell
cd C:\quantlab\backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

`init_db()` runs on startup and idempotently creates the `experiment_registry`
table if it is missing (non-destructive — existing data is untouched).

## 2. Start the frontend dev server

```powershell
cd C:\quantlab\frontend
npm run dev
```

Open http://localhost:3000 and click **Experiment Registry** in the sidebar
(Product Workflow group), or press Ctrl/Cmd+K and search "Experiment Registry".

## 3. Load the deterministic demo records

Click **Load demo registry** (header or empty-state). This inserts six
clearly-marked demo records (stable `demo_key`). It is **idempotent** — clicking
again adds nothing and duplicates nothing, and it never overwrites or deletes a
real record. Equivalent API call:

```powershell
curl.exe -X POST http://localhost:8000/experiment-registry/demo-seed
```

## 4. View, filter, sort, paginate

- Summary cards show totals, completed/failed, reproducible, baselines, modules.
- The filter bar covers module, type, status, reproducibility, baseline-only, and
  a name/description search; **Reset filters** clears them.
- Click a column header to sort; use Prev/Next to page.
- Click a row's name or **View** to open the detail.

## 5. Inspect a detail

The detail shows identity/status, the reproducibility assessment (with the
per-check reasons and the honest-scope disclaimer), full fingerprints (click to
copy), provenance & lineage (Git commit, app version, dataset, seed, parent),
timing, parameters, metrics, tags, notes, any error message, and a read-only raw
JSON view. When the Dataset Lineage registry (Phase 49.0) has versions linked
to the experiment, a **Linked datasets** section lists them with their roles
and fingerprint match/mismatch flags — see
[`DATASET_LINEAGE_RUNBOOK.md`](DATASET_LINEAGE_RUNBOOK.md).

## 6. Compare two experiments

Tick the comparison checkbox on two rows (or use **Compare with…** in a detail),
then **Compare selected**. Differences are grouped and neutral; numeric metrics
show absolute and (when valid) percentage differences. No experiment is
recommended.

## 7. Mark a baseline

In a completed experiment's detail, **★ Mark as baseline** makes it the sole
baseline in its `(module, experiment_type, dataset identity)` scope; any previous
baseline in that same scope is unmarked. Baselines in other scopes are untouched.

## 8. Export

**Export JSON** downloads the current (filtered) registry as a JSON file. The
export contains the schema version, timestamp, applied filters, records,
fingerprints, and provenance — and never any local absolute paths, database
paths, secrets, or environment variables.

## 9. Testing

Backend (isolated temporary SQLite databases — never the real DB):

```powershell
cd C:\quantlab\backend
.\venv\Scripts\python.exe -m pytest tests\test_experiment_registry_fingerprints.py `
  tests\test_experiment_registry_store.py tests\test_experiment_registry_service.py `
  tests\test_experiment_registry_api.py tests\test_experiment_registry_integration.py -q
```

Frontend typecheck:

```powershell
cd C:\quantlab\frontend
npx tsc --noEmit
```

Browser E2E (only when backend + frontend are already running):

```powershell
cd C:\quantlab\frontend
npx playwright test experiment-registry --project=chromium
```

The E2E spec only performs the idempotent demo-seed plus read-only interactions;
it never mutates or deletes a real registry record. Baseline/delete/invalidate
transitions are covered by the backend tests against isolated databases.

## 10. Resetting demo/test data safely

Demo records are additive and clearly marked. To remove them from a dev database
after exploring, delete them by id via the API (they never share ids with your
real records because they are inserted as ordinary rows — check the list first):

```powershell
# List ids, then delete the demo ones you loaded:
curl.exe "http://localhost:8000/experiment-registry/experiments?page_size=100"
curl.exe -X DELETE http://localhost:8000/experiment-registry/experiments/<id>
```

Never run destructive SQL against `backend/data/quantlab.db` directly.

## 11. Troubleshooting

- **404 on `/experiment-registry/...`** — the backend predates this feature;
  restart it so the new router loads.
- **Empty table after seeding** — confirm the backend is the one the frontend
  proxies to (`BACKEND_URL`), and that `/demo-seed` returned `created > 0` or
  `skipped > 0`.
- **422 on create** — inputs failed validation (blank name, non-finite metric,
  bad SHA-256 dataset fingerprint, unknown field). The response detail names the
  field.
- **409 on complete/fail/mark-baseline** — the record is not in a state that
  allows the transition (e.g. completing an already-completed run, or marking a
  non-completed run as baseline).

## 12. Database backup reminder

The registry lives in `backend/data/quantlab.db` alongside your saved backtests
and reports. Before bulk edits or upgrades, copy that file to back it up. Never
commit the database — it is gitignored.
