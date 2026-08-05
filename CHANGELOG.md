# Changelog

All notable changes to QuantLab are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project aims
to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Changes
after v4.7.0 are **grouped by release area** rather than per-commit — the
per-phase detail lives in [`docs/ROADMAP.md`](docs/ROADMAP.md), and local tags
follow `v4.xx.0-short-feature-name-v1`
(see [`docs/VERSION_MANIFEST.md`](docs/VERSION_MANIFEST.md)). Version labels
are project milestone labels, not package publications; no public release is
claimed by an entry here.

> **Research only.** QuantLab is an educational/research tool — it does not place
> trades, connect to a broker, or provide investment advice, and it is not
> production trading, risk, or compliance infrastructure.

---

## Unreleased

- **Master Blueprint Reconciliation, Project Status Audit & Forward
  Roadmap v1** (v4.80 series): a documentation/status phase — no new
  financial model, analytics engine, database table, API endpoint,
  frontend workspace, dependency, provider integration or trading
  capability. Adds an evidence-backed
  `docs/BLUEPRINT_STATUS_MATRIX.md` (every Master Blueprint phase-order
  area and all 12 model categories classified as built / built_partial /
  planned / research / deferred / deliberate_non_goal, each with backend,
  frontend, test and documentation evidence paths), a
  `docs/BLUEPRINT_RECONCILIATION_REPORT.md` (stale-document findings; the
  signal-vs-strategy ensemble gap; the unified-ML-lifecycle,
  replay-by-hash, futures real-data, frontend-quality and deployment
  gaps; and a neutral tag/version audit covering the missing v4.76
  Phase 58 tag and the recorded v4.69 deviation — no history rewritten,
  no tags created or moved), and a dependency-aware
  `docs/FORWARD_ROADMAP_PHASES_63_70.md` (Phase 63 recommendation:
  Frontend Component Test Foundation and Registry Drift Guards v1; the
  strategy return-stream ensemble follows in Phase 64). Reconciles the long-stale `TASKS.md`,
  `STOP_POINT.md` and `LOG.md` (which still described the July 2026
  local-futures v0.1 checkpoint) with the actual Phase 61 state, updates
  `docs/MASTER_BLUEPRINT_V3.md` status labels to repository reality
  (futures, real estate and microstructure are no longer "research"/
  "future"; Signal Ensemble is not the Strategy Ensemble Builder; ML
  validation exists while a unified ML lifecycle stays partial; launch
  tooling exists while hosted deployment and accounts stay deferred),
  and refreshes ROADMAP / PROJECT_SNAPSHOT / VERSION_MANIFEST. Local
  positioning unchanged: local-first, deterministic, educational, not
  investment advice, no live trading, no production-risk certification.

- **Signal Ensemble, Redundancy & Combination Diagnostics Lab v1**
  (v4.79 series): a local-first lab for COMPARING multiple stored signals
  and evaluating EXPLICIT, user-configured combination references — never
  an optimiser, selector or ensemble recommender. Universes are explicit:
  2–12 Phase 60-style signal definitions in deterministic canonical
  order, one shared stored frequency (mixed frequencies refused — nothing
  is resampled), bounded entities/observations/aligned keys, and per-signal
  user-declared orientation (never derived from performance; raw values
  unchanged; never called a correction). Alignment is by exact
  (entity, timestamp) keys — row-number alignment is impossible by
  construction — under a declared policy: strict_intersection (the ONLY
  universe combinations, matrices and conditioning may use) or
  pairwise_complete (pairwise rows only, each carrying its own sample
  count; a pairwise-complete matrix is never assembled). Missingness is
  disclosed per signal (present / stored-null / absent / coverage) and
  never repaired: no forward fill, interpolation, zero or mean imputation.
  Normalisation is explicit per signal (none, cross-sectional rank
  percentile `(rank−0.5)/n`, cross-sectional z-score with declared ddof,
  or a STRICTLY trailing z-score with declared window and
  current-observation policy); zero variance and thin universes stay
  unavailable with counted reasons, and adversarial tests prove a future
  entity or future outlier cannot change an earlier value. Pairwise
  diagnostics reuse the reviewed Phase 60 correlation machinery (real
  scipy p-values, Kendall tau-b on request, constants/ties/thin overlap
  honestly unavailable) plus comparable-scale mean absolute difference,
  sign agreement with zero-sign counts, per-timestamp bucket agreement
  (exact/adjacent/top/bottom Jaccard over the SAME shared universe) and
  rank-based tail co-occurrence at an explicit quantile — counts only, no
  synthetic p-values, and NO correlation threshold ever marks signals
  duplicates. Matrix-level redundancy runs on the strict intersection
  only: distance `sqrt(0.5·(1−ρ))` (unavailable propagates, never a
  silent zero), eigenvalues with a 1e-10 PSD tolerance (a non-PSD matrix
  is refused, never repaired), rank and condition number (unavailable
  rather than infinite at singularity), eigenvalue concentration and the
  effective signal count `(Σλ)²/Σλ²` — always labelled a
  matrix-concentration diagnostic, never the true number of independent
  signals. Hierarchical clustering uses the already-approved scipy stack
  (single/complete/average linkage, EXPLICIT flat threshold,
  deterministic merges/leaf order, refuses incomplete matrices; no
  auto cluster count, no representative selection, no signal removal).
  Combinations are explicit: equal weight, user-supplied STATIC weights
  (declared negative-weight policy; require_sum_to_one /
  normalise_by_sum / normalise_by_gross / none with gross, net,
  max |w|, zero-weight ids and the residual stored), rank average
  (equal-weight mean of rank percentiles) and a majority-sign vote
  (non-linear, contributions reported as sign votes, reconciliation
  not_applicable). Missing components follow require_all (default) or
  the explicitly opted-in renormalise_available (missing ids, effective
  count and effective weights visible; minimum component count
  enforced); per-observation contributions
  `effective_weight × oriented_normalised` reconcile with the combined
  score to 1e-9 over ALL observations (a stored deterministic sample is
  disclosed), and a combined observation's availability is the LATEST
  component availability — one violation marks the run invalid. The
  combined score and every component are evaluated side by side through
  the Phase 60 horizon/lag/bucket policies with signed-book turnover
  (demo cases show combining both cancelling and CREATING churn —
  neither called better) and pinned Phase 55 notional-proportional costs
  (gross always separate; missing inputs never zero). Neutral
  leave-one-signal-out deltas (no exclusion recommendation, no "harmful
  signal" label), stored Phase 54 regime conditioning (rare regimes
  withheld), Phase 52 train/held-out separation (per-timestamp and
  trailing transforms fit no persistent parameter, weights stay fixed —
  nothing refittable), Phase 59 factor-residual OUTCOME comparison
  (signal-value residualisation deferred with its reason: no stored
  residual signal series exists and automatic residualisation is
  prohibited), Phase 53 Bonferroni/Holm/BH adjustment beside raw
  p-values, seeded whole-cross-section bootstrap quantiles (timestamp or
  moving-block; no bootstrap p-value) and bounded deterministic
  sensitivity scenarios (base exactly once, duplicates collapse by
  fingerprint, ≤24, no preferred configuration). Six canonical
  fingerprints, integrity-gated baselines (never performance-gated),
  neutral field-state comparison that declares no winner, a
  schema-versioned export (`signal_ensemble_export_v1`, ≤25 runs, no
  ids/paths/credentials, NaN/Infinity rejected), 10 SQLite tables + 29
  indexes, a 24-case hand-computable idempotent demo (`demo:sen:*`), 16
  API routes, the **Signal Ensemble Lab** view (similarity matrix with an
  accessible table, redundancy/effective-count panel, cluster table,
  contribution view, full-vs-LOO, horizon/turnover/cost/regime/held-out/
  factor/bootstrap/sensitivity sections, six-fingerprint policy panel),
  80 backend tests and a 26-test Playwright spec. Nothing here proves
  signal independence, diversification, predictability or alpha,
  recommends signals, weights or an ensemble, optimises a combination,
  executes trades, or is investment advice.

