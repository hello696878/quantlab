# QuantLab — Market Regime Robustness & Conditional Performance Lab (Phase 54.0)

The local-first lab that conditions candidate outcomes on explicitly defined
market regimes.  Companions:
[`MARKET_REGIME_DEFINITION_POLICY.md`](MARKET_REGIME_DEFINITION_POLICY.md)
(dimension rules and threshold fitting) ·
[`REGIME_NO_LOOKAHEAD_POLICY.md`](REGIME_NO_LOOKAHEAD_POLICY.md) (the
causality contract) ·
[`CONDITIONAL_PERFORMANCE_POLICY.md`](CONDITIONAL_PERFORMANCE_POLICY.md)
(metric conventions) ·
[`REGIME_DIAGNOSTICS_RUNBOOK.md`](REGIME_DIAGNOSTICS_RUNBOOK.md).

> **Honest scope.** Regimes here are descriptive research states formed by
> explicit causal rules — the lab does **not** predict future regimes, does
> not prove causality or profitability, does not select or switch
> strategies or models, does not size positions or allocate capital, is not
> scientific certification or regulatory validation, and is not investment
> advice.  No live data is fetched anywhere.

## 1. Purpose

For a bounded universe of candidates over one shared timeline, the lab
answers: which regime label was effective at every observation; whether
those labels used only information available at or before the documented
cutoff; how much coverage each regime has; how neutral statistics vary
across regimes; whether results concentrate in one or two states; whether
candidate rankings flip between regimes; what is measured around regime
transitions; which regimes are honestly withheld for lack of observations;
and which registry records supplied and store everything, reproducibly via
fingerprints.

## 2. Input model

One shared timeline of 24–2000 strictly-increasing, tz-consistent ISO-8601
timestamps with a **declared frequency**; 1–16 candidates with one finite
outcome per period (`outcome_kind` `return` or `score`); up to 8 named
market-feature series (one finite value per period) from which regimes are
formed — **regimes are never formed from candidate outcomes**; optional
per-period `sample_ids` mapping to Model Validation memberships.  Strict
identical alignment: no forward-filling, no fabricated timestamps, no
imputation.  Observation ids derive deterministically as
`{candidate_id}:{period_index}`.

## 3. Regime definitions

1–6 definitions per run across the dimensions **volatility** (trailing
sample std of the source feature), **trend** (trailing mean),
**liquidity** (trailing mean of an explicitly named liquidity feature —
never inferred), **drawdown state** (trailing-peak drawdown of the
compounded feature level), **categorical** (user-supplied labels with
provenance), and **combined** (exactly two non-combined sources, ≤ 12
distinct pair labels, no rare-combination merging in v1).  Unsupervised
clustering does not exist in v1.  Full rules:
[`MARKET_REGIME_DEFINITION_POLICY.md`](MARKET_REGIME_DEFINITION_POLICY.md).

## 4. No-look-ahead policy and integrity states

The lab's central contract — see
[`REGIME_NO_LOOKAHEAD_POLICY.md`](REGIME_NO_LOOKAHEAD_POLICY.md).  Trailing
windows only; the label effective at period *i* uses the statistic at
*i − lag* with lag ≥ 1; centered windows and negative lags are rejected;
drawdown uses the trailing peak only.  Integrity states per definition
(the run carries the **least-trusted** state among its valid definitions):
`verified_causal_rule`, `verified_from_validation_split`, `declared`,
`full_sample_descriptive` (never leakage-safe, always warned), `unknown`,
`invalid`.  Declared and full-sample labels are never promoted to verified.
The no-look-ahead property is proven by adversarial future-data mutation
tests (backend suite + a dedicated verification pass).

## 5. Conditional performance

Per candidate × definition × regime label: observation count and coverage
(kept more prominent than any statistic), mean/median/std/min/max,
positive/negative rates, cumulative (compounded for returns, summed for
scores), per-period Sharpe-like ratio, downside deviation — under the
conventions in
[`CONDITIONAL_PERFORMANCE_POLICY.md`](CONDITIONAL_PERFORMANCE_POLICY.md).
Regimes below the definition's `min_observations` report counts only, with
statistics withheld and a low-coverage warning; nothing is zero-substituted
and no NaN/Infinity leaves the API.  Maximum drawdown is deliberately
omitted (non-contiguous regime observations have no honest drawdown
semantics — documented).

