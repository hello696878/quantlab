# Signal Combination and Contribution Policy (Phase 61, v1)

## 1. Normalisation before combining

Normalisation is an explicit per-signal configuration — signals are
never normalised automatically merely because their units differ:

* `none` — supplied values unchanged;
* `cross_sectional_rank_percentile` — per timestamp over that signal's
  eligible entities, `(rank − 0.5) / n`, documented average or
  deterministic-first tie method;
* `cross_sectional_zscore` — `(x − mean_t) / std_t` with an explicit
  ddof (0 or 1);
* `trailing_zscore` — per entity over the last `window` stored
  observations, STRICTLY before the current one unless
  `include_current` is explicitly true; centred windows do not exist.

Zero variance, thin universes and short histories yield unavailable
values with counted reasons. Future observations cannot change earlier
values by construction (tested adversarially), and full-sample
standardisation does not exist here — a component whose Phase 60
definition declares `rank_full_sample` demotes the whole run to
`full_sample_descriptive`.

## 2. The four combination modes

* **equal_weight** — `combined = Σ oriented_normalised_k / K`;
* **user_weights** — static user weights under an explicit
  negative-weight policy and an explicit normalisation policy
  (`require_sum_to_one`, `normalise_by_sum`, `normalise_by_gross`,
  `none`); gross weight, net weight, maximum |weight|, zero-weight
  signals and the normalisation residual are all stored;
* **rank_average** — the equal-weight mean of per-signal
  cross-sectional rank percentiles (an explicit property of the mode);
* **majority_sign** — `sign(Σ sign(signal_k))` for sign-semantic
  signals; it is not linear, so contributions are reported as sign
  votes and linear reconciliation is `not_applicable` (stated).

No automatic weights, no optimisation, no performance-derived weights,
no hidden normalisation, no automatic thresholds, and no stacking,
boosting, neural ensembles or learned meta-models in v1.

## 3. Missing-component policies

* **`require_all`** (default) — a combined score exists only when every
  component is present; missing ids are listed per observation;
* **`renormalise_available`** (explicit opt-in only) — available
  components' configured weights are renormalised; the missing ids,
  effective component count and effective weights all stay visible, and
  a minimum component count (≥ 2) applies.

No zero imputation, no carry-forward, no automatic long-only
conversion. A key whose available components carry zero gross or zero
net configured weight is unavailable with that reason rather than
divided by zero.

## 4. Contribution reconciliation

For linear modes, every observation retains per component: raw value,
oriented value, normalised value, configured weight, effective weight,
`contribution = effective_weight × oriented_normalised`, and missing
state. The engine verifies

```
combined_score = Σ contributions   (tolerance 1e-9)
```

over ALL observations; a failure is a run-level error state and is
never redistributed. Persistence stores a deterministic sample of
contribution rows (timestamp, entity, signal order) with the sampled /
total counts disclosed on the run.

## 5. Point-in-time combined scores

A combined observation's availability is the LATEST `available_at` of
its used components: a combination is never more point-in-time than its
inputs. A component available only after the observation timestamp
makes the run `invalid`. When linked validation is used, all used
components must also reference one consistent stored validation sample;
cross-sectional samples are therefore not guessed from a non-unique
timestamp. Aggregate contribution summaries are labelled descriptive.

## 6. Leave-one-signal-out

For each component, the SAME configured policy is re-applied to the
remaining signals (weights renormalised only as that policy dictates)
and the differences — coverage, mean |correlation|, effective count,
first-horizon rank IC, spread, turnover — are reported as neutral
deltas. This is not a feature-selection algorithm: there is no
exclusion recommendation, no "harmful signal" label, and insufficient
data stays unavailable. Similarity and effective-count diagnostics are
recomputed on the remaining signals' own common post-normalisation
sample rather than slicing the full-universe matrix.
