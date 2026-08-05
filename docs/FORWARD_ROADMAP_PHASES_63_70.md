# QuantLab — Forward Roadmap, Phases 63–70 (written in Phase 62.0)

An ordered, dependency-aware plan derived from the evidence audit in
[`BLUEPRINT_STATUS_MATRIX.md`](BLUEPRINT_STATUS_MATRIX.md) and the gap
analysis in
[`BLUEPRINT_RECONCILIATION_REPORT.md`](BLUEPRINT_RECONCILIATION_REPORT.md).

Ground rules that apply to **every** phase below and are not repeated in
each entry:

- local-first, deterministic, educational; **not investment advice**;
- no live trading, broker/exchange/wallet integration or order execution;
- no automatic selection, recommendation, optimisation or position sizing;
- no paid providers, no scraping, no new heavy dependency without an
  explicit decision in that phase;
- no authentication, cloud sync or telemetry;
- one implementation commit, then a review commit, then a user-created
  tag — never automatic;
- every statistic honest: unavailable states with reasons, no fabricated
  p-values, gross and costed figures separate.

Sequencing rationale: 63 adds the missing frontend invariant and component-test
layer before another large panel lands → 64 closes the biggest capability gap
with existing infrastructure → 65 unifies the ML islands that 64 can consume →
66 gives every run a replayable identity (needed before an explainer can cite
runs) →
67 defines the real-data contract → 68 uses 67's discipline plus 59's
factor tooling on the scanner → 69 explains what 66 made citable → 70
plans exposure of the result.

---

## Phase 63 — Frontend Component Test Foundation and Registry Drift Guards v1 · **SELECTED NEXT**

**Goal.** Give the frontend its first unit/component test layer and stop
registry-versus-route drift silently.

**Dependencies.** None technical; benefits everything.

**Scope.** A component test framework decision (Vitest + Testing Library
is the natural fit for Next 14 + TS) with a small, high-value suite:
registry invariants (slug uniqueness, every `live` model resolving to a
real strategy id, every registry route existing in the view union),
formatting helpers (`fmtNum`/`fmtPct`/`fmtP` null and non-finite paths),
and pill/state components. Plus a drift guard test that fails when a
sidebar item, view union member or registry entry loses its counterpart.

**Explicit non-scope.** No visual/pixel regression; no snapshot sprawl;
no rewrite of existing Playwright specs; no CI gating change without the
user's decision.

**Commits/tag.** `Add frontend component test foundation registry drift
guards v1` → `Review …` → `v4.81.0-frontend-component-tests-registry-drift-guards-v1`.

**Acceptance criteria.** The new suite runs offline in seconds; a
deliberately broken registry entry fails a test; `npx tsc --noEmit` and
the Playwright suite stay green.

**Risks.** A new dev dependency — must be dev-only, offline, and
explicitly approved in that phase.

---

## Phase 64 — Strategy Return Stream, Strategy Similarity and Portfolio Ensemble Diagnostics Lab v1

**Goal.** Measure how multiple stored **strategy return streams** relate
to one another and what explicit, user-configured combinations of them
would have looked like — the strategy-level analogue of Phase 61's
signal-level lab.

**Why here.** Phase 61 combined signal values; the blueprint's Strategy
Ensemble Builder (area 15) has been `research` since v3 and is the
largest gap that current infrastructure can close without new data,
dependencies or engines.

**Dependencies (all present).** Phase 56 (allocation, constraints),
Phase 57 (drawdown attribution), Phase 58 (contribution reconciliation,
active risk), Phase 54 (regimes), Phase 55 (costs), Phase 52
(train/held-out), Phase 53 (multiple testing), Phases 60–61 (alignment,
fingerprints, baselines, neutral comparison patterns).

**Scope.**
- A strategy universe: 2–12 explicitly declared return streams (supplied
  series, or read-only references to stored backtest/portfolio runs)
  with declared frequency, currency, return convention and availability.
- Strict calendar alignment on explicit timestamps; missing days
  disclosed, never filled; per-pair sample counts.
