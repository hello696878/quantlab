# Release Evidence Ledger — v4.64.0 (Phase 46.0)

The evidence ledger for the public GitHub release — facts only, no
promotional copy. Every row is either a recorded repository fact, an
observed remote run (read-only API inspection, 2026-07-12), or explicitly
marked pending. Companion: [`GITHUB_RELEASE_FINAL_v4.64.md`](GITHUB_RELEASE_FINAL_v4.64.md) ·
[`PUBLIC_GITHUB_LAUNCH_CHECKLIST.md`](PUBLIC_GITHUB_LAUNCH_CHECKLIST.md).

## A. Repository state

| Field | Value |
|---|---|
| Target version | 4.64.0 |
| Target tag | `v4.64.0-public-github-release-launch-v1` — **exists**, local = remote → `2d4bcfe` (verified Phase 47.0) |
| Release commit | `2d4bcfe` "Add public GitHub release launch closure v1" — the implementation commit was tagged directly (no separate Phase 46 review commit exists; recorded) |
| Branch | `main` |
| Frozen predecessor tag | `v4.60.0-public-release-candidate-demo-freeze-v1` → `7cf9708` |
| E2E-guard predecessor tag | `v4.61.0-browser-e2e-regression-guard-v1` → `32c8f35` |
| Release-package predecessor tag | `v4.62.0-public-release-package-demo-asset-kit-v1` → `f2d8831` |
| Manual-CI predecessor tag | `v4.63.0-manual-ci-browser-e2e-evidence-v1` → `47bfec0` |

Note on v4.63: no commit named "Review manual ci browser e2e evidence
workflow v1" exists — the tag was placed on `47bfec0` ("Add Phase 12 e2e
catalog test and as-built docs"), which sits above the Phase 45
implementation commit `414f40a` and also contains unrelated Phase 12
futures-catalog work. Both CI workflows are green on that exact commit
(section D), so the tag target is verified; the review-commit convention
was skipped for that phase. Recorded as-is; the tag was not modified.

## B. Frozen evidence (v4.60 — never regenerated)

| Item | Location | Status |
|---|---|---|
| Freeze tag | `v4.60.0-…` → `7cf9708ec542708cdd6f604064d32001b26ce2c7` | verified locally + on remote |
| Evidence commit | `7cf9708` (freeze record + five screenshots) | verified |
| Five screenshots | `docs/screenshots/release_*.png` | SHA-256 re-verified this phase — all match the freeze record |
| Browser smoke report | `docs/BROWSER_SMOKE_TEST_REPORT.md` | frozen record + addenda |
| Demo freeze checklist | `docs/DEMO_FREEZE_CHECKLIST.md` §1 | completed record, untouched |
| Final smoke runbook | `docs/FINAL_SMOKE_TEST_RUNBOOK.md` | living procedure |

## C. Local validation evidence

| Check | Command | Observed result | Source | Date | Re-run before release? |
|---|---|---|---|---|---|
| Backend suite | `backend\venv\Scripts\python.exe -m pytest backend\tests -q` | 3,062 passed, exit 0 (615s; includes Phase 12 catalog tests + 8 checksum-verifier tests) | Phase 46.0 run | 2026-07-12 | Yes |
| Backend suite (freeze) | same | 2,968 passed, exit 0 | freeze record | 2026-07-11 | superseded by above |
| Frontend typecheck | `npx tsc --noEmit` | exit 0 | Phase 46.0 run | 2026-07-12 | Yes |
| Production build | `npm run build` | exit 0, no warnings | freeze record (42.2) | 2026-07-11 | Yes (user-run) |
| Production browser smoke | manual runbook pass | PASS, 37 views | BROWSER_SMOKE_TEST_REPORT | 2026-07-11 | recommended |
| Local Playwright E2E | `npx playwright test --project=chromium` | 12 passed, exit 0 (1.1m, dev base URL) | Phase 46.0 run | 2026-07-12 | Yes if servers available |
| E2E discovery | `npx playwright test --list --project=chromium` | 12 tests in 4 files | Phase 46.0 run | 2026-07-12 | Yes |
| Checksum manifest | `python scripts/verify_release_checksums.py docs/RELEASE_CHECKSUMS_v4.64.sha256` | 14 file(s) verified, exit 0 | Phase 46.0 run | 2026-07-12 | Yes |

