# Portfolio Construction, Risk Budgeting, Diversification & Constraint Diagnostics Lab (v1)

Phase 56.0 adds a local-first portfolio-research diagnostics lab that
constructs and evaluates portfolio weights under explicit covariance,
risk-budget, exposure, turnover and concentration assumptions. For any run
it answers: which assets and observations were used, whether weights used
only pre-decision information, which method and constraints were active,
whether the solver converged and the constraints were actually satisfied,
the marginal/component/percentage risk contributions and how they compare
to configured budgets, concentration and diversification measures,
weight sensitivity to covariance assumptions, rebalance turnover, how
linked Phase 55 cost assumptions and Phase 54 regimes bear on the result,
and whether everything reproduces from deterministic fingerprints.

**The lab is NOT** a live portfolio manager, broker or execution system,
automatic capital allocation, a recommendation engine, or proof of
diversification, profitability, or safety. It never applies generated
weights to any other system, never recommends an allocation or identifies
an optimal / safest portfolio, never guarantees diversification, risk
reduction, or performance, and never certifies portfolio risk. Nothing
here is investment advice.

Related policies: [PORTFOLIO_CONSTRUCTION_POLICY.md](PORTFOLIO_CONSTRUCTION_POLICY.md) ·
[COVARIANCE_ESTIMATION_POLICY.md](COVARIANCE_ESTIMATION_POLICY.md) ·
[RISK_BUDGET_AND_CONTRIBUTION_POLICY.md](RISK_BUDGET_AND_CONTRIBUTION_POLICY.md) ·
[PORTFOLIO_CONSTRAINT_POLICY.md](PORTFOLIO_CONSTRAINT_POLICY.md) ·
[PORTFOLIO_DIAGNOSTICS_RUNBOOK.md](PORTFOLIO_DIAGNOSTICS_RUNBOOK.md).

## 1. Universe and alignment

### Local Portfolio Source Composer v1

In local mode, **New portfolio run** is available in the toolbar and empty
state. Paste JSON or choose a local JSON file, validate the preview, select
manual weights (default), equal weight or inverse volatility, supply any required
weights, choose the rolling lookback, then deliberately
select **Create and run**. No data is seeded and no execution starts on import.
The preview is bounded to asset identities/metadata, observation count,
declared frequency, date range and the first three return values per asset.
Edits invalidate the preview and weights; obsolete asynchronous file reads
cannot replace a newer selection or paste.

The Composer accepts one return-data-only JSON shape (this abbreviated shape
illustrates fields; an actual import needs 24-2,000 dates and returns per asset):

```json
{
  "frequency": "daily",
  "timestamps": ["2024-01-01", "2024-01-02"],
  "assets": [
    {"asset_id": "asset-a", "name": "Asset A", "asset_type": "index", "group": "core", "currency": "USD", "returns": [0.01, -0.005]},
    {"asset_id": "asset-b", "returns": [0.002, 0.004]}
  ]
}
```

- Both pasted UTF-8 input and file size are limited to **2 MiB before JSON
  parsing**. Root fields are only `frequency`, `timestamps`, `assets`.
- 2-20 assets, 24-2,000 shared observations, identical array lengths, finite
  JSON numbers only (no numeric strings, booleans, null, or overflow `1e400`).
  **0.01 means a 1% period return**, not a price or a 0.01% return. No unit
  guessing, filling, dropping, resampling or numeric-value adjustment.
- Dates are the Composer's narrower **exact `YYYY-MM-DD`** subset: real
  calendar dates in years 0001-9999, strictly increasing without duplicates.
  Accepted strings are preserved. Datetime/offset imports use the existing
  broader API, which is unchanged. Declared frequency does not certify a
  trading calendar, regular spacing or historical authenticity.
- Asset order is preserved. IDs are trimmed, nonempty, unique after trimming,
  at most 64 characters; prototype-named IDs are supported. Optional metadata
  is only `name` (nullable, <=200), `asset_type` (equity/futures/crypto/fx/rates/
  candidate/index/other), `group` (nullable, nonblank <=64, <=8 distinct groups),
  and `currency` (nullable, nonblank <=8, one declared currency, no conversion).
  Unsupported fields are rejected, including `metadata`, weights, linked IDs,
  provenance and execution options. The public AssetInput accepts no `metadata`.