- **Signal Decay, Forecast Horizon, Turnover & Implementation Lag
  Diagnostics Lab v1** (v4.78 series): a local-first lab that measures the
  DESCRIPTIVE association between stored signal observations (scores,
  probabilities, ranks) and later outcomes across explicitly declared
  forecast horizons and implementation lags. Signal definitions are explicit
  contracts — type, unit, a declared direction that is NEVER inferred from
  the name, tie policy, availability policy (`explicit_available_at` or
  `same_timestamp`, the latter marked "(assumed)" everywhere), and a
  transformation (`none`, `rank_cross_sectional`, or `rank_full_sample`
  which demotes the whole run to `full_sample_descriptive`). Timing is a
  single enforced contract: signal at grid index i, entry lag l, horizon k
  (units = observations on the entity's OWN stored grid; clock units
  deferred with the resampling reason stated) → entry `grid[i+l]`, exit
  `grid[i+l+k]`, forward return by EXACT-timestamp price lookup only, the
  return earned over `(entry, exit]`; one `available_at > entry` violation
  makes the whole run `invalid`, forensically visible and permanently
  baseline-ineligible. Integrity (7 states, from
  `verified_from_validation_split` down to `invalid`) and overlap
  (`non_overlapping` / `partially_overlapping` / `overlapping` on half-open
  `[entry_idx, exit_idx)` intervals, so back-to-back holdings do not
  overlap) are separate run-level axes; overlapping cells keep their REAL
  scipy p-values with an attached limitation note (never suppressed, never
  "corrected" silently), an effective non-overlapping count that is
  documented as descriptive — never an inferential sample size — and an
  optional deterministic earliest-first non-overlapping selection stored
  BESIDE the full rows, never replacing them. Statistics are scipy-only
  (pearsonr/spearmanr/kendalltau); constants, small samples and degenerate
  ties are unavailable WITH reasons — never 0, never NaN. Cross-sectional
  rank IC is computed per timestamp over that stamp's own ≥3-entity
  universe and aggregated (mean/median/std, descriptive ic_ratio, sign
  shares). Equal-count rank buckets (2–10, global or per-timestamp,
  deterministic tie ordering) yield bucket outcome means, a monotonicity
  description with NO p-value, and a top-minus-bottom spread that is a
  neutral equal-weight measurement reference (gross exposure 2.0
  disclosed) — conservatively unavailable when unique scores < bucket
  count; under a linked Phase 52 validation split, bucket thresholds are
  frozen from TRAINING observations and applied unrefitted to held-out
  data. Decay summaries report the first sign-change horizon, first
  below-threshold horizon, the largest-|statistic| horizon (a location,
  NEVER "the best horizon") and a guarded exponential fit whose half-life
  exists only when the fitted slope is negative. Turnover of the reference
  ranking: one-way turnover 0.5·Σ|Δw| with explicit initial-rebalance
  policies (`no_prior_unavailable` default — the first rebalance is null,
  excluded from means — or `zero_prior_full_build`), top-bucket Jaccard,
  entry/exit counts, holding duration, and holding-cohort overlap with
  gross exposure disclosed under a declared normalisation. Implementation
  lags shift BOTH entry and exit; the lag surface reports degradation and
  no lag is ever recommended. A linked Phase 55 cost model (pinned by
  fingerprint, read-only) contributes only its notional-proportional
  components (commission bps, spread bps × fraction, per-side slippage
  bps) — impact and monetary models are unavailable with reasons — and the
  cost-adjusted spread (gross spread minus MEAN per-rebalance reference
  cost return, different time bases disclosed) always sits in a separate
  column from gross. Stored Phase 54 regime assignments are never
  recomputed (rare regimes < 10 observations withhold statistics), Phase
  59 factor residuals are summed read-only over `[entry, exit)` with an
  exact-coverage requirement, Bonferroni/Holm/BH adjustment (shared Phase
  53 utility) shows adjusted p-values NEXT TO raw ones, and an optional
  seeded bootstrap (iid/moving-block/timestamp, `default_rng`, 50–2000
  resamples) reports quantiles only — no bootstrap p-value. Six canonical
  fingerprints, an integrity-gated baseline (never performance-gated), a
  neutral field-state run comparison that declares no winner, a
  schema-versioned export (`signal_decay_export_v1`, ≤25 runs, no ids/
  paths/credentials), completeness that counts DATA gaps only (structural
  grid-end unavailability disclosed separately), 8 tables + 26 indexes, a
  24-case hand-computable demo (correlations exactly ±1, sign change at
  horizon 2, gross-positive/cost-adjusted-non-positive, a deliberately
  invalid future-looking run, one eligible baseline), 72 backend tests, a
  full Signal Decay Lab UI (decay curve, buckets, turnover, cost, regime,
  held-out, factor-residual, bootstrap, multiple-testing, observations and
  policy panels) and a Playwright spec. Review hardening adds calendar-valid
  canonical timestamps (offset-aware values normalised to UTC), exact
  supplied-interval overlap selection, missing-rank safety,
  exact validation-sample membership, no held-out threshold refit, combined
  gross-2 turnover/cost arithmetic, fit residual evidence, entity-safe
  bootstrap, complete result fingerprints and database-id-free export.
  Nothing here proves
  predictability, validates alpha, recommends a signal, horizon, lag or
  threshold, or is investment advice.

