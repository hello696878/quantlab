# Portfolio Constraint Policy (v1)

Exact constraint semantics (`backend/app/portfolio_diagnostics/constraints.py`).
All units are portfolio-weight fractions (1.0 = 100%). Solver output is
ALWAYS re-checked independently after every solve with the documented
tolerance (1e-6); there is no silent relaxation and no automatic removal
of constraints.

## Supported constraints

Long-only / allow-short; per-asset minimum and maximum weight (lower ≤
upper enforced; long-only requires min ≥ 0); gross-exposure limit (≤ 5.0
— this doubles as the v1 leverage bound, documented); net-exposure
target; explicit cash-residual allowance; group caps and group minimums
over |w| by declared asset group (minimum ≤ cap enforced); turnover cap
(≤ 2.0) against the half-L1 one-way turnover; frozen asset weights
(user_supplied and min_variance only in v1 — fixed bounds); excluded
assets (forced to zero; cannot also be frozen); and `max_active_assets`
as a **validation-only** count check — explicitly not a cardinality
optimizer (none exists in v1).

## Feasibility before optimization

Checked eagerly at create where decidable, with explicit 422 reasons:
bound ordering, unknown groups/assets, frozen-vs-excluded conflicts,
frozen weights outside bounds, long-only or short-enabled reachability of the
required net exposure under per-asset bounds, gross exposure below absolute
required net exposure, group-minimum reachability after exclusions, fully
group-capped universes summing below the required exposure, oversized
rebalance schedules, and sensitivity values conflicting with the
constraint set (e.g. a scenario weight cap below the configured minimum).
Method-specific structural conflicts (ERC with excluded assets, net
target ≠ 1, positive minimum weight, frozen weights, or shorting) are
likewise rejected at create. Conditions decidable only after a solve
(e.g. a turnover cap against realized turnover) are enforced by the
independent post-solve check and reported as violations — visible,
baseline-blocking, never silently relaxed.

## Post-solve verification

`check_weights` re-derives every configured constraint from the final
weights (per-asset bounds with structured asset ids, exclusions, frozen
weights, gross/net exposure, group caps/minimums, turnover cap,
max-active count) and returns a violations list with the constraint
name, a human-readable detail, the violation amount, and the affected
asset id where applicable. Violation counts appear on the run, on each
rebalance, and in the Experiment Registry record; any violation blocks
baseline marking.
