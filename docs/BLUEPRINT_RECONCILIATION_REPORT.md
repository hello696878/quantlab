# QuantLab — Blueprint Reconciliation Report (Phase 62.0)

What the planning documents claimed, what the repository actually
contains, where the two disagreed, and which gaps matter. Every claim
here was checked against files; the per-area evidence lives in
[`BLUEPRINT_STATUS_MATRIX.md`](BLUEPRINT_STATUS_MATRIX.md) and the
forward plan in
[`FORWARD_ROADMAP_PHASES_63_70.md`](FORWARD_ROADMAP_PHASES_63_70.md).

**Scope of this phase:** documentation, audit and planning only. No
financial model, analytics engine, database table, API endpoint,
frontend workspace, dependency, provider integration or trading
capability was added, and no product behaviour changed.

---

## 1. Stale and contradictory documents found

| Document | What it claimed | Repository reality | Action taken |
|---|---|---|---|
| `TASKS.md` | "Now: local futures data path v0.1 stable — no task in flight"; "Do Not Do Yet: ML, options, futures_continuous, real data" (dated 2026-07-05) | Options shipped long before that date (Phases 14.x); `futures_continuous` exists (`backend/app/datastore/futures_continuous.py`, `continuous_build.py`); a full local-futures ML loop exists (`features/`, `labels/`, `ml_signal/`, `local_pipeline/`); Phases 48–61 added fourteen diagnostics labs | Rewritten to the truthful Phase 62 state; historical "Done" records preserved verbatim; superseded prohibitions relabelled as history |
| `STOP_POINT.md` | "Current Phase: local futures data path v0.1 — stable … committed through `3d320f6`" | `main` is at `40ec1fd` (Phase 61 review), VERSION was `4.79.0-dev`, 124 tags exist | Replaced with a Phase 62 handoff (version/phase/branch/tag state, frozen baseline, next safe step, restart commands, non-goals) |
| `LOG.md` | Newest entry 2026-07-05 (futures v0.1) | 13 feature phases landed afterwards | New dated entry prepended in the existing format; older entries untouched |
| `docs/MASTER_BLUEPRINT_V3.md` | "Futures & Commodities — research"; "Real Estate — research"; "Microstructure & HFT — future"; "ML & AI — future"; "Strategy Ensemble Builder — research"; status vocabulary `built/planned/research/future` | Futures: educational lab **and** a local research pipeline with instruments, ingest, continuous contracts, backtest adapter and ML loop. Real estate: income-property + MBS analytics with 50 tests. Microstructure: order-book/TCA/toxicity lab with 43 tests. ML: validation chain (Phases 50–61) plus the futures ML loop. Signal Ensemble ≠ Strategy Ensemble Builder | Status labels corrected in place; vocabulary aligned to the six-class matrix; the document stays an internal direction, not a feature claim |
| `docs/PROJECT_SNAPSHOT.md` | Phase 61 header, "~40 interactive workspaces" | Accurate but version-stale | Header/version refreshed; pointer to the status matrix added |
| `docs/VERSION_MANIFEST.md` | 123 tags, latest verified v4.78 | 124 tags, latest verified v4.79 | Counts and expected-tag line updated |
| `AGENTS.md` | "The current priority is: build a correct backend MVP" | The MVP shipped at v4.0.0; the platform is at v4.79 | **Left unchanged** — it is a historical instruction file for the Codex review flow, not a status claim; noted here instead |
| `CLAUDE.md` | "Current focus: Phase 1 futures-first … Do not implement yet: ML, options, futures_continuous …" | Same contradiction as `TASKS.md` | **Left unchanged** — it is the user's own operating-instruction file; flagged here for the user to update if desired (this phase does not rewrite user instructions) |

Nothing else in `docs/` contradicted the code materially: the per-lab
documents written in Phases 48–61 matched their implementations, and
`docs/LIMITATIONS.md` / `docs/KNOWN_LIMITATIONS_PUBLIC.md` were already
honest about deterministic data and missing capabilities.

## 2. Headline finding

The repository is **substantially further along than its top-level
planning files claimed**, and **less far along than the blueprint's
category headlines imply**. Both directions matter:

