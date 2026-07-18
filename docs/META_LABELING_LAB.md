# Meta-Labeling, Calibration & Threshold Lab (Phase 51.0)

A **local-first** research lab evaluating a secondary meta-label layer on top
of an existing primary signal.

> **Honest scope.** The lab does not prove profitability, does not select a
> best model, does not recommend a trading threshold, provides no position
> sizing or execution instructions, and certifies nothing. Meta-label 1 means
> the documented research outcome condition was met — nothing more.

## 1–2. Purpose; primary signal and secondary meta-label

The primary signal supplies a direction per observation (`primary_side`:
**−1** negative/short, **0** no action/abstention, **1** positive/long) and
optionally a raw probability. The meta-label asks: *was that direction correct
under the documented outcome rule?* The lab then evaluates how reliable the
predicted probabilities are (calibration) and how decision thresholds trade
coverage against precision/recall.

## 3. Outcome policy

`meta_label = 1` iff `primary_side × realized_outcome > outcome_threshold`
(strict inequality — an outcome exactly at the threshold, including a zero
outcome at threshold 0, yields 0). The threshold shares `realized_outcome`'s
units, must be finite, may be negative (an explicit research choice), and
carries no hidden fees or slippage — any cost-style adjustment is the user's
explicit threshold configuration. The policy is part of the configuration
fingerprint. Missing outcomes on non-abstained observations are rejected —
never invented.

## 4. Side-zero policy

`primary_side == 0` observations are recorded as **abstained**: `meta_label`
stays null, and they are excluded from calibration fitting, probability
metrics, and threshold confusion counts. They are never converted into failed
signals.

## 5. Out-of-fold requirements

OOF statuses: `verified_from_validation_run` (calibrators fitted per split on
the linked Model Validation run's recorded train memberships and applied only
to held-out test observations; requires a completed, **leakage-clean** run,
full membership match, and no train/test overlap — violations fail the run
honestly), `declared_out_of_fold` (the caller declared the supplied raw
probabilities as already OOF — recorded as a declaration, never shown as
verified), `not_out_of_fold` (calibrator fitted on all observations —
disclosed with a warning banner), `unknown`.

## 6. Calibration methods

`none`, `sigmoid` (Platt scaling via Newton–Raphson with Platt's smoothed
targets — scikit-learn is not a project dependency, so this is a small
deterministic implementation), and `isotonic` (pool-adjacent-violators with
linear interpolation between block centers). Stored parameters are plain
floats (A/B or block arrays) — **no pickle/joblib, no model files, ever**.
Rules: fit on training data only; ≥8 labeled samples; both classes required
(one-class → honest failure); probabilities clipped only by the documented
epsilon 1e−6; raw and calibrated probabilities both preserved. Full policy:
[`PROBABILITY_CALIBRATION_POLICY.md`](PROBABILITY_CALIBRATION_POLICY.md).

## 7–8. Calibration metrics and reliability curves

Brier score, log loss, rank-based ROC AUC, average precision (PR AUC),
positive prevalence, valid count — each null with a recorded reason when
undefined (one-class folds, no probabilities), never zero-substituted.
Reliability bins (2–30; equal-width or equal-frequency) record bounds, count,
mean predicted probability, observed frequency, and absolute gap; empty bins
are kept with null statistics. **ECE** is the sample-count-weighted mean
absolute gap over non-empty bins; **MCE** is the maximum gap. The frontend
draws the diagonal + raw and calibrated curves (shape-coded: circles vs
squares) with a bin-table fallback and a small-sample disclosure.

## 9–10. Decision thresholds; coverage and abstention

Accept iff `calibrated_probability >= threshold` (boundary inclusive), over a
bounded grid (≤101 points, [0,1], deduplicated, sorted). Each row reports
accepted/rejected counts, coverage, confusion counts, precision, recall,
specificity, F1, balanced accuracy, accepted-positive rate, and optional
descriptive accepted-outcome statistics — zero denominators yield null. An
optional abstention band **sets aside** probabilities strictly inside
`(lower, upper)`: those observations are excluded from the confusion matrix
(never counted as false negatives or true negatives), so precision/recall
describe the decision population only, while coverage stays measured over all
observations; `lower > upper` is invalid. **No threshold is ever selected
as best or recommended** — the user picks; coverage stays prominent.

## 11. Threshold-policy baselines

