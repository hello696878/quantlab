# Factor Exposure, Return Decomposition and Macro Sensitivity Diagnostics Lab (v1)

Phase 59.0 · module `factor_diagnostics` · API `/factor-diagnostics` ·
UI **Factor Diagnostics**

## 1. What this lab is

A local-first research lab that measures the sensitivity of **one explicitly
declared return series** to **supplied** factor and macro observations under
a **stated timing rule**, and decomposes the measured return into an
intercept, per-factor contributions and a residual that reconcile exactly.

It answers, for a single stored run:

1. which return series was analysed, and where it came from;
2. which factor definitions and transformations were used;
3. which factor observation fed each period, and when it was knowable;
4. whether exposures were supplied or estimated;
5. which estimator was used and under which switches;
6. what the sensitivities, intercept and residual are;
7. how much measured return each factor explains under the model;
8. whether the decomposition reconciles;
9. how stable the sensitivities are across trailing windows;
10. how sensitive the result is to lookback, lag, scaling, subset and
    regularisation assumptions;
11. whether the factors are collinear, constant, rank deficient or weakly
    identified;
12. which statistics are valid and which are unavailable, with reasons;
13. how exposures differ from an explicitly declared benchmark;
14. how they differ across stored Phase 54 regimes;
15. what an explicitly supplied factor shock would imply under the measured
    exposures;
16. which Dataset Lineage, Portfolio Attribution, Model Validation, Regime,
    Stress and Experiment Registry records supplied the inputs;
17. whether the whole thing reproduces from deterministic fingerprints.

## 2. What this lab is NOT

It does **not** prove causality, prove alpha, prove manager skill, predict
future returns, recommend a factor exposure, recommend a macro trade,
recommend a portfolio, build a factor portfolio, hedge an exposure, allocate
capital, execute trades, certify a factor model, or constitute investment,
trading or risk-management advice. It never downloads market or
macroeconomic data: **every observation is supplied locally.**

A coefficient is a least-squares sensitivity under the declared
specification. The intercept is the mean return that specification did not
explain over that sample — it is never called alpha without exactly that
qualification, and the residual is never relabelled alpha anywhere.

## 3. Target series (`targets.py`)

Exactly one target per run. Either

* **read from a stored Phase 58 attribution run** — `portfolio_return`,
  `benchmark_return`, `active_return` or `cost_adjusted_portfolio_return`,
  taken verbatim from `attribution_period_results` with that run's own
  `information_available_at` per period, or
* **supplied directly** as a descriptive series with declared
  `target_type`, convention, frequency and currency.

No benchmark or factor series is mixed into the target vector, no currency
is converted silently, and a convention or frequency mismatch against the
linked attribution run is a validation error, not an adjustment.

## 4. Factor definitions and observations

See [`FACTOR_DEFINITION_AND_TRANSFORMATION_POLICY.md`](FACTOR_DEFINITION_AND_TRANSFORMATION_POLICY.md)
for the full contract: categories, units, the eight transformation formulas,
lag bounds, availability policies, the strictly-trailing z-score, and why
winsorisation is deferred.

Alignment is **exact**: a factor value is matched to a target period by
timestamp equality in the factor's own observation sequence, offset by the
declared integer lag. Nothing is resampled, forward-filled, interpolated or
zero-filled; a period whose factor value is missing leaves the estimation
sample and is listed with its reason.

## 5. Timing and integrity states

| state | meaning |
| --- | --- |
| `verified_from_validation_split` | causal timing **and** a completed, leakage-clean Model Validation split governs the fit |
| `verified_causal_lag` | every factor lags ≥ 1 period and was knowable before the period it explains |
| `verified_trailing_estimation` | as above, and the run declares the trailing rolling estimates as its usable result |
| `supplied_descriptive` | descriptive; e.g. the linked validation run reports leakage |
| `contemporaneous_descriptive` | factor and target carry the same period stamp — association only |
| `full_sample_descriptive` | fitted over the whole sample, or a latest-vintage policy is in force |
| `unknown` | not yet executed |
| `invalid` | a factor value was knowable only after the period it explains, or the caller declared a future-looking alignment |

A future-looking alignment exists **only** when the caller sets
`timing_policy: "future_looking_invalid"` with `lead_periods ≥ 1`. Such a run
is always `invalid`, warns loudly, and can never become a baseline. Negative
lags and centred windows are rejected outright.

## 6. Analysis modes

* `time_series_regression` — the exposure to factor *k* is the estimated
  coefficient, constant over the sample.
* `supplied_exposure_aggregation` — asset-level exposures are **supplied**
  and aggregated with the beginning-of-period weights of a stored Phase 56
  book: `portfolio_exposure_k,t = Σ_i w_i,t · exposure_i,k`.
* `cross_sectional_decomposition` — **deferred in v1** with a stated reason
  (no stored record holds per-period asset exposures aligned with per-period
  asset returns; anything less would be a placeholder).

## 7. Estimator

See [`FACTOR_MODEL_AND_REGRESSION_POLICY.md`](FACTOR_MODEL_AND_REGRESSION_POLICY.md).
Ordinary least squares solved by SVD, with rank, singular values and the
condition number of the **centred** factor block; an explicit rank policy
(`fail` or a labelled `minimum_norm_descriptive`); classical covariance only,
never called robust; and an explicit ridge reference with no p-values and no
automatic lambda.

## 8. Decomposition and reconciliation

