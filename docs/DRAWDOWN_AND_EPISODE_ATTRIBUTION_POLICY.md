# Drawdown and Episode Attribution Policy (v1)

Conventions for the Portfolio Stress Lab's historical drawdown analysis.
Nothing here proves why a drawdown occurred.

## Return series

The drawdown path uses the **canonical Phase 56 realized return series**
(`portfolio_diagnostics.rebalance.portfolio_returns`): weights effective at
a decision index govern that period onward and **drift** between rebalances
exactly as recorded. Periods before the first effective rebalance are
honestly unavailable (`None`), never zero-filled.

## Wealth, peaks, drawdowns

```
W_t     = Π_{s ≤ t} (1 + r_s)      starting from 1.0
peak_t  = max(1.0, max_{s ≤ t} W_s)      TRAILING history only
dd_t    = W_t / peak_t − 1
```

The initial capital 1.0 **is** a peak, so a book that opens down shows a
real drawdown rather than zero. No future maximum ever enters a peak.
Interior gaps in the series and a non-positive wealth index (a return ≤
−100%) make the analysis unavailable with an explicit reason, which is also
surfaced in the run warnings.

## Episodes (deterministic)

An episode opens at the first index whose drawdown goes below zero after a
peak; its trough is the minimum drawdown (first occurrence on ties); it
closes at the first observed index where wealth returns to or above the
episode peak (`recovered`) or stays open at the series end
(`unrecovered` — no fabricated recovery date). Exact-zero drawdowns are
boundaries, not members. `duration` counts the below-peak observations from
the episode's first period through the trough.

Episode ids are chronological. Detection is exhaustive; persistence is
bounded to the **deepest 40** episodes, and whenever that bound truncates,
the run stores the true total count, an `episodes_truncated` flag and a
warning. The deepest episode is always selected from the **full** list, so
the attributed episode always matches the reported maximum drawdown.

## Attribution of an episode

Over the below-peak interval `[episode start … trough]` (the peak-making
period's return is **not** part of the decline):

```
contribution_i = Σ_t w_i[t] × r_i[t]
```

with `w[t]` the static stored-target weights governing period `t` — a
**labelled approximation** (`weight_policy`). Contributions sum to the
interval's summed **arithmetic** portfolio return *under that weight
policy*. Two gaps are disclosed in the stored `reconciliation_note` rather
than hidden: compounding (the geometric episode depth differs from an
arithmetic sum), and the weight policy itself (the depth is measured on the
recorded **drifting**-weight series, while attribution holds the stored
targets fixed within the interval). Average weights, absolute shares
and group contributions are reported alongside.

Attribution describes what was measured — it never claims to prove why the
drawdown happened, and it is not a prediction of future drawdowns.
