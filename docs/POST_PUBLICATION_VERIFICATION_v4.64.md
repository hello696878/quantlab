# Post-Publication Verification — v4.64 (Phase 47.0)

Item-by-item verification results, each with expected/observed/result/source
and corrective action where failed. All observations 2026-07-12, read-only
(local git, `git ls-remote`, unauthenticated GitHub REST GETs; `gh` CLI not
installed). Nothing here was marked passed without evidence.

| # | Item | Expected | Observed | Result | Evidence source | Corrective action |
|---|---|---|---|---|---|---|
| 1 | Local v4.64 tag | exists, targets the release commit | lightweight tag → `2d4bcfe` ("Add public GitHub release launch closure v1"), ancestor of `main` (merge-base exit 0) | ✅ PASS | `git rev-list`, `git cat-file -t` | — |
| 2 | Remote v4.64 tag | exists, matches local | `2d4bcfe` — identical; no divergence | ✅ PASS | `git ls-remote --tags origin` | — |
| 3 | Release existence | published release at the tag | **no published v4.64 release**; only historical `v4.0.0` is published (an invisible draft, if any, is not publication) | ❌ FAIL | REST GET `/releases/tags/…` → 404; `/releases` list | User: launch-checklist runbook steps 16–26 — publish manually |
| 4 | Draft/prerelease status | published, non-draft, prerelease per intent | not verifiable — no release | ⏸ PENDING | blocked by #3 | verify after publication |
| 5 | Release title | "QuantLab v4.64.0 — Public Research Platform Release with Browser E2E Evidence" | not verifiable — no release | ⏸ PENDING | blocked by #3 | copy from `GITHUB_RELEASE_FINAL_v4.64.md` |
| 6 | Release URL | real `hello696878/quantlab` releases URL | none exists | ⏸ PENDING | blocked by #3 | record in a later evidence commit |
| 7 | Release-body consistency vs tracked draft | material statements match | not verifiable — no release body | ⏸ PENDING | blocked by #3 | compare after publication (checklist §13) |
| 8 | Normal CI on release commit | green push run on `2d4bcfe` | run **29188597089** — success; Backend Tests ✅ Frontend Build ✅ | ✅ PASS | REST GET runs?head_sha=… | — |
| 9 | Browser E2E Preflight on release commit | green `workflow_dispatch` run on `2d4bcfe` | run **29193708980** — success; all steps ✅ incl. full Playwright suite | ✅ PASS | REST GET runs + jobs | — |
| 10 | Artifact existence | evidence artifact on that run | `browser-e2e-evidence-29193708980`, 212,110 B, not expired, expires 2026-07-26 | ✅ PASS | REST GET artifacts (metadata; contents not downloaded) | user: download + inspect logs/report (checklist §§6–9) |
| 11 | Screenshot integrity | five frozen PNGs match freeze-record SHA-256 | all five match; `git diff -- docs/screenshots` empty | ✅ PASS | sha256sum vs freeze record | — |
| 12 | Checksum integrity | both manifests verify, exit 0 | release manifest 14/14 OK; post-publication manifest verified after creation (counts in Phase 47 report) | ✅ PASS | `verify_release_checksums.py` runs | — |
| 13 | README links | relative links/images resolve | 0 broken relative links (README + release docs re-checked) | ✅ PASS | stdlib link check | — |
| 14 | Release-document links | new v4.64 docs' links resolve | 0 broken relative links | ✅ PASS | stdlib link check | — |
| 15 | Logged-out accessibility | release page reachable logged-out | not verifiable — no release; repository API itself is publicly readable (unauthenticated GETs succeeded) | ⏸ PENDING | blocked by #3 | checklist §21 after publication |
| 16 | Secrets review | no credential-shaped material | scan clean — names/warnings only | ✅ PASS | Phase 47 secret scan | — |
| 17 | Overclaim review | negations/limitations only | scan clean | ✅ PASS | Phase 47 overclaim scan | — |
| 18 | Generated-artifact hygiene | none staged/committed | tree contains only Phase 47 doc/tooling changes; no artifacts/logs/traces | ✅ PASS | `git status`, path grep | — |
| 19 | Current main state | clean, HEAD = tag target at start of phase | clean at start; HEAD `2d4bcfe` = v4.64 target = origin/main | ✅ PASS | `git status`, `git log` | — |
| 20 | Post-publication decision | VERIFIED PUBLISHED RELEASE | **PUBLICATION RECORD INCOMPLETE — BLOCKERS REMAIN** (single blocker: release not published) | ❌ blocked | this table | publish, then re-verify #3–#7, #15 |

## Convention notes (recorded, not repaired)

- No Phase 46 review commit exists; the v4.64 tag was placed directly on the
  implementation commit `2d4bcfe` (same pattern as v4.63). Tags are never
  moved; recorded as-is.
- The v4.63 tag target additionally contains unrelated Phase 12 catalog work
  (recorded in the v4.64 evidence ledger).

## Ground rules (unchanged by this doc)

Read-only verification only — nothing was created, edited, triggered,
tagged, pushed, or published during this phase.
