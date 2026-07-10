# QuantLab — Developer Onboarding (Phase 39.0)

The fastest honest path from `git clone` to a productive change. Companion
docs: [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md) (full architecture map) ·
[`COMMAND_REFERENCE.md`](COMMAND_REFERENCE.md) ·
[`TROUBLESHOOTING.md`](TROUBLESHOOTING.md).

## 1. Repo structure

```
quantlab/
├── backend/            FastAPI app (venv at backend\venv)
│   ├── app/            main.py + one package per lab + *_routes.py routers
│   └── tests/          pytest suite (~2,900 deterministic tests)
├── frontend/           Next.js 14 + TypeScript + Tailwind
│   └── src/            app/ (shell + safety pages), components/, lib/
├── scripts/            Python check/report scripts + PowerShell helpers (39.0)
├── configs/            futures instrument YAML specs
└── docs/               roadmap, limitations, demo/launch docs
```

## 2. Backend architecture in one paragraph

Every lab is a package with three files — `models.py` (strict Pydantic v2:
`extra="forbid"`, finite-float types so NaN/Infinity can't cross the API),
`sample.py` (hand-written deterministic sample data + a `DISCLAIMER`), and
`service.py` (pure functions, no I/O) — exposed by a `app/<lab>_routes.py`
router with `GET /<lab>/sample` + `POST /<lab>/analyze`, registered via
`include_router` in `app/main.py`. Older engines (backtests, options,
credit) define endpoints directly in `main.py`. Saved work uses local SQLite.

## 3. Frontend architecture in one paragraph

A single-page shell: `AppShell.tsx` holds the `View` union, `Sidebar.tsx` the
grouped nav, `page.tsx` the title registry + command palette + view renders.
Each lab pairs a typed client in `src/lib/<lab>.ts` (fetch wrappers +
formatting helpers) with a `src/components/<Lab>Panel.tsx` (sample load on
mount → request `useMemo` → debounced analyze with AbortController). Shared
primitives: `components/charts/LabCharts.tsx`, `components/math/`
(FormulaReference/SafeMath), `components/ui/` state components,
`components/controls/ShockSlider.tsx`.

## 4. Where things live

- New lab analytics → `backend/app/<lab>/` + `backend/app/<lab>_routes.py`
- New lab tests → `backend/tests/test_<lab>.py`
- New panel → `frontend/src/components/<Lab>Panel.tsx` + `frontend/src/lib/<lab>.ts`
- Navigation → `AppShell.tsx` (View union), `Sidebar.tsx` (group + icon),
  `page.tsx` (TITLES, palette entries, view render), `HomeDashboard.tsx` (card)
- Docs → `docs/ROADMAP.md` (phase entry) + `docs/LIMITATIONS.md` (honest paragraph)

## 5. Adding a new deterministic lab (the checklist)

1. Copy the shape of a recent package (e.g. `app/scenario_studio/`).
2. `models.py`: strict schemas; bound every score; `Literal` enums for ids.
3. `sample.py`: hand-written samples, fixed timestamps, a `DISCLAIMER`
   constant, catalogs for the frontend.
4. `service.py`: pure functions; guard every division; clip every score;
   raise `KeyError`/`ValueError` for bad ids (the route maps them to 422).
5. Router + `include_router` in `main.py` (follow the comment pattern).
6. Tests: endpoints, formula spot-checks vs hand-computed values, validation
   rejections, an `_assert_all_finite` walk of every response, and wording
   contracts if you generate text (no recommendation language).
7. Frontend lib + panel (copy a recent panel's skeleton), then wire the four
   navigation points.
8. Docs: ROADMAP phase entry, LIMITATIONS paragraph, READMEs.
9. Verify: `.\scripts\run_backend_tests.ps1` and
   `.\scripts\run_frontend_typecheck.ps1`. The production build is user-run.

## 6. Testing rules

- Tests must be deterministic and offline: real `TestClient` against the real
  app with the real sample data.
- **Never depend on a live provider.** The only external path (yfinance) is
  monkeypatched in backtest API tests, and the built-in KO/PEP pairs demo has
  a network-free fixture (`app/data.py::sample_pairs_close`). Follow that
  pattern for anything new: opt-in, fail-closed, fixture-backed.
- After the suite, the repo-root `artifacts\` folder must not exist.

## 7. Typecheck

`cd frontend; npx tsc --noEmit` (or `.\scripts\run_frontend_typecheck.ps1`).
Strict TypeScript; avoid `any`. `tsconfig.tsbuildinfo` is tracked — commit it
with your change. There is currently no frontend test framework.

## 8. Conventions worth copying (inferred from the repo)

- Theme via CSS tokens (`var(--text-hi)`, `var(--accent)` …), never raw hex
  or Tailwind numeric color classes for text on dark cards.
- Charts only through the shared `LabCharts` wrappers (non-finite filtering,
  empty states, `ariaLabel`).
- Formulas only through `FormulaReference` (+ `collapsible` for big sets).
- Every generated report ends with the lab's disclaimer; wording contracts
  ("no recommendation language", "never claims tests ran") are tests.
- Honest labels beat impressive ones — every hero carries a data-mode badge.
- One phase = one focused change set + tests + docs, committed by the user.

## Ground rules (unchanged by this doc)

Deterministic educational sample data; no live trading; no telemetry; not
investment advice; not production compliance/risk infrastructure.
