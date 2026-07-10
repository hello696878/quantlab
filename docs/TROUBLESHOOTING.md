# QuantLab — Troubleshooting (Phase 39.0)

Common local issues and their fixes. All commands are Windows PowerShell,
run by you. First stop: `.\scripts\check_environment.ps1` (read-only).

## 1. `uvicorn` not found

The dev server must run from the repo venv:

```powershell
cd C:\quantlab\backend
venv\Scripts\uvicorn app.main:app --reload --port 8000
```

If `venv\Scripts\uvicorn.exe` is missing, install deps into the venv
(yourself): `venv\Scripts\python.exe -m pip install -r requirements.txt`.

## 2. Python venv missing

This repo's venv lives at `backend\venv` (not `.venv`). Recreate it:

```powershell
cd C:\quantlab\backend
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 3. Backend import error on startup

Almost always a missing dependency in the venv (see #2) or running uvicorn
from the wrong directory — it must be `backend\` so `app.main:app` resolves.

## 4. `pytest` missing

You're using global Python instead of the venv. Run tests as:

```powershell
cd C:\quantlab
backend\venv\Scripts\python.exe -m pytest backend\tests -q
```

## 5. `frontend\node_modules` missing

```powershell
cd C:\quantlab\frontend
npm install
```

## 6. `npx tsc` not found

Install Node 18+ (which includes npx), then `npm install` in `frontend\` so
TypeScript is present in `node_modules`.

## 7. Next.js behaving strangely after big changes

Clear the build cache (only `frontend\.next` is removed):

```powershell
.\scripts\clean_frontend_build_cache.ps1
```

Then re-run `npm run dev` (yourself).

## 8. Port 8000 already in use

Find and stop the process using it (or start uvicorn with another `--port`
and set `BACKEND_URL` accordingly):

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen | Select-Object OwningProcess
Get-Process -Id <pid>
```

## 9. Port 3000 already in use

Same approach with `-LocalPort 3000`, or `npm run dev -- --port 3001`.

## 10. yfinance / external provider unavailable

Expected behavior, not a bug: arbitrary-ticker backtests show a friendly
error; the built-in KO/PEP pairs demo always works offline via its
deterministic fixture; the globe's optional FRED/quote adapters are disabled
by default and fail closed to static data. For demos, stay on the
deterministic paths (see `docs/LOCAL_DEMO_GUIDE.md`). External availability
is never guaranteed.

## 11. NaN / Infinity in the UI

Should never happen — backends guarantee finite payloads and shared charts
filter non-finite values. If you see one: note the module and inputs, check
the browser console, and treat it as a bug to fix (the lab's test file has
an `_assert_all_finite` pattern to extend).

## 12. Formulas not rendering

KaTeX is local (no CDN). A malformed formula falls back to a contained code
block by design — the page keeps working. If **no** formula renders, check
that `katex/dist/katex.min.css` is imported in `app/layout.tsx` and that
`npm install` completed.

## 13. Command palette route missing

Every view needs four wiring points: the `View` union (`AppShell.tsx`), a
sidebar group entry (`Sidebar.tsx`), TITLES + palette entries + the view
render (`page.tsx`). If a palette entry does nothing, the view render in
`page.tsx` is the usual missing piece.

## 14. PowerShell won't run the helper scripts

Your execution policy may block local scripts. The helper scripts **never
change the policy** (and you shouldn't need to globally either) — run a
one-off bypass for the current process only, then decide for yourself:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check_environment.ps1
```

All helper scripts are short and readable — inspect them before running;
none install anything, start the frontend, download code, or touch secrets.
