# Strategy Similarity, Drawdown and Tail Policy

## Pair statistics

Pearson/Spearman statistics and p-values reuse the existing SciPy-backed helper.
The default minimum N is 4 (allowed 3-100). Insufficient or constant correlation
inputs remain null with reasons, never synthetic significance. Sample covariance
uses `ddof=1` and decimal-return-squared units per declared period. Sign agreement,
simultaneous loss/gain, opposite-sign counts, joint-loss rate and mean absolute
difference retain each pair's sample. Zero has its own sign, not a positive or
negative observation. Counts may be displayed below inferential sample limits.

The hypothesis family is all available Pearson and Spearman pair tests in one
run. Phase 53's helper retains raw p-values and adjusted results; **Holm** is the
declared correction (the helper also returns its Bonferroni/BH fields). No
p-values are invented for tails, drawdown or contribution differences. Classical
p-values do not correct serial dependence; significance is not alpha or proof
of diversification. No automatic duplicate label or correlation cutoff.

## Empirical lower-tail overlap

Default quantile 0.1, default minimum N 20 (bounded 10-200). Linear quantile
thresholds, inclusive `<=` lower-tail comparisons, `>=` upper-tail comparisons.
Ties can make more than 10% of observations lower-tail observations. The result
records thresholds and tie policy, joint count, Jaccard, each conditional
probability and opposite-tail rate. Constants or insufficient data are null.
This is descriptive **empirical overlap**, not a copula tail-dependence estimator
and not downside protection.

## Drawdown

Start wealth and running peak at 1. For each observed return:

```text
wealth[t] = wealth[t-1] * (1 + return[t])
peak[t] = max(peak[t-1], wealth[t])
drawdown[t] = wealth[t] / peak[t] - 1
```

This includes losses on the first period and uses no future peaks. Episodes
start at the first underwater period's start, record trough at period end,
and recover at an observed period end with drawdown zero. Duration counts
observed periods, including the recovery period when present; unrecovered
episodes have null recovery. No calendar-day duration is inferred across gaps.

Individual paths use each strategy's complete supplied history; ensemble paths
use strict intersection. Pair state/severe/deepest-episode overlap counts are
restricted to that pair's displayed sample. Deepest-episode ties choose the
first chronological episode. Severe threshold defaults to -10% and is explicit.
Episode contributions are arithmetic observations, not causal attribution or a
claim that a component hedges. Historical stress records are untouched.

## Common-sample matrix

Pearson or explicit Spearman alternate on the strict common sample only.
One constant member makes the full matrix unavailable; no misleading partial
matrix or fabricated diagonal. Eigenvalues, rank, condition and absolute
off-diagonal correlation are reported when valid. PSD is checked against an
explicit tolerance (default 1e-10, bounded 1e-12 to 1e-8), with no repair.
Small numerical negative eigenvalues remain visible; singular condition is
null rather than Infinity.

`effective_strategy_count = (sum(eigenvalues))^2 / sum(eigenvalues^2)` is a
**matrix concentration diagnostic**, not the true count of independent strategies.
No return metric is annualized; crypto and equity calendars are not presumed
interchangeable. See [alignment](STRATEGY_RETURN_STREAM_ALIGNMENT_POLICY.md).
