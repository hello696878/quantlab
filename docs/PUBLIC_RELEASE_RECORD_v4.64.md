# QuantLab v4.64 Public Release Record

Factual publication evidence only (Phase 47.0). Every value below is either
verified by read-only inspection (local git, `git ls-remote`, unauthenticated
GitHub REST GETs on 2026-07-12) or explicitly marked pending. Companion:
[`POST_PUBLICATION_VERIFICATION_v4.64.md`](POST_PUBLICATION_VERIFICATION_v4.64.md).

## Release identity

| Field | Value |
|---|---|
| Release name | **Pending — not verified** (no published v4.64 release exists; intended title: "QuantLab v4.64.0 — Public Research Platform Release with Browser E2E Evidence") |
| Release tag | `v4.64.0-public-github-release-launch-v1` (tag exists; release does not) |
| Release URL | **Pending — not verified** (the repository's only published release is the historical `v4.0.0`) |
| Published timestamp | **Pending — not verified** |
| Draft status | **Pending — not verified** (an unpublished draft, if any, is invisible to unauthenticated read-only inspection; a draft is not publication) |
| Prerelease status | **Pending — not verified** |
| Local tag target | `2d4bcfeb218dfee758b908032eef198e305fbc4f` (lightweight tag) |
| Remote tag target | `2d4bcfeb218dfee758b908032eef198e305fbc4f` — identical to local; no divergence |
| Release commit SHA | `2d4bcfe` — ancestor of `main` (merge-base check exit 0); HEAD at verification time |
| Release commit message | `Add public GitHub release launch closure v1` (2026-07-12; the Phase 46 implementation commit — no separate Phase 46 review commit exists) |

## Release lineage

| Milestone | Tag | Target commit | Status |
|---|---|---|---|
| Frozen public demo | `v4.60.0-public-release-candidate-demo-freeze-v1` | `7cf9708` | verified local + remote (annotated) |
| Browser E2E guard | `v4.61.0-browser-e2e-regression-guard-v1` | `32c8f35` | verified local + remote |
| Public release package | `v4.62.0-public-release-package-demo-asset-kit-v1` | `f2d8831` | verified local + remote |
| Manual CI browser E2E | `v4.63.0-manual-ci-browser-e2e-evidence-v1` | `47bfec0` | verified local + remote (tag includes unrelated Phase 12 catalog work; no Phase 45 review commit — recorded) |
| Public release launch | `v4.64.0-public-github-release-launch-v1` | `2d4bcfe` | tag verified local + remote; **GitHub Release not published** |

## Normal CI evidence (observed 2026-07-12, read-only)

| Field | Value |
|---|---|
| Workflow | CI |
| Run ID | 29188597089 |
| Commit | `2d4bcfe` (the v4.64 tag target, exactly) |
| Event / conclusion | push / **success** |
| Jobs | Backend Tests ✅ · Frontend Build ✅ |
| Run URL | https://github.com/hello696878/quantlab/actions/runs/29188597089 |

## Browser E2E Preflight evidence (observed 2026-07-12, read-only)

| Field | Value |
|---|---|
| Run ID | 29193708980 |
| Commit | `2d4bcfe` (the v4.64 tag target, exactly) |
| Event / conclusion | workflow_dispatch / **success** |
| Steps | all ✅: dependency installs (backend pip, `npm ci`, Playwright Chromium), backend tests, TypeScript check, production build, backend + frontend startup, both readiness waits, **Run Playwright browser E2E suite**, evidence upload (diagnostics correctly skipped) |
| Artifact | `browser-e2e-evidence-29193708980` — 212,110 bytes, not expired, expires 2026-07-26 (metadata inspected read-only; contents not downloaded — user inspection step remains open in the launch checklist) |
| Run URL | https://github.com/hello696878/quantlab/actions/runs/29193708980 |

## Local validation evidence (recorded runs with sources)

| Check | Result | Source | Date |
|---|---|---|---|
| Backend suite | 3,062 passed, exit 0 (615s) | Phase 46.0 run (ROADMAP) | 2026-07-12 |
| Frontend typecheck | exit 0 | Phase 46.0/47.0 runs | 2026-07-12 |
| Production build | exit 0, no warnings | freeze record (Phase 42.2) | 2026-07-11 |
| Production browser smoke | PASS, 37 views | BROWSER_SMOKE_TEST_REPORT | 2026-07-11 |
| Local Playwright E2E | 12 passed, exit 0 | Phase 46.0 run | 2026-07-12 |
| Checksum manifests | verified, exit 0 | Phase 46.0/47.0 runs | 2026-07-12 |

## Release assets

Final release notes (`GITHUB_RELEASE_FINAL_v4.64.md`) · evidence ledger
(`RELEASE_EVIDENCE_v4.64.md`) · launch checklist
(`PUBLIC_GITHUB_LAUNCH_CHECKLIST.md`) · checksum manifests
(`RELEASE_CHECKSUMS_v4.64.sha256`, `POST_PUBLICATION_CHECKSUMS_v4.64.sha256`)
· the five frozen screenshots (`docs/screenshots/release_*.png`, SHA-256
re-verified this phase) · browser smoke report · Browser E2E docs
(`BROWSER_E2E_RUNBOOK.md`, `CI_BROWSER_E2E.md`).

## Limitations (unchanged, repeated for the record)

Not investment advice · not production trading · no order execution · not a
compliance certification · not a security certification · E2E/CI green is a
regression signal on a specific commit · deterministic/sample data where
documented · local-first, no SLA or availability guarantee.

## Publication verification decision

**PUBLICATION RECORD INCOMPLETE — BLOCKERS REMAIN**

Verified: the tag (local = remote, on `main`), green CI, green Browser E2E
Preflight with an unexpired evidence artifact — everything the launch
checklist requires *before* publication. Blocker: **the GitHub Release
itself has not been published** (steps 16–26 of the launch-checklist
runbook). This record flips to VERIFIED PUBLISHED RELEASE only in a later
evidence commit that records the real release URL and published timestamp.
