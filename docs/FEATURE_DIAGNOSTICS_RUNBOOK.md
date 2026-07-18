# QuantLab — Feature Diagnostics Runbook (Phase 52.0)

How to drive the Feature Importance / Stability / Drift Diagnostics Lab.
Companions: [`FEATURE_DIAGNOSTICS_LAB.md`](FEATURE_DIAGNOSTICS_LAB.md) ·
[`FEATURE_IMPORTANCE_POLICY.md`](FEATURE_IMPORTANCE_POLICY.md) ·
[`FEATURE_STABILITY_AND_DRIFT_POLICY.md`](FEATURE_STABILITY_AND_DRIFT_POLICY.md).

## 1. Start the app

```powershell
cd C:\quantlab\backend; venv\Scripts\uvicorn app.main:app --reload --port 8000
cd C:\quantlab\frontend; npm run dev   # http://localhost:3000
```

Open **Feature Diagnostics** in the sidebar (Product Workflow, after the
Meta-Labeling Lab) or via the command palette (Ctrl+K → "Feature
Diagnostics").

## 2. Load the deterministic demo

Click **Load demo runs** (or `POST /feature-diagnostics/demo-seed`).  Four
runs appear; loading again reports "nothing duplicated".  The seed cascades
the Meta-Labeling / Model Validation / Dataset Lineage / Experiment Registry
demo loaders (all idempotent, clearly-marked `demo_key` records) — real user
records are never modified.

## 3. Create a run (API)

`POST /feature-diagnostics/runs` with name, `method`
(`permutation` | `native_impurity` | `coefficient`), `model_type`
(`logistic_regression` | `linear_regression` | `decision_tree`),
`target_type`, `metric`, 1–32 `features`, 16–2000 `samples`
(`sample_id`, `timestamp`, complete numeric `features`, explicit `target`),
optional `permutation_repeats` (1–20), `seed`, `correlation`
(`{method, threshold}`), `drift` (`{mode, psi_bins, psi_thresholds}`), and
**either** `validation_run_id` **or** `declared_splits` (never both).
Bad configurations 422 at creation (duplicate features, missing values,
target-as-feature, invalid thresholds/bins/repeats).  Then
`POST /runs/{id}/execute` (optionally `{"create_experiment": true}`).

## 4. Select the dataset and validation run

Link `dataset_version_id` to a Dataset Lineage version — the detail shows
provenance/quality and warns on invalidated versions, and feature
`source_column`s are checked against the version schema (mismatch → warning,
never a fabricated mapping).  Link `validation_run_id` to a **completed,
leakage-clean** Model Validation run whose sample ids cover your samples —
that is what makes integrity `verified_held_out`.  A leakage-failed or
invalid-split run fails execution honestly (see the demo's fourth run).

## 5. Choose method and metric

`permutation` is the primary held-out method.  `native_impurity`
(decision tree) and `coefficient` (linear/logistic) are training-data
references, always labelled `not_held_out` with their caveats.  Metrics must
match the target type; each metric's direction is recorded and importance is
normalized so positive = held-out performance got worse.

## 6. Inspect importance

Detail → **Feature importance**: bars with a visible zero line, min–max
whiskers, negative importance in a distinct color, top-N control, and the
full accessible table (mean/median/std/min/max, sign fractions, stability).
"Rank 1" is a descriptive statement of highest measured importance — nothing
is recommended.

## 7. Inspect stability

**Rank stability across splits**: mean/min Spearman, mean Kendall, top-k
overlap, the per-split rank matrix, pairwise split correlations, and the
documented stability-score formula and thresholds.

## 8. Inspect correlations

**Correlated feature groups**: members, pair correlations with signs, max
|r|, and the group's combined mean importance — read this before trusting
individual ranks of correlated features.

## 9. Inspect drift

**Feature distribution drift** (explicit reference/comparison labels and
counts, PSI, KS, mean Δ, std ratio, out-of-range fraction, classification
pills) and **Importance drift** (earlier vs later splits, Δ, rank/sign
changes).  Thresholds are documented in the policy doc; drift does not prove
model failure.

## 10. Compare runs

Select two runs' checkboxes → **Compare selected**.  Identity and stability
groups plus a per-feature A/B table (importance, |Δ|, Δ%, ranks, rank
change, sign change, availability) — all neutral; no winner is declared.

## 11. Mark a baseline

Detail → **Mark as scope baseline** (completed + held-out evidence + no
invalid splits required; one baseline per method/metric/model/dataset/
validation scope, transactionally replaced).  A `not_held_out` or failed run
is rejected with a 409 — try it on the native-impurity demo run to see the
refusal.

## 12. Export

**Export JSON** downloads the filtered runs with all diagnostics and
fingerprints.  Raw feature samples, absolute paths, credentials and
serialized models are excluded by design; verify with any text editor.

## 13. Troubleshooting

* **Run failed with "leakage-clean" message** — the linked validation run is
  not completed+clean; pick a clean one (e.g. the purged+embargo demo).
* **"not members of the linked validation run"** — your `sample_id`s must
  exactly match the validation run's recorded memberships.
* **Metric unavailable on a split** — one-class fold or constant target;
  the split is recorded as failed with the reason, others still aggregate.
* **No correlation groups** — no pair exceeded the threshold; lower it
  (within 0.1–0.999) and re-create.
* **Backend offline banner** — start uvicorn on port 8000.

## 14. Safe demo/test reset

Demo records carry unique `demo_key`s (`demo:fd:*`) and cascade-linked demo
keys (`demo:ml:*`, `demo:mv:*`, `demo:ds*`, experiment demo keys).  They can
be deleted from a dev database by key without touching real records; the
Playwright suite only ever writes these idempotent seeds (plus one
deliberately-rejected baseline attempt that writes nothing).  Never delete
from a database you care about without a backup.

## Ground rules (unchanged by this doc)

Deterministic educational sample data; no live data; importance is not
causality or profitability; no automatic feature selection; not investment
advice; not production trading, risk, or compliance infrastructure.
