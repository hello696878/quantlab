# QuantLab — Feature Importance, Stability & Drift Diagnostics Lab (Phase 52.0)

The local-first research lab that measures which features a model depends on
and whether those dependencies stay stable across validation splits, time
periods and dataset versions.  Companions:
[`FEATURE_IMPORTANCE_POLICY.md`](FEATURE_IMPORTANCE_POLICY.md) (what
importance does and does not mean) ·
[`FEATURE_STABILITY_AND_DRIFT_POLICY.md`](FEATURE_STABILITY_AND_DRIFT_POLICY.md)
(stability/drift definitions and thresholds) ·
[`FEATURE_DIAGNOSTICS_RUNBOOK.md`](FEATURE_DIAGNOSTICS_RUNBOOK.md) (how to
drive it) · [`MODEL_VALIDATION_LAB.md`](MODEL_VALIDATION_LAB.md) (the splits
it consumes) · [`META_LABELING_LAB.md`](META_LABELING_LAB.md) (optional link).

> **Honest scope.** Importance here is a measured sensitivity under one
> method, one model and one metric.  It is **not** proof of causality, not
> proof of profitability, not automatic feature selection or deletion, not
> model selection, not position sizing or execution, not scientific
> certification, not regulatory model validation, and not investment,
> trading, tax, legal, or risk advice.  No live data is fetched anywhere.

## 1. Purpose

For a bounded, caller-supplied feature matrix and target, the lab answers:
which features are most influential under the selected method; was importance
evaluated only on held-out data where required; how stable are rankings
across folds; are signs and magnitudes consistent; do correlated features
split or mask importance; does feature-distribution drift accompany
importance drift; which Dataset Lineage version supplied the features, which
Model Validation run supplied the splits, which Experiment Registry record
stores the result; and can the analysis be reproduced via fingerprints.
Anything unavailable or uncertain is reported as unavailable — never
substituted with zeros.

## 2. Feature definitions and input model

A run declares 1–32 **feature definitions** (`feature_name` unique, ≤ 64
chars, `data_type: numeric` only in v1, optional display name / source
column / group / description / dataset schema reference) and 16–2000
**samples** (`sample_id` unique, ISO-8601 `timestamp` with one timezone
convention, a complete `features` object, and an explicit `target`).

