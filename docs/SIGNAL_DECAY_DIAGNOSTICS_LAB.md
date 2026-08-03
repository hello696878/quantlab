# Signal Decay, Forecast Horizon, Turnover and Implementation Lag Diagnostics Lab (v1)

Phase 60.0 · module `signal_decay` · API `/signal-decay` ·
UI **Signal Decay Lab**

## 1. What this lab is

A local-first research lab that measures the **descriptive association**
between stored signal observations (scores, probabilities, ranks) and later
outcomes across **explicitly declared forecast horizons and implementation
lags**, under a stated availability rule, with overlap, ties, missing data
and costs disclosed rather than smoothed over.

It answers, for a single stored run:

1. which signal was analysed — type, unit, declared direction, tie policy,
   availability policy and transformation;
2. which outcome was paired with it — forward returns computed from stored
   prices by exact timestamp lookup, or explicitly supplied outcomes;
3. exactly when each signal was knowable, and whether any pair violates
   its own availability (a violation makes the run **invalid**);
4. how the association behaves across each configured horizon × entry-lag
   cell: Pearson, Spearman (with real scipy p-values), Kendall on request,
   sign agreement and per-timestamp cross-sectional rank IC;
5. how equal-count rank buckets of the signal map to outcome means, whether
   bucket means are monotone, and what the top-minus-bottom spread of a
   neutral equal-weight reference is — gross, and separately with a linked
   Phase 55 cost model applied;
6. where the measured statistic first changes sign, first drops below a
   configured absolute threshold, where its absolute value is largest, and
   — only when an exponential description fits — a half-life;
7. how much one-way turnover, membership churn (Jaccard), entry/exit
   traffic and holding-period overlap the ranking implies at a reference
   rebalance cadence;
8. how the same statistics look inside stored Phase 54 regime assignments
   (never recomputed), on a stored Phase 52 validation split with bucket
   thresholds frozen from training observations, and against a linked
   Phase 59 factor run's stored residual outcomes;
9. which p-values survive Bonferroni/Holm/Benjamini–Hochberg adjustment
   over the declared family (raw values always shown beside adjusted);
10. seeded bootstrap quantiles for a chosen statistic (never a bootstrap
    p-value);
11. whether the whole result reproduces from six deterministic
    fingerprints.

## 2. What this lab is NOT

It does **not** prove predictability, prove or validate alpha, certify a
signal, recommend a signal, recommend or optimise a horizon, lag, threshold
or holding period, size positions, build or execute a strategy, monitor
anything live, guarantee persistence of any measured association, or
constitute investment, trading or risk-management advice. It never
downloads market data: **every observation is supplied locally.**

The horizon with the largest measured statistic is reported as a location
in this sample — it is never called the *best* horizon. A perfect
in-sample association (the demo contains one by construction) is still
only a description of that sample.

## 3. Module map

| File | Responsibility |
| --- | --- |
| `definitions.py` | signal/outcome definition contracts, direction, tie and availability policies, orientation |
| `observations.py` | validation and bounds, pair construction, overlap intervals, non-overlapping selection, integrity classification |
| `statistics.py` | correlation block (scipy only), cross-sectional IC, autocorrelation, sign agreement, overlap p-value note |
| `buckets.py` | equal-count rank buckets, frozen-threshold assignment, bucket outcomes, top-minus-bottom, monotonicity |
| `decay.py` | per-statistic decay summary: sign change, threshold crossing, max location, guarded exponential fit |
| `turnover.py` | one-way turnover, membership timeline, Jaccard, holding-period overlap |
| `costs.py` | Phase 55 cost-model mapping to notional-proportional per-side bps, per-rebalance cost returns |
| `bootstrap.py` | iid / moving-block / timestamp bootstrap, seeded `default_rng`, quantiles only |
| `fingerprints.py` | six canonical-JSON fingerprints (12-dp floats, NaN/Inf rejected) |
| `store.py` | SQLite persistence: 8 tables, children replaced atomically per execution |
| `service.py` | orchestration: link pinning, 7-step execution order, states, baseline, comparison, export |
| `demo.py` | 24 deterministic hand-computable demo cases (`demo:sd:*`) |

## 4. Run lifecycle

`create_run` validates every definition, bound and policy **before**
anything is stored; a run is created `pending` with its configuration and
identity fingerprints. `execute_run` pins all linked records (dataset
version, feature run, meta-labeling run, validation run + split, regime
run + definition, cost run + model fingerprint, factor run) by identity
and fingerprint, executes the seven engine steps in a fixed order, and
replaces all child rows atomically. An engine refusal (bad configuration
discovered at execution time) stores its honest failure message and marks
the run `failed`; stale results are cleared. `invalidate_run` is the only
mutation of a completed run and only appends an audit reason.

