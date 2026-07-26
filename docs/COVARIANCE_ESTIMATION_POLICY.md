# Covariance Estimation Policy (v1)

Exact estimation, validation, repair and stress semantics
(`backend/app/portfolio_diagnostics/covariance.py`). All matrices are
per-period (never annualized) and estimated ONLY from the no-look-ahead
window documented in [PORTFOLIO_DIAGNOSTICS_LAB.md](PORTFOLIO_DIAGNOSTICS_LAB.md).

## Estimation methods

- **sample** — `np.cov(window, ddof=1)`, symmetrized against numeric
  noise; declared return frequency and sample count recorded; at least 3
  observations required; missing values cannot occur (strict alignment).
- **diagonal** — sample variances with zero off-diagonals; clearly
  labelled a reference assumption, not a dependence estimate.
- **fixed_shrinkage** — `(1−α)·sample + α·target` with a caller-declared
  α ∈ [0,1] (never data-driven in v1) and an explicit stored target:
  `diagonal` (the sample's diagonal) or `scaled_identity` (identity times
  the mean sample variance). A convex combination of PSD matrices — it
  can never create a non-PSD result.
- **Ledoit-Wolf: deferred.** scikit-learn is not an approved dependency
  of this repository and no in-repo implementation exists; a heavy
  dependency is not added for it.

## Validation

Square, symmetric (1e-10 tolerance), finite, non-negative diagonal;
minimum/maximum eigenvalue via `numpy.linalg.eigvalsh`; PSD when the
minimum eigenvalue ≥ −1e-10; condition number with a near-singular
warning above 1e12; singular (zero eigenvalue) and non-PSD states carry
distinct warnings; invalid matrices return a stable report shape with
null eigenvalue fields.

## Repair — never silent

- **none** (default): an invalid/non-PSD matrix stays invalid and the
  solve fails visibly with the policy named in the reason.
- **eigenvalue_floor**: eigenvalues clamped at an explicit visible floor
  ∈ (0,1]; original AND repaired eigenvalues retained; the repaired flag,
  policy and floor are stored and fingerprinted. No repair happens when
  the minimum eigenvalue already clears the floor, and non-finite
  matrices are never "repaired".
- Nearest-PSD approximation: not available in v1 (no approved existing
  implementation) — documented rather than half-implemented.

## Correlation and stress

Correlation derives from the covariance only when every variance is
positive (otherwise honestly None). Research stresses multiply
off-diagonal correlations by a configured factor (clamped to [−1,1])
and/or asset volatilities by explicit positive factors, rebuild the
covariance, and re-validate PSD under the same explicit repair policy —
clamping can break PSD for 3+ assets, and that failure is visible, never
silently accepted. Stressed matrices are fingerprinted beside the
preserved base matrix. No stress predicts anything and none is
auto-selected.