- For manual construction every weight must be explicitly entered, 0-100% inclusive; blank is not
  zero. Percentages are converted to fractions once and must sum to 1 within
  `1e-6` fractional tolerance (0.0001 percentage points). The entered total is
  shown without rounding into validity. No equal-weight substitution or scaling.

Construction Methods v1 exposes three existing backend methods without new
portfolio mathematics:

- **Manual**: `method=user_supplied`, `normalization=none`, declared weight
  provenance (`basis=declared`, never `causal_rolling`). Entered fractions are
  preserved without rescaling. Blank is invalid; explicit zero is allowed.
- **Equal weight**: `method=equal_weight`, `normalization=sum_to_one`. The backend
  constructs equal allocations, not provisional browser-calculated weights.
- **Inverse volatility**: `method=inverse_volatility`, `normalization=sum_to_one`.
  The backend uses inverse trailing-window sample volatility (sample standard
  deviation, ddof=1), proportional to 1/sigma. This is not equal risk contribution,
  optimal allocation or guaranteed risk reduction. `volatility_floor` is omitted:
  unusable assets can receive zero weight with a warning and stored per-asset reason;
  if none are usable, construction fails with weights unavailable. No hidden floor
  or equal-weight fallback.

Derived requests omit both `weights` and `weight_provenance` from serialized JSON.
Manual drafts may survive method switches but cannot affect derived requests;
switching back restores manual validation. Import edits still clear preview and
weight associations. Method selection stays within the locked form and never
creates or executes a run by itself. The narrow request union excludes manual
fields from derived requests and a volatility floor from all Composer requests.

Common fixed scope: sample covariance with `repair=none`; long-only weights in [0,1], net exposure target and gross
limit 1, no cash residual. Rebalance is one-time, initial turnover policy
`none`. Lookback L is an integer from 3 through `min(500, observations-1)`
(visible default 20), rolling estimation, lag 1. The estimation window is
indices 0 through L-1, the decision/first effective date is index L; earlier
portfolio returns are unavailable. Weights subsequently drift under the
existing engine: this is not constant-weight daily rebalancing or an allocation
invested over the entire imported history. Covariance and volatility remain
per-period; missing prior-book/cost information is unavailable, not zero-cost
evidence. No optimizer UI, shorting/leverage, normalization selector, sensitivity,
linked datasets/regimes/costs, benchmark import or baseline creation is added.

Lifecycle uses the existing `POST /portfolio-diagnostics/runs`, then executes
that same positive ID with `{"create_experiment":false}`. Inputs lock during
writes; duplicate clicks cannot issue duplicate writes. A lost/unknown create
response requires list inspection, not automatic recreation. After a known ID
has been created, lost execution responses retain it: refresh stored status,
then explicitly retry that same pending/failed ID. Recovery rechecks status
before execution; completed records open stored diagnostics, running or
invalidated records cannot execute via recovery. Pending/failed stored details
provide a route back to same-ID recovery. Obsolete detail successes/failures
cannot replace a new Composer, later selection, filtering/reload, or navigation.

Parent `completed` does **not** establish solver success or usable weights.
The actual stored detail shows method, weights, parent, solver and rebalance states,
warnings, violations and unavailable metrics. Rebalance **Inspect** also exposes
stored unavailable-asset reasons and any recorded floor use (Composer requests
never opt into a floor). Integrity labels describe backend estimation policy,
not independent certification of imported historical provenance.
Only a successful stored rebalance read
with usable weights establishes source availability; no replacement weights
or replacement run are fabricated. **Open Portfolio Stress** uses existing
navigation; select the displayed source name/ID and explicit stored rebalance
there (ID `0` is valid). Stress eligibility/calculations remain unchanged.
ServingGate keeps this authoring workflow out of read-only-demo and unverified
capability states. Existing list, comparison, demo, baseline and export actions
remain available under their existing policies.