- **Factor Exposure, Return Decomposition & Macro Sensitivity Diagnostics
  Lab v1** (v4.77 series): a local-first factor research lab that measures
  the sensitivity of ONE explicitly declared return series — a stored Phase
  58 portfolio, benchmark, active or cost-adjusted return, or a supplied
  descriptive series, never a mixture — to SUPPLIED factor and macro
  observations. Factor definitions are explicit contracts: category, source
  unit, one of eight documented transformation formulas (level, simple
  return, percent change, log change, first difference, basis-point change
  whose 10 000× / 100× conversion is fixed by a declared rate unit, a
  STRICTLY trailing z-score whose window ends one observation before the
  value it standardises, or a supplied transformed series), an integer lag
  in [0, 60] with negative lags rejected, an availability policy and a
  missing policy that is only ever `unavailable` — nothing is forward-filled,
  interpolated or zero-filled, no factor is categorised automatically, and
  winsorisation is DEFERRED with its reason (every full-sample quantile
  threshold is look-ahead). Alignment is by EXACT timestamp in the factor's
  own observation sequence offset by its lag, so history before the target
  window can satisfy a lag or a differencing transform instead of losing the
  first period; a period whose factor value is missing leaves the sample with
  a stated reason. Timing is explicit and enforced: `lagged_causal` verifies
  that every value used by a period was knowable at or before that period's
  information cutoff (availability OR the selected vintage's release,
  whichever is later) and fails the whole run to `invalid` otherwise;
  `contemporaneous` stays descriptive and is never called ex-ante or
  predictive; a future-looking alignment exists only when the caller declares
  `future_looking_invalid` with a lead, is always `invalid`, and can never
  become a baseline. Macro vintages select `first_release`,
  `latest_available_as_of_cutoff` (so a later revision can never reach an
  earlier fit), `supplied_vintage` or `full_sample_latest_descriptive` (which
  forces a descriptive state), original values are preserved, and a macro
  factor with no release timestamp gets its availability ASSUMPTION stated as
  a warning rather than assumed silently. Estimation is closed-form on the
  approved numpy/scipy stack — statsmodels and scikit-learn are NOT installed
  and were deliberately not added: OLS by SVD with rank, singular values and
  the condition number of the CENTRED factor block; an explicit rank policy
  that either fails honestly or records a labelled minimum-norm solution with
  every standard error withheld; classical covariance
  `sigma² (X'X)⁻¹` with its assumptions printed and NEVER called robust (no
  HC/HAC estimator exists here, so none is advertised); Student-t p-values
  and confidence intervals withheld — not infinite — at zero residual
  variance, insufficient degrees of freedom or a rank-deficient design; an
  R-squared that is UNAVAILABLE rather than 0 or 1 for a constant target; and
  an explicit ridge reference whose coefficients are labelled regularised,
  carry no p-values, get no multiple-testing correction and never select
  their own lambda. Diagnostics: factor correlation with constant factors
  unavailable, exact duplicate- and constant-column detection, variance
  inflation that is unavailable rather than infinite under exact
  collinearity, a neutral condition-number flag stated NOT to be a universal
  rule, residual mean/std/skewness/excess kurtosis/lag-1
  autocorrelation/largest absolutes/concentration and an explicitly defined
  additive cumulative-residual drawdown. Decomposition reconciles every
  period against the estimator's OWN residual vector rather than assuming the
  identity, with the cross-check skipped (not mis-aligned) under a
  training-only fit; supplied asset exposures aggregate with stored Phase 56
  beginning-of-period weights under signed long/short semantics with nothing
  normalised and a missing asset exposure left unavailable rather than zero;
  cross-sectional decomposition is DEFERRED with its reason. Trailing rolling
  windows never read an observation after their own end index — a test proves
  a late outlier cannot change an earlier window's fingerprint — and
  rank-deficient or failed windows stay visible and are never interpolated.
  Benchmark-relative exposure fits the SAME specification to the linked
  attribution run's explicitly declared benchmark; stored Phase 54 regimes
  bucket the periods without ever being recomputed (rare regimes withheld);
  stored Phase 57 stress records supply factor shocks only EXPLICITLY, in the
  factor's transformed unit, with the hypothetical residual component
  reported undefined and no hedge or reallocation implied; stored Phase 58
  attribution is a complementary view whose cost block is never folded into a
  factor contribution; a linked Model Validation split fits on training rows
  only and benchmarks held-out R² against the TRAINING mean. Plus bounded
  deterministic sensitivity scenarios (base exactly once, duplicates dropped,
  no "best model" label), the Phase 53 multiple-testing corrections reused on
  valid p-values with raw values preserved, five content-addressed fingerprint
  kinds, eight new SQLite tables, baselines gated on verified timing +
  complete + full rank + reconciled, a 20-case idempotent demo with
  hand-computable coefficients, the **Factor Diagnostics** view, 81 backend
  tests, a 30-test Playwright spec and six documents. Nothing here proves
  causality, proves alpha, proves manager skill, predicts future returns,
  recommends a factor exposure, a macro trade or a portfolio, hedges,
  allocates, executes trades, certifies a factor model, or constitutes
  investment advice — and no market or macroeconomic data is ever downloaded.