- Similarity: correlation of returns (real scipy statistics, unavailable
  with reasons), rolling correlation, tail/drawdown overlap, up/down
  capture, and a documented distance — never called independence.
- Explicit combinations only: equal weight, user-supplied static weights
  (declared normalisation, negative-weight policy), inverse-volatility
  and equal-risk-contribution **as declared references reusing Phase 56
  code** — never optimised, never selected.
- Per-period contribution reconciliation: combined return equals the sum
  of weight × strategy return within tolerance.
- Ensemble diagnostics: drawdown, tail overlap, turnover implied by
  rebalancing between strategies, linked Phase 55 cost pricing (gross
  and costed separate), regime conditioning, train/held-out separation
  with frozen weights, leave-one-strategy-out neutral deltas.
- Fingerprints, integrity/completeness states, integrity-gated baseline,
  neutral two-run comparison, schema-versioned export, deterministic
  demo, backend tests, a frontend lab and a Playwright spec.

**Explicit non-scope.** No weight optimisation of any kind; no strategy
selection or ranking; no "best ensemble"; no live rebalancing; no
capital allocation advice; no walk-forward *policy search* (a declared
walk-forward evaluation is in scope, choosing the policy is not); no
strategy generation.

**Commits/tag.** `Add strategy return stream similarity portfolio
ensemble diagnostics lab v1` → `Review …` → expected
`v4.82.0-strategy-return-stream-similarity-portfolio-ensemble-v1`.

**Acceptance criteria.** Hand-computable demo cases (identical streams →
correlation 1 and zero diversification effect; anti-correlated pair;
zero-variance stream unavailable; a combination whose drawdown is
shallower than both components and one where it is not); contribution
reconciliation verified over all periods; gross and costed rows never
mixed; every unavailable state carries a reason; full backend suite,
typecheck and the new spec green.

**Data / security boundary.** Supplied series or stored local runs only;
no network; no new dependency (numpy/scipy/pandas already present).

**Release risks.** Wording risk is the main one — a combination that
looks smoother must never be described as better, diversified or
recommended; the overclaim scan must cover "optimal allocation",
"diversified portfolio", "recommended blend".

---

## Phase 65 — Unified ML Research Lifecycle and Model Artifact Registry v1

**Goal.** Join the two ML islands (the CLI futures loop and the
API/SQLite diagnostics chain) into one traceable lifecycle: dataset →
features → labels → training → purged validation → calibration →
held-out predictions → cost-aware evaluation → artifact registry →
comparison.

**Why here.** Phase 64 will want strategy streams that came from
somewhere traceable, and every later phase benefits from one model
identity instead of two.

**Dependencies.** Phases 49–55 labs; `backend/app/experiments/store.py`;
the futures feature/label/model modules.

**Scope.** A model-artifact registry (identity, dataset version, feature
spec, label spec, model family and parameters, environment fingerprint,
metrics, content hashes — no pickle, no arbitrary code); adapters that
let a stored ML run's predictions flow into Model Validation,
Meta-Labeling, Feature Diagnostics, Cost and Signal Decay without
re-implementing them; a read-only lifecycle view; export.

**Explicit non-scope.** No new model families (no boosting/neural nets);
no AutoML or hyperparameter search; no automatic retraining; no unsafe
deserialisation; no remote registry.

**Commits/tag.** `Add unified ml research lifecycle model artifact
registry v1` → `Review …` → `v4.83.0-unified-ml-lifecycle-model-artifact-registry-v1`.

**Acceptance criteria.** One demo run traverses every stage with a
single identity; refusal paths tested (missing dataset version,
fingerprint mismatch, unsafe artifact); no duplication of existing lab
math.

**Risks.** Scope creep into "an ML platform"; mitigated by registry +
adapters only.

---

## Phase 66 — Reproducible Run Replay by Hash and Environment Manifest v1

**Goal.** Make a stored run recreatable from its hash: resolve a config
hash to its canonical configuration, attach an environment manifest, and
give the UI a replay path.

