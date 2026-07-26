# Factor Model and Regression Policy (v1)

Phase 59.0 · `backend/app/factor_diagnostics/regression.py` and
`diagnostics.py`

## 1. Dependencies

Only the repository's approved numerical stack is used: **numpy** for the
linear algebra and **scipy.stats** for the Student-t tail. `statsmodels` and
`scikit-learn` are **not installed** and were deliberately not added — every
estimator here is closed-form with a documented formula. The existing
price-based `portfolio.factor_analysis` helper in the Portfolio Lab is a
different contract (price frames, long-only weights, no timing policy, no
standard errors, no rank policy) and is left untouched; this lab's solver
follows its condition-number convention so the two agree on that measure.

## 2. Ordinary least squares

`beta_hat` minimises `||y − X·beta||²` and is obtained from the singular
value decomposition of `X` (`numpy.linalg.lstsq`), which is numerically
stable where the normal equations `(XᵀX)⁻¹Xᵀy` are not.

Rank is read from the same decomposition with an explicit tolerance
(`max(shape) · 1e-12 · s_max`). The **condition number is computed on the
CENTRED factor block**, so an intercept column's scale cannot mask two
near-duplicate factors.

Reported: coefficients, intercept, fitted values, residuals, RSS, TSS, R²,
adjusted R², RMSE, residual mean and standard deviation, degrees of freedom,
rank vs expected rank, singular values, condition number and state.

## 3. Intercept policy

`include` (default) or `exclude`, always stated. The intercept is described
everywhere as *the mean return this specification did not explain over this
sample* — it is **never called alpha** without that narrow definition, and
the residual is never relabelled alpha.

## 4. Rank policy

* `fail` (default) — a rank-deficient design is **refused** with the rank,
  the constant columns and the duplicate columns named. Nothing is dropped
  automatically and no factor is selected automatically.
* `minimum_norm_descriptive` — the SVD minimum-norm solution is recorded and
  **labelled** `rank_deficient_descriptive`. Every standard error,
  t-statistic, p-value and confidence interval is withheld, because the
  coefficients are not identified, and such a run can never be a baseline.

## 5. Standard errors — classical only

```
sigma²        = RSS / (n − p)          p = columns of X, intercept included
Var(beta_hat) = sigma² (XᵀX)⁻¹        via V diag(1/s²) Vᵀ from the SVD
se_j          = sqrt(Var_jj)
t_j           = beta_j / se_j
p_j           = 2 · P(T_{n−p} > |t_j|)         (scipy.stats.t)
CI_j          = beta_j ± t_{1−(1−c)/2, n−p} · se_j
```

These assume homoskedastic, serially uncorrelated errors, and the lab prints
that assumption next to the numbers. **They are never labelled robust.** No
HC3 or HAC/Newey-West estimator exists in this repository, so none is
offered and none is advertised — adding an untested robust estimator would
be worse than saying plainly that there isn't one.

Statistics are withheld, with the reason attached, when:

* the design is rank deficient;
* the degrees of freedom are below 1;
* the residual variance is zero (an exact fit) — the classical standard
  errors would collapse to zero and every t-statistic would be infinite;
* the cross-product matrix cannot be inverted stably.

`n ≤ p` is refused before fitting: *"N observations cannot identify P
parameter(s)"*.

## 6. Constant target

If the total sum of squares is zero, **R² is undefined** and is reported as
`null` with a reason — never as 0 or 1. Adjusted R² and RMSE follow the same
availability logic.

## 7. Ridge — an explicit research reference

```
beta_hat = (XᵀX + lambda·I)⁻¹Xᵀy,   the intercept excluded from I
```

`lambda` is finite, non-negative and **always supplied by the caller**:
there is no hyper-parameter search and no cross-validated lambda. The
feature-scaling policy is explicit (`none` or `zscore_fit_sample`), and
coefficients are reported back in the original factor units. Ridge
coefficients are labelled **regularised**; they carry no standard error, no
t-statistic and no p-value, no multiple-testing correction is applied to
them, and no claim of improved prediction is made anywhere. OLS and ridge
results are kept distinct — a ridge R² is descriptive and is not comparable
with an OLS R².

## 8. Multicollinearity diagnostics

* design-matrix rank vs expected rank;
* singular values of the centred factor block;
* condition number, flagged above `1e8` as a **neutral warning** that is
  explicitly *not* a universal rule;
* Pearson factor-correlation matrix in the declared factor order, with a
  constant factor's row and column reported `unavailable`;
* exact duplicate-column and constant-column detection;
* variance inflation `VIF_k = 1 / (1 − R²_k)` from regressing factor *k* on
  the others with an intercept.

A VIF is `unavailable` with a reason — never a sentinel and never infinite —
when there are fewer than two factors, too few observations, a constant
factor, or an exact linear dependence (`R²_k = 1`). Nothing is removed,
reordered or selected automatically.

## 9. Residual diagnostics

Mean, sample standard deviation (ddof = 1), skewness
(`scipy.stats.skew(bias=True)`), **excess** kurtosis
(`scipy.stats.kurtosis(fisher=True, bias=True)`, normal = 0), lag-1
autocorrelation, the five largest absolute residuals with their periods,
residual concentration (HHI of squared residuals) with the effective number
of periods, and a cumulative residual drawdown defined explicitly as the
maximum drawdown of the **additive** cumulative residual sum against its
trailing peak (residuals are not compounded and are not a tradable series).

Small samples and constant residual series leave the shape moments
unavailable with a note. The lab states that residuals are what the
specification did not explain — **not alpha, not skill, not evidence of a
missing factor**.

## 10. Multiple testing

When enabled, the Phase 53 corrections are **reused** (`bonferroni`, `holm`,
`bh`) on the valid coefficient p-values only. Raw p-values are preserved
alongside the adjusted ones, the family is stated explicitly, no factor is
omitted from the family, and no correction is offered for ridge
coefficients. Benjamini–Yekutieli is **not** implemented in Phase 53 and is
therefore rejected rather than simulated. An adjusted p-value is still not
evidence of causality.

## 11. Rolling estimates

A window that ends at aligned observation `i` uses observations
`i − window + 1 … i` and nothing else. There are no centred windows, and
because a window never reads an observation after its own end index, a later
outlier cannot change an earlier estimate — asserted directly by a test that
compares window fingerprints before and after a late shock. Each window
records its start, end, decision timestamp (when its data is complete),
effective timestamp (the first period it could govern), observation count,
coefficients, intercept, R², condition number, rank and status
(`estimated`, `rank_deficient`, `insufficient_observations`, `failed`).
Failed and rank-deficient windows stay visible and are never interpolated
from their neighbours. Bounds: window 4–500, step 1–50, at most 400 windows.

## 12. Sensitivity scenarios

Bounded (≤ 16), deterministic, de-duplicated, base exactly once, over
lookback, uniform lag delta, intercept policy, ridge lambda, explicit factor
subset and factor scaling. Standardisation-policy and winsorisation
dimensions are **deferred** with stated reasons: they change the factor
definition and therefore the observation-universe identity, which is a
different run rather than a cell of this run's grid. No scenario is labelled
best, optimal or recommended, and nothing is re-run with a "winning" setting.