A saved policy is a research record (name, threshold, band, fingerprint,
observed neutral metrics) — never account size, order quantity, or execution
rules. Scope: **one active baseline policy per run** (a run fixes its dataset
and calibration method, satisfying the per-run/dataset/method preference);
replacement is transactional; only completed runs qualify, and runs with
`not_out_of_fold` status are rejected for baselines.

## 12. Fingerprints

Deterministic SHA-256 over shared canonical JSON: **configuration** (label
policy, side convention, ordered observation identity, calibration method +
settings, OOF policy, threshold grid, validation-run fingerprint, seed);
**result** (configuration fp, calibration parameters, ordered raw and
calibrated probabilities, labels, metrics, bins); **policy** (result fp,
threshold, band, observed metrics). No DB ids, timestamps, or paths.
Integrity aids only.

## 13–15. Registry integrations

**Experiment Registry:** optional idempotent record (module `meta_labeling`,
Brier/ECE/prevalence metrics) — re-execution reuses the linked experiment.
**Dataset Lineage:** optional version link with fingerprints,
provenance/quality states, and a visible invalidation warning; recorded
identity preserved. **Model Validation:** the OOF evidence link — method,
leakage status, and configuration fingerprint displayed; leakage-failed runs
cannot produce verified status; split fingerprints are never modified.
Bidirectional navigation throughout. **Feature Diagnostics** (Phase 52.0,
[`FEATURE_DIAGNOSTICS_LAB.md`](FEATURE_DIAGNOSTICS_LAB.md)) may link a
meta-label run for context when feature analysis targets meta-label
predictions — the link displays this lab's OOF status, calibration method
and result fingerprint exactly as recorded and never recomputes calibration.

## 16. Demo fixture

`POST /meta-labeling/demo-seed` (idempotent, explicit): uncalibrated
overconfident run, sigmoid- and isotonic-calibrated runs (disclosed
not-OOF), an honest one-class failure, a declared-OOF run, a
**verified-OOF** run calibrated per split of the clean purged+embargo Model
Validation demo run, a run linked to the invalidated dataset demo version,
three threshold policies showing coverage trade-offs, and one baseline
policy. Seeds the other registries' idempotent demo loaders first.

## 17. API

`/meta-labeling`: `GET /summary` · `GET/POST /runs` · `GET /runs/{id}` ·
`POST /runs/{id}/execute` · `POST /runs/{id}/invalidate` ·
`GET /runs/{id}/observations` (paginated) · `GET /runs/{id}/calibration` ·
`GET /runs/{id}/thresholds` · `GET|POST /runs/{id}/threshold-policies` ·
`POST /threshold-policies/{id}/mark-baseline` · `GET /compare?a=&b=` ·
`GET /export` · `POST /demo-seed`. 404/409/422 semantics, parameterised SQL,
bounded execution (≤2000 observations).

## 18. Frontend workflow

Sidebar → **Meta-Labeling Lab** (Product Workflow group + command palette).
List: summary cards, dark `ql-input` filters, min-width runs table (OOF pill,
Brier/ECE previews, invalidated-dataset ⚠). Detail: raw-vs-calibrated metric
table (unavailable metrics say so), reliability chart + bin table, threshold
chart + table with click-to-select threshold and live coverage/confusion
stats, save-policy action (explicitly the user's own selection), policy table
with baseline marking, paginated observation table, and linked-record cards
with open actions. Compare: neutral grouped diffs.

## 19. Export

`GET /export` → runs (with metrics, threshold analysis, fingerprints, linked
identities), reliability bins, and threshold policies. Never contains
absolute paths, credentials, environment variables, or serialized model
objects. Browser download only.

## 20. Testing

`backend/tests/test_meta_labeling.py` (28 tests: policy table-driven cases,
side-zero, boundary, calibration methods + one-class + isolation, metrics +
undefined cases, bins/ECE/MCE, threshold grid + abstention, fingerprints,
OOF verification + membership mismatch, idempotent experiment linking,
dataset invalidation, policies/baselines, comparison, export privacy, demo
idempotence, adversarial paths) on temporary SQLite;
`frontend/e2e/meta-labeling.spec.ts` (10 tests).

## 21. Limitations

Observations arrive with the caller's raw probabilities — the lab trains no
primary or secondary model; verified OOF applies to *calibration fitting*
(the raw probabilities' own OOF-ness is only as good as their source);
abstention analysis is descriptive; accepted-outcome statistics are
descriptive research numbers, not P&L; and all limits are v1-bounded (≤2000
observations, ≤101 thresholds, ≤30 bins).
