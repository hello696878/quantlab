# Strategy Ensemble Weight, Contribution and Cost Policy

## Explicit static weights

Only equal weight (`1/N`) or `user_static`, with exactly one nonnegative weight
for every strategy. Each supplied weight is at most 10; effective total exposure
is at most 10. Negative weights and all-zero allocations are rejected. Zero
members remain part of the declared alignment universe. No automatic allocation.

Normalization is explicit: `require_sum_to_one` (default), `normalize_by_sum`,
`normalize_by_gross`, or `none`. With nonnegative weights, sum/gross normalization
coincide. `none` preserves the supplied total. Original/effective weights, sum,
gross/net, maximum absolute weight, zero members and residual are returned.

These are **strategy return weights**, not evidence of actual funded capital,
margin or executable exposure. Internal leverage already reflected in a source
is never multiplied again. Optional internal exposure observations remain source
metadata; absent exposure is not fabricated from returns.

## Return and contribution

```text
component_contribution[i,t] = effective_weight[i] * supplied_return[i,t]
ensemble_return[t] = sum(component_contribution[i,t])
```

Per-period reconciliation residual and maximum residual are explicit. Period
returns compound from wealth 1. Cumulative arithmetic contributions, signed
shares (null near a zero aggregate), positive/negative periods and absolute
shares are descriptive. Absolute-contribution concentration is the sum of
squared absolute shares. Summed arithmetic contributions do NOT reconcile to
geometric multi-period return; the difference is returned, not hidden.
No Phase 58 geometric linking or causal allocation of losses is implied.

## Turnover

The v1 `static_return_reference` has unchanged target weights and reports zero
**subsequent target-weight change**, not zero executed trading. Initial turnover
is unavailable by default. Opt-in `zero_prior_weights` reports
`0.5 * sum(abs(weight))` as a half-L1 target-allocation reference.
Executed rebalance turnover is null: no holdings drift, cash, notionals, cadence
or rebalance execution is modeled. Scenario comparisons are alternatives, not
chronological rebalances.

Underlying turnover and costs are read only from supplied observations. Sums
are available only if all common-period observations for that strategy provide
the field. No inferred turnover, missing-as-zero fallback, or combination of
underlying turnover with target-allocation turnover.

## Cost basis and double-count protection

Each source declares `gross`, `net_of_strategy_costs`, `partially_costed` or
`unknown`; every observation must match its definition. Input returns are used
verbatim. **No underlying cost is deducted again**, including supplied net
returns and optional Phase 55-style source cost information.

When all nonzero-weight sources have a common gross or net basis, the matching
ensemble reference is available. Mixed/partial/unknown basis cannot be called
gross or net; unavailable references remain null. Zero-weight members do not
determine active cost basis. No reverse reconstruction of gross from net.

Allocation costs are not modeled, so fully net executable performance is always
unavailable. A net-of-strategy-costs reference is not fully cost-complete.
Source declarations are not independently verified; no claim of execution realism.

## Scenarios and held-out data

At most 12 caller-defined scenarios plus Base. Equivalent effective weights and
initial-build/cost/rebalance policy are fingerprint-deduplicated. Coverage,
return, volatility, drawdown, concentration, common-matrix correlation, turnover
and cost completeness remain descriptive. No automatic grid and no winner.

Linked validation reuses exactly the same weights in training and held-out
blocks. There is no optimizer, refit or strategy selector. Changes to explicit
weights/policies create a new run identity. See [lab](STRATEGY_ENSEMBLE_DIAGNOSTICS_LAB.md).