**Dependencies.** Phase 12.7 config hash; Phase 49 dataset versions;
Phase 65 artifact identity.

**Scope.** Persist `config_hash` with saved runs; a resolve endpoint
(hash → canonical config, never auto-executing); an environment manifest
(Python/Node versions, key library versions, app version, git commit);
dataset-version pinning inside the identity; a replay route that
prefills the form and states explicitly what could not be reproduced.

**Explicit non-scope.** No public permalinks or sharing service; no
automatic re-execution; no cloud storage; no user accounts.

**Commits/tag.** `Add reproducible run replay by hash environment
manifest v1` → `Review …` → `v4.84.0-reproducible-run-replay-environment-manifest-v1`.

**Acceptance criteria.** Round-trip test (config → hash → resolve →
identical canonical config); environment mismatch surfaces as a warning,
never silently; unknown hash → 404 with an honest message.

**Risks.** Implying bit-identical reproducibility across environments —
the manifest must state what it does and does not guarantee.

---

## Phase 67 — Futures Point-in-Time Data Contract, Calendar Foundation and Adapter Specification v1

**Goal.** Specify what real futures data would require and implement the
local calendar/validation foundation without integrating a provider:
a point-in-time contract, a session/holiday calendar model, correction
and vintage policy, provenance and licensing rules, and an adapter
interface behind the existing fail-closed seam.

**Dependencies.** The local CSV pipeline and `RawFuturesStore`;
`docs/DATA_PROVENANCE_POLICY.md`; `docs/FUTURES_DATA_INGESTION_PLAN.md`.

**Scope.** A written data contract (fields, as-of semantics, restatement
handling, hash/version identity); a calendar model specification
(sessions, holidays, early closes, roll interaction) with a local
implementation over *declared* calendars only; a validation suite for
continuous series (roll seams, gaps, spikes) run on local data; an
adapter interface definition with fail-closed defaults; licensing and
attribution requirements written down.

**Explicit non-scope.** No vendor integration, no API keys, no paid
subscription, no downloads, no scraping — contract and adapter specification
plus local calendar/validation implementation only.

**Commits/tag.** `Add futures point in time data contract calendar
foundation adapter specification v1` → `Review …` →
`v4.85.0-futures-point-in-time-contract-calendar-foundation-adapter-spec-v1`.

**Acceptance criteria.** A local CSV corpus validates against the
contract; a deliberately restated bar is detected rather than silently
overwritten; calendar-aware session counting replaces the documented
calendar-free simplification for declared calendars.

**Risks.** Licensing claims must stay generic (no vendor named as
approved); "point-in-time" must not be claimed for data that isn't.

---

## Phase 68 — Advanced Cross-Sectional Neutralisation and Scanner Validation v1

**Goal.** Extend the scanner beyond dollar-neutral weighting and give
its selections the same validation discipline the labs already apply.

**Dependencies.** Phase 59 (factor exposures/residuals), Phase 52/53
(purged validation, PBO/multiple testing), Phase 67 discipline for any
future real universe.

**Scope.** Declared neutralisation options (sector-neutral from explicit
labels, beta-neutral against a declared factor/benchmark, volatility
targeting as a declared reference), cross-sectional residualisation
reusing Phase 59 code, per-rebalance diagnostics, and a validation path
that runs scanner selections through purged CV and multiple-testing
corrections with honest unavailable states.

**Explicit non-scope.** No automatic neutralisation choice; no universe
expansion to real data (that waits on 67); no signal search; no capacity
promises.

**Commits/tag.** `Add advanced cross sectional neutralisation scanner
validation v1` → `Review …` → `v4.86.0-cross-sectional-neutralisation-scanner-validation-v1`.

**Acceptance criteria.** Hand-computable neutralisation cases (a
perfectly sector-aligned signal neutralises to zero exposure); validated
selections report adjusted p-values beside raw; the synthetic-universe
caveat stays prominent.

**Risks.** Neutralised results looking like alpha — wording and
disclaimers must stay at Phase 59/61 standards.

---

