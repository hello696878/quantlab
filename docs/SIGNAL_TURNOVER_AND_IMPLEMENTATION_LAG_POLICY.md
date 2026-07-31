# Signal Turnover and Implementation Lag Policy (Phase 60, v1)

## 1. Why turnover is measured here

A signal whose ranking churns every observation implies trading whether
or not anyone trades it. The lab measures that implication descriptively
at a reference rebalance cadence (each stored timestamp with a full
cross-section) for the same equal-weight top-vs-bottom reference used by
the spread — a measurement device, not a strategy.

## 2. One-way turnover

Let `w_t` be the combined signed reference weights: +1 allocated equally
across the top bucket and -1 allocated equally across the bottom bucket
(gross exposure 2.0). Then:

```
one_way_turnover_t = 0.5 · Σ_i |w_t(i) - w_{t-1}(i)|
```

Both legs are measured directly. An asymmetric bottom-leg change is not
approximated by doubling top-leg turnover.

Initial-rebalance policies are explicit:

* **`no_prior_unavailable`** (default) — the first rebalance has no
  prior book, so its turnover is null, labelled "unavailable (no
  prior)", and excluded from means;
* **`zero_prior_full_build`** — the first rebalance is a full build from
  cash and counts at its actual (maximal) value.

Membership churn is additionally reported as top-bucket Jaccard
similarity between consecutive rebalances, entry/exit counts per
rebalance, and the average holding duration in rebalances.

## 3. Holding-period overlap

When the holding horizon spans `k` observations but rebalances happen
every observation, up to `k` cohorts are open simultaneously. The lab
reports the maximum and average number of concurrently open cohorts and
the implied gross exposure under the declared normalisation:
`none_disclosed` (gross exposure grows with cohort count — disclosed,
not hidden) or `per_cohort_equal_split` (each cohort gets 1/k of the
reference book). Nothing is netted silently.

## 4. Implementation lags

Entry lags model implementation delay only: a lag `l` means the signal
observed at grid index `i` is acted on at `grid[i+l]`, and the holding
still spans exactly the configured horizon. Lag surfaces (statistic by
horizon × lag) describe how the measured association degrades as entry
is delayed. **No lag is ever called optimal or recommended** — the lab
reports the degradation, full stop.

## 5. Cost mapping (linked Phase 55 model, read-only)

The linked cost model is pinned by id and fingerprint and read verbatim.
Only notional-proportional components are computable in this lab:

* commission when expressed as bps of notional;
* spread as `fixed_bps × configured fraction`;
* slippage when expressed as fixed bps per side.

Impact models and monetary-per-unit models are **unavailable with
reasons** — mapping them onto a unitless reference book would require
inventing volumes. With computable per-side bps `c` and one-way turnover
`τ` on the combined signed gross-2 book and reference notional `N`
(validated to [1e3, 1e9]):

```
total_traded_notional = 2 · τ · N
per_rebalance_cost = (c / 1e4) · total_traded_notional
```

The cost-adjusted spread is reported only for the first configured horizon
and lag used to construct the turnover timeline: gross top-minus-bottom
spread minus the **mean** per-rebalance reference cost return. Holding periods and
rebalance intervals are different time bases; the mismatch is disclosed
rather than rescaled. Gross and cost-adjusted values are always separate
columns, and missing cost inputs stay unavailable — never zero.
