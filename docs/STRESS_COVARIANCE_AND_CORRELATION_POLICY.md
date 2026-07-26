# Stress Covariance and Correlation Policy (v1)

How the stressed covariance is built, validated and (only ever explicitly)
repaired. Nothing here predicts future volatility or correlation.

## Construction

The baseline covariance is **always retained**. The stressed matrix is
rebuilt from stressed volatilities and a stated correlation matrix:

```
Σ* = D(σ*) · R* · D(σ*)
```

with `D(σ*)` the diagonal matrix of stressed volatilities. When a baseline
variance is zero the correlation is undefined and the whole stress is
reported unavailable with that reason — never fabricated.

## Volatility stress

| Mode | Rule |
| --- | --- |
| `multiplicative` | `σ*_i = σ_i × m` (uniform and/or per-asset multipliers, each in (0, 10]) |
| `additive` | `σ*_i = σ_i + a` in per-period volatility units, `|a| ≤ 1`; a negative result is floored at zero and the flooring is **disclosed per asset** |

## Correlation stress

| Mode | Rule |
| --- | --- |
| `uniform_multiplier` | off-diagonals × m |
| `additive` | off-diagonals + a |
| `toward_one` | `ρ* = ρ + α(1 − ρ)`, α ∈ [0, 1] |
| `supplied` | an explicit n×n matrix in the portfolio's asset order |

The diagonal stays exactly 1 and symmetry is preserved. Any clamping to
[−1, 1] is disclosed in the run's warnings. Supplied matrices must already
be symmetric with a unit diagonal — asymmetry or a non-unit diagonal is
**rejected at validation**, never silently averaged or overwritten.

## PSD validation and explicit repair

The stressed matrix is validated with the shared Phase 56 utilities
(`numpy.linalg.eigvalsh`, `PSD_TOLERANCE = −1e-10`, near-singular condition
warning at `1e12`). The repair policy is always explicit:

- repair policy `none` → a matrix below the PSD tolerance is **unavailable**
  with the exact reason; risk stress is withheld, the run is `partial`, and
  it cannot become a baseline. Nothing is silently accepted or repaired.
- repair policy `eigenvalue_floor` → an explicit spectral floor is applied
  whenever an eigenvalue is below the configured positive floor. This can
  include a singular but positive-semidefinite matrix. Original and repaired
  eigenvalues are both recorded, a run warning fires, and the repair is
  visible in the UI; it is not mislabelled as necessarily non-PSD.

Because a spectral repair rewrites both the diagonal and the off-diagonals,
the **disclosed** `stressed_vols` / `stressed_correlation` always describe
the matrix actually used for risk. The pre-repair values are kept
separately as `requested_vols` / `requested_correlation`, so the block can
never be read as describing something else, and the UI shows the two side
by side (for the demo's infeasible 0.9/0.9/−0.9 triangle: requested 0.9000
→ effective 0.3020 after the eigenvalue floor).

## Risk recomputation

Baseline and stressed risk both use the Phase 56 identities:

```
MCR = (Σw)_i / σ      CCR_i = w_i × MCR_i      PCR_i = CCR_i / σ
Σ CCR = σ             Σ PCR = 1
```

Both identity checks are reported. Per asset the lab stores baseline and
stressed MCR/CCR/PCR, `ΔPCR` and the rank change. A row is `available` only
when a stressed contribution actually exists — a zero-volatility stressed
book yields `baseline_only` rows plus the upstream reason, never a
"computed" label over null values. A higher stressed contribution is a
measured change under these assumptions — **not automatically worse**.

The stressed covariance carries its own fingerprint; the baseline
covariance record is never modified.