- **Portfolio Performance Attribution, Benchmark & Active Risk Diagnostics
  Lab v1** (v4.76 series): a local-first attribution lab that decomposes
  MEASURED performance of STORED Phase 56 portfolio weights — a period/asset
  observation model built from stored weights and returns where period t
  spans timestamps[t]→[t+1] and its weights are those known at its start;
  a beginning-of-period weight contract where a stored rebalance's weights
  govern period i onward (Phase 56 already guarantees they used data through
  i−lag with lag ≥ 1) and drift between rebalances by the identical
  recursion, verified by a test that reproduces Phase 56's canonical
  realized-return series exactly, with adversarial future-rebalance and
  future-return invariance tests and `end_of_period` timing accepted only as
  an explicitly INVALID descriptive declaration; six integrity states
  (verified_from_stored_rebalance / verified_causal_weights /
  supplied_descriptive / full_sample_descriptive / unknown / invalid, the
  last also covering a linked centered weight basis); exact contribution
  reconciliation (contribution_i = w_i × r_i summing to the portfolio market
  return, group totals summing to the asset totals with no double counting,
  a supplied return NEVER forced to match the reconstruction, and cash
  disclosed as the explicit residual 1 − Σw); explicit benchmark definitions
  (fixed-weight / per-period / buy-and-hold, from an ordered asset list with
  declared weights — never auto-selected, never an implicit equal-weight
  fallback, never silently renormalized, with benchmark-only assets
  requiring explicit returns and explicit groups); Brinson-Fachler and
  Brinson-Hood-Beebower single-period decompositions with both formulas
  documented and hand-computed tests, zero-weight and one-sided groups
  leaving their terms honestly unavailable, and residuals reported verbatim
  with stated reasons and NEVER redistributed; multi-period linking by
  arithmetic summation (with the arithmetic-versus-geometric compounding gap
  disclosed) or Carinó smoothing (reconciling with the geometric active
  return, using the exact x=y limit 1/(1+x) rather than an epsilon guard,
  withheld entirely when a −100% return makes the logarithm undefined, and
  reporting a closure identity so a non-zero linking residual is provably the
  scaled single-period residual); a time-weighted return that is only ever
  LABELLED time-weighted when the inputs support it, with no money-weighted
  or IRR placeholder; cost attribution from stored Phase 56 rebalance
  estimates (Phase 55 records read-only) that distinguishes a structural
  `no_trade` zero from an `unavailable` measurement and nets only over the
  stated costed basis; active-risk diagnostics with a sample (ddof=1)
  convention, annualization only under a declared frequency, an information
  ratio that is unavailable — never infinite — at zero tracking error, hit
  rates and a relative active drawdown; absolute-contribution concentration
  with the signed parts separate; stored-regime and stored-drawdown-episode
  views that never recompute their sources; four fingerprint kinds over
  content-addressed identity; eight new SQLite tables; baselines gated on
  verified provenance + complete results + reconciliation; failed executions
  clearing stale results; a 17-case idempotent demo that seeds its own
  hand-computable books through the Phase 56 public service; the **Portfolio
  Attribution** view (reconciliation, benchmark definition, contribution
  waterfall, group drilldown, Brinson bars + residual, linking, costs,
  active risk, active-return timeline with a table alternative, regimes,
  drawdowns, stored policy); 40 backend tests, a 20-test Playwright spec and
  six docs. Because attribution demo books are ordinary Phase 56 books and
  therefore share the Portfolio Diagnostics registry, that lab's runs table
  now pages 25 rows instead of 15 so its own demo set still fits the first
  page — ordering, filters and every stored record are unchanged. Factor
  attribution is DEFERRED with a stated reason (no
  validated exposure/factor-return matrices exist; factors are never
  inferred from asset names). Nothing here proves alpha or manager skill,
  recommends a benchmark or a portfolio, guarantees future performance,
  produces GIPS-compliant reporting, performs tax accounting, executes
  trades, or constitutes investment advice.

## Grouped release areas — v4.75 (portfolio-stress series)

### Portfolio stress, scenario shock & drawdown attribution lab (v4.75)

- **Portfolio Stress Testing, Scenario Shock & Drawdown Attribution Lab
  v1** (v4.75 series): a local-first stress lab that applies explicit
  deterministic scenarios to STORED Phase 56 portfolio weights — nine
  scenario types (historical window / single period replays of actual
  stored observations, hypothetical asset shock, hypothetical group shock
  — each with an optional global-shock level — volatility, correlation,
  liquidity-and-cost, combined, user-supplied descriptive); unambiguous
  shock units (return decimal, percent, bps;
  absolute price shocks unsupported because stored universes carry
  returns, not reference prices — never fabricated) under a documented
  precedence (asset → group → global → explicit missing-shock policy) with
  the resolved source stored per asset; integrity states
  (`verified_historical_window` — ex-ante only when the window ends
  strictly before the portfolio decision cutoff, `verified_deterministic_rule`,
  `supplied_descriptive`, `full_sample_descriptive`, `unknown`, `invalid`;
  `linked_to_stored_regime` reserved and unused; factor shocks deferred
  with an explicit reason because no run-linked exposure system exists);
  a documented, fingerprinted eight-step execution order; contribution
  attribution reconciled to the scenario total with the cost leg's state,
  reason, completeness and reference-turnover basis carried inside the
  triple (a configured-but-uncomputable cost leg is labelled, never
  silently equal to gross); post-shock drifted weights with a SIGNED cash
  residual (levered books unchanged at a zero shock) and honest
  unavailability for a wiped-out book — no automatic rebalancing;
  independent constraint re-checks on the original and drifted books with
  breaches attributed per book; volatility/correlation stress
  (multiplicative / additive with disclosed zero-flooring; uniform
  multiplier / additive / toward-one / supplied, with asymmetric or
  non-unit-diagonal supplied matrices rejected rather than silently
  fixed) rebuilding Σ* = D(σ*)·R*·D(σ*) with PSD validation and
  never-silent explicit eigenvalue-floor repair, where the disclosed
  vols/correlations always describe the repaired matrix actually used;
  baseline-vs-stressed MCR/CCR/PCR with ΔPCR, rank changes and both
  identity checks; liquidity/cost stress applied to a deep COPY of the
  linked Phase 55 model with its own new fingerprint (the stored model is
  never modified) and honestly unavailable components; trailing-peak-only
  drawdown analysis on the canonical Phase 56 realized series (initial
  capital counts as a peak; interior gaps and non-positive wealth
  refused), exhaustive episode detection with recovered/unrecovered
  states and disclosed deepest-40 persistence, plus per-asset attribution
  of the deepest episode over the below-peak interval under a labelled
  static-weight approximation whose arithmetic-vs-geometric gap is
  disclosed; bounded one-at-a-time sensitivity where the base row shares
  the run's net basis and probes are labelled self-contained scenarios;
  six fingerprint kinds (no database ids — a byte-identical configuration
  reproduces its fingerprint in another database); eight new SQLite
  tables; baselines gated on verified integrity + complete results + an
  available stressed covariance; failed executions clear their stale
  results; a 16-case deterministic demo; the **Portfolio Stress Lab** view
  (contribution waterfall, baseline-vs-stressed PCR bars, drawdown chart
  with episode table, cost/participation panel, sensitivity table,
  verbatim scenario definition); 26 backend tests verified by a 5-agent
  adversarial pass (188 hand-verified checks; every finding — 7 major,
  ~20 minor — fixed); a 17-test Playwright spec; six docs. Scenarios are
  assumptions, not predictions; no scenario is a worst case; measured
  losses are not guarantees; nothing hedges, rebalances, trades,
  recommends an action, or proves safety or robustness.

## Grouped release areas — v4.74 (portfolio-construction series)

### Portfolio construction, risk budgeting & constraint diagnostics lab (v4.74)

