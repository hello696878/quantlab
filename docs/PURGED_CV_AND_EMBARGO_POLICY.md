# Purged CV & Embargo Policy (Phase 50.0)

The exact rules the Model Validation Lab applies. These mirror the interval
semantics of `app/finml/cv.py` (López de Prado, AFML ch. 7), generalized from
bar indices to timestamps.

## Interval convention

A sample occupies the **closed interval** `[prediction_time,
evaluation_time]` — both boundaries **inclusive**. `prediction_time` is when
the signal becomes available; `evaluation_time` is when the label is fully
known. `evaluation_time >= prediction_time` always.

## Overlap rule

Intervals `A` and `B` overlap iff `A.start <= B.end AND A.end >= B.start`.
**Exact boundary contact counts as overlap** (a training label ending exactly
when a test label starts is purged). This is deliberately conservative: it can
purge slightly more than strictly necessary, never less.

## Purging rule

For each split, every candidate training sample whose interval overlaps ANY
test sample's interval is removed from training and reported in
`purged_ids` with a per-id reason. Purging is interval-based only — never by
row index, adjacency, or fold arithmetic. Handled cases (all unit-tested):
train starts inside test; train ends inside test; train contains test; test
contains train; exact boundary contact; multiple disjoint test intervals;
long-horizon samples; irregular timestamps.

## Embargo rule

The embargo removes training samples whose interval **starts** in the window
`(block_end, block_end + delta]` after a test block:

- **start-exclusive** — a sample starting exactly at `block_end` overlaps the
  closed test interval and is already purged;
- **end-inclusive** — a sample starting exactly at `block_end + delta` is
  embargoed;
- `delta` comes from exactly one mode: `duration_days` (≥ 0, fractional
  allowed) or `fraction` (0–0.2 of the span from the earliest prediction time
  to the latest evaluation time). Supplying conflicting or unknown modes,
  negative durations, or fractions above 0.2 is rejected.

## Multiple test blocks

Test samples are merged into disjoint time blocks; an embargo window follows
**each** block. Chain-overlapping windows are merged, so the reported
`embargo_windows` are the effective disjoint intervals (the removed-sample set
equals the union either way).

## Final boundary

An embargo window extending past the last observation removes nothing extra
and is reported as configured — no clipping surprises.

## Irregular timestamps

All rules operate on real timestamps; nothing assumes equal spacing. The
timeline visualization also uses a true temporal axis.

## Missing label end times

Never inferred. A sample without `evaluation_time` is rejected unless the run
explicitly opts into `allow_missing_evaluation="prediction_time"`, which uses
a zero-length interval at the prediction time (useful only for genuinely
instantaneous outcomes — documented, visible in the stored samples).

## Deterministic split identity

Samples are stably sorted by (prediction_time, evaluation_time, sample_id);
fold blocks and CPCV combinations are constructed deterministically; shuffled
K-fold requires an explicit seed. Split fingerprints hash the configuration
fingerprint + sorted membership ids, so identical inputs always produce
identical split identities.

## Leakage-clean definition

A run is **leakage-clean** iff every generated split has, after purge and
embargo: zero remaining train/test interval overlaps (recomputed from
scratch), zero duplicate assignments, and zero chronological violations
(walk-forward). One invalid split makes the run not leakage-clean; invalid
splits are marked and reported, never silently kept.

## What these checks do NOT prove

They validate the represented intervals only. They cannot see leakage through
features computed from windows wider than the declared intervals, through
overlapping data preprocessing, through hyperparameter selection on the same
data, or through any information channel outside the sample metadata. A
leakage-clean audit is a methodology check — not proof of model quality,
profitability, scientific validity, or regulatory compliance.
