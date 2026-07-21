# QuantLab — Backtest Overfitting, PBO & Multiple Testing Diagnostics Lab (Phase 53.0)

The local-first lab that measures selection bias across a bounded universe of
strategy candidates.  Companions:
[`PBO_AND_CSCV_POLICY.md`](PBO_AND_CSCV_POLICY.md) (CSCV/PBO conventions) ·
[`SHARPE_DEFLATION_POLICY.md`](SHARPE_DEFLATION_POLICY.md) (PSR/DSR/MinTRL) ·
[`MULTIPLE_TESTING_POLICY.md`](MULTIPLE_TESTING_POLICY.md) (corrections) ·
[`OVERFITTING_DIAGNOSTICS_RUNBOOK.md`](OVERFITTING_DIAGNOSTICS_RUNBOOK.md).

> **Honest scope.** Every number here is a research statistic under stated
> assumptions.  The lab does **not** prove profitability, does not prove
> robustness or safety, does not select a deployment strategy, does not
> eliminate overfitting, does not certify statistical validity, does not
> replace independent review, is not regulatory validation, and is not
> investment, trading, allocation, tax, legal, compliance, or
> risk-management advice.  No live data is fetched anywhere.

## 1. Purpose

When many candidates are tried and the in-sample winner is reported, the
selection itself inflates apparent performance.  The lab answers: how many
candidates were tested; which was selected in each in-sample partition; how
did it rank out of sample; what is the estimated Probability of Backtest
Overfitting; how does in-sample performance degrade out of sample; is the
highest observed Sharpe unusual after accounting for the number of trials
(PSR/DSR); how long a track record the stated confidence would require;
which nominal p-values survive Bonferroni/Holm/BH; how correlated the trials
were; which registry records supplied the inputs; and whether the whole
result reproduces via fingerprints.  Anything whose assumptions fail is
reported as unavailable — never zero, never NaN.

## 2. Candidate universe

2–24 candidates (unique ids ≤ 64 chars, optional name/description/group,
optional experiment / validation-run / dataset-version links, optional
configuration/result fingerprints, optional nominal p-value with provenance,
bounded metadata) over one shared timeline of 24–2000 strictly-increasing
ISO-8601 timestamps with one timezone convention.  **Alignment policy
(v1): strict identical alignment** — every candidate supplies exactly the
same number of ordered observations; there is no intersection alignment, no
forward-filling, no fabricated timestamps, and missing/non-finite values are
rejected.  Candidates are ordered deterministically by candidate_id
everywhere (matrix columns, fingerprints, tie-breaking).

## 3. Performance metric policy

CSCV ranking metrics (all higher-is-better, per-period, **never silently
annualized**): `mean_return`, `median_return`, `sharpe_like`
(= mean / std(ddof=1), risk-free 0, sample std — the registry-era
convention).  `cumulative_return` is descriptive only and can never rank.
Downside-adjusted ratios are omitted in v1 (no correct existing
implementation to reuse — documented).  Undefined metrics (fewer than 2
observations, zero volatility) return null + note; incompatible metrics are
never mixed in one ranking; `periods_per_year` is a display/calendar
declaration only.

## 4–8. CSCV, PBO, rank convention, tie policy, lambda

See [`PBO_AND_CSCV_POLICY.md`](PBO_AND_CSCV_POLICY.md) for the full
convention set.  Summary: S even chronological contiguous blocks (4 ≤ S ≤
12, sizes differ ≤ 1, every observation in exactly one block, boundaries
recorded); all C(S, S/2) in-sample combinations in lexicographic order with
exact complements (no sampling or truncation — C(12,6) = 924 is the hard
cap, larger configurations 422); per combination the in-sample metric ranks
every candidate, the top candidate is selected (exact ties → smallest
candidate_id, recorded), out-of-sample ranks use **ascending average ties
(rank 1 = worst OOS, rank N = strongest OOS)**, ω = rank/(N+1),
λ = ln(ω/(1−ω)); **PBO = fraction of valid splits with λ < 0** (λ = 0
counts in the denominator, not as overfit); splits whose metrics are
undefined are recorded invalid and excluded from the denominator, never
dropped silently.  Aggregates: λ mean/median/std/quantiles, IS↔OOS
correlation of the selected candidate (pre-checked, null when constant),
OOS-loss fraction (sign-based, meaningful because all ranking metrics are
zero-centred for a no-edge candidate), mean/median performance and rank
degradation, per-candidate selection frequency + IS/OOS rank statistics.
Stochastic-dominance summaries are deliberately omitted in v1.  Wording is
fixed: lower/higher **estimated selection-overfitting frequency under this
configuration** — never robustness.

