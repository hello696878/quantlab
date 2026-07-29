# Signal and Outcome Timing Policy (Phase 60, v1)

The single question this policy answers: **was the signal knowable before
the outcome it is paired with began?** Everything else in the Signal Decay
Lab depends on the answer being explicit, per observation, and never
assumed silently.

## 1. Availability policies

Each signal definition declares exactly one availability policy:

* **`explicit_available_at`** — every observation carries its own
  `available_at` timestamp, stating when the value was knowable. This is
  the strongest declaration and the only one eligible for
  `verified_point_in_time`.
* **`same_timestamp`** — availability is *assumed* to equal each
  observation's own timestamp. The UI marks these values "(assumed)".
  Because a value stamped *t* that was actually computed from data at *t*
  (e.g. a close-to-close return) is only safely tradable strictly after
  *t*, this policy is verified **only** when every configured entry lag is
  ≥ 1 (`verified_trailing_signal`); at lag 0 it is merely
  `supplied_descriptive`.

## 2. The timing contract

For a signal at grid index `i` on its entity's own stored grid, entry lag
`l` and horizon `k` (both in grid observations):

```
entry_ts = grid[i + l]        exit_ts = grid[i + l + k]
forward_return = price(exit_ts) / price(entry_ts) - 1
```

* Price lookups are **exact-timestamp only** — nothing is resampled,
  interpolated, forward-filled or nearest-matched. A missing price makes
  that pair unavailable with a reason (`kind: "data"`).
* The return is earned over the half-open-at-the-left interval
  `(entry_ts, exit_ts]`: the entry price is the last knowable price, the
  exit price is the last price of the holding.
* Pairs whose `i + l + k` runs past the end of the grid are structurally
  unavailable (`kind: "structural"`) — disclosed, but not a data gap.
* A delayed entry shifts **both** entry and exit stamps; the holding
  length stays exactly `k` observations.

## 3. Violations make a run invalid

A pair violates timing when `available_at > entry_ts` — the signal was
not knowable when the outcome began. One violation anywhere makes the
**whole run** `invalid`: its numbers remain visible for forensics, every
surface carries the invalid marker, and the run can never be a
comparison baseline. Violations are listed with entity, signal stamp,
availability stamp and outcome start, so the defect is auditable.

## 4. Integrity states

| State | Meaning |
| --- | --- |
| `verified_from_validation_split` | explicit availability **and** evaluated on a linked Phase 52 split by prediction time |
| `verified_point_in_time` | explicit `available_at` on every observation, zero violations |
| `verified_trailing_signal` | `same_timestamp` policy with **every** entry lag ≥ 1, zero violations |
| `supplied_descriptive` | supplied outcomes, or `same_timestamp` evaluated at lag 0 — descriptive only |
| `full_sample_descriptive` | the `rank_full_sample` transformation was used: each score depends on the whole sample, so nothing point-in-time can be claimed |
| `unknown` | integrity could not be established |
| `invalid` | at least one timing violation |

The spec's `overlapping_descriptive` notion is represented as a separate
run-level **overlap status** axis rather than an integrity state, so that
"was the signal knowable" and "are the samples independent" stay
independently visible — see
[`FORECAST_HORIZON_AND_OVERLAP_POLICY.md`](FORECAST_HORIZON_AND_OVERLAP_POLICY.md).

## 5. Transformations and orientation

`rank_cross_sectional` ranks each timestamp's own universe and stays
point-in-time eligible. `rank_full_sample` ranks over the entire sample
and therefore demotes integrity to `full_sample_descriptive` — useful as
a descriptive contrast, never as evidence. The declared direction
(`higher_is_higher_score` / `higher_is_lower_score`) is an explicit part
of the definition and is **never inferred from the signal's name**; an
inverting direction negates configured scores while raw stored values
remain unchanged, and a warning discloses the inversion.

## 6. Supplied outcomes

Supplied outcomes are accepted verbatim as descriptive data: horizons are
the single literal `"supplied"`, only lag 0 is allowed, and integrity is
capped at `supplied_descriptive` because the lab cannot verify how they
were computed.