The focused public-API bridge test is
`backend/tests/test_portfolio_source_composer.py`: non-equal 70/30 declared
weights survive persistence without normalization, actual rebalance 0 is used
for a -10%/0% asset shock (-7% portfolio return), stored source fingerprints
correspond, and downstream stress leaves the source and its weights unchanged.
Construction-method cases use 24 observations and lookback 20: A repeats
`[-0.001, 0.001, -0.001, 0.001]`, B repeats
`[-0.002, -0.002, 0.002, 0.002]`. Their noncollinear sample-volatility ratio is 1:2.
Public create/execute/read routes persist equal weights 1/2,1/2 and inverse-volatility
weights 2/3,1/3; rebalance 0 uses indices 0-19 and takes effect at index 20.
Actual stored weights produce -5% and approximately -6.6666667% under -10%/0%
shocks. Future-only mutations do not change the initial inverse-volatility weights
(whole-input fingerprints need not match). Partial/all-unusable cases preserve
warnings/failure rather than fabricating a successful portfolio.
Only test-owned SQLite is accessible. Component/API tests and a production
build are separate from browser acceptance; no browser execution is added.
Current focused verification and retained failures are recorded in the
[Construction Methods handoff](../STOP_POINT.md#current-handoff-portfolio-construction-methods-v1-2026-11-08).

One universe = one shared, strictly increasing, tz-consistent timeline
(parsed datetimes — never lexicographic strings) with a declared return
frequency, 2–20 assets with identically aligned finite return series
(strict identical alignment; no forward fill, no fabricated timestamps),
optional benchmark returns kept separate from the asset matrix, optional
prior weights (assets absent from the prior map are 0.0 — the documented
"not held" convention), optional aligned unique sample ids, and bounded JSON per-asset metadata
plus name/type/group/currency (one currency per universe; no silent
conversion), 24–2000 observations. The supplied asset order is canonical
and fingerprinted; malformed metadata is rejected rather than discarded.

## 2. No-look-ahead estimation

At a rebalance with decision index i the estimation window is
``returns[i-lag-lookback+1 .. i-lag]`` (rolling) or ``returns[0 .. i-lag]``
(expanding, with a minimum history), with **lag ≥ 1 enforced** — the
period being traded never informs its own weights. A target becomes effective
at index i and then drifts with asset returns until the next rebalance; the
engine does not imply daily rebalancing between scheduled decisions. Centered windows and
negative lags are rejected outright. Early rebalances with insufficient
history are honestly unavailable. Training-only estimation restricts the
permitted window to a leakage-clean validation split's exact recorded
training membership (Phase 50 gates: completed + leakage_clean + valid
split + full membership check) and cannot be combined with full-sample
mode. Full-sample estimation is labelled ``full_sample_descriptive``,
prominently warned, and never called leakage-safe. Future-data mutation
tests prove weight invariance.

Integrity states: ``verified_from_validation_split`` /
``verified_causal_rolling`` / ``declared`` / ``full_sample_descriptive`` /
``unknown`` / ``invalid`` (a user-supplied centered or negative-lag
provenance claim).

## 3. Methods

``user_supplied`` (validated, explicit provenance, normalization by
explicit policy with raw weights retained), ``equal_weight`` (1/N over
eligible assets), ``inverse_volatility`` (1/σ over the trailing window
with an optional VISIBLE volatility floor; floor clamps and per-asset
unavailability are recorded in solver output and run warnings — never
hidden), ``erc`` (equal/targeted risk contribution via the log-barrier
convex formulation, deterministic L-BFGS-B, bounded iterations, explicit
tolerance, residual-based convergence with an absolutely capped loose
band), and ``min_variance`` (deterministic SLSQP, equal-weight init,
explicit maxiter/ftol, convergence + equality residual + objective value
reported, singular/invalid covariance handled honestly). **Deferred
honestly:** maximum diversification (no coherent v1 formulation under the
current constraint model) and mean-variance expected-return optimization
(no robust expected-return model exists here); requesting them returns a
422 with the reason — no placeholder methods exist. Constraints are
independently re-checked after every solve.

## 4. Covariance

Sample (ddof=1, per-period), diagonal reference (clearly labelled an
assumption), fixed shrinkage ``(1-α)·sample + α·target`` with a declared
α ∈ [0,1] and an explicit target (diagonal or scaled identity) — never
data-driven; Ledoit-Wolf deferred (scikit-learn is not a dependency).
Validation reports symmetry, finiteness, diagonal sign, minimum
eigenvalue, PSD status, condition number and near-singular warnings.
Repair is never silent: policy ``none`` leaves invalid matrices invalid
(the solve fails visibly); ``eigenvalue_floor`` clamps at an explicit
visible threshold with original and repaired eigenvalues retained and
fingerprinted. Correlation/volatility stresses rebuild the covariance,
clamp correlations to [−1, 1], and re-validate under the same explicit
repair policy.

## 5. Risk, budgets, concentration

Exact formulas (per period, never annualized):
``σ² = wᵀΣw``, ``MCR_i = (Σw)_i/σ``, ``CCR_i = w_i·MCR_i``,
``PCR_i = CCR_i/σ``; identities ``ΣCCR = σ`` and ``ΣPCR = 1`` checked
within documented tolerance; zero-volatility portfolios return
unavailable contributions; negative contributions in long-short books
stay visible. Budget diagnostics compare targets vs measured PCR with
abs/signed/relative differences and neutral tolerance states plus
max/mean/RMS aggregates — low deviation is never called superior.
Concentration: |w|-share HHI + effective positions, max |w|, top-3 share,
risk-contribution HHI (|PCR| shares ≡ |CCR| shares), pairwise correlation
stats (clipped), and the diversification ratio ``Σ|w_i|σ_i / σ_p``
(absolute weights documented for long-short) — all descriptive; a higher
ratio guarantees nothing.

## 6. Rebalances, turnover, costs, regimes

Schedules: one-time, every N, fixed timeline timestamps (never
fabricated), bounded at 60 (checked eagerly at create). Turnover
convention: ``one_way_turnover = 0.5 × Σ|target weight − drifted pre-trade
weight|``. The prior target is drifted through intervening realized returns;
cash is the visible residual and earns zero in v1. The initial-turnover policy
is explicit (none / zero_book / supplied — supplied requires prior weights).
Linked Phase 55 cost models produce descriptive
rebalance-cost estimates from ``2 × turnover`` (both legs) on the
period-cost path — only turnover-proportional components apply; monetary
fixed fees, one-sided spread configs, order counts and liquidity-dependent
impact are honestly unavailable with explicit reasons (never silently
dropped or costed round-trip); Phase 55 rows and fingerprints are never
mutated, and weights are never submitted anywhere. Linked Phase 54 regime
assignments are joined by exact timestamp (never recomputed) to summarize
per-regime portfolio returns, turnover and cost completeness with
rare-regime warnings; no regime is preferred.

## 7. Sensitivity

Bounded deterministic one-at-a-time scenarios (lookback, shrinkage α,
weight cap, correlation multiplier, volatility multiplier; ≤ 5 values per
dimension, ≤ 40 scenarios, deduplicated, base exactly once, per-scenario
fingerprints). Dimensions inapplicable to the configured
estimation/covariance are rejected at create; a scenario whose value
conflicts with the constraint set is rejected at create; a failing
scenario records a failed row and never voids the run. The base row
reports the final rebalance's actual turnover; variation rows report the
shift from the base book. ``cost_notional_scale`` is deliberately absent
(all period-applicable cost components are notional-invariant in return
space — the scenario could never show anything). No scenario is preferred
or optimal.

## 8. Fingerprints, persistence, baselines

Universe / covariance / constraint / configuration / result / scenario /
weight SHA-256 fingerprints over canonical JSON (12-dp quantization,
NaN/Infinity rejected, no db ids/timestamps/durations/paths). Universe identity
includes aligned observation ids, prior weights and bounded asset metadata;
configuration identity includes normalization, floor, notional, user weights
and immutable linked fingerprints. Each rebalance covariance fingerprint uses
only its permitted causal estimation observations, so a future-only mutation
cannot alter an earlier covariance identity. Result identity includes full
solver, constraint, cost, covariance, regime and sensitivity diagnostics. Six
SQLite tables use idempotent migration with no drops, preserve prior registries,
insert no startup demos, and atomically replace the parent execution snapshot
and every child table. Failed executions are recorded as failed (clearing any
baseline flag) — never left running. Baselines: completed + integrity ∈
{verified_*, declared} +
solver ∈ {closed_form, converged, converged_loose (capped)} + zero
constraint violations + every scheduled rebalance completed + result
fingerprint; scope = universe|dataset|method|covariance-policy|
constraints|window; transactional replacement, idempotent, never
auto-selected by volatility, return, concentration, or deviation.

## 9. API, frontend, demo, export, testing

13 routes under ``/portfolio-diagnostics`` (422/404/409, bounded
pagination, parameterized SQL, no stack traces, no provider calls, no
order submission). Sidebar view **Portfolio Diagnostics** (command
palette registered): six live cards, dark filters, runs table; detail
with fingerprints + baseline action, warnings, linked-record cards,
weight bars with bounds and constraint status, risk-contribution table
with target-vs-measured reconciliation, concentration metrics, covariance and
correlation matrices with printed values (shading is a reading aid — never the
only signal), and a rebalance table exposing decision/effective dates, solver
residuals, constraint details, causal fingerprints, drift-aware turnover and
cost-unavailability reasons. Sensitivity and per-regime tables remain neutral.
Responsive 1440/1024/768. Deterministic idempotent demo (11 runs, 15 spec cases,
seeds 56xxx, ``demo:pd:*``). Export ``portfolio_diagnostics_export_v1`` has a
truncation flag and no paths/credentials/models. The focused backend suite
includes adversarial future-outlier, malformed-input, drifted-book,
fingerprint-materiality and transactional-rollback coverage; the 18-test
Playwright spec remains the browser workflow.

## 9b. Downstream: Portfolio Stress Lab (Phase 57.0)

The Portfolio Stress Lab
([`PORTFOLIO_STRESS_LAB.md`](PORTFOLIO_STRESS_LAB.md)) consumes this lab's
**stored** weights and covariance read-only: a stress run pins the
selected rebalance's weight and covariance fingerprints at create time and
refuses to execute if the stored weights changed since (risk stress is
withheld with an explicit warning if the covariance changed). Nothing in
this lab's records is recomputed, rewritten, or re-fingerprinted by a
stress run, and no stressed result is ever written back as an allocation.

## 9c. Downstream: Portfolio Attribution Lab (Phase 58.0)

The Portfolio Attribution Lab
([`PORTFOLIO_ATTRIBUTION_LAB.md`](PORTFOLIO_ATTRIBUTION_LAB.md)) consumes
this lab's **stored** weights, returns and group labels read-only. It
rebuilds the beginning-of-period weight path with the identical drift
recursion this lab uses for its realized return series — a Phase 58 test
asserts the implied per-period return reproduces
`rebalance.portfolio_returns` exactly — pins this run's configuration
fingerprint at create time, and refuses to execute if that fingerprint
changed. Nothing in this lab's records is recomputed, rewritten or
re-fingerprinted by an attribution run.

Attribution demo books are ordinary Phase 56 books and are listed here
alongside every other run, so this lab's runs table now pages 25 rows
instead of 15 (Phase 58.0). Ordering, filters and every stored record are
unchanged; only the first page holds more rows.

## 10. Limitations

Weights are research measurements under configured assumptions, not
allocations; covariance estimates are sample statistics with estimation
error the lab does not model; ERC is long-only and constraint-free beyond
sum-to-one in v1 (structurally conflicting configs are rejected eagerly);
no cardinality optimization, no expected-return optimization, no
Ledoit-Wolf, no integer-lot enforcement in construction. In minimum-variance
long-short mode, non-smooth gross/group constraints and turnover caps are
post-solve diagnostics rather than SLSQP constraints; violations remain
visible and baseline-blocking. Sensitivity is one-at-a-time around the final
rebalance; cost estimates cover only
turnover-proportional components; upstream quality of supplied returns is
the caller's responsibility.
