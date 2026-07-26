# QuantLab — Feature Stability & Drift Policy (Phase 52.0)

Definitions and thresholds for every stability and drift number the Feature
Diagnostics Lab reports.  Companion:
[`FEATURE_DIAGNOSTICS_LAB.md`](FEATURE_DIAGNOSTICS_LAB.md).

## 1. Rank stability

Within each valid split, features are ranked by mean importance — rank 1 is
the highest measured importance in that split, and **ties receive average
ranks** (scipy `rankdata`, method `average`), so tied features share a
fractional rank instead of an arbitrary order.  Across splits the lab
records mean/median rank, rank standard deviation and rank range per
feature.

**Stability score (transparent formula):**

```
stability_score = 1 − min(1, rank_std / max_spread)
max_spread      = (n_features − 1) / 2
```

Defined only with ≥ 2 valid splits and ≥ 2 features; otherwise null.
Classification thresholds (documented, fixed in v1):

| classification      | condition            |
|---------------------|----------------------|
| `stable`            | score ≥ 0.75         |
| `moderately_stable` | score ≥ 0.50         |
| `unstable`          | score < 0.50         |
| `unknown`           | score undefined      |

These are research diagnostics — an unstable feature is an observation to
investigate, not automatically a bad feature, and the lab never deletes or
demotes it.

## 2. Sign consistency

Per feature: the fraction of valid splits with positive mean importance and
with negative mean importance; `sign_consistency = max(pos, neg)` and a
boolean flag when both signs occur.  A sign that flips across folds is
reported as such — with no judgement attached.

## 3. Split comparisons

Pairwise over the first 12 valid splits (truncation disclosed): Spearman and
Kendall correlations of the per-split mean-importance vectors over their
shared defined features (≥ 2 required), and top-k overlap
`|topk(A) ∩ topk(B)| / k` with `k = min(5, n_features)`.  Constant vectors
or too-few shared features make a pair's correlation null with a note —
never NaN.  Summary values are means/minimum over defined pairs only.

## 4. Distribution-drift reference/comparison policy

Reference and comparison sets are always explicit and labelled with their
sample counts:

* `early_vs_late` (default) — the earlier vs later half of the
  timestamp-sorted samples (deterministic midpoint).
* `first_vs_last_split` — the held-out test members of the first vs last
  valid split (requires linked or declared splits).

Empty sets make the diagnostic unavailable; fewer than 30 samples on either
side attaches a small-sample warning ("indicative only").

The two-sample KS statistic is reported for any two non-empty sets, including
the degenerate case where both sides are internally constant: two *different*
constants are the strongest possible shift and score 1.0, two equal constants
score 0.0.  (PSI, by contrast, is genuinely undefined for a constant
reference — see §5 — and is reported as unavailable there.)

## 5. PSI definition

Population Stability Index over explicit equal-width bins anchored on the
**reference** range (4–50 bins, default 10); comparison values outside the
range are clipped into the boundary bins and additionally reported as an
`out_of_range_fraction`; both frequency vectors get a smoothing epsilon of
1e-6 before

```
PSI = Σ (cmp_frac − ref_frac) · ln(cmp_frac / ref_frac)
```

A constant reference makes PSI honestly unavailable (`unknown`
classification).  Empty bins are safe by construction (the epsilon).

## 6. KS definition

Two-sample Kolmogorov–Smirnov statistic and p-value via scipy's asymptotic
method (deterministic, defined for tied samples).  Reported alongside PSI,
never merged with it.

## 7. Drift classification thresholds

By PSI, documented and configurable within safe bounds
(0 < low < moderate < high ≤ 10):

| classification | default condition   |
|----------------|---------------------|
| `none`         | PSI < 0.02          |
| `low`          | 0.02 ≤ PSI < 0.10   |
| `moderate`     | 0.10 ≤ PSI < 0.25   |
| `high`         | PSI ≥ 0.25          |
| `unknown`      | PSI unavailable     |

## 8. Importance-drift classification

Valid splits are halved by split order (earlier half vs later half; ≥ 2
valid splits required, otherwise unavailable).  Per feature: early/late mean
importance, difference, |Δ%| when `|early| > 1e-12`, rank change, sign
change.  Classification by |Δ%|: none < 10 ≤ low < 25 ≤ moderate < 50 ≤
high; unknown when the percentage is undefined.  Wording is restricted to
increased / decreased / sign changed / unchanged / unavailable.

## 9. Small samples and missing data

Missing feature values are rejected at input (v1 policy — no imputation), so
missing-rate drift is structurally zero and not reported as a statistic.
Small-sample warnings propagate into the run's warning list and the UI.
Aggregates over zero defined values are null, never zero.

## 10. What drift does NOT prove

Distribution drift describes a change between two sample sets.  It does
**not** prove the model failed, does not imply a trading decision, position
change, or risk judgement, and does not certify anything about live
behavior.  Importance drift likewise describes measured sensitivity moving
between split halves — the interpretation belongs to the researcher.
