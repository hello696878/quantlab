# Stress Scenario Definition Policy (v1)

How Portfolio Stress Lab scenarios are defined, validated and classified.
Nothing in this policy predicts anything; every scenario is an explicit
assumption.

## Scenario types

`historical_window`, `historical_single_period`, `hypothetical_asset_shock`,
`hypothetical_group_shock`, `volatility_stress`, `correlation_stress`,
`liquidity_and_cost_stress`, `combined_scenario`, `user_supplied_descriptive`.

**Factor shocks are deferred in v1** and rejected with an explicit reason: no
estimated, run-linked factor-exposure system exists in this repository, and
exposures are never inferred from asset names.

## Shock units (explicit, unambiguous)

| Unit | Meaning | Example |
| --- | --- | --- |
| `return` | decimal simple return | −0.05 = −5% |
| `percent` | value / 100 | −5 = −5% |
| `bps` | value / 10 000 | −500 = −5% |

Absolute **price** changes are NOT supported in v1: stored portfolio universes
carry returns, not reference prices, and the lab never fabricates a price.
Shocks are bounded to ±100% in return space. Non-finite values are rejected.

## Precedence (deterministic)

An asset-specific shock overrides its group shock; a group shock overrides the
global shock; assets covered by none follow the explicit
`missing_shock_policy`:

- `zero` — an explicitly configured "unshocked" assumption (a configuration,
  not silence);
- `unavailable` — the asset carries no assumed shock; the scenario total
  covers the shocked subset only, the run is `partial`, and drifted weights
  are withheld.

Overlapping shocks are never combined additively — the precedence chain
selects exactly one source per asset, and the chosen source is stored per
asset (`asset` / `group` / `global` / `policy_zero` / `unavailable`).

## Historical scenarios

A historical window must reference **actual stored observations** of the
linked portfolio's universe (start/end timestamps must exist on the stored
timeline; end ≥ start). Per-asset shocks are the compounded simple returns
over the window. The timing usage is explicit:

- `ex_ante` — verified only when the window ends **strictly before** the
  portfolio decision cutoff of the selected rebalance; a window that reaches
  or passes the cutoff is **invalid** (a future period is never labelled
  ex-ante verified).
- `descriptive` — realized post-decision analysis, warned as such.

A window spanning the whole sample is `full_sample_descriptive`.

## Bounds

|shock| ≤ 100% (return space); volatility multipliers in (0, 10]; additive
volatility within ±1.0 per-period units (negative results floor at zero with
disclosure); correlation multipliers in (0, 2], additive within ±2,
`toward_one` alpha in [0, 1]; supplied correlations in [−1, 1] and n×n in the
portfolio's asset order; liquidity multipliers in (0, 100]; sensitivity ≤ 40
scenarios (≤ 5 values per dimension). Execution is bounded and deterministic.

## Integrity states

`verified_historical_window` · `verified_deterministic_rule` (fully explicit
hypothetical parameters) · `supplied_descriptive` (user-supplied outcomes —
never called verified) · `full_sample_descriptive` · `unknown` · `invalid`.
`linked_to_stored_regime` is reserved and not used in v1. Invalid runs still
execute (results are labelled non-causal) but can never become baselines.
