# Purged CV, Embargo & CPCV Model Validation Lab (Phase 50.0)

A **local-first** validation lab for time-dependent financial research:
temporal-event samples, four split methods, interval-based purging, a
configurable embargo, a from-scratch leakage audit, neutral fold metrics,
deterministic fingerprints, and links to the Experiment Registry and Dataset
Lineage registries.

> **Honest scope.** This lab demonstrates and audits split methodology. It
> does not prove a model is profitable or correct, is not scientific
> certification or regulatory validation, does not eliminate leakage outside
> the represented information intervals, and nothing here is investment,
> trading, or risk advice.

## 1. Purpose

Answer, for a set of time-dependent samples: do training and test labels
overlap in time; which samples must be purged or embargoed; how do K-fold,
walk-forward, purged K-fold, and CPCV differ; are all samples assigned
correctly; is any split leaking; how stable are metrics across folds; and can
the split configuration and result be reproduced (fingerprints) and traced
(registry links)?

## 2. Information intervals

Each sample carries `prediction_time` (when the signal becomes available) and
`evaluation_time` (when the outcome is fully known), interpreted as the
**closed interval** `[prediction_time, evaluation_time]` — both boundaries
inclusive, matching `app/finml/cv.py`. Overlap: `a.start <= b.end AND a.end >=
b.start`; exact boundary contact **counts as overlap** (conservative — purges
more, never less). Full rules: [`PURGED_CV_AND_EMBARGO_POLICY.md`](PURGED_CV_AND_EMBARGO_POLICY.md).

Sample validation: `evaluation_time >= prediction_time`; timezone-consistent
timestamps (all naive or all aware; aware normalized to UTC); unique ids;
finite labels/predictions/scores/returns/weights; deterministic sort by
(prediction, evaluation, id); missing evaluation times are an error unless the
explicit `allow_missing_evaluation="prediction_time"` policy is set — label
end times are never inferred silently. Bounds: 4–2000 samples per run.

## 3. Temporal leakage

A training sample whose information interval overlaps a test sample's interval
shares future information with the test set. Chronological order alone does
not fix this: the last pre-test training labels extend INTO the test window.

## 4. Standard K-fold (reference only)

Included for comparison; shuffle is OFF by default and enabling it requires an
explicit seed. The UI and the run description warn that ordinary K-fold leaks
with overlapping labels — its splits are expected to audit **invalid**.

## 5. Walk-forward

Expanding (default) or rolling training windows; chronological test folds;
configurable `min_train_size`, `test_size`, optional `step_size`,
`rolling_size`; capped at 50 folds. No sample at/after a test block's start
enters its training set, and **boundary purging is ON by default** (disable
with `"purge": false` for an educational reference — those folds audit
invalid). A configured embargo applies as in purged K-fold.

## 6. Purged K-fold

Contiguous time-ordered test blocks (2–20 folds). For each fold, every
candidate training sample whose interval overlaps ANY test interval is purged
— by interval, never by row index or adjacency. Per split the lab returns the
candidate/retained/purged/test counts, the purged sample ids, and per-id
overlap reasons ("overlaps test sample X").

## 7. Embargo

One mode at a time: `{"mode": "none"}`, `{"mode": "duration_days", "value": d}`
(d ≥ 0, fractional days allowed), or `{"mode": "fraction", "value": f}`
(0 ≤ f ≤ 0.2 of the total observation span). The embargo removes training
samples whose interval **starts** inside `(block_end, block_end + delta]` —
start-exclusive (a sample starting exactly at the block end is already purged
by closed-interval overlap), end-inclusive — applied **after each disjoint
test block**, with chain-overlapping windows merged into one effective
interval per block. Windows extending past the dataset end are harmless.
Purged and embargoed samples are always reported separately. Rejected:
negative durations, fractions above 0.2, unknown modes, non-finite values.

## 8. CPCV

`N` contiguous time-ordered groups (2–12), all `C(N, k)` deterministic test-
group combinations (`1 ≤ k < N`), purge + embargo per combination, stable
split ids (`cpcv-g0-g1`, …). Conservative v1 limit: **C(N,k) ≤ 100** —
configurations beyond it are rejected with a clear 422 at creation (and again
at execution). v1 outputs the combination split set (path assembly is a
documented future extension).

## 9. Split fingerprints

