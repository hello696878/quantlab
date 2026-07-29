# Factor Exposure and Return Decomposition Policy (v1)

Phase 59.0 · `backend/app/factor_diagnostics/decomposition.py`

## 1. Supplied versus estimated exposure

The two are never mixed and always labelled.

**Estimated** (`time_series_regression`) — the exposure to factor *k* is the
least-squares coefficient, constant over the estimation sample:

```
factor_contribution_k,t = beta_k · f_k,t
modelled_return_t       = intercept + Σ_k factor_contribution_k,t
residual_t              = measured_t − modelled_return_t
```

**Supplied** (`supplied_exposure_aggregation`) — asset-level exposures are
supplied by the caller and aggregated with the beginning-of-period weights
of a stored Phase 56 book (rebuilt through the Phase 58 observation builder,
so the weight path is the one the portfolio lab itself records):

```
portfolio_exposure_k,t  = Σ_i weight_i,t · asset_exposure_i,k
factor_contribution_k,t = portfolio_exposure_k,t · factor_return_k,t
modelled_return_t       = Σ_k factor_contribution_k,t
residual_t              = measured_t − modelled_return_t
```

Rules for the supplied path:

* no regression estimator is run and no static coefficient is reported; the supplied period-level exposures remain the exposure source of record;
* asset ordering is exact and weights are used as the book holds them —
  **nothing is normalised**;
* long and short weights aggregate under the same signed formula, which the
  UI states rather than hiding;
* a missing asset exposure makes that factor's contribution **unavailable
  for that period** — it is never treated as a zero exposure, and the count
  of affected periods is reported;
* every factor must carry a return-like transformed unit
  (`return_fraction`, `return_percent`, `basis_points`), because an exposure
  multiplied by a non-return factor is not a return. Any other unit is
  refused with that sentence.

## 2. Cross-sectional decomposition is deferred

`cross_sectional_decomposition` would estimate period-level factor returns
from asset exposures and aligned asset returns:

```
asset_return_i,t = intercept_t + Σ_k exposure_i,k,t · factor_return_k,t + residual_i,t
```

No stored QuantLab record holds per-period asset exposures aligned with
per-period asset returns — Phase 58 stores per-asset contributions
aggregated over the window — so v1 **defers** the mode with that reason
instead of shipping a placeholder. The API rejects the mode with the reason
attached, and the UI lists it under *Deferred in v1*.

## 3. Reconciliation

Every period reports:

| column | meaning |
| --- | --- |
| `measured_return` | the target return for that period |
| `intercept_contribution` | the model constant (0 for the supplied path) |
| `factor_contributions` | one entry per factor, in the declared order |
| `modelled_return` | intercept + Σ contributions |
| `residual` | `measured − modelled`, by definition |
| `least_squares_residual` | the estimator's own residual, where it covers the same rows |
| `reconciliation_difference` | `residual − least_squares_residual`, or 0 where the estimator's vector does not cover the row |
| `reconciliation_state` | `reconciled` inside the tolerance, else `mismatch` |

The identity closes by construction; the interesting check is the **second**
column — comparing the decomposition's residual against the estimator's own
residual row by row proves the reported contributions really are the
least-squares fit and that nothing was redistributed. Under a training-only
fit the estimator's residual vector covers the training rows only, so that
cross-check is **skipped rather than mis-aligned**, and the identity check
still holds.

The tolerance is explicit (default `1e-9`, bounded to `[1e-12, 1e-2]`). A
mismatch is reported verbatim with its signed size and a warning — it is
never absorbed into a contribution and never silently rescaled.

Window totals are arithmetic sums across periods and say so: they are **not**
a compounded return over the window.

## 4. Benchmark-relative exposure

When the target comes from a stored Phase 58 attribution run that carries an
explicitly declared benchmark, the lab fits the **same specification** —
same factors, same units, same transformations, same periods — to that
benchmark's stored return series and reports:

```
active_exposure_k     = portfolio_exposure_k     − benchmark_exposure_k
active_contribution_k = portfolio_contribution_k − benchmark_contribution_k
```

The benchmark is **never selected automatically**: it is whatever the linked
attribution run declared. The benchmark must cover every portfolio estimation period. Under linked Model Validation, both fits use the same training rows. A missing benchmark value withholds the comparison rather than fitting a different sample; observations outside the estimation window are irrelevant. If the exact shared sample cannot identify the same specification, the comparison is withheld. Every row carries the sentence *an active exposure is a measured
difference; it is neither desirable nor undesirable here*.

## 5. What a contribution is not

A factor contribution is an arithmetic decomposition of a **measured**
return under a **declared** specification over a **specific** sample. It is
not a prediction, not a causal statement, not a claim about economic
exposure, and not a recommendation to take, avoid or hedge any exposure.
Gross and cost-adjusted targets are separate runs with separate identities;
transaction cost stays inside the Phase 58 cost block and is never folded
into a factor contribution.
