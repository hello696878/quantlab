# QuantLab — Environment Doctor (Phase 39.0)

What `scripts\check_environment.ps1` checks, what it deliberately does not,
and how to read its output.

## What it checks

- **Python** — a `python` on PATH (informational; the venv matters more).
- **Backend venv** — `backend\venv\Scripts\python.exe` (this repo's real
  location), with `.venv\Scripts\python.exe` accepted as an alternate.
- **Backend dependency markers** — `backend\requirements.txt` and
  `backend\app\main.py` exist; a local import probe inside the venv
  (`import fastapi, pydantic, pytest`) confirms the core packages resolve.
- **Node / npm** — both on PATH, with versions printed.
- **Frontend dependency marker** — `frontend\package.json` and
  `frontend\node_modules` exist.
- **Docs** — the local demo guide and troubleshooting doc are present.
- **Port hints** — best-effort, read-only look at whether anything is
  already listening on 8000/3000 (wrapped in try/catch; purely
  informational and skipped gracefully where unavailable).

## What it does NOT check (on purpose)

- It does **not** run the test suite, the typecheck, or any build — so a
  green doctor is **not** proof the code works; it is proof the toolchain is
  present. Run the verification commands yourself
  (see [`COMMAND_REFERENCE.md`](COMMAND_REFERENCE.md)).
- It does **not** touch the network — no version lookups, no downloads, no
  provider probes. QuantLab's data policy (deterministic samples, fail-closed
  optional providers) extends to its tooling: a doctor that phoned home would
  contradict the platform it checks.
- It does **not** install or fix anything, start servers, change execution
  policy, require admin, or write to the repository.

## Reading the output

- `[ OK ]` — the marker was found. Presence, not correctness.
- `[MISS]` — the marker was not found; each miss prints the suggested
  user-run fix (e.g. `npm install`, recreating the venv).
- `[HINT]` — informational only (ports); a busy port is not an error — it
  may be your already-running backend.
- **Exit code** — 0 when everything was found, 1 when anything was missing
  (so you can script around it), and the summary line says which.

## Safe next steps after a green run

1. `.\scripts\run_backend.ps1` — start the backend (prints its command first).
2. `cd frontend; npm run dev` — start the frontend (always user-run).
3. `.\scripts\run_backend_tests.ps1` — run the suite; artifacts\ must be
   absent afterwards.
4. `.\scripts\run_frontend_typecheck.ps1` — typecheck.
5. `cd frontend; npm run build` — production build (always user-run).

The doctor never claims a pass/fail verdict about QuantLab itself — only
about the presence of the tools needed to run and verify it yourself.