- **Portfolio Construction, Risk Budgeting, Diversification & Constraint
  Diagnostics Lab v1** (v4.74 series): a local-first portfolio-research
  diagnostics lab — strictly aligned 2–20-asset universes with parsed
  chronological timelines; a no-look-ahead estimation contract (windows
  end at i−lag with lag ≥ 1; centered windows and negative lags rejected;
  training-only estimation on a leakage-clean validation split's exact
  recorded membership; full-sample permanently descriptive and never
  promotable — adversarially mutation-tested); explicit covariance policy
  (sample ddof=1 / diagonal reference / fixed shrinkage with a declared
  alpha and stored target; Ledoit-Wolf honestly deferred without adding
  scikit-learn) with PSD/eigenvalue/condition validation and a
  never-silent explicit eigenvalue-floor repair; deterministic
  transparent methods (user-supplied with provenance-based integrity,
  equal weight, inverse volatility with a visible fingerprinted floor and
  recorded clamps, ERC via the log-barrier convex formulation with
  residual-based convergence and an absolutely capped loose band, SLSQP
  minimum variance with equality-residual + objective-value reporting;
  max-diversification and mean-variance deferred with reasons, no
  placeholders); constraints with eager structural-infeasibility 422s and
  an independent post-solve re-check (asset-id-structured violations, no
  silent relaxation); exact MCR/CCR/PCR risk contributions with verified
  ΣCCR=σ and ΣPCR=1 identities, neutral risk-budget deviation states,
  concentration/diversification descriptions with clipped correlations;
  half-L1 turnover with explicit initial-book policies; descriptive
  rebalance costs from linked Phase 55 models where trade-level config
  fields (one-sided spreads, monetary fee floors, order counts) are
  honestly unavailable instead of silently dropped; regime-conditioned
  summaries from stored Phase 54 assignments (never recomputed); bounded
  one-at-a-time sensitivity with create-time applicability checks and
  scenario failures that never void the run; seven fingerprint kinds; six
  new SQLite tables; baselines gated on integrity + solver success + zero
  violations + fully completed rebalance histories; an 11-run
  deterministic demo (15 spec cases); the **Portfolio Diagnostics** view
  (weight bars with bounds, target-vs-measured risk contributions,
  printed-value correlation matrix, rebalance/cost table, sensitivity
  with a neutral base marker, regime table); 22 backend tests verified by
  a 5-agent adversarial pass (128 hand-verified checks; every finding —
  3 major, ~12 minor — fixed); an 18-test Playwright spec; six docs.
  Nothing applies weights anywhere, recommends an allocation, identifies
  an optimal/safest portfolio, or guarantees diversification, risk
  reduction, or performance.

## Grouped release areas — v4.73 (execution-cost series)

### Transaction cost, slippage, impact & capacity diagnostics lab (v4.73)

- **Transaction Cost, Slippage, Market Impact & Capacity Diagnostics Lab
  v1** (v4.73 series): a local-first execution-cost diagnostics lab —
  explicitly configured commission / spread / slippage / square-root
  market-impact assumptions applied to supplied trade-level (monetary) or
  period-level (return-space) observations with unit-safe conversions
  (1 bp = 0.0001, explicit percent, tick/price/per-contract/per-unit/
  per-order units, one currency per run, no silent FX conversion);
  per-side round-trip semantics with floor-then-cap fee bounds, an
  explicitly configured spread fraction (no silent half-spread), a
  never-favourable modelled-slippage stress multiplier with supplied
  realized slippage passed through un-stressed, and a documented
  `coefficient × volatility × √participation` impact approximation with
  explicit participation modes and unit-matched ADV; an adversarially
  verified execution-input no-look-ahead policy (trailing windows with
  lag ≥ 1 only, chronologically validated series, centered windows and
  negative lags rejected, no silent fallback from trailing derivation to
  unclassified supplied inputs, mutation-proven future-data invariance)
  with seven provenance-based integrity states; exact gross-to-net
  reconciliation where missing inputs stay unavailable — never zero —
  with complete/partial/gross-only completeness; aggregates with neutral
  wording, break-even diagnostics (bps of notional, max cost multiplier,
  per-component multipliers, impact-coefficient linearity), a bounded
  deduplicated sensitivity grid with a marked base scenario, capacity
  scaling where fixed fees stay fixed and impact scales as scale^1.5
  (optional integer-contract policy with reported exclusions), and
  participation-threshold warnings; costs conditioned on stored Phase 54
  regime assignments (never recomputed); gross + cost-adjusted candidate-
  matrix fingerprints beside read-only Phase 53 links; five new SQLite
  tables; scope-transactional baselines gated on completeness and
  integrity; a 6-run deterministic demo (12 spec cases); the **Cost &
  Capacity** view (gross-to-net waterfall, composition, break-even,
  sensitivity, capacity curve with printed values, regime cost table);
  43 backend tests verified by a 5-agent adversarial pass (197
  hand-computed checks; every finding fixed with a regression); an
  18-test Playwright spec; five docs. Everything is an estimate under
  configured assumptions — no fill prediction, capacity guarantee, order
  execution, size/broker recommendation, profitability proof, or
  investment/execution advice.

## Grouped release areas — v4.72 (conditional-performance series)

### Market regime robustness & conditional performance lab (v4.72)

- **Market Regime Robustness & Conditional Performance Lab v1** (v4.72
  series): a local-first regime-diagnostics lab — candidate outcomes
  conditioned on explicitly defined market regimes (volatility, trend,
  liquidity from an explicitly named feature, drawdown state from the
  trailing peak only, user-supplied categorical states with provenance,
  pairwise combined regimes) under a strict adversarially-tested
  no-look-ahead contract: trailing windows only, effective labels lagged
  ≥ 1 period, centered windows and negative/zero lags rejected; four
  threshold-fitting modes with distinct integrity states (fixed/expanding
  causal, training-only fitted on a leakage-clean validation split's
  recorded membership, full-sample always flagged descriptive and never
  leakage-safe; centered declarations invalid); conditional
  candidate×regime metrics with observation counts prominent and rare
  regimes honestly withheld; robustness classifications, warning-free
  rank stability (rank-reversal demo), concentration diagnostics with
  mixed-sign honesty, and transition before/after differences with no
  significance claims and no fabricated p-values; universe/definition/
  threshold/configuration/result fingerprints; three new SQLite tables;
  verified-or-declared-only scope-transactional baselines; a 5-run
  deterministic demo (11 spec cases); the **Regime Diagnostics** view
  (per-definition regime timeline strips with interval-table fallbacks,
  coverage/conditional/robustness/rank/concentration/transition tables);
  25 backend tests verified by a 4-agent adversarial mutation-attack pass
  (339 checks; 5 findings fixed); a 16-test Playwright spec; five docs.
  Regimes are descriptive states — never predictions, causality,
  profitability, or switching advice.

## Grouped release areas — v4.71 (selection-bias series)

### Backtest overfitting, PBO & multiple testing diagnostics lab (v4.71)

