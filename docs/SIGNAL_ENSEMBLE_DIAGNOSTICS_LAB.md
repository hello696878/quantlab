# Signal Ensemble, Redundancy and Combination Diagnostics Lab (v1)

Phase 61.0 · module `signal_ensemble` · API `/signal-ensembles` ·
UI **Signal Ensemble Lab**

## 1. What this lab is

A local-first diagnostics lab for COMPARING multiple stored signals and
evaluating EXPLICIT, user-configured signal-combination references. It
answers, for a single stored run:

1. which signals form the candidate universe — each one a full Phase 60
   definition contract (type, unit, frequency, declared direction, tie
   policy, availability policy, transformation), in deterministic
   canonical (sorted) order;
2. how the signals align on explicit (entity, timestamp) keys — never by
   row number — under a declared strict-intersection or pairwise-complete
   policy, with the missingness summary part of the result;
3. how much pairwise redundancy exists — raw-value Pearson/Spearman
   (Kendall tau-b on request) with real scipy p-values, mean absolute
   difference on comparable scales, sign agreement with zero-sign counts,
   per-timestamp bucket agreement (exact, adjacent, top/bottom Jaccard)
   and tail co-occurrence at an explicit quantile;
4. what the strict-intersection correlation matrix looks like — its
   distance transform `sqrt(0.5·(1−ρ))`, rank, condition number,
   eigenvalue concentration and the effective signal count
   `(Σλ)²/Σλ²`, always described as a matrix-concentration diagnostic;
5. optional hierarchical clustering (scipy single/complete/average
   linkage at an explicit threshold — no cluster count is auto-selected,
   no representative is chosen, no signal is removed);
6. what an explicit combination does — equal weight, user-supplied
   static weights, rank average or majority sign — with per-observation
   component contributions that reconcile exactly, an explicit
   missing-component policy, and evaluation through the Phase 60
   horizon/lag/bucket/turnover/cost policies side by side with each
   component;
7. neutral leave-one-signal-out differences, regime-conditioned
   similarity on stored Phase 54 assignments, training-versus-held-out
   results on a stored Phase 52 split, factor-residual outcome
   comparison against a pinned Phase 59 run, Phase 53 multiple-testing
   adjustment beside raw p-values, seeded bootstrap quantiles and
   bounded sensitivity scenarios;
8. whether everything reproduces from six deterministic fingerprints.

## 2. What this lab is NOT

It does **not** select signals, derive or optimise ensemble weights,
pick thresholds, horizons or lags, prove signal independence, prove
diversification, prove predictability or alpha, recommend or certify an
ensemble, allocate capital, execute anything, or constitute investment
advice. A low correlation never proves independent information; a high
one never proves duplication. The effective signal count is never called
the true number of independent signals, and a combination here is a
measurement reference, not a strategy. No market data is ever
downloaded.

## 3. Module map

| File | Responsibility |
| --- | --- |
| `universe.py` | signal-universe contract (reuses Phase 60 definitions), canonical ordering, bounds, alignment/missing policies, orientations |
| `alignment.py` | (entity, timestamp) grid, strict intersection, pairwise overlap, missingness summary |
| `normalisation.py` | none / cross-sectional rank percentile / cross-sectional z-score / strictly-trailing z-score, explicit ddof and inclusion policy |
| `pairwise.py` | pair rows (reusing `signal_decay.statistics.correlation`), bucket agreement, tail co-occurrence, similarity policy |
| `redundancy.py` | correlation/distance matrices, eigen diagnostics, effective count, scipy hierarchical clustering |
| `combination.py` | four combination modes, weight validation/normalisation, missing policies, contribution reconciliation |
| `fingerprints.py` | six canonical-JSON fingerprints (Phase 60 `_clean` reused) |
| `store.py` | SQLite persistence: 10 tables, atomic child replacement |
| `service.py` | orchestration: link pinning, 9-step execution, LOO, regimes, validation, factor, MT, bootstrap, sensitivity, baseline, compare, export |
| `demo.py` | 24 deterministic hand-computable cases (`demo:sen:*`) |

## 4. Alignment and missingness

See [`SIGNAL_UNIVERSE_AND_ALIGNMENT_POLICY.md`](SIGNAL_UNIVERSE_AND_ALIGNMENT_POLICY.md).
Strict intersection (keys where EVERY signal has a stored non-null
value) is the only universe combination calculations and matrix-level
diagnostics use; pairwise-complete rows exist for pairwise diagnostics
only and always carry their own sample counts. Nothing is
forward-filled, interpolated or zero/mean-imputed.

## 5. Similarity and redundancy

See [`SIGNAL_SIMILARITY_AND_REDUNDANCY_POLICY.md`](SIGNAL_SIMILARITY_AND_REDUNDANCY_POLICY.md).
Constants, heavy ties and thin overlaps are unavailable with reasons; no
correlation threshold marks signals duplicates; an incomplete matrix
withholds eigen diagnostics rather than imputing; a non-PSD matrix
(beyond a 1e-10 tolerance) is refused, never silently repaired.

## 6. Combinations and contributions

See [`SIGNAL_COMBINATION_AND_CONTRIBUTION_POLICY.md`](SIGNAL_COMBINATION_AND_CONTRIBUTION_POLICY.md).
All weights are user-configured (never performance-derived); missing
components follow `require_all` or the explicitly opted-in
`renormalise_available`; linear combinations reconcile per observation
to 1e-9 and a failure is a run-level error, never redistributed. The
combined score's availability is the LATEST availability of its used
components, so a combination can never be more point-in-time than its
inputs.

## 7. Evaluation, validation and costs

See [`SIGNAL_ENSEMBLE_VALIDATION_AND_COST_POLICY.md`](SIGNAL_ENSEMBLE_VALIDATION_AND_COST_POLICY.md).
The combined score and every component are evaluated through the same
reviewed Phase 60 machinery (build_pairs, correlation, buckets,
turnover, cost mapping) — read-only and fingerprint-pinned. Combining
can remove turnover or CREATE it; neither direction is called better.

## 8. Integrity, completeness, baseline

Integrity states: `verified_from_validation_split`,
`verified_point_in_time`, `verified_trailing_transformation`,
`supplied_descriptive`, `contemporaneous_descriptive`,
`full_sample_descriptive`, `unknown`, `invalid` (one availability or
timing violation marks the whole run invalid). Completeness is
`complete` only with full combination coverage, a complete matrix and
(when linked) complete costs. A baseline is integrity-gated only — never
chosen by IC, spread, cost, effective count or turnover — with
transactional same-scope replacement.

## 9. Comparison and export

Two-run comparison reports neutral field states (`same` / `changed` /
`only_in_a` / `only_in_b` / `unavailable`) plus comparability warnings
and declares no winner. Export (≤25 runs) is schema-versioned
(`signal_ensemble_export_v1`), contains no ids/paths/credentials,
rejects NaN/Infinity, and repeats the lab disclaimer.

## 10. Limitations

Bounded execution (≤12 signals, ≤50 entities, ≤40 000 observations,
≤10 000 aligned keys, ≤6 horizons × 3 lags, ≤24 sensitivity scenarios);
contribution rows persist a deterministic sample (disclosed) while
reconciliation is verified over all observations; signal-value factor
residualisation is deferred (no stored residual signal series exists and
automatic residualisation is prohibited); clock-unit horizons remain
deferred; the multiple-testing utility supports Bonferroni/Holm/BH only;
stacking, boosting, neural ensembles and learned meta-models do not
exist here by design.