## 5. Integrity, overlap and completeness states

Integrity (per run): `verified_from_validation_split`,
`verified_point_in_time`, `verified_trailing_signal`,
`supplied_descriptive`, `full_sample_descriptive`, `unknown`, `invalid` —
see [`SIGNAL_AND_OUTCOME_TIMING_POLICY.md`](SIGNAL_AND_OUTCOME_TIMING_POLICY.md).

Overlap (per run, a separate axis): `non_overlapping`,
`partially_overlapping`, `overlapping` — see
[`FORECAST_HORIZON_AND_OVERLAP_POLICY.md`](FORECAST_HORIZON_AND_OVERLAP_POLICY.md).

Completeness counts **data** gaps only (null signal values, missing price
stamps, missing supplied outcomes). Structural unavailability at the end
of an entity's grid — the last `horizon + lag` observations cannot have an
outcome by construction — is disclosed but never counted against
completeness.

## 6. Statistics discipline

All correlation statistics come from `scipy.stats` (`pearsonr`,
`spearmanr`, `kendalltau`) so every p-value is a real one. Constant
inputs, samples below the minimum, and degenerate tie structures make a
statistic **unavailable with a reason** — never `0`, never `NaN`. When
outcome intervals overlap, every classical p-value carries a stated
limitation note; the note is attached to the result, never suppressed,
and the raw p-value is never hidden. Multiple-testing adjustment
(Bonferroni, Holm, BH via the shared Phase 53 utility) is reported next
to — never instead of — the raw values.

## 7. Buckets, IC, turnover, lags and costs

See [`SIGNAL_BUCKET_AND_IC_POLICY.md`](SIGNAL_BUCKET_AND_IC_POLICY.md) and
[`SIGNAL_TURNOVER_AND_IMPLEMENTATION_LAG_POLICY.md`](SIGNAL_TURNOVER_AND_IMPLEMENTATION_LAG_POLICY.md).
The top-minus-bottom spread is a neutral equal-weight measurement
reference (gross exposure 2.0), not a strategy. Turnover is measured on
the combined signed long-top/short-bottom book. Cost adjustment uses a
linked, fingerprint-pinned Phase 55 model read-only; only its
notional-proportional components are computable here, everything else is
unavailable with a reason, and gross and cost-adjusted values are always
separate columns. The cost-adjusted spread is limited to the first horizon
and lag whose turnover timeline actually supplies the estimate.

## 8. Linked records

Every link is pinned by id **and** fingerprint at execution time; a
fingerprint mismatch is a conflict, not a silent re-read. Regime
assignments, validation split membership (by explicit sample id when
available, with only an unambiguous prediction-time fallback; purge and
embargo included), cost model components and factor residuals are used
exactly as stored. Feature and meta-labeling links are identity pinning
only in v1. Residual outcomes are the arithmetic sum of the linked factor
run's stored per-period residuals inside `[entry, exit)`, required to
cover exactly `horizon` periods; raw and residual diagnostics are
separate rows and nothing is neutralised automatically.

## 9. Baseline, comparison, export

A run can be a comparison baseline only when integrity is one of the
three verified states and completeness is complete or partial — never
because of its IC, spread or decay profile. Comparison of two runs
reports field states (`same` / `changed` / `only_in_a` / `only_in_b` /
`unavailable`) with comparability warnings; no winner is declared. Export
(≤ 25 runs) is schema-versioned (`signal_decay_export_v1`), contains no
database ids, paths or credentials, and repeats the lab disclaimer.

## 10. Limitations

Stored-grid horizons only (clock-unit horizons are deferred with a stated
resampling reason); descriptive statistics on possibly overlapping
samples; single-asset time-series IC and cross-sectional IC are both
reported but neither implies tradability; costs cover
notional-proportional components only; no slippage-from-impact modelling;
no automatic selection of anything. All of this is restated in
[`KNOWN_LIMITATIONS_PUBLIC.md`](KNOWN_LIMITATIONS_PUBLIC.md).

## 11. Downstream: Signal Ensemble Lab (Phase 61.0)

The Signal Ensemble Lab (Phase 61) reuses this lab's reviewed machinery
read-only — the definition contract for every universe member, the
correlation/bucket/turnover/cost engines for evaluating combined scores,
and optionally a completed run of this lab pinned by configuration and
result fingerprints as identity context. Stored decay results are never
recomputed or mutated there, and a combination evaluated through these
policies is a measurement reference, never a strategy.
