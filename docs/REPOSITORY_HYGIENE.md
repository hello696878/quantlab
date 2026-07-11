# QuantLab — Repository Hygiene (Phase 41.0)

What belongs in the repo, what never does, and how to check before you
commit or go public. Companion docs: [`SECURITY_AND_SECRETS.md`](SECURITY_AND_SECRETS.md) ·
[`../CONTRIBUTING.md`](../CONTRIBUTING.md) · [`CI.md`](CI.md) ·
[`VERSION_MANIFEST.md`](VERSION_MANIFEST.md). Read-only status helper:
`scripts\check_repo_hygiene.ps1`.

## Committed (tracked on purpose)

Source (`backend/app`, `frontend/src`), tests, `configs/` instrument YAML,
curated `docs/`, example fixtures (e.g. `backend/tests/fixtures`,
`frontend/.env.example`), helper scripts, CI workflow, `VERSION`,
`CHANGELOG.md`, `package-lock.json` — and, by standing project decision,
`frontend/tsconfig.tsbuildinfo` (see below).

## Never committed (and gitignored)

- `.env` and `.env.*` (except `.env.example`) — environment/secret material.
- Virtualenvs (`.venv/`, `venv/` — the real one lives at `backend\venv`).
- `node_modules/`, `frontend/.next/`, `out/`, `dist/`, `build/`.
- `artifacts/`, `data/`, `models/`, `checkpoints/`, `mlruns/`,
  `reports/generated|experiments/` — local data/ML outputs.
- Caches: `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`,
  `.coverage`, `htmlcov/`.
- The local SQLite DB (`backend/data/*.db`).
- OS/editor/scratch noise: `.DS_Store`, `Thumbs.db`, `*.log`, `*.tmp`.
- Temporary screenshots and local data dumps (curate real captures into
  `docs/screenshots/` deliberately; bulk data files `*.parquet|pkl|h5|…` are
  ignored globally).

## Branch / commit / tag conventions

Work lands on `main` as small, tested change sets: **`Add <feature> v1`**
followed by **`Review <feature> v1`**; the user tags after review as
**`v4.xx.0-short-feature-name-v1`** and pushes the tag manually (full policy:
[`VERSION_MANIFEST.md`](VERSION_MANIFEST.md)).

## The tsbuildinfo special case (resolved in Phase 42.3)

`frontend/tsconfig.tsbuildinfo` was **listed in `.gitignore` but tracked**
for many phases (ignore rules only affect untracked files). Resolved at
release-freeze time: the file is generated output of the current TypeScript
config (`"incremental": true`), so it was untracked via
`git rm --cached frontend/tsconfig.tsbuildinfo` and the existing ignore line
now governs it. The local file is untouched; it simply no longer appears in
diffs. Do not re-add it.

## Cleaning generated files safely

Only ever delete the specific known-generated paths — never broad globs:

```powershell
.\scripts\clean_frontend_build_cache.ps1          # removes exactly frontend\.next
if (Test-Path .\artifacts) { Remove-Item -Recurse -Force .\artifacts }
Remove-Item -Recurse -Force backend\tests\_tmp_normalized_futures  # if created
```

## Inspecting before a commit

```powershell
git status --short          # anything unexpected?
git diff --stat             # size/shape of the change
git diff --cached           # exactly what will be committed
git ls-files --others --exclude-standard   # untracked files git would ignore adding
```

If `git status` shows a file you don't recognize, investigate before `git add -A`.

## Avoiding committed credentials

- Real keys live only in your environment (or an untracked `.env`); the repo
  needs none to run — see [`SECURITY_AND_SECRETS.md`](SECURITY_AND_SECRETS.md).
- Before committing: `git diff --cached | Select-String -Pattern "api_key","secret","password","token" -SimpleMatch` —
  expect only documented env-var *names* (e.g. `FRED_API_KEY`) and
  negation/policy sentences.
- If one slips through anyway: rotate it immediately, then follow the
  accidental-commit steps in the security doc.

## Checking for oversized files

```powershell
# Largest tracked files (top 20)
git ls-files | ForEach-Object { Get-Item $_ -ErrorAction SilentlyContinue } |
  Sort-Object Length -Descending | Select-Object -First 20 Length, FullName
```

Anything unexpectedly large (data dumps, media, archives) should be removed
before it enters history — history rewrites after the fact are painful.

## Before making the repo public

1. Run the safety/overclaim and secret searches (patterns in the Phase 41.0
   ROADMAP entry; also `git log --all -p -S "API_KEY"`-style spot checks if
   paranoid about history).
2. Walk [`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md) Part 1 once.
3. Check `docs/screenshots/` for personal paths or stale claims.
4. Confirm `README.md` + `LIMITATIONS.md` still say what is true.
5. Confirm CI is green on the exact commit you publish.
