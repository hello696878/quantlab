# Forecast Horizon and Overlap Policy (Phase 60, v1)

## 1. Horizon units

Horizons and entry lags are integers counted in **observations on each
entity's own stored grid** (`unit: "observations"`, alias
`"stored_periods"`). Clock units (seconds, minutes, hours, days) are
**deferred**: converting a clock horizon onto an irregular stored grid
requires a resampling policy, and any resampling contradicts this lab's
exact-timestamp discipline. The deferral and its reason are part of the
validation error message.

Bounds: at most 12 horizons and 6 entry lags per run, horizon values
1–250, lag values 0–60, at most 100 entities and 20 000 observations —
bounded execution over silent truncation.

## 2. Overlap definition

Each evaluated pair occupies the half-open index interval
`[entry_idx, exit_idx)` on its entity's grid. Two pairs of the same
entity overlap when their intervals intersect. Back-to-back holdings
(one exiting exactly where the next enters) therefore do **not**
overlap. Per horizon × lag cell the lab stores the overlap ratio (share
of pairs overlapping at least one neighbour), the maximum number of
simultaneously open intervals, and an effective non-overlapping count.

Run-level overlap status: `non_overlapping` (no cell overlaps),
`partially_overlapping` (some do), `overlapping` (every populated cell
does). This is a separate axis from integrity by design — a
point-in-time-verified run can still be heavily overlapping.

## 3. What overlap does to p-values

Overlapping outcome intervals share price moves, so observations are not
independent and every classical p-value computed from them is optimistic
to an unknown degree. The lab's response is disclosure, not adjustment:

* the limitation note is attached to every affected statistic and shown
  in the UI next to the raw p-value — never suppressed, and the p-value
  itself is never hidden or replaced;
* the effective non-overlapping count is a documented descriptive
  approximation, **never** an inferential sample size;
* no Newey–West or similar correction is applied in v1 (that would be a
  new statistical dependency and a modelling choice; deferred).

## 4. Deterministic non-overlapping selection

When a run requests `overlap_policy: "non_overlapping"`, the lab
additionally evaluates a deterministically selected subset: keep the
earliest pair, then repeatedly keep the next pair whose entry index is at
or after the previous kept pair's exit index (per entity, ties broken by
entity id then timestamp). Both the full overlapping rows and the
selected rows are stored side by side — selection is a documented rule,
never a sampling choice, and never replaces the full sample.

## 5. Decay description across horizons

Per statistic (Spearman rank IC and top-minus-bottom spread) across the
first entry lag's horizon sequence the lab reports: the first horizon
where the sign changes, the first horizon where |statistic| falls below
the configured absolute threshold (threshold optional, must be in
(0, 1)), the horizon with the largest |statistic|, and simple ratios
between horizons. An exponential description `|stat_k| ≈ exp(a + b·k)`
is fitted only when at least 3 same-sign non-zero horizons exist; the
half-life `-ln 2 / b` is reported only when `b < 0`, otherwise null with
the reason. All of it describes this sample; the maximum-|statistic|
horizon is a location, **never "the best horizon"**, and no horizon,
lag or threshold is ever recommended.
