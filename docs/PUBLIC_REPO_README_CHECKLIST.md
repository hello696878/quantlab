# Public Repo README Checklist (Phase 44.0)

A verification checklist for the repo README before (and right after) the
repository is shared publicly. This is a **checklist, not a rewrite** — the
README was rewritten for the public in Phase 38 and only needs link/claims
upkeep.

## 1. Title & one-liner

- [ ] Title says what it is in one line: interactive, local-first,
      **educational** quant research platform.
- [ ] The ground-rules blockquote (deterministic data, no live trading, not
      advice, not production infrastructure) sits directly under it.

## 2. Screenshot section

- [ ] At least one current screenshot near the top; captions match what is
      actually shown.
- [ ] Frozen release evidence (`docs/screenshots/release_*.png`) referenced
      where useful — never regenerated for cosmetics.
- [ ] `docs/screenshots/README.md` distinguishes the showcase set from the
      frozen release-evidence set.

## 3. Quickstart

- [ ] Backend + frontend startup commands are copy-paste correct for a
      fresh clone (venv path `backend\venv`, `npm install`, ports 8000/3000).
- [ ] Production build clearly labeled user-run.

## 4. Verification commands

- [ ] Backend pytest, `npx tsc --noEmit`, and `npm run e2e` all present,
      with the E2E servers-must-be-running caveat and runbook link.

## 5. Architecture

- [ ] A short text architecture description (FastAPI + Pydantic v2 /
      Next.js 14 + TS / SQLite / deterministic fixtures / fail-closed
      adapters) with a pointer to `docs/PROJECT_OVERVIEW.md`.

## 6. Feature map

- [ ] Major module groups listed and current (compare against the sidebar
      groups; ~40 workspaces claim still true).

## 7. Demo path

- [ ] The suggested demo path matches the frozen route (Showcase → Demo
      Center → Scenario Studio → Research Workspace → Data Reliability →
      QA → Release Notes) and the demo scripts.

## 8. Limitations

- [ ] Links to `docs/KNOWN_LIMITATIONS_PUBLIC.md` and `docs/LIMITATIONS.md`;
      the Data & safety section states: not advice, not a trading system,
      not production risk/compliance infrastructure.

## 9. Security / secrets

- [ ] Zero-secrets policy referenced (`docs/SECURITY_AND_SECRETS.md`); no
      env values, keys, or tokens anywhere in the README.

## 10. No-overclaims checklist

- [ ] No "production-ready", "institutional-grade", "audited", "certified".
- [ ] No user/customer/revenue claims.
- [ ] No performance/alpha claims; the losing pairs demo is described as
      deliberate honesty.
- [ ] Test counts match the latest **recorded** run (2,968 as of the v4.61
      freeze evidence) — update the number when you re-run, never round up.
- [ ] CI described as a preflight signal; E2E as a regression guard.

## 11. Links to docs

- [ ] Every entry in the README "Project docs" list resolves (click each on
      the GitHub rendering, not just locally).
- [ ] The public release package docs (release draft, LinkedIn post, case
      study, video scripts, asset manifest) are linked.

## 12. Before publishing

- [ ] `git status` clean; no generated artifacts tracked (`artifacts/`,
      `test-results/`, `playwright-report/`).
- [ ] Publishing-time secret search from `docs/SECURITY_AND_SECRETS.md` run
      and clean.
- [ ] Frozen tags intact (`v4.60.0-…`, `v4.61.0-…` — never force-updated).
- [ ] README renders correctly on GitHub (tables, code fences, images) at
      the commit being shared.

## Ground rules (unchanged by this doc)

The README's honesty is part of the product: public portfolio readiness
only — not investment advice, not production trading or compliance
infrastructure.
