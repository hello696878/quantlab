# QuantLab — Market Regime Definition Policy (Phase 54.0)

The exact rules behind every regime dimension and threshold-fitting mode in
the Regime Diagnostics Lab.  Companions:
[`REGIME_DIAGNOSTICS_LAB.md`](REGIME_DIAGNOSTICS_LAB.md) ·
[`REGIME_NO_LOOKAHEAD_POLICY.md`](REGIME_NO_LOOKAHEAD_POLICY.md).

## 1. Shared mechanics

Every computed statistic at index *j* uses the trailing window
`values[j − lookback + 1 … j]` (lookback 2–250).  The label **effective at
period i uses the statistic at j = i − lag** with lag 1–30 (default 1) —
end-of-period information can never label its own period.  Three-way
classification: `stat < T1 → labels[0]`, `T1 ≤ stat < T2 → labels[1]`,
`stat ≥ T2 → labels[2]` with `T1 < T2` enforced.  Periods without a full
window+lag stay unavailable.  Missing values are rejected at input (no
filling), and definitions carry no executable code of any kind.

## 2. Volatility

Trailing **sample** standard deviation (ddof=1) of the source feature
(conventionally a per-period return series; the feature's own meaning is
the caller's declaration).  Not annualized — the timeline's declared
frequency is display metadata only.  Default labels low/normal/high.

## 3. Trend

Trailing mean of the source feature.  Default labels
downward/neutral/upward; the neutral band is exactly `[T1, T2)` and its
width is the caller's explicit choice — a narrow band makes neutral rare,
and rare regimes are honestly withheld rather than padded.

## 4. Liquidity

Trailing mean of an **explicitly named** liquidity feature (spread, depth,
volume — whatever the caller supplies and documents).  Liquidity is never
inferred from unrelated fields; a definition naming a missing feature is a
422.  Default labels thin/normal/deep.

## 5. Drawdown state

`level[j] = Π(1 + v[k])` for k ≤ j; `peak[j] = max(level[0..j])` — the
**trailing peak only**, never a future maximum; `dd[j] = level/peak − 1`.
Thresholds are two ascending positive magnitudes `[d1, d2]` (default
[0.05, 0.15]): `dd > −d1 → near_peak`, `−d2 < dd ≤ −d1 →
moderate_drawdown`, `dd ≤ −d2 → deep_drawdown`.  Fixed thresholds only in
v1; always `verified_causal_rule` (with the standard lag).

## 6. User-supplied categorical

Aligned label array (≤ 6 distinct plain strings ≤ 32 chars, no markup,
None = unavailable) plus provenance `{source, causality, description}`.
`causality: "trailing"` → integrity `declared`; `"unknown"` → `declared`
with a note; `"centered"` → **invalid** (the labels are not used at all).
Supplied labels are never automatically verified.

## 7. Combined

Exactly two non-combined source definitions; the pair label is
`"{a}|{b}"` when both sources are defined at the period, else unavailable;
more than 12 distinct pair labels invalidates the definition (no silent
merging, no rare-combination grouping in v1); integrity = the
**least-trusted** source state.

## 8. Threshold-fitting modes

| mode                   | thresholds come from                                   | integrity state                    |
|------------------------|--------------------------------------------------------|------------------------------------|
| `fixed`                | the caller's explicit values                            | `verified_causal_rule`             |
| `expanding_quantile`   | quantiles of statistics strictly at or before *i − lag*, re-fitted per period, ≥ `min_history` defined stats required (early periods unavailable) | `verified_causal_rule` |
| `training_quantile`    | quantiles of statistics at the named validation split's recorded **training** periods only | `verified_from_validation_split` |
| `full_sample_quantile` | quantiles of the full statistic sample                  | `full_sample_descriptive` — never leakage-safe, always warned |

Quantiles are two ascending values in (0, 1) (default 1/3, 2/3).  Modes
never fall back silently: a training fit without resolvable membership, or
with too few defined training statistics, makes the definition invalid.
Every fitted threshold set carries its own SHA-256 fingerprint.

## 9. Training-membership resolution

`training_quantile` requires a linked, **completed, leakage-clean** Model
Validation run, per-period `sample_ids`, and a named valid split: every
period's sample id must be a recorded member of the run (unknown ids fail
honestly), the fitting subset is exactly the split's `train_ids`, held-out
observations never affect the thresholds, and invalid or leakage-failed
splits can never produce verified thresholds.

## 10. Bounds

≤ 6 definitions per run, ≤ 6 labels per definition, ≤ 12 combined labels,
lookback 2–250, lag 1–30, `min_observations` 2–100 (default 8),
`min_history` ≥ lookback + 5.