## 9. PBO sensitivity

Sensitivity to block count, metric, candidate subset, or window is done by
creating **separate runs** — each with its own universe/configuration/result
fingerprints — and comparing them; the compare endpoint warns explicitly
when universes, metrics, block counts, windows, annualization declarations,
or trial-count assumptions differ.  Incompatible configurations are never
averaged, and no configuration or candidate is ever preferred automatically.

## 10–12. PSR, DSR, MinTRL

See [`SHARPE_DEFLATION_POLICY.md`](SHARPE_DEFLATION_POLICY.md).  Summary:
PSR(SR\*) = Φ((SR̂ − SR\*)·√(T−1) / √(1 − γ₃·SR̂ + ((γ₄−1)/4)·SR̂²)) with
population-moment skewness and **non-excess** kurtosis; the variance
expansion must be positive and T ≥ 12, else unavailable; T < 30 attaches a
visible small-sample warning.  DSR = PSR against the expected-maximum-Sharpe
benchmark E[maxSR] ≈ √V·((1−γ)·Φ⁻¹(1−1/K) + γ·Φ⁻¹(1−1/(K·e))) (γ =
Euler–Mascheroni, V = cross-trial variance of estimated Sharpes, K =
effective trials); run-level PSR/DSR/MinTRL focus on the **highest observed
Sharpe candidate** — the value selection bias applies to, a descriptive
focus, never a recommendation.  K comes from an explicit policy: raw count,
a manual value within [1, raw], or the dependence-based approximation — the
assumption is always displayed; one trial → DSR honestly unavailable.
MinTRL = 1 + (1 − γ₃·SR̂ + ((γ₄−1)/4)·SR̂²)·(z_conf/(SR̂ − SR\*))² in
observations at the stated frequency (calendar conversion only when
`periods_per_year` is declared); SR̂ ≤ SR\* → unavailable.  PSR is never
"the probability the strategy will be profitable"; DSR is never proof
against overfitting; no track record guarantees future performance.

## 13. Multiple-testing corrections

See [`MULTIPLE_TESTING_POLICY.md`](MULTIPLE_TESTING_POLICY.md).  Bonferroni
(min(1, p·m)) and Holm (step-down, monotone) control the family-wise error
rate; Benjamini–Hochberg (reverse-cummin q-values) controls the false
discovery rate under stated assumptions — **BH does not control FWER**.
m counts only candidates that supplied a valid p-value; missing values stay
unavailable; invalid values (out of range, non-finite) are excluded from m
and marked invalid; ties use stable ordering; original candidate order is
preserved; all outputs are bounded [0,1].  States at the configured alpha
are neutral (below/above threshold/unavailable) — nothing is approved,
validated, accepted, or rejected automatically.

## 14. Candidate dependence

Pearson correlation over candidate returns (target/benchmark never
included), with constant candidates detected **before** any correlation call
(scale-free `ptp == 0` plus a 1e-12 std tolerance — no ConstantInputWarning
is ever raised or suppressed, a defect caught and fixed during this phase's
adversarial verification).  Reported: mean/median |ρ|, pairs above a
validated threshold, deterministic union-find clusters, and the approximate
effective trial count `K_eff = 1 + (K−1)·(1 − mean|ρ|)` — a documented
conservative interpolation, explicitly not exact.  Nothing is collapsed or
deleted, and correlated trials are never treated as independent.

## 15. Baseline policy

A completed run with zero invalid splits and a result fingerprint may be
marked the baseline of its scope — one active baseline per (dataset version,
universe fingerprint, metric, block count, observation window), replaced
transactionally, idempotent on re-mark, cleared by invalidation, and never
selected automatically by lowest PBO or highest DSR.  A baseline is a
comparison reference — not a recommended strategy and not validated
research.

## 16. Integrations

**Experiment Registry** — optional `create_experiment` records a neutral
`overfitting_diagnostics` experiment (candidate count, metric, blocks, PBO,
PSR/DSR, trial-count assumption, methods, both fingerprints); idempotent
across re-executions; no recommendation is stored and no candidate is
marked for deployment.  **Dataset Lineage** — linked versions display
name/label, fingerprints, provenance/quality states and an invalidation
warning; dataset metadata is never mutated.  **Model Validation** — linked
runs display method, split counts, leakage status and fingerprints; the
card states explicitly that PBO complements and never replaces split-level
validation.  **Feature Diagnostics** — optional context link displaying the
run name and held-out integrity status; records are never rewritten.