- **Backtest Overfitting, PBO & Multiple Testing Diagnostics Lab v1**
  (v4.71 series): a local-first selection-bias diagnostics lab — CSCV over
  a strictly-aligned bounded candidate universe with the Probability of
  Backtest Overfitting under a fixed documented rank/logit convention
  (rank 1 = worst OOS, ω = rank/(N+1), λ = ln(ω/(1−ω)), PBO = fraction of
  valid splits with λ < 0, deterministic tie handling, all C(S,S/2)
  combinations with a hard 924 cap and no sampling); λ-distribution,
  IS↔OOS degradation and selection-frequency diagnostics in neutral
  wording; Probabilistic and Deflated Sharpe Ratios with explicit
  conventions (per-period ddof=1 Sharpe, population skew, NON-excess
  kurtosis, expected-maximum-Sharpe benchmark, explicit raw/manual/
  dependence-adjusted trial-count policies, honest one-trial and
  zero-variance handling) plus Minimum Track Record Length; Bonferroni /
  Holm / Benjamini–Hochberg corrections with the FWER-vs-FDR distinction,
  declared-only p-value provenance and stable tie ordering; bounded
  candidate-dependence diagnostics with warning-free constant detection
  and an approximate effective trial count; universe/configuration/result
  fingerprints; four new SQLite tables; scope-transactional baselines;
  comparison with explicit comparability warnings; JSON export; a 4-run
  deterministic demo; the **Overfitting Diagnostics** view (λ histogram
  with labelled zero line, Sharpe assumptions on display, multiple-testing
  table); 26 backend tests verified by a 5-agent adversarial
  reference-check pass (303 checks; 3 findings fixed); a 14-test
  Playwright spec; five docs. Every value is a research statistic under
  stated assumptions — never profitability, robustness, safety, or a
  recommendation.

## Grouped release areas — v4.69/v4.70 (research-diagnostics series)

### Feature importance, stability & drift diagnostics lab (v4.70)

- **Feature Importance, Stability & Drift Diagnostics Lab v1** (v4.70
  series): a local-first feature-diagnostics lab — held-out permutation
  importance as the primary method (deterministic in-process estimators:
  L2 logistic, closed-form ridge, bounded CART — no scikit-learn or SHAP
  added, never pickle/joblib), fitted per linked Model Validation split on
  train members only and evaluated on held-out test members
  (leakage-clean runs required; membership mismatches and leakage-failed
  links fail honestly), with declared splits recorded as declarations and
  no-split runs disclosed as not held-out; direction-normalized importance
  (positive = permuting worsened the held-out metric) with bounded
  deterministic repeats and honest negative values; model-native impurity
  and standardized-coefficient references with fixed caveats (drop-column
  omitted, documented); rank stability (Spearman/Kendall, top-k overlap,
  transparent score + thresholds); deterministic correlated-feature groups
  (no automatic removal); distribution drift with explicit
  reference/comparison sets, PSI (explicit bins, ε=1e-6) + KS + documented
  configurable thresholds; importance drift with neutral wording;
  target-leakage rejection; config/result/baseline fingerprints; six new
  SQLite tables; scope-transactional held-out-only baselines; sample-free
  JSON export; a 4-run deterministic demo; the **Feature Diagnostics**
  view (importance bars with zero line + negative-in-color, stability
  matrix, correlation groups, drift tables); 37 backend tests; a 15-test
  Playwright spec; four docs. Importance is measured sensitivity — never
  causality, profitability, or a recommendation.

### Meta-labeling, calibration & threshold lab (v4.69 series — untagged; included in the v4.70 tag history)

- **Meta-Labeling, Probability Calibration & Decision Threshold Lab v1**
  (v4.69 series): a local-first secondary-signal lab — meta-labels whether the
  primary side (−1/0/1; side 0 abstains, never a failed signal) was correct
  under a documented strict-inequality outcome rule; dependency-light Platt
  sigmoid and isotonic (PAV) calibration fitted on training data only, with
  **verified out-of-fold** calibration per linked Model Validation split
  memberships (leakage-clean runs only; membership mismatches fail honestly)
  and declared/not-out-of-fold statuses disclosed rather than trusted;
  Brier / log loss / ROC AUC / PR AUC / reliability bins / ECE / MCE with
  undefined metrics null+reason; a bounded neutral threshold grid (coverage
  prominent, optional abstention band, no "optimal" selection ever); saved
  research threshold policies with per-run baselines (rejected on failed or
  not-OOF runs); deterministic configuration/result/policy fingerprints;
  four new SQLite tables; idempotent Experiment Registry linking and Dataset
  Lineage links with invalidation warnings; a new **Meta-Labeling Lab** view
  (reliability + threshold SVG charts with accessible table fallbacks, dark
  `ql-input` controls); a 7-run demo with policies; a 10-test Playwright
  spec; 28 backend tests; and three docs (`META_LABELING_LAB.md`,
  `PROBABILITY_CALIBRATION_POLICY.md`, `META_LABELING_RUNBOOK.md`). Also
  fixed a fingerprint-row overflow in the Phase 50/51 detail views.
  Meta-label 1 means the research condition was met — never profitability.

## Grouped release areas — v4.8 through v4.68 (post-showcase series)

### Purged CV, embargo & CPCV model validation lab (v4.68)

- Local-first validation lab: temporal-event samples with closed information
  intervals, standard K-fold as an explicitly-warned leakage reference,
  boundary-purged walk-forward, purged K-fold with per-id overlap reasons,
  CPCV bounded at 100 combinations, duration/fraction embargo per disjoint
  test block, a from-scratch leakage audit (any remaining overlap or empty
  training set marks the split invalid), dependency-light neutral metrics,
  deterministic fingerprints, leakage-clean-only baselines, the Model
  Validation Lab frontend with a temporal split timeline, an 11-test
  Playwright spec, and three docs.


### Data provenance & dataset lineage dashboard (v4.67)

- Local-first SQLite dataset registry: dataset identity with immutable
  versions, deterministic schema/manifest fingerprints (content fingerprints
  only via explicit operations), privacy-safe logical storage locators
  (absolute paths/credentials rejected), cycle-safe transformation lineage
  with bounded traversal, metadata-driven quality checks, neutral schema-drift
  comparison, invalidation that preserves lineage and links, bidirectional
  Experiment Registry links with fingerprint-match flags, JSON export, an
  idempotent three-chain demo, the Dataset Lineage frontend view (SVG lineage
  graph + tabular fallback), and a 9-test Playwright spec.

### Research experiment registry & reproducibility dashboard (v4.66)

- Local-first SQLite registry of reproducibility metadata: deterministic
  SHA-256 configuration/result fingerprints (canonical JSON, NaN/Infinity
  rejected), a conservative reproducibility assessment, per-scope baseline
  selection, neutral two-experiment comparison, JSON export, idempotent demo
  records, an opt-in best-effort integration helper (Scenario Studio / KO-PEP
  endpoints unmodified), the Experiment Registry frontend view, a Playwright
  spec, and app-wide 422 hardening for non-finite JSON tokens. The review
  pass added the dark-theme `ql-input` filter controls and the min-width
  table-density fix with E2E guards for both.

