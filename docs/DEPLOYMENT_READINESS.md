# QuantLab — Deployment Readiness Notes (Phase 38.0)

An honest inventory of what exists for running QuantLab, and what a public
hosted deployment would still need. **Deployment is not complete and is not
claimed** — QuantLab is local-first today. No secrets or API keys live in
this repo, and none are added by this document.

---

## 1. Current local development setup

- **Backend:** FastAPI (Python 3.11) with a venv at `backend\venv`; local
  SQLite file for saved backtests/reports.
- **Frontend:** Next.js 14 + TypeScript; `/api/*` is rewritten to the backend
  (`next.config.js`), so no CORS setup is needed locally.
- **Containers:** `docker-compose.yml` brings up both services (frontend
  `:3000`, backend `:8000`).
- **CI:** `.github/workflows/ci.yml` runs backend tests and a frontend build
  on push/PR.

## 2. Environment assumptions

- Windows 11 + PowerShell is the primary dev environment (paths below use
  it); the code itself is OS-neutral Python/Node.
- Node 18+ and Python 3.11 available; no global Python packages required
  (the venv carries everything, including pytest).
- No network needed for any default demo or for the test suite.

## 3–6. The four user-run commands

```powershell
# Backend dev server
cd C:\quantlab\backend
venv\Scripts\uvicorn app.main:app --reload --port 8000

# Backend tests (from repo root)
cd C:\quantlab
backend\venv\Scripts\python.exe -m pytest backend\tests -q

# Frontend typecheck
cd C:\quantlab\frontend
npx tsc --noEmit

# Production build — run locally by the user
cd C:\quantlab\frontend
npm run build
```

These are listed, not run, by this document; the QA Command Center in-app
checklist mirrors them.

## 7. Environment variables review

- `BACKEND_URL` (frontend) — backend origin for the `/api/*` rewrite;
  defaults to `http://localhost:8000` (`frontend/.env.example`).
- `GLOBE_FRED_ENABLED` / `FRED_API_KEY` (backend, optional) — opt-in globe
  macro enrichment; **disabled by default**; the key is read from the
  environment, never committed, never sent to the frontend.
- `GLOBE_QUOTES_ENABLED` / `GLOBE_QUOTES_PROVIDER` (backend, optional) —
  opt-in delayed globe quotes; disabled by default; fails closed.
- `GLOBE_NEWS_ENABLED` (backend, optional) — the news scaffold stays static
  sample in every configuration; enabling it never fetches live news.
- No other secrets. Nothing in the repo requires an API key to run.

## 8. Static sample data notes

Every lab serves deterministic hand-written samples from its `GET /sample`
endpoint; analyses are pure functions of the validated request. The built-in
KO/PEP pairs demo has a network-free fixture. Saved work lives in a local
SQLite file (gitignored). Nothing claims to be live or current.

## 9. External provider caveats

yfinance (user-configured backtests + optional globe quotes) and FRED
(optional globe macro) are the only external providers. Both are optional
where optional, disabled by default where opt-in, fail closed to static
data, and are never relied on in tests. **Availability is never guaranteed**
— a hosted deployment must assume they can return nothing at any time.

## 10. Pre-deployment checklist (before any public hosting)

- [ ] Run the four commands above locally; record results honestly.
- [ ] Confirm `artifacts/` and `backend\tests\_tmp_normalized_futures` absent.
- [ ] Walk `docs/RELEASE_CHECKLIST.md` (manual QA) and the in-app QA Command
      Center smoke matrix.
- [ ] Re-read `README.md` + `docs/LIMITATIONS.md` for overclaims.
- [ ] Verify CI green on the deploy commit.
- [ ] Decide the SQLite story for hosting (see §12 — currently single-user).

## 11. Known limitations (deployment-relevant)

- Single-user by design: no auth, no sessions, no per-user data isolation —
  the SQLite saved-work store is shared by whoever reaches the instance.
- No rate limiting, request quotas, or abuse protection on the API.
- No monitoring/alerting/log aggregation (deliberately no telemetry).
- The backend allows arbitrary-ticker yfinance fetches in backtests — a
  public instance would proxy third-party load and needs a policy decision.
- Fonts load from Google Fonts with system fallbacks; a fully offline deploy
  may want them vendored.

## 12. What public hosted deployment still needs

1. A decision on scope: read-only showcase (disable saves + live fetches —
   simplest and safest) vs. interactive sandbox (needs per-session isolation).
2. Auth or hard isolation for the saved-work store if writes stay enabled.
3. Rate limiting and provider-call guards (or disabling the yfinance path).
4. Hosting targets + HTTPS + a reverse proxy in front of uvicorn (the dev
   server command above is not a production server configuration).
5. Backup/reset story for the SQLite file, or swapping saves to read-only
   demo content.
6. A final compliance-style pass on public wording (the educational/not-advice
   labels must survive any marketing edits).

Until those exist, the honest public story is: **clone it and run it
locally — two commands, no keys, fully deterministic.**
