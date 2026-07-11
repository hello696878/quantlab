# QuantLab — Public Launch Readiness (Phase 42.0)

The final go / no-go review before making the repo public and sharing it.

> **Scope:** this is **public portfolio readiness only** — is the project
> presentable, honest, and verifiable as a portfolio piece? It is **not a
> production certification** of any kind: not trading readiness, not
> compliance readiness, not hosting readiness
> ([`DEPLOYMENT_READINESS.md`](DEPLOYMENT_READINESS.md) covers what a hosted
> demo would still need).

Work through the ten areas, then fill in the decision table in §12.

## 1. GitHub readiness

- Repo history reviewed with [`REPOSITORY_HYGIENE.md`](REPOSITORY_HYGIENE.md)
  §go-public checklist (no secrets, no generated artifacts, no oversized
  files).
- Default branch is `main`; latest commit is the reviewed, tagged one.
- CI badge/workflow state matches reality — a green run **observed**, not
  assumed ([`CI.md`](CI.md)).

## 2. README readiness

- Reads correctly to a stranger in the first 30 seconds: what it is
  (educational quant research platform), what it is not (ground-rules
  blockquote), how to run it.
- Quick-start commands verified on this machine; test counts match the last
  real run.

## 3. Docs readiness

- The "Project docs" list resolves end to end.
- [`ROADMAP.md`](ROADMAP.md) and [`LIMITATIONS.md`](LIMITATIONS.md) include
  the current phase; [`PROJECT_SNAPSHOT.md`](PROJECT_SNAPSHOT.md) facts spot-
  checked.

## 4. Demo readiness

- Full smoke pass done ([`FINAL_SMOKE_TEST_RUNBOOK.md`](FINAL_SMOKE_TEST_RUNBOOK.md)).
- Demo freeze recorded ([`DEMO_FREEZE_CHECKLIST.md`](DEMO_FREEZE_CHECKLIST.md)).
- At least one timed rehearsal of [`FINAL_DEMO_SCRIPT.md`](FINAL_DEMO_SCRIPT.md).

## 5. Screenshot readiness

- [`SCREENSHOT_CHECKLIST.md`](SCREENSHOT_CHECKLIST.md) captures complete, at
  the frozen commit, error-free, consistently sized.

## 6. LinkedIn readiness

- Chosen draft from [`LINKEDIN_POST_DRAFTS.md`](LINKEDIN_POST_DRAFTS.md)
  fact-checked against [`KNOWN_LIMITATIONS_PUBLIC.md`](KNOWN_LIMITATIONS_PUBLIC.md).
- No metric in the post that a repo reader couldn't verify.

## 7. Interview readiness

- [`INTERVIEW_TALKING_POINTS.md`](INTERVIEW_TALKING_POINTS.md) reviewed; you
  can answer "what would it take to trade this?" honestly (answer: it
  doesn't trade, and that's deliberate — see the limitations docs).

## 8. CI readiness

- Latest push to `main` is green on GitHub Actions — **observed on the
  Actions tab**, with the run link/date noted as evidence.
- You can state what CI does and does not check ([`CI.md`](CI.md)): a
  preflight signal, not a certification.

## 9. Security / secrets readiness

- Publishing-time secret search from
  [`SECURITY_AND_SECRETS.md`](SECURITY_AND_SECRETS.md) run and clean.
- No `.env` files tracked; the optional local FRED key (if you ever set one)
  confirmed absent from the repo and history spot-checks.

## 10. Limitations readiness

- [`KNOWN_LIMITATIONS_PUBLIC.md`](KNOWN_LIMITATIONS_PUBLIC.md) is current and
  linked from wherever the project is shared.
- Nothing in the README, showcase page, or posts contradicts it.

## 11. Final user-run checks (the non-negotiables)

Run all three and record real results before flipping the repo public:

```powershell
cd C:\quantlab
if (Test-Path .\artifacts) { Remove-Item -Recurse -Force .\artifacts }
backend\venv\Scripts\python.exe -m pytest backend\tests -q

cd C:\quantlab\frontend
npx tsc --noEmit
npm run build   # always user-run
```

## 12. Launch decision table

One row per area; the only honest statuses are **Ready**, **Needs fix**, and
**Defer** (consciously postponed, with a note — e.g. hosted demo).

| # | Area | Status (Ready / Needs fix / Defer) | Notes / evidence |
|---|---|---|---|
| 1 | GitHub | | |
| 2 | README | | |
| 3 | Docs | | |
| 4 | Demo | | |
| 5 | Screenshots | | |
| 6 | LinkedIn | | |
| 7 | Interview | | |
| 8 | CI | | |
| 9 | Security/secrets | | |
| 10 | Limitations | | |
| 11 | Final user-run checks | | |

**Launch rule:** every row Ready or an explicitly noted Defer → share.
Any "Needs fix" → fix first. There is no "close enough" for the security
row or the final-checks row.

## Ground rules (unchanged by this doc)

Deterministic educational sample data; no live trading; not investment
advice; not production trading, risk, or compliance infrastructure. Public
portfolio readiness only.
