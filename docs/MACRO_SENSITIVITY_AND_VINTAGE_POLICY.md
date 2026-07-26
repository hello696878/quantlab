# Macro Sensitivity and Vintage Policy (v1)

Phase 59.0 · `backend/app/factor_diagnostics/observations.py`

## 1. Macro data is supplied, never fetched

The lab **never** downloads central-bank, statistical-agency or vendor data,
never scrapes a website, and adds no external data provider. Every macro
observation is supplied locally by the caller, exactly like every other
factor observation. The demo uses generic synthetic series (a policy-rate
level differenced into basis points); nothing in it is real economic data.

Release dates are never inferred. If a macro factor does not declare an
availability timestamp, the lab does not guess one — it **states the
assumption as a warning**:

> macro factor(s) [...] declare no release timestamp, so availability is
> ASSUMED to equal the observation timestamp. That is an assumption about
> publication timing, not a measurement; a real release lag would change
> which periods could have used the value.

## 2. Levels versus changes, percent versus basis points

Ambiguity is a validation error, not a convention:

* a rate arrives as `rate_fraction` (0.0425) or `rate_percent` (4.25) and
  must say which;
* `basis_point_change` multiplies the first difference by `10 000` for a
  fraction source and `100` for a percent source, and is **rejected** for
  any other source unit;
* `level` keeps the source unit, so a level factor's coefficient is
  "target return per 1 unit of level" and the UI prints exactly that;
* a factor in `zscore`, `index_level`, `ratio` or `count` units cannot be
  multiplied by a supplied exposure to produce a return, and the aggregation
  mode refuses it.

## 3. Timing: contemporaneous is descriptive, lagged can be verified

A macro value carrying the same period stamp as the target return gives a
**descriptive** relationship — the lab labels it
`contemporaneous_descriptive` and never calls it ex-ante or predictive.

A macro factor may reach `verified_causal_lag` only when both hold:

1. its declared lag is ≥ 1 period, and
2. the value it contributes was knowable — `available_at`, or the selected
   vintage's `release_timestamp`, whichever is later — at or before the
   information cutoff of the period it explains.

If any period fails that check the whole run is marked `invalid` with the
offending factor, timestamp and count named. A measured sensitivity is never
called a macro forecast.

## 4. Vintages and revisions

An observation may carry an ordered `vintages` list, each entry with a
`release_timestamp`, a `value` and an optional label. Release timestamps
must be strictly increasing and may not precede the period they describe.
The **original values are preserved**: a revision never overwrites the
observation's own declared value, and the selected release timestamp is
stored next to the aligned observation.

| policy | selection |
| --- | --- |
| `supplied_vintage` (default) | the observation's own declared value |
| `first_release` | the earliest release for that period |
| `latest_available_as_of_cutoff` | the latest release whose `release_timestamp` ≤ the consuming period's information cutoff |
| `full_sample_latest_descriptive` | the latest release regardless of timing |

`latest_available_as_of_cutoff` is the leak-free choice: a revision
published after a period can never reach that period's fit. When no release
exists before the cutoff the value is `unavailable` with the state
`no_release_before_cutoff`, and the period leaves the sample rather than
borrowing a later number.

`full_sample_latest_descriptive` **forces the whole run to
`full_sample_descriptive`** with an explicit warning, because it uses
revisions published after the periods they describe.

An observation with no vintage information keeps the state
`unknown_vintage` — missing vintage information stays unknown rather than
being treated as a first release.

## 5. Vintage handling is available, not assumed

Input schemas that carry no vintage information work unchanged under
`supplied_vintage`; nothing is fabricated for them. The limitation is
stated: without release timestamps the lab cannot verify publication timing
and says so in the run's warnings rather than implying a verified macro
timing claim.

## 6. What a macro sensitivity is not

A measured macro sensitivity is a least-squares coefficient over a supplied
sample under a declared transformation, unit, lag and vintage policy. It is
**not** a forecast, not evidence that the macro variable causes the return,
not a hedge ratio, not a trade, and not advice. Nothing in this lab
constructs a macro position, sizes one, or recommends one.