### Post-publication verification & stable release baseline (v4.65)

- Read-only verification of the real v4.64 state (tag local = remote →
  `2d4bcfe`; CI run 29188597089 ✅ and Browser E2E Preflight run 29193708980 ✅
  observed on that exact commit; GitHub Release publication remained pending),
  a factual publication record, an item-by-item post-publication verification
  report, the stable post-release baseline document, evidence-ledger/launch-
  checklist updates, and a post-publication checksum manifest.

### Public GitHub release launch closure (v4.64)

- Final manual release draft, facts-only evidence ledger with observed
  CI/E2E run IDs, 22-section public launch checklist + publication runbook,
  SHA-256 checksum manifest with a read-only verifier
  (`verify_release_checksums.py`, unit-tested), README screenshot gallery
  from the frozen evidence. Publication remains a manual user action.

### Manual CI browser E2E evidence (v4.63)

- `workflow_dispatch`-only GitHub Actions workflow (`Browser E2E Preflight`)
  that builds and starts QuantLab in an isolated Ubuntu runner and runs the
  Playwright frozen-demo guard, with per-run evidence artifacts (14-day
  retention); stdlib-only localhost-only readiness helper
  (`scripts/wait_for_http.py`, unit-tested); `CI_BROWSER_E2E.md`. First
  remote run observed green (run 29185725247 on the tag target commit).

### Public release package & demo asset kit (v4.62)

- Copy-ready GitHub release draft (manual publication only), LinkedIn launch
  post drafts, portfolio case study, demo video shot list + 90-second and
  3-minute scripts, public-README checklist, release asset manifest, and
  `scripts/print_public_release_package.ps1` (print-only). Presentation
  material only — no product behavior changes, no automatic releases.

### Browser E2E regression guard (v4.61)

- Playwright harness (one devDependency; drives OS-installed Edge — zero
  browser downloads): 12 tests guarding the frozen demo route, Scenario
  Studio severe-combo result, the KO/PEP pairs fixture, and 1440/1024/768
  responsive geometry; hydration-aware stabilization; E2E runbook, setup,
  and frozen-demo-guard docs; refuse-if-down wrapper scripts.

### Public release candidate & demo freeze (v4.60)

- Six public-readiness docs (release candidate, final smoke test runbook,
  demo freeze checklist, public launch readiness, public known limitations,
  final demo script), the in-app Public Release Candidate page,
  `scripts/print_public_release_candidate.ps1` (print-only), the first full
  browser smoke test (37 views; three responsive defects fixed), futures
  fixture isolation + YM roll coverage, and the frozen freeze record with
  five SHA-256'd production screenshots.

The tags between v4.8.0 and v4.68.0 (local milestone tags; full per-phase
detail in `docs/ROADMAP.md`) grouped by area:

### CI preflight, repository hygiene & security sweep (v4.59)

- CI workflow hardening (read-only permissions, fast-fail typecheck step),
  extended `.gitignore`, `CONTRIBUTING.md`, CI / repository-hygiene /
  security-and-secrets docs, and the read-only
  `scripts/check_repo_hygiene.ps1`.

### Release management (v4.58)

- Version manifest, the grouped changelog refresh, release-notes template,
  extended release checklist, milestone history, project snapshot, `VERSION`
  file, in-app Release Notes Center page, and
  `scripts/print_release_summary.ps1` (print-only).

### Developer onboarding & local demo readiness (v4.57)

- Local demo guide, developer onboarding, troubleshooting, command reference,
  and environment-doctor docs; six safe PowerShell helper scripts (read-only
  doctor, run/test/typecheck wrappers, `.next` cache cleaner, print-only
  cheat sheet); in-app Developer Onboarding page.

### Portfolio launch & public docs (v4.56)

- Public-facing README; portfolio launch pack, public project summaries,
  screenshot checklist, demo video scripts, LinkedIn drafts, interview
  talking points, deployment-readiness notes; in-app Portfolio Showcase page.

### Platform UX polish (v4.55)

- App-router error/loading/not-found safety pages; the sidebar grouped into
  labelled sections (all entries preserved); dashboard "Suggested Starting
  Paths"; chart `ariaLabel` support; visible keyboard focus on shared sliders.

### QA & release readiness (v4.54)

- QA Command Center: 21-module QA registry, coverage rates and release
  score, rule-based release decision, smoke-test matrix, regression
  checklists, exact local verification commands — explicitly never claiming
  tests were run.

### Data reliability & offline fixtures (v4.53)

- Data Reliability Center: module data-mode registry, provider registry
  (optional yfinance/FRED/delayed-quote paths disabled by default,
  fail-closed, never relied on in tests), offline fixture registry incl. the
  KO/PEP pairs-demo fallback, documented reliability rates and score.

### Demo center & product walkthroughs (v4.52)

- Demo Center: eight guided demo paths with deep links, module health
  dashboard, capability matrix, audience/time-budget-aware demo script
  builder with Markdown/JSON export.

### Research workspace & experiment journal (v4.51)

- Research Workspace: saved research packs, staged-run experiment journal,
  severity/coverage/reproducibility scores, workflow timeline, methodology
  checklist, Markdown/JSON exports, optional browser-local drafts.

### Scenario studio & cross-lab reports (v4.50)

- Unified Scenario Studio: ten deterministic scenario templates, global
  shock sliders, documented cross-lab impact-score weight tables, module
  impact charts and heatmap, regime classification, copyable Markdown report.

### Crypto / DeFi / on-chain / alternative data / macro labs (≈v4.42–v4.49)

- Crypto Derivatives (perp funding/basis, educational liquidation
  estimates), DeFi Risk (kinked rate model, finite-by-construction health
  factors), Tokenomics (unlocks, treasury runway), On-Chain Analytics
  (flows, cohorts, whale reads), Alternative Data (sentiment pipeline,
  signal decay, leakage guards), Macro Regime & Cross-Asset Allocation —
  later upgraded with interactive shock sliders, horizon selectors, local
  charts, and collapsible formula panels.

### Derivatives / volatility / futures / real assets / microstructure labs (≈v4.8–v4.41)

- Options Lab (Black-Scholes, Greeks, IV solver, payoff builder, CRR trees,
  Monte Carlo incl. Asian/barrier, vol surface + SVI research fit, Heston);
  Volatility Surface & Variance Swap Lab (explicitly not the VIX
  methodology); Futures & Commodities Lab (cost-of-carry, curve shapes,
  roll yield); Real Estate + MBS Prepayment (CPR/SMM/PSA, WAL, duration);
  Credit Risk (Merton, hazard, simplified CDS); Yield Curve & Short Rate
  (Vasicek/CIR); FX (parity, carry, Garman-Kohlhagen); Event Lab (event
  studies); Market Microstructure & Execution (order-book analytics, TCA
  attribution summing to shortfall by construction, order-flow toxicity
  approximations); Global Markets Globe data layer with opt-in fail-closed
  adapters; Cross-Sectional Scanner; local LaTeX formula rendering
  everywhere.

