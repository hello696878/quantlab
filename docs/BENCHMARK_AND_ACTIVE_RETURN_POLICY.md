# Benchmark and Active Return Policy (v1)

How a benchmark is declared, validated and used in the Portfolio Attribution
Lab.

## No automatic benchmark

A benchmark is **never selected automatically**, never downloaded, and never
falls back to an implicit equal-weight book. "Equal weight" is only ever a
benchmark the caller writes out explicitly. Without a benchmark definition,
benchmark-relative measurements are simply unavailable and the run uses the
`contribution_only` method.

## Benchmark definition

Every benchmark declares: id, name, description, source
(`user_supplied` / `demo_fixture` / `linked_dataset` / `custom_descriptive`),
kind, an **ordered** asset list, weights, optional explicit returns, group
mappings, return convention, timing policy and an optional dataset version.

| Kind | Weight behaviour |
| --- | --- |
| `fixed_weights` | the declared vector is restored at the beginning of **every** period (a documented periodic-rebalancing benchmark) |
| `supplied_per_period` | one explicit weight row per attribution period, in the benchmark's asset order |
| `buy_and_hold` | the declared vector **drifts** with benchmark returns by the same recursion the portfolio uses |

## Returns and universes

Benchmark asset returns default to the linked portfolio universe's **stored**
returns for assets shared with that universe — an exact reuse of stored data.
A **benchmark-only asset must supply its own returns explicitly**; without
them it is rejected rather than silently dropped, and it must carry an
**explicit group** (groups are never inferred from names).

Universe differences are disclosed: `portfolio_only_assets`,
`benchmark_only_assets` and the shared-asset count, each surfaced as a run
warning and in the benchmark panel.

## Weight validation

Weights must be finite and within ±10. Their sum is computed and
**disclosed**: a sum other than 1 is reported (`weight_sum_is_one: false`
plus a warning) and the weights are used **as declared** — never silently
renormalized. Duplicate benchmark asset ids, unknown keys, a mismatched
return convention and a non-beginning-of-period timing policy are all
rejected with explicit messages.

## Active return

```
active_return_t = portfolio_return_t − benchmark_return_t
```

computed on identical periods under the identical return convention. The lab
distinguishes:

- **gross / market-only active return** — the market contribution difference;
- **cost-adjusted active return** — available only where the cost leg exists,
  over its stated costed basis (see the attribution policy);

A period whose benchmark observation is unavailable (for example a
buy-and-hold benchmark book that was wiped out) leaves benchmark-relative
results for that period unavailable, marks the run `partial`, and **withholds
multi-period linking** rather than implying a partial-period link.

There is no currency conversion anywhere: Phase 56 enforces a single currency
per universe and the lab never converts.

## Wording

A positive active return is a **measured benchmark-relative return**. It is
never called alpha, skill, outperformance-as-ability, superior or
recommended. The lab's `benchmark.py` sibling module in the backtest path
computes a narrowly-defined Jensen's alpha for single-asset equity curves;
this lab deliberately does not, and does not reuse that vocabulary.
