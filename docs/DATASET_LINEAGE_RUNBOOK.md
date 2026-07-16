# Dataset Lineage Runbook (Phase 49.0)

Operational steps for running, demoing, and testing the Data Provenance &
Dataset Lineage dashboard. PowerShell-first; the user runs frontend servers,
production builds, and browser E2E.

## 1. Start the services

```powershell
cd C:\quantlab\backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
# separate terminal:
cd C:\quantlab\frontend
npm run dev
```

`init_db()` idempotently adds the five registry tables on startup — existing
data (experiments, saved reports/backtests) is untouched.

## 2. Open the view

http://localhost:3000 → sidebar **Dataset Lineage** (Product Workflow group),
or Ctrl/Cmd+K → "Dataset Lineage". An empty registry shows the empty state
with a demo-loader action.

## 3. Load the deterministic demo lineage

Click **Load demo lineage**. This idempotently inserts 7 demo datasets,
8 versions, 5 lineage edges, quality results, and 4 experiment links (seeding
the Experiment Registry demo records first so links have targets). Clicking
again duplicates nothing and never touches real records. Equivalent:

```powershell
curl.exe -X POST http://localhost:8000/datasets/demo-seed
```

## 4. Browse datasets

Summary cards show datasets/versions/derived/quality failures/unknown
provenance/linked experiments. Filters (source, domain, format, quality,
provenance, search, demo-only) all use the dark `ql-input` controls; **Reset
filters** clears them. Click a row (or **View**) for the detail.

## 5. Follow lineage

In a detail, the **Lineage** section draws the bounded parent→child SVG graph
(selected node highlighted, invalidated nodes dashed, quality dots). Click any
node to jump to that version; the parents/children tables underneath are the
accessible fallback and show the transformation per edge. Truncation (depth/
node limits) is stated when it happens.

## 6. Review quality checks

The **Quality checks** section lists each recorded result with status and
message (e.g. the demo alt-data v1 carries a `missing_ratio_within_limit`
warning). Run more checks via the API:

```powershell
curl.exe -X POST http://localhost:8000/dataset-versions/<id>/quality-checks `
  -H "Content-Type: application/json" -d '{"checks": [], "expectations": {}}'
```

Checks validate declared structural metadata only.

## 7. Compare versions

In the version-history table, tick two versions → **Compare selected
versions** → identity, neutral schema drift (with the conservative drift
class), size metrics, fingerprints, quality, and provenance changes.

## 8. Link experiments

```powershell
curl.exe -X POST http://localhost:8000/dataset-links -H "Content-Type: application/json" `
  -d '{"experiment_id": 1, "dataset_version_id": 2, "role": "input"}'
```

Links appear on both sides: the version's **Linked experiments** section and
the experiment's **Linked datasets** section (Experiment Registry detail),
including a fingerprint match/mismatch flag when the experiment recorded a
dataset fingerprint.

## 9. Export

**Export JSON** downloads the (filtered) registry — datasets, versions,
lineage, quality, links, fingerprints, provenance. Never contains absolute
paths, database paths, credentials, or secrets. Nothing is written into the
repository.

## 10. Testing

```powershell
cd C:\quantlab\backend
.\venv\Scripts\python.exe -m pytest tests\test_dataset_registry_core.py `
  tests\test_dataset_registry_service.py tests\test_dataset_registry_api.py -q

cd C:\quantlab\frontend
npx tsc --noEmit
npx playwright test dataset-lineage --project=chromium   # servers must be running
```

The E2E spec's only writes are the idempotent demo seeds; it never mutates or
deletes real records. Invalidation and other destructive transitions are
covered by backend tests on temporary databases.

## 11. Resetting demo data safely

Demo rows are precisely identifiable by their `demo_key` (datasets and
versions) — real records never carry one. There is deliberately no delete API
for datasets in v1; to remove demo rows from a development database, stop the
backend and delete exactly the `demo_key` rows and their dependents (links,
quality results, lineage edges referencing demo versions) — or simply leave
them: they are clearly marked, inert, and idempotent. Never run destructive
SQL against a database you have not backed up.

## 12. Backup reminder

Everything lives in `backend/data/quantlab.db` alongside saved backtests,
reports, and the experiment registry. Copy that file before bulk operations.
It is gitignored — never commit it.

## 13. Troubleshooting

- **404 on `/datasets/...`** — the backend predates this phase; restart it.
- **"already exists" (409)** — dataset names and per-dataset version labels
  are unique; pick a new label or reuse the existing record.
- **422 "storage locator …"** — the locator violated the privacy policy
  (absolute path, credentials, traversal). Use the logical URI forms in
  [`DATASET_REGISTRY.md`](DATASET_REGISTRY.md) §5.
- **422 "would create a lineage cycle"** — the edge you are adding makes an
  ancestor depend on its descendant; record the derivation in the direction
  it actually happened.
- **Empty lineage graph** — the version simply has no recorded parents or
  children yet; lineage only shows what was declared.
