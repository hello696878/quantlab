# QuantLab — Playwright Setup (Phase 43.0)

One-time setup for the browser E2E harness. Day-to-day usage lives in
[`BROWSER_E2E_RUNBOOK.md`](BROWSER_E2E_RUNBOOK.md).

## 1. Dependency

`@playwright/test` is a frontend devDependency (see `frontend/package.json`).
A normal install brings it in:

```powershell
cd C:\quantlab\frontend
npm install
```

## 2. Browser — no download required on the reference setup

The config drives the **OS-installed Microsoft Edge**
(`channel: "msedge"`), so on the reference Windows machine there is nothing
to install. Alternatives:

```powershell
$env:E2E_BROWSER_CHANNEL = "chrome"   # use OS-installed Chrome instead
```

or, to use Playwright's own Chromium build (downloads a browser — a
deliberate, manual step, never done automatically by any script here):

```powershell
npx playwright install chromium
$env:E2E_BROWSER_CHANNEL = ""         # empty = bundled Chromium
```

Failure *videos* are off in v1 because they would require Playwright's
downloadable ffmpeg component (`npx playwright install ffmpeg` if you ever
want them); traces and failure screenshots are the evidence instead.

## 3. Running tests

Start the backend and a frontend yourself (the harness never starts
servers), then from `C:\quantlab\frontend`:

```powershell
npm run e2e              # everything
npm run e2e:frozen       # frozen-demo guard only
npm run e2e:responsive   # viewport geometry guard only
```

## 4. Base URL configuration

| Env var | Default | Meaning |
|---|---|---|
| `E2E_BASE_URL` | `http://localhost:3000` | Frontend under test (use `http://localhost:3100` for the production server) |
| `E2E_BROWSER_CHANNEL` | `msedge` | Browser channel; `chrome`, or empty for bundled Chromium |

The backend is expected on `http://localhost:8000` (reached through the
frontend's `/api` rewrite — tests never call it cross-origin).

## 5. Artifact locations

All generated output goes under `C:\quantlab\artifacts\e2e\`
(`test-results\`, `playwright-report\`) — gitignored via the repo-root
`artifacts/` rule and safe to delete. `npm run e2e:report` opens the HTML
report. Frozen release evidence (`docs\screenshots\release_*.png`) is never
written by the harness.

## 6. Troubleshooting

- **First run against a freshly started dev server is slow / used to flake** —
  `next dev` compiles pages on demand and hydrates slowly on the first
  request. The harness waits for real interactivity (the mounted TopBar
  clock rendering HH:MM:SS is its hydration witness — independent of backend
  health) with generous budgets, so a cold first run just takes longer; it
  should not fail. If it
  ever does, re-read the failure message — `gotoView` errors include the
  current URL, h1, and visible buttons.
- **Prod-mode (:3100) pages render unstyled / tests fail in setup** — `next
  dev` and `next start` share the `.next` directory; a dev server running
  alongside (or after) the production server corrupts the served assets.
  Stop both, `npm run build`, then `npx next start --port 3100` fresh —
  never run both at once.
- **"Executable doesn't exist … ffmpeg"** — video was enabled without the
  ffmpeg component; keep `video: "off"` or run `npx playwright install ffmpeg`.
- **"BLOCKED" from wrapper scripts / connection refused** — the backend or
  frontend isn't running; start them first (runbook §3).
- **Pairs test times out** — the KO/PEP backtest takes ~5–15 s on the
  backend; check the backend terminal for errors before suspecting the test.
- **Frozen-metric assertion failed** — read
  [`FROZEN_DEMO_REGRESSION_GUARD.md`](FROZEN_DEMO_REGRESSION_GUARD.md) §3
  before touching the assertion.

## 7. CI status

**E2E is not part of the push/PR CI gate.** Since Phase 45.0 a separate,
**manually triggered** workflow (`Browser E2E Preflight`,
`.github/workflows/browser-e2e.yml`) can run the suite in an isolated
Ubuntu runner — it installs its own Chromium there, builds/starts the app,
and uploads evidence artifacts ([`CI_BROWSER_E2E.md`](CI_BROWSER_E2E.md)).
Main CI (`ci.yml`) is unchanged: backend tests + frontend typecheck/build.

E2E green is a regression signal only — not a production, trading, or
compliance certification. Deterministic fixtures are intentional; no live
data is required.
