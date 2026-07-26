# Portfolio Construction Policy (v1)

Exact method semantics for the Portfolio Diagnostics Lab
(`backend/app/portfolio_diagnostics/methods.py`). Every solver is
deterministic (fixed initialization, bounded iterations, explicit
tolerances), reports convergence status and residual, and is followed by
an independent constraint re-check. A failed solve returns a failed
status with weights unavailable — never a silently degraded portfolio.
No method output is an allocation recommendation.

## User-supplied weights

Validated finite numbers over known assets with explicit provenance
(`basis` ∈ causal_rolling / declared / full_sample / centered / unknown —
centered or negative-lag claims make the run integrity `invalid`).
Normalization follows the explicit policy only; original raw weights are
always retained. A long-short input under `sum_to_one` with a
non-positive raw sum is unavailable — never silently converted long-only.

## Normalization policies

`sum_to_one` (positive raw sum required), `net_target` (scale to the
configured net exposure; zero raw net refused), `gross_target` (scale so
Σ|w| equals the target), `cash_residual` (no scaling; **net AND gross
exposure ≤ 1** so the "no hidden leverage" promise holds for long-short
inputs; the un-invested residual is explicit), `none`. No division by
zero anywhere; residuals and tolerances visible.

## Equal weight

`w_i = 1/N` over eligible (non-excluded) assets scaled to the configured
target exposure; zero eligible assets fail honestly; long-only reference.

## Inverse volatility

`raw_i = 1/σ_i` with σ from the trailing estimation window (sample std,
ddof=1), normalized over available assets. A zero/negative σ with no
configured floor makes the asset unavailable (weight 0, recorded); with
an explicit floor, σ is clamped upward and the clamp is recorded in the
solver output and surfaced as a run warning — the floor value is
fingerprinted. A subnormal σ whose inverse overflows is unavailable.
Nothing is hidden or clipped silently.

## Equal Risk Contribution (risk budgeting)

Long-only v1. Solves `min ½wᵀΣw − Σ b_i ln(w_i)` (deterministic L-BFGS-B,
analytic gradient `Σw − b/w`, equal-weight init, bounded iterations) and
normalizes to sum 1 — at the optimum the percentage risk contributions
equal the positive budgets b (which must cover every asset and sum to
one). PSD covariance with a positive diagonal required (zero variance
fails honestly). Convergence is judged by the residual `max|PCR_i − b_i|`
against the explicit tolerance; a `converged_loose` tier exists up to an
absolutely capped band `min(100×tolerance, 1e-3)`; anything beyond is
`failed` with weights unavailable. Configurations the constraint-free v1
solver is structurally guaranteed to violate (excluded assets, net target
≠ 1, positive min weight, frozen weights, shorting) are rejected at
create with explicit reasons.

## Minimum variance

Deterministic scipy SLSQP: `min wᵀΣw` from equal-weight init under
per-asset bounds (excluded → (0,0), frozen → fixed, long-only clamp),
the sum-to-target equality, and long-only group caps/minimums as smooth
inequalities (long-short group caps are validated post-solve — the
non-smooth |w| term is not given to SLSQP; documented). Reports
convergence, the equality-slack residual, and the minimized variance as
`objective_value`. No claim of an optimal future portfolio is ever made —
the minimized quantity is an in-sample estimate under one covariance
assumption.

## Deferred (no placeholders)

`max_diversification` — no coherent v1 formulation under the current
constraint model without a second solver pass. `mean_variance` — no
robust explicit expected-return model exists in this repository.
Requesting either returns a 422 naming the reason.