Deterministic SHA-256 over the shared canonical JSON (sorted keys,
NaN/Infinity rejected, no database ids, no wall-clock timestamps, no paths):
**configuration** (method + ordered sample identity [id, prediction,
evaluation] + configuration + seed when set), **split** (configuration fp +
label + sorted train/test/purged/embargoed ids), **result** (configuration fp
+ split fps + aggregate metrics + leakage summary + linked dataset identity).
Integrity aids only.

## 10. Leakage audit

Every split is re-audited from scratch: train/test counts, purge/embargo
counts, prediction/evaluation time ranges for both sides, **remaining
train/test interval overlaps (recomputed)**, chronological violations
(walk-forward), duplicate assignments, unassigned samples, test label balance,
group coverage, and interval-span statistics. **Critical invariant:** any
remaining overlap marks the split `invalid` with example pairs — never
silently valid. A run is `leakage_clean` only when every split is valid.

## 11. Metrics

Dependency-light and neutral (no scikit-learn): classification (accuracy,
balanced accuracy, binary precision/recall/F1, rank-based ROC AUC, log loss
for probability scores), regression (MAE, MSE, RMSE, R²), and supplied-return
statistics (mean, std, hit rate, cumulative sum, and a `sharpe_like` ratio
explicitly labeled a simplified research statistic). Metrics are computed only
when inputs are available and mathematically valid; otherwise **null with a
recorded reason** — never hidden, never Infinity, never coerced to zero.
Cross-fold aggregation: mean/median/std/min/max/valid-fold count. Split
integrity is displayed above performance metrics.

## 12. Baseline policy

Scope: at most one active baseline per **(method, dataset_version_id)** —
runs without a dataset link share the NULL-dataset scope per method. Only
`completed` runs with **all splits valid and a passed leakage audit** qualify;
marking transactionally unmarks the previous same-scope baseline, leaves other
scopes untouched, and is idempotent. Failed/invalidated/dirty runs → 409.

## 13. Experiment Registry integration

`POST /runs/{id}/execute` with `{"create_experiment": true}` records a
completed experiment (module `model_validation`, type = method, split/leakage
metrics, method configuration, seed) via the best-effort integration helper.
**Idempotent:** once `experiment_id` is set on the run, re-execution reuses it
— no duplicates. Failed executions are recorded honestly on the run itself.

## 14. Dataset Lineage integration

A run may link a `dataset_version_id` at creation (404 if missing). The run
detail shows the dataset name/version, manifest fingerprint, provenance and
quality states, and a **visible warning when the version has been invalidated**
— the recorded identity is always preserved on historical runs. Runs without a
dataset link remain fully supported.

## 15. Demo validation

`POST /model-validation/demo-seed` (or the "Load demo validation" button)
creates + executes seven deterministic runs over a shared 60-sample series
with overlapping 5-day horizons: K-fold leakage reference (audits invalid),
walk-forward, purged K-fold, purged K-fold + embargo, CPCV (C(5,2)=10), an
intentionally invalid configuration (recorded as an honest `failed` run), and
a leakage-clean baseline candidate linked to the Dataset Lineage KO/PEP demo
version and an Experiment Registry record. Idempotent (`demo_key`), explicit
action only, never touches real records; the other registries' demo loaders
are seeded first so links have targets.

## 16. API

`/model-validation`: `GET /summary` · `GET/POST /runs` · `GET /runs/{id}` ·
`POST /runs/{id}/execute` · `POST /runs/{id}/mark-baseline` ·
`POST /runs/{id}/invalidate` · `GET /runs/{id}/splits` ·
`GET /runs/{id}/leakage-audit` · `GET /runs/{id}/samples` · `GET /compare?a=&b=`
· `GET /export` · `POST /demo-seed`. Filters: method, status, dataset version,
experiment, baseline, leakage status, text query, created range, configuration
fingerprint; bounded pagination and stable sorting; 404/409/422 semantics;
parameterised SQL; execution bounded and deterministic.

## 17. Frontend workflow

Sidebar → **Model Validation Lab** (Product Workflow group; command palette
entry). List: summary cards, dark `ql-input` filters, min-width runs table
(leakage pill, baseline star, key-metric preview, fingerprints). Detail:
identity + status + leakage audit stats, K-fold leakage warning, linked
dataset/experiment cards with open actions, aggregate-metrics table, per-split
table, and the **split timeline** — every sample's interval drawn on a true
temporal axis, colored + patterned by assignment (retained/test/purged/
embargoed/unused/invalid-overlap; hatching and dashed outlines accompany
color), bounded to 400 rows with explicit truncation, with a membership-table
fallback as the accessible alternative. Compare: neutral grouped diffs with
split integrity above metrics. v1 creates runs via the API; the UI creates
runs through the demo loader (a UI run-builder is a future extension).

