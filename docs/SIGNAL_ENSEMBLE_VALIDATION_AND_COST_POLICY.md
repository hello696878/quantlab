# Signal Ensemble Validation and Cost Policy (Phase 61, v1)

## 1. Evaluation through the Phase 60 policies

The combined score becomes a synthetic observation series (value =
combined score, availability = latest component availability) and runs
through the SAME reviewed Phase 60 machinery — `build_pairs`
(exact-timestamp forward returns, structural vs data unavailability,
timing violations), scipy correlations, per-timestamp cross-sectional
IC, equal-count buckets and the neutral top-minus-bottom reference.
Components are evaluated the same way at the first configured lag, so
component and combination diagnostics sit side by side.  Horizons are
1–250 grid observations (≤ 6 per run), lags 0–60 (≤ 3), and no horizon,
lag or ensemble is ever called better.  One timing violation anywhere
marks the run `invalid`.

## 2. Turnover — components versus combination

The combination's reference turnover uses the Phase 60 signed
top-vs-bottom book (`0.5·Σ|Δw|`, gross 2.0) at per-timestamp buckets,
with the declared initial-rebalance policy; each component's own
reference turnover is measured identically.  Combining can REMOVE
turnover (churning components whose sum is stable) or CREATE it (stable
components whose sum alternates) — both demo cases exist, and neither
direction makes a combination better.

## 3. Cost integration (Phase 55, read-only)

A linked cost model is pinned by id and model fingerprint and read
verbatim.  Only notional-proportional components are computable
(commission bps of notional, spread `fixed_bps × fraction`, per-side
slippage bps); impact and monetary-per-unit models stay unavailable
with reasons.  The reference notional is explicit (validated to
[1e3, 1e9]); the cost-adjusted spread (gross spread minus the MEAN
per-rebalance reference cost return, different time bases disclosed)
always sits in a separate column from gross; missing cost inputs stay
unavailable — never zero; partial completeness is visible.  No capacity
guarantee, no fill guarantee, no trade submission, and lower turnover is
never called better.

## 4. Model Validation integration (Phase 52, read-only)

Training and held-out memberships come from the stored split by
prediction time (purge and embargo used exactly as stored, split
fingerprint pinned).  Per-timestamp and trailing transformations fit no
persistent parameter, and supplied weights stay fixed, so nothing is or
can be refitted on held-out data.  Training, held-out and full-sample
combination diagnostics are reported separately; a leakage-failed run
keeps its figures descriptive and the verified claim withheld;
evaluating on a clean split earns `verified_from_validation_split`.

## 5. Regime integration (Phase 54, read-only)

Strict-intersection keys and combination pairs are grouped by the
stored assignments of the pinned regime definition (never recomputed).
Per regime: observations, pairwise mean |correlation|, effective signal
count (only when that regime's matrix is complete), the combined
score's rank IC and coverage.  Regimes under 10 observations are rare
and withhold statistics; no regime is preferred, and no
regime-dependent weight switching exists.

## 6. Factor integration (Phase 59, read-only)

The combined score's OUTCOMES can be compared against the pinned factor
run's stored per-period residuals (arithmetic sum over `[entry, exit)`
with exact horizon coverage; raw and residual scopes are separate rows;
a residual association is never called alpha).  Signal-VALUE
residualisation is **deferred with its reason stated**: no stored
factor-residualised signal series exists in this repository, and
automatic residualisation is prohibited.

## 7. Bootstrap and sensitivity

Bootstrap resamples WHOLE timestamp cross-sections (`timestamp` iid or
`moving_block` over chronologically ordered stamps — blocks never cross
entity boundaries), with a deterministic seed, 50–2000 resamples,
explicit block length, 2.5/50/97.5 quantiles and unavailable resamples
counted.  No bootstrap p-value exists and nothing is called
scientifically validated.  Sensitivity scenarios are user-declared
overrides (normalisation, orientation, weights, missing policy,
minimum components, matrix method, bucket count, horizon, lag) — the
base scenario appears exactly once, duplicates collapse by scenario
fingerprint, the grid is bounded at 24, and no configuration is marked
preferred or best.