## 6. Robustness, rank stability, concentration

Per candidate × definition: observed/defined/unavailable regimes,
dispersion of regime means, sign consistency, min/max regime mean, largest
observation share, and a documented classification
(`broadly_consistent` / `mixed` / `concentrated` / `unstable` / `unknown`)
— "broader measured consistency under this configuration", never
"robust".  Rank stability per definition: candidate ranks per regime
(rank 1 = lowest mean, average ties), pairwise Spearman with constant
vectors pre-checked (no scipy warning can escape), top-k overlap with
sparse-pair normalization, per-candidate rank std/range.  Concentration:
observation HHI, positive-outcome HHI, largest/top-2 shares of Σ|outcome|
(signed shares only when all regime sums share one sign — mixed signs are
honestly unavailable), effective regime count 1/HHI, entropy −Σp·ln p.
Concentration is never described as proof of overfitting.

## 7. Transitions

Deterministic intervals from effective labels (unavailable gaps break
intervals without creating transitions); per transition and candidate the
bounded event window's before/after means and their **measured difference**
— never causal wording, and no significance test exists in v1.  Windows are
2–20 periods (default 5); overlapping windows are flagged; ≤ 50 transitions
per definition carry detail (truncation disclosed).

## 8. Multiple comparisons

v1 implements no hypothesis test, fabricates no p-values, and reports
descriptive effect sizes only with significance unavailable — the decision
is recorded in every run's configuration.  Callers with genuinely tested
p-values can apply the Phase 53 Bonferroni/Holm/BH corrections in the
Overfitting Diagnostics Lab, where provenance is enforced.

## 9. Fingerprints

SHA-256 over shared canonical JSON (sorted keys, NaN/Infinity rejected,
12-decimal quantization; no DB ids/timestamps/durations/paths):
**universe** (candidate ids, timestamps, frequency, outcomes, market
features, sample ids, alignment policy), **per-definition** (dimension,
method parameters, threshold mode + fitting-subset identity, labels,
policies) and per-definition **threshold fingerprints**, **configuration**
(universe fp + ordered definition fps + metric/transition policies + linked
validation/overfitting fps), **result** (configuration fp + ordered
assignments + all diagnostics + warnings + integrity).  Material-change
tests included.  Integrity aids only.

## 10. Persistence

Three tables — `regime_diagnostic_runs`, `regime_definitions` (each row
carries its per-period effective-label array as bounded JSON: the
documented v1 form of the `regime_assignments` entity, plus interval
summaries and transition detail: the v1 form of
`regime_transition_results`), and `regime_conditional_results` (explicit
columns) — with 13 indexes, idempotent migration, deterministic child-row
replacement on re-execution, and all prior registries preserved (tested).

## 11. Baseline policy

Completed runs with zero invalid definitions, verified-or-declared
integrity (full-sample descriptive and unknown are rejected — documented
policy) and a result fingerprint may become the baseline of their scope
(dataset version | universe fingerprint | ordered definition fingerprints |
observation window); transactional same-scope replacement, idempotent
re-marking, cleared on invalidation, never selected automatically.  A
baseline is a comparison reference only.

## 12. Integrations

**Experiment Registry** — optional idempotent `regime_diagnostics` record
(dimensions, integrity, coverage/stability counts, both fingerprints); no
recommendation.  **Dataset Lineage** — linked version's fingerprints,
provenance/quality and invalidation warning.  **Model Validation** —
training-only thresholds use the named split's exact recorded training
membership (leakage-clean completed runs only; unknown memberships and
invalid splits fail honestly); split fingerprints never modified.
**Overfitting Diagnostics** — optional candidate-universe link displaying
PBO/PSR/DSR and the universe fingerprint; Phase 53 records never rewritten.
**Feature Diagnostics / Meta-Labeling** — optional contextual links only.
**Cost Diagnostics** (Phase 55.0,
[`TRANSACTION_COST_DIAGNOSTICS_LAB.md`](TRANSACTION_COST_DIAGNOSTICS_LAB.md))
— a cost-diagnostic run may join this lab's **stored** effective
assignments of one named definition by exact timestamp to condition cost
estimates on regimes; assignments are never recomputed and this lab's
fingerprints and results are never modified by that join.

