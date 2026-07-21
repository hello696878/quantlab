# QuantLab — Regime No-Look-Ahead Policy (Phase 54.0)

The causality contract every regime label in the Regime Diagnostics Lab
must satisfy — the lab's most important requirement.  Companion:
[`MARKET_REGIME_DEFINITION_POLICY.md`](MARKET_REGIME_DEFINITION_POLICY.md).

## 1. The contract

A regime label effective at timestamp *t* may use only information
available at or before its documented cutoff.  Concretely, with period
index *i* for *t*:

* the underlying statistic lives at **source index j = i − lag** with
  **lag ≥ 1** — an end-of-period value (a close, a day's return) can never
  label its own period;
* the statistic's window is **trailing**: `values[j − lookback + 1 … j]`;
* **centered windows are prohibited** (`centered: true` or
  `window: "centered"` → 422);
* **negative lags are prohibited** (422), and lag 0 is prohibited for every
  computed dimension (a deliberately conservative v1 rule — the lab assumes
  end-of-period feature availability);
* the drawdown state's peak is the **trailing** maximum only — a future
  rally never repaints a past drawdown;
* expanding thresholds at *i* use only statistics at indices ≤ *i − lag*,
  with a minimum history below which the label is honestly unavailable;
* training-fitted thresholds use only the named validation split's recorded
  training membership — held-out observations never touch them;
* full-sample thresholds violate this contract by construction and are
  therefore labelled `full_sample_descriptive`, warned, never called
  verified or leakage-safe, and never eligible for verified integrity;
* supplied categorical labels declare their own causality — a declared
  centered construction makes the definition `invalid` and its labels are
  not used;
* validation split memberships are never modified by any of this.

## 2. Integrity states

| state                            | meaning                                                        | leakage-safe claim |
|----------------------------------|----------------------------------------------------------------|--------------------|
| `verified_causal_rule`           | fixed or expanding thresholds over trailing lagged statistics  | yes — by construction, adversarially tested |
| `verified_from_validation_split` | thresholds fitted on recorded training membership only         | yes — against the named split |
| `declared`                       | caller-supplied labels claiming trailing construction          | **no** — recorded, not verified |
| `full_sample_descriptive`        | thresholds fitted on the full sample                           | **no** — descriptive only, warned |
| `unknown`                        | not executed                                                   | no |
| `invalid`                        | future-looking or unfittable definition                        | no — labels unused |

A run's integrity is the least-trusted state among its valid definitions.
Declared and full-sample states are never promoted.

## 3. Adversarial verification

The property is enforced by tests, not prose: the backend suite mutates
future observations and asserts every effective label is unchanged for
every dimension and threshold mode (including the expanding-quantile
history), asserts sensitivity to the true window end (*i − lag*), and
rejects centered/negative-lag/zero-lag definitions.  An independent
four-agent adversarial verification pass ran the same attacks from first
principles before the test suite was written.

## 4. What the contract cannot see

The lab guarantees causality **of its own label construction**.  It cannot
audit how the supplied market features were produced upstream — a feature
that itself embeds future information (a revised series, a
centered-smoothed input) is invisible to this contract and remains the
caller's responsibility, as recorded in the run's provenance.