- Under-claimed: the entire local futures research track (instruments →
  ingest → continuous contracts → backtest → features/labels → model →
  experiment store → evidence packs) was invisible in `TASKS.md` and
  `STOP_POINT.md`, and is still invisible in the product UI.
- Over-claimable: "~40 workspaces" is **not** ~40 models, and the
  ~100-model catalog has no defined denominator. This document
  publishes no completion percentage for that catalog; see §3.

## 3. Counting rules (why there is no "X of 100 models" number)

The blueprint's "~100 educational quant models across 12 categories" has
never been enumerated in the repository: there is no list of 100 named
models, no rule for whether (say) Vasicek and CIR count as one model or
two, and no rule for whether a diagnostic lab counts at all. Publishing
a percentage would therefore be fabricating a denominator. What can be
stated honestly:

- ~40 interactive workspaces are routed in the frontend view switch.
- 14 strategy entries exist in `frontend/src/lib/modelRegistry.ts`, of
  which **7** are `live` (executable through Backtest Studio).
- The pricing/analytics catalogue (options, vol, rates, FX, credit, real
  estate/MBS, microstructure, crypto family) contains dozens of distinct
  closed-form or simulation models, each with its own tests.
- 16 product-workflow diagnostics workspaces exist (Phases 48–61).

## 4. Gap analysis

### 4.1 Strategy Ensemble versus Signal Ensemble

Phase 61 combines **signal values** at aligned (entity, timestamp) keys.
A Strategy Ensemble Builder combines **strategy return streams**. The
following strategy-level functions are absent today:

| Function | Present? | Nearest existing infrastructure |
|---|---|---|
| Strategy return-stream alignment (different calendars, start dates, missing days) | **No** | `signal_ensemble/alignment.py` aligns signal values, not return series |
| Capital / risk allocation across strategies | **No** | `portfolio_diagnostics/` allocates across *assets* (ERC, min-var, inverse-vol) |
| Strategy-level turnover and rebalancing between strategies | **No** | `signal_decay/turnover.py` measures a bucket reference book |
| Drawdown / tail overlap between strategies | **No** | `portfolio_stress/` has drawdown attribution for one book |
| Walk-forward ensemble policies | **No** | `research/*` walk-forward is single-strategy SMA |
| Frozen held-out combination evaluation | Partly | Phase 52 splits + Phase 61 frozen-threshold pattern exist and are reusable |
| Portfolio constraints applied to an ensemble | **No** | `portfolio_diagnostics/constraints.py` exists for asset weights |
| Strategy contribution attribution | **No** | `portfolio_attribution/` attributes across assets/groups |

This is the single largest blueprint gap that current infrastructure can
close cleanly → **Phase 63** (selected, §6).

### 4.2 Unified ML research lifecycle

| Stage | Exists? | Where |
|---|---|---|
| dataset | Partly | `dataset_registry/` (declared metadata, versions, fingerprints) and `RawFuturesStore` — two unrelated systems |
| features | Yes | `backend/app/features/` (16 futures features, warmup-marked, no fill) |
| labels | Yes | `backend/app/labels/` (forward return, direction, vol-adjusted) and `finml/labeling.py` (triple barrier) — two unrelated implementations |
| training | Yes (narrow) | `backend/app/ml_signal/` — linear/logistic/dummy only |
| purged validation | Yes | `model_validation/` (purged K-fold, embargo, CPCV) and `finml/cv.py` — again two implementations |
| calibration | Yes (separate) | `meta_labeling/` (Platt/isotonic) — not wired to the ML loop |
| held-out predictions | Partly | the ML loop writes predictions to `ExperimentStore`; the labs consume caller-supplied probabilities |
| cost-aware evaluation | Yes (separate) | `cost_diagnostics/`, `signal_decay/costs.py` — not wired to the ML loop |
| model / artifact registry | **No** | `experiments/store.py` stores run directories; there is no model artifact identity, no environment manifest, no lineage from dataset → model → prediction |
| comparison | Partly | `experiment_catalog/` (CLI) and `experiment_registry/` (API/UI) are separate systems |

**Diagnosis:** the pieces exist but form two parallel islands — a
CLI/filesystem futures ML loop and an API/SQLite diagnostics chain —
with no shared identity. → **Phase 64**.

### 4.3 Replay by hash

