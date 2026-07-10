# QuantLab — Security & Secrets Policy (Phase 41.0)

The standing policy for a repo that is designed to need no secrets at all.
This is a policy document, **not a formal security audit** — none has been
performed, and none is claimed.

## The policy, in one paragraph

QuantLab holds **no secrets, no API keys, no credentials, no tokens** — the
platform runs fully offline on deterministic sample data, so nothing in the
repo needs to authenticate to anything. There is no broker, exchange, or
wallet integration of any kind (and no trading capability to secure), no
telemetry, no analytics tracking, no login system, and no cloud sync. CI
uses no secrets (`permissions: contents: read`). This must stay true: any
change that would introduce a required secret is a design smell to be
challenged first.

## The one optional key that may exist locally

The globe's **opt-in** FRED macro adapter reads `FRED_API_KEY` from your
local environment if you choose to enable `GLOBE_FRED_ENABLED`. It is
disabled by default, fails closed to static data, is never required, never
committed (`.env*` is gitignored; only `.env.example` is tracked), and never
sent to the frontend. The optional yfinance paths need no key at all.

## No live-data guarantees

External providers (yfinance historical downloads, optional FRED, optional
delayed globe quotes) can be unavailable at any time; every path fails
closed or shows a friendly error, tests never rely on them, and **no output
anywhere is live or guaranteed current**.

## If a secret is accidentally committed

1. **Rotate/revoke the credential immediately** — treat it as compromised
   the moment it entered a commit, even a local one. Rotation is the fix;
   everything below is cleanup.
2. Remove it from the working tree and commit the removal.
3. If it was pushed, rewrite history for the affected paths (e.g.
   `git filter-repo`) and force-push only after coordinating — and rely on
   the rotation, not the rewrite, for actual safety (forks/caches may
   retain it).
4. Add the file/pattern to `.gitignore` and re-run the secret search below.

## Safe local environment-variable practice

- Keep real values in your shell profile or an untracked `.env`; commit only
  `.env.example` placeholders with no real values.
- Never echo secrets into logs, scripts, screenshots, or demo recordings
  (the screenshot checklist's "no personal paths" rule extends to env vars).
- The helper scripts in `scripts\` neither read nor write secrets — by
  documented design.

## Periodic secret search (run before publishing)

```powershell
cd C:\quantlab
git grep -inE "api_key|apikey|secret|password|token|BEGIN (RSA )?PRIVATE KEY|ghp_|sk-|AKIA" -- . ":!docs" ":!*.md"
```

Expected hits: documented env-var *names* (`FRED_API_KEY` in globe config
code) and nothing else. Anything unexpected → treat as an incident (above).

## Security limitations (honest)

- Single-user local application: no authentication, authorization, session
  management, or rate limiting — do not host it publicly as-is (see
  [`DEPLOYMENT_READINESS.md`](DEPLOYMENT_READINESS.md)).
- Dependencies are pinned via `requirements.txt`/`package-lock.json` but not
  monitored by an update bot; review advisories manually when bumping.
- No formal threat model, penetration test, or third-party audit exists —
  and this document does not claim otherwise.
- The uvicorn `--reload` dev command is a development server, not a hardened
  production configuration.
