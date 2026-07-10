# Contributing to QuantLab

QuantLab is a local-first, deterministic, **educational** quant research
platform. Contributions should preserve exactly that: no live data, no
trading, no telemetry, no secrets, and honest labeling everywhere. This
guide is the practical version; the deep dives are
[`docs/DEVELOPER_ONBOARDING.md`](docs/DEVELOPER_ONBOARDING.md) (architecture
+ the add-a-lab checklist), [`docs/REPOSITORY_HYGIENE.md`](docs/REPOSITORY_HYGIENE.md),
[`docs/SECURITY_AND_SECRETS.md`](docs/SECURITY_AND_SECRETS.md), and
[`docs/CI.md`](docs/CI.md).

## Scope

In scope: deterministic educational labs (strict `sample`/`analyze` API
pattern), product/QA/reliability layers, docs, tests, UX polish.
Out of scope: live market feeds as requirements, broker/exchange/wallet
integration, trading, telemetry, login/cloud, secrets, and anything that
turns an educational label into a production claim.

## Local setup

```powershell
# Backend (venv lives at backend\venv)
cd C:\quantlab\backend
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\uvicorn app.main:app --reload --port 8000

# Frontend
cd C:\quantlab\frontend
npm install
npm run dev
```

Environment check: `.\scripts\check_environment.ps1` (read-only). Common
issues: [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md).

## Verify your change

```powershell
# Backend tests — deterministic and offline; never depend on a live provider
cd C:\quantlab
if (Test-Path .\artifacts) { Remove-Item -Recurse -Force .\artifacts }
backend\venv\Scripts\python.exe -m pytest backend\tests -q

# Frontend typecheck — strict TypeScript, avoid `any`
cd C:\quantlab\frontend
npx tsc --noEmit

# Production build — run locally before calling a change done
npm run build
```

`artifacts\` must not exist after the test run. CI (backend tests +
typecheck + build) runs on push, but CI green does not replace running the
checks yourself.

## Adding a deterministic lab

Follow the 9-step checklist in
[`docs/DEVELOPER_ONBOARDING.md`](docs/DEVELOPER_ONBOARDING.md) §5. The short
version: strict Pydantic models (finite floats, `Literal` enums), hand-written
`sample.py` with a `DISCLAIMER`, pure `service.py` (guard every division,
clip every score), router + `include_router`, tests (endpoints, formula
spot-checks, validation rejections, an all-finite payload walk, wording
contracts), typed frontend client + panel, the four navigation wiring points,
and docs (ROADMAP entry + LIMITATIONS paragraph).

## Adding docs

Every feature phase updates `docs/ROADMAP.md` (what was built and what was
actually run) and `docs/LIMITATIONS.md` (an honest paragraph about what the
feature is *not*). Keep README public-facing and concise.

## Writing safe copy (non-negotiable)

- No investment/trading/allocation/legal/tax/compliance/risk advice — and no
  recommendation wording in generated reports (it's enforced by tests).
- No live-data or availability guarantees; label sample data as sample data.
- No production trading/risk/compliance claims; version tags and CI green
  are milestones, not certifications.
- Never claim tests or builds ran unless they actually ran — record real
  counts.
- No fake metrics, users, customers, or revenue.

## Pull request checklist

- [ ] Backend suite green locally (real count noted); `artifacts\` absent after.
- [ ] `npx tsc --noEmit` exit 0; `npm run build` run locally.
- [ ] New behavior has tests (including validation and finiteness where applicable).
- [ ] ROADMAP + LIMITATIONS updated; README/doc links intact.
- [ ] No secrets/keys (`docs/SECURITY_AND_SECRETS.md` search comes back clean).
- [ ] No new dependencies unless justified; no telemetry, no network calls.
- [ ] Safe-copy rules above respected in UI text, docs, and generated output.

## Commit convention

Small, tested change sets on `main`: **`Add <feature> v1`** then
**`Review <feature> v1`**; the maintainer tags after review as
`v4.xx.0-short-feature-name-v1` (see
[`docs/VERSION_MANIFEST.md`](docs/VERSION_MANIFEST.md)).

## Secrets

There are none, and contributions must not introduce any — the platform is
designed to run with zero credentials. See
[`docs/SECURITY_AND_SECRETS.md`](docs/SECURITY_AND_SECRETS.md), including
what to do if one is committed accidentally (rotate first).