### Methodology & testing (throughout)

- AFML Methodology Lab (CUSUM events, triple-barrier labels, purged K-fold +
  embargo, sequential bootstrap, fractional differentiation — synthetic
  data, no fitted models, no performance claims); platform-wide testing
  discipline: ~2,900 deterministic backend tests with no live-provider
  dependency, strict Pydantic v2 schemas with finiteness guarantees, wording
  contracts as tests, GitHub Actions CI (backend tests + frontend build).

---

## v4.7.0 — Showcase Candidate — 2026-06-13

This candidate packages QuantLab as a portfolio-ready local research showcase:
the core backtesting/research stack is stable, the Trust Layer is visible in
results and reports, and the Content Engine explains strategies, papers, and
failure modes without pretending planned work is already built.

### Added

**Trust Layer v1**
- Data-quality diagnostics, benchmark analytics/visualization, reproducible
  SHA-256 config hashes, Robustness Lab bootstrap diagnostics, and Stability
  Lab SMA parameter-sensitivity heatmaps.
- Report/export integration for trust diagnostics and caveats, so saved and
  downloaded research remains auditable.

**Content Engine v1**
- Strategy Library pages for live strategies plus honest planned/research
  catalog entries with no run buttons until the backend exists.
- Paper Replications pages with clearly labelled inspired demos, not full
  academic replications.
- Quant Disasters case studies that connect backtest limitations to real risk
  mechanisms and explicit "cannot model yet" lists.
- Command Center content hub, global-search access, and release screenshot/demo
  plans for the showcase flow.

### Changed

- README, release checklist, demo script, screenshot plan, limitations, and
  known-issues docs refreshed for v4.7 showcase readiness.
- Command Palette search now opens all existing educational registry pages
  (including planned Strategy Library / Paper Replication entries) while keeping
  runnable commands limited to implemented strategies and safe demo presets.
- Test-count references updated to the current 1,060+ backend tests across 53
  files.

### Limitations

- Still **research only**: no live trading, broker connection, account system,
  cloud sync, billing, or AI copilot.
- yfinance/CSV daily data only; no survivorship-bias-free institutional data,
  intraday/tick data, or live feeds.
- Cost modelling is static bps/commission/slippage/spread; there is no
  size-dependent market-impact, partial-fill, order-book, borrow, margin, or tax
  simulator.
- Browser print-to-PDF remains the PDF export path; embedded chart images in
  reports are future work.

---

## v4.0.0 — Local-First Quant Research Terminal — 2026-06-08

The first public, portfolio-ready release: a full local-first quantitative
research platform (FastAPI backend · Next.js frontend · local SQLite), with a
neon "quant terminal" UI, single-asset and portfolio analytics, a no-code
strategy builder, branded reporting, and a polished command-center experience.

### Added

**Product experience**
- **Command Center** — local-first home dashboard (quick actions, recent saved work, system status, feature map).
- **Guided Demo Mode** — onboarding card + prefilled demo presets that never auto-run, plus a local quick-start checklist.
- **Command Palette / Global Search** — `Ctrl/Cmd + K` to navigate and search commands plus real saved backtests, reports, and templates.
- **Neon theme & neon chart system** — CSS-variable accent theme (six accents incl. a Risk mode) and accent-aware glowing equity/drawdown/heatmap charts.
- **Toast notifications**, an app-level **error boundary**, and consistent **loading / empty / offline** state primitives.
- **App Settings** — local (browser) defaults for capital, cost, benchmark, date range, accent theme, and report template.

**Strategy research**
- **Single-asset backtesting** with a vectorised, lookahead-bias-free engine (one-day signal shift).
- Strategies: **SMA Crossover, RSI Mean Reversion, Bollinger Band, Time-Series Momentum, Volatility Breakout, Pairs Trading**.
- **Long / short / long-short** direction modes (SMA, Momentum, Volatility Breakout) with diagnostics and a short-selling warning.
- **Strategy Comparison** and **Research tools** — Parameter Sweep, Train/Test validation, Walk-Forward validation.
- **CSV Upload Backtesting** — run strategies on your own daily price CSV.

**Custom strategy lab**
- **Custom Strategy Builder** — no-code entry/exit rule builder over whitelisted indicators (no `eval`).
- **Saved strategy templates** with JSON **import / export**, and a built-in **Strategy Template Gallery**.

**Portfolio lab**
- **Portfolio Backtesting** (equal-weight, turnover-based rebalancing costs).
- **Portfolio Optimization** (min-volatility / max-Sharpe, long-only) and **Walk-Forward Portfolio Optimization** (out-of-sample).
- **Efficient Frontier**, **Risk Dashboard**, **Stress Testing**, and **Factor Analysis**.

**Reporting & persistence**
- **Markdown** and **PDF / print** report export with four **branded report templates**.
- **Saved Reports Gallery** and **Saved Backtests**, persisted in local SQLite.

**Platform**
- **Docker / Docker Compose** one-command stack and **GitHub Actions CI** (backend tests + frontend build).

### Changed
- **README and docs refreshed** — local-first positioning, categorized feature overview, screenshot gallery, and release/QA docs.
- **UI upgraded** to the neon quant-terminal style across every workspace.
- **Default parameters calibrated** for demo usability (clearly not tuned for returns, and not recommendations).
- **Offline UX improved** — friendly "Backend offline" panels with Retry instead of raw HTTP errors, de-duplicated offline notifications.

### Limitations
- **Research only — not investment advice**; **no live trading** and **no broker integration**.
- **yfinance data limitations** (no SLA, possible gaps/anomalies; not survivorship-bias-free; daily only).
- **Local SQLite only** — single-user, no authentication, no cloud sync.
- **Short selling is simplified** — no borrow fees, margin, liquidation, or funding modelled (`|position| ≤ 1`).
- **Portfolio optimization is historical / in-sample** and can overfit; it does not forecast future performance.
- **PDF export** is browser print-to-PDF (text + tables; embedded chart images are future work).

See [`docs/KNOWN_ISSUES.md`](docs/KNOWN_ISSUES.md) and [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) for the full, categorized list.

---

_Earlier development progressed through phases 0–11 (backend MVP → strategies →
research tools → portfolio lab → reporting → settings/theme → long/short →
Command Center / palette / search → toasts, error boundary, state polish →
release prep). See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the full history._