## D. Remote validation evidence (observed via read-only API, 2026-07-12)

| Workflow | Run ID | Commit | Conclusion | Key steps | Artifact | Source |
|---|---|---|---|---|---|---|
| CI | 29141440276 | `c059c4e` | success | Backend Tests ✅ Frontend Build ✅ | — | recorded (Phase 42.3) + docs |
| CI | 29147666495 | `7cf9708` | success | Backend Tests ✅ Frontend Build ✅ | — | recorded (Phase 42.4) + docs |
| CI | 29185696068 | `47bfec0` | success | Backend Tests ✅ Frontend Build ✅ | — | observed this phase |
| Browser E2E Preflight | 29185725247 | `47bfec0` | success | all 16 steps ✅ (backend tests, typecheck, build, both readiness waits, full Playwright suite, evidence upload; diagnostics skipped) | `browser-e2e-evidence-29185725247` (212,058 B, expires 2026-07-26) | observed this phase (`workflow_dispatch`) |

Remote evidence for the **v4.64 release commit `2d4bcfe`** (observed
2026-07-12, read-only — Phase 47.0):

| Workflow | Run ID | Commit | Conclusion | Key steps | Artifact |
|---|---|---|---|---|---|
| CI | 29188597089 | `2d4bcfe` | **success** | Backend Tests ✅ Frontend Build ✅ | — |
| Browser E2E Preflight | 29193708980 | `2d4bcfe` | **success** | all steps ✅ incl. full Playwright suite + evidence upload | `browser-e2e-evidence-29193708980` (212,110 B, expires 2026-07-26) |

## E. Integrity checks (this phase)

| Check | Result |
|---|---|
| Frozen screenshot hashes | all five match the freeze-record SHA-256 (re-computed this phase) |
| Release file hashes | `docs/RELEASE_CHECKSUMS_v4.64.sha256` — generated after final edits; verifier exit recorded in the Phase 46 report |
| `git status` | working tree contains only the intended Phase 46 files at report time |
| Tag target verification | v4.60→`7cf9708`, v4.61→`32c8f35`, v4.62→`f2d8831`, v4.63→`47bfec0` — local and remote agree; none modified |
| Generated-artifact hygiene | no `artifacts/**`, traces, reports, logs, node_modules, or `.next` in the diff |
| Secret scan | no credential-shaped material (documented env-var *names* only) |
| Overclaim scan | negations/policy text only |

## F. Release-blocking conditions

Publication is blocked while ANY of these hold:

- [ ] Dirty worktree at tagging time.
- [ ] Normal CI not green on the final review commit.
- [ ] Browser E2E Preflight not green on the final review commit (the
      `47bfec0` run does not transfer to later commits).
- [ ] Evidence artifact missing/expired without a replacement run.
- [ ] Any frozen screenshot hash mismatch (hard blocker — investigate, never
      re-capture).
- [ ] `verify_release_checksums.py` non-zero.
- [ ] Secret-like material found anywhere.
- [ ] Generated artifacts staged/committed.
- [ ] Release notes contradicting the evidence in this ledger.
- [ ] Unresolved test failures (backend, typecheck, or E2E).

## G. Final release decision (updated Phase 47.0)

**READY FOR MANUAL PUBLICATION** — the three original blockers cleared:

1. ~~Review commit~~ → the release commit exists: `2d4bcfe` (the
   implementation commit was tagged directly; convention deviation
   recorded in §A).
2. ~~Green runs on that commit~~ → CI 29188597089 ✅ and Browser E2E
   Preflight 29193708980 ✅, both observed on `2d4bcfe`.
3. ~~Tag~~ → `v4.64.0-public-github-release-launch-v1` exists, local =
   remote.

The remaining act is publication itself (launch-checklist runbook steps
16–26). **The GitHub Release is NOT yet published** — publication status is
tracked in [`PUBLIC_RELEASE_RECORD_v4.64.md`](PUBLIC_RELEASE_RECORD_v4.64.md),
which stays "PUBLICATION RECORD INCOMPLETE" until the real release URL and
timestamp are recorded.

## Ground rules (unchanged by this doc)

Facts and observed run IDs only; pending means pending. No release exists
until the user publishes it manually.
