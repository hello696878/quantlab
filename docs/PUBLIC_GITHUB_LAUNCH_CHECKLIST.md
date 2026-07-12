# Public GitHub Launch Checklist (Phase 46.0)

The gate between "the repo is ready" and "the release is published." Work
top to bottom; every box is a manual inspection by the user. Evidence ledger:
[`RELEASE_EVIDENCE_v4.64.md`](RELEASE_EVIDENCE_v4.64.md) · release text:
[`GITHUB_RELEASE_FINAL_v4.64.md`](GITHUB_RELEASE_FINAL_v4.64.md).

> Nothing in this checklist changes GitHub settings, repository visibility,
> tags, or releases — it tells you what to inspect and do yourself.

## 1. Repository cleanliness
- [ ] `git status --short` clean; `git status --ignored --short` shows only
      expected ignored paths (venvs, node_modules, `.next`, `artifacts/`).

## 2. Branch and commit verification
- [ ] On `main`, synced with `origin/main`; HEAD is the intended Phase 46
      review commit; note its SHA.

## 3. Required tags
- [ ] v4.60/v4.61/v4.62/v4.63 exist locally and remotely with the targets
      recorded in the evidence ledger (`git ls-remote --tags origin "v4.6*"`).
- [ ] `v4.64.0-public-github-release-launch-v1` — created only at step 20-adjacent
      runbook stage below, never before review.

## 4. Normal CI
- [ ] The push CI run on the release commit is green — record the run ID.

## 5. Browser E2E Preflight
- [ ] A `workflow_dispatch` run of **Browser E2E Preflight** on the release
      commit is green — record the run ID (the observed `47bfec0` run does
      not transfer to newer commits).

## 6. Artifact inspection
- [ ] Download `browser-e2e-evidence-<run id>` from that run; the Playwright
      HTML report opens and shows the expected suite results.

## 7. Backend log inspection
- [ ] `backend.log` in the artifact: normal uvicorn startup + request lines;
      no tracebacks, no secret-like values.

## 8. Frontend log inspection
- [ ] `frontend.log`: normal `next start` output; no errors, no secrets.

## 9. Playwright report inspection
- [ ] All specs present (frozen demo, scenario studio, pairs, responsive);
      zero failures; no unexpected skips.

## 10. Frozen screenshot integrity
- [ ] `git diff -- docs/screenshots` empty; SHA-256 of the five
      `release_*.png` match `DEMO_FREEZE_CHECKLIST.md` §1. Any mismatch is a
      hard blocker — investigate history, never re-capture.

## 11. Release checksum verification
- [ ] `python scripts/verify_release_checksums.py docs/RELEASE_CHECKSUMS_v4.64.sha256`
      → exit 0, all files OK.

## 12. README verification
- [ ] README renders on GitHub at the release commit: gallery images load,
      ground-rules block intact, all "Project docs" links resolve, test
      counts match the latest recorded run.

## 13. Release notes verification
- [ ] `GITHUB_RELEASE_FINAL_v4.64.md` cross-checked against the evidence
      ledger — every run ID, count, and tag matches; limitations section
      present.

## 14. Security and secret review
- [ ] Publishing-time secret search from `SECURITY_AND_SECRETS.md` clean on
      the tree; spot-check recent history.

## 15. Overclaim review
- [ ] The §13 overclaim search (Phase 46 spec pattern) returns only
      negations/policy text in public-facing docs.

## 16. GitHub repository visibility review
- [ ] Consciously confirm the intended visibility (public/private) in
      Settings — decide, don't drift. (This checklist never changes it.)

## 17. License review
- [ ] A LICENSE decision is made and the file (or its deliberate absence) is
      intentional; README/release notes don't promise a license that isn't
      there.

## 18. Issue/discussion settings review
- [ ] Issues/Discussions enabled or disabled deliberately; templates or a
      note about response expectations if enabled.

## 19. Demo asset review
- [ ] The five frozen screenshots are the ones you want public; optional
      extra captures per `SCREENSHOT_CHECKLIST.md` done or consciously
      deferred; no demo video is claimed anywhere unless actually recorded.

## 20. Manual GitHub Release creation
- [ ] Performed exactly per the runbook below — by hand.

## 21. Post-publication verification
- [ ] Open the release URL in a logged-out/private window: title, body,
      screenshots, tag, and limitations all correct.

## 22. Rollback/correction procedure
- [ ] If a factual error is found post-publication: edit the release body
      immediately (releases are editable); if the tag target is wrong,
      delete the RELEASE (not the tag history) and republish correctly —
      never force-move a tag; record the correction in the next evidence
      commit.

---

## Manual publication runbook (exact user actions)

1. `git pull` latest `main`.
2. Confirm clean worktree (`git status --short`).
3. Run the checksum verifier (§11) → exit 0.
4. Run backend tests → record count + exit 0.
5. Run `npx tsc --noEmit` → exit 0.
6. Run `npx playwright test --list --project=chromium` → suite discovered.
7. If backend+frontend are running: `npx playwright test --project=chromium`
   → green.
8. Confirm normal CI green on HEAD (Actions tab).
9. Trigger + confirm **Browser E2E Preflight** green on HEAD.
10. Record both run IDs (evidence ledger section D, "pending" row).
11. Download and inspect the CI evidence artifact (§§6–9).
12. Confirm no secret values in either log.
13. Confirm the release commit SHA one last time.
14. Create the tag per repo convention (annotated preferred; v4.60 is
    annotated, later tags were lightweight — either is acceptable, be
    deliberate): `git tag -a v4.64.0-public-github-release-launch-v1 -m "..."`.
15. `git push origin v4.64.0-public-github-release-launch-v1`.
16. GitHub → **Releases**.
17. **Draft a new release**.
18. Select tag `v4.64.0-public-github-release-launch-v1`.
19. Copy title + body from `GITHUB_RELEASE_FINAL_v4.64.md`.
20. Optionally attach selected frozen screenshots (they also render from the
    repo paths).
21. Confirm the limitations section survived the paste.
22. **Publish release** — manually.
23. Open the release in a logged-out/private window and inspect.
24. Verify README links and screenshots render at the tag.
25. Correct factual errors immediately if found (§22 above).
26. Record the final release URL in the docs in a later evidence commit —
    never pre-write it.

## Ground rules (unchanged by this doc)

Public portfolio publication only — not a production, security, compliance,
or trading certification; not investment advice.
