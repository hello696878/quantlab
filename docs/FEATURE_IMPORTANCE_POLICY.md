# QuantLab — Feature Importance Policy (Phase 52.0)

What a feature-importance number in the Feature Diagnostics Lab means, what
it does not mean, and the rules every importance computation follows.
Companion: [`FEATURE_DIAGNOSTICS_LAB.md`](FEATURE_DIAGNOSTICS_LAB.md).

## 1. What importance means

A permutation-importance value is the **measured change in one evaluation
metric on one evaluation set when one feature column is shuffled** — a
sensitivity of this model, under this metric, on these samples.  Positive
importance means the permutation made held-out performance worse; a value
near zero means the model's held-out performance barely depends on that
column; the ranking is descriptive ("highest measured importance", "rank 1
under the selected method").

## 2. What importance does NOT mean

* **Not causality.** A feature can be important through correlation with an
  unmeasured driver; permuting it breaks the model's use of it, not the
  world's.
* **Not profitability.** No importance value implies a tradable edge, and
  the lab never says a feature is profitable, best, or recommended.
* **Not feature selection.** The lab never deletes, keeps, or recommends
  features; correlated-group and stability views exist so a human can reason,
  not so the system can act.
* **Not model quality.** A confidently wrong model produces confident
  importance values.

## 3. Held-out evaluation requirements

Trusted (verified) importance requires: splits from a completed,
leakage-clean Model Validation run with all splits valid; the model fitted
per split on recorded **train members only**; evaluation only on that
split's **held-out test members**; exact membership matching (unknown sample
ids fail the run); train/test overlap rejected; purged/embargoed membership
preserved; validation results never rewritten.  Caller-declared splits are
validated structurally and labelled `declared_held_out` — a recorded
declaration, never verified.  Fitting and evaluating on the same samples is
allowed but always labelled `not_held_out` with a warning, and such runs can
never become baselines.

## 4. Metric direction

Every metric declares `higher_is_better` or `lower_is_better`, stored in the
run configuration, and importance is direction-normalized:

```
higher_is_better:  importance = baseline_score − permuted_score
lower_is_better:   importance = permuted_score − baseline_score
```

so positive importance always reads the same way.  Baseline and permuted
scores are retained per split.  Undefined metrics (one-class ROC AUC,
constant-target R², empty folds) stay unavailable with a reason — never
silently zero.

## 5. Permutation policy

Exactly one feature column is permuted at a time, only within the evaluation
set; the target and all other features are untouched; the model is never
refitted for a permutation; permuting across train and test together is
forbidden by construction.

## 6. Repeat and seed policy

Repeats are bounded (1–20, default 5).  Every shuffle uses a deterministic
RNG seeded from (run seed, split index, feature index, repeat index), so any
run reproduces bit-identical results; changing the seed is a configuration
change and changes the configuration fingerprint.  Per-repeat values feed
mean/median/std/min/max and positive/negative repeat counts — the spread is
part of the result, not noise to hide.

## 7. Negative importance

Negative values (permutation *improved* the metric) are legitimate outcomes
for weak or noisy features on finite samples.  They are displayed honestly
— in the chart (distinct color, zero line visible), tables, and exports —
never clipped to zero.

## 8. Correlated-feature interpretation

When features correlate, permutation importance can **split** across them
(each looks weaker than the group) or one can **mask** another.  Read the
correlation-group view (members, pair correlations, combined mean
importance) before interpreting individual ranks.  The lab groups; it never
removes.

## 9. Model-native importance caveats

Impurity-based importance (decision tree) may favor high-cardinality
features, splits across correlated features, is computed from **training
data** (not held-out degradation), and is not causal.  It is a reference,
never the primary trusted method, and such runs are labelled
`not_held_out`.

## 10. Coefficient caveats

Coefficient magnitude is scale-dependent unless standardized (the lab
standardizes and says so); correlation between features affects both
magnitude and sign; sign is not proof of causality.  Coefficients from
different model families are never merged into one score.

## 11. No causal interpretation — ever

No output of this lab may be described as causal, and the UI, exports and
docs avoid "causal", "best feature", "recommended feature" and "optimal"
phrasing by policy (enforced by an E2E check).  This policy file is the
contract: importance is measurement, interpretation stays with the
researcher.