## 18. Export

`GET /export` → `{schema_version, exported_at, filters, runs, splits}` with
memberships, diagnostics, metrics, fingerprints, and linked identities — no
absolute paths, credentials, environment variables, or database paths; sample
payloads are omitted from run objects (memberships live on splits). Browser
download only; nothing is written into the repository.

## 19. Testing

`backend/tests/test_model_validation_engine.py` (events, boundary/overlap
cases, splitters, embargo modes, audit invariant, fingerprints, metrics) and
`test_model_validation_api.py` (persistence/migration, lifecycle, baseline
scope, links, comparison, export privacy, demo idempotence, adversarial
paths, registry coexistence) on temporary SQLite; `npx tsc --noEmit`;
`frontend/e2e/model-validation.spec.ts` (11 tests).

## 20. Meta-Labeling Lab integration (Phase 51.0)

The Meta-Labeling Lab ([`META_LABELING_LAB.md`](META_LABELING_LAB.md)) uses a
completed, leakage-clean validation run's recorded split memberships as
out-of-fold evidence for probability calibration — fitting per split on train
members and applying only to held-out test members. Split fingerprints are
never modified by that use.

The Feature Diagnostics Lab
([`FEATURE_DIAGNOSTICS_LAB.md`](FEATURE_DIAGNOSTICS_LAB.md), Phase 52.0)
consumes the same memberships for **verified held-out permutation
importance**: its estimators fit per split on recorded train members and
evaluate importance only on held-out test members, requiring a completed,
leakage-clean run with all splits valid; membership mismatches fail honestly
and split fingerprints are carried through unchanged.

The Overfitting Diagnostics Lab
([`BACKTEST_OVERFITTING_DIAGNOSTICS_LAB.md`](BACKTEST_OVERFITTING_DIAGNOSTICS_LAB.md),
Phase 53.0) may link a validation run for display context (method, split
counts, leakage status, fingerprints).  Its CSCV blocks are contiguous
chronological subperiods **without interval purging** — PBO complements, and
never replaces, this lab's split-level validation; linked records are never
rewritten.

The Regime Diagnostics Lab
([`REGIME_DIAGNOSTICS_LAB.md`](REGIME_DIAGNOSTICS_LAB.md), Phase 54.0) uses
a completed, leakage-clean run's **exact recorded training membership** of a
named split to fit training-only regime thresholds
(`verified_from_validation_split` integrity): held-out observations never
affect the thresholds, unknown memberships and invalid or leakage-failed
splits fail honestly, and split memberships/fingerprints are never
modified.

The Cost Diagnostics Lab
([`TRANSACTION_COST_DIAGNOSTICS_LAB.md`](TRANSACTION_COST_DIAGNOSTICS_LAB.md),
Phase 55.0) may link a validation run to display its method, leakage status
and fingerprints beside a cost-diagnostic run; cost evaluation is read-only
— split memberships and fingerprints are never changed.

The Portfolio Diagnostics Lab
([`PORTFOLIO_DIAGNOSTICS_LAB.md`](PORTFOLIO_DIAGNOSTICS_LAB.md), Phase
56.0) uses a completed, leakage-clean run's **exact recorded training
membership** of a named valid split to restrict covariance-estimation
windows to training observations only
(`verified_from_validation_split` integrity): held-out observations never
affect training-only estimates, unknown memberships and invalid or
leakage-failed splits fail honestly, full-sample estimation cannot be
combined with a split link, and split memberships / purge / embargo /
fingerprints are never modified.

The Portfolio Stress Lab
([`PORTFOLIO_STRESS_LAB.md`](PORTFOLIO_STRESS_LAB.md), Phase 57.0) does
not link validation runs directly: it inherits whatever provenance the
stressed Phase 56 portfolio run recorded, and its own timing discipline is
scenario-level (a historical window may claim `ex_ante` only when it ends
strictly before that portfolio's decision cutoff). Nothing in this lab is
read or modified by a stress run.

## 21. Limitations

Sample membership is stored as bounded JSON arrays (≤2000 samples/run —
documented persistence decision for v1); CPCV emits the combination split set
rather than assembled backtest paths; metrics evaluate supplied predictions/
scores (the lab trains no models); the audit covers only the represented
intervals — features built from wider windows can still leak outside them; and
the demo/UI sample series is deterministic synthetic data, not market data.