| Requirement | State |
|---|---|
| config hash | **Built** — canonical JSON, documented normalization, CSV content folded in |
| dataset version | Partly — `dataset_registry` versions exist but do not enter the backtest config hash |
| exact run recreation | **Missing** — no endpoint or route resolves a hash back to a config or result; `saved_backtests` does not store `config_hash` |
| environment identity | **Missing** — no manifest of Python/Node/library versions attached to a run |
| artifact identity | Partly — `ExperimentStore` writes content-hashed artifacts; diagnostics labs use result fingerprints; nothing unifies them |
| replay routing | **Missing** — the UI states the hash "is not a public URL", which is accurate |

→ **Phase 65**.

### 4.4 Real research data (futures)

| Requirement | State |
|---|---|
| futures historical ingestion | **Built for local CSV** — validation, canonical schema, content hash, `RawFuturesStore` |
| point-in-time metadata | **Missing** — no as-of/vintage layer; corrections would silently overwrite |
| contract calendars | **Missing** — expiry math exists (third Friday), but there is no holiday/session calendar (a documented v1 simplification) |
| continuous-contract validation | Partly — ratio-adjusted stitching with documented roll rules and a days-before-expiry fallback exists and is tested; no cross-vendor or economic validation of the resulting series |
| licensing / provenance | **Missing** — `docs/DATA_PROVENANCE_POLICY.md` covers the price provider seam; no futures vendor licensing decision exists |
| correction / version policy | **Missing** — no restatement or re-ingest policy |

→ **Phase 67** (specification and contract first; no vendor integration).

### 4.5 Frontend quality

| Requirement | State |
|---|---|
| frontend unit / component tests | **None** — no test framework is installed for `frontend/src` (only Playwright e2e exists) |
| registry-versus-route drift tests | **None** — `modelRegistry.ts`, `paperRegistry.ts`, `disasterRegistry.ts` and the sidebar/view union can drift silently |
| accessibility | Partial — labelled controls, dark-theme contrast assertions and keyboard-focus conventions are enforced ad hoc inside e2e specs; no axe-style audit |
| performance | Not measured — no bundle-size or render budget |
| visual regression | Deliberately avoided — five frozen screenshots exist as release evidence, not as assertions (pixel tests are excluded by policy) |
| screenshot currency | **Stale** — `docs/screenshots/release_*.png` date from the v4.60 freeze; workspaces added since are not depicted (`docs/SCREENSHOT_CHECKLIST.md`) |

19 Playwright spec files / 254 chromium tests exist and are the only
frontend regression net. → **Phase 66**.

### 4.6 Deployment

| Requirement | State |
|---|---|
| hosted read-only demo | **Missing** (planned as a specification in Phase 70) |
| authentication | **Deferred** — explicitly not added; single-user by design |
| multi-user isolation | **Deferred** — one local SQLite file, no per-user scoping |
| backups | **Missing** |
| migration operations | Partly — `db.py` applies idempotent `CREATE TABLE IF NOT EXISTS` migrations; no versioned migration tool or rollback |
| monitoring | **Missing** |
| secret management | Partly — env-var documentation and a no-secrets-in-repo rule; no vault/rotation story |
| provider governance | Partly — opt-in, fail-closed, disabled-by-default adapters; no per-instance quota/abuse policy |

Authentication and multi-user hosting **remain deferred and are not
silently added by this phase**. → **Phase 70** (plan only).

## 5. Tag and version audit (neutral; nothing repaired)

`git tag` count: **124**. Verified targets:

