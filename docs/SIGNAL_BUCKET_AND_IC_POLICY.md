# Signal Bucket and IC Policy (Phase 60, v1)

## 1. Correlation statistics

Per horizon × lag cell, over aligned (score, outcome) pairs:

* **Pearson**, **Spearman** and (on request) **Kendall** via
  `scipy.stats` — Kendall is explicitly the tie-adjusted tau-b variant,
  and every p-value is the real scipy value;
* **sign agreement**: share of pairs where sign(score) equals
  sign(outcome), reported with its base count;
* constants, samples below the configured minimum, and degenerate ties
  make a statistic unavailable **with a reason** — never 0, never NaN.

Spearman uses average ranks under the declared tie policy; tie counts
are stored and shown. The overlap p-value limitation note travels with
every affected cell (see
[`FORECAST_HORIZON_AND_OVERLAP_POLICY.md`](FORECAST_HORIZON_AND_OVERLAP_POLICY.md)).

## 2. Cross-sectional IC

At each timestamp with at least 3 entities holding both a score and an
outcome, the lab computes the Spearman rank correlation over **that
timestamp's own eligible universe** — never a pooled panel pretending to
be a cross-section. Aggregates across timestamps: mean, median, standard
deviation, a descriptive `ic_ratio` (mean/std, unavailable when std is
0 or undefined), and the share of positive/negative timestamps. A
time-series association for a single entity and a cross-sectional IC
across entities are different measurements and are labelled as such.

## 3. Equal-count rank buckets

* 2–10 buckets, global scope (rank the whole sample once) or
  `per_timestamp` scope (rank each timestamp's universe);
* deterministic tie ordering: (score value, entity id, timestamp) — the
  same input always yields the same buckets;
* every bucket row stores its count, score min/max, outcome mean, median,
  sample standard deviation and positive rate; bucket outcomes are pooled
  observation-weighted, so under `per_timestamp` scope a timestamp with more
  eligible entities has more weight;
  a `minimum_per_bucket` guard makes underpopulated bucketing
  unavailable with a reason;
* when the number of **unique** scores is smaller than the bucket count
  (binary or constant signals), bucket assignment would be arbitrary
  tie-splitting, so the spread is conservatively unavailable with
  exactly that reason;
* under a linked validation split, global bucket thresholds are derived from
  TRAINING observations only and applied **frozen** to held-out observations;
  if training cannot fit them, the held-out bucket spread is unavailable,
  never refitted. Per-timestamp bucketing has no persistent fitted threshold
  and uses only each timestamp's contemporaneous signal cross-section.

## 4. Top-minus-bottom spread

The spread is the outcome mean of the top bucket minus the outcome mean
of the bottom bucket: a **neutral equal-weight measurement reference**
with gross exposure 2.0 (1.0 long, 1.0 short), not a strategy, not a
portfolio, and never sized. Gross values never include costs;
cost-adjusted values (linked Phase 55 model, notional-proportional
components only) are always a separate column — see
[`SIGNAL_TURNOVER_AND_IMPLEMENTATION_LAG_POLICY.md`](SIGNAL_TURNOVER_AND_IMPLEMENTATION_LAG_POLICY.md).

## 5. Monotonicity

Bucket-mean monotonicity is described by the direction of adjacent
bucket-mean differences: consistent steps, violations, and a strict/
non-strict flag. No trend test and no p-value is attached — a monotone
staircase in this sample is a description of this sample, not evidence
of predictability.

## 6. Multiple testing

When several horizon × lag cells are evaluated, their Spearman p-values
form the declared family (ordered by lag, then horizon) and are adjusted
with the shared Phase 53 utility (Bonferroni, Holm, Benjamini–Hochberg;
priority Holm > BH > Bonferroni when several are configured). Raw
p-values are always displayed next to adjusted ones. Adjustment changes
the honesty of the disclosure, not the descriptive nature of the lab.