## 17. Demo fixture

`POST /overfitting-diagnostics/demo-seed` (or the UI button) idempotently
loads four runs covering the ten spec cases — see
`backend/app/overfitting_diagnostics/demo.py`: the 14-noise-candidate
high-PBO run (with the correlated pair, the surviving-nothing p-values, and
the many-trial DSR deflation), the persistent-drift lower-PBO run (linked +
baseline), the short-record/constant/one-trial run, and the honest
invalid-configuration failure.  Seeding cascades the Feature Diagnostics →
Meta-Labeling → Model Validation → Dataset Lineage → Experiment Registry
demo loaders (all idempotent, unique `demo_key`); reload duplicates
nothing; there is no startup insertion.

## 18. API

`/overfitting-diagnostics/*`: `GET summary`, `GET/POST runs` (filters:
status/metric/dataset/validation/fingerprints/baseline/PBO range/query;
bounded pagination; stable sorting), `GET runs/{id}`,
`POST runs/{id}/execute|invalidate|mark-baseline`,
`GET runs/{id}/candidates|pbo-splits|sharpe-diagnostics|multiple-testing|
dependence`, `GET compare?a&b`, `GET export`, `POST demo-seed`.  422/404/409
mapping, parameterized SQL, no stack traces, no file access, no model
loading, no shell execution, no provider calls; execution deterministic and
bounded (≤24 candidates, ≤2000 observations, ≤12 blocks, ≤924 combinations,
≤64 hypotheses); re-execution replaces rather than duplicates rows and
reuses the linked experiment.

## 19. Frontend workflow

Sidebar → **Overfitting Diagnostics** (also in the command palette).  List:
disclaimer header, six live summary cards, dark `ql-input` filters, runs
table (candidates/observations/metric/blocks/valid splits/PBO/PSR/DSR/
status/fingerprint/baseline star).  Detail: identity + three fingerprints +
baseline action, warnings, linked-record cards, the PBO section (stat cards,
convention footnotes, λ histogram with a labelled zero line and table-backed
split data), candidate selection-frequency table, paginated CSCV split
table, Sharpe diagnostics with every assumption on display, the
multiple-testing table with the FWER/FDR explanation, dependence, and the
candidate table.  Neutral comparison view with explicit comparability
warnings.  Usable at 1440/1024/768; no page-level horizontal overflow.

## 20. Export

`GET /overfitting-diagnostics/export` returns schema-versioned JSON
(`overfitting_diagnostics_export_v1`): runs with configuration and
fingerprints, the candidate universe (including return series — the
deterministic research inputs), CSCV block definitions and split results,
PBO aggregates, Sharpe diagnostics with assumptions, multiple-testing rows,
dependence, and linked identities.  Absolute paths, environment variables,
credentials and serialized models are excluded; NaN/Infinity rejected;
nothing is written into the repository automatically.

## 21. Testing

`backend/tests/test_overfitting_diagnostics.py` (26 tests, isolated
temporary SQLite): input validation + deterministic ordering, block
construction + combination limits + lexicographic determinism, the
PBO = 0 / PBO = 1 reference constructions, tie handling (two-way, all-tied,
OOS average ranks, λ = 0 boundary), invalid-split exclusion, hand-computed
PSR/E[maxSR]/DSR/MinTRL references (including the PSR(T = MinTRL) ≡
confidence identity), the classic BH example + ties + missing/invalid
p-values, warning-free constant handling in dependence, fingerprint
sensitivity, API happy/error paths, honest failure, baseline transitions,
integrations, export privacy, demo idempotence and migration safety.  A
five-agent adversarial verification pass (303 hand-computed reference
checks) ran against the canonical formulas before the test suite was
written; the three defects it found were fixed and regression-tested.
`frontend/e2e/overfitting-diagnostics.spec.ts` (14 Playwright tests) covers
the browser workflow.

## 22. Limitations (v1)

Strict identical alignment only; three ranking metrics; no
downside-adjusted ratio; no stochastic-dominance summary; sensitivity =
separate runs, not an in-run sweep; the effective-trial estimate is an
approximation; p-values are caller-declared (nothing is
`verified_from_supported_test` in v1 because the lab runs no hypothesis
tests of its own); CSCV blocks are contiguous chronological subperiods (no
purging between blocks — link a Model Validation run for interval-aware
splits); PSR/DSR inherit their distributional assumptions and small-sample
fragility.  And permanently: low PBO under one configuration is not
robustness, high DSR is not proof against overfitting, and nothing here
selects, recommends, or allocates.