## 13. Demo fixture

`POST /regime-diagnostics/demo-seed` idempotently loads five runs covering
the eleven spec cases (see `backend/app/regime_diagnostics/demo.py`):
volatility+trend+combined with transitions and a regime-concentrated
candidate, the rank-reversal run with an honestly-withheld rare neutral
band, the training-verified baseline, the full-sample-descriptive +
drawdown run, and the invalid centered-labels definition alongside a valid
causal one.  Seeding cascades every other registry's idempotent demo
loader; reload duplicates nothing; no startup insertion.

## 14. API

`/regime-diagnostics/*`: `GET summary`, `GET/POST runs` (filters, bounded
pagination, stable sorting), `GET runs/{id}`,
`POST runs/{id}/execute|invalidate|mark-baseline`,
`GET runs/{id}/definitions` (assignments + intervals + transitions),
`GET runs/{id}/conditional-results` (filterable), `GET compare?a&b`,
`GET export`, `POST demo-seed`.  422/404/409 mapping, parameterized SQL, no
stack traces, no file access, no shell execution, no provider calls;
deterministic bounded execution and deterministic replacement on retry.

## 15. Frontend workflow

Sidebar → **Regime Diagnostics** (also in the command palette).  List:
disclaimer, six live summary cards, dark `ql-input` filters, runs table
(candidates/periods/definitions/regimes/integrity pills/invalid + low-
coverage counts/fingerprint/baseline).  Detail: identity + integrity +
three fingerprints + baseline action, warnings, linked-record cards, the
definitions table with per-definition integrity and thresholds, the
**regime timeline** (color+legend strips per definition with interval-table
alternatives — never color-only), coverage table with unassigned counts,
the conditional candidate×regime table with prominent observation counts
and low-sample pills, robustness and concentration tables with neutral
classification pills, rank-stability matrices, and the transitions table
with measured before/after differences.  Neutral comparison with
comparability warnings.  Usable at 1440/1024/768.

## 16. Export

`regime_diagnostics_export_v1`: runs with configuration and fingerprints,
definitions with assignments/thresholds/transitions, conditional results,
and linked identities.  No absolute paths, environment variables,
credentials, or model binaries; NaN/Infinity rejected; browser download
only.

## 17. Testing

`backend/tests/test_regime_diagnostics.py` (25 tests, isolated temporary
SQLite): input validation, hand-computed trailing statistics, **adversarial
future-data mutation tests** for volatility/trend/drawdown/expanding modes,
lag/centered rejections, every threshold mode and integrity state,
training-membership resolution with leaky-run and unknown-membership
honesty, combined regimes with least-trusted propagation, conditional
metrics + withholding, robustness boundary cases, concentration (mixed-sign
honesty), warning-free rank stability, interval/transition hand-checks,
fingerprint sensitivity, baselines, integrations, migration, export
privacy, demo idempotence, and API paths.  A four-agent adversarial
verification pass (339 reference checks) ran before the tests — its
findings (None-interval contract, whitespace-duplicate feature names,
non-dict candidates, −0.0 entropy, sparse top-k) were fixed.
`frontend/e2e/regime-diagnostics.spec.ts` (16 Playwright tests) covers the
browser workflow.

## 18. Limitations (v1)

Strict identical alignment only; regimes from supplied market features
(the lab cannot audit how those features were produced upstream);
training-only thresholds fit against one named split (not per-split
assignment sets); no unsupervised clustering; no event-study significance;
categorical labels are declarations; combined regimes are pairwise; maximum
drawdown omitted.  And permanently: a regime label is a descriptive state
under one rule — never a prediction, and conditional performance under it
is never causality or profitability evidence.
