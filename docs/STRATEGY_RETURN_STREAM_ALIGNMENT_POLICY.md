# Strategy Return Stream Alignment and Timing Policy

## Observation contract

Every observation has a strategy ID, `period_start`, `period_end`, decimal
`return_value`, cost basis and `information_available_at`. Optional turnover,
cost-return, gross/net exposure and source observation IDs are never inferred.
Returns are **simple arithmetic**, finite and greater than -1 (upper bound 100).
Ensemble returns at or below -1 and wealth overflow/underflow fail clearly.

ISO timestamps normalize to UTC, including offset-aware inputs. Naive dates or
times explicitly mean UTC, not the host timezone. Period end must follow start;
per-strategy duplicates and overlaps fail validation. Observations must lie in
the declared definition window and use its cost basis. All selected definitions
must declare the same frequency and currency. No resampling or FX conversion.
Frequency is a declared label, not a separately verified trading calendar.

## Exact samples

Alignment keys are the exact pair `(period_start, period_end)`. Two rows sharing
a start but with different ends are different periods. Never align row offsets.

The ensemble and correlation matrix **always use strict intersection** of all
strategies, including zero-weight members. Pairwise diagnostics can explicitly
use `pairwise_complete`, with each row showing its own N and sample policy.
Those pairwise cells are never assembled into a purported common-sample matrix.

Coverage reports union size, common size, stored/missing/excluded counts and
common/stored ratio for each strategy. Missing means union keys absent from that
strategy; excluded means stored keys not in the all-strategy intersection.
Gaps count non-adjacent observed intervals; weekends can be gaps too. No forward
fill, interpolation, zero fill, omitted-period cash return or hidden inference.
At least two common periods are required to execute. Statistics have separate
minimum-N policies. Compounded wealth covers observed periods only, not a
continuous calendar exposure across gaps.

## Availability

Execution requires, for every input observation:

```text
configuration_available_at <= period_start
weights_available_at <= period_start
information_available_at >= period_end
```

Returns are realized outcomes, not tradable contemporaneous signals. The lab
does not generate or shift strategy signals and does not change source timing.
Availability violations mark a run failed, with no valid result or baseline.
Passing these checks means **declared timing passed**, not proven point-in-time
data or leakage-free human parameter choice.

Stored validation membership is exact, with evaluation time equal to return
period end. A later outcome publication fails that link because its recorded
label interval would not cover availability. Purge/embargo sets are never
recomputed or altered. Dataset links are optional and read-only; unlabeled
lineage is not invented. See [lab](STRATEGY_ENSEMBLE_DIAGNOSTICS_LAB.md).
