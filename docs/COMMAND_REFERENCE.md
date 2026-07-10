# QuantLab — Command Reference (Phase 39.0)

Copy-friendly Windows PowerShell commands. Everything here is **run by you**
— helper scripts print or wrap these, never more. Repo assumed at
`C:\quantlab`; the Python venv lives at `backend\venv`.

## Run

```powershell
# Backend dev server (http://localhost:8000, docs at /docs)
cd C:\quantlab\backend
venv\Scripts\uvicorn app.main:app --reload --port 8000

# Frontend dev server (user-run; http://localhost:3000)
cd C:\quantlab\frontend
npm run dev
```

## Verify

```powershell
# Backend test suite (~2,900 deterministic tests; artifacts\ must be absent after)
cd C:\quantlab
backend\venv\Scripts\python.exe -m pytest backend\tests -q

# Frontend typecheck
cd C:\quantlab\frontend
npx tsc --noEmit

# Production build (user-run)
cd C:\quantlab\frontend
npm run build
```

## Clean

```powershell
# Throwaway test-artifacts folder (should not exist after a suite run)
cd C:\quantlab
if (Test-Path .\artifacts) { Remove-Item -Recurse -Force .\artifacts }

# Next.js build cache only (frontend\.next)
.\scripts\clean_frontend_build_cache.ps1

# Futures CSV throwaway output (if you ran the normalize script)
Remove-Item -Recurse -Force C:\quantlab\backend\tests\_tmp_normalized_futures
```

## Git

```powershell
git status --short          # working tree at a glance
git branch --show-current   # current branch
git pull --rebase           # update local branch onto remote

git add -A
git commit -m "Add <thing> v1"

git push

git tag v<x.y.z>            # tag a release commit
git push origin v<x.y.z>    # push the tag
```

## Helper scripts (Phase 39.0 — inspect before running)

```powershell
.\scripts\check_environment.ps1        # read-only environment doctor
.\scripts\print_demo_commands.ps1      # print-only cheat sheet
.\scripts\run_backend.ps1              # starts uvicorn (prints command first)
.\scripts\run_backend_tests.ps1        # artifacts pre-clean + pytest
.\scripts\run_frontend_typecheck.ps1   # npx tsc --noEmit
.\scripts\clean_frontend_build_cache.ps1  # removes only frontend\.next
```

None of the scripts install packages, run `npm run dev`/`npm run build`,
download anything, change execution policy, or handle secrets.
