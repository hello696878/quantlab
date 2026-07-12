# QuantLab — Version Manifest (Phase 40.0)

The project's versioning conventions, verified against the local git history
when written. Companion docs: [`../CHANGELOG.md`](../CHANGELOG.md) (grouped
changelog) · [`MILESTONE_HISTORY.md`](MILESTONE_HISTORY.md) ·
[`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md) ·
[`RELEASE_NOTES_TEMPLATE.md`](RELEASE_NOTES_TEMPLATE.md) ·
[`PROJECT_SNAPSHOT.md`](PROJECT_SNAPSHOT.md).

> Version labels are **project milestone labels**, not package publications.
> No entry here claims a public release, production certification, or
> anything about live trading.

## 1. Current version label

**`4.63.0-dev`** (see the repo-root [`VERSION`](../VERSION) file). The next
expected tag on completion of the current phase's review is
`v4.63.0-manual-ci-browser-e2e-evidence-v1` — "expected" because tags are
created by the user after review, never automatically.

## 2. Release family

The **v4.x productization / platformization series**: v4.0.0 (local-first
research terminal) → v4.7.0 (showcase candidate) → v4.8+ (one milestone tag
per feature phase). 109 local tags existed when this manifest was last
updated (Phase 45.0); the latest verified tag is
`v4.62.0-public-release-package-demo-asset-kit-v1` (the frozen
release-candidate tag is
`v4.60.0-public-release-candidate-demo-freeze-v1`).

## 3. Major release areas

- **Quant research labs** — portfolio/macro, derivatives/volatility/futures,
  crypto/DeFi/on-chain/alt-data, microstructure, real assets/credit, rates/FX.
- **Product workflow layers** — Scenario Studio, Research Workspace,
  Demo Center, Portfolio Showcase.
- **Reliability / QA layers** — Data Reliability Center, QA Command Center.
- **Public portfolio docs** — launch pack, summaries, demo/video scripts.
- **Developer onboarding** — local demo guide, environment doctor, helper
  scripts, release management (this phase).

## 4. Versioning policy (as practiced in this repo)

1. Each feature phase lands as an **`Add <feature> v1`** commit.
2. A review pass lands as a **`Review <feature> v1`** commit.
3. The user tags **after review** and pushes the tag manually.
4. The frontend production build is **run locally by the user** — it is not
   part of any automated step in this repo (CI additionally builds the
   frontend on push, which is separate from the local release flow).

## 5. Tag naming convention (verified)

`v4.xx.0-short-feature-name-v1` — e.g.
`v4.54.0-qa-command-center-release-readiness-v1`. Early-series tags
(`v4.5.0-data-provider-quality`, `v4.7.0-showcase`) predate the `-v1` suffix.

## 6. Commit naming convention (verified)

`Add <feature> v1` followed by `Review <feature> v1` — visible throughout
`git log --oneline`.

## 7. What a review tag means

- The code was reviewed via the project's review prompt flow.
- Backend tests and the frontend typecheck are **expected to have been run**
  during the phase and review (each phase's ROADMAP entry records the actual
  counts when they were run).
- The frontend production build remains **user-run** unless a phase's notes
  explicitly state otherwise.

## 8. What a review tag does NOT mean

- Not a production certification of any kind.
- Not a compliance or risk certification.
- Not live-trading readiness — QuantLab has no trading capability at all.
- Not investment advice, and not a claim that any model output is calibrated
  to markets.

## 9. Release safety checklist (summary)

Before tagging (full version in [`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md)):

- [ ] Backend suite run locally and green; `artifacts\` absent afterwards.
- [ ] `npx tsc --noEmit` clean; `npm run build` run locally by the user.
- [ ] No secrets/keys, no telemetry, no live-data or production overclaims
      introduced (see the safety searches in the checklist).
- [ ] CHANGELOG "Unreleased" moved under the new version heading; `VERSION`
      bumped; docs cross-links intact.