| Phase | Implementation commit | Review commit | Expected tag | Observed state | Action required | Historical repair recommended? |
|---|---|---|---|---|---|---|
| Frozen demo baseline | — | — | `v4.60.0-public-release-candidate-demo-freeze-v1` | **Exists** → `7cf9708` | None (frozen; never move) | No |
| Public launch baseline | — | — | `v4.64.0-public-github-release-launch-v1` | **Exists** → `2d4bcfe` | None | No |
| 50.0 Model Validation | — | — | `v4.68.0-purged-cv-cpcv-model-validation-v1` | **Exists** → `18ab11b` | None | No |
| 51.0 Meta-Labeling | `2d9625b` | `3057a93` | `v4.69.0-…` | **Missing** (recorded deviation; work sits inside the `v4.70.0` history) | None — documented in `VERSION_MANIFEST.md` | **No** |
| 52.0 Feature Diagnostics | `64f56b7` | `96b9e32` | `v4.70.0-feature-importance-stability-drift-lab-v1` | **Exists** → `96b9e32` | None | No |
| 53.0 Overfitting | `2da0aa4` | `1989ecd` | `v4.71.0-…` | **Exists** | None | No |
| 54.0 Regime | `e99f788` | `e332f16` | `v4.72.0-…` | **Exists** | None | No |
| 55.0 Cost & Capacity | `eb21c4a` | `f3af7c2` | `v4.73.0-…` | **Exists** | None | No |
| 56.0 Portfolio Diagnostics | `6d54a2b` | `54ecabb` | `v4.74.0-…` | **Exists** | None | No |
| 57.0 Portfolio Stress | `a8b1476` | `b02be07` | `v4.75.0-…` | **Exists** | None | No |
| **58.0 Portfolio Attribution** | **`e354d76`** | **`ad8679e`** | **`v4.76.0-portfolio-performance-attribution-benchmark-diagnostics-v1`** | **MISSING — no v4.76 tag exists** | Record only | **No** |
| 59.0 Factor Diagnostics | `6273189` | `b281d15` | `v4.77.0-…` | **Exists** → `b281d15` | None | No |
| 60.0 Signal Decay | `1e15ab0` | `d726527` | `v4.78.0-…` | **Exists** → `d726527` | None | No |
| 61.0 Signal Ensemble | `c0f256d` | `40ec1fd` | `v4.79.0-…` | **Exists** → `40ec1fd` | None | No |
| 62.0 (this phase) | not yet committed | pending | `v4.80.0-master-blueprint-reconciliation-project-status-roadmap-v1` | Not created | User creates after review | n/a |

### 5.1 Phase 58 missing-tag finding

Phase 58's implementation (`e354d76`) and review (`ad8679e`) commits are
both on `main`, but `v4.76.0-portfolio-performance-attribution-benchmark-diagnostics-v1`
was never created. The version sequence therefore skips v4.76, exactly
as it skips v4.69.

**Recommendation: do not repair.** The repository's stated policy is
that tags are never moved or re-created, and both gaps are already
documented in `docs/VERSION_MANIFEST.md`. Creating a v4.76 tag now would
attach a "release" label months after the fact, out of chronological
order with the tags that followed it, which is worse for auditability
than a documented gap. This phase creates, moves and deletes **no
tags**.

## 6. Selected next phase: Phase 63

**Strategy Return Stream, Strategy Similarity and Portfolio Ensemble
Diagnostics Lab v1.**

Why it follows Phase 61 naturally:

1. Phase 61 combines signal VALUES; Phase 63 combines complete strategy
   RETURN STREAMS — the same discipline one level up.
2. It closes the largest genuine blueprint gap (area 15, §4.1): the
   Strategy Ensemble Builder has been listed as `research` since v3 of
   the blueprint and has no implementation.
3. It reuses existing infrastructure rather than inventing engines:
   Portfolio Diagnostics (allocation and constraints), Attribution
   (contribution reconciliation), Stress (drawdown attribution), Cost
   (turnover pricing), Regime (conditioning), Model Validation
   (train/held-out), Overfitting (multiple testing), Signal Decay and
   Signal Ensemble (alignment, redundancy, fingerprints, baselines,
   neutral comparison).
4. It needs no new dependency, no new data source and no new provider.

Full scope, non-scope, acceptance criteria and risks:
[`FORWARD_ROADMAP_PHASES_63_70.md`](FORWARD_ROADMAP_PHASES_63_70.md).
**Phase 63 was deliberately not started in this phase.**

## 7. Remaining uncertainties

- The ~100-model catalog remains undefined; any future percentage claim
  needs an enumerated list and a counting rule first (§3).
- Frontend registries have no tests, so the matrix's frontend evidence
  is file-verified but not regression-protected until Phase 66.
- The five frozen screenshots predate ~14 workspaces; they remain valid
  as release evidence for v4.60 but no longer depict the product.
- `CLAUDE.md` and `AGENTS.md` still carry early-phase operating
  instructions; this phase flags rather than rewrites them because they
  are the user's own instruction files.
