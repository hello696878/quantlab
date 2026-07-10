# QuantLab — Release Notes Template (Phase 40.0)

Copy this file's skeleton for each milestone tag. The three verification
distinctions are load-bearing — never blur them:

- **"Tests actually run"** — you ran them; record the real count and result.
- **"Tests expected"** — conventions say they should be run; you did not run
  them in this pass, and the notes must say so.
- **"Frontend build user-run"** — `npm run build` is always a local user
  step; state whether you ran it and what happened, or that it is pending.

---

```markdown
# QuantLab <version tag> — <Release Title>

**Tag:** v4.xx.0-<short-feature-name>-v1
**Commits:** Add <feature> v1 · Review <feature> v1

## Summary

<2–4 sentences: what this milestone adds and why. No hype; deterministic
educational sample data; no live-data or production claims.>

## Highlights

- <the 2–4 things a reader should look at first>

## Added

- <new modules/endpoints/docs/scripts>

## Changed

- <behavior or copy changes to existing modules>

## Fixed

- <bugs fixed, drift corrected — say how each was verified>

## Documentation

- <docs added/updated: ROADMAP entry, LIMITATIONS paragraph, READMEs, …>

## Tests / checks actually run

- Backend suite: `backend\venv\Scripts\python.exe -m pytest backend\tests -q`
  → **<N> passed** on <your machine, date>; `artifacts\` absent afterwards.
- Frontend typecheck: `npx tsc --noEmit` → exit <0/…>.
- <anything you did NOT run goes under "expected", below — not here.>

## Checks expected but not run in this pass

- <e.g. "frontend production build — pending user run", or "none">

## Frontend build status

- `npm run build` (user-run): <run locally on <date>: succeeded / pending>.

## Known limitations

- <link the relevant docs/LIMITATIONS.md paragraphs; add anything new>

## Data mode / safety notes

- Deterministic static sample / user-input data; optional external providers
  disabled by default and fail closed; never relied on in tests.
- Educational only — not investment, trading, allocation, legal, tax,
  compliance, or risk-management advice; no live trading; not production
  trading, risk, or compliance infrastructure.

## Manual demo checklist

- [ ] <the 3–6 clicks that prove this milestone works, from the phase's
      manual-testing guidance>

## Rollback notes

- Single-commit-pair milestone: `git revert` the Review and Add commits (or
  reset a local branch to the previous tag `v4.<xx-1>.0-…`). No migrations;
  saved-work SQLite is unaffected unless the notes say otherwise.

## Next release candidates

- <1–3 follow-ups from the phase report's "next recommended tiny step">
```