## Phase 69 — Evidence-Grounded Research Explainer v1 (Deterministic)

**Goal.** Explain stored results in plain language, citing only values
that exist in a stored run — never recommending anything.

**Dependencies.** Phase 66 (a run must be citable and replayable),
Phase 65 (model identity), the existing per-lab policy documents that
supply the honest vocabulary.

**Scope.** An explanation service that reads a stored run, produces a
structured narrative where **every numeric claim carries a provenance
reference** to the field it came from, refuses when the underlying value
is unavailable, and is constrained by an explicit banned-claim list
(no predictions, no advice, no "good/bad" verdicts). The v1 renderer is
deterministic and offline: validated templates map stored fields to prose
without any generative model or provider.

**Explicit non-scope.** No trading or investment advice; no
recommendations of signals, strategies, weights or horizons; no local or
cloud LLM/model calls; no provider credentials or new model dependency;
no free-form generation; no persuasion or confidence language.

**Commits/tag.** `Add deterministic evidence grounded research explainer
v1`
→ `Review …` → `v4.87.0-deterministic-evidence-grounded-research-explainer-v1`.

**Acceptance criteria.** Every sentence in an explanation maps to a
stored field or is a stated limitation; a run with unavailable
statistics produces an explanation that says so; the banned-claim scan
passes on rendered output as well as on source code.

**Risks.** The highest wording risk in the roadmap; mitigated by
template-only design, provenance requirements and rendered-output
scanning.

---

## Phase 70 — Read-Only Hosted Demo and Deployment Hardening Plan v1

**Goal.** Produce the plan and the hardening work for a **read-only**
public demo, without adding authentication or multi-user features.

**Dependencies.** Phase 63 (frontend guards), the frozen demo baseline,
`docs/DEPLOYMENT_READINESS.md`.

**Scope.** A read-only mode specification (which endpoints are disabled,
how writes are rejected, how the demo database is seeded and reset), a
hosting-shape decision document (container, HTTPS, reverse proxy,
resource limits), backup/restore and migration operations for the
single-file SQLite store, monitoring and health-check requirements,
secret-management rules, provider governance for a public instance
(everything fail-closed and disabled by default), and an abuse/rate-limit
policy — plus whatever hardening can be implemented locally without
hosting anything.

**Explicit non-scope.** No authentication, no user accounts, no
multi-user isolation, no actual deployment, no cloud provisioning, no
telemetry, no paid services. Nothing is hosted by this phase.

**Commits/tag.** `Add read only hosted demo deployment hardening plan
v1` → `Review …` → `v4.88.0-read-only-hosted-demo-deployment-hardening-plan-v1`.

**Acceptance criteria.** Read-only mode is demonstrable locally (writes
refused with honest messages); the plan states explicitly what remains
unbuilt; no secret, key or credential enters the repository.

**Risks.** The wording must never imply the platform is deployable or
certified for production use; the document has to keep saying it is a
plan plus local hardening, with the unbuilt parts named.

---

## Summary table

| Phase | Title | Status of dependencies | New dependency? | Data boundary |
|---|---|---|---|---|
| 63 | Frontend component tests + drift guards | none | dev-only test runner (decision required) | none |
| 64 | Strategy return stream / ensemble diagnostics | frontend guards from 63 | none | supplied series + stored local runs |
| 65 | Unified ML lifecycle + artifact registry | 64 helps, not required | none | local artifacts only |
| 66 | Replay by hash + environment manifest | 65 recommended | none | local only |
| 67 | Futures point-in-time contract + calendar foundation | local pipeline present | none | local CSV only |
| 68 | Cross-sectional neutralisation + scanner validation | 59, 52, 53 present; 67 helps | none | synthetic universe |
| 69 | Deterministic evidence-grounded explainer | 66 required, 65 recommended | none | stored runs only |
| 70 | Read-only hosted demo + hardening plan | 63 recommended | none | local demo data |

Phases 63–70 deliberately schedule **no** live execution, **no** paid
providers and **no** automatic investment recommendations.