Explicit v1 policies (recorded in every run's configuration):

* **Missing values are rejected** — no imputation exists, so none is
  silently applied.
* **Categorical features are not supported** — callers pre-encode to numeric
  columns upstream and own that encoding.
* **The target is always explicit** — it is never inferred from a column
  position, a feature may not be named `target`, and a feature that is the
  target (or an exact affine transform of it, |correlation| = 1) is rejected
  as target leakage at creation.
* Samples sort deterministically by (timestamp, sample_id); features keep
  the declared order.

## 3. Held-out permutation importance (primary method)

For every valid split: the estimator is fitted on the split's **training
members only**; the baseline metric is evaluated on the **held-out test
members**; then exactly one feature column is permuted *within the held-out
set* (the target and every other column untouched) and the metric is
re-evaluated.  Repeats (1–20, default 5) use deterministic seeds derived
from (seed, split index, feature index, repeat) — the same run always
reproduces the same numbers.  Per-feature, per-split statistics (mean /
median / std / min / max, positive/negative/valid repeat counts, within-split
rank) aggregate across splits into mean/median/std/min/max importance, mean/
median rank, rank std/range, positive-split fraction, and a quantile interval
**only when ≥ 4 valid splits exist** (never fabricated from fewer).
Permutation never crosses train and test, and never refits the model.

## 4. Metric direction

Supported metrics (task-matched, from the local registry): classification —
`log_loss`, `brier`, `roc_auc`, `pr_auc`, `balanced_accuracy`, `f1`
(threshold 0.5, documented); regression — `mae`, `mse`, `rmse`, `r2`.  Each
metric carries a direction, and importance is normalized so **positive
importance always means permuting the feature made held-out performance
worse**:

* higher-is-better: `importance = baseline_score − permuted_score`
* lower-is-better:  `importance = permuted_score − baseline_score`

Undefined metrics (one-class fold for ROC AUC, constant target for R²,
empty fold) are reported as unavailable with a reason; a split whose baseline
is undefined is recorded as failed and excluded from aggregates.  Nothing is
zero-substituted, and no NaN/Infinity ever leaves the API.

## 5. Model-native importance (reference only)

The bounded deterministic CART tree exposes impurity-based importance.  It is
shown as a clearly-labelled reference with fixed caveats: it may favor
high-cardinality features; correlated features may split importance; it is
**training-data derived**, not held-out degradation; and it is not causal.
A run whose primary method is `native_impurity` is therefore always
`not_held_out`.

## 6. Coefficient magnitude (reference only)

Logistic/linear models expose standardized coefficients (raw sign + mean
absolute magnitude per split, with a sign-consistency flag).  Caveats always
shown: magnitude is scale-dependent unless standardized (ours are), feature
correlation affects interpretation, and sign is not proof of causality.
Incompatible methods are never combined into one score.

**Drop-column importance is deliberately omitted in v1** — it multiplies
model refits by features × splits and adds retraining-equality subtleties;
the omission is documented rather than half-implemented.

## 7. Rank stability

Within each split, features are ranked by mean importance (rank 1 = highest;
ties get average ranks).  Across splits the lab reports per-feature
mean/median rank, rank std/range, sign consistency, and a transparent
stability score with documented thresholds (see
[`FEATURE_STABILITY_AND_DRIFT_POLICY.md`](FEATURE_STABILITY_AND_DRIFT_POLICY.md));
plus pairwise split Spearman and Kendall correlations of the importance
vectors and top-k overlap (k = min(5, features)), bounded to the first 12
valid splits with any truncation disclosed.  Undefined correlations are null
with a reason.  `stable / moderately_stable / unstable / unknown` are
research diagnostics — an unstable feature is not automatically bad.

## 8. Correlated features

Pearson (default) or Spearman correlation over all normalized samples
(features only — the target is never included), a validated absolute
threshold (default 0.8, allowed 0.1–0.999), and deterministic
connected-component grouping of pairs above threshold.  Constant features
have undefined correlation and are excluded with a warning.  Groups show
members, pair signs/magnitudes and a descriptive combined mean importance —
because correlated features can split or mask importance between them.
Nothing is removed automatically and correlation is never presented as
causation.

## 9. Distribution drift

An explicit reference set is compared against an explicit comparison set
(v1 modes: `early_vs_late` timestamp halves, or `first_vs_last_split` test
members when splits exist).  Numeric diagnostics per feature: mean/median
difference, std ratio, p10/p50/p90 quantile changes, two-sample KS statistic
(scipy, asymptotic method), PSI over explicit equal-width bins anchored on
the reference range (4–50 bins, default 10, smoothing ε = 1e-6), and the
out-of-range fraction.  Small samples (< 30 on either side) carry a warning;
constant references make PSI honestly unavailable.  Categorical drift is out
of scope with categorical features (v1).  Drift **describes a data change —
it does not prove model failure** and carries no financial interpretation.

## 10. Importance drift

The valid splits are halved by split order; per feature the lab reports
early/late mean importance, difference, percentage difference (only when the
denominator is meaningful), rank change, sign change, and a classification
from documented |Δ%| thresholds — using only neutral wording (increased /
decreased / sign changed / unavailable), never improved/worsened/safer.

## 11. Held-out integrity

* `verified_held_out` — splits come from a linked, **completed,
  leakage-clean** Model Validation run with all splits valid; memberships are
  matched exactly (unknown sample ids fail the run), train/test overlap is
  rejected, purge/embargo membership is preserved, and split fingerprints are
  carried through unchanged.
* `declared_held_out` — the caller supplied explicit splits; they are
  validated structurally (no overlap, known ids, minimum train size) but the
  declaration is **recorded, not verified**.
* `not_held_out` — no splits (fit and evaluate on all samples) or a
  native/coefficient method; always disclosed with a warning.
* `unknown` — not executed yet, or failed.

Linked validation results are never rewritten.  When a Meta-Labeling run is
linked, its OOF status, calibration method and result fingerprint are
displayed as recorded — a declared status is never shown as verified, and
calibration is never recomputed.

## 12. Baseline policy

A completed run with held-out evidence (verified or declared), no invalid
splits and a result fingerprint may be marked as the **baseline of its
scope** — one active baseline per (method, metric, model type, dataset
version, validation run).  Marking is transactional (the previous same-scope
baseline is unmarked in the same transaction), idempotent, and never
automatic — no run is ever selected by highest score or stability, and a
baseline is a comparison reference, not a recommendation.  Invalidating a
run clears its baseline flag.

## 13. Fingerprints

Deterministic SHA-256 over canonical JSON (UTF-8, sorted keys, stable
separators, NaN/Infinity rejected):

* **configuration** — method, model type + hyperparameters, target type,
  metric + direction, ordered feature names, sample identity (ids,
  timestamps, rounded values, targets), split source + declared splits +
  linked validation-run fingerprint, permutation repeats + seed, correlation
  and drift settings, and the missing-value/encoding policies.  Excludes DB
  ids, wall-clock timestamps, durations, absolute paths and any serialized
  model bytes.
* **result** — configuration fingerprint + ordered split-level results +
  aggregates + stability summary + correlation groups + drift + warnings +
  integrity status.
* **baseline** — result fingerprint + the baseline scope.

Fingerprints are integrity aids only — they prove *what was recorded*, not
that the analysis is correct.

## 14. Integrations

* **Experiment Registry** — optional `create_experiment` on execute records
  a neutral `feature_diagnostics` experiment (method, metric, integrity, top
  feature names as descriptive metadata, stability/drift summary counts,
  both fingerprints); idempotent across re-executions.
* **Dataset Lineage** — linked versions show name/label, manifest
  fingerprint, provenance/quality status and an invalidation warning;
  feature `source_column`s are checked against the version's schema snapshot
  and mismatches produce **warnings, never fabricated mappings**.
* **Model Validation** — linked runs show method, leakage status, split
  counts and fingerprints; leakage-failed or invalid-split runs make
  execution fail honestly.
* **Meta-Labeling** — optional context link (OOF status, calibration
  method, result fingerprint) for analyses that target meta-label
  predictions.

## 15. Demo fixture

`POST /feature-diagnostics/demo-seed` (or the UI button) idempotently loads
four deterministic runs — see the docstring of
`backend/app/feature_diagnostics/demo.py`: (1) the verified held-out
flagship (stable dominant feature, correlated pair, unstable noise, drifting
feature; marked baseline), (2) importance drift without distribution drift
over declared splits (linked to the verified-OOF meta-labeling demo run),
(3) a model-native impurity reference, (4) an honest failure against the
leakage-failed validation demo run.  Seeding cascades the Meta-Labeling /
Model Validation / Dataset Lineage / Experiment Registry demo loaders (all
idempotent, unique `demo_key`); reloading creates nothing and never touches
real records.  There is no startup insertion.

## 16. API

`/feature-diagnostics/*`: `GET summary`, `GET/POST runs` (filters:
status/method/metric/integrity/validation run/dataset version/config
fingerprint/baseline/query; bounded pagination; stable sorting),
`GET runs/{id}`, `POST runs/{id}/execute`, `POST runs/{id}/invalidate`,
`POST runs/{id}/mark-baseline`, `GET runs/{id}/features|splits|correlations|
drift`, `GET compare?a&b`, `GET export`, `POST demo-seed`.  422 for invalid
input, 404 for unknown ids, 409 for state conflicts; parameterized SQL only;
no raw stack traces, no file access, no model upload, no unsafe
deserialization, no provider calls.  Execution is deterministic and bounded
(≤ 2000 samples, ≤ 32 features, ≤ 20 repeats, ≤ 12 declared splits).

## 17. Frontend workflow

Sidebar → **Feature Diagnostics** (also in the command palette).  List view:
disclaimer header, six summary cards, dark-theme filters, runs table
(integrity pills, rank-1 feature, stable/drift counts, truncated
fingerprints, baseline stars) with internal horizontal scrolling.  Detail
view: identity + fingerprints + baseline action, warnings, linked-record
cards, the importance bar chart (zero line, min–max whiskers, negative
importance in a distinct color, top-N control, full accessible table),
rank-stability matrix + pairwise correlations, correlation groups,
distribution/importance drift tables with classification pills, caveated
model references, and split-level results.  Neutral comparison view with a
per-feature A/B table.  Usable at 1440/1024/768 with no page-level
horizontal overflow.

## 18. Export

`GET /feature-diagnostics/export` returns schema-versioned JSON
(`feature_diagnostics_export_v1`): applied filters, runs with configuration
and fingerprints, aggregate/split results, stability, correlation groups,
drift rows, linked identities and provenance.  **Raw feature samples are
deliberately excluded**, as are absolute paths, environment variables,
credentials and serialized model objects; NaN/Infinity are rejected.
Exports download through the browser — nothing is written into the
repository automatically.

## 19. Testing

`backend/tests/test_feature_diagnostics.py` (37 tests, isolated temporary
SQLite databases): input validation + target leakage, deterministic
estimators, metric direction + undefined cases, permutation signal/
determinism/single-column purity, negative importance, tied ranks, stability
(Spearman/Kendall/top-k, score boundaries), correlation groups + constant
features + threshold validation, drift (PSI/KS, config validation,
importance drift), fingerprint sensitivity, verified/declared/not-held-out
integrity via real Model Validation runs, leaky-run and membership-mismatch
honesty, baseline scope transitions + rejections, migration idempotence with
existing registries preserved, experiment/dataset/meta-labeling
integrations, neutral comparison, export privacy, demo idempotence, and
adversarial API paths.  `frontend/e2e/feature-diagnostics.spec.ts` (15
Playwright tests) covers the browser workflow — see
[`BROWSER_E2E_RUNBOOK.md`](BROWSER_E2E_RUNBOOK.md).

## 20. Limitations (v1)

Numeric features only (categoricals must be pre-encoded upstream); three
deterministic in-process estimators (no external model import — by design,
since unsafe deserialization is banned); drop-column importance omitted;
distribution drift is univariate; importance drift halves splits by order
rather than calendar time; declared held-out splits are recorded
declarations, not verified; the quality of any conclusions is bounded by the
caller-supplied samples.  And permanently: measured importance is not
causality, not profitability, and never a recommendation.