See [`FACTOR_EXPOSURE_AND_RETURN_DECOMPOSITION_POLICY.md`](FACTOR_EXPOSURE_AND_RETURN_DECOMPOSITION_POLICY.md).
Per period the lab reports measured return, intercept contribution, each
factor contribution, the modelled return, the residual and the
reconciliation difference; the identity is checked numerically against the
estimator's own residual vector rather than assumed.

## 9. Macro sensitivity and vintages

See [`MACRO_SENSITIVITY_AND_VINTAGE_POLICY.md`](MACRO_SENSITIVITY_AND_VINTAGE_POLICY.md).
Macro series are supplied locally, units are explicit (levels vs changes,
percent vs basis points), release timing is explicit or the assumption is
stated as a warning, and a `latest_available_as_of_cutoff` vintage policy
guarantees a later revision never reaches an earlier fit.

## 10. Cross-lab views (all read-only)

* **Regime (Phase 54)** — periods are bucketed by stored assignments;
  regimes are never recomputed and their fingerprints are pinned. Fewer than
  10 observations withholds the conditional fit.
* **Stress (Phase 57)** — measured exposures multiplied by **explicitly
  supplied** factor shocks in each factor's transformed unit. Factor shocks
  are never inferred from a scenario's asset shocks, no hedge or
  reallocation follows, and the residual component of a hypothetical shock
  is reported as undefined.
* **Attribution (Phase 58)** — the same measured return, explained a second
  way. Brinson allocation/selection and factor exposure are complementary
  views; neither overwrites the other and transaction cost stays inside the
  attribution lab's cost block.
* **Model Validation (Phase 52)** — coefficients are fitted on the split's
  training observations only and applied unchanged to the held-out rows;
  purged and embargoed periods belong to neither set. Held-out R² uses the
  **training** mean in its denominator, and a negative value is reported as
  measured.
* **Dataset Lineage / Experiment Registry** — identity is displayed and
  recorded; no lineage or registry record is mutated.

## 11. Fingerprints

Six kinds — factor definition, target series, observation universe, model
policy, configuration and result — over canonical JSON with 12-dp float
quantization. NaN and Infinity are rejected. No database id, timestamp,
duration or path enters a fingerprint. Factor fingerprints include each factor's dataset identity; the observation fingerprint includes selected source observation ids, timestamps, vintages, raw values and quality state; sensitivity result fingerprints include the effective sample, scenario and fitted result. Thus the same inputs under the same
policy reproduce the same fingerprint on another machine. Execution re-checks
every linked record's fingerprint and refuses rather than silently measuring
different inputs.

## 12. Baselines

A baseline requires a completed run with a verified integrity state,
`complete` completeness, `full_rank` rank status, a reconciled decomposition
and a stored result fingerprint. Same-scope replacement is transactional;
other scopes are untouched. A baseline is a **comparison reference only** —
it is never chosen by R², p-value, residual or held-out performance, and it
recommends nothing.

## 13. The UI is a read-and-inspect surface

The **Factor Diagnostics** view lists runs with neutral status pills and
filters (status, integrity, mode, timing, rank, free-text search), and its
detail page renders the factor definitions, the coefficient table and, only when static coefficients are available, its bar
chart, the reconciliation block, the per-period decomposition, design
conditioning with the correlation matrix (heatmap **and** table — colour is
never the only signal), residual diagnostics with a residual chart, rolling
exposures with a chart and table, exposure stability, benchmark-relative
exposure, stored-regime rows, the stress and attribution linkages, held-out
metrics, sensitivity scenarios, the aligned observations with their
availability stamps, and the stored policy with all five fingerprints.

Run **creation** happens through the API (`POST /factor-diagnostics/runs`)
or the demo loader, following every other diagnostics lab in this project:
a run's payload carries the full factor observation series, which is not
something a form should be asked to carry in v1. This is a stated
limitation, not an oversight — the UI never hides a parameter that the API
requires.

## 14. Demo fixture

Twenty idempotent cases over synthetic, generic series, all hand-computable.
See [`FACTOR_DIAGNOSTICS_RUNBOOK.md`](FACTOR_DIAGNOSTICS_RUNBOOK.md) §3 for
the list and the worked numbers.

## 15. Limitations

Simple returns only; ≤ 12 factors, ≤ 2000 observations, ≤ 400 rolling
windows, ≤ 16 sensitivity scenarios; classical standard errors only (no
HC/HAC estimator exists in this repository and none is simulated);
cross-sectional decomposition, winsorisation and lag/standardisation
sensitivity dimensions deferred with reasons; measured sensitivities describe
the supplied sample under the declared specification and nothing else.

## 16. Downstream: Signal Decay Lab (Phase 60.0)

The Signal Decay Lab (Phase 60) can link a completed run of this lab
(pinned by configuration, result and model-policy fingerprints, read-only)
to compare raw outcomes with factor-residualised outcomes: the residual
outcome of a holding is the arithmetic sum of this lab's stored per-period
residuals whose period start falls inside `[entry, exit)`, required to
cover exactly the holding's horizon. Raw and residual diagnostics are
separate rows there, a residual association is not alpha, and nothing is
neutralised automatically or written back to this lab.

## 17. Downstream: Signal Ensemble Lab (Phase 61.0)

The Signal Ensemble Lab (Phase 61) can compare its combined score's
OUTCOMES against this lab's stored per-period residuals (pinned,
read-only, exact horizon coverage; raw and residual scopes separate;
never called alpha). Residualising SIGNAL VALUES is deferred there with
its reason: no stored factor-residualised signal series exists, and
automatic residualisation is prohibited.
